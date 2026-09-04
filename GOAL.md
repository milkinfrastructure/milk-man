# Current Milk execution goal

## Outcome

Publish one coherent Milk baseline, then prove one fresh current-code mechanics
lineage from the official OpenAI SDK through live Milk Parlor, remote object
memory, local Milk Man, useful eval generation, Qwen3.5-0.8B training,
comparable evaluation, candidate serving, signed routing, fallback, rollback,
and zero provider capacity.

In parallel, append an owned Modal Endpoint lifecycle for
`zai-org/GLM-5.3-Flash` so Milk Man can use either the existing managed Baseten
endpoint or a separately selected Milk-owned Modal endpoint through `LLM_*`.
Do not replace the working custom Modal controller or silently fail over.

This file is the active execution order. [PRD.md](PRD.md) is the stable product
contract. [goal_tracker.md](goal_tracker.md) is the evidence ledger.

## Starting state: 2026-09-04

- Milk Parlor `37c0f892cee2bb03277fff6cc107312e36fda672` is published,
  deployed, and healthy. It reports both supported protocols, 106 completed and
  persisted exchanges, zero capture drops, and a live background writer.
- Milk Landing `db49fb7c436d5841d6b73a759a3bbe7604232adc` is published and
  live.
- Milk Man local `main` is 13 commits ahead of published
  `ef315662a436a1df6166b5038f18dff68c75e7ab`. The latest local commit
  replaced a working controller binding with an unimplemented endpoint
  contract. The working tree restores the coherent 11-job contract.
- The local dashboard supervisor is reachable. Its last model turn failed
  because the provider returned no assistant text; no code, job, route, or
  provider state changed.
- Remote object memory contains 6,623 objects across seven scopes. Historical
  mechanics scopes prove the full loop in small form. None is the fresh
  current-code lineage required by this goal, and none qualifies a learned
  production route.
- The current dashboard scope has 106 captures and a completed summary, but its
  eval attempts are parked quality experiments. Do not resume, mutate, or call
  them the current lineage.

## Execution rules

1. Work in the three existing repositories only: `milk-parlor`, `milk-man`,
   and the static `milk-landing` site. Do not add another runtime service.
2. Keep Parlor as the small Rust data plane. Keep orchestration in Milk Man.
3. Run Milk Man locally from Bash against remote Parlor, R2, and explicit
   inference/GPU providers. No local Docker or GPU is required.
4. Use one fresh scope UUID and immutable revision IDs for the proof. Never mix
   artifacts, prompts, model bindings, or case IDs from an older lineage.
5. Each job selects a reviewed handler and resolves its own environment names
   from `config/jobs.json`. Secret values remain in the private process
   environment and never enter Git, the dashboard, logs, prompts, or objects.
6. Baseten and Modal are independent adapters and jobs. A failure never causes
   implicit fallback. The selected provider is an explicit command or env
   binding.
7. Idle reconciliation is model-free and exits. No internal tick, sleep loop,
   database, queue service, resident cloud manager, or standing GPU.
8. Use structured provider output plus small deterministic checks. Do not add
   an LLM validator, broad rules engine, fixture suite, or speculative gates.
9. Do not put model weights in Git or an OCI image. Hydrate pinned weights at
   job start or reuse a provider cache/volume.
10. The shared allowance for supervised build validation is $500. It is an
    operator limit for this proof, not runtime product code. Record actual
    provider IDs and usage; stop new paid work before the allowance can be
    exceeded.
11. Mark a tracker item complete only from the evidence class it names. Hosted
    mechanics is not production-qualified evidence.
12. Patch the first concrete failure and continue the same valid lineage. Do
    not broaden the audit or refactor unrelated code while paid work is active.

## P0 — publish a coherent baseline

- [x] Keep the working 11-job contract and remove declarations for handlers
  that do not exist.
- [x] Ensure `config/jobs.json`, `milk_v2/config.py`, `milk_v2/runner.py`,
  `bin/milk`, `bin/man`, the dashboard, README, PRD, goal, and tracker describe
  the same commands and bindings.
