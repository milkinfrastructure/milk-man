# goal_tracker.md — Build Milk Parlor and a Minimal Milk Man

This file is the repository implementation and evidence tracker. It does not
replace, modify, shorten, or redefine the active Codex goal. Brackets record
only evidence-backed implementation progress.

## Goal

Replace the pre-release architecture with two focused public repositories:

- `milkinfrastructure/milk-parlor`: a tiny CPU-only Rust gateway deployed at `parlor.milkinfrastructure.com`.
- `milkinfrastructure/milk-man`: a local-first Bash agent harness plus deterministic Milk job runtime.

This is not a legacy migration or parity exercise. Freeze the old work once, define the final contracts, create clean repositories, and copy only functions that directly implement those contracts. Old prefixes, APIs, schedulers, quota code, fixtures, and control-plane behavior are not compatibility targets.

The completed system must prove:

```text
official OpenAI SDK
        |
        v
Milk Parlor -- baseline/candidate inference --> streamed response
        |
        +-- asynchronous exact request+response capture
                         |
                         v
              S3-compatible object memory
                         |
        external schedule or local shell
                         |
                         v
Milk Man: account -> summarize -> classify -> readiness -> evals
                         |
                         v
  strongest teacher -> data -> train/merge Qwen3.5-0.8B
                         |
                         v
    BF16 | dynamic FP8 | static FP8
                         |
                         v
        deterministic winner -> sealed evaluation
                         |
                         v
     unsigned proposal -> operator-signed route
                         |
                         v
      canary -> fallback -> rollback -> zero route
                         |
                         v
                 zero active GPU
```

A separate development loop must prove:

```text
OpenAI-compatible bootstrap
        |
        v
local Milk Man reads goal_tracker.md + skills + memory
        |
        v
Milk Man calls its inference-ensure tool
        |
        v
Modal starts GLM-4.5-Air-FP8 on one H200
        |
        v
same trajectory resumes using that GLM endpoint
        |
        v
Milk Man edits Milk Man or Milk Parlor
        |
        v
narrow check -> reviewable commit
```

## Verified starting point — 2026-09-01 snapshot

These are donor facts, not completion claims for the new system:

- [x] Current Milk Carton source was published at `18a84629431c45a995e2103934bb8d8b722f351d`; its deployed predecessor handled official SDK traffic, scoped authentication, asynchronous R2 capture, signed routing, fallback, and storage-failure survival.
- [x] Current Milk Man source was published at `57068bae5bf83ccc16aa31080118f0689af97d9f`; it runs locally from Bash and contains useful object-store, statistics, classification, eval, Modal, Baseten, training, and evaluation code.
- [x] Existing mechanics evidence proves local/S3-compatible storage, hosted summary/eval inference, one Modal cache operation, replay, and zero containers.
- [x] At this starting snapshot no final `milk-parlor` release, minimal Headlong-based `milk-man`, GLM controller handoff, production summary loop, trained winner, signed Parlor route, or complete two-provider proof existed. Current progress is recorded below.

Execution begins by re-verifying these revisions and preserving one local bundle. Do not spend a milestone reconciling the old 32 traces or reproducing old behavior.

## Non-negotiable architecture

### Repository and reuse boundary

