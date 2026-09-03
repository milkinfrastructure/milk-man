# Milk Man

Milk Man is a local program that can work on Milk's code and run one Milk job
at a time. It reads the same object storage used by production and can collect
statistics, create evaluation data, train a small model, compare versions, and
prepare a release for a person to approve.

It does not need Docker, a local GPU, a database, a queue, or a background
service. Settings and keys come from environment variables. When there is no
work, it does not call a model or rent a GPU.

## What we have run

We completed a fresh check of the whole system using 180 conversations sent
through Milk Parlor into Cloudflare R2:

- Milk Parlor saved both sides of each conversation in Cloudflare R2.
- Milk Man counted, classified, and summarized all 180 conversations.
- It created 100 evaluation cases and kept development, calibration, and final
  checks separate.
- It trained `Qwen/Qwen3.5-0.8B` for one step on a Baseten H100.
- It compared normal 16-bit, dynamic 8-bit, and static 8-bit versions on the
  same examples. Dynamic 8-bit won and passed a final held-back check.
- It served that model briefly on Modal. The live gateway proved signed
  candidate traffic, automatic fallback when Modal stopped, and a signed return
  to the baseline with the candidate key removed.
- Baseten finished every job and Modal returned to zero running containers.

This proves the parts connect and stop cleanly. The dataset was intentionally
tiny, so it does not prove that the trained model is useful yet.

## Run locally

Requirements: Bash, Python 3, Git, and `curl`. Docker is not required.

Start the local dashboard:

```bash
bin/man dashboard
```

It binds only `127.0.0.1`. The page shows the current Milk Man conversation,
tool output, saved memory, workspace changes, gateway health, object-store
progress, and every step from captured traffic to a route proposal. It refreshes
local activity every second and says whether Milk Man is working, ready with a
saved session, or needs setup. The job setup panel explains each fixed job,
when it starts, what it reads and writes, and which environment names this
process has. It never displays their values. Safe IDs, fixed commands, and
environment names copy on click. The nine-stop Milk line can be dragged or
used with arrow keys to inspect any stored stage and its trigger.

![Milk Man dashboard](docs/dashboard.png)

The prompt box starts or resumes the exact recorded workspace set with the
provider environment inherited by the dashboard. One follow-up may wait for the
active turn; a second is rejected. It never exposes environment values or
grants push, deploy, signing, or merge authority.

`MILK_PARLOR_BASE_URL` enables its public gateway-health light.
`MILK_SUMMARY_THRESHOLDS` drives the data progress marks and checkpoint
statistics; the same object-store environment used by jobs supplies the data.

Start one supervised development task:

```bash
export OPENAI_API_KEY=...

bin/man develop \
  --workspace milk-man="$PWD" \
  --workspace milk-parlor=/absolute/path/milk-parlor \
  -- "inspect both repositories and make one bounded correction"
```

The direct OpenAI driver defaults to `gpt-5.6-sol` with maximum reasoning.
`LLM_API_URL`, `LLM_MODEL`, and optional `LLM_API_KEY` select any other
OpenAI-compatible driver. `--resume` continues the current trajectory for the
exact workspace set. Milk Man may edit and commit locally; push, deployment,
and route signing remain operator actions.

## Run jobs

Every command prints one `milk.job-result.v2` JSON object.

```bash
export MILK_SCOPE_ID=11111111-1111-4111-8111-111111111111
export MILK_STORE_KIND=local
export MILK_STORE_ROOT="$PWD/.milk-objects"

bin/milk status
bin/milk run summary
bin/milk operate --once
```

For S3-compatible storage, set:

```text
MILK_STORE_KIND=s3
MILK_STORE_ENDPOINT
MILK_STORE_REGION
MILK_STORE_BUCKET
MILK_STORE_ACCESS_KEY_ID
MILK_STORE_SECRET_ACCESS_KEY
```

`MILK_STORE_SESSION_TOKEN` and `MILK_STORE_PATH_STYLE` are optional. Inference,
Baseten, and Modal jobs use the environment names declared in
[`config/jobs.json`](config/jobs.json). Provider jobs are separate; failure in
one never calls another.

Durable objects live under `milk/v2/scopes/<scope_uuid>/`. Captured exchanges
use `c/`; summaries `s/`; labels `l/`; readiness `readiness/`; evals `e/`;
datasets `d/`; models `m/`; evaluations `v/`; and unsigned route proposals
`p/`. Content is immutable. Small conditional `current.json` objects select the
active revision.

The fine-tune base is the exact `Qwen/Qwen3.5-0.8B` revision in
[`config/student.json`](config/student.json). Model weights remain outside OCI
images. Milk Man can propose a route, but only an operator can sign one; Milk
Parlor verifies and serves it.

## License

Milk-owned code is Apache-2.0. The reduced Headlong derivative under
`vendor/headlong` retains its upstream license and modification notice. Model
weights are not included and retain their own licenses.
