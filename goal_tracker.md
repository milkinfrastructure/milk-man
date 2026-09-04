# goal_tracker.md — Build Milk Parlor and a Minimal Milk Man

This file is the repository implementation and evidence tracker. It does not
replace, modify, shorten, or redefine the active Codex goal. Brackets record
only evidence-backed implementation progress.

## Goal

Replace the pre-release architecture with two focused public runtime repositories:

- `milkinfrastructure/milk-parlor`: a tiny CPU-only Rust gateway deployed at `parlor.milkinfrastructure.com`.
- `milkinfrastructure/milk-man`: a local-first Bash agent harness plus deterministic Milk job runtime.

`milkinfrastructure/milk-landing` is the dependency-free static website only. It
contains no runtime, credentials, customer data, job controls, or cloud API.

- [x] Published the six-file static `milk-landing` repository at
  `9e71150cdf3bdd9217d4aea993b5e7965b66ee15`, disabled repository Actions, and
  activated both `milkinfrastructure.com` and `www.milkinfrastructure.com` on
  Cloudflare Pages. Both domains return the typewriter page with the original
  carton asset and strict static security headers.

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
 canary -> pre-byte candidate failure -> baseline -> rollback -> zero
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

## Current execution decision — 2026-09-02

- [x] Stopped the v21 100,000-case mechanics feed and removed its restart heartbeat. No local eval runner remains active.
- [x] Audited a 53,584-case prepared snapshot. Object schemas, identities, source bindings, digests, case IDs and accepted verdicts were valid, but 9,018 inputs (16.83%) were exact normalized duplicates across shards.
- [x] Reconstructed and inspected 1,872 accepted cases from eight deterministic shards. The corpus was dominated by simple transformations, extraction, classification, translation and repeated mechanics templates. The same GLM binding generated and validated the cases and accepted 98.47%; this proves mechanics, not useful eval quality.
- [x] Retain every v21 object as immutable mechanics evidence. Do not coordinate, publish, train from, repair or resume that revision.
- [x] Replaced the independent 100,000-case target with source-proportional generation: `MILK_CASES_PER_CONVERSATION=100`. `MILK_EVAL_SOURCE_CONVERSATIONS` selects an exact deterministic source count and stops before inference if it is unavailable. One eligible held-out conversation produced exactly 100 creative cases. The separate 100-source/10,000-case proof remains under P7.
- [x] The first v22 one-source attempt, revision `12c0e095680e3d2f04ce257dc0e4baed17b7d68bd338a63e86e5857b8bd1d5d4`, made eight OpenAI inference calls and zero provider lifecycle calls. The validator rejected 80 answer-leaking prompts and one incorrect answer; its 19 accepted cases were still trivial. No shard, eval pointer, dataset, training, or GPU work was published. Do not repair this attempt.
- [x] The second v22 attempt, revision `38a22326fae84d6557067d52c58ebd59f5815d7613a983a4a898e90d0acdc7f3`, used the deterministic 100-slot reasoning, setting, and difficulty brief. It produced substantially more varied multi-step work with no repeated 8- or 24-token prefix families. The semantic validator accepted 42 and rejected 58; its repair was stopped during validation. No shard, eval pointer, dataset, training, or GPU work was published.
- [x] v23 removed the second LLM validator. The eval model commits JSON-schema-constrained output; Milk Man enforces identity, count, source lineage, oracle representation, exact copy, and normalized duplicate checks locally. The implementation was published at `5947a4841`.
- [x] The first v23 pilot published immutable eval `7de3ce6e-760b-5dae-a790-0851fb38d960`, revision `43509f46cac86491073433ea758688668e36d89b63fa1c705752ce9f9dbcf6f6`, from one source to exactly 100 unique cases in four OpenAI inference calls and zero provider lifecycle calls. Format, lineage, count, copy, and duplicate checks passed; there were no repeated 8- or 24-token prefix families and no mechanics boilerplate.
- [x] A direct read of all 100 v23 outputs rejected this corpus for use: 31 cases had clearly wrong, impossible, non-unique, or under-specified expected answers. Examples included a copper zint that contradicted its premise, a five-item ordering with the wrong middle item, and multiple incorrect arithmetic and timeline results. Do not run dataset, training, GPU, or routing from this eval.
- [x] Published `a426e554a` with the shorter generation prompt: infer useful capabilities, prefer realistic work, solve each case, and recompute its expected answer before one structured commit.
- [x] Revision `7251287e5066c9772dbfe9a956f91190c96b9d0f5b0f0a80e1f6414561b3e3fb` was interrupted after immutable batch zero: 64 cases and two inference calls. Direct review found elementary correctness errors and correction-pair answer leakage. It wrote no prepared shard, `e/current.json`, dataset, provider, training, or route output. Never resume it.
- [x] Eval-source admission now uses only deterministic capture facts: distinct request digest, parsed HTTP-successful text on both sides, model completion, and no tools. Semantic labels such as answerability, safety, outcome, and oracle remain summary metadata; unsupported source oracles normalize to generated `reference` while their original label provenance remains bound.
- [x] Local Rust Parlor captured two realistic Responses exchanges into fresh R2 scope `8cc33bba-6790-4701-8a88-b3ba565971ee`. Local Milk Man wrote summary `4d9a0d1c-a7a6-54fe-9626-41488f3aa941`, readiness `259d0030-bb64-58ee-bd6a-81b1f30e22d9`, and selected the intended DEV source with readiness true.
- [x] Eval `4476d990-7047-5b5e-a2fa-58b3dd48bf0f` expanded that source into exactly 100 schema-valid, lineage-bound, unique cases in four inference calls and zero provider calls. Replay made zero inference and provider calls.
- [x] A direct read of all 100 accepted this revision only as mechanics evidence. Ninety-five cases were materially correct; orders 1, 50, 57, 72, and 74 contained bounded assumptions or unsupported details. All 100 remained in one event-aggregation family, so this corpus must not feed dataset or training.
- [x] Scope `8cc33bba-6790-4701-8a88-b3ba565971ee` reconciled 103/103 captures into summary `69cf59a3-d9aa-5a25-b3c0-f500b1aadbee` and readiness `484d8224-971c-541a-b571-a1dc8ede9d2f`, with exactly 50 DEV, 25 calibration, and 25 sealed held-out sources. Replay made zero inference/provider calls.
- [x] Revisions `ed4c84eda5fb1498d1a1f3a9a1c8bfb5b7fe5406027baedef08d121347d3c68b` and `3586f34b4e42156edd2a53ca12a63fa105878a2bc85559374b4fbc575f5d4f56` are rejected low-reasoning pilots: both passed format checks but retained source task templates and contained unacceptable semantic errors. Never coordinate, train, or route them.
- [x] Eval v24 revision `ab5f9fbc02664d5e03eebb97e664e1ae883c3fbeeae21facda1ce6553e860c3d`, eval `d2742262-68ae-5ca9-8728-ab0a5baf3acf`, used `gpt-5.6-sol` at maximum reasoning to prepare exactly 100 cases from one source in four inference calls and zero provider calls. Direct review found 98/100 materially correct and 96/100 clean including minor wording issues; all 100 followed their deterministic operation and structured-output contract with no duplicates, source copying, or improper answer leakage. Replay made zero calls. This is generation proof only and is not a training corpus.
- [x] Stopped the 10,000-case fan-out revision `9172e6c6f16ad4d5873a3c44e3ab59d56636ddbbe27a4db064b9d91fcea1e9a1` after one immutable 64-case generation receipt. It published no prepared shard, eval, dataset, training, GPU, or route state and must not be resumed.
- [x] The serial v24 scope `8cc33bba-6790-4701-8a88-b3ba565971ee` reached 100 cases, dataset, and Qwen3.5-0.8B training. Its three DEV jobs failed before inference because the evaluator expected the prior three-field validation record instead of the current record with empty `guidance`; all three jobs are terminal and no GPU remains active. Commits `9d1762bf1` and `68a4d7306` fixed and pinned the evaluator. Do not retry this scope.
- [x] Fresh mechanics run `c47a7dd1-05fb-47fc-bfbe-1ba014ffa77b` completed the full loop without reusing old captures. Local Rust Parlor persisted 180/180 new Responses exchanges with zero drops: 80 train, 50 DEV, 25 calibration and 25 sealed. Summary `1cb3f7e2-0d4b-560a-94fb-fe5635affbe7` classified all 180; readiness `88e43988-181e-5a49-85a4-769085692a44` passed; eval `259e831c-1f20-5e13-b907-d648dbcd8ac3` produced 100 unique split-pure cases; dataset `af6004f0-923e-5abd-977f-ed654f5966c6` fed Baseten job `q89ez53` and model `d0677ba8-b72b-54e1-be3d-49eed424058b`. Dynamic FP8 won three repaired DEV branches and passed sealed evaluation group `0859095f-1c49-550b-b6d2-dcbd93e0acb9`. Modal served candidate `98a5b561-44d7-559c-9311-1b0a76edc345`; Milk Man wrote unsigned proposal `008d3ba1-06f9-53eb-9bb2-d9cd8b10d9ae`; production Parlor then proved signed candidate, pre-byte fallback, and signed zero. This is complete mechanics evidence, not a production-qualified corpus.

