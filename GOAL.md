# Current Milk execution goal

## Outcome

Make Milk Man an autonomous, prompt-driven Bash agent that can deploy,
operate, optimize, and research models and compute. Given one objective and an
environment, it must inspect available resources and prior results, reuse or
create scripts, execute work, measure it, adapt, persist useful state, and
continue until the objective is complete or a specific external blocker is
proven.

The dashboard is an optional view and control surface. The same task must run
from Bash without the dashboard. Human supervision is useful while developing
Milk Man, but it is not a runtime requirement and must not be encoded as a
per-command gate.

The Milk Parlor traffic-to-model flywheel remains the flagship application:

```text
official OpenAI SDK -> Milk Parlor -> response + scoped object memory
                                             |
                                             v
Milk Man -> summaries -> evals/data -> training/research -> serving -> route
```

Fine-tuning, reinforcement learning, and signed routing are extensions of the
agent's general compute and research loop. They do not block proving the core
agent.

The product north star is continuous autoresearch for each scope UUID: learn
from that scope's captured traffic and pursue an open-source model that beats
the best measured baseline for its workload and operating constraints. Each
scope retains its objective, evaluation set, current best result, experiment
history, and next action. Milk Man uses the same jobs to generate useful data,
adapt models, tune inference, compare results, and repeat as new data arrives.
State-of-the-art is a measured target, not a guaranteed outcome or a claim
inferred from synthetic data. This applies equally to application traffic and
Milk Man's own research trajectories.

Milk Man's own reasoning traffic must also pass through Milk Parlor. Give this
deployment a separate operator key and UUIDv6 scope, named
`milk-man-autoresearch`, so its requests, responses, tool calls, and returned
tool results become useful data for improving its research behavior. Preserve
task/trajectory grouping; repeated context is not independent conversation
data. Start with capture and one inspected task, then reuse the existing
summary and learning jobs. The OpenAI driver defaults to `gpt-6-astra`; GLM
remains an independent environment-selected option. Switch a running task at a
safe turn boundary without repeating completed work.

This file is the execution order. [PRD.md](PRD.md) is the stable product
contract. [goal_tracker.md](goal_tracker.md) is the evidence ledger.

## Audit starting point: 2026-09-04

These are the audit's initial observations. Current publication and deployment
are recorded in the tracker's repository and live snapshots.

- [x] Milk Parlor `37c0f892cee2bb03277fff6cc107312e36fda672` is
  published, deployed, and healthy. Both supported OpenAI protocols are live;
  its audited process reported 106 completed and persisted exchanges with zero
  capture drops.
- [x] Milk Landing `db49fb7c436d5841d6b73a759a3bbe7604232adc` is
  published and live.
- [x] Milk Man public `main` is
  `38c1b9812e0182ec132d12a3da2460506fa9efd7`. It runs Headlong locally
  from Bash, resumes trajectories, exposes a dashboard, reads remote object
  storage, and has eleven implemented Milk jobs.
- [x] Managed Baseten `zai-org/GLM-5.3-Flash` completed one dashboard turn at
  maximum reasoning, invoked `bin/milk status`, returned assistant text, and
  exited zero in trajectory `df36b6bc-1651-4f74-aa40-43da7a8a216a`.
- [~] Existing object memory contains historical summaries, evals, training,
  candidate, route, fallback, rollback, and teardown mechanics. Those results
  prove useful functions, not one current production-qualified lineage.
- [~] Local changes now support script jobs and a dashboard-independent
  heartbeat. Chrome-driven status, script reuse, idle checks, two Modal model
  lifecycles, and restart against a ready provider resource have run. Fully
  autonomous 120B recovery remains unproven. Baseten-owned Qwen/L4 now
  completed three requests and verified shutdown; empty reasoning tags in
  answer text still need a serving-configuration correction. A small
  comparable inference A/B run selected CUDA graphs and
  stopped both deployments, with corrections; see the tracker for evidence.
- [x] Reconciled Cloudflare generations at 23:30 UTC: only the selected
  `parlor-d82c3cd-capture` instance is running; the other 20 are inactive.
  No stop or deletion was needed.

