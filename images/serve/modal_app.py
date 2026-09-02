"""Scale-to-zero Modal deployment for one sealed Milk candidate."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import modal


SHA256 = re.compile(r"[0-9a-f]{64}\Z")
NAME = re.compile(r"[a-z0-9][a-z0-9-]{1,62}\Z")
IMAGE = re.compile(r"ghcr\.io/milkinfrastructure/milk-man-serve@sha256:[0-9a-f]{64}\Z")

APP_NAME = os.environ["MILK_MODAL_CANDIDATE_APP_NAME"]
VOLUME_NAME = os.environ["MILK_MODAL_CANDIDATE_VOLUME_NAME"]
SERVE_IMAGE = os.environ["MILK_SERVE_IMAGE"]
ARTIFACT_SHA256 = os.environ["MILK_CANDIDATE_ARTIFACT_SHA256"]
BRANCH = os.environ["MILK_CANDIDATE_BRANCH"]
ACTIVATION_SCALE = os.environ.get("MILK_CANDIDATE_ACTIVATION_SCALE")
LINEAR_COUNT = os.environ["MILK_CANDIDATE_LINEAR_COUNT"]
GPU = os.environ.get("MILK_CANDIDATE_ACCELERATOR", "H100")
ROUTING_REGION = os.environ.get("MILK_MODAL_ROUTING_REGION", "us-west")
MODEL_ROOT = Path("/models") / ARTIFACT_SHA256
MARKER = MODEL_ROOT / ".milk-checkpoint.json"

if (
    NAME.fullmatch(APP_NAME) is None
    or NAME.fullmatch(VOLUME_NAME) is None
    or IMAGE.fullmatch(SERVE_IMAGE) is None
    or SHA256.fullmatch(ARTIFACT_SHA256) is None
    or BRANCH not in {"bf16", "dynamic_fp8", "static_fp8"}
    or (BRANCH == "static_fp8") != (ACTIVATION_SCALE is not None)
    or GPU not in {"H100", "H200"}
):
    raise RuntimeError("Modal candidate configuration is invalid")

candidate_key = os.environ.get("MILK_CANDIDATE_API_KEY", "")
if modal.is_local() and (not candidate_key or "\n" in candidate_key or "\r" in candidate_key):
    raise RuntimeError("MILK_CANDIDATE_API_KEY is invalid")
candidate_secret = modal.Secret.from_dict(
    {"MILK_CANDIDATE_API_KEY": candidate_key} if candidate_key else {}
)

runtime_environment = {
    "BT_LOAD_CHECKPOINT_DIR": str(MODEL_ROOT),
    "MILK_CANDIDATE_ARTIFACT_SHA256": ARTIFACT_SHA256,
    "MILK_CANDIDATE_BRANCH": BRANCH,
    "MILK_CANDIDATE_LINEAR_COUNT": LINEAR_COUNT,
}
definition_environment = {
    "MILK_MODAL_CANDIDATE_APP_NAME": APP_NAME,
    "MILK_MODAL_CANDIDATE_VOLUME_NAME": VOLUME_NAME,
    "MILK_SERVE_IMAGE": SERVE_IMAGE,
    "MILK_CANDIDATE_ARTIFACT_SHA256": ARTIFACT_SHA256,
    "MILK_CANDIDATE_BRANCH": BRANCH,
    "MILK_CANDIDATE_LINEAR_COUNT": LINEAR_COUNT,
    "MILK_CANDIDATE_ACCELERATOR": GPU,
    "MILK_MODAL_ROUTING_REGION": ROUTING_REGION,
}
if ACTIVATION_SCALE is not None:
    runtime_environment["MILK_CANDIDATE_ACTIVATION_SCALE"] = ACTIVATION_SCALE
    definition_environment["MILK_CANDIDATE_ACTIVATION_SCALE"] = ACTIVATION_SCALE
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=False)
hydrate_image = modal.Image.debian_slim(python_version="3.12").env(definition_environment)
serve_image = modal.Image.from_registry(SERVE_IMAGE).entrypoint([]).env(
    {**definition_environment, **runtime_environment}
)
app = modal.App(APP_NAME)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_manifest(files: list[dict]) -> dict:
    expected = []
    for item in files:
        relative = PurePosixPath(item.get("path", ""))
        size = item.get("bytes")
        digest = item.get("sha256")
        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
            or type(size) is not int
            or size < 1
            or not isinstance(digest, str)
            or SHA256.fullmatch(digest) is None
        ):
            raise ValueError("checkpoint manifest is invalid")
        expected.append({"path": relative.as_posix(), "bytes": size, "sha256": digest})
    expected.sort(key=lambda item: item["path"])
    if not expected or len({item["path"] for item in expected}) != len(expected):
        raise ValueError("checkpoint manifest is empty or duplicated")
    identity = {
        "schema_version": "milk.modal-candidate-cache.v2",
        "artifact_sha256": ARTIFACT_SHA256,
        "files": expected,
    }
    return {**identity, "manifest_sha256": hashlib.sha256(canonical(identity)).hexdigest()}


@app.function(
    image=hydrate_image,
    volumes={"/models": volume},
    cpu=4,
    memory=16384,
    timeout=60 * 60,
)
def hydrate(files: list[dict]) -> dict:
    marker = expected_manifest(files)
    if MARKER.is_file() and json.loads(MARKER.read_text()) == marker:
        return {key: marker[key] for key in ("schema_version", "artifact_sha256", "manifest_sha256")}
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    by_path = {item["path"]: item for item in files}
    for expected in marker["files"]:
        source = by_path[expected["path"]]
        parsed = urlsplit(source.get("url", ""))
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("checkpoint URL is invalid")
        target = MODEL_ROOT.joinpath(*PurePosixPath(expected["path"]).parts)
        if target.is_file() and target.stat().st_size == expected["bytes"] and file_sha256(target) == expected["sha256"]:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name("." + target.name + ".partial")
        digest = hashlib.sha256()
        written = 0
        try:
            with urlopen(source["url"], timeout=120) as response, temporary.open("wb") as output:
                for block in iter(lambda: response.read(8 * 1024 * 1024), b""):
                    output.write(block)
                    digest.update(block)
                    written += len(block)
            if written != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
                raise ValueError("checkpoint file identity differs")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    MARKER.write_bytes(canonical(marker))
    volume.commit()
    return {key: marker[key] for key in ("schema_version", "artifact_sha256", "manifest_sha256")}


@app.server(
    image=serve_image,
    secrets=[candidate_secret],
    gpu=GPU,
    cpu=4,
    memory=32768,
    volumes={"/models": volume.with_mount_options(read_only=True)},
    port=8000,
    unauthenticated=True,
    routing_region=ROUTING_REGION,
    min_containers=0,
    max_containers=1,
    scaledown_window=60,
    startup_timeout=20 * 60,
    exit_grace_period=30,
    target_concurrency=1,
)
class Candidate:
    @modal.enter()
    def start(self) -> None:
        if not MARKER.is_file():
            raise RuntimeError("candidate checkpoint is not hydrated")
        self.process = subprocess.Popen(["python", "/opt/milk/server.py"], start_new_session=True)
        request = Request(
            "http://127.0.0.1:8000/health",
            headers={"Authorization": "Bearer " + os.environ["MILK_CANDIDATE_API_KEY"]},
        )
        deadline = time.monotonic() + 15 * 60
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"candidate server exited with {self.process.returncode}")
            try:
                with urlopen(request, timeout=5) as response:
                    if response.status == 200:
                        return
            except OSError:
                time.sleep(3)
        raise TimeoutError("candidate server did not become ready")

    @modal.exit()
    def stop(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