## Dashboard/controller proof — 2026-09-03

This path is complete. It does not alter the historical evidence below.

- [x] Launch the local dashboard with only the reviewed environment bindings
  needed by the selected controller and Milk jobs. Show presence or absence,
  never values.
- [x] Send one explicit operator instruction through the existing dashboard
  prompt. The resumed supervised trajectory reads this tracker, applicable
  skills and bounded memory, inspects both repositories, then invokes the fixed
  `inference-status` and, only when needed, `inference-ensure` jobs.
- [x] Stream bounded redacted progress in the dashboard while preserving the
  exact workspace set and trajectory across controller creation. Prove the next
  reasoning turn on that same trajectory reaches the validated controller
  endpoint.
- [x] Invoke `inference-stop` from the supervised trajectory and independently
  observe zero active controller containers.
- [x] Dashboard trajectory `df36b6bc-1651-4f74-aa40-43da7a8a216a` created and
  reached Modal controller `bc78fca753201668b03008141987ea5e56bcc22ecf9e95709e9547894cb11375`
  with the pinned GLM revision, executed real repository and `milk status` tool
  calls, then stopped it from a second dashboard instruction. The retained
  zero receipt reports zero containers, an independent Modal listing is empty,
  and controller pointers are cleared. One unrequested old-scope `eval` call
  failed before inference or provider work because its eval binding was absent.
- [x] Local commit `970cda8e0` keeps interactive trajectory state distinct from
  deterministic jobs and reports the exact active `milk_v2.runner` job counts
  in the dashboard. Live Chrome showed `chat waiting · 3 eval jobs active`
  while the saved trajectory remained available and all cloud/job bindings
  stayed redacted.
- [x] Local commit `136653580` repairs dashboard prompt submission, changes the
  supervised OpenAI driver default to `gpt-5.6-sol` with low reasoning while
  leaving Milk data jobs at max, removes Git subprocesses from the one-second
  local refresh, and opens the first completed summary by default. Live Chrome
  resumed trajectory `df36b6bc-1651-4f74-aa40-43da7a8a216a`; one bounded
  correction recovered from an invalid first answer and accurately reported
  six active `eval` jobs without file, cloud or provider changes.
- [x] Created fresh mechanics scope
  `aeaa9585-74c8-43ea-b6e5-070b60c40619`, deployed its operator-issued key in
  Cloudflare version `4515234c-d762-4be6-816a-d4cda7f3582b`, and sent 104 real
  official-SDK exchanges through the production Parlor. Parlor persisted all
  104 with zero drops or storage failures.
- [x] Audited every stored body before summary inference. One hundred are
  complete request-response pairs in the exact 50 DEV, 25 calibration and 25
  sealed split. Four Responses calls ended `incomplete/max_output_tokens`; they
  remain valid traffic statistics but are excluded from eval-source admission.
- [x] Milk Man classified all 104 captures into summary
  `5b8dd30a-a395-54b5-be20-ffe08a8fc761`; its structural statistics report 104
  parsed HTTP successes, 100 model-completed answers, four incomplete answers
  and zero duplicates. Readiness `f716fe26-12b1-59bd-b8c0-6698d3f1bc6e`
  passed every mechanics check and exposes exactly 100 eligible sources in the
  50/25/25 split. A first capped attempt returned no tool call and wrote no
  checkpoint; the explicit `MILK_SUMMARY_MAX_OUTPUT_TOKENS=32768` binding then
  completed in six inference calls. A replay made zero inference/provider calls.
- [x] Audited the downstream dataset boundary before scaling eval generation.
  The 104-capture summary had zero train-split sources, so its reviewed
  256-case eval shard is retained as historical evidence only. Three disjoint
  workers were stopped before completing another shard; no coordinator or GPU
  job ran.
- [x] Sent two additional official-SDK exchanges through production Parlor.
  Both completed, persisted as captures 105 and 106, deterministically entered
  the train split, and contain nonempty request and response text. Checkpoint
  105 proved the train boundary; checkpoint 106 bound the exact 100-source eval
  policy. Current summary `0630f2fb-6044-59f8-bb41-dcd5de25b876` and readiness
  `9c730aa1-0f1a-5c9a-8e05-9f97d79eb5d7` contain two completed train sources
  plus exactly 50 DEV, 25 calibration and 25 sealed sources. Each incremental
  checkpoint used two inference calls and zero provider lifecycle calls.
- [x] Restricted dataset source admission to model-completed, two-sided text
  captures. HTTP success alone can no longer admit an incomplete response.
- [x] Started the current 10,000-case eval revision
  `a2e501131e6193046276314f72fc310b64ac4b742cff53369d4983c70a4b8f9e`
  (`01959d30-7eb2-54e9-96ed-42824c5e588c`) from checkpoint 106. Directly
  reviewed samples from prepared shards 0–3 were distinct, useful, correctly
  solved and bound to the intended DEV sources. Eight concurrent requests
  produced no rate-limit errors.
- [x] Drained the run without losing work when OpenAI returned
  `credit_balance_exhausted`: prepared shards 0–6 and 38–39 remain immutable;
  shards 7–9 and 34–37 retain their completed attempt-0 batches. Zero eval
  runner, model request or provider-lifecycle process remains active.
- [x] Raised the Milk Infrastructure OpenAI organization monthly spend limit
  from `$120` to `$500`. One exact shard-35 resume then stopped after one call
  with `credit_balance_exhausted`; the live organization credit balance was
  `-$9.32`, so no fan-out started and all retained receipts remain unchanged.
- [ ] Add OpenAI API credits, then resume this exact revision from its retained
  receipts. Do not change prompts, provider binding or case identity.
- [ ] Generate this scope's 10,000-case lineage, then continue through the
  model, proposal, signed-route and zero-capacity proofs.

## Non-negotiable architecture

### Repository and reuse boundary

- The product runtime remains only `milk-parlor` and `milk-man`; `milk-landing`
  is a static presentation surface and never becomes a third runtime.
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
- It stops after evaluation at the provider-selection boundary. Status reports
  the availability and missing environment names for both provider jobs; the
  result says `next: select-route-provider`, and the Milk Man system prompt and
  operator task select exactly one named job.
- When nothing changed, it makes zero inference and provider calls.
- Semantic jobs run a restricted Headlong session with a fixed job-specific system prompt and only `milk job read` and `milk job commit` available.
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
bin/milk run route-propose-baseten
bin/milk run route-propose-modal
bin/milk run gpu-reconcile-modal
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
MILK_TEACHER_BASE_URL / MODEL / API_KEY
MILK_SUMMARY_API_MODE / MILK_EVAL_API_MODE / MILK_TEACHER_API_MODE
MILK_REASONING_EFFORT
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