- [x] Run only syntax/import/config checks and one read-only dashboard status
  fetch. Do not run a broad test suite.
- [x] Secret-scan the unpublished Milk Man range and current diff.
- [x] Commit and push the 13 retained local commits plus the reconciliation.
- [x] Confirm public `main` resolves to baseline commit
  `503ac816aa1c495798f09fa06cfd560d52d56b24`.
- [ ] Restart the dashboard from the published source when the current local
  supervisor can be replaced, then confirm its read-only state endpoint.
- [ ] Run one bounded dashboard instruction through managed Baseten
  `zai-org/GLM-5.3-Flash` at maximum reasoning. It must make at least one fixed
  tool call, return assistant text, and leave an exact trajectory record.
- [ ] Identify the Cloudflare instance selected by Parlor and stop the five
  stale running generations. Retain only the selected generation; uptime is
  not a constraint during this development cutover.

Acceptance: public source, local runtime, dashboard contract, and live Parlor
all agree; no incomplete endpoint appears as ready; no secret is published.

## P1 — fresh traffic, summary, and readiness

- [ ] Generate a new mechanics scope UUID and bind one operator-issued Milk
  key to it.
- [ ] Select source IDs deterministically before derivation. Capture enough
  complete two-sided traffic for exactly 100 held-out eval sources plus the
  configured training sources; the raw capture total may therefore exceed 100.
- [ ] Send both Responses and Chat Completions through the official OpenAI SDK
  to live Parlor. Use the lowest suitable reasoning for synthetic source
  traffic. Keep request and returned-response bodies complete.
- [ ] Confirm Parlor returns responses before asynchronous R2 writes and every
  accepted source appears once under the fresh scope `c/` prefix.
- [ ] From the dashboard, invoke Milk Man once to read the remote scope and run
  `summary`. Use the configured maximum-intelligence summary teacher.
- [ ] Inspect the immutable labels, summary, readiness, and current pointers.
  Counts must reconcile exactly to accepted capture keys. Rerunning without a
  new watermark must make zero inference calls and leave pointers unchanged.

Acceptance: the fresh scope has exact two-sided capture lineage, one useful
summary checkpoint, deterministic readiness, and an idle zero-call replay.

## P2 — prove eval usefulness before fan-out

- [ ] Set `MILK_EVAL_SOURCE_CONVERSATIONS=100` and
  `MILK_CASES_PER_CONVERSATION=1`.
- [ ] Run one eval job through the dashboard with the strongest configured
  teacher and structured JSON output.
- [ ] Require exactly one new, self-contained, answerable case for each selected
  source. Preserve source ID, prompt/model/config digests, case ID, expected
  answer, and oracle type.
- [ ] Check only parseability, exact count, unique IDs, source coverage,
  answer presence, and obvious duplicate text.
- [ ] Review the 100 cases once as a human. Record direct counts for useful,
  repairable, duplicate, unanswerable, and source-copying cases, with a small
  redacted sample.
- [ ] If the contract fails, make one minimal prompt/schema correction and
  create a new eval revision. Never overwrite or splice the failed revision.

Acceptance: one reviewed revision demonstrates that the teacher is producing
useful cases, not merely valid JSON. No bulk fan-out begins before this point.

## P3 — produce the 10,000-case lineage

- [ ] Freeze the accepted prompt, schema, provider binding, source manifest,
  and code revision.
- [ ] Set `MILK_CASES_PER_CONVERSATION=100` and generate exactly 10,000 unique
  cases from the same 100 sources using bounded immutable shards.
- [ ] Resume only missing or incomplete ranges. A replay of a completed shard
  must make zero inference calls.
- [ ] Publish `e/current.json` only after all 10,000 cases parse, reconcile to
  the source manifest, and are unique by case ID and normalized content.
- [ ] Do not add another semantic validator loop. Audit one deterministic
  sample and record the result.

Acceptance: one current pointer names exactly 10,000 source-bound cases from a
single immutable contract; no old revision is mixed in.

## P4 — train and compare the student

- [ ] Assign source-level train, DEV, calibration, and sealed splits before
  teacher targets. Assert no source crosses a split.