Do not discard these implementations or restart large generation work. Adapt
the current code in small working slices.

## Execution rules

1. Preserve Headlong's reasoning -> Bash -> result loop. Bash is the universal
   execution boundary; Milk jobs are reusable tools, not the limit of what the
   agent can do.
2. One high-level prompt authorizes the in-scope steps needed to complete it.
   Milk Man may inspect, edit, deploy, benchmark, tune, wait, recover, and
   clean up without requiring the human to name each command.
3. Reuse existing scripts first. If a workload is missing or broken, Milk Man
   may write or repair the smallest repository-owned Bash or Python script,
   execute it, and retain it for reuse.
4. A reusable job declares its purpose, inputs, required and optional
   environment names, status, and cleanup. Adding a job must not require adding
   another branch to a central handler enum.
5. Environment variables select object stores, inference endpoints, models,
   providers, credentials, GPU resources, runtimes, and optimization targets.
   Secret values may enter the private process but never Git, prompts, logs,
   dashboard payloads, or stored public evidence.
6. Managed APIs and owned deployments are independent choices. Provider
   failures do not silently select another provider.
7. Keep one lightweight heartbeat owner for an active task. Idle checks inspect
   only known job/resource state and changed object-store markers, invoke no
   model, and back off through an environment-configured interval.
8. Persist the active objective, trajectory, scripts used, resource IDs,
   configuration, observations, conclusions, and next wake. Resume must not
   repeat completed experiments or create duplicate resources.
9. Models, providers, GPU types, counts, and serving stacks are configurable.
   GLM Flash, a 120B model, and Qwen are initial proving workloads, not
   architectural constants.
10. Keep model weights out of Git and lightweight runtime images. Hydrate a
    pinned revision at runtime or reuse a provider cache or volume.
11. Use direct execution and measured results. Patch the first real failure;
    do not add a broad test framework, duplicate orchestrator, database, queue,
    or speculative provider framework.
12. The existing $500 authorization limits this development proof, not product
    behavior. Record provider usage and do not exceed it.
13. Preserve immutable Milk objects and small conditional current pointers.
    Historical and synthetic mechanics never become production evidence by
    assertion.

## P0 — align the operating contract

- [x] Publish the coherent Milk Man baseline and recover the implemented
  eleven-job surface.
- [x] Prove one real managed-GLM dashboard tool turn against remote object
  state.
- [x] Align `AGENTS.md`, `PRD.md`, `GOAL.md`, `prompts/develop.md`, the
  dashboard language, and the tracker around autonomous prompt execution.
- [x] Record the current eleven jobs as existing capabilities, not a permanent
  allowlist or completion boundary.
- [x] Restart the dashboard from the aligned source and verify that it reports
  the active task, trajectory, driver, heartbeat, current activity, and next
  wake without exposing secrets.

Acceptance: documentation and runtime behavior agree that a high-level task,
not a sequence of human-issued commands, drives Milk Man.

## P1 — complete one autonomous task

- [x] Route the driver through Parlor using its own Milk key, prove the
  request/response and tool sequence in its UUIDv6 scope, and show the selected
  gateway connection and heartbeat in the dashboard. Preserve other scopes.
  Live proof on 2026-09-04: Astra through Responses; all five keys still
  authenticate; eleven exchanges retained, seven with the same trajectory ID.

- [x] Remove the prompt rule that a Milk job must be named by the human.
- [x] Keep the system prompt short: inspect state once, choose the next useful
  action, execute it through Bash, observe the result, and continue.
- [x] Through dashboard chat, give Milk Man one bounded objective that requires
  an existing job but does not prescribe its commands.
- [x] Verify Milk Man chooses and runs the job, streams readable progress,
  handles its result, saves useful state, and reports completion without
  manual command-by-command steering.
- [x] Run the same objective from Bash without the dashboard.
- [x] On a repeated run, recognize the retained result instead of repeating
  the external work. The 100-exchange summary replay retained its checkpoint,
  returned idle, and made zero inference/provider calls.

Acceptance: one prompt becomes one completed multi-step task through both user
interfaces, with one retained trajectory and no duplicate operation.

## P2 — make jobs extensible