Candidate-serving jobs additionally bind:

```text
MILK_SERVE_IMAGE
MILK_CANDIDATE_API_KEY
MILK_CANDIDATE_ACCELERATOR
MILK_ROUTE_CANDIDATE_BPS
MILK_ROUTE_TIMEOUT_SECONDS
```

Configuration records environment-variable names, never secret values. The same code must work locally, against R2, and against remote inference/GPU providers by changing bindings only.

The Milk Man system prompt and operator task select one reviewed named provider
job after inspecting status availability. That job resolves only its own
environment binding; the presence of a credential never triggers a provider,
and a provider failure never selects a different adapter.

Job-scoped environments reduce accidental credential propagation; they are not presented as cryptographic isolation from a same-user development shell. Do not build a secret broker for the first version.

## Milk Parlor contract

### Public endpoints

```text
POST /v1/chat/completions
POST /v1/responses
GET  /healthz
GET  /
GET  /status
GET  /api/status
```

Parlor supports only these two OpenAI create routes, including SSE. It does not
claim compatibility with other OpenAI endpoints, WebSocket or Realtime.

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

Baseline and candidate definitions are explicit protocol-native environment
bindings:

```text
MILK_BASELINE_CHAT_BASE_URL
MILK_BASELINE_CHAT_API_KEY
MILK_BASELINE_RESPONSES_BASE_URL
MILK_BASELINE_RESPONSES_API_KEY

MILK_CANDIDATE_A_ARTIFACT_SHA256
MILK_CANDIDATE_A_CHAT_BASE_URL
MILK_CANDIDATE_A_CHAT_API_KEY
MILK_CANDIDATE_A_RESPONSES_BASE_URL
MILK_CANDIDATE_A_RESPONSES_API_KEY

MILK_ROUTE_VERIFY_KEY
```

Candidate routing requires the artifact digest plus at least one complete
protocol URL/key pair. Provider base URLs stop before `/v1`.

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

e/<eval_uuid>/revision.json
e/<eval_uuid>/context.json.zst
e/<eval_uuid>/manifest.json
e/<eval_uuid>/shards/<split>/<first_case_ordinal>-<last_case_ordinal>/cases.jsonl.zst
e/<eval_uuid>/shards/<split>/<first_case_ordinal>-<last_case_ordinal>/validation.json
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

Individual eval-source admission is deterministic and requires:

- parsed text from an HTTP-successful response;
- no tool calls in the source interaction; and
- a request digest unique among admitted sources.

Answerability, safety, outcome, and oracle labels are retained only as metadata
and never gate source admission. An unsupported source oracle is normalized to
a generated reference while preserving the source oracle and its provenance in
metadata.

Do not reintroduce session identity. The threshold unit is one complete gateway exchange containing whatever prior conversation context the client supplied.

Mechanics scopes can become mechanics-ready but can never produce a production-qualified route.

## Eval and model loop

### Eval generation

A ready summary triggers a fixed teacher job selected through `MILK_EVAL_*`.

The generation ratio is explicit:

```text
MILK_CASES_PER_CONVERSATION=100

1 eligible held-out conversation    -> 100 validated eval cases
100 eligible held-out conversations -> 10,000 validated eval cases
```

The versioned split policy first assigns source digests. Only eligible held-out
DEV, calibration and sealed sources expand into eval cases; train sources remain
isolated for teacher training targets. The total is derived from the immutable
source list and `MILK_CASES_PER_CONVERSATION`, never selected independently.
Changing the ratio creates a new revision. Milk Man creates exactly 100 planned
case identities per source at the default ratio, gives the teacher each source's
bounded request and response plus its per-source example index, and asks for a
materially distinct realistic scenario rather than a paraphrase or mechanics
template. The teacher chooses content, not counts, source assignment, split,
identity or storage location.

Milk Man generates cases in bounded batches and writes compressed immutable shards.
`MILK_EVAL_SHARD_CASES` is fixed in the eval revision identity; changing it
creates a new revision. Case IDs, order, and source assignment remain
deterministic within that revision.

Each shard identity binds the immutable eval revision, ordinal range, selected
source digests, and prompt/model/config digests. A repeated `bin/milk operate
--once` resumes at the first absent shard. It never regenerates a completed
shard and never loads or rewrites the full corpus. The final manifest binds the
ordered shard keys, digests, ranges, and counts.
`e/current.json` advances only after the manifest accounts for the exact derived
case count, every source contributes the configured ratio, every input is
globally unique, and every referenced shard digest exists. Generation is
batched model work. JSON-schema output and deterministic identity, lineage,
count, copy, and duplicate checks run locally; bounded operator review makes no
inference call. There is no requirement or design for one inference request per
eval case.

The generation prompt is deliberately generic. The immutable revision retains
the complete deterministic source request/response corpus. Each model
batch receives the current summary checkpoint, its assigned ordinal/source
descriptors, per-source example indexes, and only the source conversations bound
to those assignments. The
selected high-intelligence model spends its output tokens producing synthetic
examples that reproduce the observed task distribution, formats, difficulty,
and failure modes without copying traffic. Code does not encode a
synthetic-data DSL or hand-authored mutation catalog.

Strict tool schemas already enforce JSON fields, types, counts and bounds. They
do not establish usefulness. Before scaling, a model-free corpus audit must
report exact duplicates, repeated normalized prefixes/templates, source
contribution counts, operation/oracle coverage and length distributions. A
bounded operator review of an independently selected sample must establish
correctness, difficulty, diversity and absence of mechanics boilerplate.
Failure leaves the revision unreferenced and stops further paid generation.

The existing four-case mechanics path proves orchestration, training splits,
and GPU execution quickly. It is not evidence that source-proportional cases are
useful at 100-per-source scale. Production traffic and generated mechanics
traffic remain separate scopes.

The first proof is one eligible held-out source expanded into exactly 100 cases,
fully reduced, published and audited. Only after that passes may the same code
expand 100 eligible held-out sources into exactly 10,000 cases. Mechanics
traffic cannot qualify a production route.

The deterministic plan selects:

- 24 representative cases by cycling through populated operation categories and choosing the lowest deterministic hash;
- 8 tails from long, rare, error-prone, tool, multimodal, and low-confidence cells;
- unique source exchanges only.

The generated eval must bind source digests without copying raw source text into
its manifest. Deterministic format and identity checks require:

- exact schema and planned order;
- unique case IDs and inputs;
- valid source and summary provenance bindings;
- no exact duplicate cases;
- no unsupported tool or multimodal requirement; and
- source separation from training data.

Separately, bounded human semantic review of the first complete 100-case corpus
judges material correctness, answerability and reference quality, answer
leakage, and semantic near-duplication before downstream work. Human review is
recorded as review evidence; it is not a deterministic format or identity
check.

The representative/tail selection above determines eligible held-out sources.
Deterministic expansion supplies exactly the configured number of cases per
source while retaining each source digest and category cell. Case IDs are derived
from the eval revision and ordinal so sharding and retries cannot duplicate or
renumber them.

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
  available through `MILK_TEACHER_*`. Eval generation uses its own reviewed
  `MILK_EVAL_*` binding. These roles may
  select GLM or another approved high-intelligence model without code changes.
- Teacher and eval calls never fall back to the 0.8B student or to
  a student-derived endpoint. A missing or failed high-intelligence binding
  blocks that semantic job; it does not silently lower generation quality.
- The cheaper `MILK_SUMMARY_*` binding remains isolated to bounded traffic
  classification. Summary classification output is not teacher training data.

The full whiteboard sequence is:

1. Generate bounded teacher training targets from train sources.
2. Validate and publish one immutable dataset.
3. Launch one Qwen3.5-0.8B training job.
4. Merge the resulting adapter with the exact pinned Qwen3.5-0.8B base revision.
5. In mechanics, produce three candidates:
   - BF16;
   - dynamic FP8;
   - static FP8 using only the calibration split.
   Production omits the prototype static branch and produces only BF16 and
   stable dynamic FP8.
6. Evaluate every eligible branch concurrently on the identical ordered DEV set.
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

- Baseten jobs for post-training, evaluation, and Baseten candidate serving.
- Modal jobs for Modal controller or candidate serving.

`route-propose-baseten` and `route-propose-modal` are separate tool calls with
separate reviewed environment bindings. `operate --once` stops after evaluation;
Milk Man chooses one from its system prompt, operator task, and reported binding
availability, or the operator invokes one directly. Neither adapter calls the
other.

A timeout, disconnect, 429, 5xx, or ambiguous create must reconcile the exact
identity with that same provider before retry. Never create another resource
while the first may exist.

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

Milk Man creates unsigned proposals only. The operator-run `milk-parlor/ops/publish-route.py` holds the private key outside both runtimes.

A signed route contains:

```json
{
  "schema_version": "milk.route.v3",
  "route_id": "<uuidv7>",
  "scope_id": "<uuid>",
  "revision": 4,
  "baseline": "baseline",
  "candidate": {
    "target": "candidate-a",
    "artifact_sha256": "<sha256>",
    "basis_points": 100,
    "protocols": {
      "chat_completions": "<binding-sha256>"
    }
  },
  "valid_from": "<UTC>",
  "expires_at": "<UTC>",
  "signature": "<ed25519>"
}
```

Parlor:

- verifies canonical manifest bytes with Ed25519;
- caches routes independently per scope;
- ignores an invalid or stale replacement;
- routes baseline when no valid manifest exists;
- tunnels Chat Completions and Responses to separate protocol-native baseline bindings;
- considers a candidate only for protocols named and signed in the route;
- selects the candidate deterministically from route ID and exchange UUID;
- retries baseline only before any candidate headers or bytes reach the client;
- never replays after streaming begins;
- treats rollback as a new signed higher revision;
- treats a signed zero route as candidate binding null and basis points zero.

Candidate credentials remain deployment environment bindings. Do not implement hot rotation.

## Status interface

Milk Man serves one local raw HTML/CSS/JavaScript page from `bin/man dashboard`:

- [x] Bind only to `127.0.0.1` and read the current bounded trajectory, memory and exact workspace revisions.
- [x] Accept one same-origin bounded development prompt, resume the exact recorded workspace set, and queue at most one follow-up until an active turn exits.
- [x] Stream a bounded view of the child process into the chat, remove terminal control codes, redact configured secret values and common credential assignments, and explicitly distinguish attached, externally running, detached and missing sessions.
- [x] Reuse `milk_v2.store` and `MILK_SUMMARY_THRESHOLDS`; do not add another object-store client, database, cache or status writer.
- [x] Refresh local Milk Man state every second; read cloud state on page load, the explicit button, and every 30 seconds while visible.
- [x] Probe Parlor's public `/healthz` through optional `MILK_PARLOR_BASE_URL` and show a hardware-style active/degraded/down lamp plus the last-checked time.
- [x] Count durable scoped captures, show equal-width threshold segments for `100,1000,10000,100000` or the configured values, and traverse the bounded immutable summary-parent chain.
- [x] At every completed threshold show parse and success rates, unique and classified counts, latency, throughput, and leading topic, task, sentiment and capability counts.
- [x] Show the remaining eval, dataset, student, winner, candidate and route pointers from `status/current.json` without opening their payloads.
- [x] Apply Susan Kare's design discipline with one monospace face, the original black/white/pink/teal palette, crisp square bevels, tactile controls and compact hardware-like lamps whose fill and rim distinguish confirmed success, missing/error and waiting states; use no gradients, shadows, opacity, ambient motion, extra assets or extra colors. Motion must communicate direct manipulation or changing live state. Iterate from real Chrome screenshots.
- [x] Replace the duplicated static path diagram with one native nine-stop Milk line. Its existing pixel carton thumb moves by drag or arrow key, its stops distinguish completed, selected and pending stages, and selecting a stop opens the same stage disclosure below with the exact job, trigger and record.
- [x] Make the dense page understandable through native `details` and `title` disclosure: label mechanics versus production, explain the next deterministic action and all nine stored stages in plain language, and show each reviewed job's trigger, automatic/manual execution, fixed command, read/write prefixes, prompt, timeout and required/optional environment-name presence—never values. Clicking safe scope/record IDs, fixed commands and environment names copies exact text with inline feedback; use no modal, custom tooltip library or new endpoint. Never imply a prepared candidate is serving, an unsigned proposal is active, or configured credentials prove provider availability.
- [x] Use no frontend framework, package manager, asset request, build step or analytics.

Cloud data remains read only in the browser. The localhost prompt endpoint
starts only the supervised development harness; it is not a generic job API and
does not accept a handler, provider, command, object prefix or environment name
from HTTP. After an explicit operator instruction, that supervised trajectory
may invoke reviewed fixed `bin/milk` jobs through the repository shell; each job
still resolves only its declared environment bindings. The browser cannot sign
or mutate a route, expose environment values, or return raw customer traffic or
semantic samples. Parlor retains its public `/healthz` and authenticated
`/api/status` for remote scope status; a hosted gateway cannot and must not
expose Milk Man's local files or development trajectory.

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

Image release:

- no GitHub Actions run from either repository;
- a reviewed local or external builder publishes only affected `linux/amd64` images with registry-backed BuildKit caching;
- every release records immutable image digests and source revision;
- image building never runs Milk reconciliation, provider jobs, deployment, traffic generation, or paid work.

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

### [x] P0 — Preserve and establish clean repositories

Progress 2026-09-01:

- [x] Verified current Milk Man and Milk Carton revisions and the seven-path M5A4 dirty state.
- [x] Saved and verified complete Git bundles, the dirty patch, and bounded local state under `/Users/shantanu/milk-release-evidence/milk-v2-bootstrap-20260901`.
- [x] Installed this file as the sole active repository tracker and removed the previous `GOAL.md`.
- [x] Reduced Milk Man to 38 tracked files and 5,851 lines, committed the result as independent root `5bcfaeb4fe3733b5962c6b5fc07b152eac827171`, and removed the stale Prime upstream remote.
- [x] Published independent-root default histories. Recorded checkpoints include Milk Man `530235a879c3078623ef2f69e3fb830667a9e496` and Milk Parlor `70dba12f96a12feedf7ed13b605f20d05ebefd23`; the verified local bundle preserves the obsolete history.
- [x] After verifying the retained all-history bundle, removed all 55 obsolete `origin/codex/*` branches; `origin/main` is now the only remote branch.
- [x] Detached Milk Man from the GitHub fork network through the signed-in repository control. Real Chrome now shows a standalone public repository with no upstream fork label or ahead/behind controls; `main` remains the Milk-owned root history and `origin/main` remains its only remote branch.
- [x] Disabled repository Actions, removed its obsolete 21-secret provider environment and GHCR publishing secret, removed Wiki and Projects, retained public issue/PR creation, selected squash-only merges with automatic branch cleanup, and restricted direct `main` updates to `ShantanuJoshi` without status checks.

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
- [x] A later local `gpt-5.6-sol` low-effort Milk Man run loaded this tracker and `milk-system`, inspected both current repositories and their diff, made no speculative edit, and identified P0/P10 as the remaining phases.
- [x] A fresh local `gpt-5.6-sol` max-reasoning trajectory recovered from an overlong read-only attempt, reviewed exactly the requested three-file diff, ran narrow syntax and diff checks, and retained commit `12984457a` in two turns without invoking a Milk job or cloud provider.
- [x] The development system prompt is under 1 KB, the 93 KB tracker is no longer injected, automatic trajectory and memory context default to 32 KB and 4 KB, and the direct OpenAI driver defaults to `gpt-5.6-sol` at maximum reasoning. A supervised Milk Man trajectory reviewed, corrected, checked, and committed the seven-file v24 change as `f0977e738`.
- [x] A dependency-free local dashboard now shows bounded Milk Man trajectory activity, memory, exact workspace revisions, and the object-memory pipeline. It binds only to `127.0.0.1`, reuses `milk_v2.store`, performs one read of `status/current.json`, and exposes no environment values. Milk Man reviewed and committed the implementation as `203fab30e`; the browser proved working-to-idle state changes and live R2 counts.
- [x] The localhost dashboard accepts a bounded prompt for the exact recorded workspaces and can hold one follow-up until the active turn exits. A live browser run moved from idle to working to idle, read both repository revisions in one maximum-reasoning turn, and made no file, job, provider or cloud changes.
- [x] Real Chrome validated the localhost dashboard at `127.0.0.1:8766`: native disclosure preserved open sections across refresh; safe IDs, fixed commands and environment names provided inline copy feedback; no environment value, raw traffic, provider-liveness claim or route-authority control appeared. The page clearly distinguished working, ready and setup states while cloud status remained read only. The public dashboard and tightened development prompt are published at `a0ec22b77`.
- [x] The foreground dashboard is now the persistent local Milk Man supervisor. A server-side watcher refreshes gateway health, the small saved object-store status and reviewed job-environment presence without a browser; exact capture inventory remains an explicit refresh so idle cost does not grow with the corpus. The chat stays connected to the saved trajectory while bounded model turns move through working, queued, failed and idle states. A five-second localhost smoke observed two independent watcher timestamps and a failed unconfigured turn returned to an online supervisor without making an inference call.
- [x] Real Chrome moved the native Milk line from stage 01 to stage 04, opened the exact eval-stage disclosure, exposed its fixed trigger, preserved that selection through an explicit status refresh, and emitted no browser warning or error. The dependency-free control and updated public screenshot are published at `8d2d9dd31`.
- [x] Public onboarding now states the exact product boundary on the landing page, dashboard, and README: applications keep the official OpenAI SDK, change only the Parlor base URL and Milk key, and use the supported Responses or Chat Completions routes. The local dashboard shows only the latest turn, reports the live Parlor writer, readable object memory, job readiness and environment-name presence, and keeps values hidden. The development prompt and `milk-system` skill now make a specific task take precedence over tracker ritual and forbid repeated unchanged reads.

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

- Prime, persistent thinkers, messaging, remote dashboard controls, deployment, provider jobs and production scheduling.

### [x] P2 — Milk Parlor direct request path

Progress 2026-09-01:

- [x] Created the fresh Rust repository at root `d089c46c3255b76bbf4ae40774d41aae5681a0bf` with no legacy code; `70dba12f96a12feedf7ed13b605f20d05ebefd23` is the initial published checkpoint and `216c27231dece763aa86812e6105012d88bf3285` is the current deployment commit.
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
- [x] Replaced the single ambiguous upstream binding with native Chat Completions and Responses bindings. Local direct smoke routed Chat to Baseten and Responses to OpenAI without translation; each returned the requested output and advertised only its configured protocol.
- [x] Actions run `33597630523` built the locally verified protocol-native source into GHCR index `sha256:6d2726586116de52ce0372aa67d7a1144f9fcd0401ba46f8e563d7d0aeac385d`, Linux AMD64 manifest `sha256:f8caebc7c0bf2d8b24809c72cbba1f97165245022caa9c1e6a9b4c1c0aa5ed39`, and Cloudflare manifest `sha256:50d8901bc8a4a4172bc9dcaa8014d836d6d596d25bfd5b41fbeb340dcc6d510d` with 2,342,654 compressed layer bytes.
- [x] Deployed that exact Cloudflare manifest. Native streaming Chat reached Baseten and native streaming Responses reached OpenAI through signed zero route revision 5; both completed and persisted without a candidate binding.
- [x] A fresh scope accepted and asynchronously persisted exactly 100/100 official OpenAI Python SDK Responses exchanges in 23,361 ms with eight clients, zero drops, zero storage failures, and a live writer. This proves the requested small-threshold path; no capture-overhead number is claimed, so an artificial enabled-versus-disabled benchmark is not a completion gate.
- [x] Retained protocol-native proof at `/Users/shantanu/milk-release-evidence/milk-v2-protocol-native-20260902/report.json`, SHA-256 `7c988ce858176a2cd57a9c846ccb490bfd949b331a1793c3fecf8c627f64503d`.
- [x] Parlor commit `02ec39593504b3fefe495acaebbcd1a9a44831cb` documents the customer contract without inventing a Milk SDK: official Python and JavaScript OpenAI clients use `https://parlor.milkinfrastructure.com/v1` plus an operator-issued Milk key; Parlor claims only native Responses and Chat Completions compatibility. The local dashboard shows the same request, streaming, asynchronous capture, object-memory and Milk Man path.

Owned:

