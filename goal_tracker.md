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

- [x] The dashboard now exposes the watched model server's saved status and
  replica count, with copyable IDs in inline details. Chrome verified the
  actual Baseten BUILDING observation; restarting only the dashboard left
  heartbeat owner 9907 and its task/watch running. No extra provider polling
  or dependencies were added.
- [~] Chrome-prompted Baseten-owned Qwen3-0.6B deployment `qj7d9z2` on model
  `w7mpx8dw` built successfully with one L4, minimum zero and maximum one
  replica. The model loaded and began vLLM compilation, but did not become
  ready before the proof cutoff. Zero benchmark calls ran. Milk Man stopped
  it; an independent provider read confirmed INACTIVE and zero active replicas.
  Cleanup receipt SHA-256:
  `649ca420d4cb5bb6742f84dac36608ae2e3e20b8cba507d67ca2143460fb2f56`.
  Private run: `baseten-owned-qwen3-06b-c1899de-v0181`. A next attempt can
  reactivate this already-built deployment; no duplicate model or rebuild is
  needed. Owned Baseten inference remains unproven.
- [!] This task needed one correction after repeated source reads. Codex also
  corrected the private benchmark base URL before execution. Later the agent
  used timer-only status reviews instead of keeping its read-only watch.
  Prompt guidance now addresses both patterns; unassisted correction remains
  to be observed. Neither successful submission nor shutdown proves inference.
- [x] Local dashboard separates the active chat goal from saved traffic stages.
  Commands stay folded; summaries have keyboard/tap help and clickable
  thresholds; research shows conclusions before measurements and references.
  Chrome verified the live page, help controls, real summary, and research
  navigation. Original palette and embossed controls remain; no dependencies
  or unit-test suite added. Unknown watched-job status is displayed explicitly.
- [x] Added `native-trial`: one pinned visible context, one model request,
  no saved answer sent and no returned command executed. Real Astra trial
  `7ec4d4a1063baaa759182e142ef37448a82d5022c9b15c8aba82b8204842a163`
  returned a valid action in 13.382 seconds (11,655 total tokens). Its exact-ID
  replay made zero inference calls. Result SHA-256:
  `7b1bac6692436b974421686e4151fbfddb8f157d0d8ae6d4c150497f5aff6b21`.
  This source belongs to the training split; it is not a held-out quality win.
- [x] Dashboard UI `7362ec915` is published and running locally. Chrome verified
  separate chat/data/experiments/settings/setup views, setting-specific help,
  readable replies, saved comparisons, and draft-only task buttons. Landing
  and docs `74a87c0` are deployed; production content matches the local files.
  Idle checks continued without a model turn. No provider work was started
  by the UI changes.
- [~] Milk Man chose prefix caching as its next serving experiment, but needed
  a follow-up to stop repeated contract reads. Its precreated empty working
  directory then prevented launch. `bin/background` now claims an empty
  private directory once; local completion and no-duplicate replay passed.
  Codex resumed the same saved worker, not a new experiment. The sequential
  baseline/candidate comparison is now complete: eight requests total, with
  the four completed baseline calls reused during candidate-only recovery.
  Mean full-reply latency rose from 566.56 to 915.21 ms; first visible text
  rose from 545.18 to 909.13 ms. The candidate lost. Both configurations
  returned four correct tiny-workload answers, including warmups. This is
  not a broad quality finding or fully unassisted research proof.
- [x] Milk Man saved that completed result in research revision
  `36904358f7e468a6528a5322fbdfb61122457fa5a6daec99a0efcff5a1f16ba6`
  and returned to idle. Both app receipts show stopped and zero containers;
  an independent baseline query repeated that observation after closeout.
  Private completed summary: `tune-next.OFAuGb/candidate-continuation/execution/summary.json`,
  SHA-256 `8d0c7d1e792d130f8afaea6d04ce6fe2f7d89bf0a6ad9e7fa9a0eb3070a09052`.
- [x] Fixed the observed Modal stop race: zero containers while the app is
  still stopping is no longer reported as completed teardown. The retained
  candidate continuation exercised the corrected stop path.
- [x] Optional `agent-trial` outcome checking accepts one trusted repository
  script and leaves correctness unknown on a failed/changed checker. Local
  checks covered true, false, malformed output, timeout, changed source, and
  zero-call replay. This adds scoring, not a gate or a claim of task quality;
  a real checker-assisted model trial remains open.
