# Local Milk Man execution

Milk Man uses Prime Agent's source runner, goals, and schedules directly. There
is no separate Milk daemon, queue, scheduler service, or wrapper service.

## Build

```sh
npm ci
npm run check
```

Node 22.8 or newer and Python 3.11 or newer are required. Run from source with
`./prime-agent.sh`.

## Isolated configuration

Create a temporary owner-only configuration directory outside the target
repository. Copy `milk/models.example.json` to `models.json` there only when a
model-backed run is required. Supply `BASETEN_API_KEY` through the process
environment; never place its value in the task document, command line, or
repository.

Use `DO_NOT_TRACK=1`, `PI_SKIP_VERSION_CHECK=1`, and a task-specific session
directory. Load only the checked-in Milk skill:

```sh
DO_NOT_TRACK=1 \
PI_SKIP_VERSION_CHECK=1 \
PRIME_AGENT_CODING_AGENT_DIR=/absolute/private/config \
./prime-agent.sh \
  --cwd /absolute/disposable/worktree \
  --session-dir /absolute/private/sessions \
  --no-extensions \
  --no-skills \
  --skill /absolute/milk-man/.prime/agent/skills/milk-system/SKILL.md \
  --no-prompt-templates \
  --no-themes \
  --model milk-teacher/zai-org/GLM-5.3-Flash \
  --thinking low \
  --autonomous \
  --autonomous-gate "npm run check" \
  --autonomous-max-continuations 2 \
  --autonomous-max-turns 4 \
  --autonomous-max-tokens 20000 \
  --autonomous-timeout-ms 900000 \
  @/absolute/reviewed-task.json
```

The gate shown is only for a Milk Man worktree. Use the exact fixed command
listed by the Milk skill for a Milk Carton task. The operator chooses the
command from the admitted gate ID; the model does not construct it.

## Deterministic jobs

The checked-in `milk-jobs` skill exposes `await milk_jobs.reconcile()` for one
finite reconciliation pass. It accepts no arguments. `MILK_HARNESS_ROOT` pins
the checkpointed implementation and `MILK_RUN_ONCE_CONFIG` pins the reviewed
configuration. The model cannot supply a shell command, path, configuration,
budget, credential, scope, or write target.

During migration, that call executes the checkpointed
`python -m milk_harness run-once` implementation. This is an implementation
bridge, not a third Milk product or service. A Prime Agent schedule may re-enter
the reviewed task and invoke the same call; scheduling does not expand its
permissions.

Durable inputs and outputs belong in local or qualified S3-compatible object
storage. AWS S3, Cloudflare R2, and MinIO are admitted only after the backend
passes the object contract. Session state and scratch files are local and
disposable. Secrets and signing keys stay outside object storage.

Prime Agent runs generated code with the user's permissions and is not a
security sandbox. Use a disposable trusted worktree. A production-grade broker
may later place that same command in a network-denied VM, but that is not a
reason to build another framework now.

## Result

A successful coding run yields a diff and passing gate. A successful job call
yields a bounded result backed by object-store artifacts. Neither result proves
a deployment. Commit, push, cloud deploy, provider calls, remote object writes,
route preparation, signing, and publication require their own admitted
permissions.