- [x] Adapt the existing job registry so a reviewed repository-relative script
  can be discovered and invoked without extending `milk_v2.runner`'s central
  handler list. Keep the current Python handlers available during the change.
- [x] Use the existing configuration surface rather than creating a separate
  plugin or workflow framework. A job entry may name only a script inside the
  repository and the environment names it needs; model-provided paths or shell
  fragments are not configuration.
- [x] Standardize the small process contract: arguments in, inherited declared
  environment, progress on stderr, one final JSON result on stdout, plus
  explicit status and cleanup when the job owns external resources.
- [x] Give Milk Man a small objective for which no current job exists. Verify
  it creates or adapts one script, executes it, repairs one observed failure if
  needed, and retains the working script.
- [x] Repeat the objective and reuse the script without changing the Headlong
  loop or runner core.
- [x] Give the agent compact job definitions and verified checkpoint facts.
  Chrome-prompted Milk Man used the read-only checkpoint job to report retained
  R2 counts and the missing tool-aware training path. Two earlier source-reading
  trials exhausted their reply allowances; retain them as failures, not wins.

Acceptance: an unseen workload becomes a reusable tool through a small script,
not another bespoke orchestration branch.

## P3 — add the durable lightweight heartbeat

- [x] Run the heartbeat independently of the browser. Closing or refreshing
  the dashboard must not stop the active task.
- [x] Configure initial interval, maximum interval, and idle backoff with
  environment variables.
- [x] Hold one lock/lease per active task and persist its objective, trajectory,
  current activity, resource IDs, last observation, and next wake time.
- [x] Wake on a new prompt, scheduled review, changed object marker, completed
  or failed asynchronous job, or measured service regression.
- [x] Invoke no model while idle. Check saved metadata and bound any capture
  listing to the next threshold within this scope, never the whole bucket.
  Send compact changed results when reasoning resumes.
- [x] Idle cycles, timer restart, provider status wake, and owner restart
  during real provider startup are proven. The same detached worker and
  saved watch survived; the restored watch resumed automatically. This does
  not erase earlier corrections needed to get the experiment launched.

Acceptance: Milk Man remains available and resumes useful work at low idle cost
without a separate scheduler service.

## P4 — general model and compute lifecycle

- [~] Refactor the current fixed controller lifecycle into reusable,
  provider-native scripts for ensure/reuse, status/logs, inference smoke, and
  stop. Both paths ran live; Baseten-owned activation, three requests, and
  verified shutdown completed. Its exact-answer check correctly failed on
  empty reasoning tags, confirmed from saved hashes without further inference.
- [~] Select provider, model and revision, API mode, runtime/image, GPU
  type/count, tensor parallelism, context, batching, cache/volume, region, and
  endpoint identity through environment variables. The completed Modal runs
  proved the model, revision, runtime, GPU, cache, and serving-argument subset.
- [x] Keep Baseten managed inference, Baseten-owned resources, and Modal-owned
  resources available independently. Do not encode an automatic fallback.
- [x] Set the existing Baseten vLLM arguments to separate Qwen reasoning
  (`--reasoning-parser qwen3`) for the next selected serving run. Preserve the
  old failed receipt and use the resulting new profile identity. Do not change
  the exact-answer comparison or repeat completed calls to diagnose it.
  Corrected deployment `wxe4k60` returned three exact answers and was
  independently observed INACTIVE with zero replicas. Final chat reporting
  needed a follow-up after a gateway HTTP 500; retain that recovery gap.
- [x] First prove the lifecycle on an inexpensive model: inspect existing
  state, create or reuse one deployment, call it, inspect failure if any, and
  stop or retain it according to the prompt.
- [x] Repeat with the intended 120B workload. It reused the weight cache and
  weight-free runtime image, made three correct calls, and returned to zero;
  Codex corrections were still required during the sequence.
- [~] The selected 120B endpoint powered a fresh native Milk Man child through
  a real research-status task. Switching the parent's active trajectory to
  that endpoint and capturing its traffic through Parlor remains unproved.
- [x] A later Chrome checkpoint task completed without command-by-command
  correction: owned 120B startup, heartbeat resume, one native child task,
  automatic stop, and an independent zero-container observation. The child
  repaired one malformed finish call. This is task execution, not a quality win.

