# Milk Man

Milk Man is Milk's local agent harness and one-shot jobs runtime. It edits code
under supervision, reads the same object memory used by production, and runs
fixed data, inference, training, evaluation, and provider jobs.

It has no daemon, database, queue, local GPU requirement, or credential store.
Configuration and credentials enter through environment variables. An idle job
does not call an inference or GPU provider.

## Run locally

Requirements: Bash, Python 3, Git, and `curl`. Docker is not required.

Start the local dashboard:

```bash
bin/man dashboard
```

It binds only `127.0.0.1`, reads Milk Man's current trajectory, memory, and
workspace state, and reads `status/current.json` through the configured object
store. It does not invoke a job or provider.

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
