from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import NoReturn

from . import config
from . import dataset as dataset_job
from . import eval as eval_job
from . import evaluate as evaluate_job
from . import route as route_job
from . import semantic
from . import summary
from . import train as train_job
from .providers import modal_controller
from .store import StoreError, open_store, settings_from_environment


RESULT_SCHEMA = "milk.job-result.v2"
USAGE = "usage: milk jobs [name] | milk status | milk operate --once | milk run <job> [status|stop]"
EXIT_USAGE = 64
EXIT_CONFIG = 65
EXIT_PROVIDER = 69
EXIT_INTERNAL = 70
EXIT_BUSY = 75
POINTERS = ("status/current.json", "s/current.json", "readiness/current.json", "e/current.json", "r/current.json")
CONTROLLER_HANDLERS = frozenset({"inference-ensure", "inference-status", "inference-stop"})
CONTROLLER_STATES = {
    "inference-ensure": {
        "planned": ("idle", "inference-ensure", 0),
        "ready": ("complete", None, 0),
        "blocked": ("blocked", "inference-status", 0),
        "ambiguous": ("failed", "inference-status", EXIT_INTERNAL),
    },
    "inference-status": {
        "not_deployed": ("idle", "inference-ensure", 0),
        "incomplete": ("active", "inference-status", 0),
        "ready_zero": ("complete", None, 0),
        "ready_active": ("active", None, 0),
    },
    "inference-stop": {
        "planned": ("idle", "inference-stop", 0),
        "zero": ("complete", None, 0),
        "ambiguous": ("failed", "inference-status", EXIT_INTERNAL),
    },
}


class UsageError(ValueError):
    pass


def _json_digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _result(job: str, state: str, scope_id: str | None, identity: str, artifacts=(), next_job=None, details=None, error=None, inference_calls=0, provider_calls=0):
    value = {
        "schema_version": RESULT_SCHEMA,
        "job": job,
        "state": state,
        "identity": identity,
        "scope_id": scope_id,
        "artifacts": list(artifacts),
        "inference_calls": inference_calls,
        "provider_calls": provider_calls,
        "next": next_job,
    }
    if details is not None:
        value["details"] = details
    if error is not None:
        value["error"] = error
    return value


