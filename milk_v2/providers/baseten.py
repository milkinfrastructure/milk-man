from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


API = "https://api.baseten.co/v1"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, ambiguous: bool = False):
        super().__init__(message)
        self.ambiguous = ambiguous


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
                "Authorization": "Bearer " + self.api_key,
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
