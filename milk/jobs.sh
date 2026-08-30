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

cd "$ROOT/.prime/agent/skills/milk-jobs/src"
unset PYTHONHOME PYTHONPATH
exec "$PYTHON" -E -S -m milk_jobs
