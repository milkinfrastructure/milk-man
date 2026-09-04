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

- [x] The corrected product goal is autonomous, prompt-driven Milk Man: given
  an objective and configured environment, it uses Bash, existing or newly
  written scripts, prior results, and live measurements to operate and improve
  models or compute until complete or externally blocked.
- [x] The whiteboard traffic-to-model flywheel remains the flagship Milk
  application. Summary, eval, fine-tuning, RL, and signed routing are extensions
  of the general agent rather than prerequisites for proving its core loop.
- [x] Milk Parlor is a deployed, healthy Rust gateway. It is not a manager,
  scheduler, training service, or generic router.
- [x] Milk Man runs locally from Bash, has an always-on model-free dashboard
  supervisor, resumes trajectories, and can make OpenAI-compatible reasoning
  turns that invoke the current fixed tools and jobs.
- [x] Summary, readiness, eval, dataset, training, evaluation, candidate,
  proposal, route, fallback, rollback, and teardown mechanics have all run in
  at least one retained small lineage.
- [~] Those mechanics span older code and generated traffic. They do not prove
  one coherent current-code lineage or a production-qualified learned route.
- [x] Published Milk Man `38c1b9812e0182ec132d12a3da2460506fa9efd7`
  contains the coherent eleven-job baseline and one successful managed-GLM
  dashboard tool turn.
- [x] Local commit `ba5c62f47acf3454ca4180392b38fdc0066eca3f`
  adds the autonomous task contract, reusable script dispatch, persistent
  heartbeat, dashboard reporting, and their retained local proof. It is not
  published yet.
- [x] Local Milk Man completed a Chrome-prompted remote progress check and then
  authored and reused `bin/progress` across an automatic ten-second follow-up.
  Both readings were 106 captured / 106 summarized. Four useful memory entries
  are retained in trajectory `df36b6bc-1651-4f74-aa40-43da7a8a216a`.
- [x] The independent heartbeat survived a dashboard-server restart, stopped,
  and restarted from Bash with the same trajectory and no new model turn.
- [~] Idle backoff and timer continuation work locally. Failed result parsing
  did not duplicate the first inference call, but process restart during real
  asynchronous provider work remains unproven.
- [x] The first environment-selected P4 lifecycle served
  `Qwen/Qwen3-0.6B` on one Modal L4, completed three correct inference calls,
  stopped app `ap-joFFZzWQm7cFTdMJ7F0QGz`, and observed zero tasks and zero
  containers. This is a small lifecycle proof, not 120B or autotuning proof.

## Repository snapshot

Current source snapshot:

| Repository | Local state | Published state | Assessment |
| --- | --- | --- | --- |
| `milk-man` | `dd7b61ade`, plus this progress checkpoint | `38c1b9812e0182ec132d12a3da2460506fa9efd7` | heartbeat, serving, benchmark, native finish, and conversation replay fixes are committed locally, not pushed |
| `milk-parlor` | `37c0f892cee2bb03277fff6cc107312e36fda672` | same | clean and deployed |
| `milk-landing` | `db49fb7c436d5841d6b73a759a3bbe7604232adc` | same | clean and live |

Published Milk Man audit baseline:
`38c1b9812e0182ec132d12a3da2460506fa9efd7`.

- [x] Milk Man is no longer a GitHub fork. It retains a pinned, attributed
  minimal Headlong subset as implementation source.
- [x] Milk Parlor has no tracked Actions, test fixtures, model weights, Python
  runtime, or orchestration code.
- [x] Milk Man repository Actions are absent; jobs run from `bin/milk` and
  prompt-driven Headlong runs from `bin/man`.
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
- [x] Live check on 2026-09-04 returned status `ok`: Responses and Chat
  Completions configured; candidate bindings absent; capture writer alive; 106
  persisted and zero dropped.
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

- [x] Dashboard returned HTTP 200 on `127.0.0.1:8766` on 2026-09-04.
- [x] Current trajectory:
  `df36b6bc-1651-4f74-aa40-43da7a8a216a`
- [x] Selected driver: Baseten, `zai-org/GLM-5.3-Flash`, Chat Completions,
  maximum reasoning.
