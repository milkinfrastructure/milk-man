# Milk evidence and execution tracker

Updated: 2026-09-04

This is the concise state ledger. The stable contract is [PRD.md](PRD.md); the
ordered work is [GOAL.md](GOAL.md). The former 1,874-line tracker remains in Git
history and is not copied into another archive file.

Status notation:

- `[x]` verified against current source, live state, or an exact retained object
- `[~]` real historical or partial mechanics evidence; not current completion
- `[!]` verified defect, drift, or operational residue
- `[ ]` not yet proven

## Executive state

- [x] The architecture is still the whiteboard architecture: a small gateway
  captures model traffic into scoped object memory; Milk Man turns it into
  summaries, evals, training data, a student, comparisons, and a route proposal.
- [x] The product and development loops are now separated in `PRD.md` while
  sharing the same Milk jobs and object contract.
- [x] Milk Parlor is a deployed, healthy Rust gateway. It is not a manager,
  scheduler, training service, or generic router.
- [x] Milk Man runs locally from Bash, has an always-on model-free dashboard
  supervisor, and can make bounded OpenAI-compatible reasoning turns with fixed
  tools and jobs.
- [x] Summary, readiness, eval, dataset, training, evaluation, candidate,
  proposal, route, fallback, rollback, and teardown mechanics have all run in
  at least one retained small lineage.
- [~] Those mechanics span older code and generated traffic. They do not prove
  one coherent current-code lineage or a production-qualified learned route.
- [!] The immediate source defect was an incomplete Modal Endpoint declaration
  that replaced the working controller contract. The working tree restores the
  implemented 11-job contract; native Modal Endpoint jobs remain explicit work.
- [ ] The next proof is a fresh scope: 100 held-out sources, one reviewed case
  per source, then 100 cases per source and the complete downstream loop.

## Repository snapshot

Snapshot captured before the centralization commit:

| Repository | Local state | Published state | Assessment |
| --- | --- | --- | --- |
| `milk-man` | `2985a52a037a3a03164add303fa622e25c929c0c`, plus the documented reconciliation | `ef315662a436a1df6166b5038f18dff68c75e7ab` | 13 commits ahead at audit time; independent repository; publish after narrow checks |
| `milk-parlor` | `37c0f892cee2bb03277fff6cc107312e36fda672` | same | clean and deployed |
| `milk-landing` | `db49fb7c436d5841d6b73a759a3bbe7604232adc` | same | clean and live |

- [x] Milk Man is no longer a GitHub fork. It retains a pinned, attributed
  minimal Headlong subset as implementation source.
- [x] Milk Parlor has no tracked Actions, test fixtures, model weights, Python
  runtime, or orchestration code.
- [x] Milk Man repository Actions are absent; jobs run from `bin/milk` and
  supervised development runs from `bin/man`.
- [!] Milk Man has 93 local branches and 44 worktrees from prior iterations.
  They are local clutter, not product architecture; clean them only after the
  retained commits and evidence are safely published.
- [!] GitHub `main` is currently unprotected. Anyone may fork, open issues, and
  submit pull requests, but owner-only merge policy is not yet enforced by a
  branch ruleset.

## Live Parlor snapshot

- [x] Endpoint: `https://parlor.milkinfrastructure.com`
- [x] Cloudflare deployment:
  `020c50ea-375e-4d7f-b4c1-1d19a0f06e12`
- [x] Worker version: `4515234c-d762-4be6-816a-d4cda7f3582b`
- [x] Image:
  `sha256:7311ba8e6021f9c24277ad35ee5e6aeddc78e944e859ca4df0e933518a0e335e`
- [x] Health at audit: Responses and Chat Completions configured; candidate
  bindings absent; capture writer alive; 106 observed, completed, enqueued, and
  persisted; zero dropped, interrupted, oversized, or storage-failed.
- [x] The image is already a multi-stage Alpine build with a `scratch` runtime.
  Cloudflare's displayed 2 GB is ephemeral disk allocation, not image size.
- [x] Requests route to one secret-selected named container instance. The
  current deployment is not an autoscaling pool.
- [!] Cloudflare listed 19 named generations: 6 running and 13 inactive. Only
  one running generation can be selected, leaving five running generations to
  reconcile and stop.
- [ ] Measure gateway capture overhead with one warm capture-on/capture-off
  comparison before making a latency claim. R2 writes are already asynchronous.
