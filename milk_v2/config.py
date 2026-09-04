from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re


SCHEMA = "milk.jobs.v2"
STUDENT_SCHEMA = "milk.student-base.v2"
STUDENT_MODEL_REPO = "Qwen/Qwen3.5-0.8B"
STUDENT_MODEL_REVISION = "2fc06364715b967f1860aea9cf38778875588b17"
HANDLERS = frozenset(
    {
        "inference-ensure",
        "inference-status",
        "inference-stop",
        "summary",
        "eval",
        "dataset",
        "train",
        "evaluate",
        "route-propose-baseten",
        "route-propose-modal",
        "gpu-reconcile-modal",
    }
)
TRIGGERS = frozenset(
    {
        "manual",
        "crossed_capture_threshold",
        "readiness",
        "eval_ready",
        "dataset_ready",
        "training_ready",
        "evaluation_ready",
        "provider_frontier",
    }
)
BINDING_ENVIRONMENTS = {
    "store": {
        "required": ("MILK_SCOPE_ID", "MILK_STORE_KIND"),
        "optional": (
            "MILK_SCOPE_PROFILE",
            "MILK_STORE_ROOT",
            "MILK_STORE_ENDPOINT",
            "MILK_STORE_REGION",
            "MILK_STORE_BUCKET",
            "MILK_STORE_ACCESS_KEY_ID",
            "MILK_STORE_SECRET_ACCESS_KEY",
            "MILK_STORE_SESSION_TOKEN",
            "MILK_STORE_PATH_STYLE",
            "MILK_STORE_TIMEOUT_SECONDS",
        ),
    },
    "controller": {
        "required": (
            "MODAL_TOKEN_ID",
            "MODAL_TOKEN_SECRET",
            "MODAL_PROXY_TOKEN_ID",
            "MODAL_PROXY_TOKEN_SECRET",
        ),
        "optional": (
            "MODAL_ENVIRONMENT",
            "MILK_MODAL_ENDPOINT_NAME",
            "MILK_MODAL_ENDPOINT_MODEL",
            "MILK_MODAL_ROUTING_REGION",
            "MILK_MODAL_CONTROLLER_APPLY",
            "MILK_MODAL_CONTROLLER_STARTUP_TIMEOUT",
            "MILK_MODAL_STOP_TIMEOUT",
            "MILK_MODAL_CLI",
        ),
    },
    "summary": {
        "required": ("MILK_SUMMARY_BASE_URL", "MILK_SUMMARY_MODEL", "MILK_SUMMARY_API_KEY"),
        "optional": (
            "MILK_SUMMARY_API_MODE",
            "MILK_REASONING_EFFORT",
            "MILK_SUMMARY_THRESHOLDS",
            "MILK_SUMMARY_REPRESENTATIVE_SAMPLE",
            "MILK_SUMMARY_TAIL_SAMPLE",
            "MILK_CLASSIFIER_TEXT_BYTES",
            "MILK_SUMMARY_MAX_OUTPUT_TOKENS",
            "MILK_EVAL_MIN_CAPTURES",
            "MILK_EVAL_REPRESENTATIVE_CASES",
            "MILK_EVAL_TAIL_CASES",
            "MILK_EVAL_MIN_UNIQUE_SOURCES",
            "MILK_EVAL_MIN_PARSE_WILSON_BPS",
            "MILK_EVAL_MAX_ABSTAIN_WILSON_BPS",
        ),
    },
    "eval": {
        "required": ("MILK_EVAL_BASE_URL", "MILK_EVAL_MODEL", "MILK_EVAL_API_KEY"),
        "optional": (
            "MILK_EVAL_API_MODE",
            "MILK_REASONING_EFFORT",
            "MILK_CASES_PER_CONVERSATION",
            "MILK_EVAL_SOURCE_CONVERSATIONS",
            "MILK_EVAL_SHARD_CASES",
            "MILK_EVAL_PRECOMPUTE_SHARD",
            "MILK_EVAL_MAX_OUTPUT_TOKENS",
        ),
    },
    "teacher": {
        "required": ("MILK_TEACHER_BASE_URL", "MILK_TEACHER_MODEL", "MILK_TEACHER_API_KEY"),
        "optional": ("MILK_TEACHER_API_MODE", "MILK_REASONING_EFFORT", "MILK_TEACHER_MAX_OUTPUT_TOKENS", "MILK_DATASET_TRAIN_EXAMPLES", "MILK_DATASET_TEXT_BYTES"),
    },
    "modal": {
        "required": ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"),
        "optional": ("MODAL_ENVIRONMENT", "MILK_MODAL_ROUTING_REGION", "MILK_MODAL_CLI"),
    },
    "baseten": {
        "required": ("BASETEN_API_KEY", "BASETEN_TRAINING_PROJECT_ID", "MILK_TRAIN_IMAGE"),
        "optional": (
            "BASETEN_TEAM_NAME",
            "BASETEN_TRAINING_ACCELERATOR",
            "MILK_BASETEN_RUNTIME_SECRET_MAP_JSON",
            "MILK_TRAIN_STEPS",
            "MILK_TRAIN_MAX_TOKENS",
            "MILK_TRAIN_LEARNING_RATE",
            "MILK_EVAL_IMAGE",
            "MILK_EVALUATE_MAX_NEW_TOKENS",
        ),
    },
    "candidate-baseten": {
        "required": (
            "BASETEN_API_KEY",
            "MILK_SERVE_IMAGE",
            "MILK_CANDIDATE_API_KEY",
        ),
        "optional": (
            "BASETEN_TEAM_NAME",
            "MILK_CANDIDATE_ACCELERATOR",
            "MILK_ROUTE_CANDIDATE_BPS",
            "MILK_ROUTE_TIMEOUT_SECONDS",
        ),
    },
    "candidate-modal": {
        "required": (
            "BASETEN_API_KEY",
            "MODAL_TOKEN_ID",
            "MODAL_TOKEN_SECRET",
            "MILK_SERVE_IMAGE",
            "MILK_CANDIDATE_API_KEY",
        ),
        "optional": (
            "MODAL_ENVIRONMENT",
            "MILK_CANDIDATE_ACCELERATOR",
            "MILK_MODAL_CANDIDATE_APP_PREFIX",
            "MILK_MODAL_CANDIDATE_VOLUME_PREFIX",
            "MILK_MODAL_ROUTING_REGION",
            "MILK_MODAL_CLI",
            "MILK_ROUTE_CANDIDATE_BPS",
            "MILK_ROUTE_TIMEOUT_SECONDS",
        ),
    },
    "route": {
        "required": (),
        "optional": ("MILK_ROUTE_VERIFY_KEY",),
    },
}
TIMEOUT_ENVIRONMENTS = frozenset(
    {
        "MILK_CONTROLLER_TIMEOUT_SECONDS",
        "MILK_SUMMARY_TIMEOUT_SECONDS",
        "MILK_EVAL_TIMEOUT_SECONDS",
        "MILK_DATASET_TIMEOUT_SECONDS",
        "MILK_TRAIN_TIMEOUT_SECONDS",
        "MILK_EVALUATE_TIMEOUT_SECONDS",
        "MILK_ROUTE_TIMEOUT_SECONDS",
        "MILK_GPU_TIMEOUT_SECONDS",
    }
)
OPERATE_ORDER = ("summary", "eval", "dataset", "train", "evaluate")
ENVIRONMENT_NAME = re.compile(r"[A-Z][A-Z0-9_]{0,127}\Z")
PREFIX = re.compile(r"[a-z][a-z0-9-]{0,31}\Z")