- [x] At 2026-09-04 18:59 UTC the trajectory completed a managed Baseten
  GLM-5.3-Flash turn at maximum reasoning. It ran exactly one
  `bin/milk status`, read the remote S3 scope, returned assistant text, and
  exited 0. The job result reported 106 captures, 106 processed, `next=eval`,
  `inference_calls=0`, and `provider_calls=0`.
- [x] The preceding failed turn was isolated to a successful HTTP response with
  no visible assistant content. It changed no file, object, provider, or route.
- [~] Exhausting the prior 16,384-token allowance is one hypothesis, not a
  proven cause because the raw provider body was not retained. Local changes
  raise the allowance and add bounded finish/usage diagnostics; recurrence and
  the diagnosis remain unproved.
- [x] The dashboard's status refresh is model-free and the supervisor can remain
  idle without inference consumption.
- [x] After removing the unimplemented endpoint declarations, the live API
  again reported 11 jobs and no job-contract error.
- [x] Run one clean bounded GLM tool turn after the reconciled source is
  published. Evidence: trajectory
  `df36b6bc-1651-4f74-aa40-43da7a8a216a`, 2026-09-04 18:59 UTC, exit 0.
- [x] Current private memory contains seven entries, including the retained
  small-model lifecycle result.
- [!] A preceding fenced-mode lifecycle attempt read source for 20 iterations
  without performing a provider action, then exited 70.
- [x] The first native Bash function turn launched the environment-configured
  `Qwen/Qwen3-0.6B` `serve-modal` job on one L4 at 2026-09-04 20:35:03 UTC.
  After repairing the serving image's missing Python runtime, the lifecycle
  reached inference and cleanup without relaunching the first completed call.
- [x] Retained `benchmark-run-{1,2,3}.json` records three of three exact-match
  successes at 1902.449, 1639.6, and 1722.826 ms. Each response reported 86
  output tokens; these are non-streaming end-to-end timings, not decode speed.
- [x] Modal app `ap-joFFZzWQm7cFTdMJ7F0QGz` is stopped; the independent final
  observation returned zero tasks and an empty container list.
- [x] The native finish path is live-proven. A Chrome closeout prompt at
  20:53:59 UTC read the three results and provider status, saved memory at
  20:54:07, emitted one factual final at 20:54:11, and returned the heartbeat
  to online idle at turn 12 without another deployment or inference call.
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
| High-level prompt -> existing job | `[x]` Chrome and Bash objectives chose and completed remote progress checks; one timer follow-up continued automatically | repeat an external operation without duplicating it |
| Repository-script jobs | `[x]` Milk Man authored and reused `bin/progress`; `serve-modal` executed through the generic executable catalog | reuse the same dispatch for the next model |
| Lightweight heartbeat | `[x]` zero-model idle backoff, timer continuation, dashboard restart, stop, and Bash resume worked | recover a real provider operation without duplicate work |
| Managed GLM Milk Man driver | `[x]` Baseten GLM status turn proven | autonomous multi-step task through the driver |
| General model lifecycle | `[~]` one env-selected Qwen/L4 lifecycle completed three correct calls and verified zero resources | repeat with the intended 120B workload without hardcoding it |
| Inference autotuning | `[~]` one fixed configuration has three retained end-to-end measurements | compare configurations, select one from results, clean losing resources |
| Different compute workload | `[ ]` harness generality not proven | complete a second workload without editing the engine |
| Official SDK -> Parlor | `[x]` live for Responses and Chat Completions, including streaming | retain as Milk application input |
| Key -> scope UUID | `[x]` source and historical live proof | reuse when the application needs a new scope |
| Async two-sided capture | `[x]` live counters and exact historical object proof | preserve during application work |
| Summary/classification | `[x]` current 106-source checkpoint | heartbeat-driven threshold and idle replay |
| Deterministic readiness | `[x]` current mechanics result | retain as application logic |
| Useful eval generation | `[~]` 98/100 materially correct in best pilot; later pilot 60/64 clean | inspect a small application sample before expansion |
| 10,000-case experiment | `[ ]` not generated as one accepted current contract | optional configured expansion after small output is useful |
| Source-separated dataset | `[~]` small mechanics proven | next training workload with no split leakage |
| Qwen3.5-0.8B SFT | `[~]` one-step Baseten H100 mechanics proven | run only as a selected application workload |
| Explicit RL experiment | `[ ]` existing SFT is not RL | rollout, reward/judge, recipe, baseline, and evaluation when requested |
| BF16/dynamic FP8 comparison | `[~]` tiny mechanics proven | same ordered evaluation set when selected |
| Static FP8 | `[~]` mechanics only | never select until independently qualified |
| Candidate proposal | `[~]` historical unsigned proposal proven | coherent application lineage when requested |
| Signed canary/fallback/rollback/zero | `[~]` historical live mechanics proven | repeat on a coherent application lineage |
| Provider cleanup | `[~]` historical Baseten and Modal zero-capacity audits | verify after each new lifecycle or tuning task |
| Production-qualified learned route | `[ ]` no independent traffic lineage | independent traffic after the application loop is fixed |