Acceptance: a prompt can make Milk Man operate a real model lifecycle without
hardcoding that model or provider into the harness.

## P5 — inference autotuning

- [x] Accept a measurable objective such as minimum throughput subject to a
  latency, correctness, GPU, or cost constraint.
- [ ] Have Milk Man propose the next configuration from prior measurements,
  execute it, and capture cold start, time to first token, output tokens per
  second, p50/p95 latency, errors/OOM, output correctness, and compute cost.
- [x] Compare like-for-like requests and concurrency. Persist exact model,
  revision, runtime, resource, serving arguments, endpoint identity, metrics,
  and conclusion for every trial.
- [~] Milk Man proposed prefix caching after the CUDA-graphs result, measured
  it on the same tiny workload, rejected the slower setting, and saved the
  result. Corrections were needed; representative unassisted research remains
  open rather than being inferred from this serving check.
- [x] Retain or reuse the best configuration that meets the task objective;
  stop losing trials and verify their resources are absent.
- [x] Demonstrate a successful native Milk Man turn through the selected
  endpoint. The 120B child read research status and finished successfully;
  the Astra parent remained on Parlor.
- [x] Candidate-only recovery reused the completed baseline without new
  baseline inference. The earlier failed receipt remains unchanged; see the
  tracker for the required stop-condition fix and Chrome correction.

Acceptance: Milk Man improves a live inference configuration from evidence and
leaves one requested winner or zero resources according to the prompt.

## P6 — prove continuity and generality

- [x] Restart during an active research task and resume its trajectory,
  resources, measurements, and next experiment without duplication. Owner
  9907 resumed the same task/watch while detached workers 8869/8870 continued
  the one pending 120B startup. No second launch was observed.
- [x] Replace ad-hoc background shells with a reusable detached-command
  helper. Local execution proved that it does not inherit the heartbeat's
  process group or owner lock and that replay does not launch again. Apply it
  to the next asynchronous provider task before proving owner restart.
- [x] Give Milk Man a different model or compute objective. It may reuse,
  adapt, or create scripts, but must not require an edit to the harness engine.
- [x] Verify the second workload completes, leaves reusable code and retained
  conclusions, and cleans up or preserves resources as requested. Qwen/L4 and
  120B/H200 both completed and returned to zero; the 120B task was not unassisted.

Acceptance: the agent is a general research and compute operator, not a GLM,
120B, Qwen, Modal, Baseten, or Milk-pipeline special case.

## P7 — extend the Milk whiteboard application

Build these capabilities with the same scripts, heartbeat, state, and
optimization loop. Reuse existing R2 objects and historical implementations;
do not restart parked large generation runs.

- [x] Store each scope's research objective, targets, experiment references,
  next action, and planned wake in object storage through a registered job.
  Chrome-prompted Milk Man saved its own scope's record, replayed the same
  write unchanged, and registered a read-only heartbeat watch. The dashboard
  reads the same record; no new orchestrator was added.
- [ ] Bind the record to measured baseline and candidate results on untouched
  evaluation data. Its baseline, evaluation, and best fields are currently
  unknown; saved notes alone do not qualify a winner.
- [ ] Prove one small scope-specific research iteration: inspect captured
  data, choose an experiment, run existing jobs, compare on the same held-out
  tasks, retain the result even if it loses, and select the next useful action.
  New traffic must resume this loop without restarting completed work.

- [~] Parlor already authenticates official OpenAI SDK traffic, streams both
  supported protocols, and writes scoped request/response objects
  asynchronously.
- [~] Summary, readiness, eval, dataset, Qwen3.5-0.8B training, model
  comparison, proposal, routing, fallback, rollback, and teardown have each
  run in historical mechanics lineages.
- [x] Reconcile retained traffic before new generation: Chrome-prompted Milk Man
  advanced the 20-exchange checkpoint to 100 using two summary inference calls.
  Eight examples were classified; all 100 exchanges carry tools. Independent
  digest and ancestry reads agree. Readiness remains false; this is not a
  trained or improved model.