- [ ] Decide later whether deterministic sampling is needed. Current behavior
  captures every eligible complete exchange; this is the minimal initial rule.

## Local Milk Man snapshot

- [x] Dashboard supervisor was alive on `127.0.0.1:8766` during the audit.
- [x] Current trajectory:
  `df36b6bc-1651-4f74-aa40-43da7a8a216a`
- [x] Selected driver: Baseten, `zai-org/GLM-5.3-Flash`, Chat Completions,
  maximum reasoning.
- [~] The trajectory previously completed a real tool-using GLM turn that read
  both repository HEADs.
- [!] Its latest turn ended `llm: response contained no assistant text`, exit 1.
  It changed no file, object, provider, or route.
- [x] The dashboard's status refresh is model-free and the supervisor can remain
  idle without inference consumption.
- [x] After removing the unimplemented endpoint declarations, the live API
  again reported 11 jobs and no job-contract error.
- [ ] Run one clean bounded GLM tool turn after the reconciled source is
  published.
- [ ] Current saved-memory count is zero. Retention code and historical proof
  exist, but the next useful decision should create the first current memory.
- [!] The private local process is the current credential trust boundary. Jobs
  inherit its environment. Do not claim per-child secret isolation until it is
  actually implemented; do not add a secret broker for this private phase.

## Remote object-memory inventory

Read-only inventory at audit time: 6,623 objects below `milk/v2/scopes/` across
seven scope UUIDs.

| Prefix | Objects | Meaning |
| --- | ---: | --- |
| `c` | 740 | completed gateway captures |
| `l` | 795 | per-capture classifications |
| `s` | 37 | summary objects and pointers |
| `readiness` | 22 | readiness objects and pointers |
| `e` | 188 | eval revisions, manifests, and shards |
| `d` | 31 | dataset manifests and splits |
| `m` | 8 | model manifests |
| `v` | 18 | evaluation outputs |
| `p` | 4 | unsigned proposals |
| `r` | 8 | signed route objects and pointers |
| `j` | 4,765 | immutable job attempts and results |
| `status` | 7 | disposable current projections |

Scope inventory:

| Scope | Total | Relevant state | Disposition |
| --- | ---: | --- | --- |
| `c2ab9c16-79cc-4c7f-955d-49871f240919` | 4,817 | 102 captures, 4,374 job artifacts, older large eval work | retain as historical; never splice into new proof |
| `c47a7dd1-05fb-47fc-bfbe-1ba014ffa77b` | 446 | 180 captures and a complete small route lineage | best full mechanics reference; not production qualification |
| `aeaa9585-74c8-43ea-b6e5-070b60c40619` | 386 | 106 captures, summary/readiness, parked eval pilots | current dashboard reference only; do not resume evals |
| `8d28cf6c-c711-48d0-a5d5-bc5b145e9b41` | 366 | historical mechanics | retain |
| `8cc33bba-6790-4701-8a88-b3ba565971ee` | 330 | historical mechanics | retain |
| `b6df8f84-bcc8-45a8-a89a-14350fdc1f23` | 259 | production-profile capture/summary and signed route history | status is stale; no learned production qualification |
| `2b08c7d1-5bfe-4f74-9979-c8eec35d73d4` | 19 | early mechanics | retain |

Current dashboard scope `aeaa9585-74c8-43ea-b6e5-070b60c40619`:

- [x] 106 complete captures and 106 processed classifications.
- [x] Summary `0630f2fb-6044-59f8-bb41-dcd5de25b876`, digest prefix
  `cb680bc7`, is current.
- [x] Readiness `9c730aa1-0f1a-5c9a-8e05-9f97d79eb5d7` is mechanics-ready
  and explicitly not statistically qualified.
- [x] No accepted current eval, dataset, model, evaluation, or proposal pointer
  exists.
- [~] Thirteen prepared shards contain 3,268 cases from a parked experiment,
  plus later small pilots. They are immutable research residue, not work to
  continue.

Production-profile scope `b6df8f84-bcc8-45a8-a89a-14350fdc1f23`:

- [x] Exact inventory contains 138 captures.
- [!] `status/current.json` reports only 115 captured and 100 processed, so its
  projection is stale and must be reconciled before display.
- [~] It has a 100-capture summary and signed route revision 7.
- [ ] It has not crossed production statistical qualification with independent
  customer traffic.

## Capability matrix