class ConfigError(ValueError):
    pass


def _object(value: object, name: str, required: set[str], optional: set[str] = frozenset()) -> dict:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ConfigError(f"{name} must be an object")
    missing = required - value.keys()
    unknown = value.keys() - required - optional
    if missing or unknown:
        raise ConfigError(f"{name} fields are invalid: missing={sorted(missing)}, unknown={sorted(unknown)}")
    return value


def _string(value: object, name: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise ConfigError(f"{name} is invalid")
    return value


def _environment(value: object, name: str) -> str:
    value = _string(value, name, 128)
    if ENVIRONMENT_NAME.fullmatch(value) is None:
        raise ConfigError(f"{name} must be an environment variable name")
    return value


def _strings(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigError(f"{name} must be a string array")
    if len(value) != len(set(value)):
        raise ConfigError(f"{name} contains duplicates")
    return tuple(value)


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ConfigError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _invalid_constant(value):
    raise ConfigError(f"invalid JSON constant: {value}")


@dataclass(frozen=True)
class Job:
    name: str
    handler: str
    trigger: dict
    bindings: tuple[str, ...]
    input_prefixes: tuple[str, ...]
    output_prefixes: tuple[str, ...]
    system_prompt: str | None
    timeout_env: str
    teardown_handler: str | None


@dataclass(frozen=True)
class StudentBase:
    model_repo: str
    model_revision: str
    digest: str


@dataclass(frozen=True)
class RuntimeConfig:
    jobs: dict[str, Job]
    operate_order: tuple[str, ...]
    student_base: StudentBase
    digest: str

    def job(self, name: str) -> Job:
        try:
            return self.jobs[name]
        except KeyError as error:
            raise ConfigError(f"unknown job: {name}") from error


def load(path: Path | None = None) -> RuntimeConfig:
    root = Path(__file__).resolve().parents[1]
    path = path or root / "config" / "jobs.json"
    try:
        raw = path.read_bytes()
        value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConfigError(f"cannot read job configuration: {error}") from error
    value = _object(value, "configuration", {"schema_version", "environment_bindings", "jobs", "operate_order"})
    if value["schema_version"] != SCHEMA:
        raise ConfigError(f"schema_version must be {SCHEMA}")

    student_path = root / "config" / "student.json"
    try:
        student_raw = student_path.read_bytes()
        student_value = json.loads(
            student_raw,
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConfigError(f"cannot read student configuration: {error}") from error
    student_value = _object(
        student_value,
        "student configuration",
        {"schema_version", "model_repo", "model_revision"},
    )
    if student_value != {
        "schema_version": STUDENT_SCHEMA,
        "model_repo": STUDENT_MODEL_REPO,
        "model_revision": STUDENT_MODEL_REVISION,
    }:
        raise ConfigError("student configuration differs from the reviewed fine-tune base")
    student_canonical = json.dumps(
        student_value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    student_base = StudentBase(
        STUDENT_MODEL_REPO,
        STUDENT_MODEL_REVISION,
        hashlib.sha256(student_canonical).hexdigest(),
    )

    bindings = _object(
        value["environment_bindings"],
        "environment_bindings",
        set(BINDING_ENVIRONMENTS),
    )
    for name, expected in BINDING_ENVIRONMENTS.items():
        binding = _object(bindings[name], f"environment_bindings.{name}", {"required", "optional"})
        required = _strings(binding["required"], f"environment_bindings.{name}.required")
        optional = _strings(binding["optional"], f"environment_bindings.{name}.optional")
        for item in required + optional:
            _environment(item, f"environment_bindings.{name}")
        if required != expected["required"] or optional != expected["optional"]:
            raise ConfigError(f"environment_bindings.{name} differs from the reviewed contract")

    jobs_value = value["jobs"]
    if not isinstance(jobs_value, dict) or set(jobs_value) != HANDLERS:
        raise ConfigError("jobs must contain exactly the reviewed handlers")
    jobs = {}
    for name, raw_job in jobs_value.items():
        if name not in HANDLERS:
            raise ConfigError(f"unreviewed job: {name}")
        raw_job = _object(
            raw_job,
            f"jobs.{name}",
            {
                "handler",
                "trigger",
                "bindings",
                "input_prefixes",
                "output_prefixes",
                "system_prompt",
                "timeout_env",
                "teardown_handler",
            },
        )
        handler = _string(raw_job["handler"], f"jobs.{name}.handler", 64)
        if handler != name or handler not in HANDLERS:
            raise ConfigError(f"jobs.{name}.handler is not reviewed")
        trigger = _object(raw_job["trigger"], f"jobs.{name}.trigger", {"kind"}, {"values_env"})
        kind = _string(trigger["kind"], f"jobs.{name}.trigger.kind", 64)
        if kind not in TRIGGERS:
            raise ConfigError(f"jobs.{name}.trigger.kind is not reviewed")
        if kind == "crossed_capture_threshold":
            if set(trigger) != {"kind", "values_env"} or trigger["values_env"] != "MILK_SUMMARY_THRESHOLDS":
                raise ConfigError("the capture threshold trigger must use MILK_SUMMARY_THRESHOLDS")
        elif set(trigger) != {"kind"}:
            raise ConfigError(f"jobs.{name}.trigger has invalid fields")
        job_bindings = _strings(raw_job["bindings"], f"jobs.{name}.bindings")
        if any(binding not in BINDING_ENVIRONMENTS for binding in job_bindings):
            raise ConfigError(f"jobs.{name}.bindings contains an unreviewed binding")
        input_prefixes = _strings(raw_job["input_prefixes"], f"jobs.{name}.input_prefixes")
        output_prefixes = _strings(raw_job["output_prefixes"], f"jobs.{name}.output_prefixes")
        if any(PREFIX.fullmatch(item) is None for item in input_prefixes + output_prefixes):
            raise ConfigError(f"jobs.{name} contains an invalid object prefix")
        prompt = raw_job["system_prompt"]
        if prompt is not None:
            prompt = _string(prompt, f"jobs.{name}.system_prompt", 256)
            prompt_path = (root / prompt).resolve()
            if root not in prompt_path.parents or not prompt_path.is_file():
                raise ConfigError(f"jobs.{name}.system_prompt is not a repository file")
        timeout_env = _environment(raw_job["timeout_env"], f"jobs.{name}.timeout_env")
        if timeout_env not in TIMEOUT_ENVIRONMENTS:
            raise ConfigError(f"jobs.{name}.timeout_env is not reviewed")
        teardown = raw_job["teardown_handler"]
        if teardown is not None and teardown not in HANDLERS:
            raise ConfigError(f"jobs.{name}.teardown_handler is not reviewed")
        jobs[name] = Job(
            name,
            handler,
            trigger,
            job_bindings,
            input_prefixes,
            output_prefixes,
            prompt,
            timeout_env,
            teardown,
        )

    order = _strings(value["operate_order"], "operate_order")
    if order != OPERATE_ORDER:
        raise ConfigError("operate_order differs from the reviewed contract")
    canonical = json.dumps(
        {"jobs": value, "student_base": student_value},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return RuntimeConfig(jobs, order, student_base, hashlib.sha256(canonical).hexdigest())
