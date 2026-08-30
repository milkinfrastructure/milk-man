#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

die() {
	echo "self-improve: $*" >&2
	exit 2
}

[[ $# -eq 1 ]] || die "usage: MILK_MAN_STATE_DIR=/private/path OPENAI_API_KEY=... $0 <task>"
: "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"
: "${MILK_MAN_STATE_DIR:?MILK_MAN_STATE_DIR is required}"
[[ "$MILK_MAN_STATE_DIR" == /* ]] || die "MILK_MAN_STATE_DIR must be absolute"
[[ -x "$ROOT/node_modules/.bin/srt" ]] || die "run npm ci first"
[[ "$(uname -s)" == Darwin ]] || die "the local launcher currently requires APFS clone support on macOS"
[[ -z "$(git -C "$ROOT" status --porcelain)" ]] || die "the source checkout must be clean"

mkdir -p "$MILK_MAN_STATE_DIR"
STATE="$(cd "$MILK_MAN_STATE_DIR" && pwd -P)"
HOST_HOME="$(cd "$HOME" && pwd -P)"
case "$STATE" in
	/|"$HOST_HOME"|"$ROOT"|"$ROOT"/*) die "MILK_MAN_STATE_DIR must be a dedicated path outside the source checkout" ;;
esac
case "$ROOT" in
	"$STATE"/*) die "MILK_MAN_STATE_DIR cannot contain the source checkout" ;;
esac

HEAD="$(git -C "$ROOT" rev-parse --verify HEAD)"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-${HEAD:0:12}-$$"
CONTROL="$STATE/control/$RUN_ID"
WORKTREE="$STATE/worktrees/$RUN_ID"
CONFIG="$STATE/config"
SESSIONS="$STATE/sessions"
TMP="$STATE/tmp"
HOME_DIR="$STATE/home"
VENV="$STATE/kernel-venv"
ARTIFACTS="$STATE/session-artifacts"
WORKTREE_CREATED=0

report_retained_worktree() {
	local code=$?
	if [[ "$WORKTREE_CREATED" -eq 1 ]]; then
		echo "Retained worktree: $WORKTREE"
	fi
	trap - EXIT
	exit "$code"
}
trap report_retained_worktree EXIT

mkdir -p "$CONTROL" "$CONFIG" "$SESSIONS" "$TMP" "$HOME_DIR" "$ARTIFACTS" "$STATE/worktrees"
chmod 700 "$STATE" "$CONTROL" "$CONFIG" "$SESSIONS" "$TMP" "$HOME_DIR" "$ARTIFACTS" "$STATE/worktrees"
install -m 600 "$ROOT/milk/self-improve-settings.json" "$CONFIG/settings.json"
printf '{}\n' >"$CONFIG/auth.json"
cp -R "$ROOT/packages/coding-agent/skills/refine" "$CONTROL/refine"

# Bootstrap trusted runtime code before the model-controlled process starts.
env -i \
	PATH="${PATH:-/usr/bin:/bin}" \
	HOME="$HOME_DIR" \
	TMPDIR="$TMP" \
	PRIME_AGENT_KERNEL_VENV="$VENV" \
	DO_NOT_TRACK=1 \
	PI_SKIP_VERSION_CHECK=1 \
	"$ROOT/node_modules/.bin/tsx" "$ROOT/packages/coding-agent/src/core/kernel/bootstrap-cli.ts"
KERNEL_PYTHON="$VENV/bin/python"

git -C "$ROOT" worktree add --detach "$WORKTREE" "$HEAD"
WORKTREE_CREATED=1
[[ "$(git -C "$WORKTREE" rev-parse HEAD)" == "$HEAD" ]] || die "worktree HEAD changed"
cp -cR "$ROOT/node_modules" "$WORKTREE/node_modules"
[[ -L "$WORKTREE/node_modules/.bin/srt" ]] || die "node_modules clone did not preserve relative symlinks"
[[ "$(readlink "$WORKTREE/node_modules/.bin/srt")" == "$(readlink "$ROOT/node_modules/.bin/srt")" ]] ||
	die "node_modules clone changed the srt symlink"

SRT_SETTINGS="$CONTROL/srt.json"
PYTHON_ROOT="$("$KERNEL_PYTHON" -c 'import os, sys; print(os.path.dirname(os.path.dirname(os.path.realpath(sys.executable))))')"
node - "$SRT_SETTINGS" "$HOST_HOME" "$ROOT" "$WORKTREE" "$STATE" "$CONTROL" "$VENV" "$PYTHON_ROOT" <<'NODE'
const fs = require("node:fs");
const path = require("node:path");
const [out, home, root, worktree, state, control, venv, pythonRoot] = process.argv.slice(2);
const config = {
	network: {
		allowedDomains: [],
		deniedDomains: ["*"],
		strictAllowlist: true,
		allowUnixSockets: [],
		allowLocalBinding: false,
	},
	filesystem: {
		denyRead: [path.dirname(home), root, path.join(worktree, ".git")],
		allowRead: [
			worktree,
			path.join(state, "tmp"),
			path.join(state, "session-artifacts"),
			path.join(control, "refine"),
			venv,
			pythonRoot,
		],
		allowWrite: [
			worktree,
			path.join(state, "tmp"),
			path.join(state, "session-artifacts", "**", "kernel-state.dill"),
			path.join(state, "session-artifacts", "**", "kernel-state.dill.*.tmp"),
			path.join(state, "session-artifacts", "**", "kernel-state.json"),
			path.join(state, "session-artifacts", "**", "kernel-state.json.*.tmp"),
		],
		denyWrite: [path.join(worktree, ".git"), path.join(worktree, "node_modules"), control, venv],
	},
	allowAppleEvents: false,
};
fs.writeFileSync(out, `${JSON.stringify(config, null, 2)}\n`, { mode: 0o600 });
NODE

GATE="$CONTROL/check"
printf '#!/usr/bin/env bash\ncd %q\nexec env -i PATH=%q HOME=%q TMPDIR=%q CLAUDE_CODE_TMPDIR=%q NO_COLOR=1 %q --settings %q npm run check\n' \
	"$WORKTREE" "${PATH:-/usr/bin:/bin}" "$HOME_DIR" "$TMP" "$TMP" "$ROOT/node_modules/.bin/srt" "$SRT_SETTINGS" >"$GATE"
chmod 700 "$GATE"

echo "Retained worktree: $WORKTREE"
echo "Persistent state: $STATE"

set +e
env -i \
	PATH="${PATH:-/usr/bin:/bin}" \
	LANG="${LANG:-C}" \
	HOME="$HOME_DIR" \
	TMPDIR="$TMP" \
	CLAUDE_CODE_TMPDIR="$TMP" \
	OPENAI_API_KEY="$OPENAI_API_KEY" \
	PRIME_AGENT_CODING_AGENT_DIR="$CONFIG" \
	PRIME_AGENT_KERNEL_VENV="$VENV" \
	PRIME_AGENT_KERNEL_SANDBOX_COMMAND="$ROOT/node_modules/.bin/srt" \
	PRIME_AGENT_KERNEL_SANDBOX_SETTINGS="$SRT_SETTINGS" \
	PRIME_AGENT_KERNEL_HOST_REQUEST_ALLOWLIST=refine.run,refine.status \
	PRIME_AGENT_STRIP_TOOL_SECRETS=1 \
	DO_NOT_TRACK=1 \
	PI_SKIP_VERSION_CHECK=1 \
	"$ROOT/prime-agent.sh" \
	--cwd "$WORKTREE" \
	--session-dir "$SESSIONS" \
	--model openai/gpt-5.6-luna \
	--thinking low \
	--tools ipython \
	--no-extensions \
	--no-skills \
	--skill "$CONTROL/refine/SKILL.md" \
	--no-prompt-templates \
	--no-themes \
	--no-context-files \
	--autonomous \
	--autonomous-gate "$GATE" \
	--autonomous-gate-retries 1 \
	--autonomous-gate-timeout-ms 300000 \
	--autonomous-max-continuations 3 \
	--autonomous-max-turns 4 \
	--autonomous-max-tokens 20000 \
	--autonomous-timeout-ms 900000 \
	--append-system-prompt "Improve Milk Man itself, not Milk jobs. Work only in the disposable checkout. Do not use git, edit node_modules, push, deploy, call Milk providers, write object storage, or publish routes. After validation, persist at most one reusable lesson with await refine.run('focused lesson', global_=True); otherwise do not refine." \
	-- "$1"
STATUS=$?
set -e

exit "$STATUS"