## Evaluation lessons retained

- [x] One captured conversation can generate 100 structurally valid cases.
- [~] The best inspected one-to-100 pilot produced 98 materially correct and 96
  clean cases. That proves mechanics, not sufficient diversity or usefulness.
- [!] The earlier 100,000-case v21 run was structurally valid but repetitive and
  template-heavy. It was correctly stopped and must not be resumed.
- [!] v25-v28 improved the prompt but still showed premise and completeness
  defects. Repeated prompt-version fan-out became the loop to avoid.
- [x] One retained application plan is 100 independent sources times one case
  for inspection, followed by the same accepted contract at 100 cases per
  source. It is experiment configuration, not a core Milk Man prerequisite.
- [x] Provider structured output plus six deterministic checks is sufficient:
  valid JSON, exact count, unique case IDs, complete source coverage, expected
  answers present, and no obvious normalized duplicates.
- [x] Do not add an LLM validator or large semantic policy engine. Inspect a
  small result before optional bulk spend.

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
end-to-end completion. It also treated one eval/training lineage as the product
goal instead of one application of the autonomous harness.

| Former section | Checked | Open | Disposition |
| --- | ---: | ---: | --- |
| Goal and current GLM focus | 5 | 4 | requirements moved to PRD/GOAL; duplicate GLM items removed |
| Starting point and execution decision | 26 | 0 | compressed into current snapshot and evidence classes |
| Dashboard/controller and status UI | 35 | 1 | current facts retained; incomplete endpoint marked open |
| P0-P4 | 52 | 0 | real source/local mechanics retained, not treated as release completion |
| P4B | 2 | 3 | useful eval evidence retained as application work |
| P5-P7 | 41 | 1 | implementation/historical provider proof retained separately |
| P8-P9 | 42 | 0 | relabeled historical small-lineage mechanics |
| Provider follow-up | 10 | 0 | useful lifecycle evidence retained; adaptive optimization remains open |

Corrections made by this audit:

- [x] Replaced the stale $1,000 wording with a $500 development testing
  allowance and kept it out of product runtime logic.
- [x] Replaced "first live production vertical" with "live mechanics vertical."
- [x] Separated current proof from historical proofs and parked experiments.
- [x] Restored the implemented eleven-job baseline. It is retained capability,
  not the final extensibility boundary.
- [x] Stopped treating R2 object count, dashboard rendering, or a checked box as
  route or production authority.
- [x] Kept the full old text recoverable in Git instead of creating another
  stale context file.

## Active work, in order

### P0 align source and contract

- [x] Publish Milk Man baseline
  `38c1b9812e0182ec132d12a3da2460506fa9efd7` and retain its eleven
  working jobs.
- [x] Prove one managed-GLM dashboard tool turn against remote object state.
- [x] Align `AGENTS.md`, `GOAL.md`, `PRD.md`, `prompts/develop.md`, and this
  tracker around autonomous prompt-driven Bash execution.
- [x] Local commit `ba5c62f47acf3454ca4180392b38fdc0066eca3f`
  retains repository-script dispatch and the heartbeat; P1-P3 below record the
  Chrome and Bash proof. The commit is not published yet.
- [x] Restart the dashboard from the aligned source and verify truthful task,
  trajectory, driver, heartbeat, current activity, and next-wake state.
- [x] Chrome shows an always-visible heartbeat strip above chat: state light,
  last check, next check, task wakeups, and idle checks. Disconnects are labeled
  as lost visibility, not proof that the underlying task stopped.