- [ ] Generate training targets with the separately configured strongest
  teacher.
- [ ] Build the dataset and train exact
  `Qwen/Qwen3.5-0.8B@2fc06364715b967f1860aea9cf38778875588b17` on
  ephemeral Baseten training capacity.
- [ ] Evaluate BF16 and dynamic FP8 on the same ordered DEV cases. Run static
  FP8 only as mechanics unless its implementation is independently qualified.
- [ ] Select the winner deterministically from the published evaluation policy
  and run exactly one sealed evaluation.
- [ ] Record dataset/model/evaluation UUIDs, source and image digests, provider
  job IDs, metrics, termination receipts, and zero active training capacity.

Acceptance: one source-separated dataset leads to one reproducible student and
one deterministic, sealed winner without leakage or standing training GPUs.

## P5 — serve, route, fall back, and stop

- [ ] Explicitly select either the Baseten or Modal candidate job. Do not try
  both automatically.
- [ ] Hydrate the winning weights into a weight-free serving image and record
  the exact candidate URL identity without exposing its key.
- [ ] Milk Man writes one unsigned proposal. Only the operator route publisher
  may sign and advance Parlor's route pointer.
- [ ] Prove a low-percentage signed canary with the official SDK.
- [ ] Prove candidate success, pre-byte fallback after candidate removal,
  higher-revision rollback, and a signed zero route.
- [ ] Remove candidate credentials and confirm Parlor reports no candidate
  binding.
- [ ] Independently confirm zero active candidate/training capacity on Baseten
  and zero active Milk GPU apps on Modal.

Acceptance: the same fresh lineage reaches a signed live mechanics route and
returns to the baseline with both providers at zero capacity.

## P6 — append the owned Modal GLM driver

This work may proceed beside P1–P5 but may not block them.

- [ ] Add three implemented jobs beside the existing controller:
  `inference-endpoint-ensure`, `inference-endpoint-status`, and
  `inference-endpoint-stop`.
- [ ] Pin `zai-org/GLM-5.3-Flash`, the weight revision, vLLM/runtime version,
  GPU type/count, tensor parallelism, context, batching, image digest, volume,
  region, and endpoint name through reviewed config and environment names.
- [ ] Keep its state pointer separate from the existing custom-controller state.
- [ ] `ensure` reuses an exact healthy deployment, reconciles an ambiguous
  creation before retrying, or creates one new deployment. `status` is
  read-only. `stop` removes it and proves absence.
- [ ] Feed the resulting OpenAI-compatible URL/model/key to the existing
  `LLM_*` driver selection. Do not special-case Modal in Headlong.
- [ ] Through the Chrome-controlled local dashboard, prove ensure, one later
  tool-using Milk Man turn powered by that endpoint, stop, and zero capacity.
- [ ] Compare measured cold start, time to first token, output tokens/second,
  p50/p95 latency, failure rate, and cost with the managed Baseten endpoint.
  Record the result; do not build an automatic optimizer.

Acceptance: managed Baseten and owned Modal are two explicit usable GLM driver
choices. Neither replaces the custom controller or silently selects the other.

## P7 — publish and distinguish qualification

- [ ] Update concise READMEs and public docs with the two-loop diagram, official
  SDK setup, exact supported endpoints, dashboard screenshots, object stages,
  provider choices, and the evidence-class distinction.
- [ ] Publish current source and tags only after the current-code mechanics
  lineage completes. Repository Actions remain absent.
- [ ] Record a compact final report linking exact commits, live deployment,
  scope/revisions, provider jobs, route revisions, and zero-capacity evidence.
- [ ] Keep the learned route labeled mechanics until independently collected
  customer traffic crosses the production readiness contract. Then repeat the
  same fixed loop in a fresh production lineage before calling it qualified.

## Stop conditions

Stop and report one precise blocker if continuation would require a missing
credential, account capability, operator signature, unavailable source traffic,
or a semantic contract change to an already-started immutable revision. Do not
hide the blocker behind another audit, retry loop, provider fallback, or new
abstraction.