- [x] Restarted owner 99949 during that real provider startup. Owner 9907
  resumed the same trajectory, task, and watch; workers 8869/8870 survived in
  a separate process group. One startup intent remained. The restored watch
  detected the active worker and resumed turn 61 without another prompt.
  Private proof: `tune-next.OFAuGb/owner-99949-restart-after.json`, SHA-256
  `fead9e33f8a959df7998614f6e5643a3983e73f5608236aaedd5cdf3d7307bfa`.
  This proves startup restart, not unassisted experiment completion.
- [x] Restarted the idle local owner after publishing `38f07a9b5`; the same
  trajectory resumed with 57 turns and no new model call. Owner 99949 loaded
  the detached-command guidance and remained connected in Chrome. This was
  an idle restart, not a provider-startup interruption.
- [x] Chrome-prompted Milk Man saved both new results through `research`.
  Independent R2 verification confirmed revision
  `dfc90c22df70fc059788b81fe4b77a1af0939518b7218f8d1b63108d283d34c5`,
  record `bc57f059-c669-59f1-b931-ad72b12f9ece`, with four retained experiment
  entries. Baseline, evaluation, and best remain unknown. The write job made
  zero inference/provider calls; its Astra driver replies were paid.
- [x] Chrome-prompted Milk Man completed the owned checkpoint task without a
  follow-up instruction: launched/reused cached `openai/gpt-oss-120b` on one
  H200, resumed automatically after startup, ran the frozen child, and stopped
  the service. Child trial
  `54608c2ba68840f2bb783fce1382e1f77e0c377c369876712e8e2097e4ff41cc`
  completed in 17.343 seconds with three model replies: one Bash call and two
  finish calls. It corrected its first malformed finish arguments itself.
  The final counts were 20 exchanges, five source groups, eight classified,
  20 tool-bearing, zero text-eval eligible, and unknown task success.
  The suggested next action was generic; this is an operations check, not
  proof of better research decisions. Both runtime and workspace remained
  clean at `25031f4bf`. Result SHA-256:
  `cb6115789092dc738b67e7395561ebe2009af9453cfc60aaa1cce61f710691fe`.
  Independent Modal status confirmed app `ap-zM2gDYyZlY2ue5AtzLGshF` stopped,
  zero containers; the weight cache remains. The parent stayed on Astra/Parlor.
- [!] During startup, the agent's `nohup` wrapper inherited heartbeat owner
  PID 68699's process group and lock descriptor. Restarting the owner then
  would have killed the wrapper or prevented ownership recovery. No restart
  was attempted while it was active; startup and cleanup finished normally.
- [x] Added `bin/background` and entrypoint/skill guidance for long commands.
  Its worker uses a new process group, closes inherited descriptors, records
  its own PID before starting the command, and retains private logs and an
  exit receipt. A live local command ran without inherited owner FD 233; the
  original lock was reacquired while that command was still active. Exit 0
  was retained and replaying its run directory launched nothing. Proof:
  `milk-background-proof.uzz_k5ow` in private local state. This proves process
  isolation, not yet restart during an actual provider startup.
- [x] Added `native-capture`, reusing the existing capture integrity checks.
  A repeated exact-key R2 read produced the same private artifact:
  `a1227941b1b58a403b3e124d999486e1e539b23f9c9ba43b4aceafc1f791ecf9`.
  Capture `01a06e91-db01-79f1-b70a-2b038cf1924f` contains 28 ordered context
  messages, ten matched historical tool results, two tool definitions, and
  one next assistant tool-call target. Encrypted reasoning is explicitly
  omitted. No inference, provider action, or object-store write occurred.
  The old text parser returned identical output on this object. This is
  visible-only example extraction: task success and training admission remain
  unproven; native Chat and streaming have no live extraction proof.
- [x] Added reusable `agent-trial` and independent `serve-baseten` scripts in
  `57b7584ff`. Trials retain exact task, code-content identity, driver settings,
  elapsed time, tool counts, and private results. Baseten-owned deployment is
  implemented but has not yet been exercised live; managed inference remains
  independent.
- [!] The first frozen checkpoint-decision trial reached the correct stored
  counts but used all six replies before reporting a decision: exit 76,
  140.086 seconds, six Bash calls, no final answer. Trial
  `dca569cf30d8c40f4dc20f2aa4e734a742f6133684ba6c2f760eb2a7b4ab153d`
  is retained. Chrome-prompted Milk Man replayed its failed receipt with zero
  inference and stopped before launching the planned 120B comparison.
