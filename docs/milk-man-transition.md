# Milk Man transition

Status: two-product implementation decision, 2026-08-29.

## Decision

Milk has two products:

- `milk-carton` is the small Rust data plane. It authenticates operator-issued
  keys, serves the OpenAI-compatible API, captures admitted traffic, enforces
  signed routes, and performs bounded fallback.
- `milk-man` is the agentic harness. It edits trusted checkouts and invokes a
  small set of deterministic jobs for traffic summaries, classification,
  readiness, eval generation, and unsigned route proposals.

Milk Man uses Prime Agent's existing sessions, goals, schedules, subagents,
compaction, autonomous gates, and supplemental self-refinement. It does not add
a Milk database, queue, resident manager, scheduler service, or generic provider
framework.

The model may choose among calls admitted by a reviewed task. It cannot supply
an arbitrary command or change a job's scope, configuration digest, budget,
credential reference, write target, or route policy. Route signing and route
publication remain operator-only actions outside Milk Man.

## Implementation checkpoint

- Milk Carton's routing and capture implementation is checkpointed at
  `8ce45f3daf3d262eaa77e672ece2aa7918033aed`; its Rust workspace tests passed
  150 tests on 2026-08-29.
- The deterministic Python implementation is checkpointed at
  `07db7b7e472a87d44e0dd62ee32a878d2874b012`. For this migration it remains a
  temporary implementation bridge behind Milk Man's fixed job call. It is not a
  third product, service, scheduler, or authority.
- Milk Man's published pre-stitch checkpoint is
  `8e6d875fca9c4e3377e9e8ac9aae85c81e3555e3`; its source check and one bounded
  model-backed disposable-worktree proof passed.

The temporary bridge already performs one finite
`python -m milk_harness run-once` pass: summary, classification, readiness,
eval generation, and unsigned proposal. Milk Man calls it with operator-pinned
configuration and credentials. The bridge can be absorbed after the fixed call
and object-store contract are proven; its repository is not part of the final
product boundary.

Baseten's hosted `zai-org/GLM-5.3-Flash` endpoint has passed Chat Completions,
Responses, and classifier-wire qualification. Observed qualification spend was
approximately $0.000072. Provider credentials remain outside repositories and
object storage.

Local tests and provider-wire checks do not prove deployment. Production proof
still requires exact published commits and CI, a current Milk Carton deployment,
real captured traffic, one completed scheduled Milk Man job, an
operator-reviewed proposal, signed canary, fallback, signed zero route, and a
verified zero-GPU finish.

## Durable memory

Milk Carton and Milk Man share one scope-first object contract. Traffic, job
claims and results, summaries, eval revisions, unsigned proposals, and route
versions are durable objects. Immutable objects identify their inputs; small
head pointers may move only through conditional writes. Live REPL state and
scratch files are disposable. Credentials and signing keys are never objects.

The supported storage modes are local filesystem and qualified S3-compatible
storage. AWS S3, Cloudflare R2, MinIO, or another implementation is supported
only after it passes the required create-if-absent, ETag compare-and-swap,
read-after-write, ordered-prefix-list, and delete semantics. “S3-compatible” is
not accepted from branding alone.

```text
OpenAI SDK traffic
  -> Milk Carton
  -> sampled scope objects
  -> fixed Milk Man job call
  -> summary and readiness decision
  -> teacher-generated eval revision
  -> unsigned route proposal
  -> operator signing and publication
  -> Milk Carton route
```

## Upstream provenance

- source: `https://github.com/PrimeIntellect-ai/prime-agent`;
- initial branch: `main`;
- initial commit: `5b6c0e94e11a97fcfdd7a9fc9dc4f7acbda9c853`;
- observed version: `0.8.1`;
- software license: MIT, preserving the Mario Zechner and Prime Intellect
  notices.

Prime Agent is a TypeScript/Node application with a Python kernel. It stays
that way. Rust remains the small always-on Milk data plane; agent execution is
not latency-sensitive and should follow upstream.

