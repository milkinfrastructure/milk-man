"""Scale-to-zero Modal server for Milk Man's pinned GLM controller."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

import modal


MODEL_REPO = "zai-org/GLM-4.5-Air-FP8"
MODEL_REVISION = "f9a9c5acf5e543cd24d659a056c5dbcda78ffcfc"
SERVED_MODEL = "glm-4.5-air-fp8"
SGLANG_IMAGE = "lmsysorg/sglang@sha256:34d728fd77f57ae62f5bf236239ed48774f1e96f8a293adf2e1e29bfe5949bbb"
PORT = 8000
VOLUME_SUBPATH = f"glm-4.5-air-fp8/{MODEL_REVISION}"
MODEL_PATH = Path("/models") / VOLUME_SUBPATH
MARKER = MODEL_PATH / ".milk-model.json"

APP_NAME = os.environ["MILK_MODAL_CONTROLLER_APP_NAME"]
VOLUME_NAME = os.environ["MILK_MODAL_CONTROLLER_VOLUME_NAME"]
ROUTING_REGION = os.environ.get("MILK_MODAL_ROUTING_REGION", "us-west")
CONTROLLER_API_KEY = os.environ["MILK_CONTROLLER_API_KEY"]
if not CONTROLLER_API_KEY or "\n" in CONTROLLER_API_KEY or "\r" in CONTROLLER_API_KEY:
    raise RuntimeError("MILK_CONTROLLER_API_KEY is invalid")

volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=False)
download_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "huggingface_hub==1.27.0"
).env({"HF_XET_HIGH_PERFORMANCE": "1"})
server_image = modal.Image.from_registry(SGLANG_IMAGE).entrypoint([]).env(
    {"HF_HUB_OFFLINE": "1"}
)
controller_secret = modal.Secret.from_dict(
    {"MILK_CONTROLLER_API_KEY": CONTROLLER_API_KEY}
)
app = modal.App(APP_NAME)


def marker_value() -> dict:
    return {
        "schema_version": "milk.modal-model-cache.v2",
        "model_repo": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "volume_subpath": VOLUME_SUBPATH,
    }


@app.function(
    image=download_image,
    volumes={"/models": volume},
    cpu=8,
    memory=32768,
    ephemeral_disk=524288,
    timeout=6 * 60 * 60,
)
def hydrate() -> dict:
    from huggingface_hub import snapshot_download

    expected = marker_value()
    if MARKER.exists():
        if json.loads(MARKER.read_text()) != expected:
            raise RuntimeError("controller cache marker differs from the pinned model")
        return expected
    MODEL_PATH.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_REPO,
        revision=MODEL_REVISION,
        local_dir=MODEL_PATH,
    )
    if not (MODEL_PATH / "config.json").is_file():
        raise RuntimeError("controller cache has no config.json")
    MARKER.write_text(json.dumps(expected, sort_keys=True, separators=(",", ":")) + "\n")
    volume.commit()
    return expected


@app.server(
    image=server_image,
    secrets=[controller_secret],
    gpu="H200",
    cpu=16,
    volumes={"/models": volume.with_mount_options(read_only=True)},
    port=PORT,
    unauthenticated=True,
    routing_region=ROUTING_REGION,
    min_containers=0,
    max_containers=1,
    scaledown_window=60,
    startup_timeout=30 * 60,
    exit_grace_period=30,
    target_concurrency=8,
)
class Controller:
    @modal.enter()
    def start(self) -> None:
        if not MARKER.is_file() or json.loads(MARKER.read_text()) != marker_value():
            raise RuntimeError("pinned controller weights are not hydrated")
        command = [
            "python3", "-m", "sglang.launch_server",
            "--model-path", str(MODEL_PATH),
            "--served-model-name", SERVED_MODEL,
            "--host", "0.0.0.0",
            "--port", str(PORT),
            "--api-key", os.environ["MILK_CONTROLLER_API_KEY"],
            "--tp-size", "1",
            "--tool-call-parser", "glm45",
            "--reasoning-parser", "glm45",
            "--speculative-algorithm", "EAGLE",
            "--speculative-num-steps", "3",
            "--speculative-eagle-topk", "1",
            "--speculative-num-draft-tokens", "4",
            "--mem-fraction-static", "0.7",
            "--disable-shared-experts-fusion",
            "--context-length", "32768",
        ]
        self.process = subprocess.Popen(command, start_new_session=True)
        deadline = time.monotonic() + 25 * 60
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"SGLang exited with {self.process.returncode}")
            try:
                with urlopen(f"http://127.0.0.1:{PORT}/health", timeout=5) as response:
                    if response.status == 200:
                        return
            except OSError:
                time.sleep(5)
        raise TimeoutError("SGLang did not become ready")

    @modal.exit()
    def stop(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=25)
        except subprocess.TimeoutExpired:
            self.process.kill()