- [x] `407db7393` adds `milk jobs NAME`: this trial's catalog lookup falls
  from 12,863 to 1,018 bytes without changing the complete catalog. `b11dd40c6`
  makes job discovery conditional and tells the driver its reply allowance.
  The explicit second attempt also exhausted six replies: 171.796 seconds,
  exit 76, no final answer. Trial
  `2c5b019dd069e94292df91197099a9f01916c846c63cf331d5f0c572baa435e7`
  remains retained. These prompt changes did not establish autonomous success.
- [x] Added a 63-line read-only `checkpoint` job so agents can use verified
  summary facts without reconstructing storage internals. A real R2 read of
  checkpoint `e6393c53` returned 20 exchanges, five source groups, eight
  classified, 20 tool-bearing, and zero eligible for the text-eval path in
  1.29 seconds. No inference, provider action, object write, or capture-body
  read occurred. This does not assert dataset admission or task success.
- [x] Chrome-prompted Milk Man then discovered the named checkpoint job,
  executed it once, and correctly reported the counts and missing tool-aware
  training support at `2026-09-05T00:18:31Z`, without reading source or capture
  bodies. Three paid Astra replies drove this interaction; the checkpoint
  job itself made zero inference/provider calls. This proves the reusable-job
  path, not a successful six-reply source-inspection trial or model-quality win.
- [x] Milk Man saved both failures through the research job; independent R2
  verification confirmed revision
  `d488354068c9c3db48dcc20a0610186a04d990ce7ac5685c763bf1fb9e1ae176`.
  Baseline, evaluation, and best remain null. A separate live Modal check
  confirmed the selected H200 app is still stopped with zero containers.
- [x] `36433b983` isolates nested Milk Man heartbeat context and makes
  subcommand `--help` work. A child no longer inherits the parent's wait file.
- [x] Read-only Modal serving status now works while startup holds its mutation
  lock. Live status returned `active`, one H200 container, app
  `ap-5OBmVF7Ek1uUyykOziCT2v`, without inference. Startup later completed;
  after the child task Milk Man stopped this app. An independent status call
  confirmed `stopped`, zero containers, and the retained model cache.
- [x] The 120B endpoint then powered a real native Milk Man child: one Bash
  call read R2 research status, one `finish` reported threshold not crossed
  and no measured best model, exit 0 in 12.781 seconds. Trajectory
  `c2bc3280-849a-4e93-b7c7-90ede5f98a85`, SHA-256
  `d7e33a0a3c01acb3b820b686f31218ce30ac111c87edb7a76910887cf933dc15`.
  Its reported count 20 is summarized exchanges, not the live capture total.
  This child used the owned endpoint directly; the Astra parent stayed on
  Parlor. It does not prove captured OSS-driver traffic or a model-quality win.
- [x] A fresh Astra child completed the exact same task in 15.110 seconds,
  exit 0, with one Bash call and `finish`; both returned identical research
  status. Astra trajectory `801e15ca-127c-4e99-8477-ec7d7ee70640`, SHA-256
  `8055c5d2c1008367e049bcb2b1f339876f53299028a08956a4dcc9539cdc85a2`.
  Task SHA-256 `87ad92578a1274fed01da5a85185ac504107f5ee06160b450f7bee39252e8938`.
  These are single operations checks, not a speed or quality ranking: API
  mode, reasoning effort, network path, and working-tree snapshot differ.
  The 120B timing excludes deployment and cleanup. No rerun is needed to
  retain this limited result; a quality comparison needs untouched tasks.
- [x] Milk Man appended this operations check to R2 research revision
  `da39c68f11802b50eff1e4786c9f3ec44af012005468263f95600c3919356c4e`,
  record `0b876290-3685-5c38-afce-b43134759e79`, then finished turn 48.
  Baseline, evaluation, and best remain null. The next action is an untouched
  task comparison, not new generation. Private comparison SHA-256:
  `baca9923b9994d60fad0462744eb603563da456db1fb1f57c53abcdc36907e58`.
- [!] Comparison closeout repeated artifact/schema/help reads after both
  children had finished. One narrowed Chrome instruction completed the saved
  record and final report. This sequence still needed assistance; autonomous
  research efficiency remains open.
- [!] The first child sent an empty API key and failed HTTP 401 before a tool
  ran. Milk Man retained it and ran the corrected authenticated attempt on the
  same deployment. Missing flag documentation also required a chat correction.
  CLI help/check now expose effective limits; serving results identify the
  credential environment name without returning its value.
