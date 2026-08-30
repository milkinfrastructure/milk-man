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

Start from a clean source checkout on macOS. Supply a project-scoped OpenAI key
and a dedicated state directory outside the repository:

```sh
export OPENAI_API_KEY=...
export MILK_MAN_STATE_DIR=/absolute/private/milk-man-state
./milk/self-improve.sh \
  "Treat empty piped stdin as absent and add the focused regression test."
```

The launcher retains a detached worktree at the source checkout's exact `HEAD`
and APFS-clones its installed `node_modules`, preserving relative symlinks. It
selects `openai/gpt-5.6-luna`, loads only the checked-in refinement skill,
disables recursive agents, limits the run to four turns, and requires the fixed
`npm run check` gate. Commit, push, merge, and production actions remain
operator work.

`MILK_MAN_STATE_DIR` persists sessions and the continual harness. Supplemental
prompt notes are mutable policy, memories hold durable facts, skills hold
reusable procedures, and subagent entries hold delegation patterns. Executable
tools remain reviewed source changes; a run may propose them but should not
activate new code before review.

The OpenAI client remains outside the sandbox so it can call the model. The
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

Durable job inputs and outputs belong in local or qualified S3-compatible
object storage. AWS S3, Cloudflare R2, and MinIO are admitted only after the
backend passes the object contract. Secrets and signing keys stay outside
object storage.

## Result

A successful self-improvement run yields a retained detached worktree with an
uncommitted diff and a passing repository gate. Its path is printed before and
after the run. A successful Milk job yields bounded object-store artifacts.
Neither result proves a deployment; production routing remains a separate
operator action.