The pinned upstream dependency audit currently reports three advisories: a
high-severity `extract-zip` path-traversal advisory with no npm-proposed fix, a
high-severity transitive `nanoid` zero-size loop advisory with a fix available,
and a moderate transitive `protobufjs` parser loop advisory with a fix
available. Milk Man is limited to trusted disposable repositories for this
milestone. Do not present it as a sandbox or run untrusted packages until the
archive path is removed, replaced, or fixed upstream.

## License boundary

Repository software and model artifacts are licensed separately.

- Milk Man preserves Prime Agent's MIT license and notices.
- The custom GLM-5.3 license applies when covered GLM-5.3 weights,
  configuration, code, or documentation are copied or distributed.
- GLM-5.3-Flash is MIT at the pinned source revision.
- Calling a hosted model does not replace the caller repository's license.

Exact pinned model licenses and sources are recorded in
[`THIRD_PARTY_MODEL_NOTICES.md`](../THIRD_PARTY_MODEL_NOTICES.md). No model
weights are included.

## Portable task handoff

Migrate one reviewed task document conforming to
[`milk/task.schema.json`](../milk/task.schema.json). It contains exact base
commits, intended branches, allowed paths, acceptance text, fixed gate IDs,
limits, configuration hashes, non-secret credential references, and explicit
permissions. A task can admit a bounded agent-model call or one fixed Milk job
call. Push, deploy, provider calls, object writes, route preparation, signing,
and publication remain separate permissions and default to false.

The task document remains the authority. A run may also receive a reviewed,
bounded Codex message range through `milk/codex-context.sh` as advisory history.
The adapter retains only user and assistant text and rejects unbounded or
oversized input. Do not migrate a full transcript, hidden reasoning, tool calls
or results, raw credentials, browser sessions, shell history, memory folders,
production prompts or responses, signing keys, implicit approvals, or an
unreviewed dirty checkout.

## Minimum local loop

1. Review the task document and verify exact clean base commits.
2. Create disposable worktrees for the admitted Milk Carton or Milk Man
   repositories.
3. Run the pinned Milk Man source against those worktrees.
4. Load only the Milk project skill and trusted repository context.
5. Let Prime Agent edit within the task and run the fixed local gates, or invoke
   the one admitted fixed job call.
6. Stop on success or declared turn, time, token, or spend limits.
7. Return a reviewable diff and bounded test result.
8. Keep commit, push, cloud deploy, provider spend, object writes, signing, and
   publication as separately admitted operator actions.

Local deployment means a checked-in fixed command such as launching a temporary
Milk Carton and running the official SDK smoke. Cloud deployment is separate.
No new Rust orchestration framework is required: Milk Man calls existing typed
commands and HTTP contracts.

Self-refinement may update supplemental prompts, task guidance, or skills. It
may not alter the immutable base prompt, task limits, secret mapping, gate
list, spend limits, or route-signing boundary.

## Pixel design

The canonical Milk asset is `milk-ide/milkCarton.png`, introduced at
`444fee886901a1fa443803acef72e2f4405620d9`, with SHA-256
`35e8b806c7748dbec86d067806a251f24cdef84e4d734da2d58fa6e1d6178b59`.

Use a black `#000000` background, hot pink `#ED2D6C` frame, white `#FFFFFF`,
teal `#00A092`, cyan `#68CADE`, and rose `#F06A91`; system monospace; flat
fills; one-pixel borders; compact uppercase labels; and nearest-neighbor
integer scaling. Do not add gradients, smoothing, or unrelated Exo artwork.

## Stop point

The fork, source check, and disposable local agent proof are recorded in
[`local-proof-receipt.md`](local-proof-receipt.md). The next milestone ends only
when the fixed Milk Man job call and Milk Carton object contract pass locally
and on exact published commits. Production proof remains a separate live gate.
