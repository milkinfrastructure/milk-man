# Milk Infrastructure product contract

This file defines the product. `GOAL.md` defines the current execution outcome.
`goal_tracker.md` records evidence and remaining work.

## Product promise

Milk Man turns a high-level objective and an environment into completed model,
compute, and research work. It inspects existing resources and prior results,
reuses or creates scripts, executes them through Bash, measures outcomes,
adapts, persists what it learned, and continues until the objective is complete
or a specific external blocker is proven.

Milk Parlor is the first major application and data source. It turns completed
model traffic into scoped object memory that Milk Man can summarize, use for
evaluation or training research, and eventually route to an improved model. An
application keeps the official OpenAI SDK and changes only two settings:

```text
OPENAI_BASE_URL=https://parlor.milkinfrastructure.com/v1
OPENAI_API_KEY=<operator-issued Milk key>
```

Milk currently supports `POST /v1/responses` and
`POST /v1/chat/completions`, including streaming. It does not claim the entire
OpenAI API and does not require a Milk SDK.

The end state is continuous autoresearch per scope UUID: use its captured
traffic to pursue an open-source model that beats the best measured baseline
on that scope's tasks, within its latency, throughput, and compute constraints.
Improving Milk Man itself is one instance of this same product loop.

## Scope-specific research

Each scope keeps a small versioned research record in object storage, with a
conditional current pointer: objective, metrics, baseline model/configuration,
held-out evaluation identity, best measured candidate, completed experiments,
next action, and wake condition. The record references existing summaries,
datasets, jobs, models, and measurements instead of copying their contents.
This is state for the existing heartbeat and job runner, not a second service.

Changed traffic advances cumulative summaries at configured thresholds. Milk
Man uses the summaries and previous experiments to choose the next useful job:
generate examples, tune inference, train an open-source base, run a genuine RL
experiment, evaluate, or wait. Model/provider choices and operating targets
come from the scope's configuration and environment bindings.

With `MILK_AUTO_SUMMARY=1`, the heartbeat counts capture objects within the
configured scope, stopping at the next `MILK_SUMMARY_THRESHOLDS` value. Crossing
it starts the existing summary job directly. Counting needs no model call and
does not replace another job's wait. One private background receipt prevents
duplicate launches; failed jobs remain visible rather than retrying blindly.
The dashboard reads the finished summary file through the existing pointer;
partial generation never appears as a completed summary. Tasks may separately
watch research results when those results matter to their objective.
Thresholds count stored exchanges; readiness
must separately account for independent source groups, including whole agent
trajectories. A summary alone does not prove enough independent training data
or a better model.

Compare the current baseline and candidate on the same untouched tasks, with
source conversations and agent trajectories kept together across data splits.
Keep failed and losing results so later iterations do not repeat them. A new
best must have measured evidence; generating more data or completing training
is not an improvement by itself. A state-of-the-art claim names its benchmark,
reference model/configuration, date, and comparable measurements. A win on one
scope is not a global state-of-the-art claim.

Scopes remain separate unless their operator explicitly authorizes combining
data. Serving promotion follows the existing route contract. The dashboard
shows each scope's objective, baseline versus best, latest result, next action,
and heartbeat without exposing private traffic or credentials.

## The two loops

```text
Autonomous research loop

high-level prompt + environment + retained state
                       |
                       v
inspect -> plan -> Bash/scripts -> resources -> measurements
   ^                                              |
   |                                              v
   +------ compare <- persist result <- adapt/cleanup

Milk application

official SDK -> Milk Parlor -> configured model -> response to application
                    |
                    +-> completed request + response -> object memory
                                                        |
                                                        v
Milk Man -> summary -> evals/data -> training/research -> serving -> route
```

The dashboard is an optional view and prompt surface for the same agent that
runs from Bash. Human supervision is useful during development but is not a
runtime dependency. One task may require many autonomous commands, waits, code
changes, deployments, measurements, and cleanups.

## Components and ownership

| Component | Owns | Must not own |
| --- | --- | --- |
| `milk-parlor` | Key authentication, protocol-native proxying, streaming, bounded asynchronous capture, signed-route verification, pre-byte fallback, process health | Summaries, thresholds, jobs, model training, provider lifecycle, user database |
| `milk-man` | Autonomous Bash harness, trajectories, skills, memory, heartbeat, reusable and self-authored scripts, model/compute lifecycle, optimization, object traversal, Milk research jobs, local dashboard | Customer request serving, credential publication, unrelated external actions |
| `milk-landing` | Static public explanation and developer guide | Credentials, customer data, job execution, runtime control |
| Object store | Durable scoped data, lineage, job receipts, and current pointers | Computation, scheduling, secret storage |
| Human/operator | High-level objectives, environment and provider accounts, route signatures when required, production qualification | Naming each command or manually advancing routine work |

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

Milk Man opts into `X-Milk-Trajectory-Id` for gateway-bound driver calls.
Parlor stores its validated UUID as optional `trajectory_id` and removes the
header before forwarding. Summary and dataset jobs keep that scope-bound task
group together across splits; untagged traffic retains request-based grouping.
Native tool calls and results are captured intact. Training on those sequences
is still separate work; a text-only training path must not silently discard
them or treat repeated context as independent conversations.