- [~] Preserve native assistant examples without flattening tool history.
  `native-capture` extracted one pinned Responses exchange into 28 context
  messages, two tools, and one next assistant tool-call target. Prior tool
  results remain paired; hidden reasoning is explicitly omitted. Native
  dataset selection and assistant-only training are now demonstrated below.
  Held-out agent-task evaluation remains unfinished; extraction does not
  establish task success.
- [~] `native-dataset` now derives four examples from the saved 100-exchange
  summary: three train, one DEV, zero calibration/sealed. R2 hashes and whole
  task separation were verified; replay makes zero capture reads or model and
  provider calls. The actual Qwen tokenizer preserves tool history and masks
  context, leaving only new assistant targets for SFT. One history needs
  12,954 tokens; explicit native training supports a larger context without
  truncation. The existing trainer accepts the exact native manifest through
  environment variables and retains its results separately from text evals.
  The first submitted H100 job failed allocating full-sequence training
  logits. The corrected run `wg8glgq` completed three steps on one H100,
  projecting only assistant-target positions without shortening context.
  Milk Man collected model `e7718471-f9fd-569f-b169-ec4a6cfdd2ae` and its
  result. Replaying unchanged made zero inference/provider calls. Loss on
  one held-out example fell from 1.1153 to 1.0929; this does not prove better
  task completion. One Codex correction separated HTTP timeout from the job
  deadline. Keep the original failure intact. Native-model serving, held-out
  task comparison and Chrome-prompted reuse remain unproven.
- [~] Summary execution/resume and zero-call replay are proven. The heartbeat
  now checks summary milestones independently of a task's resource wait.
  The resumed live owner counted below threshold with no model turn or job
  launch. An automatic crossed-threshold run remains to be observed.
- [~] With `MILK_AUTO_SUMMARY=1`, count saved objects in the existing heartbeat
  and directly run the summary job when `MILK_SUMMARY_THRESHOLDS` is crossed.
  No driver reasoning is required for counting or dispatch. Keep other job waits
  intact, handle an already-reached milestone, and skip saved milestones.
  Reuse the existing background runner; do not add another service.
  Show waiting, due and saved separately in the dashboard; claim running only
  from an actual job observation. Prove one crossing and one idle replay.
- [ ] Add or reuse scripts for eval generation, synthetic rollouts, scoring or
  rewards, filtering/deduplication, source-group splitting, dataset building,
  training, merging, quantization, evaluation, serving, and cleanup.
- [ ] Prove each required job with a small, inspected output before increasing
  volume. The prior 100-conversation x 100-case target is one configurable
  experiment, not a core runtime invariant.
- [ ] Keep Qwen3.5-0.8B as the first student workload. SFT is the current
  demonstrated training mechanic; do not call it RL.
- [ ] Add an explicit RL experiment only when needed: rollout generation,
  reward/judge output, training recipe, baseline, evaluation, and result must
  be independently visible.
- [ ] Complete one coherent application lineage through an unsigned proposal,
  operator-signed canary, candidate success, pre-byte fallback, rollback,
  signed zero route, and provider cleanup.

Acceptance: the whiteboard flywheel is one complete application of the general
Milk Man engine, with fine-tuning and RL represented truthfully.

## P8 — publish and operate

- [x] Reconcile unselected Parlor generations and retain the selected live
  instance. The complete live list shows one running and 20 inactive.
- [ ] Keep the local dashboard and public docs accurate for someone with no
  prior context. Show the active prompt, heartbeat, logs, environment-name
  readiness, resources, measurements, object progress, and cleanup state.
- [x] Preserve the original dependency-free Milk HTML/CSS design. The local
  dashboard adds accessible help and inline detail without new dependencies.
- [ ] Make focused commits, push validated source, deploy the updated local and
  hosted surfaces, and record exact revisions and live evidence in the tracker.
- [ ] Preserve the distinction between historical mechanics, current hosted
  execution, and production-qualified customer traffic.

## Stop conditions

Stop only when the objective is complete or a concrete external dependency is
unavailable: required credentials, provider/account capability, source data,
or an operator-held route signature. Record the exact state needed to resume.
Do not substitute repeated audits, unchanged polling, silent provider fallback,
or another abstraction for progress.
