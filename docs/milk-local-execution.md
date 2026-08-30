# Local Milk Man execution

Milk Man uses Prime Agent's source runner directly. There is no separate Milk
daemon, queue, scheduler service, or agent framework.

## Build

```sh
npm ci
npm run check
```

Node 22.8 or newer and Python 3.11 or newer are required.

## Self-improvement

Start from a clean source checkout on macOS. Supply an operator-issued Milk
Carton key and a dedicated state directory outside the repository:

```sh
export OPENAI_API_KEY=milk_live_...
export MILK_MAN_STATE_DIR=/absolute/private/milk-man-state
mkdir -p "$MILK_MAN_STATE_DIR"
./milk/self-improve.sh \
  "Treat empty piped stdin as absent and add the focused regression test."
```

The launcher retains a disposable `codex/milk-man-self-improve-*` worktree
branch at the source checkout's exact `HEAD` and APFS-clones its installed
`node_modules`, preserving relative symlinks. It
keeps durable state at `MILK_MAN_STATE_DIR` but places Unix sockets in an
owner-only short-lived `/private/tmp` directory so long state paths work on
macOS. It
calls `zai-org/GLM-5.3-Flash` through
`https://carton.milkinfrastructure.com/v1`, assigns a unique Milk session ID,
loads only the checked-in refinement skill,
disables recursive agents, limits the run to four turns, and requires the fixed
repository gate. Commit, push, merge, and production actions remain
operator work.

To seed a run from a bounded part of a local Codex task, install
[`txcript`](https://github.com/skillsynchq/txcript), select an explicit message
range, and pipe the sanitized projection into the same launcher:

```sh
./milk/codex-context.sh \
  01234567-89ab-cdef-0123-456789abcdef#120-160 |
  ./milk/self-improve.sh "Continue the Milk implementation from this reviewed context."
```

The adapter requires a closed range (`N` or `N-M`) and keeps only user and
assistant text. It drops reasoning, tool calls, tool results, images, artifacts,
usage, and harness metadata. It isolates txcript from unrelated local harness
stores before resolving the exact Codex rollout, refuses an
unbounded session, and caps output at 128 KiB by default. Review the selected
range: text written directly by a user or assistant can still contain sensitive
material. `txcript` remains an optional local CLI, not a Milk runtime
dependency.

`MILK_MAN_STATE_DIR` persists sessions and the continual harness. Supplemental
prompt notes are mutable policy, memories hold durable facts, skills hold
reusable procedures, and subagent entries hold delegation patterns. Executable
tools remain reviewed source changes; a run may propose them but should not
activate new code before review.

The Carton client remains outside the sandbox so it can call the model. The
model-controlled Python kernel and every process it starts run under SRT with no
network and no API key. The kernel can write only the disposable worktree,
temporary files, and its namespace snapshots. Harness configuration, session
transcripts, runtime control files, the Python environment, `.git`, and
`node_modules` remain host-owned. Global refinement is a filtered host request,
so the kernel never needs direct write access to harness state. The real
checkout and the rest of the user's home directory are unreadable. The fixed
repository gate runs in a separate key-free SRT process. This materially limits
the run but is not a virtual machine; use reviewed tasks and inspect the retained
worktree.

## Deterministic Milk jobs

The separate checked-in `milk-jobs` skill exposes
`await milk_jobs.reconcile()` for one finite reconciliation pass. It accepts no
arguments. `MILK_HARNESS_ROOT` pins the checkpointed implementation and
`MILK_RUN_ONCE_CONFIG` pins the reviewed configuration. A schedule may re-enter
that fixed call; scheduling does not expand its permissions.

The same job runs directly from bash; credentials remain envvars:

```sh
export MILK_HARNESS_ROOT=/absolute/path/to/milk-harness
export MILK_HARNESS_REVISION=<exact-40-character-commit>
export MILK_RUN_PROFILE=production
export MILK_RUN_ONCE_CONFIG="$MILK_HARNESS_ROOT/deploy/run-once.production.json"
export MILK_CONTROL_R2_ACCOUNT_ID=<cloudflare-account-id>
export MILK_CONTROL_R2_BUCKET=<bucket>
export MILK_CONTROL_R2_ACCESS_KEY_ID=<access-key-id>
export MILK_CONTROL_R2_SECRET_ACCESS_KEY=<secret-access-key>
export BASETEN_API_KEY=<baseten-key>
export MILK_GATEWAY_API_KEY=<operator-issued-milk-key>
export MILK_MAN_PYTHON=/absolute/path/to/python3.13
./milk/jobs.sh
```

Durable job inputs and outputs belong in local or qualified S3-compatible
object storage. AWS S3, Cloudflare R2, and MinIO are admitted only after the
backend passes the object contract. Secrets and signing keys stay outside
object storage.

## Result

A successful self-improvement run yields a retained disposable worktree branch
with an uncommitted diff and a passing repository gate. Its path and branch are
printed before the run. A successful Milk job yields bounded object-store
artifacts. Neither result proves a deployment; production routing remains a
separate operator action.
