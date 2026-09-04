"""Environment-selected, scale-to-zero vLLM server for Milk Man."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

import modal


APP_NAME = os.environ["MILK_MODAL_SERVE_APP_NAME"]
PROFILE_ID = os.environ["MILK_MODAL_SERVE_PROFILE_ID"]
CACHE_ID = os.environ["MILK_MODAL_SERVE_CACHE_ID"]
VOLUME_NAME = os.environ["MILK_MODAL_SERVE_VOLUME"]
MODEL = os.environ["MILK_MODAL_SERVE_MODEL"]
REVISION = os.environ["MILK_MODAL_SERVE_REVISION"]
SERVED_MODEL = os.environ["MILK_MODAL_SERVE_SERVED_MODEL"]
IMAGE = os.environ["MILK_MODAL_SERVE_IMAGE"]
GPU = os.environ["MILK_MODAL_SERVE_GPU"]
GPU_COUNT = int(os.environ["MILK_MODAL_SERVE_GPU_COUNT"])
VLLM_ARGS = json.loads(os.environ.get("MILK_MODAL_SERVE_VLLM_ARGS_JSON", "[]"))
ROUTING_REGION = os.environ.get("MILK_MODAL_ROUTING_REGION", "us-west")
SCALEDOWN_SECONDS = int(os.environ.get("MILK_MODAL_SERVE_SCALEDOWN_SECONDS", "60"))
TARGET_CONCURRENCY = int(os.environ.get("MILK_MODAL_SERVE_TARGET_CONCURRENCY", "8"))
MODEL_PATH = Path("/models") / CACHE_ID
MARKER = MODEL_PATH / ".milk-model.json"
PUBLIC_ENV = {
    "MILK_MODAL_SERVE_APP_NAME": APP_NAME,
    "MILK_MODAL_SERVE_PROFILE_ID": PROFILE_ID,
    "MILK_MODAL_SERVE_CACHE_ID": CACHE_ID,
    "MILK_MODAL_SERVE_VOLUME": VOLUME_NAME,
    "MILK_MODAL_SERVE_MODEL": MODEL,
    "MILK_MODAL_SERVE_REVISION": REVISION,
    "MILK_MODAL_SERVE_SERVED_MODEL": SERVED_MODEL,
    "MILK_MODAL_SERVE_IMAGE": IMAGE,
    "MILK_MODAL_SERVE_GPU": GPU,
    "MILK_MODAL_SERVE_GPU_COUNT": str(GPU_COUNT),
    "MILK_MODAL_SERVE_VLLM_ARGS_JSON": json.dumps(VLLM_ARGS, separators=(",", ":")),
    "MILK_MODAL_ROUTING_REGION": ROUTING_REGION,
    "MILK_MODAL_SERVE_SCALEDOWN_SECONDS": str(SCALEDOWN_SECONDS),
    "MILK_MODAL_SERVE_TARGET_CONCURRENCY": str(TARGET_CONCURRENCY),
}

api_key = os.environ.get("MILK_MODAL_SERVE_API_KEY", "")
if modal.is_local() and (not api_key or "\n" in api_key or "\r" in api_key):
    raise RuntimeError("MILK_MODAL_SERVE_API_KEY is invalid")
runtime_secret = modal.Secret.from_dict(
    {"VLLM_API_KEY": api_key} if api_key else {}
)
hf_token = os.environ.get("HF_TOKEN", "")
hydrate_secrets = [modal.Secret.from_dict({"HF_TOKEN": hf_token})] if hf_token else []

volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
hydrate_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "huggingface_hub==1.27.0"
).env(PUBLIC_ENV)
serve_image = modal.Image.from_registry(IMAGE, add_python="3.12").entrypoint([]).env(
    {**PUBLIC_ENV, "HF_HUB_OFFLINE": "1"}
)
app = modal.App(APP_NAME)


def marker_value() -> dict:
    return {
        "schema_version": "milk.modal-serve-cache.v1",
        "cache_id": CACHE_ID,
        "model": MODEL,
        "revision": REVISION,
    }


@app.function(
    image=hydrate_image,
    secrets=hydrate_secrets,
    volumes={"/models": volume},
    cpu=8,
    memory=32768,
    ephemeral_disk=524288,
    timeout=6 * 60 * 60,
)
def hydrate() -> dict:
    from huggingface_hub import snapshot_download

    expected = marker_value()
    if MARKER.is_file():
        if json.loads(MARKER.read_text()) != expected:
            raise RuntimeError("model cache marker differs")
        return expected
    MODEL_PATH.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL,
        revision=REVISION,
        local_dir=MODEL_PATH,
        token=os.environ.get("HF_TOKEN") or None,
        allow_patterns=["*.jinja", "*.json", "*.model", "*.py", "*.safetensors", "*.txt"],
        ignore_patterns=["metal/*", "original/*"],
    )
    if not (MODEL_PATH / "config.json").is_file():
        raise RuntimeError("model cache has no config.json")
    MARKER.write_text(json.dumps(expected, sort_keys=True, separators=(",", ":")) + "\n")
    volume.commit()
    return expected


@app.server(
    image=serve_image,
    secrets=[runtime_secret],
    gpu=f"{GPU}:{GPU_COUNT}" if GPU_COUNT > 1 else GPU,
    cpu=8,
    memory=32768,
    volumes={"/models": volume.with_mount_options(read_only=True)},
    port=8000,
    unauthenticated=True,
    routing_region=ROUTING_REGION,
    min_containers=0,
    max_containers=1,
    scaledown_window=SCALEDOWN_SECONDS,
    startup_timeout=30 * 60,
    exit_grace_period=30,
    target_concurrency=TARGET_CONCURRENCY,
)
class Model:
    @modal.enter()
    def start(self) -> None:
        if not MARKER.is_file() or json.loads(MARKER.read_text()) != marker_value():
            raise RuntimeError("model weights are not hydrated")
        command = [
            "vllm",
            "serve",
            str(MODEL_PATH),
            "--served-model-name",
            SERVED_MODEL,
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--tensor-parallel-size",
            str(GPU_COUNT),
            *VLLM_ARGS,
        ]
        self.process = subprocess.Popen(command, start_new_session=True)
        deadline = time.monotonic() + 25 * 60
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"vLLM exited with {self.process.returncode}")
            try:
                with urlopen("http://127.0.0.1:8000/health", timeout=5) as response:
                    if response.status == 200:
                        return
            except OSError:
                time.sleep(5)
        raise TimeoutError("vLLM did not become ready")

    @modal.exit()
    def stop(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=25)
        except subprocess.TimeoutExpired:
            self.process.kill()