| Capability | Current assessment | Next proof |
| --- | --- | --- |
| Official SDK -> Parlor | `[x]` live for Responses and Chat Completions, including streaming | repeat both in fresh scope |
| Key -> scope UUID | `[x]` source and historical live proof | bind fresh mechanics key |
| Async two-sided capture | `[x]` live counters and exact historical object proof | exact fresh object reread |
| Summary/classification | `[x]` current 106-source checkpoint | fresh threshold checkpoint and idle replay |
| Deterministic readiness | `[x]` current mechanics result | fresh result from accepted sources |
| Useful eval generation | `[~]` 98/100 materially correct in best pilot; later pilot 60/64 clean | 100 sources times one case and human review |
| 10,000-case target | `[ ]` not generated as one accepted current contract | freeze reviewed contract, then 100 times 100 |
| Source-separated dataset | `[~]` small mechanics proven | current lineage with no split leakage |
| Qwen3.5-0.8B training | `[~]` one-step Baseten H100 mechanics proven | current dataset, exact pinned revision |
| BF16/dynamic FP8 comparison | `[~]` tiny mechanics proven | same current ordered DEV set |
| Static FP8 | `[~]` mechanics only | never select until independently qualified |
| Sealed winner | `[~]` tiny mechanics proven | exactly one current sealed run |
| Candidate proposal | `[~]` historical unsigned proposal proven | one current explicit provider |
| Signed canary/fallback/rollback/zero | `[~]` historical live mechanics proven | repeat same fresh lineage |
| Baseten zero capacity | `[~]` historical independent audit | confirm after current run |
| Modal zero capacity | `[~]` historical independent audit | confirm after current run |
| Managed GLM Milk Man driver | `[x]` Baseten GLM tool call proven | one clean post-publish turn |
| Owned Modal GLM endpoint | `[ ]` contract not implemented | append ensure/status/stop and prove via dashboard |
| Production-qualified learned route | `[ ]` no independent traffic lineage | repeat fixed loop after production readiness |

## Evaluation lessons retained

- [x] One captured conversation can generate 100 structurally valid cases.
- [~] The best inspected one-to-100 pilot produced 98 materially correct and 96
  clean cases. That proves mechanics, not sufficient diversity or usefulness.
- [!] The earlier 100,000-case v21 run was structurally valid but repetitive and
  template-heavy. It was correctly stopped and must not be resumed.
- [!] v25-v28 improved the prompt but still showed premise and completeness
  defects. Repeated prompt-version fan-out became the loop to avoid.
- [x] The next rational ratio is 100 independent sources times one case for a
  direct review, followed by the same frozen contract at 100 cases per source.
- [x] Provider structured output plus six deterministic checks is sufficient:
  valid JSON, exact count, unique case IDs, complete source coverage, expected
  answers present, and no obvious normalized duplicates.
- [x] Do not add an LLM validator or large semantic policy engine. Human review
  happens once before bulk spend.

## Historical evidence index

These reports are retained and their referenced SHA-256 digests matched during
the audit. Each is historical unless explicitly repeated on the new lineage.

| Evidence | Class | SHA-256 |
| --- | --- | --- |
| `milk-v2-local-postcut-20260901/report.json` | local mechanics | `750c9a8d3c728295184176c514e96393340f265df44420df7247713d584c1571` |
| `milk-v2-r2-20260901/report.json` | hosted object/replay mechanics | `7c96b77a387dbcce75ecbf4c696cebefc28d4f3e1f0d11c685007918f301169f` |
| `milk-v2-live-20260901/report.json` | live gateway mechanics | `cda2ed3e33acea77bef2c710fd64c558e033e3441426e10a245c6a8d45a70caa` |
| `milk-v2-protocol-native-20260902/report.json` | live SDK protocol mechanics | `7c988ce858176a2cd57a9c846ccb490bfd949b331a1793cfecf8c627f64503d` |
| `milk-v2-threshold100-provider-20260902/report.json` | paid training/evaluation mechanics | `64aea65f086da151ce975bea6c7080d403654e7896edf5712455b94ae3074d74` |
| `milk-v2-live-candidate-20260901/report.json` | live route/fallback/rollback mechanics | `33f94057a7ae1ef700d4d16cbb335d958c193d4365033cfad1b05836aa6cb889` |
| `milk-v2-baseten-log-audit-20260902/report.json` | paid-provider audit | `958bf46d4047440670b11527c997138902d6daf26bb8ba8e0062f69312246a54` |

