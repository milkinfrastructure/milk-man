# Milk Infrastructure product contract

This file defines the product. `GOAL.md` defines the current execution outcome.
`goal_tracker.md` records evidence and remaining work.

## Product promise

Milk turns completed model traffic into scoped object memory, useful summaries,
evaluation data, a trained small-model candidate, and an operator-approved route.
An application keeps the official OpenAI SDK and changes only two settings:

```text
OPENAI_BASE_URL=https://parlor.milkinfrastructure.com/v1
OPENAI_API_KEY=<operator-issued Milk key>
```

Milk currently supports `POST /v1/responses` and
`POST /v1/chat/completions`, including streaming. It does not claim the entire
OpenAI API and does not require a Milk SDK.

## The two loops

```text
Product loop

official SDK -> Milk Parlor -> configured model -> response to application
                    |
                    +-> completed request + response -> object memory
                                                        |
                                                        v
Milk Man -> summary -> readiness -> evals -> dataset -> Qwen3.5-0.8B
                                                        |
                                                        v
                compare versions -> candidate -> unsigned route proposal
                                                        |
                                                        v
                 operator signature -> canary -> fallback -> rollback -> zero

Development loop

human -> local Milk Man dashboard -> bounded reasoning trajectory
                                      |
                                      +-> named Milk jobs
                                      +-> inspect/edit Milk repositories
                                      +-> narrow check and reviewable commit
```

The loops share code and object memory, not authority. Development reasoning
may edit code and invoke reviewed jobs. It cannot silently push, deploy, merge,
sign a route, or select a credential.

## Components and ownership

| Component | Owns | Must not own |
| --- | --- | --- |
| `milk-parlor` | Key authentication, protocol-native proxying, streaming, bounded asynchronous capture, signed-route verification, pre-byte fallback, process health | Summaries, thresholds, jobs, model training, provider lifecycle, user database |
| `milk-man` | Local harness, trajectories, skills, memory, deterministic jobs, object traversal, summaries, evals, datasets, training/evaluation adapters, candidate proposals, local dashboard | Customer request serving, route signing, implicit deployment authority |
| `milk-landing` | Static public explanation and developer guide | Credentials, customer data, job execution, runtime control |
| Object store | Durable scoped data, lineage, job receipts, and current pointers | Computation, scheduling, secret storage |
| Human/operator | Keys, provider accounts, merges, deployment, route signatures, production qualification | Routine deterministic data processing |

There are two runtime repositories and one static site. Do not add a fourth
repository or another runtime service to coordinate them.

## Milk Parlor

### Authentication and routing

`MILK_KEYS_JSON` maps a SHA-256 digest of an operator-issued bearer key to a
canonical scope UUID, profile (`mechanics` or `production`), and the trusted
route revision when required. Parlor never stores or logs the bearer key.

Chat Completions and Responses have separate baseline and candidate URL/key
bindings. Parlor never translates one protocol into the other. A production
route is accepted only when its canonical JSON, object digest, scope, revision,
validity interval, candidate identity, and Ed25519 signature all verify.

Candidate traffic may fall back to the baseline only before candidate response
bytes are exposed. Missing or invalid routes use the baseline. Rollback is a
higher signed revision. A signed zero route removes candidate exposure.

### Response and capture path

Parlor forwards the supported request body, path, query, and relevant headers;
only authority, host, authentication, and route selection change. It streams
the upstream response to the application.

For every eligible completed authenticated exchange, Parlor attempts to enqueue
one bounded request/returned-response copy. Zstandard compression and object
storage occur after the response path. Queue pressure, oversized bodies,
disconnects, or storage failure drop the capture and increment counters; they
do not fail a customer response. The request path never waits for R2.

Initial behavior captures every eligible completed exchange. If storage or
privacy cost later requires traffic sampling, add one deterministic
environment-selected decision before capture allocation. Do not add a sampling
service or semantic logic to Parlor.

The authoritative capture key is:

```text
milk/v2/scopes/<scope_uuid>/c/<exchange_uuidv7>.json.zst
```

The envelope binds exact received request-body bytes and exact returned-response
bytes by length and SHA-256, along with endpoint, status, safe headers, route,
fallback reason, timing, completion, profile, and scope. Never store
authorization, cookies, or arbitrary proxy credentials.

Start with one named Cloudflare container. Add a fixed pool or scope sharding
only after a warm saturation measurement demonstrates the need.

## Object memory

The scope UUID is the root identity. Folder-like keys form the traversal index;
parent UUIDs and content digests form the lineage graph.