- The final public repositories are only `milk-parlor` and `milk-man`.
- Preserve the current repositories, dirty Milk Man changes, local Milk Man state, and evidence references in checksum-verified Git bundles before replacing public contents.
- The old code is a parts inventory. It is not a release gate, behavioral oracle, compatibility requirement, or production fallback.
- Use a new `milk/v2` object prefix. New code never reads `milk/v1`.
- Remove Prime entirely. Do not port its TypeScript extension, packages, installer, identities, dashboards, bridges, broad tests, or release machinery.
- Start Milk Man from a pinned minimal subset of [Headlong](https://github.com/laude-institute/headlong): Bash model loop, OpenAI-compatible call, trajectories, context, memory, skills, and small file tools.
- Do not use Exo for this version; its Docker and multi-runtime surface does not help the local Bash-first path.
- Milk-owned source is Apache-2.0. Preserve Headlong’s license and modification notice. Keep model-weight licenses separate; never redistribute weights in Git or OCI.

### Runtime boundary

Milk Man has two entrypoints with one shared job implementation:

```text
bin/man   interactive development and controller bootstrap
bin/milk  deterministic direct jobs and production reconciliation
```

Development mode:

- Runs Headlong locally from Bash without Docker or a local GPU.
- Reads `goal_tracker.md`, `prompts/develop.md`, applicable skills, bounded memory, and the exact prior trajectory.
- Accepts multiple absolute workspaces so it can edit both repositories.
- Has ordinary shell access for development.
- May edit files, add Milk skills, run narrow checks, and retain a local commit.
- Does not receive route-signing material and does not silently push, merge, deploy, or activate routes.

Production mode:

- An external scheduler invokes `bin/milk operate --once`.
- It contains no sleeping loop, internal tick, resident manager, or background thinker.
- It lists object metadata, selects the next ready job deterministically, progresses all immediately ready work, then exits.
- When nothing changed, it makes zero inference and provider calls.
- Semantic jobs run a restricted Headlong session with a fixed job-specific system prompt and only `milk job read`, `milk job commit`, and `milk status` available.
- Production never reads development trajectories, coding memories, workspaces, or editing skills.
- After local proof, the same `operate --once` command may run as a scheduled scale-to-zero CPU Modal job. GitHub Actions never runs Milk jobs.

### Local state

Repository-owned:

```text
goal_tracker.md
config/jobs.json
prompts/develop.md
prompts/summary.md
prompts/eval.md
skills/milk-system/SKILL.md
skills/milk-jobs/SKILL.md
```

Machine-owned:

```text
${MILK_MAN_STATE_DIR:-$HOME/.local/state/milk-man}/
  controller/current.json
  trajectories/
  memories/
  workspaces/<workspace-set-digest>.json
  runs/<job-id>/
```

Rules:

- `goal_tracker.md` is loaded on every new or resumed development run.
- `prompts/develop.md` is the stable agent identity; do not invent a separate “soul” framework.
- Skills are indexed, then read fully only when applicable.
- Memory contains concise decisions and recovery notes, not raw Codex transcripts, prompts, secrets, or provider logs.
- A workspace record binds all workspace paths, HEADs, dirty-state digest, trajectory ID, controller binding, and last Milk job.
- `--resume` resolves the latest trajectory for the exact workspace set.
- Resume first inspects Git state and the last job receipt; it never blindly repeats commands.

## Public Milk Man interface

```bash
# Development
bin/man develop \
  --workspace milk-man=/absolute/path/milk-man \
  --workspace milk-parlor=/absolute/path/milk-parlor \
  -- "task"

bin/man develop --resume --workspace ... -- "continue"
bin/man develop --traj <trajectory-id> --workspace ... -- "continue"

# Bootstrap Milk Man onto its own Modal controller
bin/man bootstrap --workspace ... -- "create the controller and continue"

# Direct operation
bin/milk status
bin/milk operate --once
bin/milk run inference-ensure
bin/milk run inference-status
bin/milk run inference-stop
bin/milk run summary
bin/milk run eval
bin/milk run dataset
bin/milk run train
bin/milk run evaluate
bin/milk run route-propose
bin/milk run gpu-reconcile
```

Every `bin/milk` invocation emits one JSON object to stdout; diagnostics go to stderr:

```json
{
  "schema_version": "milk.job-result.v2",
  "job": "summary",
  "state": "idle|progressed|active|complete|blocked|failed",
  "identity": "<sha256>",
  "scope_id": "<uuid>",
  "artifacts": [{"key": "...", "sha256": "..."}],
  "inference_calls": 1,
  "provider_calls": 0,
  "next": "eval"
}
```

Exit codes:

- `0`: valid result, including idle or active.
- `64`: invalid CLI use.
- `65`: invalid configuration or stored object.
- `69`: definite provider rejection or unavailability.
- `70`: internal failure or ambiguous external operation requiring reconciliation.
- `75`: another process already owns the same deterministic job.

## Job and environment contract

Use one strict `config/jobs.json`. Do not recreate the Prime TypeScript registry or allow configuration to introduce executable paths.

Each job definition contains:

```json
{
  "handler": "summary",
  "trigger": {
    "kind": "crossed_capture_threshold",
    "values_env": "MILK_SUMMARY_THRESHOLDS"
  },
  "bindings": ["store", "summary"],
  "input_prefixes": ["c", "s"],
  "output_prefixes": ["j", "s", "readiness", "status"],
  "system_prompt": "prompts/summary.md",
  "timeout_env": "MILK_SUMMARY_TIMEOUT_SECONDS",
  "teardown_handler": null
}
```

The runtime must:

1. Validate `handler` against a hardcoded enum.
2. Resolve only the selected job’s bindings.
3. Validate every configured environment-variable name.
4. Start the fixed handler under a cleaned environment with only safe process variables and the selected binding variables.
5. Never log credential values.
6. Reject shell fragments, command paths, prefixes, provider names, model revisions, images, GPU types, or credential names supplied as model arguments.

Storage variables:

```text
MILK_SCOPE_ID
MILK_SCOPE_PROFILE=production|mechanics
MILK_STORE_KIND=local|s3
MILK_STORE_ROOT
MILK_STORE_ENDPOINT
MILK_STORE_REGION
MILK_STORE_BUCKET
MILK_STORE_ACCESS_KEY_ID
MILK_STORE_SECRET_ACCESS_KEY
MILK_STORE_SESSION_TOKEN
```

R2 uses the `s3` implementation with its endpoint. An empty session token is omitted.

Inference roles are independent OpenAI-compatible bindings:

```text
MILK_BOOTSTRAP_BASE_URL / MODEL / API_KEY
MILK_CONTROLLER_BASE_URL / MODEL / API_KEY
MILK_SUMMARY_BASE_URL / MODEL / API_KEY
MILK_EVAL_BASE_URL / MODEL / API_KEY
MILK_VALIDATOR_BASE_URL / MODEL / API_KEY
MILK_TEACHER_BASE_URL / MODEL / API_KEY
```

GPU variables remain explicit:

```text
MODAL_TOKEN_ID
MODAL_TOKEN_SECRET
MODAL_ENVIRONMENT

BASETEN_API_KEY
BASETEN_TEAM_NAME
BASETEN_TRAINING_PROJECT_ID
BASETEN_TRAINING_ACCELERATOR
BASETEN_TRAINING_REGISTRY_SECRET
MILK_BASETEN_RUNTIME_SECRET_MAP_JSON
```

Configuration records environment-variable names, never secret values. The same code must work locally, against R2, and against remote inference/GPU providers by changing bindings only.

Job-scoped environments reduce accidental credential propagation; they are not presented as cryptographic isolation from a same-user development shell. Do not build a secret broker for the first version.

## Milk Parlor contract

### Public endpoints

```text
POST /v1/chat/completions
POST /v1/responses
ANY  /v1/*                 raw HTTP passthrough where supported
GET  /healthz
GET  /
GET  /status
GET  /api/status
```

Initial acceptance covers Chat Completions and Responses, including SSE. WebSocket/Realtime is not claimed until a dedicated duplex adapter and direct smoke exist.

### Authentication

```text
MILK_KEYS_JSON
```

maps SHA-256 key digests to:

```json
{
  "scope_id": "<uuid>",
  "profile": "production|mechanics"
}
```

Parlor:

- hashes the bearer token and compares digests in constant time;
- maps one operator-issued key to one scope;
- never logs or stores the bearer token;
- uses the same key for `/api/status`;
- has no user database or key-rotation service.

Upstream and candidate definitions are environment bindings:

```text
MILK_ROUTE_BINDINGS_JSON
MILK_BASELINE_API_KEY
MILK_CANDIDATE_API_KEY
MILK_ROUTE_VERIFY_KEY
```

The binding JSON contains base URLs, public model aliases, and API-key environment-variable names—not secret values.

### Proxy behavior

Milk Parlor:

- forwards request method, path, query, body, and relevant headers without rewriting model semantics;
- changes only upstream authority, Host, authentication, and the selected route;
- streams upstream bytes to the client;
- does not parse conversations, classify traffic, infer sessions, count thresholds, generate summaries, or run jobs;
- keeps all object-store compression and writes off the response path.

Start with one named Cloudflare container. Do not build autoscaling or a pool until observed warm saturation justifies it.

### Exact two-sided capture

One complete HTTP exchange becomes one traffic object:

```text
milk/v2/scopes/<scope_uuid>/c/<exchange_uuidv7>.json.zst
```

The canonical JSON envelope contains:

```json
{
  "schema_version": "milk.exchange.v2",
  "scope_id": "<uuid>",
  "profile": "production|mechanics",
  "exchange_id": "<uuidv7>",
  "started_at": "<UTC>",
  "completed_at": "<UTC>",
  "endpoint": "chat_completions|responses|other",
  "streaming": true,
  "request": {
    "method": "POST",
    "path": "/v1/responses",
    "headers": {"content-type": "application/json"},
    "body_base64": "<exact received body bytes>",
    "byte_len": 123,
    "sha256": "<sha256>"
  },
  "response": {
    "status": 200,
    "headers": {"content-type": "text/event-stream"},
    "body_base64": "<exact bytes returned to the client>",
    "byte_len": 456,
    "sha256": "<sha256>"
  },
  "route": {
    "route_id": null,
    "target": "baseline",
    "fallback_reason": null
  },
  "timing": {
    "ttft_ms": 81,
    "total_ms": 902
  },
  "complete": true
}
```

Capture rules:

- Capture mode is initially all complete authenticated exchanges. There is no semantic selection, HMAC sampling, product rate limit, or commercial allowance in Parlor.
- Request and returned-response bodies are byte-exact. SSE is stored as the exact event-stream bytes delivered.
- Only safe reconstructive headers are retained. Authorization, cookies, proxy credentials, and arbitrary query values are excluded.
- Non-2xx upstream responses count if their returned body completed.
- Client disconnects, capture-memory overflow, queue rejection, and storage failure create no authoritative `c/` object.
- The request still succeeds when capture fails.
- Operational memory bounds remain configurable so an oversized response cannot exhaust the gateway; this is a fail-open process safeguard, not traffic rationing.
- Counters record observed, completed, enqueued, persisted, dropped, oversized, interrupted, and storage-failed exchanges.
- Compression uses Zstandard level 3 in the background.
- The request path performs only a bounded copy/tee and nonblocking queue operation; it never awaits R2.

Reuse from current Carton only:

- constant-time scoped authentication;
- request forwarding and streaming;
- hop-by-hop header removal;
- bounded nonblocking capture;
- zstd JSON envelope;
- local/S3-compatible storage;
- Ed25519 route verification;
- pre-byte fallback.

Do not copy:

- traffic sampling and eligibility;
- hourly stats;
- `tick`;
- summaries/readiness;
- provider, teacher, student, lease, allowance, or materialization code;
- hidden operator commands;
- hot key rotation;
- outcome/tombstone APIs;
- old schemas, fixtures, or proof frameworks.

## Object-store memory

All backends implement:

```text
get(key)
paginated lexicographic list(prefix)
put-create-only(key, bytes)
replace-if-match(key, prior-etag, bytes)
```

Root:

```text
milk/v2/scopes/<scope_uuid>/
```

Tree:

```text
c/<exchange_uuid>.json.zst

l/<classifier_config_digest>/<exchange_content_digest>.json

s/<summary_uuid>/source.json.zst
s/<summary_uuid>/summary.json
s/current.json

readiness/<readiness_uuid>.json
readiness/current.json

e/<eval_uuid>/source.json.zst
e/<eval_uuid>/eval.jsonl.zst
e/<eval_uuid>/validation.json
e/current.json

d/<dataset_uuid>/manifest.json
d/<dataset_uuid>/train.jsonl.zst
d/<dataset_uuid>/dev.jsonl.zst
d/<dataset_uuid>/calibration.jsonl.zst
d/<dataset_uuid>/sealed.jsonl.zst

t/<training_uuid>/manifest.json
t/<training_uuid>/result.json

m/<model_uuid>/manifest.json

v/<evaluation_uuid>/bf16.json
v/<evaluation_uuid>/dynamic-fp8.json
v/<evaluation_uuid>/static-fp8.json
v/<evaluation_uuid>/sealed.json

p/<proposal_uuid>.json

r/<route_uuid>.json
r/current.json

j/<job_name>/<job_id>/intent.json
j/<job_name>/<job_id>/receipt.json
j/<job_name>/<job_id>/result.json

status/current.json
```

Rules:

- `c`, `l`, versioned artifacts, and job records are immutable.
- Only `current.json` and `status/current.json` are mutable, using conditional replacement.
- Every derived object binds its scope, profile, UUID, content digest, parent UUID/digest, source manifest digest, configuration digest, prompt digest, model-binding digest, code revision, and creation time.
- Immutable writes are create-same: an existing identical digest succeeds; different content at the same key is an error.
- Raw capture has no current pointer.
- Pointers reference only fully validated immutable artifacts.
- The status object is a disposable UI projection, never authority.
- Raw customer content remains in the private store. Logs and release evidence contain only digests, counts, object keys, request IDs, and redacted provider receipts.

## Summary and classification loop

### Threshold progression

```text
MILK_SUMMARY_THRESHOLDS=100,1000,10000,100000
```

Mechanics may use `1`; production defaults remain powers of ten.

For each scope:

1. List all complete `c/` objects.
2. Load the current summary and its ancestor source manifests.
3. Subtract exactly processed capture keys.
4. If the next threshold is not crossed, update status and exit without inference.
5. Select the lexicographically earliest unprocessed UUIDv7 keys needed for that threshold.
6. Validate body and envelope digests.
7. Compute model-free delta statistics.
8. Merge exact accumulators with the parent summary.
9. Select deterministic representative and tail samples.
10. Run the fixed summary agent.
11. Validate and commit the summary.
12. Compute deterministic readiness.
13. Continue through every crossed threshold in order during the same reconciliation.
14. Continue into eval generation if the newest readiness result makes it immediately eligible.

Full listing at the four milestone counts is intentional. It handles late object arrival without a database, counter service, or fragile high-water assumption.

### Structural statistics

Milk Man, not Parlor, parses supported OpenAI JSON and SSE.

Required exact counts and distributions:

- complete captures, successful responses, non-2xx responses, parse successes/failures;
- endpoint, upstream model, route target, fallback reason, status and error class;
- streaming, modalities, message/input-item counts;
- tool definitions, tool calls, valid tool arguments;
- structured output, reasoning effort, refusal and finish state;
- request/response bytes;
- input, output, cached and reasoning tokens when reported;
- TTFT, total latency and output tokens/second;
- duplicates, unique exchange content and capture gaps;
- concurrency and time-of-day distribution.

Each numeric accumulator retains count, sum, sum-of-squares, min, max, and a fixed versioned logarithmic histogram. Cumulative counters merge exactly; p50/p95/p99 are reported as histogram upper bounds. Wilson 95% intervals accompany parse, success, duplicate, eligibility, and classifier proportions.

### Semantic sample and taxonomy

Each checkpoint selects:

- a deterministic uniform sample using the lowest hashes of full capture keys;
- deterministic tails for errors, tool usage, multimodal traffic, long inputs, rare structural cells, and low-frequency operations.

Default sample sizes:

```text
MILK_SUMMARY_REPRESENTATIVE_SAMPLE=256
MILK_SUMMARY_TAIL_SAMPLE=64
MILK_CLASSIFIER_TEXT_BYTES=2048
```

The fixed semantic taxonomy is versioned and starts with:

```text
operation:
answer, summarize, extract, classify, transform, generate,
code, plan_or_tool_use, conversation, other

domain:
general, software, math_science, business, legal,
finance, health, creative, other

capability:
knowledge, reasoning, instruction_following,
structured_output, tool_use, multimodal

oracle:
exact, schema, executable, reference, pairwise_judge, human

sentiment:
positive, neutral, negative, mixed, unknown

outcome:
success, refusal, partial, upstream_failure, malformed, unknown
```

Each label also includes language, complexity, answerability, safety class, confidence, and abstention. Do not infer identity, health status, wealth, politics, or other sensitive personal attributes.

The summary agent receives:

- the previous compact summary;
- exact cumulative and delta structural statistics;
- bounded excerpts from both sides of the deterministic sample;
- the fixed taxonomy and output schema.

It writes one JSON output file and must call:

```bash
milk job commit "$MILK_JOB_ID" "$MILK_JOB_OUTPUT"
```

The commit handler—not the model—sets object keys, scope, parents, provenance, counts, digests, and pointers. Code recomputes aggregate label counts; it never trusts model-supplied totals.

Teacher labels are stored under `l/` and reused when capture, taxonomy, prompt, and model-binding digests match. A cheaper classifier may replace teacher labeling later only after a held-out agreement study; do not train that classifier in the first vertical.

### Readiness

Readiness is deterministic and makes no model call.

Production defaults:

```text
MILK_EVAL_MIN_CAPTURES=1000
MILK_EVAL_REPRESENTATIVE_CASES=24
MILK_EVAL_TAIL_CASES=8
MILK_EVAL_MIN_UNIQUE_SOURCES=32
MILK_EVAL_MIN_PARSE_WILSON_BPS=9500
MILK_EVAL_MAX_ABSTAIN_WILSON_BPS=2000
```

Eligibility requires:

- complete production-profile capture;
- supported request and returned response parsing;
- successful response;
- unique request-response content digest;
- benign text case;
- non-abstained classification;
- an executable, exact, schema, reference, pairwise, or human oracle;
- sufficient representative and tail coverage.

Do not reintroduce session identity. The threshold unit is one complete gateway exchange containing whatever prior conversation context the client supplied.

Mechanics scopes can become mechanics-ready but can never produce a production-qualified route.

## Eval and model loop

### Eval generation

A ready summary triggers a fixed teacher job selected through `MILK_EVAL_*`.

The deterministic plan selects:

- 24 representative cases by cycling through populated operation categories and choosing the lowest deterministic hash;
- 8 tails from long, rare, error-prone, tool, multimodal, and low-confidence cells;
- unique source exchanges only.

The generated eval must bind source digests without copying raw source text into its manifest. Validation requires:

- exact schema and planned order;
- unique case IDs and inputs;
- source and summary provenance;
- answerability and appropriate oracle;
- no answer leakage;
- no duplicate or near-duplicate cases;
- no unsupported tool or multimodal requirement;
- source separation from training data;
- one independent validator verdict per case.

Invalid output receives one bounded repair prompt. A still-invalid revision remains an unreferenced job result and does not advance `e/current.json`.

### Dataset separation

Before teacher-data generation, deterministically assign each unique source digest to exactly one split using a versioned hash policy:

```text
train       80%
DEV         10%
calibration 5%
sealed      5%
```

The split assignment is immutable for a scope and policy version.

- Training examples derive only from the train split.
- The three model branches use the same ordered DEV set.
- Static FP8 may use only the calibration split.
- The deterministic winner alone sees the sealed split once.
- Mechanics and public/generated traffic remain isolated from production data.

Dataset targets are reproducibility inputs selected by environment variables, not a commercial allowance or runtime spending system.

### Teacher, training and evaluation

Model roles are deliberately asymmetric:

- The only fine-tune and merge base is `Qwen/Qwen3.5-0.8B` at revision
  `2fc06364715b967f1860aea9cf38778875588b17`. This identity is fixed in
  `config/student.json`, enters every dataset/training/evaluation job digest,
  and cannot be overridden by an environment variable.
- Data generation uses the strongest reviewed OpenAI-compatible binding
  available through `MILK_TEACHER_*`. Eval generation and independent
  validation use their own reviewed `MILK_EVAL_*` bindings. These roles may
  select GLM or another approved high-intelligence model without code changes.
- Teacher, eval, and validator calls never fall back to the 0.8B student or to
  a student-derived endpoint. A missing or failed high-intelligence binding
  blocks that semantic job; it does not silently lower generation quality.
- The cheaper `MILK_SUMMARY_*` binding remains isolated to bounded traffic
  classification. Summary classification output is not teacher training data.

The full whiteboard sequence is:

1. Generate bounded teacher training targets from train sources.
2. Validate and publish one immutable dataset.
3. Launch one Qwen3.5-0.8B training job.
4. Merge the resulting adapter with the exact pinned Qwen3.5-0.8B base revision.
5. Produce three candidates:
   - BF16;
   - dynamic FP8;
   - static FP8 using only the calibration split.
6. Evaluate all three concurrently on the identical ordered DEV set.
7. Select the winner in code using the fixed score tuple.
8. Evaluate only that winner on the sealed set.
9. Write an unsigned proposal under `p/`.

The score tuple and tie-break order must be declared in the evaluation config and digested into the job identity. A model cannot choose the winner.

## Modal controller bootstrap

The first controller is the pinned `zai-org/GLM-4.5-Air-FP8` revision on one H200 using a pinned weight-free SGLang runtime. Its official model card documents OpenAI-compatible SGLang serving and one-H200 FP8 operation, while full 128K context requires more capacity; the first controller therefore uses a reviewed bounded context rather than tuning. [GLM-4.5-Air-FP8 model card](https://huggingface.co/zai-org/GLM-4.5-Air-FP8)

`milk run inference-ensure` must:

1. Derive a deterministic deployment identity from provider, exact model revision, SGLang image digest, serving arguments, GPU, scope and code revision.
2. Check for an existing deployment and Modal Volume marker.
3. Hydrate the pinned model revision into a Modal Volume if absent.
4. Deploy one H200, minimum containers zero, with a short idle scale-down.
5. Run authenticated `/v1/models` and bounded Chat Completions smokes.
6. Write intent, provider receipt, endpoint receipt and result.
7. Write local `controller/current.json` containing endpoint, model, provider identity, binding digest and API-key environment-variable name—not the key.
8. Return `complete`.

`bin/man bootstrap`:

1. Creates one trajectory and appends the operator's original task.
2. Invokes `milk run inference-status` and `milk run inference-ensure` directly, without a model, and records both commands, results and exit codes in that trajectory.
3. Exits after a dry-run plan; on failure it aborts with the recorded result and never starts Headlong.
4. On `ready`, validates the exact `controller/current.json`, intent and endpoint identities before warming the controller.
5. Removes Modal-management, bootstrap and alternate inference credentials from the development process.
6. Starts Headlong once, on the same trajectory, with the validated controller as its only reasoning endpoint.
7. Gives the controller the original task and real job outputs as trajectory context; provider selection and controller creation never depend on model compliance.
8. Proves the first reasoning call reached Modal GLM using the trajectory and Modal request receipt.

The first implementation does not search serving configurations. Add `inference-benchmark` only after this fixed controller and the data vertical work end to end.

`milk run inference-stop` terminates the deployment and proves zero active containers; the cached model volume remains.

## GPU provider contract

Use two explicit implementations, not a provider framework:

- Baseten primary for post-training and initial winner serving.
- Modal fallback only after a definite Baseten pre-create denial.

A timeout, disconnect, 429, 5xx, or ambiguous create must reconcile the exact Baseten identity before retry or fallback. Never create a second resource while the first may exist.

Every external job records:

```text
deterministic job ID
source/config/model/image digests
create intent
provider request and object ID
result/artifact digests
termination intent
termination receipt
verified zero-capacity observation
```

Pure calculations do not need claims. Before inference or provider mutation, create one deterministic intent. Replays return the stored result. This prevents duplicate work; it is not a spending or product-budget mechanism.

The shared `$1,000` figure is only the supervised build-validation allowance. Do not implement budget ledgers, allowance slots, route caps, token caps, or per-run model-call caps.

## Signed routing

Milk Man creates unsigned proposals only. An operator-run signer in `milk-parlor/scripts/sign-route` holds the private key outside both runtimes.

A signed route contains:

```json
{
  "schema_version": "milk.route.v2",
  "route_id": "<uuidv7>",
  "scope_id": "<uuid>",
  "revision": 4,
  "previous_route_id": "<uuid-or-null>",
  "proposal_digest": "<sha256>",
  "candidate_artifact_digest": "<sha256>",
  "baseline_binding": "baseline",
  "candidate_binding": "candidate-a",
  "candidate_basis_points": 100,
  "fallback": "before_first_byte",
  "not_before": "<UTC>",
  "expires_at": "<UTC>",
  "signer_key_id": "<id>",
  "signature": "<ed25519>"
}
```

Parlor:

- verifies canonical manifest bytes with Ed25519;
- caches routes independently per scope;
- ignores an invalid or stale replacement;
- routes baseline when no valid manifest exists;
- selects the candidate deterministically from route ID and exchange UUID;
- retries baseline only before any candidate headers or bytes reach the client;
- never replays after streaming begins;
- treats rollback as a new signed higher revision;
- treats a signed zero route as candidate binding null and basis points zero.

Candidate credentials remain deployment environment bindings. Do not implement hot rotation.

## Status interface

Embed one raw HTML/CSS/JavaScript page in Milk Parlor:

- reuse the owned pixel milk-carton asset from `/Users/shantanu/milk-ide/milkCarton.png`;
- reuse the original Milk HTML, CSS, and typewriter text-execution code as the
  donor instead of recreating its interaction;
- apply Susan Kare's design discipline: immediate legibility, crisp pixel
  iconography, a restrained system palette, strong information hierarchy,
  memorable direct metaphors, and small moments of delight without ornament;
- keep the black terminal background and monospace/typewriter voice, but use
  motion only to reveal live execution; honor reduced-motion and provide the
  same information without animation;
- no frontend framework, package manager, build step, database, or analytics;
- enter the same operator API key client-side and retain it only in `sessionStorage`;
- fetch only `/api/status`.

This dashboard is deferred until the data and route loop works. It remains one
hyper-minimal, dependency-free document and a read-only view of the UUID's
object-memory progress; it cannot launch jobs, mutate routes, expose secrets,
or display raw customer traffic.

Show:

- Parlor health and capture counters;
- persisted complete exchange count;
- next summary threshold and progress;
- latest summary, readiness and eval;
- controller and teacher endpoint state;
- current Milk job and active GPU count;
- route, candidate and fallback state.

`/api/status` authenticates the key, resolves its scope, and combines Parlor’s local counters with one GET of `status/current.json`. It never lists raw traffic or returns prompt content.

## Images and deployment

Milk Parlor:

- Alpine/musl Rust builder stage;
- BuildKit cache mounts for Cargo registry, Git and target;
- rustls/webpki roots;
- stripped static binary;
- final `scratch` image containing only the binary, certificates and licenses;
- target compressed image size below 50 MiB;
- no shell, libc, compiler, Node, Python, CUDA or model weights.

GPU images:

- pinned compatible glibc/CUDA bases;
- shared cached layers;
- no model weights;
- model revisions hydrated into Modal Volumes or Baseten-native mounts and identified by digest.

GitHub Actions:

- builds and publishes only affected `linux/amd64` images;
- uses registry-backed BuildKit caching;
- emits immutable image digests, provenance and SBOM;
- never runs Milk reconciliation, provider jobs, deployment, traffic generation, or paid work.

Cloud deployment:

- one local deploy command accepts an immutable Parlor image digest;
- deploys the Cloudflare Worker/container binding;
- binds `parlor.milkinfrastructure.com`;
- waits for health;
- runs the direct SDK smoke;
- records Worker version, container application version, image digest and configuration digest.

Remove old images only after proving they are not referenced by Cloudflare, Modal, Baseten or a retained run.

## Limited-context execution packages

Every coding agent receives this goal, its owned subsystem, exact public contracts, and only the listed donor files. It must not broaden scope or build speculative abstractions.

### [~] P0 — Preserve and establish clean repositories

Progress 2026-09-01:

- [x] Verified current Milk Man and Milk Carton revisions and the seven-path M5A4 dirty state.
- [x] Saved and verified complete Git bundles, the dirty patch, and bounded local state under `/Users/shantanu/milk-release-evidence/milk-v2-bootstrap-20260901`.
- [x] Installed this file as the sole active repository tracker and removed the previous `GOAL.md`.
- [x] Reduced Milk Man to 38 tracked files and 5,851 lines, committed the result as independent root `5bcfaeb4fe3733b5962c6b5fc07b152eac827171`, and removed the stale Prime upstream remote.
- [x] Published independent-root default histories. Recorded checkpoints include Milk Man `530235a879c3078623ef2f69e3fb830667a9e496` and Milk Parlor `70dba12f96a12feedf7ed13b605f20d05ebefd23`; the verified local bundle preserves the obsolete history.
- [ ] Detach Milk Man's GitHub fork metadata and remove the 56 legacy remote branches after confirming the retained bundle; GitHub still reports `fork: true` with parent `PrimeIntellect-ai/prime-agent`.

Objective:

- Re-verify current revisions and dirty state.
- Create checksum-verified Git bundles and a bounded state archive.
- Establish clean `milk-parlor` and `milk-man` trees with independent root histories, not a Prime-derived commit graph.
- Install this document as the sole `goal_tracker.md`.

Allowed donor inputs:

- current repository HEADs and dirty Milk Man paths;
- current evidence index;
- no raw Codex transcript import.

Acceptance:

- bundle paths, SHA-256 digests and restored-tree verification recorded;
- final GitHub repositories report `fork: false`, Milk Man has no Prime upstream remote, and both histories begin from Milk-owned root commits;
- new repositories contain only minimal source plus concise license, notice, security, contribution, tracker, and image-release metadata;
- progress uses `[x]`, `[~]`, and `[ ]`, with evidence required for `[x]`.

### [x] P1 — Minimal Milk Man development harness

Progress 2026-09-01:

- [x] The independent root `5bcfaeb4fe3733b5962c6b5fc07b152eac827171` contains the 1,112-line pinned Headlong subset, Bash entrypoint, exact-workspace state, bounded memory, trajectories, and two Milk skills.
- [x] Replayed two-workspace configuration and exact-workspace resume locally without Docker; a mismatched workspace set fails closed.
- [x] Proved one complete localhost OpenAI-compatible model loop that read a skill, wrote bounded memory, and retained trajectory records.
- [x] Retained the post-cut local receipt at `/Users/shantanu/milk-release-evidence/milk-v2-local-postcut-20260901/report.json`, SHA-256 `750c9a8d3c728295184176c514e96393340f265df44420df7247713d584c1571`.
- [x] Baseten `zai-org/GLM-5.3-Flash` resumed trajectory `d5985d21-2da8-4acb-ae83-93cad42857ff`, read `milk-system`, inspected both repositories, found the unauthenticated platform-readiness probe blocker, changed only `images/serve/server.py`, passed `py_compile`, and retained reviewable commit `2068b4026` with no provider lifecycle, push, deploy, or route action.

Owned:

```text
bin/man
vendor/headlong/
prompts/develop.md
skills/
milk_v2/state.py
```

Allowed donor code:

- current `milk/man.sh` workspace, environment and resume logic;
- pinned Headlong `shellm`, `llm`, trajectory, context, memory, skill and file tools.

Acceptance:

- runs locally from Bash without Docker;
- reads `goal_tracker.md` and both skills;
- opens both workspaces;
- performs one bounded self-edit;
- survives interruption and resumes the exact trajectory;
- leaves a reviewable local commit.

Excluded:

- Prime, dashboards, persistent thinkers, messaging, deployment, provider jobs and production scheduling.

### [~] P2 — Milk Parlor direct request path

Progress 2026-09-01:

- [x] Created the fresh Rust repository at root `d089c46c3255b76bbf4ae40774d41aae5681a0bf` with no legacy code; current published main is `70dba12f96a12feedf7ed13b605f20d05ebefd23`.
- [x] Replayed local Chat Completions SSE and Responses passthrough, invalid-key `401`, exact two-sided compressed capture, and response survival under an injected local-store failure.
- [x] Added env-selected local/S3 storage and replayed signed create-only PUT plus bounded GET against an independent fake S3 endpoint.
- [x] Local Parlor wrote two complete captures to the real `milk-prod` R2 bucket with zero drops or storage failures; retained receipt: `/Users/shantanu/milk-release-evidence/milk-v2-r2-20260901/report.json`, SHA-256 `7c96b77a387dbcce75ecbf4c696cebefc28d4f3e1f0d11c685007918f301169f`.
- [x] Added cached `linux/amd64` GHCR publication, Cloudflare Registry transfer, and a one-instance Worker deployment config without adding a runtime workflow.
- [x] GitHub Actions image run `33574807455` succeeded for `70dba12f96a12feedf7ed13b605f20d05ebefd23`: GHCR image digest `sha256:c5aab42449834638c3bcd31855ee1e8d68fe21262191b9b78f54e50553ce0138`, `linux/amd64` manifest `sha256:b63c78c67ace7b8f40784f377335777e886642abd026530b933adb4123e0c991`, 2,245,105 compressed layer bytes, and Cloudflare Registry digest `sha256:456a38baf70bd08ab8d10724f8873466b99277d7476dcb1095ae501d08130387`.
- [x] The stripped local arm64 release binary is 3,252,912 bytes; Rust format, check, Clippy, and release build passed.
- [x] Retained the content-free local receipt at `/Users/shantanu/milk-release-evidence/milk-v2-local-postcut-20260901/report.json`, SHA-256 `750c9a8d3c728295184176c514e96393340f265df44420df7247713d584c1571`.
- [x] Deployed immutable Cloudflare Registry image digest `sha256:456a38baf70bd08ab8d10724f8873466b99277d7476dcb1095ae501d08130387` at `parlor.milkinfrastructure.com`; official OpenAI Python SDK authentication, baseline inference, asynchronous R2 persistence, and exact sent/returned body identity passed.
- [x] A 99-request burst exposed the bounded writer queue without blocking successful customer responses: 23 captures dropped and zero storage writes failed. A follow-up 24-request run at concurrency four returned 24/24 and added zero drops. This is capacity evidence, not a production qualification claim.
- [x] Retained the content-free live vertical receipt at `/Users/shantanu/milk-release-evidence/milk-v2-live-20260901/report.json`, SHA-256 `cda2ed3e33acea77bef2c710fd64c558e033e3441426e10a245c6a8d45a70caa`.
- [ ] Record a controlled warm capture-enabled-versus-disabled timing comparison before claiming a capture overhead bound.

Owned:

```text
src/main.rs
src/store.rs
Dockerfile
.github/workflows/image.yml
deploy/cloudflare/
```

Keep capture, routing, and status in `main.rs` until a real maintenance boundary
justifies another module; file splits are not milestone work.

Allowed donor code:

- exact auth, proxy, streaming, writer, store and route functions from current Carton.

Acceptance:

- official SDK Chat Completions and Responses, including streaming, return through local then hosted Parlor;
- invalid key returns `401`;
- keys isolate scopes;
- one completed exchange writes one exact two-sided `c/` object;
- injected storage failure preserves the response and increments drop telemetry;
- capture-enabled versus disabled warm timing is recorded;
- final image is binary-only and below the size target.

Excluded:

- all jobs, summaries, inference, training, old schemas and compatibility.

P1 and P2 proceed in parallel after P0.

### [x] P3 — Deterministic Milk job runtime

Progress 2026-09-01:

- [x] The independent root `5bcfaeb4fe3733b5962c6b5fc07b152eac827171` contains the strict fixed job registry, direct CLI, local store, and SigV4 S3 implementation.
- [x] Replayed `status`, `operate --once`, and `run summary` against an empty local store; unchanged invocations returned the same identity with zero inference and provider calls.
- [x] Configuration accepts only ten reviewed handler identifiers and reviewed environment-variable names; it cannot introduce an executable path.
- [x] All ten reviewed handlers are implemented. `operate --once` deterministically advances through route proposal and stops at the operator-sign boundary; explicit `gpu-reconcile` records provider teardown and zero capacity.
- [x] Proved the public CLI against R2 through two checkpoints: immutable create-same objects, conditional pointer replacement, one concurrent owner plus one exit-75 duplicate, and an idle zero-call replay. Retained receipt: `/Users/shantanu/milk-release-evidence/milk-v2-r2-20260901/report.json`, SHA-256 `7c96b77a387dbcce75ecbf4c696cebefc28d4f3e1f0d11c685007918f301169f`.

Owned:

```text
bin/milk
config/jobs.json
milk_v2/config.py
milk_v2/store.py
milk_v2/runner.py
```

Allowed donor code:

- current local/SigV4 S3/R2 store;
- create-same and conditional pointer behavior;
- current environment-name validation.

Acceptance:

- local and R2 backends select through environment variables;
- `milk status`, `milk run <job>` and `milk operate --once` emit the exact JSON contract;
- unchanged store returns idle with zero inference/provider calls;
- concurrent identical jobs converge on one identity;
- no arbitrary executable can enter through config.

### [x] P4 — Modal GLM controller and handoff

Progress 2026-09-01:

- [x] The independent root `5bcfaeb4fe3733b5962c6b5fc07b152eac827171` contains the fixed Modal controller, immutable local intent/endpoint receipts, CLI wiring, and same-trajectory bootstrap handoff source.
- [x] Replayed deterministic ensure/stop dry runs and read-only provider status; both reported zero provider calls and no active Modal containers.
- [x] Reconciled the first real deploy attempts without model inference: the first stopped after a pre-deploy tag-length rejection; the second deployed Modal app `ap-FsI3COYpkl1jiOIZXio8vT`, failed during remote hydrate import, and produced termination plus independent zero-container receipts before the import fix at `530235a879c3078623ef2f69e3fb830667a9e496`.
- [x] Hydrated and served the pinned GLM-4.5-Air-FP8 revision on one H200 as Modal app `ap-dBNCTsA9wu7aUjAmiFYW1a`; authenticated `/models` and Chat Completions smokes passed and immutable intent, deploy, endpoint, smoke, and result receipts were retained in object memory.
- [x] Fixed H200 KV-cache admission and `.modal.direct` endpoint validation; the launcher now warms the endpoint and deterministically records status/ensure before any model call, replacing the prompt-only bootstrap action.
- [x] The same trajectory switched from the bootstrap binding to `glm-4.5-air-fp8` and completed three controller-backed reasoning turns. The run exposed a 32K-context completion-overreservation; `aa82deb1d942f465457e393d8fcf0e19d91fc90b` fixed the post-handoff ceiling without changing the controller model or endpoint.
- [x] `milk run inference-stop` stopped the exact app and wrote stop, zero, and termination receipts. A separate Modal app/container listing reported state `stopped`, zero tasks, and zero active containers.
- [x] Retained `/Users/shantanu/milk-release-evidence/milk-v2-modal-handoff-20260901/report.json`, SHA-256 `3e11f112979876f52ac7df4a8208a869a7361df16900b1e974adfcb6da9345eb`.

Owned:

```text
milk_v2/providers/modal_controller.py
images/controller/
prompts/bootstrap.md
```

Allowed donor code:

- current Modal identity, intent, receipt, teardown and ambiguity lessons;
- no old gpt-oss/Qwen constants or GPU frontier state machine.

Acceptance:

- the local OpenAI-backed Milk Man invokes `inference-ensure`;
- one H200 serves the pinned GLM-4.5-Air-FP8 revision;
- weights come from a Modal Volume, not OCI;
- the same trajectory resumes and its next model call reaches GLM;
- `inference-stop` proves zero active Modal containers.

P4 may implement against the P3 CLI contract while P3 is finishing.

### [x] P5 — Summary, classification and readiness

Progress 2026-09-01:

- [x] Implemented strict two-sided Chat Completions/Responses parsing, exact structural accumulators, deterministic full-population sampling, bounded tails, fixed semantic labels, cached label objects, compact checkpoint ancestry, and deterministic readiness.
- [x] A fresh local Parlor-to-Milk-Man run processed Chat SSE and Responses captures through thresholds `1,2`, wrote two summary/readiness checkpoints and two distinct labels, and made one semantic call per new label.
- [x] The immediate replay was idle with zero inference/provider calls; cumulative classified count stayed at two and mechanics became ready but not production-qualified.
- [x] Direct integration found and fixed strict RFC3339 fractional precision and Responses top-level `input` extraction defects.
- [x] Retained the content-free local lineage receipt at `/Users/shantanu/milk-release-evidence/milk-v2-local-postcut-20260901/report.json`, SHA-256 `750c9a8d3c728295184176c514e96393340f265df44420df7247713d584c1571`.
- [x] Repeated the complete capture-to-summary/readiness lineage against real R2 using an environment-selected localhost mechanics inference binding; replay made zero calls and mechanics remained explicitly non-production-qualified.
- [x] Repeated semantic inference against the real Baseten OpenAI-compatible binding through restricted Headlong job mode with only `milk_job_read`, `milk_job_commit`, and `milk_status`; one threshold-one checkpoint completed in two inference turns and its immediate replay made zero calls.
- [x] Processed 100 complete mechanics captures into a second real R2 summary/readiness checkpoint in two inference turns; the result remained explicitly non-production-qualified.
- [x] Proved a production scope below its first threshold remained model-free with zero inference calls, zero provider calls, and no route attempt.
- [x] Exposed bounded content-free structural quality, performance distributions, and semantic classifier totals in `status/current.json`; the dashboard still reads one object and never reads customer text.

Owned:

```text
milk_v2/summary.py
milk_v2/runner.py
prompts/summary.md
```

Allowed donor code:

- current structural statistics;
- Wilson intervals;
- deterministic representative/tail sampling;
- semantic taxonomy and drift;
- readiness checks.

Acceptance:

- a mechanics threshold of one produces `s/`, `readiness/` and `status/`;
- production thresholds are powers of ten;
- parent summary plus delta yields the next checkpoint;
- a leap across thresholds creates each checkpoint in order;
- replay makes no duplicate inference call;
- invalid semantic output cannot advance a pointer;
- no session identity or customer text enters status.
- semantic inference can read only its prepared input and commit one validated output; model arguments cannot choose scope, object key, prefix, parent, provenance, pointer, provider, or credential.

### [x] P6 — First live production vertical

Completed 2026-09-01:

- [x] Official OpenAI Python SDK traffic authenticated through hosted Parlor and persisted into the production R2 backend.
- [x] A fresh mechanics scope produced threshold-one and threshold-100 summary/readiness checkpoints through local Milk Man.
- [x] Direct decompression and hashing proved the stored request and response bodies were byte-identical to the SDK wire bodies.
- [x] Authenticated `/api/status` reported the correct mechanics and production scope progress.
- [x] Mechanics remained non-production and could not qualify a route; the real production scope below threshold made no semantic, GPU, or routing call.
- [x] Retained `/Users/shantanu/milk-release-evidence/milk-v2-live-20260901/report.json`, SHA-256 `cda2ed3e33acea77bef2c710fd64c558e033e3441426e10a245c6a8d45a70caa`.

Integrate P2 through P5:

```text
official SDK
-> parlor.milkinfrastructure.com
-> baseline response
-> R2 c object
-> local milk operate --once
-> summary
-> readiness
-> status page
```

Acceptance:

- one mechanics key proves threshold one;
- 100 complete exchanges prove the first normal summary checkpoint;
- decompressed capture contains byte-identical sent and returned bodies;
- the status page reports the correct scope and progress;
- mechanics evidence is explicitly marked non-production.

Do not continue to eval implementation until this vertical is retained.

### [x] P7 — Eval generation

Completed 2026-09-01:

- [x] Added exact request/response digests, the fixed request-digest split policy, exact split quotas, and split-aware readiness restricted to locally scoreable exact, reference, and schema oracles.
- [x] Added deterministic distinct-source representative/tail planning, restricted generator and independent validator sessions, one bounded repair, immutable job/eval artifacts, and guarded `e/current.json` advancement.
- [x] A direct mechanics `milk operate --once` smoke traversed capture, summary, readiness, eval, validation, and `e/current.json` in six inference turns; replay made zero calls.
- [x] A separate rejection smoke proved one validator rejection, one repair, acceptance in ten turns, zero-call replay, and `milk status` advancing to `dataset`.
- [x] Published `672b58cbe` and `3ec05028f`; the pinned Qwen3.5-0.8B student contract and separate high-intelligence eval/validator bindings remained intact.

Owned:

```text
milk_v2/eval.py
prompts/eval.md
```

Allowed donor code:

- existing case planning, leakage checks, schemas, validation and scoring.

Acceptance:

- readiness triggers one eval job;
- representative and tail selections match the deterministic plan;
- every case binds its source and summary;
- local and model validation pass;
- replay performs no duplicate teacher call;
- `e/current.json` advances only after the complete validated revision.
- the eval model runs through the same restricted `milk job read`, `milk job commit`, and `milk status` interface and cannot select storage or provider authority.

### [x] P8 — Dataset, training and three evaluation branches

Progress 2026-09-01:

- [x] Generated live R2 dataset `f59d59b7-9992-5f6c-bad0-9842afeec31a` from the accepted eval with disjoint train/DEV/calibration/sealed objects; creation used the teacher binding and immediate replay made zero inference or provider calls.
- [x] Expanded the mechanics vertical to eval revision `6dcc2cb3-087a-55a9-8791-b96d9359034a` with four validated cases, then generated dataset `a7376834-b241-5d8d-850b-105624d4550c` with exact counts train 1, DEV 2, calibration 1 and sealed 1. Eval and dataset replays made zero inference calls.
- [x] Published the weight-free Linux AMD64 training image in Actions run `33583603822` at `ghcr.io/milkinfrastructure/milk-man-train@sha256:93f6a973d2e7b04e3dfc0c9807b5b83cb661601ebfbc1e371659b2530a9dd16f`; Qwen weights remain a separately mounted exact revision.
- [x] Created and retained full-access Baseten operator key `milk-production-operator-20260902` in macOS Keychain without writing it to the repository. Training project, job search, secret management, API-key management, and hosted-inference checks all returned 200; `zai-org/GLM-5.3-Flash` is visible. Refreshed and re-read Baseten runtime secrets `milk-control-store-access-key-id` and `milk-control-store-secret-access-key` from the current R2 credentials.
- [x] Milk Man created Baseten job `q09v7mq`, trained exact `Qwen/Qwen3.5-0.8B@2fc06364715b967f1860aea9cf38778875588b17` for one mechanics step on one H100, retained model `17959b86-64de-5c10-baa3-274a876a857a` in R2, observed completion, and verified zero active Baseten training jobs.
- [x] Immediate training replay returned `provider_calls: 0` and status now deterministically advances to `evaluate`.
- [x] Milk Man retrained the expanded dataset in Baseten job `qek7jrq`, retained merged model `fb0eacdd-4772-5fc5-88e0-d99ecc3aafc8`, and replayed with `provider_calls: 0`.
- [x] Published the fixed three-branch policy, calibrated static-FP8 evaluator, and concurrent Baseten orchestration. The first runtime attempt exposed a missing C compiler required by TorchAO/Triton; a second isolated an `inference_mode` incompatibility. Commit `ddc04e9f0` replaced it with `no_grad`, and Actions run `33586890548` published `ghcr.io/milkinfrastructure/milk-man-eval@sha256:7d045e6432b2e6222a58b976889b8c0b4f548a55525826932ae3b435cf7f6343`.
- [x] Final coherent DEV jobs `wp98xz3`, `wlklg03`, and `3yym443` completed on identical ordered cases. Checked-in code selected static FP8 at 10,000/10,000, zero errors, 316 ms p95 and 16.978 tokens/second. Winner-only sealed job `w7x7l63` completed and produced sealed evaluation `689e3c27-d0f1-58cb-8e12-e60dafc008a7`; evaluation group `73837076-9e42-5a8a-ac56-73eac5830a89` finalized under deterministic identity `32aa44d6bc531bc282c8bfdd49c62b5c35e957269745926aceba39c1670b6a0b`. Immediate replay retained the same artifacts with zero inference and provider calls.
- [x] Actions run `33590675453` published the authenticated serve image `ghcr.io/milkinfrastructure/milk-man-serve@sha256:5d265b975920f049775e16f959b6fe5177c4c5429ab66eca6bf178d0a892f851`; weights remained outside OCI.
- [x] Candidate artifact `04f4af2eb8b2596985a4694d1a167ea99c66063b19438425199d76bf1c2e8fbd` received a definite Baseten `custom_base_image_not_enabled` preflight with no Baseten model or deployment, then deterministically fell back to Modal app `ap-pf5pYKvKgMMo5SqEyx9ZF6` and volume `milk-candidate-04f4af2eb8b2596985a4`.
- [x] Milk Man verified the exact Baseten checkpoint inventory during Modal hydration, completed one authenticated inference smoke, retained candidate `40ee1fff-303c-5a5e-842c-72ee9880638d`, and advanced to corrected unsigned proposal `d86f2910-9ccc-5d56-9aeb-ee7b400f4f8c` at `p/d86f2910-9ccc-5d56-9aeb-ee7b400f4f8c.json`.
- [x] `milk run gpu-reconcile` stopped the exact Modal app and wrote immutable intent/result objects under `j/gpu-reconcile/04f4af2e...`; independent listings showed that app stopped with zero containers, every other visible Modal app at zero containers, zero Baseten candidate models, and training job `qek7jrq` in `TRAINING_JOB_COMPLETED` with checkpoint sync `COMPLETED`.

Owned:

```text
milk_v2/dataset.py
milk_v2/train.py
milk_v2/evaluate.py
milk_v2/providers/baseten.py
milk_v2/providers/modal_gpu.py
images/train/
images/eval/
config/student.json
```

Allowed donor code:

- deterministic partitions;
- only the training kernels needed for pinned `Qwen/Qwen3.5-0.8B` revision
  `2fc06364715b967f1860aea9cf38778875588b17`;
- BF16/dynamic-FP8/static-FP8 evaluation;
- Baseten and Modal lifecycle logic.

Acceptance:

- one bounded mechanics dataset;
- all generated training targets come from the separately configured strongest
  teacher binding; no teacher/eval/validator call falls back to the student;
- train, merge and all three candidates bind the exact pinned
  `Qwen/Qwen3.5-0.8B` revision and weight files never enter OCI;
- one real Baseten train/merge job;
- separate definite-preflight Modal fallback proof;
- identical ordered DEV inputs across all branches;
- code-selected winner;
- one sealed evaluation;
- unsigned proposal;
- termination receipts and independently verified zero capacity on both providers.

### [~] P9 — Signed routing and release

Progress 2026-09-01:

- [x] Published the independently reviewed signed canary, pre-byte fallback, rollback, and zero-route implementation at Milk Parlor commit `933b45eac824787cb064b869d93515b75c0c58a8`; requests never wait for R2 route refresh.
- [x] Fixed macOS Ed25519 one-shot signing at `b1744d79be67e7606c4ba8cb2eac2e693b6436d0` and published one canonical, signature-verified production zero route at revision 1.
- [x] Built the scratch image in Actions run `33579400572`: GHCR index `sha256:cb625bb33231629d18fea12925d55f5f96397b2492def794c615ed162d72562b`, Linux AMD64 manifest `sha256:6afe8277d9ce1b10b182258fe802f65e3cf1718050a7f4f8d7ca068b808aff7a`, Cloudflare digest `sha256:545ef3a0ccef16b20e0fe689d59fd7dff06651fcb6d00dbd1ecd51be53bde728`, and 2,328,627 compressed layer bytes.
- [x] Deleted the old Cloudflare Parlor application and retained only application `a039d064-0442-45e4-aa31-8dd838c015b6` with the pinned image. Commits `5e41260` and `bfa5681` added explicit instance generations for credential/route cutovers and raised the sleeping-container ceiling from 1 to 10 so an old process cannot block a new revision.
- [x] Two live production requests returned 200. The second complete R2 capture bound signed route `8384c78c-bd73-45dd-973b-13dd2a7b20fd` and selected baseline with no candidate or fallback.
- [x] Retained `/Users/shantanu/milk-release-evidence/milk-v2-signed-zero-20260901/report.json`, SHA-256 `39c13ab4a77662246b37338ea1bdd6b21a903a9a2de90175228080fb394d546b`.
- [x] Signed revision 2 (`96da3bdc-7dcf-4169-b0f0-ad07c5ed5433`) routed 100% to candidate artifact `04f4af2e...`; the official OpenAI Python SDK returned model `milk-qwen3.5-0.8b-static-fp8` with the requested exact response.
- [x] R2 capture `01a0606d-e155-7932-902c-aab870d951d9` retained a forced cold-start fallback from the same signed route with `fallback_reason: candidate_status_503`, baseline `200`, and no candidate bytes exposed.
- [x] Higher revision 3 (`c4668940-9131-4b67-a434-a834844b4e8c`) rolled exposure back from 100% to a 1% canary; capture `01a0606f-4638-7772-8fcc-c80e9175984b` bound that route and selected baseline with no fallback.
- [x] Signed zero revision 4 (`ce2f4d88-0107-429f-89a7-6a9083c14a18`) removed candidate identity and basis points. Capture `01a0606f-feca-7280-a6ec-fd529cea9f00` bound the zero route and returned baseline `200`; Cloudflare version `d1b61ee7-ce8f-47c3-b90e-4c1e61314537` contains no candidate URL, credential, or artifact binding.
- [x] Retained the content-free candidate, fallback, rollback, provider-drain, and zero-route receipt at `/Users/shantanu/milk-release-evidence/milk-v2-live-candidate-20260901/report.json`, SHA-256 `33f94057a7ae1ef700d4d16cbb335d958c193d4365033cfad1b05836aa6cb889`.
- [ ] Finish the concise public release docs and tagged release metadata; remove old public names, runtime Actions, unused images, fixtures, and transition documents.

Owned:

```text
milk-parlor route polling/fallback
scripts/sign-route
scripts/smoke
README and release metadata
```

Acceptance:

- operator signs an isolated mechanics route;
- official SDK proves candidate success;
- forced failure before first byte proves baseline fallback;
- a newer signed route proves rollback;
- a signed zero route disables the candidate;
- no candidate credential remains after teardown;
- both public repositories have concise macOS/Linux quickstarts, environment references, object-tree documentation, licenses, security guidance, tagged commits and release digests;
- old public names, runtime Actions, unused images, fixtures and transition documents are removed.

## Validation policy

Do not create a fixture-heavy test program.

Use only:

- `bash -n` for shell entrypoints;
- Python compilation/import check for fixed job modules;
- `cargo check` before cloud build;
- GitHub’s actual cached image build;
- one direct smoke per milestone;
- final end-to-end production scripts.

The final report must distinguish:

```text
source present
local mechanics
hosted mechanics
paid provider execution
production-qualified evidence
```

It must record commits, image digests, Cloudflare versions, object keys/digests, provider object IDs, route revisions, timings, replay results and zero-capacity observations without secrets or raw customer content.

## Explicit exclusions

Do not add:

- a third active repository;
- a database or queue;
- a resident manager;
- an internal tick/sleep loop;
- a standing GPU;
- a generic provider framework;
- a secret broker;
- product budget or allowance enforcement;
- model weights in OCI;
- local Docker/GPU requirements;
- Prime or Exo runtime bulk;
- deprecated-schema readers;
- synthetic traffic in production qualification;
- raw prompt archives;
- broad unit/fixture suites;
- GitHub Actions runtime reconciliation;
- self-signing, self-merging or self-deploying development agents.

## Completion definition

The goal is complete only when:

- Milk Man runs locally, reads its goal/skills/memory, self-edits either repository, resumes, and retains a reviewed commit.
- Milk Man provisions GLM-4.5-Air-FP8 on Modal and then uses that endpoint for its own next reasoning turn.
- `parlor.milkinfrastructure.com` accepts an operator-issued key through the official SDK and asynchronously writes exact two-sided traffic into R2.
- Local and scheduled Milk Man consume the same remote store through environment bindings.
- Production-like traffic progresses through summary, classification, readiness and validated eval generation.
- The full whiteboard model loop produces a trained Qwen3.5-0.8B student from
  maximum-intelligence teacher data, three comparable branches, deterministic
  winner, sealed result and unsigned proposal.
- Operator-signed routing proves candidate success, pre-byte fallback, rollback and signed zero.
- Baseten and Modal both end at verified zero active GPU capacity.
- Both repositories are minimal, published, documented and free of the old Prime/Carton control-plane bulk.