- [x] Queued chat corrections now yield at the next safe model-call boundary,
  before executing an obsolete response. The live parent logged the yield
  and consumed the next instruction at turn 46 without an owner restart.
- [x] Product contract now explicitly targets continuous autoresearch per
  scope UUID, including Milk Man's own traffic, toward a measured best model
  for that workload. This records the requirement, not a completed capability.
- [ ] Prove the durable per-scope objective -> experiment -> held-out comparison
  -> current best -> next action loop using existing jobs and heartbeat.
- [x] The new `research` repository job stores an immutable record plus
  conditional `research/current.json`. Chrome-prompted Milk Man saved record
  `f7df310c-5424-5395-bac5-3230932640ed` in its dedicated scope, revision
  `b8a6ec8043d58bfc5338d0c330f10ac2df8200e7b38bd6bad67612d1bcc31bb1`,
  and confirmed unchanged replay. Baseline, evaluation, and best remain null;
  no experiment was invented or imported from the earlier MILK_OK benchmark.
- [x] Milk Man registered `bin/milk run research status` with its existing
  heartbeat. Owner 53305 remained alive; idle checks advanced from 148 to 150
  while model wakeups stayed at 36 and the interval increased to 60 seconds.
  The job reported zero inference/provider calls. The preceding Astra driver
  replies were real inference through Parlor; they are not counted as free.
- [x] Chrome showed the saved research record inline with expandable targets,
  baseline, held-out tasks, results, and wake plan. Raw capture totals are now
  labeled exchanges, not independent conversations. No GPU or route was
  changed in this slice.
- [x] Corrected two issues found in the live view: uncounted captures are
  labeled unknown after dashboard restart, and unchanged registered watches
  retain their growing poll interval instead of resetting to the base delay.
  Temporary-state execution proved 30/60/120/240-second delays, immediate
  instruction wake, and on-time scheduled wake without sleeping or model use.
  Chrome then showed a real 60-second wait, 156 checks, and still 36 wakeups.
- [x] Added a scoped capture-threshold probe to `research status`. It lists
  keys only up to the next threshold, reads no capture bodies, and keeps its
  output unchanged below the threshold. Dashboard reads remain metadata-only.
- [x] Chrome-prompted Milk Man saved checkpoint
  `f0da6783-f36e-5ed0-83c1-3bd685acaf2c` from 18 retained exchanges: five
  source groups (one tagged trajectory and four untagged request groups).
  This was structural accounting only: zero classified rows, zero summary
  inference, zero GPU/provider actions, and readiness false. The driver's
  Astra calls through Parlor were paid inference. No filler traffic was sent.
- [x] `5ceb65f9f` adds native non-streaming tool-call text and bounded
  excerpts without changing training eligibility. Chrome-prompted Milk Man
  then saved checkpoint `e6393c53-6e84-552e-b538-2021cee033ca` (SHA-256
  `b0de4aec8a6a0b34939f042a99d11eda31b4bad73449f473dc04eb41b5309771`):
  20 exchanges, five source groups, eight classified, two Astra summary
  calls, zero provider actions. All eight labels identify software/tool use
  and leave task outcomes unknown. Readiness is false. A direct replay made
  zero inference calls and created no checkpoint; the first record remains.
- [x] Codex linked that checkpoint into research revision
  `9c6453af8d9964b6150f94ebf86de0832408a28f6a269715345e49726a37d6ca`
  through the existing job, with no inference. Baseline and best remain null.
  Dashboard cards now include saved off-threshold checkpoints and source groups.
- [x] Milk Man is watching the normal 100-exchange summary threshold. Chrome
  showed 44 captured exchanges, 20 summarized, and 166 idle checks while model
  wakeups remained at 41. Unchanged summary and research panels now keep their
  existing elements during refresh; an open checkpoint stayed open through a
  live refresh. No generation, GPU, or route action was started by this check.
- [!] The longer summary/research instruction led Milk Man into repeated
  source inspection. Codex stopped that read-only turn after its summary and
  zero-call replay were retained. A short, single-job Chrome instruction then
  launched the corrected job, waited through the heartbeat, and reported its
  result. Broad autonomous research efficiency is not yet proven.

- [x] Reserved and validated UUIDv6
  `1f1a8ad1-5d3d-6cf0-aa19-6d696c6ba72a` for `milk-man-autoresearch`.
  Its node prefix encodes `milk`; it is not an authentication key.