Start with one named Cloudflare container. Add a fixed pool or scope sharding
only after a warm saturation measurement demonstrates the need.

## Object memory

The scope UUID is the root identity. Folder-like keys form the traversal index;
parent UUIDs and content digests form the lineage graph.

```text
milk/v2/scopes/<scope_uuid>/
  research/<research_uuid>/record.json
  research/current.json
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
bin/man   prompt-driven reasoning, resume, bootstrap, heartbeat, and dashboard
bin/milk  reusable Milk jobs and structured status/results
```

`bin/man` uses the pinned minimal Headlong subset for an OpenAI-compatible
model call, exact-workspace trajectories, bounded context, skills, memory, and
file/shell tools. Bash is the universal execution boundary. Its system prompt
stays short: inspect current state, choose and execute the next useful action,
observe the result, adapt, and continue. Skills are listed and read only when
applicable. Memory holds concise objectives, decisions, resource identities,
measurements, conclusions, and recovery state rather than copied transcripts
or full provider logs.

The Milk deployment uses Parlor for the harness's own model calls. An
operator-issued Milk key selects a dedicated UUIDv6 scope; the UUID is an
identifier, not a credential. Capture the actual API requests and responses,
including tool-call/result context, without copying process credentials.
Keep task boundaries so overlapping context is not counted as independent
training data. Captured attempts are research inputs, not automatically good
training examples: compare task outcomes before selecting examples or changing
the driver. Summaries, evaluation, and learning reuse the existing jobs.

The dashboard is an optional local prompt and observation surface bound to
`127.0.0.1`. It streams redacted reasoning/tool output and shows the active
task, selected non-secret driver identity, repository state, heartbeat, current
activity, next wake, active jobs/resources, measurements, gateway health,
object progress, and environment-variable presence. Closing the dashboard does
not stop Milk Man.

One lightweight Bash heartbeat keeps an active task available without another
service. It owns one lock per task, persists the active objective and next wake,
checks known asynchronous jobs and changed object markers, and backs off through
environment-configured intervals. A new prompt, scheduled review, changed
object, completed or failed job, or measured regression wakes reasoning. An
unchanged idle check makes zero model calls and does not scan the whole bucket.
`bin/milk operate --once` remains useful for a single deterministic pass, but it
is not the only production execution model.

Every invocation emits one `milk.job-result.v2` JSON object to stdout;
diagnostics go to stderr. Jobs are idempotent by immutable intent/result
identity. Ambiguous provider creation is reconciled before any retry.

## Jobs and environment bindings

`config/jobs.json` remains the public job and environment-name index. Existing
Python handlers continue to work, but they are not a permanent allowlist. A job
may name a reviewed repository-relative Bash or Python script plus its purpose,
inputs, required and optional environment names, timeout, status, cleanup, and
object prefixes. Adding that job must not require another branch in a central
handler enum. Resolve and execute only scripts inside the repository; model
arguments cannot supply executable paths or shell fragments.

The agent reuses a suitable job when one exists. For an unseen workload it may
write or repair the smallest repository-owned script, add it to the existing
job index, execute it, and reuse it later without changing the Headlong engine.
The process contract is small: arguments in; selected environment inherited;
progress on stderr; one final structured result on stdout; explicit status and
cleanup when external resources are owned.

Credential presence never starts work by itself. A high-level task may allow
Milk Man to choose and sequence the necessary jobs, providers, configurations,
waits, and cleanups without requiring the human to name each command. One
provider's failure never silently selects another provider.

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
  model/revision, image/runtime, GPU type/count, serving arguments
  latency/throughput/correctness/cost targets owned by the selected task
```

Baseten and Modal use small provider-native scripts behind the same process
contract, not a large generic cloud framework or silent fallback chain.

The managed GLM binding is `zai-org/GLM-5.3-Flash` through an
environment-selected OpenAI-compatible endpoint. The existing fixed Modal
controller remains usable while it is extracted into general lifecycle jobs.
When OpenAI is selected, the default model is `gpt-6-astra`. Both providers can
use a Parlor endpoint and Milk key; upstream provider credentials stay in the
gateway environment. A provider change is explicit, never an automatic fallback.
GLM Flash, a 120B workload, and Qwen are initial demonstrations, not fixed
controller, teacher, student, provider, or compute requirements.

## Model, compute, and optimization loop

For a model or compute objective, Milk Man must be able to:

1. inspect configured providers, existing deployments, caches, artifacts, and
   retained experiment results;
2. create or reuse the selected resource and record its exact identity;
3. follow startup and logs, verify readiness, and run a real workload;
4. measure correctness, cold start, time to first token, output tokens per
   second, p50/p95 latency, errors/OOM, resource usage, and cost as applicable;
5. propose the next configuration from those measurements rather than replay a
   fixed matrix;
6. vary model/revision, runtime, GPU type/count, tensor parallelism,
   quantization, context, batching/concurrency, cache, and serving arguments
   allowed by the task;
7. retain the best measured configuration satisfying the objective, stop losing
   trials, and verify their resources are absent; and
8. resume without repeating completed experiments or creating duplicate
   resources.

Managed APIs and owned deployments remain independent options. A task may keep
a winning service alive or release all compute when finished. Model weights are
hydrated from a pinned source or provider cache/volume and do not enter Git or
lightweight OCI images.

## Milk traffic and summary application

The remaining sections define the whiteboard application's existing contracts.
They are important Milk workloads, not prerequisites for accepting the general
agent, job extensibility, heartbeat, or model lifecycle.

### Summary and readiness

Thresholds are environment-selected; the production progression is:

```text
100, 1,000, 10,000, 100,000 saved request/response exchanges
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