```text
milk/v2/scopes/<scope_uuid>/
  c/<exchange_uuid>.json.zst
  l/<classifier_digest>/<exchange_digest>.json
  s/<summary_uuid>/{source.json.zst,summary.json}
  s/current.json
  readiness/<readiness_uuid>.json
  readiness/current.json
  e/<eval_uuid>/{revision.json,context.json.zst,manifest.json,shards/...}
  e/current.json
  d/<dataset_uuid>/{manifest.json,train.jsonl.zst,dev.jsonl.zst,
                    calibration.jsonl.zst,sealed.jsonl.zst}
  t/<training_uuid>/{manifest.json,result.json}
  m/<model_uuid>/manifest.json
  v/<evaluation_uuid>/{bf16.json,dynamic-fp8.json,static-fp8.json,sealed.json}
  p/<proposal_uuid>.json
  r/<route_uuid>.json
  r/current.json
  j/<job>/<job_id>/{intent.json,receipt.json,result.json,...}
  status/current.json
```

All captures, labels, versioned artifacts, and job records are immutable
create-same objects. Only small `current.json` projections may change, using
conditional replacement. A pointer advances only after the referenced object
is complete and verified. `status/current.json` is a disposable UI projection,
not authority.

Every derived artifact binds scope, profile, parents, source manifest, prompt,
model and configuration digests, code revision, content digest, and creation
time. Logs and public evidence contain keys, IDs, counts, digests, timings, and
redacted provider receipts, never raw customer content or secrets.

The storage adapter supports local files and SigV4 S3-compatible storage,
including Cloudflare R2 and Amazon S3, through environment variables only.

## Milk Man runtime

Milk Man runs from Bash without Docker or a local GPU:

```text
bin/man   supervised development, resume, bootstrap, and local dashboard
bin/milk  status, one-shot reconciliation, and named deterministic jobs
```

`bin/man` uses the pinned minimal Headlong subset for an OpenAI-compatible
model call, exact-workspace trajectories, bounded context, skills, memory, and
small file/shell tools. Its system prompt stays short. Skills are listed and
read only when applicable. Memory holds concise durable decisions, not copied
Codex transcripts or provider logs.

The dashboard is an always-on local supervisor bound to `127.0.0.1`. Its status
refresh uses no model. Each chat instruction starts one bounded model turn,
streams redacted output, then returns to idle. It shows the selected non-secret
driver identity, exact repository state, active jobs, gateway health, object
progress, summary checkpoints, and environment-variable presence. It never
shows secret values and must distinguish local state, mechanics evidence, and
production authority.

`bin/milk operate --once` is the production-compatible reconciler. An external
scheduler invokes it. It processes all immediately ready work and exits. When
no watermark or frontier changed, it makes zero inference and provider calls.
There is no internal tick, sleeping loop, queue service, or resident manager.

Every invocation emits one `milk.job-result.v2` JSON object to stdout;
diagnostics go to stderr. Jobs are idempotent by immutable intent/result
identity. Ambiguous provider creation is reconciled before any retry.

## Jobs and environment bindings

`config/jobs.json` is the public job and environment-name contract. Each entry
names a hard-coded handler, deterministic trigger, exact input/output prefixes,
required bindings, prompt, timeout, and teardown handler. Configuration cannot
introduce a command path or arbitrary shell.

The model or operator may select only a reviewed job name. The selected job
resolves its own configured environment names. Credential presence never
starts work and one provider's failure never selects another provider.

Core bindings:

```text
Store
  MILK_SCOPE_ID
  MILK_SCOPE_PROFILE
  MILK_STORE_KIND=local|s3
  MILK_STORE_ROOT or MILK_STORE_ENDPOINT/REGION/BUCKET/ACCESS_KEY_ID/SECRET_ACCESS_KEY

Interactive driver
  LLM_API_URL
  LLM_MODEL
  LLM_API_KEY
  LLM_API_MODE=responses|chat_completions
  LLM_REASONING_EFFORT

Data jobs
  MILK_SUMMARY_BASE_URL/MODEL/API_KEY/API_MODE
  MILK_EVAL_BASE_URL/MODEL/API_KEY/API_MODE
  MILK_TEACHER_BASE_URL/MODEL/API_KEY/API_MODE

GPU and serving jobs
  explicit Baseten variables
  explicit Modal variables
  pinned image/model/config variables owned by the selected job
```

Baseten and Modal remain separate adapters and separate jobs. Do not build a
generic provider framework or silent fallback chain.

The default managed development driver is `zai-org/GLM-5.3-Flash` through the
environment-selected Baseten OpenAI-compatible endpoint. A distinct Modal
Endpoint lifecycle may create the same model as an owned driver. It must be
added beside, not in place of, the existing custom Modal controller path. Each
driver has separate state and explicit ensure/status/stop commands.

## Summary and readiness

Thresholds are environment-selected; the production progression is:

```text
100, 1,000, 10,000, 100,000 completed conversations
```

At a crossed threshold Milk Man:

1. lists complete captures and subtracts exact processed keys;
2. verifies envelopes and body digests;
3. computes model-free delta statistics;
4. merges exact accumulators with the previous compact checkpoint;
5. selects deterministic representative and tail samples;
6. asks the configured summary model for structured semantic labels and notes;
7. locally validates the JSON, recomputes totals, writes immutable objects, and
   conditionally advances summary/readiness pointers.