```text
src/main.rs
src/store.rs
Dockerfile
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
- [x] Configuration accepts only eleven reviewed handler identifiers and reviewed environment-variable names; it cannot introduce an executable path.
- [x] All eleven reviewed handlers are implemented. `operate --once` deterministically advances through evaluation and stops; status exposes both provider jobs and their missing environment names, the system prompt or operator selects exactly one, and explicit `gpu-reconcile-modal` records Modal teardown and zero capacity.
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
- [x] Crossed the first production threshold at 100 complete R2 captures through local Milk Man using `gpt-5.6-sol`, the OpenAI Responses API, and low reasoning effort. It wrote one summary/readiness checkpoint in two inference turns, replayed with zero calls, and correctly remained below the 1,000-capture readiness threshold.
- [x] Used the same latest-model/low-effort OpenAI binding to generate a bounded 12-prompt follow-on batch, sent it through hosted Parlor, and reconciled 112 captured / 100 processed with zero new inference or provider calls.
- [x] Retained the content-free production summary receipt at `/Users/shantanu/milk-release-evidence/milk-v2-production-openai-summary-20260902/report.json`, SHA-256 `fcb786f4c0fd662c8ca27bc15fbfe916e51e117f3f0510709dbf2d553bd1011b`.
- [x] On fresh scope `c2ab9c16-79cc-4c7f-955d-49871f240919`, local Milk Man read 100 hosted Parlor captures from Cloudflare R2 with `MILK_SUMMARY_THRESHOLDS=100`, used `gpt-5.6-sol` through OpenAI Responses at low reasoning effort, and wrote summary `df553599-5026-507d-b9b5-6d53ea015971` plus readiness `bd464e56-893a-5cac-a94d-b9f4bff170f3`. The two-call run was mechanics-ready, explicitly not statistically qualified, and its replay made zero inference/provider calls.

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
- [x] Repeated the complete hosted-gateway-to-remote-store-to-local-Milk-Man vertical at an explicit threshold of 100 after the coordinated image build. The same environment-selected R2 and OpenAI bindings advanced summary, eval, and dataset pointers; each immediate replay made zero calls.

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

### [~] P7 — Eval generation

Completed 2026-09-01:

- [x] Added exact request/response digests, the fixed request-digest split policy, exact split quotas, and split-aware readiness restricted to locally scoreable exact, reference, and schema oracles.
- [x] Added deterministic distinct-source representative/tail planning, restricted generator and independent validator sessions, bounded resumable top-up, immutable job/eval artifacts, and guarded `e/current.json` advancement.
- [x] A direct mechanics `milk operate --once` smoke traversed capture, summary, readiness, eval, validation, and `e/current.json` in six inference turns; replay made zero calls.
- [x] A separate rejection smoke proved one validator rejection, one repair, acceptance in ten turns, zero-call replay, and `milk status` advancing to `dataset`.
- [x] Published `672b58cbe` and `3ec05028f`; the pinned Qwen3.5-0.8B student contract and separate high-intelligence eval/validator bindings remained intact.
- [x] The fresh threshold-100 R2 scope generated and independently validated eval `eee146fd-d026-59dd-ac6d-4d44a2c04613` through separate OpenAI Responses bindings using `gpt-5.6-sol` at low reasoning effort. It accepted one bounded case in eight inference calls, made zero provider calls, and replayed with zero calls.
- [x] The sharded implementation generated and validated eval `bdc67d24-36e5-5e9a-a90c-1d5a28c30013` against the same live R2 scope: exactly eight cases in three split-pure shards, resumable accepted-only repair, an immutable cumulative uniqueness ledger, and guarded current-pointer publication. Dataset `e9b7f5c7-9fac-56cd-b247-feb64b5e092c` then referenced exact held-out counts DEV 4, calibration 2 and sealed 2 while writing one train row; it used two teacher calls and zero provider calls.
- [x] The abandoned v21 100,000-case eval `d388a759-f5b2-5927-966e-bcf4ad974469` is stopped historical evidence, not current work. Its first 256-case DEV shard had completed with ten OpenAI inference turns, zero provider calls, and immutable cases, validation, and ledger objects before the run was abandoned.
- [x] Proved production-scale parallel generation against the same live R2/OpenAI bindings. Distinct precompute workers prepared ordinals `0..255` and `256..511` for eval `23faf45b-13a8-5d06-bffd-c8fbf7735374` without touching shared progress; the ordinal coordinator committed both shards, advanced the cumulative ledger to 512 unique cases, reused the first shard with zero inference, and regenerated only two real cross-shard collisions on the second. Generation and validation made zero GPU/provider calls.
- [x] Extended that immutable historical scale proof to a contiguous 2,560-case DEV prefix across ten shards. Four-way precompute was stable after adding bounded SigV4 transport retries; the coordinator never skipped an ordinal, reused globally unique prepared shards with zero inference, and regenerated 47 exact normalized collisions across seven shard reductions. The measured repair cost used only the pending cases' source conversations. A separate ordinal-diversity prompt experiment was rejected after producing 96 vacuous cases in one shard and never advanced shared progress. Eval v7 is historical and not authoritative; rejected v22 artifacts are not the current lineage; Eval v24 is current.
- [x] Historical v14 scale proof `c9f2d98a696bb40493d4d5de324ee9b0b7e5f2ab5583f18d474d3222e75e207e`, eval UUID `454efa61-1f99-5133-950e-75009bcde6e5`, prepared and coordinated the first 512 cases. Its retained receipts contain 1,723,691 input and 92,512 output tokens across 63 inference requests; at current uncached list rates this completed proof is approximately $0.31. It remains the visible 512-case pointer until the current revision is coordinated.
- [x] Stopped v21 revision `4087cdace336000e95e61ca1cdfdd6313a280c4d6f14b2e43c882e780f051596`, eval UUID `0940bb40-3cc0-5aea-b0c1-f5244ccadf65`, after the quality audit above. It remains immutable mechanics evidence and must not be resumed or promoted.
- [x] OpenAI Responses generation stopped with `credit_balance_exhausted`. This was account credit exhaustion, not throttling and not a Milk code or object-store failure. The stopped v21 run then used the separate environment-selected Baseten `zai-org/GLM-5.3-Flash` binding.
- [x] A four-worker Baseten precompute pilot returned genuine HTTP `429` responses. It launched no GPU lifecycle work and advanced no shared pointer. Three concurrent precompute workers are the observed stable ceiling for this run; do not retry with four.

- [x] Retained Milk Man commits `0458a82b9` and `056cc1143` as the self-recovery/completion-protocol proof: the former hardens agent completion and the latter keeps task context bounded across recovery.

Active source-proportional execution sequence:

1. Select the exact deterministic eligible held-out source count from `MILK_EVAL_SOURCE_CONVERSATIONS`, then derive split counts and total cases from that list multiplied by `MILK_CASES_PER_CONVERSATION`; remove `MILK_EVAL_TARGET_CASES` and all target-equals-100,000 branches.
2. Bind the ratio, exact per-split source counts, per-split case counts and per-source example index into the immutable revision and generated case provenance.
3. Run one eligible source through exactly 100 generation, deterministic local checks, global reduction, final manifest, operator review and zero-call replay. Do not start parallel workers for this proof.
4. Audit the final 100 cases for exact and repeated-template duplication, correctness, difficulty, operation/oracle coverage, boilerplate and source leakage. Record only aggregate/redacted evidence.
5. Before another fan-out, run 100 eligible held-out sources serially at one case per source and continue that smaller lineage through the full job stack.
6. After the smaller lineage proves every layer, scale the same implementation to 100 cases per source with one coordinator owning the cumulative uniqueness ledger.

- [x] Prove one eligible held-out source produces exactly 100 schema-valid, globally unique, lineage-bound cases and a zero-call replay. The current one-source v24 maximum-reasoning proof produced 100 structured cases with four inference calls, zero provider lifecycle calls and a zero-call replay; bounded human semantic review found 98 materially correct cases and two known semantic errors.
- [x] Prove 100 eligible held-out sources can advance serially without fan-out. Scope `8cc33bba-6790-4701-8a88-b3ba565971ee` produced eval `7351474f-dd59-57d6-af1d-c6ca4c986ef0`: exactly 100 unique cases in split-pure DEV 50, calibration 25 and sealed 25 shards, using 14 maximum-reasoning OpenAI Responses calls and zero GPU lifecycle calls.
- [x] The fresh post-fix scope produced eval `259e831c-1f20-5e13-b907-d648dbcd8ac3` with the same exact 50/25/25 split and one case per source. A read-only review of all 50 DEV cases found all useful, no answer leakage or substantive duplicates, and 45 correct as written; five bounded reference defects keep this mechanics-only rather than production-qualified.
- [x] On fresh scope `aeaa9585-74c8-43ea-b6e5-070b60c40619`, revision
  `08db51d03effb7bf1287caf66a6d79b9e52bbeec5214ec92fc0a10dae25a21b1`
  prepared its first 256 DEV cases in one attempt and ten maximum-reasoning
  inference calls. All 256 prompts and prompt-answer pairs are unique, none are
  empty or expose mechanics text, and bounded review found useful planning,
  classification, extraction, transformation and quantitative tasks. Exact
  replay made zero inference/provider calls. The revision is historical because
  its source summary contained no train example; the checkpoint-105 lineage
  replaces it.
- [ ] Prove 100 eligible held-out sources produce exactly 10,000 useful cases with exactly 100 cases bound to each source.

The prerequisite full-stack mechanics lineage is complete. Run the 10,000-case proof only on a fresh scope and revision; never resume the rejected historical fan-out.

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
- strict structured output and deterministic local checks pass; a bounded operator review accepts the corpus;
- replay performs no duplicate teacher call;
- `e/current.json` advances only after the complete validated revision.
- semantic workers receive only the next strict `milk job read` or `milk job commit` function; Milk Man exposes status separately, and neither surface can select storage or provider authority.

### [~] P8 — Dataset, training and three evaluation branches

Current downstream status and historical bounded-mechanics proof:

The fresh scope produced its own Qwen3.5-0.8B training result, comparable branches, deterministic winner, and sealed result. The larger production-qualified corpus remains a separate completion requirement below.

- [x] The fresh v24 eval produced dataset `bdc34bb8-f431-507c-a5fd-8b65d0d39310` with exact counts train 1, DEV 50, calibration 25 and sealed 25. The maximum-reasoning teacher used two OpenAI Responses calls; no GPU lifecycle call occurred.
- [x] Milk Man completed Baseten H100 training job `w7x9xy3` for the exact pinned Qwen3.5-0.8B base and current v24 dataset, publishing model `6c89d849-62e7-5f79-9526-2ad4a619f142`.
- [x] Milk Man launched the v24 DEV comparison on the same 50 ordered cases: BF16 job `qrv4v03`, dynamic-FP8 job `qzylyxw`, and mechanics-only static-FP8 job `qjklkp3`. All three terminated at the same stale validation-record check before model inference. The minimal schema repair is published; the fresh scope will exercise it under new job identities.
- [x] Fresh dataset `af6004f0-923e-5abd-977f-ed654f5966c6` has exact counts train 1, DEV 50, calibration 25 and sealed 25. Baseten H100 job `q89ez53` trained model `d0677ba8-b72b-54e1-be3d-49eed424058b` from pinned `Qwen/Qwen3.5-0.8B@2fc06364715b967f1860aea9cf38778875588b17`. BF16 `wg8opjq`, dynamic-FP8 `w61xv5q`, and mechanics-only static-FP8 `w5j69p3` completed with zero errors on identical DEV cases. The checked-in policy selected dynamic FP8 at 867 mean score, 132 ms p95 and 481.577 tokens/second; sealed job `qko7gl3` completed at 839 mean score, zero errors and 264 ms p95. Evaluation group `0859095f-1c49-550b-b6d2-dcbd93e0acb9` is final, and a fresh Baseten inventory found every job terminal, no active jobs and no Milk serving model.

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
- [x] Historical pre-refactor mechanics: candidate artifact `04f4af2eb8b2596985a4694d1a167ea99c66063b19438425199d76bf1c2e8fbd` received a definite Baseten `custom_base_image_not_enabled` preflight with no Baseten model or deployment, after which the old combined job launched Modal app `ap-pf5pYKvKgMMo5SqEyx9ZF6` and volume `milk-candidate-04f4af2eb8b2596985a4`. This is retained evidence, not the current provider-selection contract.
- [x] Milk Man verified the exact Baseten checkpoint inventory during Modal hydration, completed one authenticated inference smoke, retained candidate `40ee1fff-303c-5a5e-842c-72ee9880638d`, and advanced to corrected unsigned proposal `d86f2910-9ccc-5d56-9aeb-ee7b400f4f8c` at `p/d86f2910-9ccc-5d56-9aeb-ee7b400f4f8c.json`.
- [x] The former `milk run gpu-reconcile` command stopped the exact Modal app and wrote immutable intent/result objects under `j/gpu-reconcile/04f4af2e...`; independent listings showed that app stopped with zero containers, every other visible Modal app at zero containers, zero Baseten candidate models, and training job `qek7jrq` in `TRAINING_JOB_COMPLETED` with checkpoint sync `COMPLETED`. The current explicit command is `gpu-reconcile-modal`.
- [x] The fresh threshold-100 scope generated dataset `fe2c3e54-d15c-5c01-ab02-f61b46b9dd93` through the environment-selected OpenAI Responses teacher. Its manifest SHA-256 is `39a8f997e39d4349fb1f7ae5efcd6f1a6c8d11654809315ab510e1ff922603ef`; the bounded mechanics split contains one train and one DEV item, made two inference calls, made zero provider calls, and replayed with zero calls.
- [x] A pre-provider train invocation read and verified the immutable manifest's exact split counts, detected empty calibration and sealed splits, changed status back to `next: summary`, and returned idle with zero inference/provider calls without requiring Baseten credentials. Direct status reports `training_ready: false`.
- [x] Coordinated Actions run `33597613364` rebuilt the weight-free train, eval, and serve images from published Milk Man `87376d56096cf39988d6163d5752a7726acfc3a2`. Their immutable digests remain `sha256:93f6a973d2e7b04e3dfc0c9807b5b83cb661601ebfbc1e371659b2530a9dd16f`, `sha256:7d045e6432b2e6222a58b976889b8c0b4f548a55525826932ae3b435cf7f6343`, and `sha256:5d265b975920f049775e16f959b6fe5177c4c5429ab66eca6bf178d0a892f851`; model weights remain outside OCI.
- [x] Audited all 15 Baseten H100 jobs from provider logs: nine completed, six failed, and none remain active. The resolved failures were one Transformers/Qwen import, one checkpoint-root error, three missing-compiler failures, and one TorchAO inference-tensor failure. `checkpoint_sync: COMPLETED` also appeared on failed jobs and is therefore not treated as job success. The final two-DEV/one-sealed result remains mechanics evidence only.
- [x] The two successful train jobs used the same short train object but different behavior-affecting configurations (`max_tokens` 512 versus 2048 and different configuration digests). Their identical loss and weights do not justify weakening the idempotency identity; future milestones must freeze reviewed settings rather than deduplicate raw bytes unsafely.
- [x] Retained the combined threshold-100/101 proof at `/Users/shantanu/milk-release-evidence/milk-v2-threshold100-openai-20260902/report.json`, SHA-256 `4a839fc1ca14b2c29c0fa7f0b357978e781e14299e34aac22f2a229d72efb5ba`, and the content-free Baseten log audit at `/Users/shantanu/milk-release-evidence/milk-v2-baseten-log-audit-20260902/report.json`, SHA-256 `958bf46d4047440670b11527c997138902d6daf26bb8ba8e0062f69312246a54`.
- [x] Corrected the mechanics default from one eval case, which can never populate every evaluation split, to four deterministic cases. Capture 101 produced a new readiness checkpoint, eval `bc52afeb-ed92-5ead-a899-9c284be20f80`, and training-ready dataset `8ded3d52-267f-5f83-8720-12e7dd994138` with exact counts train 1, DEV 2, calibration 1, sealed 1. The dataset job used two OpenAI teacher calls and zero GPU/provider calls.
- [x] Continued that exact 101-exchange R2 lineage through Baseten training job `31e2jgw`, model `4a71ef5f-41d7-5d6f-ae70-1eabc539313b`, three concurrent DEV jobs `q4zo293`, `3m7l8k3`, and `q89opd3`, BF16 winner, sealed job `32v2d9q`, and evaluation group `e379512d-2a32-5ac1-93b8-1bcd607e6213`. The explicit Modal job reused app `ap-7rNqluqdixBxzCzGhiIkwY`, passed authenticated candidate inference, wrote candidate `a27a19e7-54fd-511f-a6b3-8924a7287484` and unsigned proposal `09588041-f3a2-5d56-9f3c-cf8419cd904f`, then stopped with zero containers. A fresh Baseten listing also reported zero active jobs. This remains mechanics evidence.

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
  teacher binding; no teacher or eval call falls back to the student;
- train, merge and all three candidates bind the exact pinned
  `Qwen/Qwen3.5-0.8B` revision and weight files never enter OCI;
- one real Baseten train/merge job;
- one separately invoked Modal candidate-serving proof;
- identical ordered DEV inputs across all branches;
- code-selected winner;
- one sealed evaluation;
- unsigned proposal;
- termination receipts and independently verified zero capacity on both providers.

### [~] P9 — Signed routing and release

Current fresh mechanics routing proof and historical capability evidence:

The fresh scope now has its own unsigned proposal and complete operator-signed live proof. Production qualification still requires independent customer traffic and the larger corpus defined below.

- [x] Milk Man hydrated the exact fresh dynamic-FP8 winner into Modal app `ap-4DFfHJ1g3QiDFyEiyfeQKX`, passed authenticated health and Chat Completions smoke, and retained candidate `98a5b561-44d7-559c-9311-1b0a76edc345` plus unsigned proposal `008d3ba1-06f9-53eb-9bb2-d9cd8b10d9ae`. Production route revision 6 (`637b9b96-6fcd-4924-a9b0-e50bb01f62cf`) returned model `milk-qwen3.5-0.8b-dynamic-fp8`; R2 capture `01a065c2-2acc-7e60-a8e8-0dbfdc036b84` binds the exact candidate with no fallback. After Milk Man stopped the app, capture `01a065c3-0023-78b1-88e5-c207a45cc547` records pre-byte `candidate_status_503` fallback to the OpenAI baseline. Signed zero revision 7 (`9f4daccd-2cf8-4203-8c57-61dda43fdf9b`) then returned baseline with no candidate or fallback in capture `01a065c4-84a5-7f21-b3c0-0ebe6b53c7fa`. Final Cloudflare version `d9a9efb8-1cb9-4617-8004-b2e9bc766937` contains no candidate secrets or bindings. The official OpenAI SDK authenticated through that final version, returned `sdk` from native Responses, and produced R2 capture `01a065c8-6aff-7712-8258-d23d95f50565`; Modal reports zero Milk containers, Baseten reports zero active jobs and no Milk serving models.

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
- [x] Published Parlor `f0b476b1a7c41ae3b0c7739aeadb06e82b3bcb0e` and Milk Man `7b528a60c3137d5c7c7a033691383c043de7bcfd`: route v3 signs protocol-specific upstream bindings, Parlor forwards `/v1/chat/completions` and `/v1/responses` unchanged, and Milk Man proposes only protocols its candidate actually implements. There is no cross-protocol translation or legacy route reader.
- [x] Signed zero revision 5 (`199226cd-4720-4b8d-9ff3-40f3e32a091e`) is the active production route. Final Cloudflare deployment `becfa07c-be0e-4b71-b431-6ebfc685c38a` runs the coordinated image with separate native Chat and Responses bindings and no candidate credentials.
- [x] Published concise public READMEs and standard license/security/contribution files. The tracked trees contain no legacy names, fixtures, transition documents, GitHub Actions, or model weights. Future images are built by the reviewed local or external builder and keep model weights outside the image.
- [x] Tagged Milk Parlor runtime release `v0.1.0` at `642e3a26ebd921bafed5eb3ff26ccd34f0e0ea51` and Milk Man release `v0.1.0` at `87376d56096cf39988d6163d5752a7726acfc3a2`. Parlor deployment commit `216c27231dece763aa86812e6105012d88bf3285` pins the resulting Cloudflare digest without triggering another image build.
- [x] Published the corrected dashboard image from Milk Parlor `f8752b8c4621e9a4b785acc808de6f575267b343`, pinned Cloudflare digest `sha256:7311ba8e6021f9c24277ad35ee5e6aeddc78e944e859ca4df0e933518a0e335e` at deployment commit `9b59d173d8ffa39e1d480315e03b59039fb90fe8`, and cut over to instance generation `parlor-20260902-f875`. Live health reports 101/101 captures persisted with zero drops; the dashboard key authenticates scope `c2ab9c16-79cc-4c7f-955d-49871f240919`, and the live dashboard now labels the unsigned artifact as a route proposal.

Owned:

```text
milk-parlor route polling/fallback
milk-parlor/ops/publish-route.py
direct official-SDK smoke
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

