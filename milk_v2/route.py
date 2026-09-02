from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid

from . import evaluate, summary, train
from .providers import baseten, modal_gpu


CODE_VERSION = "milk.route-propose.v6"
TRUSS_VERSION = "0.18.28"
BRANCHES = {"bf16", "dynamic_fp8", "static_fp8"}
IMAGE = re.compile(r"ghcr\.io/milkinfrastructure/milk-man-serve@sha256:[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
TERMINAL_FAILURE = {
    "BUILD_FAILED",
    "BUILD_STOPPED",
    "DEPLOY_FAILED",
    "FAILED",
    "INACTIVE",
    "UNHEALTHY",
}
READY = {"ACTIVE", "SCALED_TO_ZERO"}
MAX_PROVIDER_OUTPUT_BYTES = 4 * 1024 * 1024


class RouteError(ValueError):
    pass


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        provider_calls: int,
        *,
        ambiguous: bool = False,
        code: str | None = None,
    ):
        super().__init__(message)
        self.provider_calls = provider_calls
        self.ambiguous = ambiguous
        self.code = code


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RouteError(f"{name} is required")
    return value


def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise RouteError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise RouteError(f"{name} must be in {minimum}..{maximum}")
    return value


def _candidate_protocols(base_url: str, artifact_sha256: str) -> dict:
    protocol = "chat_completions"
    normalized = base_url.rstrip("/")
    binding_sha256 = hashlib.sha256(
        summary.canonical(
            {
                "artifact_sha256": artifact_sha256,
                "base_url": normalized,
                "protocol": protocol,
            }
        )
    ).hexdigest()
    return {
        protocol: {
            "base_url": normalized,
            "binding_sha256": binding_sha256,
        }
    }


def _object(store, key: str) -> tuple[dict, bytes]:
    body = store.get(key).body
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RouteError(f"{key} is invalid JSON") from error
    if not isinstance(value, dict):
        raise RouteError(f"{key} must contain an object")
    return value, body


def _artifacts(store, keys: list[str]) -> list[dict]:
    return [
        {"key": key, "sha256": summary.digest(store.get(key).body)}
        for key in dict.fromkeys(keys)
    ]


def _served_model(branch: str) -> str:
    return "milk-qwen3.5-0.8b-" + branch.replace("_", "-")


def _validated_quantization(branch: str, value: object) -> dict:
    if not isinstance(value, dict) or value.get("kind") != branch:
        raise RouteError("sealed quantization identity differs from the selected branch")
    count = value.get("quantized_linear_count")
    if type(count) is not int or count < 0 or (branch == "bf16") != (count == 0):
        raise RouteError("sealed quantized linear count is invalid")
    if branch != "bf16" and value.get("torchao_version") != "0.15.0":
        raise RouteError("sealed FP8 implementation identity differs")
    if branch == "static_fp8":
        scale = value.get("activation_scale")
        if not isinstance(scale, (int, float)) or isinstance(scale, bool) or not 0 < scale < 1:
            raise RouteError("sealed static-FP8 activation scale is invalid")
    return value


def _inputs(store, settings, runtime) -> tuple[dict, dict, dict, dict, dict]:
    model_reference = train.current(store, settings, runtime)
    evaluation_reference = evaluate.current(store, settings, runtime)
    if model_reference is None or evaluation_reference is None:
        raise RouteError("a current model and sealed evaluation are required")
    model, model_body = _object(store, model_reference["key"])
    group, group_body = _object(store, evaluation_reference["key"])
    if (
        summary.digest(model_body) != model_reference["sha256"]
        or summary.digest(group_body) != evaluation_reference["sha256"]
    ):
        raise RouteError("model or evaluation digest differs")
    sealed_reference = group.get("sealed")
    if not isinstance(sealed_reference, dict):
        raise RouteError("evaluation group has no sealed result")
    sealed, sealed_body = _object(store, sealed_reference.get("key", ""))
    winner_branch = group.get("winner", {}).get("branch")
    if (
        summary.digest(sealed_body) != sealed_reference.get("sha256")
        or group.get("profile") != settings.profile
        or sealed.get("profile") != settings.profile
        or winner_branch not in BRANCHES
        or sealed.get("branch") != winner_branch
        or sealed.get("split") != "sealed"
        or sealed.get("model", {}).get("uuid") != model_reference["uuid"]
    ):
        raise RouteError("sealed evaluation is not the selected winner")
    if settings.profile == "production" and winner_branch == "static_fp8":
        raise RouteError("prototype static FP8 cannot produce a production route")
    _validated_quantization(winner_branch, sealed.get("quantization"))
    return model_reference, model, evaluation_reference, group, sealed