- [x] Bind a dedicated Milk key to this scope, route the running driver's
  model calls through Parlor, and inspect one captured task/tool sequence.
  This is additional agent-training data; retain the existing application scopes.
- [x] Recovered the four existing key bindings from Keychain and exact deploy
  history, preserved production route revision 7, and appended the new binding.
  All five keys authenticate after deployment; private recovery files stay
  outside Git in `~/.config/milk/`.
- [x] The running driver is now `gpt-6-astra`, Responses, maximum reasoning,
  through Parlor. Baseten GLM remains an independent configuration option.
- [x] R2 inspection found eleven complete exchanges in the new scope. Seven
  include trajectory `df36b6bc-1651-4f74-aa40-43da7a8a216a` and parse as one
  scope-bound source group. Four pre-image exchanges have no trajectory field
  and were not rewritten. All eight captured Bash calls have captured results;
  known environment credential values were absent from inspected payloads.
  Content-free proof: `~/.config/milk/driver-capture-proof.json`.
- [x] `8d27935fb` carries optional task identity through summary, readiness,
  eval and dataset preparation, keeps a task in one split, and excludes exact
  held-out request/content duplicates from training. Narrow in-memory checks
  passed; no new generation or training ran.
- [ ] Add native assistant/tool sequence handling before admitting tool-call
  trajectories to training. Captured tool traffic is not yet training-ready.

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
  heartbeat, dashboard reporting, and their retained local proof. It is now
  included in published `b9fbc82b2`.
- [x] Local Milk Man completed a Chrome-prompted remote progress check and then
  authored and reused `bin/progress` across an automatic ten-second follow-up.
  Both readings were 106 captured / 106 summarized. Four useful memory entries
  are retained in trajectory `df36b6bc-1651-4f74-aa40-43da7a8a216a`.
- [x] The independent heartbeat survived a dashboard-server restart, stopped,
  and restarted from Bash with the same trajectory and no new model turn.
- [x] Idle backoff, timer continuation, provider-status wake, and owner restart
  against the same ready H200 server worked without another deployment.
- [~] Earlier provider startup recovery required Codex corrections. The later
  owned checkpoint lifecycle completed without a follow-up instruction;
  restarting during provider startup remains unproved.
- [x] The first environment-selected P4 lifecycle served
  `Qwen/Qwen3-0.6B` on one Modal L4, completed three correct inference calls,
  stopped app `ap-joFFZzWQm7cFTdMJ7F0QGz`, and observed zero tasks and zero
  containers. This is a small lifecycle proof, not 120B or autotuning proof.
- [x] Profile `e00fd2eb8ffa` served `openai/gpt-oss-120b` on one H200,
  completed three correct calls, survived a heartbeat-owner restart against
  the same ready server, stopped, and was independently observed at zero.

## Repository snapshot

Current source snapshot:

| Repository | Local state | Published state | Assessment |
| --- | --- | --- | --- |
| `milk-man` | published `ec42c5403`, plus this watched-resource UI checkpoint | `ec42c5403` | readable dashboard, native action trials, completed serving comparison and startup/restart proof; Baseten-owned proof and measured task-quality improvement remain open |
| `milk-parlor` | `2b43cbd`, deployed | `2b43cbd39cfa21a8e6f6c9057fdd0dabe6115b71` | trajectory-aware capture image deployed and source pushed |
| `milk-landing` | `74a87c0`, deployed | `74a87c0` | root and docs verified against production; generated local deployment cache is not published |

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
- [x] Worker version: `158038b4-d675-492c-a635-caaf958b1333`
- [x] Image:
  `sha256:57dd4e003466858294995f8351e24e1436b8a4df65f27cb0b6565ca4d4fc8024`
- [x] Live check on 2026-09-04 returned status `ok`: Responses and Chat
  Completions configured; candidate bindings absent; capture writer alive;
  seven exchanges persisted by the new instance, zero dropped.
- [x] The image is already a multi-stage Alpine build with a `scratch` runtime.
  Docker reports 2,348,578 bytes for the Linux AMD64 image. Cloudflare's displayed
  2 GB is ephemeral disk allocation, not image size.
- [x] Requests route to one secret-selected named container instance. The
  current deployment is not an autoscaling pool.
