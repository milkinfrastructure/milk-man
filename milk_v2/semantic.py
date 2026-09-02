from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.parse

from .summary import canonical, digest


class ProviderError(RuntimeError):
    def __init__(self, message: str, inference_calls: int = 0):
        super().__init__(message)
        self.inference_calls = inference_calls


def _endpoint(prefix: str) -> tuple[str, str, str]:
    base = os.environ.get(f"MILK_{prefix}_BASE_URL", "").rstrip("/")
    model = os.environ.get(f"MILK_{prefix}_MODEL", "")
    api_key = os.environ.get(f"MILK_{prefix}_API_KEY", "")
    if not base or not model or not api_key:
        raise ProviderError(f"MILK_{prefix}_BASE_URL, MILK_{prefix}_MODEL, and MILK_{prefix}_API_KEY are required")
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProviderError(f"MILK_{prefix}_BASE_URL is invalid")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ProviderError(f"MILK_{prefix}_BASE_URL must use HTTPS outside localhost")
    if parsed.path.rstrip("/") not in {"", "/v1"}:
        raise ProviderError(f"MILK_{prefix}_BASE_URL must be an origin or end in /v1")
    return base + ("" if parsed.path.rstrip("/") == "/v1" else "/v1") + "/chat/completions", model, api_key


def _timeout() -> int:
    try:
        value = int(os.environ.get("MILK_EVAL_TIMEOUT_SECONDS", "180"))
    except ValueError as error:
        raise ProviderError("MILK_EVAL_TIMEOUT_SECONDS must be an integer") from error
    if not 1 <= value <= 3600:
        raise ProviderError("MILK_EVAL_TIMEOUT_SECONDS must be in 1..3600")
    return value


def _tools(job: str, result_schema: dict) -> list[dict]:
    empty = {"type": "object", "properties": {}, "additionalProperties": False}
    return [
        {"type": "function", "function": {"name": "milk_job_read", "description": f"Read the immutable prepared input for this {job} job.", "parameters": empty}},
        {
            "type": "function",
            "function": {
                "name": "milk_job_commit",
                "description": f"Commit the complete result for this {job} job.",
                "parameters": {"type": "object", "properties": {"result": result_schema}, "required": ["result"], "additionalProperties": False},
            },
        },
        {"type": "function", "function": {"name": "milk_status", "description": f"Read bounded status for this {job} job.", "parameters": empty}},
    ]