### Evaluation and model loop

Native assistant/tool data is a separate input to this loop. The
`native-dataset` job reads a pinned summary and selects complete supported
exchanges within each existing trajectory split. It keeps messages, tool
definitions, prior tool results and new assistant targets in immutable split
files under `d/<uuid>/`. It does not fabricate text evals or change current
pointers. The training job can select this manifest explicitly through
`MILK_DATASET_MANIFEST_KEY/SHA256`; SFT masks the context and learns only the
new assistant target using the student's actual chat template. Context that
does not fit is reported, never silently truncated. Native training results
remain separate from the text-eval route workflow. Completed tool calls alone
are not successful tasks, and the text-similarity RL reward is not used for
tool actions. Improvement requires a baseline and comparison on held-out tasks.

Evaluation generation uses the strongest configured teacher and structured
JSON output. Captured conversations provide provenance, task distribution, and
inspiration; generated cases must be new, self-contained, answerable, and have
a coherent expected answer. The model does not choose object keys or commit
pointers.

`MILK_EVAL_SOURCE_CONVERSATIONS` selects an exact deterministic source count.
`MILK_CASES_PER_CONVERSATION` selects the expansion ratio. One planned
experiment uses 100 selected conversations times 100 cases, or 10,000 cases;
that ratio is configuration, not a runtime invariant or prerequisite for model
operations. Before any large fan-out, inspect a small output from the same
contract. Formatting is enforced by the provider's structured-output contract
plus small local identity, count, lineage, answer-presence, and uniqueness
checks. Do not add another LLM validator or grow a hand-built semantic rules
engine.

When an experiment uses train, DEV, calibration, and sealed splits, source
assignment happens before derived data so one source cannot leak across splits.
The requested counts and ratios belong to that experiment's environment and
source manifest, not the Milk Man runtime.

Dataset generation may use a separately configured maximum-intelligence teacher
for training targets. The first student workload is pinned to:

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

The whiteboard application eventually proves signed canary, candidate success,
pre-byte fallback, higher-revision rollback, signed zero, credential removal,
and independent zero active capacity on Baseten and Modal.

SFT is the currently demonstrated training mechanic. Reinforcement learning is
an explicit optional extension with separate rollout generation, reward/judge
output, training recipe, baseline, and evaluation jobs. Do not call existing
SFT mechanics RL.

## Deployment and public experience

- Parlor is a small CPU-only Rust binary in a multi-stage Alpine build with a
  `scratch` runtime. Models and Python do not belong in this image.
- Cloudflare hosts the Worker/container and R2. One selected instance is the
  initial topology.
- Milk Man runs locally first and remains alive through its lightweight Bash
  heartbeat. The same scripts may run on private cloud compute without changing
  job behavior; no separate scheduler product is required.
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
because they ran on the production domain. Claims about a completed workload
require exact commits, object IDs/digests, image digests, provider IDs,
measurements, replay results, and teardown or retained-service observations as
applicable.

Release acceptance:

- one high-level objective automatically progresses through existing scripts
  from both dashboard and Bash, saves its result, and reuses it;
- one unseen objective causes Milk Man to create or repair a reusable script
  without changing the harness engine;
- Milk Man deploys or reuses a real model, verifies it, measures and improves
  its inference configuration, selects a winner from evidence, and cleans losing
  resources;
- the heartbeat makes zero model calls while idle and resumes the same task
  after an interrupted asynchronous wait without duplicating compute;
- a different model or compute workload completes through the same mechanism;
- the official SDK authenticates and both supported protocols stream through
  live Parlor;
- exact completed exchanges appear asynchronously in remote object memory;
- local Milk Man reads that store and progresses the whiteboard application
  through summary and, as separate extensions, eval, dataset, Qwen training,
  comparison, serving, and signed routing;
- repos, deployment, docs, and tracker describe the same current behavior.

Production qualification additionally requires independent customer traffic
to satisfy the production readiness contract. Until that exists, the product
may be live and mechanically proven but no learned candidate is called
production-qualified.

## Non-goals

Do not add a database, external queue, separate scheduler service, busy
model-consuming poll loop, provider framework larger than the provider-native
scripts require, secret broker, product budget system, model weights in images,
local Docker/GPU requirement, deprecated object reader, raw prompt archive, or
broad fixture suite. Do not require a standing GPU: keep a requested winning
service alive and release other compute.
