# Milk Man

Milk Man is Milk's local-first agent harness and deterministic jobs runtime.
It has two entrypoints:

- `bin/man` runs a supervised development session against one or more local
  repositories using any OpenAI-compatible inference endpoint.
- `bin/milk` reads and writes Milk's object memory and executes fixed jobs once.

There is no daemon, internal scheduler, database, queue, local GPU requirement,
or provider framework. An external scheduler may invoke `bin/milk operate
--once`; an idle run exits without inference or provider calls.

The paired gateway is
[`milkinfrastructure/milk-parlor`](https://github.com/milkinfrastructure/milk-parlor).
The complete implementation contract and evidence ledger is
[`goal_tracker.md`](goal_tracker.md).

## Development harness

Requirements: Bash, Python 3, Git, and `curl`. Docker is not required.

```bash
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-5.6-sol

bin/man develop \
  --workspace milk-man="$PWD" \
  --workspace milk-parlor=/absolute/path/milk-parlor \
  -- "inspect both repositories and make one bounded correction"
```

Use `--resume` to continue the latest trajectory for the exact workspace set,
or `--traj <uuid>` to select one explicitly. State defaults to
`$HOME/.local/state/milk-man` and can be moved with `MILK_MAN_STATE_DIR`.

Provider selection is environment-only, in this order:

1. `LLM_API_URL`, `LLM_MODEL`, optional `LLM_API_KEY`
2. `MILK_CONTROLLER_BASE_URL`, `MILK_CONTROLLER_MODEL`, optional
   `MILK_CONTROLLER_API_KEY`
3. `MILK_BOOTSTRAP_BASE_URL`, `MILK_BOOTSTRAP_MODEL`, optional
   `MILK_BOOTSTRAP_API_KEY`
4. `OPENAI_API_KEY`, optional `OPENAI_BASE_URL` and `OPENAI_MODEL`

That order applies to `develop`. `bootstrap` does not call a bootstrap model.
It appends the task to one trajectory, invokes and records the fixed
`inference-status` and `inference-ensure` jobs itself, and starts Headlong only
after validating and warming the resulting controller binding. With the
default `MILK_MODAL_CONTROLLER_APPLY=0`, it records the dry-run plan and exits
without an inference call or provider mutation.

Milk Man loads `goal_tracker.md`, the two checked-in Milk skills, bounded memory,
and the exact trajectory. It may edit and commit locally. Push, deployment, and
route signing remain operator actions.

## Deterministic jobs

Every invocation prints one `milk.job-result.v2` JSON object to stdout.

```bash
export MILK_SCOPE_ID=11111111-1111-4111-8111-111111111111
export MILK_STORE_KIND=local
export MILK_STORE_ROOT="$PWD/.milk-objects"

bin/milk status
bin/milk operate --once
bin/milk run summary
```

For S3-compatible storage set `MILK_STORE_KIND=s3` and provide:

```text
MILK_STORE_ENDPOINT
MILK_STORE_REGION
MILK_STORE_BUCKET
MILK_STORE_ACCESS_KEY_ID
MILK_STORE_SECRET_ACCESS_KEY
```

`MILK_STORE_SESSION_TOKEN` and `MILK_STORE_PATH_STYLE` are optional. Inference
and GPU providers use the reviewed environment-variable names in
[`config/jobs.json`](config/jobs.json); configuration cannot supply executable
paths.

Candidate serving is exposed as separate `route-propose-baseten` and
`route-propose-modal` jobs. `operate --once` stops after evaluation with
`next: select-route-provider`. Status reports each job's availability and missing
environment names; Milk Man selects exactly one from its system prompt and
operator task, or the operator invokes one directly. A provider error never
invokes the other provider.

Training reads the immutable dataset manifest before provider discovery. New
GPU work starts only when train, DEV, calibration, and sealed counts are all
nonzero. Otherwise the job returns to summary with zero provider calls.
The mechanics profile therefore defaults to four representative eval cases:
two DEV, one calibration, and one sealed.

The only fine-tune base is the exact `Qwen/Qwen3.5-0.8B` revision pinned in
[`config/student.json`](config/student.json). It is an artifact input, not an
inference fallback. Summary, eval generation, validation, and teacher-data
generation each require their own OpenAI-compatible environment binding; none
inherits or falls back to the student base.

OpenAI may supply any or all teacher roles by pointing each role's reviewed
`BASE_URL`, `MODEL`, and `API_KEY` variables at the same OpenAI account. The
bindings remain separate so changing one job never silently changes another.
Set `MILK_REASONING_EFFORT` when the selected endpoint supports it; the value is
included in every semantic job identity.
Set the role-specific `MILK_SUMMARY_API_MODE`, `MILK_EVAL_API_MODE`,
`MILK_VALIDATOR_API_MODE`, or `MILK_TEACHER_API_MODE` to `responses` for an
OpenAI Responses endpoint; each defaults to `chat_completions`.

Mechanics compares BF16, dynamic FP8, and static FP8 on the same DEV cases.
Production runs and admits only BF16 and stable dynamic FP8 while static
activation FP8 remains a TorchAO prototype. The
selected branch is carried unchanged through sealed evaluation, candidate
identity, provider environment, health, and route proposal.

The object root for one authenticated scope is:

```text
milk/v2/scopes/<scope_uuid>/
```

Traffic is `c/`, summary checkpoints are `s/`, classifier metadata is `l/`,
readiness is `readiness/`, evals are `e/`, datasets are `d/`, model artifacts
are `m/`, evaluations are `v/`, and unsigned proposals are `p/`. Immutable
objects hold content; small conditional `current.json` pointers select the
active revision.

Route proposals list the native protocols a candidate actually implements and
bind each protocol to its provider base URL and artifact digest. The current
student server implements Chat Completions, so its proposal never diverts a
Responses request; Parlor sends Responses directly to its separately configured
native baseline. Parlor's pre-byte candidate-to-baseline behavior is request
routing safety and is independent of Milk Man's provider-job selection.

## License

Milk-owned code is Apache-2.0. The reduced Headlong derivative under
`vendor/headlong` retains its upstream license and modification notice. Model
weights are not included and keep their own licenses.