- [x] At 23:30 UTC, authenticated `wrangler containers instances` returned the
  complete list (`next_page_token: null`): 21 named generations, one running,
  20 inactive. Only selected `parlor-d82c3cd-capture` is running (DO ID
  `f2ec87295a98be9db4514c70568f2970bb258d8de8ab7d2a10f13190bd14ac39`).
  The earlier seven-running residue is no longer present. No stop, deletion,
  deployment, or public administrative endpoint was needed.
- [ ] Measure gateway capture overhead with one warm capture-on/capture-off
  comparison before making a latency claim. R2 writes are already asynchronous.
- [ ] Decide later whether deterministic sampling is needed. Current behavior
  captures every eligible complete exchange; this is the minimal initial rule.

## Local Milk Man snapshot

- [x] Dashboard returned HTTP 200 on `127.0.0.1:8766` on 2026-09-04.
- [x] Current trajectory:
  `df36b6bc-1651-4f74-aa40-43da7a8a216a`
- [x] Selected driver: Milk Parlor, `gpt-6-astra`, Responses, maximum reasoning.
  Heartbeat owner restart preserved the same trajectory and 34 completed
  wakeups without a new model call. Chrome's next task completed at wakeup 35.
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

Former dashboard scope `aeaa9585-74c8-43ea-b6e5-070b60c40619` (retained unchanged):

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

Initial capture proof for the current dashboard scope
`1f1a8ad1-5d3d-6cf0-aa19-6d696c6ba72a` (before its summary and 120B task):

- [x] Eleven captured driver exchanges; zero summarized. No data generation,
  training, GPU creation, or route activation was started for this scope.
- [x] The Chrome progress request completed through Astra and native Bash,
  reported ten captures at command time, and returned to online idle.
  Subsequent inventory includes its final model response, bringing the total
  to eleven. Seven tagged exchanges are one task group, not seven independent
  conversations.
- [x] The request exposed missing progress-job discovery. `a1b83d770` and
  `0476df06a` register the existing script and return its standard job result.
  Live `bin/milk run progress` returned eleven captured, zero summarized,
  `next=summary`, with zero inference and provider calls.

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
| Lightweight heartbeat | `[x]` zero-model idle backoff, timer continuation, dashboard restart, and restart during the same pending H200 startup worked | preserve these properties through the next autonomous experiment |
| Managed GLM Milk Man driver | `[x]` Baseten GLM status turn proven | autonomous multi-step task through the driver |
| General model lifecycle | `[~]` Qwen/L4 and 120B/H200 each completed three correct calls and verified zero through the same env-selected scripts | complete a Baseten-owned lifecycle and an unassisted provider recovery |
| Inference autotuning | `[~]` a same-workload 120B A/B comparison selected CUDA graphs; its endpoint later ran a native Milk Man task and stopped; corrections were required | prove independent adaptive trials on representative work |
| Different compute workload | `[x]` Qwen/L4 and 120B/H200 completed without editing the engine | retain generality while adding another provider |
| Official SDK -> Parlor | `[x]` live for Responses and Chat Completions, including streaming | retain as Milk application input |
| Key -> scope UUID | `[x]` source and historical live proof | reuse when the application needs a new scope |
| Async two-sided capture | `[x]` live counters and exact historical object proof | preserve during application work |
| Summary/classification | `[x]` dedicated driver scope: 20 exchanges, eight classified; earlier 106-source checkpoint retained separately | heartbeat-driven threshold and idle replay |
| Deterministic readiness | `[x]` driver scope remains not ready; historical application mechanics separately proved | retain as application logic |
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
  Chrome and Bash proof. The commit is included in published `b9fbc82b2`.
- [x] Restart the dashboard from the aligned source and verify truthful task,
  trajectory, driver, heartbeat, current activity, and next-wake state.
- [x] Chrome shows an always-visible heartbeat strip above chat: state light,
  last check, next check, task wakeups, and idle checks. Disconnects are labeled
  as lost visibility, not proof that the underlying task stopped.
- [x] Local commit `44502826b` separates heartbeat liveness from dashboard
  connectivity. Chrome showed stopped, starting, running, and waiting states;
  the dashboard restart preserved the active deployment and heartbeat owner.
- [x] `720ddbb81` keeps the objective separate from a correction during active
  work. The heartbeat panel exposes both under **saved task**. Chrome and the
  live API show the owner remains running after a dashboard restart.