def _artifact(
    settings,
    runtime,
    model_reference: dict,
    model: dict,
    evaluation_reference: dict,
    group: dict,
    sealed: dict,
    serving_provider: str,
) -> tuple[dict, str, str]:
    image = _required("MILK_SERVE_IMAGE")
    if IMAGE.fullmatch(image) is None:
        raise RouteError("MILK_SERVE_IMAGE must pin the reviewed GHCR image by sha256 digest")
    accelerator = os.environ.get("MILK_CANDIDATE_ACCELERATOR", "H100")
    if accelerator not in {"H100", "H200"}:
        raise RouteError("MILK_CANDIDATE_ACCELERATOR must be H100 or H200")
    output_sha256 = model.get("output_sha256")
    provider = model.get("provider")
    if (
        not isinstance(output_sha256, str)
        or SHA256.fullmatch(output_sha256) is None
        or not isinstance(provider, dict)
        or provider.get("name") != "baseten"
        or not isinstance(provider.get("job_id"), str)
        or IDENTIFIER.fullmatch(provider["job_id"]) is None
    ):
        raise RouteError("model has no exact Baseten checkpoint identity")
    branch = group["winner"]["branch"]
    identity = {
        "schema_version": "milk.candidate-artifact-identity.v3",
        "code_version": CODE_VERSION,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "model": model_reference,
        "model_output_sha256": output_sha256,
        "training_provider": {
            "name": "baseten",
            "project_id": provider.get("project_id"),
            "job_id": provider["job_id"],
        },
        "evaluation": evaluation_reference,
        "winner": group.get("winner"),
        "sealed": group["sealed"],
        "serve_image": image,
        "accelerator": accelerator,
        "serving_provider": serving_provider,
        "server": {
            "model": _served_model(branch),
            "branch": branch,
            "quantization": sealed["quantization"],
            "credential_env": "MILK_CANDIDATE_API_KEY",
            "baseten_secret": "milk-candidate-api-key",
        },
        "student_base": {
            "model_repo": runtime.student_base.model_repo,
            "model_revision": runtime.student_base.model_revision,
            "digest": runtime.student_base.digest,
        },
        "config_digest": runtime.digest,
    }
    artifact_sha256 = summary.digest(identity)
    candidate_uuid = str(
        uuid.uuid5(uuid.NAMESPACE_URL, "milk:candidate:" + artifact_sha256)
    )
    return identity, artifact_sha256, candidate_uuid


def _names(artifact_sha256: str) -> tuple[str, str]:
    suffix = artifact_sha256[:20]
    return "milk-qwen35-" + suffix, "sealed-" + suffix


def _truss_config(identity: dict, artifact_sha256: str, model_name: str) -> dict:
    quantization = identity["server"]["quantization"]
    environment = {
        "MILK_CANDIDATE_ARTIFACT_SHA256": artifact_sha256,
        "MILK_CANDIDATE_BRANCH": identity["server"]["branch"],
        "MILK_CANDIDATE_LINEAR_COUNT": str(quantization["quantized_linear_count"]),
    }
    if "activation_scale" in quantization:
        environment["MILK_CANDIDATE_ACTIVATION_SCALE"] = str(quantization["activation_scale"])
    return {
        "model_name": model_name,
        "base_image": {"image": identity["serve_image"]},
        "docker_server": {
            "start_command": "python /opt/milk/server.py",
            "server_port": 8000,
            "predict_endpoint": "/v1/chat/completions",
            "readiness_endpoint": "/health",
            "liveness_endpoint": "/health",
        },
        "environment_variables": environment,
        "secrets": {"milk-candidate-api-key": None},
        "resources": {
            "accelerator": identity["accelerator"],
            "cpu": "4",
            "memory": "32Gi",
        },
        "runtime": {
            "predict_concurrency": 1,
            "streaming_read_timeout": 120,
            "enable_tracing_data": False,
            "enable_debug_logs": False,
        },
        "training_checkpoints": {
            "download_folder": "/tmp/training_checkpoints",
            "artifact_references": [
                {
                    "training_job_id": identity["training_provider"]["job_id"],
                    "paths": ["merged/*"],
                }
            ],
        },
    }


def _safe_detail(value: str) -> str:
    return " ".join(value.split())[-1024:]