def call(job: str, prefix: str, prompt: str, input_value: dict, result_schema: dict, validate) -> tuple[dict, dict]:
    endpoint, model, api_key = _endpoint(prefix)
    timeout = _timeout()
    input_sha256 = digest(input_value)
    messages = [{
        "role": "user",
        "content": canonical({
            "schema_version": "milk.semantic-session-turn.v2",
            "job": job,
            "input_sha256": input_sha256,
            "input": input_value,
            "next": "milk_job_read",
        }).decode(),
    }]
    llm = Path(__file__).resolve().parents[1] / "vendor" / "headlong" / "bin" / "llm"
    usage = Counter()
    request_ids: list[str] = []
    tool_calls_seen = 0
    read_seen = False
    last_tools: list[str] = []
    last_rejection = "none"
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=f"milk-{job}-") as directory:
        root = Path(directory)
        system_file, messages_file, tools_file = (root / name for name in ("system", "messages.json", "tools.json"))
        system_file.write_text(prompt)
        tools_file.write_bytes(canonical(_tools(job, result_schema)))
        os.chmod(system_file, 0o600)
        os.chmod(tools_file, 0o600)
        for turn in range(1, 5):
            remaining = timeout - int(time.monotonic() - started)
            if remaining < 1:
                raise ProviderError(f"{job} provider session timed out", turn - 1)
            messages_file.write_bytes(canonical(messages))
            os.chmod(messages_file, 0o600)
            environment = {
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "LLM_API_URL": endpoint,
                "LLM_MODEL": model,
                "LLM_API_KEY": api_key,
                "LLM_CONNECT_TIMEOUT": str(min(10, remaining)),
                "LLM_MAX_TIME": str(remaining),
            }
            if os.environ.get("TMPDIR"):
                environment["TMPDIR"] = os.environ["TMPDIR"]
            try:
                process = subprocess.run(
                    [str(llm), "--system-file", str(system_file), "--messages-file", str(messages_file), "--tools-file", str(tools_file), "--json-response"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=environment,
                    timeout=remaining + 2,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                raise ProviderError(f"{job} provider request failed", turn - 1) from error
            if process.returncode != 0 or len(process.stdout) > 4 * 1024 * 1024:
                raise ProviderError(f"{job} provider request failed", turn)
            try:
                response = json.loads(process.stdout)
                message = response["message"]
                tool_calls = message["tool_calls"]
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
                raise ProviderError(f"{job} provider returned no Milk tool call", turn) from error
            if not isinstance(message, dict) or message.get("role") != "assistant" or not isinstance(tool_calls, list) or not tool_calls:
                raise ProviderError(f"{job} provider returned no Milk tool call", turn)
            request_id = response.get("provider_request_id")
            if isinstance(request_id, str) and len(request_id) <= 256:
                request_ids.append(request_id)
            response_usage = response.get("usage")
            if isinstance(response_usage, dict):
                usage.update({key: value for key, value in response_usage.items() if type(value) is int and value >= 0})
            tool_calls_seen += len(tool_calls)
            if tool_calls_seen > 16:
                raise ProviderError(f"{job} provider exceeded the Milk tool-call limit", turn)
            assistant_message = {"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls}
            if isinstance(message.get("reasoning_content"), str):
                assistant_message["reasoning_content"] = message["reasoning_content"]
            messages.append(assistant_message)
            committed = None
            can_commit = read_seen
            last_tools = []
            for tool_call in tool_calls:
                try:
                    call_id = tool_call["id"]
                    function = tool_call["function"]
                    name = function["name"]
                    arguments = json.loads(function["arguments"])
                except (KeyError, TypeError, json.JSONDecodeError) as error:
                    raise ProviderError(f"{job} provider returned an invalid Milk tool call", turn) from error
                if not isinstance(call_id, str) or not call_id or tool_call.get("type") != "function" or not isinstance(arguments, dict):
                    raise ProviderError(f"{job} provider returned an invalid Milk tool call", turn)
                last_tools.append(name)
                if name == "milk_job_commit":
                    if set(arguments) != {"result"} or not isinstance(arguments["result"], dict) or committed is not None:
                        raise ProviderError(f"{job} provider returned an invalid Milk commit", turn)
                    if not can_commit:
                        last_rejection = "commit_before_read"
                        result = {"accepted": False, "error": "read the prepared input before committing"}
                    else:
                        try:
                            committed = validate(arguments["result"])
                            continue
                        except ValueError as error:
                            last_rejection = str(error)
                            result = {"accepted": False, "error": str(error)}
                elif not arguments and name == "milk_job_read":
                    result = input_value if not read_seen else {"schema_version": "milk.job-input-reference.v2", "input_sha256": input_sha256, "already_read": True}
                    read_seen = True
                elif not arguments and name == "milk_status":
                    result = {"schema_version": "milk.job-status.v2", "job": job, "state": "active", "input_sha256": input_sha256, "turn": turn}
                else:
                    raise ProviderError(f"{job} provider requested an unavailable tool", turn)
                messages.append({"role": "tool", "tool_call_id": call_id, "name": name, "content": canonical(result).decode()})
            if committed is not None:
                receipt = {
                    "schema_version": "milk.semantic-provider-receipt.v2",
                    "job": job,
                    "provider_request_id": request_ids[-1] if request_ids else None,
                    "provider_request_ids": request_ids,
                    "model": model,
                    "usage": dict(usage),
                    "inference_calls": turn,
                    "input_sha256": input_sha256,
                    "output": committed,
                    "output_sha256": digest(committed),
                }
                return committed, receipt
    raise ProviderError(f"{job} provider did not commit within four turns: tools={','.join(last_tools)} rejection={last_rejection}", 4)