### Follow-up — Remove measured provider startup waste

Progress 2026-09-02:

- [x] Provider logs show the current Baseten compatibility path repeatedly installs apt and Python packages before a one-step job. This dominates the useful mechanics work and is the largest measured remaining latency and failure surface.
- [x] Historical GitHub Actions runs published immutable weight-free train, eval, and serve images; model weights remained separately mounted. Repository-hosted Actions are now deleted, and future image publication uses the reviewed local or external builder.
- Known limitation: the published digest-pinned images are anonymously pullable from GHCR, but Baseten still rejects them because account-level custom-base-image access is disabled. The local fixed Baseten jobs temporarily use the previously proven pinned CUDA base plus digest-verified source. This reintroduces per-job package startup but does not block the proven system loop.
- [x] TorchAO 0.18 still lists dynamic FP8 as stable but keeps static activation FP8 under `prototype`. Do not replace the known mechanics implementation with another unstable API or use its tiny-set result for production; BF16 and stable dynamic FP8 remain production candidates until a stable calibrated static path exists.
- [x] The reviewed evaluation policy runs all three comparable DEV branches in mechanics but only BF16 and dynamic FP8 in production, so a prototype static job cannot block or win the production path. The chosen branch is bound through the sealed result, candidate artifact, direct-image Baseten config, separately invoked Modal job environment, server health, and smoke identity.
- [x] Direct local payload smokes verified one-command train/eval startup, external Qwen3.5-0.8B weights, prior-checkpoint loading, zero runtime install commands, dynamic-over-static production selection, all-branch serving environments, and static-only activation-scale propagation.
- [x] Train and evaluate now resolve only store and Baseten bindings. Modal credentials enter only the explicit controller, candidate-serving, and GPU-reconciliation jobs that use them.
- [x] Actions run `33604701119` completed successfully for source `a3cd3c24c7924ebe3d0d35e7fc8c1754288a8925` and published the coordinated train, eval, and serve images at digests `sha256:93f6a973d2e7b04e3dfc0c9807b5b83cb661601ebfbc1e371659b2530a9dd16f`, `sha256:04f337317515b94972273534491cbd533bbeebb399a13386ec2bb9aae4acf4e0`, and `sha256:e0e0afae1f70cc0a0f7e920440a27a40a364f5279196c5af34de471101d95524`.
- [x] A direct Baseten invocation bound the exact training image and ready dataset `8ded3d52-267f-5f83-8720-12e7dd994138`, then failed before provider-job creation because custom base images are not enabled for the organization. A fresh provider listing found zero active training jobs; do not retry until Baseten changes the account capability.
- [x] Published `3aaf1dd22e86ea8fc11d7512c92dd5070af7e83c`: Baseten and Modal candidate serving are separate env-bound jobs selected by Milk Man or the operator. Neither job invokes the other, and `operate --once` stops at `select-route-provider`.
- [x] Retained the content-free build/provider receipt at `/Users/shantanu/milk-release-evidence/milk-v2-direct-images-20260902/report.json`, SHA-256 `0824cbe24ca069b06bee966dae8dc8271f203aa8daa7e900c18b592e52d43386`.