- [x] `759f927e5` removes the false `0 / 0 jobs configured` display. After
  dashboard PID 31594 restarted, heartbeat owner 28226 remained alive and the
  dashboard showed 13 loaded jobs, 12 configured.

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
- [x] `67b8c3371` rejects status commands that cannot execute instead of
  recording a healthy wait. A valid command's nonzero job status remains
  watchable. Exhausting one reasoning turn schedules continuation of the
  saved task; provider/protocol failures are not blindly retried. Narrow
  no-model checks passed. During the A/B closeout, turn 31 exhausted its
  allowance and turn 32 automatically resumed the saved experiment and finished.

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
- [x] Select model, revision, provider, runtime, GPU type/count, serving
  arguments, and cache through environment variables.
- [x] Repeat with the intended 120B proving workload without hardcoding it into
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
- [x] Startup failures now return a bounded HTTP 500 and a failed job record.
  H200 app `ap-5I6PxIMEQAVD3JruO5LhFR` loaded 65.6 GiB of model weights,
  then exhausted memory allocating its request cache at utilization 0.95.
  That failure automatically resumed Milk Man at turn 21.
- [x] Milk Man stopped the failed app, retained the weight cache, and changed
  utilization to 0.85. Replacement `ap-oB4ul0MsH18m5fJMxnnurF` reached ready
  on one H200 with the same model revision and runtime image.
- [!] This replacement returned one 176-token response, followed by six HTTP
  503 errors across seven attempts. The 60-second scale-down window allowed
  shutdown between requests. Correctness was not checked in those receipts;
  they are not a successful three-call proof or comparable tuning evidence.
- [x] `bb1d76207` makes a partially failed benchmark return failure and a
  nonzero exit. Existing failed receipts remain unchanged.
- [x] Chrome instructed Milk Man to increase only the scale-down window to
  600 seconds, retain the cache, run three exact-correct responses, then stop.
  Profile `e00fd2eb8ffa` completed three exact-correct responses in
  9910.347, 6563.681, and 6511.768 ms, with 69 reported output tokens each.
  Receipts `benchmark-120b-run-{4,5,6}.json` are retained locally. These are
  non-streaming lifecycle measurements, not optimized decode speed.
- [x] Milk Man stopped app `ap-RxnxnsuQhnCB9Ju1K5jMrr`, saved memory, and
  finished turn 24. An independent provider query confirmed all four 120B
  attempt apps stopped with zero containers. Earlier recovery required Codex
  corrections; do not call the full sequence unassisted.

### P5 inference autotuning

- [~] Qwen/L4 and 120B/H200 lifecycles retain non-streaming measurements.
  The later streaming 120B A/B comparison below is complete; it is a small
  exact-answer experiment, not general workload or fully autonomous proof.
- [~] At 21:45 Chrome gave Milk Man the active 120B comparison objective. Its
  first private profile used assignments rather than exports, so profile
  `6aefd` inherited the defaults: concurrency 8 and 60-second scale-down.
  Milk Man corrected the private profile to exports at 21:52, stopped the
  wrong deployment, and resumed the working `e00fd` profile through a saved
  heartbeat watch. The mistaken first configuration remains excluded.
- [x] Baseline A retained three streaming exact-answer successes at 5477.984,
  5437.509, and 5122.564 ms. Its actual workload was `MILK_OK`, not the
  initially requested classification prompt. The alternative must use this
  exact workload; these measurements do not establish broad task quality.
- [~] Milk Man selected CUDA graphs as its one changed setting and launched
  profile `f3bb494b7d5f`. Chrome corrected its invalid compound status command
  at 22:03. It resumed watching the existing deployment without launching a
  duplicate. Measurements and cleanup subsequently completed.
- [x] Same H200, pinned 120B weights, vLLM image, workload digest
  `f445469140acbdde18ede003ffb31182b0227b3bdc23ba3fa0c3b01570563c0c`,
  concurrency one, warmup and three measured calls per configuration. Removing
  only `--enforce-eager` reduced mean end-to-end latency from 5346.019 ms to
  912.863 ms. Both configurations returned three of three correct answers.
  The 5.86x result applies only to this workload; it is not decode-only speed.
- [x] Milk Man repaired its comparison script, selected B, made one successful
  endpoint demonstration, and saved the result. Receipts live in the private
  `serve-modal` state directory: `exp-ab-summary.json`,
  `benchmark-120b-exp-{a,b}-{1,2,3}.json`, and `benchmark-120b-exp-b-demo.json`.