Evidence root: `/Users/shantanu/milk-release-evidence` (approximately 272 MB,
30 report directories at audit time). Keep it local and content-free; publish
only redacted compact reports.

## Audit of the former tracker

The former tracker had 222 bracket claims: 213 checked and 9 open. A checked
box often meant "implemented once" or "historical mechanics," not current
end-to-end completion. That made it look approximately 96% complete while the
current 10,000-case lineage had not begun.

| Former section | Checked | Open | Disposition |
| --- | ---: | ---: | --- |
| Goal and current GLM focus | 5 | 4 | requirements moved to PRD/GOAL; duplicate GLM items removed |
| Starting point and execution decision | 26 | 0 | compressed into current snapshot and evidence classes |
| Dashboard/controller and status UI | 35 | 1 | current facts retained; incomplete endpoint marked open |
| P0-P4 | 52 | 0 | real source/local mechanics retained, not treated as release completion |
| P4B | 2 | 3 | useful eval work remains open under one 100-source review gate |
| P5-P7 | 41 | 1 | implementation/historical provider proof retained separately |
| P8-P9 | 42 | 0 | relabeled historical small-lineage mechanics |
| Provider follow-up | 10 | 0 | useful evidence retained; startup optimization is deferred |

Corrections made by this audit:

- [x] Replaced the stale $1,000 wording with a $500 supervised testing
  allowance and kept it out of product runtime logic.
- [x] Replaced "first live production vertical" with "live mechanics vertical."
- [x] Separated current proof from historical proofs and parked experiments.
- [x] Restored the implemented 11-job contract and made owned Modal Endpoint an
  additive goal.
- [x] Stopped treating R2 object count, dashboard rendering, or a checked box as
  route or production authority.
- [x] Kept the full old text recoverable in Git instead of creating another
  stale context file.

## Active work, in order

### P0 coherent source and operations

- [x] Centralize stable requirements in `PRD.md`.
- [x] Centralize the current execution sequence in `GOAL.md`.
- [x] Replace the mixed historical tracker with this evidence ledger.
- [x] Restore the working 11-job config contract locally.
- [x] Run narrow syntax/config checks and a secret scan.
- [ ] Commit and publish the coherent Milk Man baseline.
- [ ] Prove one clean managed-GLM dashboard tool turn.
- [ ] Stop five stale unselected Parlor container generations.

### P1 fresh data checkpoint

- [ ] Create a fresh mechanics scope and bind a key.
- [ ] Capture complete Responses and Chat Completions traffic for 100 held-out
  eval sources plus configured train sources.
- [ ] Run one remote summary/readiness job from the local dashboard.
- [ ] Verify exact counts, pointers, and a zero-call idle replay.

### P2 useful eval contract

- [ ] Generate 100 cases: one from each of 100 sources.
- [ ] Review once and record useful/defect counts.
- [ ] Freeze or minimally correct the contract in a new revision.

### P3 current 10,000-case lineage

- [ ] Generate exactly 100 cases from each accepted source.
- [ ] Complete missing-shard-only replay and publish one 10,000-case pointer.
- [ ] Build source-separated data; train pinned Qwen3.5-0.8B.
- [ ] Compare BF16 and dynamic FP8; run one sealed winner evaluation.

### P4 route and teardown

- [ ] Serve one explicitly selected provider candidate.
- [ ] Write unsigned proposal and prove operator-signed canary.
- [ ] Prove success, pre-byte fallback, rollback, signed zero, key removal, and
  independent Baseten/Modal zero capacity.

### P5 additive owned GLM driver

- [ ] Implement separate Modal Endpoint ensure/status/stop jobs and state.
- [ ] Select it through existing `LLM_*` after `ensure` succeeds.
- [ ] Prove one later dashboard tool turn, stop, absence, and compare observed
  performance/cost with managed Baseten.

### P6 public release and qualification

- [ ] Publish concise docs and redacted current-lineage evidence.
- [ ] Enforce owner-only merge controls without blocking forks, issues, or pull
  requests.
- [ ] Repeat the fixed loop on independently collected traffic before labeling
  any learned route production-qualified.

## Human-only inputs

- A production route requires the operator signing key at the signing step.
- Production qualification requires independently collected customer traffic.
- Account-specific custom-image access can reduce Baseten startup installation
  time, but it does not block the current weight-hydration path.
- GitHub branch protection/ruleset changes require repository-owner authority.

Nothing else currently justifies redefining the architecture, restarting an old
eval revision, or creating more scaffolding.