- [x] Local commit `44502826b` separates heartbeat liveness from dashboard
  connectivity. Chrome showed stopped, starting, running, and waiting states;
  the dashboard restart preserved the active deployment and heartbeat owner.

### P1 one autonomous existing-job task

- [x] A Chrome prompt requested remote progress and one follow-up; Milk Man
  selected status jobs, reported 106/106, and completed without another human
  instruction. Retained trajectory: `df36b6bc-1651-4f74-aa40-43da7a8a216a`.
- [x] Both entrypoints now stream to the same private trajectory run log. Chrome
  displayed the CLI task's actual command, JSON result, and final message.
- [x] A complete Bash-started objective ran `bin/progress`, reported 106/106,
  saved memory, and finished at 2026-09-04 20:22:55 UTC (heartbeat turn 5).
- [ ] Repeat it and prove retained state prevents duplicate external work.

### P2 reusable script extensibility

- [x] The registered `serve-modal` executable completed deployment, inference,
  and cleanup through the generic catalog without another fixed Python handler.
- [x] Chrome asked for a reusable compact progress command. Milk Man wrote
  `bin/progress`, ran it against remote R2, yielded to a timer, reused it on
  automatic continuation, compared unchanged 106/106 counts, and saved memory.
- [x] No engine change was needed for this script. Codex tightened propagation
  of upstream failures before retaining it; executable-catalog proof follows.

### P3 lightweight heartbeat continuity

- [x] At 21:03 UTC the 120B task registered its read-only status watch and
  yielded automatically without a model-written `FINAL`. Polls advanced from
  64 to 66 with task wakeups fixed at 15 and no model call while waiting.
- [x] During the real Modal deployment, the retained status watch advanced idle
  checks from 49 to 51 with task wakeups fixed at 10. Codex resumed that watch
  after the driver failed; the provider worker was not restarted.
- [x] Live idle polling advanced from 9 to 13 with model turns fixed at 2.
  A later task automatically resumed once at its timer, finished at turn 4,
  and returned to idle. Idle code runs no store scan or model request.
- [x] Isolated no-model checks cover owner-lock exclusion, interrupted-task
  recovery, stale-prompt rejection, durable inputs, and replaced-watch races.
  These checks do not prove recovery of a real provider deployment.
- [x] The Modal deployment status change resumed turn 11 automatically, which
  measured inference and stopped the app. The earlier failed turn needed a
  manually restored watch; uninterrupted launch-to-wait still needs proof.
- [~] Restarted owner 409 during a real 45-second scheduled wait. Owner 1076
  retained the exact deadline and task, resumed once (turn 6 to 7), ran the
  progress script, and finished at 20:24:27 UTC. Provider-resource recovery is
  still to be proven with the deployment workload.
- [x] Terminated dashboard PID 93960 and started a new server; heartbeat PID
  94338 remained alive. A subsequent explicit stop removed it, and Bash resume
  created a new owner for the same trajectory without replaying finished work.

### P4 general model and compute lifecycle

- [x] The first vLLM image built, but Modal could not detect its Python runtime.
  The serving image now explicitly adds Python 3.12. Milk Man stopped the old
  profile, observed zero containers, and launched corrected profile
  `68c05ebcbf60` at 20:42 UTC.
- [~] A fixed Modal GLM controller historically proved create, inference
  handoff, stop, and zero; it is not yet a general lifecycle.
- [!] A fenced-mode attempt read source for 20 iterations without taking the
  provider action and exited 70.
- [x] At 2026-09-04 20:35:03 UTC, a native Bash function turn launched the
  environment-configured `Qwen/Qwen3-0.6B` `serve-modal` job on one Modal L4.
- [x] Three retained benchmark files each contain one successful exact-match
  inference: 1902.449, 1639.6, and 1722.826 ms, with 86 output tokens each.
  A failed report parse after the first response did not duplicate that call.
- [x] Stopped Modal app `ap-joFFZzWQm7cFTdMJ7F0QGz`; an independent check
  observed zero tasks and zero containers.
- [x] A Chrome closeout prompt used the native finish path to read status and
  memory, report the three results, and return to online idle at turn 12. It
  made no new deployment or inference call.
