#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

if [[ $# -ne 0 ]]; then
	echo "usage: $0" >&2
	exit 2
fi

PYTHON="${MILK_MAN_PYTHON:-python3}"
if [[ "$PYTHON" != /* ]]; then
	PYTHON="$(command -v "$PYTHON")" || {
		echo "milk-jobs: MILK_MAN_PYTHON is not executable" >&2
		exit 2
	}
	PYTHON="$(cd "$(dirname "$PYTHON")" && pwd -P)/$(basename "$PYTHON")"
fi
[[ -x "$PYTHON" ]] || {
	echo "milk-jobs: MILK_MAN_PYTHON is not executable" >&2
	exit 2
}
VERSION="$("$PYTHON" -E -S -c 'import sys; print(sys.version_info.major * 100 + sys.version_info.minor)')"
[[ "$VERSION" =~ ^[0-9]+$ && "$VERSION" -ge 310 ]] || {
	echo "milk-jobs: Python 3.10 or newer is required" >&2
	exit 2
}

case "${MILK_RUN_PROFILE:-}" in
	production|mechanics) ;;
	*)
		echo "milk-jobs: MILK_RUN_PROFILE must be production or mechanics" >&2
		exit 2
		;;
esac
if [[ -z "${MILK_RUN_ONCE_CONFIG:-}" ]]; then
	MILK_RUN_ONCE_CONFIG="$ROOT/milk/jobs.$MILK_RUN_PROFILE.json"
fi
if [[ -z "${MILK_MAN_REVISION:-}" ]]; then
	MILK_MAN_REVISION="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null)" || {
		echo "milk-jobs: MILK_MAN_REVISION is required outside a Git checkout" >&2
		exit 2
	}
fi
export MILK_MAN_REVISION MILK_RUN_ONCE_CONFIG MILK_RUN_PROFILE

cd "$ROOT/.prime/agent/skills/milk-jobs/src"
unset PYTHONHOME PYTHONPATH
exec "$PYTHON" -E -S -m milk_jobs
