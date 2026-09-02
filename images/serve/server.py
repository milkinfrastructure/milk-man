from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import uuid

import torch
from torchao.quantization import Float8StaticActivationFloat8WeightConfig, quantize_
from transformers import AutoModelForCausalLM, AutoTokenizer


SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SERVED_MODEL = "milk-qwen3.5-0.8b-static-fp8"
MAX_BODY_BYTES = 4 * 1024 * 1024
MAX_NEW_TOKENS = 2048


def required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"{name} is required")
    return value


def model_root() -> Path:
    root = Path(required("BT_LOAD_CHECKPOINT_DIR"))
    candidates = []
    for config in root.glob("**/config.json"):
        parent = config.parent
        if (parent / "tokenizer_config.json").is_file() and any(parent.glob("*.safetensors")):
            candidates.append(parent)
    if len(candidates) != 1:
        raise ValueError("loaded checkpoint has no unique merged model")
    return candidates[0]


def integer(value, name: str, default: int, maximum: int) -> int:
    value = default if value is None else value
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be in 1..{maximum}")
    return value


def text_content(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if not isinstance(item, dict) or item.get("type") not in {"text", "input_text"} or not isinstance(item.get("text"), str):
                raise ValueError("only text message content is supported")
            parts.append(item["text"])
        return "\n".join(parts)
    raise ValueError("message content must be text")


def messages(value) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise ValueError("messages must be a nonempty array")
    output = []
    for item in value:
        if not isinstance(item, dict) or item.get("role") not in {"system", "user", "assistant"}:
            raise ValueError("message role is unsupported")
        output.append({"role": item["role"], "content": text_content(item.get("content"))})
    return output


class Runtime:
    def __init__(self):
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required")
        self.artifact_sha256 = required("MILK_CANDIDATE_ARTIFACT_SHA256")
        if SHA256.fullmatch(self.artifact_sha256) is None:
            raise ValueError("MILK_CANDIDATE_ARTIFACT_SHA256 must be lowercase SHA-256")
        try:
            scale = float(required("MILK_CANDIDATE_ACTIVATION_SCALE"))
        except ValueError as error:
            raise ValueError("MILK_CANDIDATE_ACTIVATION_SCALE must be numeric") from error
        if not 0 < scale < 1:
            raise ValueError("MILK_CANDIDATE_ACTIVATION_SCALE is invalid")
        expected = integer(int(required("MILK_CANDIDATE_LINEAR_COUNT")), "MILK_CANDIDATE_LINEAR_COUNT", 187, 10000)
        checkpoint = model_root()
        self.tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            checkpoint,
            local_files_only=True,
            torch_dtype=torch.bfloat16,
        ).cuda().eval()
        scale_tensor = torch.tensor(scale, dtype=torch.float32, device="cuda")
        quantize_(self.model, Float8StaticActivationFloat8WeightConfig(scale=scale_tensor))
        self.quantized_linear_count = sum(
            1
            for module in self.model.modules()
            if isinstance(module, torch.nn.Linear) and module.weight.__class__.__module__.startswith("torchao.")
        )
        if self.quantized_linear_count != expected:
            raise RuntimeError("quantized linear count differs from the evaluated winner")
        self.lock = threading.Lock()

    def generate(self, payload: dict) -> tuple[str, int, int]:
        request_messages = messages(payload.get("messages"))
        maximum = integer(
            payload.get("max_completion_tokens", payload.get("max_tokens")),
            "max_tokens",
            256,
            MAX_NEW_TOKENS,
        )
        prompt = self.tokenizer.apply_chat_template(
            request_messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        encoded = self.tokenizer(prompt, return_tensors="pt").to("cuda")
        with self.lock, torch.no_grad():
            generated = self.model.generate(
                **encoded,
                do_sample=False,
                max_new_tokens=maximum,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        prompt_tokens = encoded.input_ids.shape[1]
        output = generated[0, prompt_tokens:]
        return self.tokenizer.decode(output, skip_special_tokens=True), prompt_tokens, output.shape[0]


RUNTIME = Runtime()


class Handler(BaseHTTPRequestHandler):
    server_version = "milk-candidate/1"

    def log_message(self, format, *args):
        print(json.dumps({"event": "http", "message": format % args}, separators=(",", ":")))

    def body(self) -> dict:
        try:
            length = int(self.headers.get("content-length", ""))
        except ValueError as error:
            raise ValueError("content-length is required") from error
        if not 1 <= length <= MAX_BODY_BYTES:
            raise ValueError("request body is empty or oversized")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("request body must be an object")
        return value

    def send_json(self, status: int, value: dict):
        body = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_chat_stream(self, identifier: str, output: str):
        created = int(time.time())
        chunks = [
            {
                "id": identifier,
                "object": "chat.completion.chunk",
                "created": created,
                "model": SERVED_MODEL,
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": output}, "finish_reason": None}],
            },
            {
                "id": identifier,
                "object": "chat.completion.chunk",
                "created": created,
                "model": SERVED_MODEL,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            },
        ]
        body = b"".join(b"data: " + json.dumps(chunk, separators=(",", ":"), ensure_ascii=False).encode() + b"\n\n" for chunk in chunks)
        body += b"data: [DONE]\n\n"
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {
                "status": "ok",
                "model": SERVED_MODEL,
                "artifact_sha256": RUNTIME.artifact_sha256,
                "quantization": "static_fp8",
                "quantized_linear_count": RUNTIME.quantized_linear_count,
            })
        elif self.path == "/v1/models":
            self.send_json(200, {"object": "list", "data": [{"id": SERVED_MODEL, "object": "model", "owned_by": "milkinfrastructure"}]})
        else:
            self.send_json(404, {"error": {"message": "not found", "type": "invalid_request_error"}})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_json(404, {"error": {"message": "not found", "type": "invalid_request_error"}})
            return
        try:
            payload = self.body()
            requested_model = payload.get("model")
            if not isinstance(requested_model, str) or not requested_model:
                raise ValueError("model is required")
            output, prompt_tokens, completion_tokens = RUNTIME.generate(payload)
            identifier = "chatcmpl-" + uuid.uuid4().hex
            if payload.get("stream") is True:
                self.send_chat_stream(identifier, output)
                return
            self.send_json(200, {
                "id": identifier,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": SERVED_MODEL,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": output}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
            })
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self.send_json(400, {"error": {"message": str(error), "type": "invalid_request_error"}})
        except Exception:
            self.send_json(500, {"error": {"message": "candidate inference failed", "type": "server_error"}})


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8000), Handler)
    print(json.dumps({
        "event": "ready",
        "model": SERVED_MODEL,
        "artifact_sha256": RUNTIME.artifact_sha256,
        "quantized_linear_count": RUNTIME.quantized_linear_count,
    }, separators=(",", ":")))
    server.serve_forever()


if __name__ == "__main__":
    main()