- [ ] Select model, revision, provider, runtime, GPU type/count, serving
  arguments, and cache through environment variables.
- [ ] Repeat with the intended 120B proving workload without hardcoding it into
  the harness.
- [!] The first 120B objective reread setup for 15 turns and then returned no
  function call. It launched no deployment. Native tool history was being
  flattened into ordinary text; correct that conversation contract before
  repeating this objective.
- [x] Native replay now retains assistant call IDs and reasoning, paired with
  tool results. The next live turn created and repaired the private 120B
  profile in three calls rather than repeating the source audit.
- [~] That turn then returned a malformed Bash argument. The runtime now gives
  the model a matching tool error so it can repair the call; a narrow local
  replay recovered without executing the invalid command.
- [x] At 21:02:56 UTC Milk Man launched `milk-serve-845fd60ed341` for
  `openai/gpt-oss-120b` on one H100 and registered its heartbeat watch in two
  calls. All 22 model files finished downloading to the reusable cache at
  21:09:37 UTC. Unchanged waiting checks made no driver-model call.
- [!] H100 startup failed while packing MXFP4 weights: 70.40 GiB allocated,
  7.59 GiB reserved, and another 1.01 GiB allocation failed on the 79.18 GiB
  device. Modal retried the failed startup while the local readiness loop
  kept waiting. This attempt produced no successful inference.
- [x] After a Chrome correction, Milk Man stopped the local worker and
  `ap-t8u120tx5wCSovOvf0fq6X`; `stop-attempt2.log` records stopped and zero
  containers. Model-cache files and prior Qwen receipts were retained.
- [!] Two recovery turns exhausted their 20-call allowance, largely reading
  source. The 120B lifecycle is not autonomously complete. Fix startup failure
  reporting before another attempt; use a sufficient-memory GPU next.
- [x] An unrelated parallel catalog edit briefly broke job discovery. Milk Man
  backed up that edit privately and restored the working catalog before
  resuming its wait. Keep catalog changes out of active provider runs.

### P5 inference autotuning

- [~] One Qwen/L4 configuration has three retained non-streaming end-to-end
  measurements. No second configuration, adaptive decision, or cost comparison
  has run.
- [ ] Give Milk Man a measurable latency/throughput/correctness/cost objective.
- [ ] Run comparable configurations, persist exact identities and metrics, and
  let later trials respond to measured results.
- [ ] Retain the best configuration meeting the objective, use its endpoint,
  stop losing trials, and verify their resources are absent.
- [ ] Resume without rerunning completed experiments.

### P6 continuity and generality

- [ ] Complete a second model or compute workload through reused or newly
  authored scripts without editing the harness engine.
- [ ] Preserve the objective, measurements, conclusions, and reusable script
  across restart.

### P7 Milk whiteboard application extensions

- [ ] Reconcile useful existing traffic and summary objects before new paid
  generation.
- [ ] Let the heartbeat progress a configured summary threshold with zero-call
  idle behavior.
- [ ] Reuse or add generation, scoring/reward, filtering, split, dataset,
  training, merge, quantization, evaluation, serving, and cleanup scripts only
  as the chosen application needs them.
- [ ] Inspect a small output before optional expansion. The prior 100 x 100
  generation target remains one configurable experiment.
- [ ] Keep Qwen3.5-0.8B SFT and a real RL experiment distinct.
- [ ] Complete a coherent application lineage through proposal, signed route,
  candidate success, fallback, rollback, signed zero, and provider cleanup.

### P8 publish, operate, and qualify

- [ ] Stop five stale unselected Parlor generations after exact identity
  reconciliation.
- [ ] Publish concise docs and redacted evidence after the autonomous core is
  proven.
- [ ] Enforce owner-only merge controls without blocking forks, issues, or pull
  requests.
- [ ] Use independently collected traffic before labeling a learned route
  production-qualified.

## Human-only inputs

- A production route requires the operator signing key at the signing step.
- Production qualification requires independently collected customer traffic.
- Account-specific custom-image access can reduce Baseten startup installation
  time, but it does not block the current weight-hydration path.
- GitHub branch protection/ruleset changes require repository-owner authority.

These are application/release boundaries, not per-command gates for an already
configured Milk Man task. Nothing else currently justifies restarting an old
eval revision or creating more scaffolding.
