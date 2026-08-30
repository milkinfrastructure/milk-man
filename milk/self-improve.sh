#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

die() {
	echo "self-improve: $*" >&2
	exit 2
}

[[ $# -eq 1 ]] || die "usage: MILK_MAN_STATE_DIR=/private/path OPENAI_API_KEY=milk_live_... $0 <task>"
: "${OPENAI_API_KEY:?OPENAI_API_KEY must contain an operator-issued Milk Carton key}"
: "${MILK_MAN_STATE_DIR:?MILK_MAN_STATE_DIR is required}"
[[ "$OPENAI_API_KEY" == milk_live_* ]] || die "OPENAI_API_KEY must contain an operator-issued Milk Carton key"
[[ "$MILK_MAN_STATE_DIR" == /* ]] || die "MILK_MAN_STATE_DIR must be absolute"
[[ -d "$MILK_MAN_STATE_DIR" ]] || die "MILK_MAN_STATE_DIR must already exist"
[[ -x "$ROOT/node_modules/.bin/srt" ]] || die "run npm ci first"
[[ "$(uname -s)" == Darwin ]] || die "the local launcher currently requires APFS clone support on macOS"
[[ -z "$(git -C "$ROOT" status --porcelain)" ]] || die "the source checkout must be clean"

STATE="$(cd "$MILK_MAN_STATE_DIR" && pwd -P)"
HOST_HOME="$(cd "$HOME" && pwd -P)"
case "$STATE" in
	/|"$HOST_HOME"|"$ROOT"|"$ROOT"/*) die "MILK_MAN_STATE_DIR must be a dedicated path outside the source checkout" ;;
esac
case "$ROOT" in
	"$STATE"/*) die "MILK_MAN_STATE_DIR cannot contain the source checkout" ;;
esac

HEAD="$(git -C "$ROOT" rev-parse --verify HEAD)"
RUN_ID="$(date -u +%Y%m%dt%H%M%Sz)-${HEAD:0:12}-$$"
BRANCH="codex/milk-man-self-improve-$RUN_ID"
CONTROL="$STATE/control/$RUN_ID"
WORKTREE="$STATE/worktrees/$RUN_ID"
CONFIG="$STATE/config"
SESSIONS="$STATE/sessions"
TMP="$STATE/tmp"
HOME_DIR="$STATE/home"
VENV="$STATE/kernel-venv"
ARTIFACTS="$STATE/session-artifacts"
RUNTIME_TMP="$(mktemp -d /private/tmp/milk-man-runtime.XXXXXXXX)" || die "cannot create short runtime directory"
chmod 700 "$RUNTIME_TMP"
WORKTREE_CREATED=0

report_retained_worktree() {
	local code=$?
	if [[ "$WORKTREE_CREATED" -eq 1 ]]; then
		echo "Retained worktree: $WORKTREE"
	fi
	case "$RUNTIME_TMP" in
		/private/tmp/milk-man-runtime.*) rm -rf -- "$RUNTIME_TMP" ;;
	esac
	trap - EXIT
	exit "$code"
}
trap report_retained_worktree EXIT

mkdir -p "$CONTROL" "$CONFIG" "$SESSIONS" "$TMP" "$HOME_DIR" "$ARTIFACTS" "$STATE/worktrees"
chmod 700 "$STATE" "$CONTROL" "$CONFIG" "$SESSIONS" "$TMP" "$HOME_DIR" "$ARTIFACTS" "$STATE/worktrees"
install -m 600 "$ROOT/milk/self-improve-settings.json" "$CONFIG/settings.json"
printf '{"providers":{"milk-carton":{"baseUrl":"https://carton.milkinfrastructure.com/v1","api":"openai-completions","apiKey":"OPENAI_API_KEY","authHeader":true,"headers":{"x-milk-session-id":"milk-man-%s"},"models":[{"id":"zai-org/GLM-5.3-Flash","name":"GLM-5.3-Flash through Milk Carton","reasoning":true,"input":["text"],"contextWindow":131072,"maxTokens":16384}]}}}\n' "$RUN_ID" >"$CONFIG/models.json"
chmod 600 "$CONFIG/models.json"
printf '{}\n' >"$CONFIG/auth.json"
cp -R "$ROOT/packages/coding-agent/skills/refine" "$CONTROL/refine"

# Bootstrap trusted runtime code before the model-controlled process starts.
env -i \
	PATH="${PATH:-/usr/bin:/bin}" \
	HOME="$HOME_DIR" \
	TMPDIR="$RUNTIME_TMP" \
	PRIME_AGENT_KERNEL_VENV="$VENV" \
	DO_NOT_TRACK=1 \
	PI_SKIP_VERSION_CHECK=1 \
	"$ROOT/node_modules/.bin/tsx" "$ROOT/packages/coding-agent/src/core/kernel/bootstrap-cli.ts"
KERNEL_PYTHON="$VENV/bin/python"

git -C "$ROOT" worktree add -b "$BRANCH" "$WORKTREE" "$HEAD"
WORKTREE_CREATED=1
[[ "$(git -C "$WORKTREE" rev-parse HEAD)" == "$HEAD" ]] || die "worktree HEAD changed"
[[ "$(git -C "$WORKTREE" branch --show-current)" == "$BRANCH" ]] || die "worktree branch changed"
cp -cR "$ROOT/node_modules" "$WORKTREE/node_modules"
[[ -L "$WORKTREE/node_modules/.bin/srt" ]] || die "node_modules clone did not preserve relative symlinks"
[[ "$(readlink "$WORKTREE/node_modules/.bin/srt")" == "$(readlink "$ROOT/node_modules/.bin/srt")" ]] ||
	die "node_modules clone changed the srt symlink"

SRT_SETTINGS="$CONTROL/srt.json"
PYTHON_ROOT="$("$KERNEL_PYTHON" -c 'import os, sys; print(os.path.dirname(os.path.dirname(os.path.realpath(sys.executable))))')"
node - "$SRT_SETTINGS" "$HOST_HOME" "$ROOT" "$WORKTREE" "$STATE" "$CONTROL" "$VENV" "$PYTHON_ROOT" "$RUNTIME_TMP" <<'NODE'
const fs = require("node:fs");
const path = require("node:path");
const [out, home, root, worktree, state, control, venv, pythonRoot, runtimeTmp] = process.argv.slice(2);
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
			runtimeTmp,
		],
		allowWrite: [
			worktree,
			path.join(state, "tmp"),
			runtimeTmp,
			path.join(state, "config", "daemon-workers", "**", "*.orphans.jsonl"),
			path.join(state, "session-artifacts", "**", "kernel-state.dill"),
			path.join(state, "session-artifacts", "**", "kernel-state.dill.*.tmp"),
			path.join(state, "session-artifacts", "**", "kernel-state.json"),
			path.join(state, "session-artifacts", "**", "kernel-state.json.*.tmp"),
		],
		denyWrite: [
			path.join(worktree, ".git"),
			path.join(worktree, "node_modules"),
			path.join(runtimeTmp, "check"),
			control,
			venv,
		],
	},
	allowAppleEvents: false,
};
fs.writeFileSync(out, `${JSON.stringify(config, null, 2)}\n`, { mode: 0o600 });
NODE

# The autonomous runner treats the gate as a shell command, so keep its path
# short and space-free. SRT denies the model write access to this exact file.
GATE="$RUNTIME_TMP/check"
printf '#!/usr/bin/env bash\ncd %q\nif [[ -z "$(git status --porcelain --untracked-files=all)" ]]; then\n\techo "self-improve gate: disposable checkout is unchanged" >&2\n\texit 1\nfi\nexec env -i PATH=%q HOME=%q TMPDIR=%q CLAUDE_CODE_TMPDIR=%q NO_COLOR=1 %q --settings %q sh -eu -c %q\n' \
	"$WORKTREE" "${PATH:-/usr/bin:/bin}" "$HOME_DIR" "$TMP" "$TMP" "$ROOT/node_modules/.bin/srt" "$SRT_SETTINGS" \
	'node_modules/.bin/biome check --error-on-warnings . && node_modules/.bin/tsgo --noEmit && node scripts/check-installer-render.mjs && node scripts/check-browser-smoke.mjs && bash -n milk/self-improve.sh milk/codex-context.sh milk/jobs.sh' >"$GATE"
chmod 700 "$GATE"

echo "Retained worktree: $WORKTREE"
echo "Retained branch: $BRANCH"
echo "Persistent state: $STATE"

set +e
env -i \
	PATH="${PATH:-/usr/bin:/bin}" \
	LANG="${LANG:-C}" \
	HOME="$HOME_DIR" \
	TMPDIR="$RUNTIME_TMP" \
	CLAUDE_CODE_TMPDIR="$RUNTIME_TMP" \
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
	--print \
	--session-dir "$SESSIONS" \
	--model milk-carton/zai-org/GLM-5.3-Flash \
	--thinking high \
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
	--autonomous-max-turns 12 \
	--autonomous-max-tokens 20000 \
	--autonomous-timeout-ms 900000 \
	--append-system-prompt "Improve code in this Milk Man repository; do not execute production Milk jobs. The only edit root is the current working directory, which is the disposable checkout. Start by reading os.getcwd(), then read and write task files directly below it with repository-relative paths. Do not create task files with tempfile or use an unset shell variable as a path. Do not use git, edit node_modules, push, deploy, call Baseten, access object storage, or publish routes. After validation, persist at most one reusable lesson with await refine.run('focused lesson', global_=True); otherwise do not refine." \
	-- "$1"
STATUS=$?
set -e

if [[ "$STATUS" -eq 0 && -z "$(git -C "$WORKTREE" status --porcelain --untracked-files=all)" ]]; then
	echo "self-improve: agent completed without changing the disposable checkout" >&2
	STATUS=1
fi

exit "$STATUS"
