# Milk Churn transition

Status: implementation decision, 2026-08-29.

## Decision

`milkinfrastructure/milk-churn` is a fork of Prime Intellect's Prime Agent and
the local coding and research agent for Milk. It is not a third production
service.

Production remains:

- `milk-gateway`: Rust request handling, sampling, route selection, and signed
  route enforcement;
- `milk-harness`: a deterministic finite job that reads S3-compatible storage,
  summarizes traffic, invokes a teacher within a fixed budget, generates eval
  revisions, and writes unsigned route proposals.

Milk Churn may edit and test trusted disposable checkouts. It may not become
the traffic router, storage scheduler, signer, or paid-job manager. Prime Agent
already supplies sessions, goals, schedules, subagents, compaction, autonomous
gates, and supplemental self-refinement. Milk will not rebuild them.

## Current Milk state

The routing and eval-generation milestone is implemented locally but not
committed or deployed.

| Repository | Base commit | Working state | Verified 2026-08-29 |
| --- | --- | --- | --- |
| `milk-gateway` | `e7ddf254dc996476f9762b7770ddc9e3e06ca322` | `codex/routing-eval-pipeline`; 16 modified files; +2,454/-683 | Rust workspace tests: 150 passed |
| `milk-harness` | `e01ded36cef1208f8af64eecb9c5ec32a7521ad5` | `codex/routing-eval-pipeline`; 5 modified and 5 untracked files | Python unit tests: 243 passed |

Implemented locally:

- OpenAI Chat Completions and Responses through the Rust gateway;
- scope-first object keys, deterministic session sampling, and aggregate
  counters;
- candidate fallback, a sticky failure fuse, and signed canary/zero routes;
- one deterministic `python -m milk_harness run-once` pass;
- bounded summary, classification, readiness, eval-generation, and unsigned
  proposal stages;
- a 51-line hourly/manual workflow around the same command;
- separate production and mechanics configurations.

Baseten's hosted `zai-org/GLM-5.3-Flash` endpoint has passed Chat Completions,
Responses, and exact classifier-wire qualification. Observed qualification
spend was approximately $0.000072. The key is in the macOS Keychain, not a
repository.

Still required for production proof:

- reviewed commits for both current branches and CI on those exact commits;
- a current Rust gateway deployment;
- real production R2 traffic and one completed scheduled pass;
- an operator-reviewed proposal, signed canary, fallback, signed zero route,
  and verified zero-GPU finish.

Local tests and provider-wire checks do not prove those live steps.

## Production flow

```text
OpenAI SDK traffic
  -> Rust gateway
  -> sampled S3-compatible objects
  -> finite milk-harness run-once job
  -> summary and readiness decision
  -> teacher-generated eval revision
  -> unsigned route proposal
  -> operator signing
  -> Rust gateway route
```

Object storage is the durable index. Immutable objects name their inputs; only
small current pointers move with conditional writes. There is no production
database, queue, resident workflow manager, or model-driven planner.

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
available. Milk Churn is limited to trusted disposable repositories for this
milestone. Do not present it as a sandbox or run untrusted packages until the
archive path is removed, replaced, or fixed upstream.

## License boundary

Repository software and model artifacts are licensed separately.

- Milk Churn preserves Prime Agent's MIT license and notices.
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
permissions. The task may admit its bounded agent-model calls while push,
deploy, Milk-side provider calls, object writes, and route publication default
to false.

Do not migrate the Codex transcript, hidden reasoning, raw credentials,
browser sessions, shell history, memory folders, production prompts or
responses, signing keys, implicit approvals, or an unreviewed dirty checkout.

## Minimum local loop

1. Review the task document and verify exact clean base commits.
2. Create disposable worktrees for the admitted repositories.
3. Run the pinned Milk Churn source against those worktrees.
4. Load only the Milk project skill and trusted repository context.
5. Let Prime Agent edit within the task and run the fixed local gates.
6. Stop on success or declared turn, time, token, or spend limits.
7. Return a reviewable diff and bounded test result.
8. Keep commit, push, cloud deploy, spend, signing, and publication as separate
   operator actions.

Local deployment means a checked-in fixed command such as launching a temporary
Rust gateway and running the official SDK smoke. Cloud deployment is separate.
No new Rust orchestration framework is required: Milk Churn calls existing Rust
CLI and HTTP contracts. Add Rust only when an operation cannot be expressed by
an existing typed command.

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

This milestone ends after the fork is published, source checks pass, and one
disposable local agent run completes. Its receipt is recorded in
[`local-proof-receipt.md`](local-proof-receipt.md). Production deployment
resumes only after the existing gateway and harness branches are reviewed and
committed.