def _emit(value: dict, code: int = 0) -> NoReturn:
    sys.stdout.write(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
    raise SystemExit(code)


def _parse(argv: list[str]) -> tuple[str, str | None, str | None]:
    if len(argv) in {1, 2} and argv[0] == "jobs":
        return "jobs", argv[1] if len(argv) == 2 else None, None
    if argv == ["status"]:
        return "status", None, None
    if argv == ["operate", "--once"]:
        return "operate", None, None
    if len(argv) == 2 and argv[0] == "run":
        return "run", argv[1], "run"
    if len(argv) == 3 and argv[0] == "run" and argv[2] in {"status", "stop"}:
        return "run", argv[1], argv[2]
    raise UsageError(USAGE)


def _catalog(runtime, name: str | None = None) -> dict:
    rows = []
    for job in (runtime.job(name),) if name is not None else runtime.jobs.values():
        required = list(job.environment_required)
        optional = list(job.environment_optional)
        for binding in job.bindings:
            required.extend(config.BINDING_ENVIRONMENTS[binding]["required"])
            optional.extend(config.BINDING_ENVIRONMENTS[binding]["optional"])
        if job.timeout_env not in required:
            optional.append(job.timeout_env)
        rows.append(
            {
                "name": job.name,
                "description": job.description or job.name,
                "actions": [
                    "run",
                    *(["status"] if job.supports_status else []),
                    *(["stop"] if job.supports_stop else []),
                ],
                "environment": {
                    "required": sorted(set(required)),
                    "optional": sorted(set(optional)),
                },
            }
        )
    return {"schema_version": "milk.job-catalog.v1", "jobs": rows}


def _external_job(job, runtime, action: str) -> tuple[dict, int]:
    if action == "status" and not job.supports_status:
        raise UsageError(f"{job.name} has no status action")
    if action == "stop" and not job.supports_stop:
        raise UsageError(f"{job.name} has no stop action")

    # Status/stop resolve saved resource settings inside the script, not new run inputs.
    missing = sorted(name for name in job.environment_required if not os.environ.get(name)) if action == "run" else []
    identity = _json_digest(
        {"job": job.name, "action": action, "config_digest": runtime.digest}
    )
    if missing:
        return (
            _result(
                job.name,
                "failed",
                os.environ.get("MILK_SCOPE_ID"),
                identity,
                error=f"missing environment: {', '.join(missing)}",
            ),
            EXIT_CONFIG,
        )

    raw_timeout = os.environ.get(job.timeout_env, "3600")
    try:
        timeout = int(raw_timeout)
    except ValueError as error:
        raise config.ConfigError(f"{job.timeout_env} must be an integer") from error
    if not 1 <= timeout <= 86_400:
        raise config.ConfigError(f"{job.timeout_env} must be in 1..86400")

    root = Path(__file__).resolve().parents[1]
    executable = (root / str(job.executable)).resolve()
    child_environment = os.environ.copy()
    child_environment.update(
        {
            "MILK_JOB_NAME": job.name,
            "MILK_JOB_ACTION": action,
            "MILK_JOB_CONFIG_DIGEST": runtime.digest,
        }
    )
    try:
        completed = subprocess.run(
            [str(executable), action],
            cwd=root,
            env=child_environment,
            stdout=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return (
            _result(
                job.name,
                "failed",
                os.environ.get("MILK_SCOPE_ID"),
                identity,
                error=f"job {action} failed: {type(error).__name__}",
            ),
            EXIT_INTERNAL,
        )
    if len(completed.stdout) > 1024 * 1024:
        raise config.ConfigError(f"{job.name} returned more than 1 MiB")
    try:
        value = json.loads(completed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise config.ConfigError(f"{job.name} returned invalid JSON") from error
    required = {"state", "identity"}
    optional = {
        "artifacts",
        "next",
        "details",
        "error",
        "inference_calls",
        "provider_calls",
    }
    if not isinstance(value, dict) or not required.issubset(value) or value.keys() - required - optional:
        raise config.ConfigError(f"{job.name} returned an invalid result")
    state = value["state"]
    result_identity = value["identity"]
    artifacts = value.get("artifacts", [])
    inference_calls = value.get("inference_calls", 0)
    provider_calls = value.get("provider_calls", 0)
    if (
        state not in {"idle", "active", "complete", "progressed", "blocked", "failed"}
        or not isinstance(result_identity, str)
        or not result_identity
        or len(result_identity) > 512
        or not isinstance(artifacts, list)
        or type(inference_calls) is not int
        or inference_calls < 0
        or type(provider_calls) is not int
        or provider_calls < 0
    ):
        raise config.ConfigError(f"{job.name} returned an invalid result")
    if completed.returncode and state not in {"blocked", "failed"}:
        raise config.ConfigError(f"{job.name} exited nonzero without a failure result")
    result = _result(
        job.name,
        state,
        os.environ.get("MILK_SCOPE_ID"),
        result_identity,
        artifacts,
        value.get("next"),
        value.get("details"),
        value.get("error"),
        inference_calls,
        provider_calls,
    )
    code = completed.returncode if 0 <= completed.returncode <= 125 else EXIT_INTERNAL
    return result, code


def _summary_gate(store, settings, runtime, name="summary"):
    run = summary.reconcile(store, settings, runtime)
    return _result(
        name,
        run["state"],
        settings.scope_id,
        run["identity"],
        run["artifacts"],
        run["next"],
        run["details"],
        inference_calls=run["inference_calls"],
        provider_calls=run["provider_calls"],
    )


def _eval_gate(store, settings, runtime, name="eval"):
    run = eval_job.reconcile(store, settings, runtime)
    return _result(
        name,
        run["state"],
        settings.scope_id,
        run["identity"],
        run["artifacts"],
        run["next"],
        run["details"],
        inference_calls=run["inference_calls"],
        provider_calls=run["provider_calls"],
    )


def _dataset_gate(store, settings, runtime, name="dataset"):
    run = dataset_job.reconcile(store, settings, runtime)
    return _result(name, run["state"], settings.scope_id, run["identity"], run["artifacts"], run["next"], run["details"], inference_calls=run["inference_calls"], provider_calls=run["provider_calls"])


def _train_gate(store, settings, runtime, name="train"):
    run = train_job.reconcile(store, settings, runtime)
    return _result(name, run["state"], settings.scope_id, run["identity"], run["artifacts"], run["next"], run["details"], provider_calls=run["provider_calls"])


def _evaluate_gate(store, settings, runtime, name="evaluate"):
    run = evaluate_job.reconcile(store, settings, runtime)
    return _result(name, run["state"], settings.scope_id, run["identity"], run["artifacts"], run["next"], run["details"], provider_calls=run["provider_calls"])


def _route_gate(store, settings, runtime, provider: str, name: str):
    run = route_job.reconcile(store, settings, runtime, provider)
    return _result(
        name,
        run["state"],
        settings.scope_id,
        run["identity"],
        run["artifacts"],
        run["next"],
        run["details"],
        inference_calls=run["inference_calls"],
        provider_calls=run["provider_calls"],
    )


def _gpu_modal_gate(store, settings, name="gpu-reconcile-modal"):
    run = route_job.reconcile_gpu_modal(store, settings)
    return _result(
        name,
        run["state"],
        settings.scope_id,
        run["identity"],
        run["artifacts"],
        run["next"],
        run["details"],
        provider_calls=run["provider_calls"],
    )


def _operate(store, settings, runtime):
    results = []
    for name, gate, expected_next in (
        ("summary", _summary_gate, "eval"),
        ("eval", _eval_gate, "dataset"),
        ("dataset", _dataset_gate, "train"),
        ("train", _train_gate, "evaluate"),
        ("evaluate", _evaluate_gate, "select-route-provider"),
    ):
        result = gate(store, settings, runtime)
        results.append((name, result))
        if result["next"] != expected_next:
            break
    last = results[-1][1]
    return _result(
        "operate",
        last["state"],
        settings.scope_id,
        _json_digest({name: result["identity"] for name, result in results}),
        [artifact for unused_name, result in results for artifact in result["artifacts"]],
        last["next"],
        {name: result.get("details", {}) for name, result in results},
        inference_calls=sum(result["inference_calls"] for unused_name, result in results),
        provider_calls=sum(result["provider_calls"] for unused_name, result in results),
    )


def _status(store, settings, runtime):
    artifacts = []
    pointer_etags = {}
    for suffix in POINTERS:
        key = settings.scope_prefix + suffix
        try:
            item = store.get(key)
        except FileNotFoundError:
            continue
        digest = hashlib.sha256(item.body).hexdigest()
        artifacts.append({"key": key, "sha256": digest})
        pointer_etags[suffix] = item.etag
    observed = summary.inspect(store, settings)
    details = {
        "store_kind": settings.kind,
        "profile": settings.profile,
        "capture_count": observed["capture_count"],
        "processed_count": observed["processed_count"],
        "next_threshold": observed["next_threshold"],
        "ready": bool(observed["readiness_pointer"] and observed["readiness_pointer"].get("ready")),
        "statistically_qualified": bool(observed["readiness_pointer"] and observed["readiness_pointer"].get("statistically_qualified")),
    }
    details["eval_current"] = details["ready"] and eval_job.current_matches(store, settings)
    dataset_reference = dataset_job.current(store, settings, runtime) if details["eval_current"] else None
    details["dataset_current"] = dataset_reference is not None
    details["training_ready"] = bool(dataset_reference and dataset_job.training_ready(dataset_reference.get("counts")))
    if dataset_reference is not None:
        artifacts.append({"key": dataset_reference["key"], "sha256": dataset_reference["sha256"]})
    training_reference = train_job.current(store, settings, runtime) if dataset_reference is not None else None
    details["training_current"] = training_reference is not None
    if training_reference is not None:
        artifacts.append({"key": training_reference["key"], "sha256": training_reference["sha256"]})
    evaluation_reference = evaluate_job.current(store, settings, runtime) if training_reference is not None else None
    details["evaluation_current"] = evaluation_reference is not None
    if evaluation_reference is not None:
        artifacts.append({"key": evaluation_reference["key"], "sha256": evaluation_reference["sha256"]})
    details["route_jobs"] = {
        name: {
            "available": not missing,
            "missing_environment": missing,
        }
        for name in ("route-propose-baseten", "route-propose-modal")
        for missing in [
            sorted(
                {
                    variable
                    for binding in runtime.job(name).bindings
                    for variable in config.BINDING_ENVIRONMENTS[binding]["required"]
                    if not os.environ.get(variable)
                }
            )
        ]
    }
    route_reference = route_job.current(store, settings) if evaluation_reference is not None else None
    details["proposal_current"] = route_reference is not None
    if route_reference is not None:
        artifacts.extend(
            {"key": reference["key"], "sha256": reference["sha256"]}
            for reference in route_reference.values()
        )
    identity = _json_digest(
        {
            "schema_version": "milk.status-identity.v2",
            "scope_id": settings.scope_id,
            "config_digest": runtime.digest,
            "pointers": pointer_etags,
            "details": details,
        }
    )
    next_job = (
        "operator-sign-route"
        if details["proposal_current"]
        else "select-route-provider"
        if details["evaluation_current"]
        else "evaluate"
        if details["training_current"] and details["training_ready"]
        else "train"
        if details["training_ready"]
        else "summary"
        if details["dataset_current"]
        else "dataset"
        if details["eval_current"]
        else "eval"
        if details["ready"]
        else "summary"
    )
    return _result("status", "complete", settings.scope_id, identity, artifacts, next_job, details)


def _controller_apply(controller: dict, require_key: bool) -> bool:
    value = os.environ.get("MILK_MODAL_CONTROLLER_APPLY", "0")
    if value not in {"0", "1"}:
        raise config.ConfigError("MILK_MODAL_CONTROLLER_APPLY must be 0 or 1")
    if value == "1" and require_key and not os.environ.get(controller["api_key_env"]):
        raise config.ConfigError(f"{controller['api_key_env']} is required when applying the controller")
    return value == "1"


def _controller_artifacts(value: dict) -> tuple[dict, ...]:
    root = modal_controller.state_root()
    controller_id = value["controller_id"]
    run = root / "controller" / "runs" / controller_id
    paths = [
        run / name
        for name in (
            "intent.json",
            "volume-create.json",
            "deploy.json",
            "hydrate.json",
            "smoke.json",
            "endpoint.json",
            "result.json",
            "stop-intent.json",
            "stop.json",
            "zero.json",
            "termination.json",
        )
    ]
    for name in ("current.json", "pending.json"):
        path = root / "controller" / name
        record = modal_controller.read_json(path)
        if record and record.get("controller_id") == controller_id:
            paths.append(path)
    return tuple(
        {"key": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in paths
        if path.is_file()
    )


def _controller_job(name: str, settings) -> tuple[dict, int]:
    controller = modal_controller.plan()
    if name != "inference-ensure":
        controller = modal_controller.tracked_controller(modal_controller.state_root()) or controller
    apply = _controller_apply(controller, name == "inference-ensure") if name != "inference-status" else False
    if name == "inference-ensure":
        value = modal_controller.ensure(controller, apply)
    elif name == "inference-status":
        value = modal_controller.status(controller)
    else:
        value = modal_controller.stop(controller, apply)
    try:
        state, next_job, exit_code = CONTROLLER_STATES[name][value["state"]]
        calls = value["provider_calls"]
        if not isinstance(calls, int) or isinstance(calls, bool) or calls < 0:
            raise KeyError("provider_calls")
    except (KeyError, TypeError) as error:
        raise modal_controller.ControllerError("controller returned an invalid result") from error
    return (
        _result(
            name,
            state,
            settings.scope_id,
            value["controller_id"],
            _controller_artifacts(value),
            next_job,
            value,
            provider_calls=calls,
        ),
        exit_code,
    )


def _run_job(name, store, settings, runtime):
    job = runtime.job(name)
    if job.handler == "summary":
        return _summary_gate(store, settings, runtime), 0
    if job.handler == "eval":
        return _eval_gate(store, settings, runtime), 0
    if job.handler == "dataset":
        return _dataset_gate(store, settings, runtime), 0
    if job.handler == "train":
        return _train_gate(store, settings, runtime), 0
    if job.handler == "evaluate":
        return _evaluate_gate(store, settings, runtime), 0
    if job.handler == "route-propose-baseten":
        return _route_gate(store, settings, runtime, "baseten", job.handler), 0
    if job.handler == "route-propose-modal":
        return _route_gate(store, settings, runtime, "modal", job.handler), 0
    if job.handler == "gpu-reconcile-modal":
        return _gpu_modal_gate(store, settings), 0
    if job.handler in CONTROLLER_HANDLERS:
        return _controller_job(job.handler, settings)
    identity = _json_digest(
        {
            "schema_version": "milk.job-identity.v2",
            "job": name,
            "scope_id": settings.scope_id,
            "profile": settings.profile,
            "config_digest": runtime.digest,
        }
    )
    return (
        _result(
            name,
            "blocked",
            settings.scope_id,
            identity,
            next_job=name,
            details={"reason": f"{name}_handler_not_implemented"},
        ),
        0,
    )


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv in (["--help"], ["-h"], ["help"]):
        print(USAGE)
        return
    command = "invalid"
    job_name = None
    action = None
    scope_id = os.environ.get("MILK_SCOPE_ID")
    try:
        command, job_name, action = _parse(argv)
        runtime = config.load()
        if command == "jobs":
            _emit(_catalog(runtime, job_name))
        if command == "run" and job_name is not None:
            job = runtime.job(job_name)
            if job.executable is not None:
                result, exit_code = _external_job(job, runtime, action or "run")
                _emit(result, exit_code)
            if action != "run":
                raise UsageError(f"{job.name} has no {action} action")
        settings = settings_from_environment()
        store = open_store(settings)
        if command == "status":
            _emit(_status(store, settings, runtime))
        if command == "operate":
            _emit(_operate(store, settings, runtime))
        result, exit_code = _run_job(job_name or "", store, settings, runtime)
        _emit(result, exit_code)
    except UsageError as error:
        identity = _json_digest({"command": argv, "error": str(error)})
        _emit(_result(command, "failed", scope_id, identity, error=str(error)), EXIT_USAGE)
    except (config.ConfigError, StoreError) as error:
        identity = _json_digest({"command": argv, "error": str(error)})
        _emit(_result(job_name or command, "failed", scope_id, identity, error=str(error)), EXIT_CONFIG)
    except summary.BusyError as error:
        _emit(_result(job_name or command, "blocked", scope_id, error.identity, next_job="summary", error=str(error)), EXIT_BUSY)
    except eval_job.BusyError as error:
        _emit(_result(job_name or command, "blocked", scope_id, error.identity, next_job="eval", error=str(error)), EXIT_BUSY)
    except dataset_job.BusyError as error:
        _emit(_result(job_name or command, "blocked", scope_id, error.identity, next_job="dataset", error=str(error)), EXIT_BUSY)
    except BlockingIOError as error:
        identity = _json_digest({"job": job_name, "error": type(error).__name__})
        _emit(_result(job_name or command, "blocked", scope_id, identity, next_job="inference-status", error="controller operation is active"), EXIT_BUSY)
    except modal_controller.ControllerError as error:
        identity = _json_digest({"job": job_name, "error": str(error)})
        _emit(_result(job_name or command, "failed", scope_id, identity, next_job="inference-status", error=str(error)), EXIT_INTERNAL)
    except summary.ProviderError as error:
        identity = _json_digest({"command": argv, "error": str(error)})
        _emit(
            _result(
                job_name or command,
                "failed",
                scope_id,
                identity,
                next_job="summary",
                error=str(error),
                inference_calls=error.inference_calls,
            ),
            EXIT_PROVIDER,
        )
    except semantic.ProviderError as error:
        identity = _json_digest({"command": argv, "error": str(error)})
        _emit(_result(job_name or command, "failed", scope_id, identity, next_job="eval", error=str(error), inference_calls=error.inference_calls), EXIT_PROVIDER)
    except dataset_job.ProviderError as error:
        identity = _json_digest({"command": argv, "error": str(error)})
        _emit(_result(job_name or command, "failed", scope_id, identity, next_job="dataset", error=str(error), inference_calls=error.inference_calls), EXIT_PROVIDER)
    except eval_job.EvalError as error:
        identity = _json_digest({"command": argv, "error": str(error)})
        _emit(_result(job_name or command, "failed", scope_id, identity, next_job="eval", error=str(error)), EXIT_CONFIG)
    except dataset_job.DatasetError as error:
        identity = _json_digest({"command": argv, "error": str(error)})
        _emit(_result(job_name or command, "failed", scope_id, identity, next_job="dataset", error=str(error)), EXIT_CONFIG)
    except train_job.ProviderError as error:
        identity = _json_digest({"command": argv, "error": str(error)})
        _emit(_result(job_name or command, "failed", scope_id, identity, next_job="train", error=str(error), provider_calls=error.provider_calls), EXIT_PROVIDER)
    except train_job.TrainError as error:
        identity = _json_digest({"command": argv, "error": str(error)})
        _emit(_result(job_name or command, "failed", scope_id, identity, next_job="train", error=str(error)), EXIT_CONFIG)
    except evaluate_job.ProviderError as error:
        identity = _json_digest({"command": argv, "error": str(error)})
        _emit(_result(job_name or command, "failed", scope_id, identity, next_job="evaluate", error=str(error), provider_calls=error.provider_calls), EXIT_PROVIDER)
    except evaluate_job.EvaluateError as error:
        identity = _json_digest({"command": argv, "error": str(error)})
        _emit(_result(job_name or command, "failed", scope_id, identity, next_job="evaluate", error=str(error)), EXIT_CONFIG)
    except route_job.ProviderError as error:
        identity = _json_digest({"command": argv, "error": str(error)})
        code = EXIT_INTERNAL if error.ambiguous else EXIT_PROVIDER
        next_job = job_name if job_name in {"route-propose-baseten", "route-propose-modal"} else "select-route-provider"
        _emit(_result(job_name or command, "failed", scope_id, identity, next_job=next_job, error=str(error), provider_calls=error.provider_calls), code)
    except route_job.RouteError as error:
        identity = _json_digest({"command": argv, "error": str(error)})
        next_job = job_name if job_name in {"route-propose-baseten", "route-propose-modal", "gpu-reconcile-modal"} else "select-route-provider"
        _emit(_result(job_name or command, "failed", scope_id, identity, next_job=next_job, error=str(error)), EXIT_CONFIG)
    except summary.SummaryError as error:
        identity = _json_digest({"command": argv, "error": str(error)})
        _emit(_result(job_name or command, "failed", scope_id, identity, error=str(error)), EXIT_CONFIG)
    except Exception as error:
        print(f"milk: {type(error).__name__}: {error}", file=sys.stderr)
        identity = _json_digest({"command": argv, "error_type": type(error).__name__})
        _emit(_result(job_name or command, "failed", scope_id, identity, error="internal failure"), EXIT_INTERNAL)


if __name__ == "__main__":
    main()
