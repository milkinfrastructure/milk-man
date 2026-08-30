from __future__ import annotations

import asyncio
import json

from milk_jobs import MilkJobError, reconcile


def main() -> None:
    try:
        report = asyncio.run(reconcile())
    except MilkJobError as error:
        raise SystemExit(f"milk-jobs: {error}") from error
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