Acceptance:

- Baseten starts the exact reviewed image without runtime package installation;
- one bounded train and three-branch evaluation complete from those images;
- configuration identity, dataset/model provenance, and zero-capacity checks remain unchanged;
- any static FP8 production candidate uses a stable pinned implementation; otherwise it remains mechanics-only and cannot win a production route.

## Validation policy

Do not create a fixture-heavy test program.

Use only:

- `bash -n` for shell entrypoints;
- Python compilation/import check for fixed job modules;
- `cargo check` before cloud build;
- one reviewed local or external image build;
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
- GitHub Actions;
- self-signing, self-merging or self-deploying development agents.

## Completion definition

The goal is complete only when:

- Milk Man runs locally, reads its goal/skills/memory, self-edits either repository, resumes, and retains a reviewed commit.
- Milk Man provisions GLM-4.5-Air-FP8 on Modal and then uses that endpoint for its own next reasoning turn.
- `parlor.milkinfrastructure.com` accepts an operator-issued key through the official SDK and asynchronously writes exact two-sided traffic into R2.
- Local Milk Man consumes the remote store through environment bindings; an external scheduler may invoke the same one-shot command without changing its behavior.
- Production-like traffic progresses through summary, classification, readiness and validated eval generation.
- One eligible held-out source proves the audited 100-case mechanics path before scale; 100 eligible held-out sources then produce a resumable, schema-valid, deterministically checked and operator-audited 10,000-case corpus with exactly 100 cases per source.
- The full whiteboard model loop produces a trained Qwen3.5-0.8B student from
  maximum-intelligence teacher data, three comparable branches, deterministic
  winner, sealed result and unsigned proposal.
- Operator-signed routing proves candidate success, pre-byte fallback, rollback and signed zero.
- Baseten and Modal both end at verified zero active GPU capacity.
- Both repositories are minimal, published, documented and free of the old Prime/Carton control-plane bulk.