- [x] Independent Modal checks found A `ap-91PxBNIWl1TM7pHfqOtlAJ` and B
  `ap-9sYdEZ7mkJfgJN6VnXpJ2w` stopped, each with zero tasks and containers.
  Weights remain cached. Estimated GPU request cost is not total billed spend.
- [x] Give Milk Man a measurable latency/throughput/correctness/cost objective.
- [x] Run two comparable configurations and persist identities and metrics.
- [ ] Prove further adaptive trials without Codex correcting the run.
- [x] Retain the selected configuration, demonstrate its endpoint, stop both
  trials as requested, and independently verify zero resources.
- [x] The selected 120B endpoint drove an independent native Milk Man child
  through one real research-status Bash call and `finish`. The parent stayed
  on Astra; this was not a hot switch of the parent's existing trajectory.
- [x] Candidate-only continuation reused all four completed baseline calls;
  the old failed receipt remains unchanged. One Chrome correction and the
  stop-condition repair were needed; recovery was not wholly unassisted.

### P6 continuity and generality

- [x] Complete a second model or compute workload through reused or newly
  authored scripts without editing the harness engine.
- [x] Preserve the objective, measurements, conclusions, and reusable script
  across restart.
- [x] Paused the saved provider-status watch, waited for the local startup
  process to exit, and restarted owner 10616 as 28226. The same trajectory,
  objective, latest instruction, cached model, and app were retained. The new
  owner automatically resumed turn 24, measured inference, and stopped that
  app without another deployment. This proves restart with a live provider
  resource, not cancellation/recovery midway through weight loading.

### P7 Milk whiteboard application extensions

- [x] Add a per-scope research record and a stable read-only status action to
  the existing job catalog; demonstrate save/replay/watch through Chrome.
- [ ] Run and retain one genuinely measured scope-specific comparison. The
  research record and dashboard do not verify referenced measurements or
  qualify a production route by themselves.
- [x] Reconcile retained traffic and summary objects before new generation:
  the dedicated driver scope now has the inspected 20-exchange checkpoint.
- [~] Summary jobs progressed and resumed through the heartbeat; the scoped
  threshold probe is installed and unchanged checks use no inference. A later
  automatic raw-traffic threshold crossing remains to be observed.
- [ ] Reuse or add generation, scoring/reward, filtering, split, dataset,
  training, merge, quantization, evaluation, serving, and cleanup scripts only
  as the chosen application needs them.
- [ ] Inspect a small output before optional expansion. The prior 100 x 100
  generation target remains one configurable experiment.
- [~] The optional one-step length-normalized policy-gradient recipe is
  implemented with rollout/reward records and three environment settings.
  An unchanged policy records `updated:false` and cannot publish a candidate;
  that result replays without provider calls. Source and controller are
  committed locally. `59f1e87eb` adds parent-versus-child BF16 evaluation on
  identical DEV cases; a tie or regression retains the parent and starts no
  later comparison or route work. A real Qwen3.5-0.8B policy update and live
  parent comparison remain open; existing SFT is not counted as RL.
- [ ] Complete a coherent application lineage through proposal, signed route,
  candidate success, fallback, rollback, signed zero, and provider cleanup.

### P8 publish, operate, and qualify

- [x] Pushed research implementation `8b9d37bcff1ad6315be90cccf108f0ea959649bf`
  and verified remote main. The diff contained no configured credential values.
  The updated dashboard is running locally; its restart did not stop the
  separate heartbeat. This was not a new gateway or GPU deployment.
- [x] Pushed Milk Man through `b9fbc82b2` and Parlor through `2b43cbd`;
  verified both remote main refs. Unpublished diffs contained none of the
  configured credential values. Private capture evidence and keys remain local.
- [x] Reconciled all 21 Parlor generations: only the selected instance is
  running; 20 are inactive. No stop action was necessary.
- [ ] Publish concise docs and redacted evidence after the autonomous core is
  proven.
- [ ] Enforce owner-only merge controls without blocking forks, issues, or pull
  requests.
- [ ] Use independently collected traffic before labeling a learned route
  production-qualified.

## Human-only inputs

- A production route requires the operator signing key at the signing step.
- Production qualification requires independently collected customer traffic.
- Baseten accepted the owned-serving custom image in the latest attempt;
  that entitlement is no longer an assumed blocker. This does not assert
  separate training-image permissions.
- GitHub branch protection/ruleset changes require repository-owner authority.

These are application/release boundaries, not per-command gates for an already
configured Milk Man task. Nothing else currently justifies restarting an old
eval revision or creating more scaffolding.
