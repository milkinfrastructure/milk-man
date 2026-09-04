# Milk Man

[Read the Milk documentation](https://milkinfrastructure.com/docs/) first.

Milk has two programs:

- [Milk Parlor](https://github.com/milkinfrastructure/milk-parlor) is the small
  Rust gateway between an application and its model provider. It authenticates,
  routes, streams, and saves eligible request and returned-response bodies after
  each exchange ends.
- Milk Man is a local Bash agent. Give it an objective and it can use its saved
  trajectory, configured model, registered jobs, and repository scripts to do
  the work. The Parlor traffic-to-model loop is its first application.

Milk Man is local-first. It needs no Docker, local GPU, database, queue, or
separate scheduler service. One lightweight local heartbeat owns an active
task, waits without model calls, and resumes it when work changes or becomes
due. The task and configured environment define what Milk Man may operate.

## Quickstart

Requirements: Bash, Python 3, Git, and `curl`. Install the `zstd` executable
before processing capture objects. Modal operations also require the Modal CLI;
Baseten candidate serving requires `uvx`. Docker is not required.

```bash
git clone https://github.com/milkinfrastructure/milk-man.git
cd milk-man
export OPENAI_API_KEY=...
bin/man run --workspace milk-man="$PWD" -- \
  "Inspect this repository and report the next unfinished goal."
```

`run` creates one saved trajectory and keeps its heartbeat in the foreground.
In another terminal, start the optional local view:

```bash
bin/man dashboard
```

Open <http://127.0.0.1:8765>. `MILK_DASHBOARD_PORT` changes the port,
`MILK_DASHBOARD_REFRESH_SECONDS` changes the 30-second remote-status interval,
and `MILK_PARLOR_BASE_URL` enables the gateway health check. Restart the
dashboard after changing its environment.

The dashboard reads the saved trajectory and heartbeat, sends instructions,
and shows messages, workspace changes, configured environment names, gateway
health, and object-store progress. It never displays environment values.
Closing the page is not a stop command; current heartbeat proof status is in
[`goal_tracker.md`](goal_tracker.md). On a fresh install, start the first task
from Bash as shown above so the dashboard has a trajectory to resume.

## Dashboard

Connect an app and see whether Milk Man, Milk Parlor, and object memory are
reachable.

![Milk Man connection and status](docs/dashboard-overview.png)

Give Milk Man one task and follow its response and work details.

![Milk Man conversation](docs/dashboard-conversation.png)

See the current step from captured traffic to a candidate route.

![Milk processing loop](docs/dashboard-loop.png)

Open a checkpoint to see what the captured conversations contain.

![Milk summary checkpoint](docs/dashboard-summary.png)

## Continue or control a task

Restart the same heartbeat with the exact same workspace set:

```bash
bin/man run --resume --workspace milk-man="$PWD"
```

Inspect or control the current heartbeat:

```bash
bin/man heartbeat status
bin/man heartbeat pause
bin/man heartbeat resume
bin/man heartbeat stop
```

`MILK_HEARTBEAT_SECONDS` sets the first idle interval (30 seconds by default).
`MILK_HEARTBEAT_MAX_SECONDS` caps exponential idle backoff (300 seconds by
default). Idle checks do not call the model. A task may register a scheduled
wake or a read-only status command; changed status resumes the saved task.

For one direct turn without the persistent heartbeat:

```bash
bin/man develop \
  --workspace milk-man="$PWD" \
  --workspace milk-parlor=/absolute/path/milk-parlor \
  -- "inspect both repositories and report their current state"
```

This defaults to `gpt-5.6-sol`, the Responses API, and low reasoning.
The driver uses one native Bash function call per turn. For an endpoint without
function calling, explicitly set `MILK_MAN_TOOL_CALLS=0` to use fenced Bash.
`LLM_API_URL` plus `LLM_MODEL`, with optional `LLM_API_KEY`, selects another
OpenAI-compatible endpoint. `--resume` continues the latest trajectory for the
exact workspace set; `--traj UUID` selects one explicitly. Run `bin/man --help`
for the complete provider order and bootstrap command.

State defaults to `${XDG_STATE_HOME:-$HOME/.local/state}/milk-man`; set
`MILK_MAN_STATE_DIR` to an absolute dedicated directory to move it.

## Run jobs

Every `bin/milk` invocation emits one `milk.job-result.v2` JSON object to stdout.
Diagnostics go to stderr. Inspect the live catalog before choosing a job:

```bash
bin/milk jobs
```

`bin/milk jobs` returns every registered job, its supported actions, and the
required and optional environment names for starting a run. Status and stop
commands use saved resource settings. The catalog can include built-in jobs
and repository-owned executable jobs from [`config/jobs.json`](config/jobs.json).
Executable-job dispatch exists in the current development source but remains an
end-to-end proof item in [`goal_tracker.md`](goal_tracker.md).
An executable job receives `run`, `status`, or `stop`, inherits the current
environment plus `MILK_JOB_*` metadata, and returns one JSON result on stdout.

Start the built-in traffic loop with an empty local object store:

```bash
export MILK_SCOPE_ID=11111111-1111-4111-8111-111111111111
export MILK_STORE_KIND=local
export MILK_STORE_ROOT="$PWD/.milk-objects"

bin/milk status
bin/milk operate --once
bin/milk run summary
# For a catalog entry that advertises these actions:
bin/milk run <job> status
bin/milk run <job> stop
```

`status` reads the current run. `operate --once` advances
`summary`, `eval`, `dataset`, `train`, and `evaluate` while work is immediately
ready, then exits. It stops after evaluation at `select-route-provider`; it does
not choose, sign, or activate a route. An idle run makes zero inference and
provider calls.

Provider proposal jobs are explicit and separate. A credential being present
never starts a provider job, and failure in one provider does not select another.
Milk Man writes unsigned proposals only; the operator-controlled Milk Parlor
release path signs and publishes routes.

## Storage and job environment

Every store uses:

```text
MILK_SCOPE_ID
MILK_STORE_KIND=local|s3
```

`MILK_SCOPE_PROFILE=production|mechanics` and `MILK_STORE_TIMEOUT_SECONDS` are
optional. Local storage additionally requires an absolute `MILK_STORE_ROOT`.
S3-compatible object storage, such as Cloudflare R2 or Amazon S3, requires:

```text
MILK_STORE_ENDPOINT
MILK_STORE_REGION
MILK_STORE_BUCKET
MILK_STORE_ACCESS_KEY_ID
MILK_STORE_SECRET_ACCESS_KEY
```

`MILK_STORE_SESSION_TOKEN` and `MILK_STORE_PATH_STYLE` are optional. Cloudflare
R2 uses the S3 implementation with its account endpoint.

Inference, training, evaluation, and serving jobs use only their named settings
from [`config/jobs.json`](config/jobs.json). Some values are conditionally
required: `MILK_EVAL_IMAGE` is required when evaluation reaches Baseten, and
each Modal operation needs its Modal credentials and CLI. Settings and secrets
remain environment variables; never place their values in repository files.

Durable objects live under `milk/v2/scopes/<scope_uuid>/`. Versioned objects are
immutable; small conditional `current.json` pointers select active revisions.
The complete object tree and runtime contract are in [`PRD.md`](PRD.md).

## Capture traffic with Milk Parlor

Applications use the official OpenAI package, not a Milk SDK. With an
operator-issued Milk key, point the client at Parlor:

```bash
pip install openai # or: npm install openai
export OPENAI_BASE_URL=https://parlor.milkinfrastructure.com/v1
export OPENAI_API_KEY='your Milk key'
```

```python
from openai import OpenAI

milk = OpenAI()
answer = milk.responses.create(model="your-model", input="Hello")
print(answer.output_text)
```

Parlor supports Responses and Chat Completions create routes, including
streaming. It stores complete request and returned-response pairs in the object
store after the response path; Milk Man processes them later. This repository
does not issue gateway keys or deploy Parlor. Follow the
[Milk Parlor repository](https://github.com/milkinfrastructure/milk-parlor) for
gateway operation.

## What we tested

A small end-to-end run sent 180 conversations through Milk Parlor into
Cloudflare R2, summarized all 180, produced 100 model-test cases, and trained
`Qwen/Qwen3.5-0.8B` for one step on a Baseten H100. It compared one 16-bit and
two 8-bit versions, briefly served the selected version on Modal, sent signed
test traffic to it, returned safely to the default model when it stopped,
disabled the test route, and confirmed that no GPU remained running.

This proves that the components connect and stop cleanly. The intentionally tiny
dataset does not establish model usefulness or a production-qualified corpus.
The evidence record is maintained in
[`goal_tracker.md`](goal_tracker.md).

## Reference

- [Job and environment contract](config/jobs.json)
- [Evaluation policy](config/evaluation.json)
- [Pinned student model](config/student.json)
- [Product contract](PRD.md)
- [Current execution goal](GOAL.md)
- [Evidence and progress tracker](goal_tracker.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Third-party model notices](THIRD_PARTY_MODEL_NOTICES.md)
- [Headlong attribution](vendor/headlong/UPSTREAM.md)
- [Apache-2.0 license](LICENSE) and [notice](NOTICE)