Structural output includes volume, parse/success/failure, endpoint, model,
route/fallback, streaming, modalities, tools, structured output, token counts,
bytes, latency, throughput, duplicates, concurrency, and time distribution.
Semantic output includes operation, domain, capability, oracle type, language,
complexity, answerability, sentiment, outcome, safety class, confidence, and
abstention. Do not infer sensitive personal attributes.

Readiness is deterministic and makes no model call. A mechanics profile may
use small thresholds to prove code. A production profile requires independently
collected traffic and configured statistical/data-quality minima. Generated or
mechanics traffic cannot qualify a production candidate.

## Evaluation and model loop

Evaluation generation uses the strongest configured teacher and structured
JSON output. Captured conversations provide provenance, task distribution, and
inspiration; generated cases must be new, self-contained, answerable, and have
a coherent expected answer. The model does not choose object keys or commit
pointers.

`MILK_EVAL_SOURCE_CONVERSATIONS` selects an exact deterministic source count.
`MILK_CASES_PER_CONVERSATION` selects the expansion ratio. The target operating
point is exactly 100 selected conversations times 100 cases, or 10,000 cases.
Before this fan-out, the same contract must produce one case from each of the
100 sources and pass one direct operator review. Formatting is enforced by the
provider's structured-output contract plus small local identity, count,
lineage, answer-presence, and uniqueness checks. Do not add another LLM
validator or grow a hand-built semantic rules engine.

Source assignment happens before derived data so train, DEV, calibration, and
sealed material cannot leak across splits. The source manifest must include
enough model-completed two-sided traffic for 100 held-out eval sources and at
least the configured train sources; therefore the capture count can exceed 100.

Dataset generation uses a separately configured maximum-intelligence teacher
for training targets. Training is pinned to:

```text
Qwen/Qwen3.5-0.8B
revision 2fc06364715b967f1860aea9cf38778875588b17
```

Weights never enter Git or OCI images. Weight-free runtime images hydrate a
pinned model at job start or reuse a provider cache/volume. Do not ship a
30-GB-plus model image.

BF16 and dynamic FP8 candidates receive the same ordered DEV cases. Static FP8
may run for mechanics but cannot win production while its implementation is
experimental. Code selects the winner from the reviewed policy, runs one
sealed evaluation, serves exactly one explicitly selected candidate provider,
and writes an unsigned proposal.

The operator then proves signed canary, candidate success, pre-byte fallback,
higher-revision rollback, signed zero, credential removal, and independent
zero active capacity on Baseten and Modal.

## Deployment and public experience

- Parlor is a small CPU-only Rust binary in a multi-stage Alpine build with a
  `scratch` runtime. Models and Python do not belong in this image.
- Cloudflare hosts the Worker/container and R2. One selected instance is the
  initial topology.
- Milk Man runs locally first. The same one-shot command may later be scheduled
  as a scale-to-zero CPU job without changing job behavior.
- Repository Actions do not execute Milk jobs. Image publication, when needed,
  is a separate reviewed builder concern.
- Public landing/docs use dependency-free HTML/CSS/basic JavaScript and plain
  language. The local dashboard uses the original Milk black, white, pink, and
  teal visual system without a frontend framework.
- Public repositories retain license, upstream attribution, model-license,
  security, and contribution notices. Anyone may fork, open issues, and submit
  pull requests; only the owner may merge.

## Evidence and acceptance

Every report must label its evidence class:

```text
source present
local mechanics
hosted mechanics
paid provider execution
live route mechanics
production-qualified evidence
```

Historical or synthetic mechanics never become production evidence merely
because they ran on the production domain. Completion requires a coherent
current-code lineage with exact commits, object IDs/digests, image digests,
provider IDs, route revisions, replay results, and teardown observations.

Release acceptance:

- the official SDK authenticates and both supported protocols stream through
  live Parlor;
- exact completed exchanges appear asynchronously in remote object memory;
- local Milk Man reads that store and progresses a fresh current-code mechanics
  lineage through summary, eval, dataset, Qwen training, comparison, sealed
  result, one candidate, unsigned proposal, signed routing, fallback, rollback,
  zero route, and zero provider capacity;
- managed GLM drives Milk Man; the additional Modal Endpoint lifecycle proves
  create/reuse, a later tool-using turn, stop, and absence without replacing the
  existing controller;
- repos, deployment, docs, and tracker describe the same current behavior.

Production qualification additionally requires independent customer traffic
to satisfy the production readiness contract. Until that exists, the product
may be live and mechanically proven but no learned candidate is called
production-qualified.

## Non-goals

Do not add a database, external queue, resident manager, internal polling loop,
standing GPU, generic provider abstraction, secret broker, product budget
system, model weights in images, local Docker/GPU requirement, deprecated
object reader, raw prompt archive, broad fixture suite, or self-signing/
self-merging agent.
