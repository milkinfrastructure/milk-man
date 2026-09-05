#!/usr/bin/env python3
"""Read or stop one exact Baseten training job; never create a job."""

import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from milk_v2.providers import baseten
from milk_v2.state import redact

TERMINAL = {
    "TRAINING_JOB_COMPLETED": "completed",
    "TRAINING_JOB_FAILED": "failed",
    "TRAINING_JOB_STOPPED": "stopped",
    "TRAINING_JOB_CANCELED": "canceled",
}


def main():
    client = None
    identity = "baseten-training"
    try:
        if sys.argv[1:] not in ([], ["run"], ["status"], ["stop"]):
            raise ValueError("usage: baseten_training.py [run|status|stop]")
        action = sys.argv[1] if len(sys.argv) > 1 else "status"
        project = os.environ["BASETEN_TRAINING_PROJECT_ID"]
        job_id = os.environ["MILK_TRAIN_PROVIDER_JOB_ID"]
        if any(not re.fullmatch(r"[a-z0-9]{5,32}", value) for value in (project, job_id)):
            raise ValueError("Baseten training project or job ID is invalid")
        identity = project + "/" + job_id
        timeout = int(os.environ.get("MILK_TRAIN_TIMEOUT_SECONDS", "30"))
        if not 1 <= timeout <= 120:
            raise ValueError("MILK_TRAIN_TIMEOUT_SECONDS must be in 1..120")
        client = baseten.Client(os.environ["BASETEN_API_KEY"], timeout)
        job = client.get(project, job_id)
        status = job.get("current_status")
        if not isinstance(status, str) or not status.startswith("TRAINING_JOB_"):
            raise ValueError("Baseten training job returned an invalid status")
        stop_requested = action == "stop" and status not in TERMINAL
        if stop_requested:
            client.stop_training(project, job_id)
            job = client.get(project, job_id)
        status = job.get("current_status")
        if not isinstance(status, str) or not status.startswith("TRAINING_JOB_"):
            raise ValueError("Baseten training job returned an invalid status")
        outcome = TERMINAL.get(status)
        print(json.dumps({
            "state": "complete" if outcome else "active", "identity": identity,
            "inference_calls": 0, "provider_calls": client.calls,
            "details": {"provider": "baseten", "project_id": project, "provider_job_id": job_id,
                        "status": status, "terminal": outcome is not None, "outcome": outcome,
                        "stop_requested": stop_requested,
                        "note": "Training job status only; this is not an account-wide zero-GPU check."},
        }, separators=(",", ":")))
        return 0
    except (KeyError, ValueError, OSError, baseten.ProviderError) as error:
        print(json.dumps({"state": "failed", "identity": identity, "inference_calls": 0,
                          "provider_calls": client.calls if client else 0,
                          "error": redact(str(error))}, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
