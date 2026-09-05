from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request


API = "https://api.baseten.co/v1"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
TRUSS_VERSION = "0.18.28"


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, ambiguous: bool = False, code: str | None = None):
        super().__init__(message)
        self.ambiguous = ambiguous
        self.code = code


class Client:
    def __init__(self, api_key: str, timeout: int):
        if not api_key:
            raise ProviderError("BASETEN_API_KEY is required")
        self.api_key = api_key
        self.timeout = timeout
        self.calls = 0

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        raw = None if body is None else json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        request = urllib.request.Request(
            API + path,
            data=raw,
            method=method,
            headers={
                "Authorization": "Api-Key " + self.api_key,
                "Accept": "application/json",
                **({"Content-Type": "application/json"} if raw is not None else {}),
            },
        )
        self.calls += 1
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
                if len(payload) > MAX_RESPONSE_BYTES:
                    raise ProviderError("Baseten response is oversized")
        except urllib.error.HTTPError as error:
            payload = error.read(4096)
            detail = payload.decode("utf-8", "replace").replace("\n", " ")[:512]
            raise ProviderError(f"Baseten returned HTTP {error.code}: {detail}", ambiguous=error.code >= 500) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ProviderError(f"Baseten request outcome is ambiguous: {error}", ambiguous=True) from error
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProviderError("Baseten returned invalid JSON", ambiguous=method == "POST") from error
        if not isinstance(value, dict):
            raise ProviderError("Baseten returned a non-object", ambiguous=method == "POST")
        return value

    def jobs(self, project_id: str) -> list[dict]:
        value = self._request("POST", "/training_jobs/search", {"project_id": project_id})
        jobs = value.get("training_jobs")
        if not isinstance(jobs, list) or any(not isinstance(job, dict) for job in jobs):
            raise ProviderError("Baseten job search response is invalid")
        return jobs

    def create(self, project_id: str, training_job: dict) -> dict:
        value = self._request("POST", f"/training_projects/{project_id}/jobs", {"training_job": training_job})
        job = value.get("training_job")
        if not isinstance(job, dict) or not isinstance(job.get("id"), str):
            raise ProviderError("Baseten create response is invalid", ambiguous=True)
        return job

    def get(self, project_id: str, job_id: str) -> dict:
        value = self._request("GET", f"/training_projects/{project_id}/jobs/{job_id}")
        job = value.get("training_job")
        if not isinstance(job, dict) or job.get("id") != job_id:
            raise ProviderError("Baseten job response is invalid")
        return job

    def checkpoint_files(self, project_id: str, job_id: str) -> list[dict]:
        value = self._request("GET", f"/training_projects/{project_id}/jobs/{job_id}/checkpoint_files")
        files = value.get("presigned_urls")
        if not isinstance(files, list) or any(not isinstance(item, dict) for item in files):
            raise ProviderError("Baseten checkpoint response is invalid")
        return files

    def models(self) -> list[dict]:
        value = self._request("GET", "/models")
        models = value.get("models")
        if not isinstance(models, list) or any(not isinstance(model, dict) for model in models):
            raise ProviderError("Baseten model response is invalid")
        return models

    def deployments(self, model_id: str) -> list[dict]:
        value = self._request("GET", f"/models/{model_id}/deployments")
        deployments = value.get("deployments")
        if not isinstance(deployments, list) or any(not isinstance(deployment, dict) for deployment in deployments):
            raise ProviderError("Baseten deployment response is invalid")
        return deployments

    def deployment(self, model_id: str, deployment_id: str) -> dict:
        value = self._request("GET", f"/models/{model_id}/deployments/{deployment_id}")
        if value.get("id") != deployment_id or value.get("model_id") != model_id:
            raise ProviderError("Baseten deployment identity differs")
        return value

    def set_active(self, model_id: str, deployment_id: str, active: bool) -> dict:
        action = "activate" if active else "deactivate"
        value = self._request("POST", f"/models/{model_id}/deployments/{deployment_id}/{action}")
        if value.get("success") is not True:
            raise ProviderError(f"Baseten {action} response did not confirm success", ambiguous=True)
        return value

    def autoscale(self, model_id: str, deployment_id: str, settings: dict) -> dict:
        value = self._request("PATCH", f"/models/{model_id}/deployments/{deployment_id}/autoscaling_settings", settings)
        if value.get("status") != "ACCEPTED":
            raise ProviderError("Baseten autoscaling update was not accepted", ambiguous=True)
        return value


def push(config: dict, model_name: str, deployment_name: str, *, labels: dict, timeout: int) -> dict:
    """Reuse the pinned Truss CLI; keys exist only in its private temporary home."""
    api_key = os.environ.get("BASETEN_API_KEY", "")
    team = os.environ.get("BASETEN_TEAM_NAME")
    if not api_key or any(ord(c) < 33 for c in api_key) or (
        team is not None and (not team or any(ord(c) < 32 for c in team))
    ):
        raise ProviderError("Baseten credential or team name is invalid")
    with tempfile.TemporaryDirectory(prefix="milk-truss-") as directory:
        root = Path(directory)
        truss, private_home = root / "truss", root / "home"
        truss.mkdir(mode=0o700)
        private_home.mkdir(mode=0o700)
        (truss / "config.yaml").write_text(json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
        trussrc = private_home / ".trussrc"
        trussrc.write_text(
            "[baseten]\nremote_provider = baseten\nauth_type = api_key\n"
            f"api_key = {api_key}\nremote_url = https://app.baseten.co\n"
        )
        trussrc.chmod(0o600)
        command = [
            "uvx", "--from", f"truss=={TRUSS_VERSION}", "truss", "push", str(truss),
            "--remote", "baseten", "--model-name", model_name,
            "--deployment-name", deployment_name, "--no-wait", "--non-interactive",
            "--disable-truss-download", "--output", "json", "--labels",
            json.dumps(labels, separators=(",", ":")),
        ]
        if team:
            command.extend(("--team", team))
        environment = {
            "HOME": str(private_home), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "TMPDIR": directory, "UV_NO_PROGRESS": "1",
            "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR", str(Path.home() / ".cache" / "uv")),
        }
        try:
            completed = subprocess.run(
                command, cwd=truss, env=environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ProviderError(f"Baseten submission outcome is ambiguous: {error}", ambiguous=True) from error
        if len(completed.stdout.encode()) > MAX_RESPONSE_BYTES:
            raise ProviderError("Truss returned oversized output", ambiguous=True)
        if completed.returncode != 0:
            detail = " ".join(completed.stderr.split())[-1024:].replace(api_key, "[redacted]")
            if "Custom base images not supported for your organization" in detail:
                raise ProviderError(
                    "Baseten custom base images are not enabled for this organization",
                    code="custom_base_image_not_enabled",
                )
            raise ProviderError(f"Truss submission failed: {detail or 'no detail'}", ambiguous=True)
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise ProviderError("Truss returned invalid JSON", ambiguous=True) from error
        if not isinstance(value, dict):
            raise ProviderError("Truss returned invalid JSON", ambiguous=True)
        return value


def fetch_json(url: str, timeout: int, maximum: int = 1024 * 1024) -> tuple[dict, bytes]:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ProviderError("checkpoint URL is not a safe HTTPS URL")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(maximum + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as error:
        raise ProviderError(f"cannot fetch checkpoint result: {error}") from error
    if len(body) > maximum:
        raise ProviderError("checkpoint result is oversized")
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderError("checkpoint result is invalid JSON") from error
    if not isinstance(value, dict):
        raise ProviderError("checkpoint result is not an object")
    return value, body