def _push(config: dict, model_name: str, deployment_name: str) -> dict:
    api_key = _required("BASETEN_API_KEY")
    team = os.environ.get("BASETEN_TEAM_NAME")
    if any(ord(character) < 33 for character in api_key) or (
        team is not None and (not team or any(ord(character) < 32 for character in team))
    ):
        raise RouteError("Baseten credential or team name is invalid")
    timeout = _integer("MILK_ROUTE_TIMEOUT_SECONDS", 600, 30, 1800)
    with tempfile.TemporaryDirectory(prefix="milk-route-") as directory:
        root = Path(directory)
        truss = root / "truss"
        home = root / "home"
        truss.mkdir(mode=0o700)
        home.mkdir(mode=0o700)
        (truss / "config.yaml").write_bytes(summary.canonical(config))
        trussrc = home / ".trussrc"
        trussrc.write_text(
            "[baseten]\n"
            "remote_provider = baseten\n"
            "auth_type = api_key\n"
            f"api_key = {api_key}\n"
            "remote_url = https://app.baseten.co\n"
        )
        trussrc.chmod(0o600)
        command = [
            "uvx",
            "--from",
            f"truss=={TRUSS_VERSION}",
            "truss",
            "push",
            str(truss),
            "--remote",
            "baseten",
            "--model-name",
            model_name,
            "--deployment-name",
            deployment_name,
            "--no-wait",
            "--non-interactive",
            "--disable-truss-download",
            "--output",
            "json",
            "--labels",
            json.dumps(
                {"milk-artifact-sha256": config["environment_variables"]["MILK_CANDIDATE_ARTIFACT_SHA256"]},
                separators=(",", ":"),
            ),
        ]
        if team:
            command.extend(("--team", team))
        environment = {
            "HOME": str(home),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "TMPDIR": directory,
            "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR", str(Path.home() / ".cache" / "uv")),
            "UV_NO_PROGRESS": "1",
        }
        try:
            completed = subprocess.run(
                command,
                cwd=truss,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ProviderError(
                f"Baseten submission outcome is ambiguous: {error}", 1, ambiguous=True
            ) from error
        if len(completed.stdout.encode()) > MAX_PROVIDER_OUTPUT_BYTES:
            raise ProviderError("Truss returned oversized output", 1, ambiguous=True)
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError:
            value = None
        if completed.returncode != 0:
            detail = _safe_detail(completed.stderr)
            if "Custom base images not supported for your organization" in detail:
                raise ProviderError(
                    "Baseten custom base images are not enabled for this organization",
                    1,
                    code="custom_base_image_not_enabled",
                )
            raise ProviderError(
                f"Truss submission failed: {detail or 'no detail'}", 1, ambiguous=True
            )
        if not isinstance(value, dict):
            raise ProviderError("Truss returned invalid JSON", 1, ambiguous=True)
        return value


def _matching_deployment(client: baseten.Client, model_name: str, deployment_name: str):
    try:
        models = [model for model in client.models() if model.get("name") == model_name]
    except baseten.ProviderError as error:
        raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
    if len(models) > 1:
        raise ProviderError(
            "multiple Baseten models match the deterministic name", client.calls, ambiguous=True
        )
    if not models:
        return None
    model_id = models[0].get("id")
    if not isinstance(model_id, str) or IDENTIFIER.fullmatch(model_id) is None:
        raise ProviderError("Baseten model identity is invalid", client.calls)
    try:
        deployments = [
            deployment
            for deployment in client.deployments(model_id)
            if deployment.get("name") == deployment_name
        ]
    except baseten.ProviderError as error:
        raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
    if len(deployments) > 1:
        raise ProviderError(
            "multiple Baseten deployments match the deterministic name", client.calls, ambiguous=True
        )
    if not deployments:
        raise ProviderError(
            "deterministic Baseten model exists without its deployment", client.calls, ambiguous=True
        )
    return models[0], deployments[0]


def _ids_from_push(value: dict) -> tuple[str, str] | None:
    model_id = value.get("model_id")
    deployment_id = value.get("model_version_id")
    if (
        isinstance(model_id, str)
        and isinstance(deployment_id, str)
        and IDENTIFIER.fullmatch(model_id)
        and IDENTIFIER.fullmatch(deployment_id)
    ):
        return model_id, deployment_id
    return None


def _http_json(
    method: str,
    url: str,
    api_key: str,
    body: dict | None,
    timeout: int,
    authorization: str,
) -> tuple[dict, bytes]:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ProviderError("candidate endpoint is invalid", 0)
    raw = None if body is None else summary.canonical(body)
    request = urllib.request.Request(
        url,
        data=raw,
        method=method,
        headers={
            "Authorization": authorization + " " + api_key,
            "Accept": "application/json",
            **({"Content-Type": "application/json"} if raw is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read(MAX_PROVIDER_OUTPUT_BYTES + 1)
    except urllib.error.HTTPError as error:
        detail = _safe_detail(error.read(4096).decode("utf-8", "replace"))
        raise ProviderError(f"candidate returned HTTP {error.code}: {detail}", 1) from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ProviderError(
            f"candidate request outcome is ambiguous: {error}", 1, ambiguous=True
        ) from error
    if len(payload) > MAX_PROVIDER_OUTPUT_BYTES:
        raise ProviderError("candidate response is oversized", 1)
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderError("candidate returned invalid JSON", 1) from error
    if not isinstance(value, dict):
        raise ProviderError("candidate returned a non-object", 1)
    return value, payload


def _smoke(
    api_key: str,
    base_url: str,
    artifact_sha256: str,
    quantization: dict,
    timeout: int,
    authorization: str,
) -> tuple[dict, int]:
    branch = quantization["kind"]
    served_model = _served_model(branch)
    health, health_body = _http_json(
        "GET", base_url + "/health", api_key, None, timeout, authorization
    )
    if health != {
        "status": "ok",
        "model": served_model,
        "artifact_sha256": artifact_sha256,
        "quantization": branch,
        "quantized_linear_count": quantization["quantized_linear_count"],
    }:
        raise ProviderError("candidate health identity differs", 1)
    chat, chat_body = _http_json(
        "POST",
        base_url + "/v1/chat/completions",
        api_key,
        {
            "model": served_model,
            "messages": [{"role": "user", "content": "Reply with milk."}],
            "max_tokens": 4,
            "stream": False,
        },
        timeout,
        authorization,
    )
    choices = chat.get("choices")
    if (
        chat.get("object") != "chat.completion"
        or chat.get("model") != served_model
        or not isinstance(choices, list)
        or len(choices) != 1
        or not isinstance(choices[0], dict)
        or not isinstance(choices[0].get("message", {}).get("content"), str)
    ):
        raise ProviderError("candidate Chat Completions response is invalid", 2)
    return {
        "schema_version": "milk.candidate-smoke.v2",
        "health_sha256": summary.digest(health_body),
        "chat_sha256": summary.digest(chat_body),
        "model": served_model,
        "artifact_sha256": artifact_sha256,
    }, 2


def _advance_status(store, settings, candidate: dict, proposal: dict) -> str:
    key = settings.scope_prefix + "status/current.json"
    value, unused = _object(store, key)
    if value.get("schema_version") != "milk.status.v2" or value.get("scope_id") != settings.scope_id:
        raise RouteError("current status identity differs")
    summary._advance(
        store,
        key,
        {**value, "candidate": candidate, "proposal": proposal, "next_action": "operator-sign-route"},
    )
    return key


def current(store, settings) -> dict | None:
    try:
        status, unused = _object(store, settings.scope_prefix + "status/current.json")
        candidate_reference = status.get("candidate")
        proposal_reference = status.get("proposal")
        if not isinstance(candidate_reference, dict) or not isinstance(proposal_reference, dict):
            return None
        candidate, candidate_body = _object(store, candidate_reference.get("key", ""))
        proposal, proposal_body = _object(store, proposal_reference.get("key", ""))
    except FileNotFoundError:
        return None
    if (
        candidate_reference.get("schema_version") != "milk.candidate-reference.v2"
        or proposal_reference.get("schema_version") != "milk.route-proposal-reference.v3"
        or candidate_reference.get("scope_id") != settings.scope_id
        or proposal_reference.get("scope_id") != settings.scope_id
        or candidate_reference.get("sha256") != summary.digest(candidate_body)
        or proposal_reference.get("sha256") != summary.digest(proposal_body)
        or candidate.get("schema_version") != "milk.candidate.v2"
        or proposal.get("schema_version") != "milk.route-proposal.v3"
        or candidate.get("candidate_uuid") != candidate_reference.get("uuid")
        or proposal.get("proposal_uuid") != proposal_reference.get("uuid")
        or proposal.get("candidate") != candidate_reference
        or proposal.get("candidate_artifact_sha256") != candidate.get("artifact_sha256")
        or not isinstance(candidate.get("provider"), dict)
        or not isinstance(candidate["provider"].get("base_url"), str)
        or proposal.get("candidate_protocols")
        != _candidate_protocols(
            candidate["provider"]["base_url"], candidate["artifact_sha256"]
        )
    ):
        return None
    return {"candidate": candidate_reference, "proposal": proposal_reference}


def _finalize(
    store,
    settings,
    identity: dict,
    artifact_sha256: str,
    candidate_uuid: str,
    provider: dict,
    base_url: str,
    candidate_api_key_env: str,
    smoke: dict,
    prefix: str,
    provider_calls: int,
) -> dict:
    candidate_key = settings.scope_prefix + f"m/{candidate_uuid}/serve.json"
    candidate = {
        "schema_version": "milk.candidate.v2",
        "candidate_uuid": candidate_uuid,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "artifact_sha256": artifact_sha256,
        "identity": identity,
        "provider": provider,
        "smoke": smoke,
    }
    candidate_body = summary.canonical(candidate)
    store.create_same(candidate_key, candidate_body)
    candidate_reference = {
        "schema_version": "milk.candidate-reference.v2",
        "scope_id": settings.scope_id,
        "uuid": candidate_uuid,
        "key": candidate_key,
        "sha256": summary.digest(candidate_body),
        "artifact_sha256": artifact_sha256,
    }
    candidate_protocols = _candidate_protocols(base_url, artifact_sha256)
    candidate_basis_points = _integer(
        "MILK_ROUTE_CANDIDATE_BPS", 10_000 if settings.profile == "mechanics" else 100, 1, 10_000
    )
    proposal_identity = {
        "schema_version": "milk.route-proposal-identity.v4",
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "candidate": candidate_reference,
        "candidate_artifact_sha256": artifact_sha256,
        "candidate_protocols": candidate_protocols,
        "candidate_basis_points": candidate_basis_points,
        "fallback": "before_first_byte",
    }
    proposal_sha256 = summary.digest(proposal_identity)
    proposal_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:route-proposal:" + proposal_sha256))
    proposal_key = settings.scope_prefix + f"p/{proposal_uuid}.json"
    proposal = {
        **proposal_identity,
        "schema_version": "milk.route-proposal.v3",
        "proposal_uuid": proposal_uuid,
        "proposal_sha256": proposal_sha256,
        "candidate_api_key_env": candidate_api_key_env,
        "operator_action": "sign-and-publish-with-milk-parlor",
    }
    proposal_body = summary.canonical(proposal)
    store.create_same(proposal_key, proposal_body)
    proposal_reference = {
        "schema_version": "milk.route-proposal-reference.v3",
        "scope_id": settings.scope_id,
        "uuid": proposal_uuid,
        "key": proposal_key,
        "sha256": summary.digest(proposal_body),
    }
    smoke_key = prefix + "smoke.json"
    store.create_same(smoke_key, summary.canonical(smoke))
    status_key = _advance_status(store, settings, candidate_reference, proposal_reference)
    result_key = prefix + "result.json"
    result = {
        "schema_version": "milk.route-propose-result.v3",
        "job_id": artifact_sha256,
        "state": "progressed",
        "next": "operator-sign-route",
        "candidate": candidate_reference,
        "proposal": proposal_reference,
        "provider": provider,
        "artifact_keys": [candidate_key, proposal_key, smoke_key, status_key, result_key],
    }
    store.create_same(result_key, summary.canonical(result))
    return {
        "state": "progressed",
        "identity": artifact_sha256,
        "artifacts": _artifacts(store, result["artifact_keys"]),
        "inference_calls": 1,
        "provider_calls": provider_calls,
        "next": "operator-sign-route",
        "details": {
            "candidate_uuid": candidate_uuid,
            "proposal_uuid": proposal_uuid,
            "provider": provider,
            "artifact_sha256": artifact_sha256,
            "candidate_protocols": candidate_protocols,
        },
    }


def _modal_candidate(
    store,
    settings,
    identity: dict,
    artifact_sha256: str,
    candidate_uuid: str,
    model: dict,
    sealed: dict,
    prefix: str,
    intent_key: str,
    client: baseten.Client,
    timeout: int,
) -> dict:
    try:
        ensured = modal_gpu.ensure(identity, artifact_sha256, model, client)
    except modal_gpu.ProviderError as error:
        raise ProviderError(
            str(error), client.calls + error.provider_calls, ambiguous=error.ambiguous
        ) from error
    if ensured["state"] != "ready":
        return {
            "state": "active",
            "identity": artifact_sha256,
            "artifacts": _artifacts(store, [intent_key]),
            "inference_calls": 0,
            "provider_calls": client.calls + ensured["provider_calls"],
            "next": "route-propose-modal",
            "details": {
                "provider": "modal",
                "app_name": ensured["plan"]["app_name"],
                "status": ensured["observation"]["app_state"],
                "artifact_sha256": artifact_sha256,
            },
        }
    plan = ensured["plan"]
    observation = ensured["observation"]
    base_url = observation["endpoint_url"].rstrip("/")
    receipt_key = prefix + "modal-receipt.json"
    receipt = {
        "schema_version": "milk.route-provider-receipt.v2",
        "job_id": artifact_sha256,
        "provider": "modal",
        "provider_app_id": observation["app_id"],
        "provider_app_name": plan["app_name"],
        "provider_volume_name": plan["volume_name"],
        "base_url": base_url,
        "request_sha256": summary.digest(plan),
    }
    store.create_same(receipt_key, summary.canonical(receipt))
    try:
        smoke, smoke_calls = _smoke(
            _required("MILK_CANDIDATE_API_KEY"),
            base_url,
            artifact_sha256,
            sealed["quantization"],
            timeout,
            "Bearer",
        )
    except ProviderError as error:
        raise ProviderError(
            str(error),
            client.calls + ensured["provider_calls"] + error.provider_calls,
            ambiguous=error.ambiguous,
        ) from error
    provider = {
        "name": "modal",
        "app_id": observation["app_id"],
        "app_name": plan["app_name"],
        "volume_name": plan["volume_name"],
        "status": observation["app_state"],
        "base_url": base_url,
    }
    return _finalize(
        store,
        settings,
        identity,
        artifact_sha256,
        candidate_uuid,
        provider,
        base_url,
        "MILK_CANDIDATE_API_KEY",
        smoke,
        prefix,
        client.calls + ensured["provider_calls"] + smoke_calls,
    )


def reconcile(store, settings, runtime, serving_provider: str) -> dict:
    if serving_provider not in {"baseten", "modal"}:
        raise RouteError("serving provider is invalid")
    model_reference, model, evaluation_reference, group, sealed = _inputs(store, settings, runtime)
    identity, artifact_sha256, candidate_uuid = _artifact(
        settings, runtime, model_reference, model, evaluation_reference, group, sealed, serving_provider
    )
    job_name = "route-propose-" + serving_provider
    prefix = settings.scope_prefix + f"j/{job_name}/{artifact_sha256}/"
    intent_key = prefix + "intent.json"
    receipt_key = prefix + "receipt.json"
    result_key = prefix + "result.json"
    try:
        result, unused = _object(store, result_key)
        if (
            result.get("schema_version") != "milk.route-propose-result.v3"
            or result.get("job_id") != artifact_sha256
            or not isinstance(result.get("candidate"), dict)
            or not isinstance(result.get("proposal"), dict)
        ):
            raise RouteError("stored route proposal result is invalid")
        status_key = _advance_status(store, settings, result["candidate"], result["proposal"])
        return {
            "state": "idle",
            "identity": artifact_sha256,
            "artifacts": _artifacts(store, [*result["artifact_keys"], status_key]),
            "inference_calls": 0,
            "provider_calls": 0,
            "next": "operator-sign-route",
            "details": {
                "candidate_uuid": result["candidate"]["uuid"],
                "proposal_uuid": result["proposal"]["uuid"],
                "provider": result["provider"],
                "artifact_sha256": result["candidate"]["artifact_sha256"],
            },
        }
    except FileNotFoundError:
        pass

    timeout = _integer("MILK_ROUTE_TIMEOUT_SECONDS", 600, 30, 1800)
    client = baseten.Client(_required("BASETEN_API_KEY"), min(timeout, 120))
    if serving_provider == "modal":
        intent = {
            **identity,
            "job_id": artifact_sha256,
            "candidate_uuid": candidate_uuid,
            "provider": "modal",
        }
        store.create_same(intent_key, summary.canonical(intent))
        return _modal_candidate(
            store,
            settings,
            identity,
            artifact_sha256,
            candidate_uuid,
            model,
            sealed,
            prefix,
            intent_key,
            client,
            timeout,
        )

    model_name, deployment_name = _names(artifact_sha256)
    config = _truss_config(identity, artifact_sha256, model_name)
    intent = {
        **identity,
        "job_id": artifact_sha256,
        "candidate_uuid": candidate_uuid,
        "provider": "baseten",
        "provider_model_name": model_name,
        "provider_deployment_name": deployment_name,
        "truss_version": TRUSS_VERSION,
        "truss_config": config,
    }
    created = store.create_same(intent_key, summary.canonical(intent)).created

    try:
        receipt, unused = _object(store, receipt_key)
        model_id = receipt.get("provider_model_id")
        deployment_id = receipt.get("provider_deployment_id")
        if (
            receipt.get("schema_version") != "milk.route-provider-receipt.v2"
            or receipt.get("job_id") != artifact_sha256
            or not isinstance(model_id, str)
            or IDENTIFIER.fullmatch(model_id) is None
            or not isinstance(deployment_id, str)
            or IDENTIFIER.fullmatch(deployment_id) is None
        ):
            raise RouteError("stored Baseten route receipt is invalid")
    except FileNotFoundError:
        match = _matching_deployment(client, model_name, deployment_name)
        push_calls = 0
        if match is None:
            if not created:
                raise ProviderError(
                    "route intent exists but no provider receipt or deterministic deployment is visible",
                    client.calls,
                    ambiguous=True,
                )
            try:
                pushed = _push(config, model_name, deployment_name)
                push_calls = 1
            except ProviderError as error:
                push_calls = error.provider_calls
                match = _matching_deployment(client, model_name, deployment_name)
                if match is None:
                    raise ProviderError(
                        str(error),
                        client.calls + push_calls,
                        ambiguous=error.ambiguous,
                    ) from error
            if match is None:
                pushed_ids = _ids_from_push(pushed)
                if pushed_ids is None:
                    match = _matching_deployment(client, model_name, deployment_name)
                    if match is None:
                        raise ProviderError(
                            "Baseten accepted the submission but returned no deployment identity",
                            client.calls + push_calls,
                            ambiguous=True,
                        )
                else:
                    model_id, deployment_id = pushed_ids
        if match is not None:
            model_id = match[0]["id"]
            deployment_id = match[1]["id"]
        receipt = {
            "schema_version": "milk.route-provider-receipt.v2",
            "job_id": artifact_sha256,
            "provider": "baseten",
            "provider_model_id": model_id,
            "provider_model_name": model_name,
            "provider_deployment_id": deployment_id,
            "provider_deployment_name": deployment_name,
            "request_sha256": summary.digest(config),
        }
        store.create_same(receipt_key, summary.canonical(receipt))

    try:
        deployment = client.deployment(model_id, deployment_id)
    except baseten.ProviderError as error:
        raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
    status = deployment.get("status")
    if status in TERMINAL_FAILURE:
        raise ProviderError(f"Baseten candidate deployment ended in {status}", client.calls)
    if status not in READY:
        return {
            "state": "active",
            "identity": artifact_sha256,
            "artifacts": _artifacts(store, [intent_key, receipt_key]),
            "inference_calls": 0,
            "provider_calls": client.calls,
            "next": "route-propose-baseten",
            "details": {
                "provider": "baseten",
                "model_id": model_id,
                "deployment_id": deployment_id,
                "status": status,
                "artifact_sha256": artifact_sha256,
            },
        }

    base_url = f"https://model-{model_id}.api.baseten.co/environments/production/sync"
    try:
        smoke, smoke_calls = _smoke(
            _required("MILK_CANDIDATE_API_KEY"),
            base_url,
            artifact_sha256,
            sealed["quantization"],
            timeout,
            "Api-Key",
        )
    except ProviderError as error:
        raise ProviderError(
            str(error), client.calls + error.provider_calls, ambiguous=error.ambiguous
        ) from error
    provider = {
        "name": "baseten",
        "model_id": model_id,
        "model_name": model_name,
        "deployment_id": deployment_id,
        "deployment_name": deployment_name,
        "status": deployment.get("status"),
        "base_url": base_url,
    }
    return _finalize(
        store,
        settings,
        identity,
        artifact_sha256,
        candidate_uuid,
        provider,
        base_url,
        "MILK_CANDIDATE_API_KEY",
        smoke,
        prefix,
        client.calls + smoke_calls,
    )


def reconcile_gpu_modal(store, settings) -> dict:
    status, unused = _object(store, settings.scope_prefix + "status/current.json")
    candidate_reference = status.get("candidate")
    if not isinstance(candidate_reference, dict):
        raise RouteError("a current candidate is required for GPU reconciliation")
    candidate, candidate_body = _object(store, candidate_reference.get("key", ""))
    identity = candidate.get("identity")
    provider = candidate.get("provider")
    artifact_sha256 = candidate.get("artifact_sha256")
    if (
        status.get("schema_version") != "milk.status.v2"
        or status.get("scope_id") != settings.scope_id
        or candidate_reference.get("schema_version") != "milk.candidate-reference.v2"
        or candidate_reference.get("scope_id") != settings.scope_id
        or summary.digest(candidate_body) != candidate_reference.get("sha256")
        or candidate.get("schema_version") != "milk.candidate.v2"
        or candidate.get("scope_id") != settings.scope_id
        or not isinstance(identity, dict)
        or identity.get("schema_version") != "milk.candidate-artifact-identity.v3"
        or not isinstance(artifact_sha256, str)
        or SHA256.fullmatch(artifact_sha256) is None
        or summary.digest(identity) != artifact_sha256
        or not isinstance(provider, dict)
    ):
        raise RouteError("current candidate identity is invalid")
    model_reference = identity.get("model")
    if not isinstance(model_reference, dict):
        raise RouteError("current candidate has no model reference")
    model, model_body = _object(store, model_reference.get("key", ""))
    if summary.digest(model_body) != model_reference.get("sha256"):
        raise RouteError("current candidate model digest differs")

    if provider.get("name") != "modal":
        raise RouteError("gpu-reconcile-modal requires a Modal candidate")

    prefix = settings.scope_prefix + f"j/gpu-reconcile-modal/{artifact_sha256}/"
    intent_key = prefix + "intent.json"
    result_key = prefix + "result.json"
    intent = {
        "schema_version": "milk.gpu-reconcile-modal-intent.v1",
        "job_id": artifact_sha256,
        "scope_id": settings.scope_id,
        "candidate": candidate_reference,
        "provider": provider.get("name"),
        "target": "zero",
    }
    store.create_same(intent_key, summary.canonical(intent))
    try:
        result, unused = _object(store, result_key)
        if (
            result.get("schema_version") != "milk.gpu-reconcile-modal-result.v1"
            or result.get("job_id") != artifact_sha256
            or result.get("scope_id") != settings.scope_id
            or result.get("provider") != provider.get("name")
            or result.get("state") != "zero"
            or result.get("active_containers") != 0
            or not isinstance(result.get("provider_app_id"), str)
            or not isinstance(result.get("provider_app_name"), str)
            or result.get("app_state") in modal_gpu.ACTIVE
        ):
            raise RouteError("stored GPU reconciliation result is invalid")
        return {
            "state": "idle",
            "identity": artifact_sha256,
            "artifacts": _artifacts(store, [intent_key, result_key]),
            "provider_calls": 0,
            "next": None,
            "details": {
                "provider": provider.get("name"),
                "app_id": result["provider_app_id"],
                "app_name": result["provider_app_name"],
                "app_state": result["app_state"],
                "active_containers": 0,
                "state": "zero",
            },
        }
    except FileNotFoundError:
        pass

    timeout = _integer("MILK_GPU_TIMEOUT_SECONDS", 180, 30, 1800)
    try:
        stopped = modal_gpu.stop_candidate(identity, artifact_sha256, model, timeout)
    except modal_gpu.ProviderError as error:
        raise ProviderError(str(error), error.provider_calls, ambiguous=error.ambiguous) from error
    observation = stopped["observation"]
    provider_app_id = observation["app_id"] or provider.get("app_id")
    if not isinstance(provider_app_id, str):
        raise RouteError("the stopped Modal candidate has no provider app identity")
    result = {
        "schema_version": "milk.gpu-reconcile-modal-result.v1",
        "job_id": artifact_sha256,
        "scope_id": settings.scope_id,
        "provider": "modal",
        "provider_app_id": provider_app_id,
        "provider_app_name": stopped["plan"]["app_name"],
        "app_state": observation["app_state"],
        "active_containers": observation["active_containers"],
        "state": "zero",
    }
    store.create_same(result_key, summary.canonical(result))
    return {
        "state": "complete",
        "identity": artifact_sha256,
        "artifacts": _artifacts(store, [intent_key, result_key]),
        "provider_calls": stopped["provider_calls"],
        "next": None,
        "details": {
            "provider": "modal",
            "app_id": observation["app_id"],
            "app_state": observation["app_state"],
            "active_containers": observation["active_containers"],
            "state": "zero",
        },
    }
