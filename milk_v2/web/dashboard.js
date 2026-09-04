const el = id => document.getElementById(id);
const short = value => typeof value === "string" ? value.slice(0, 8) : "waiting";
const number = value => Number.isFinite(Number(value)) ? Number(value) : 0;
const stages = [
  ["traffic", "collect", "Milk Parlor stores eligible request and returned-response bodies after each exchange ends.", "Milk Parlor", "each eligible gateway exchange"],
  ["summary", "understand", "Milk Man measures every new capture and classifies a bounded sample.", "summary", "a configured conversation threshold is crossed"],
  ["readiness", "decide", "Fixed checks decide whether enough independent, usable data exists.", "summary", "each summary checkpoint completes"],
  ["eval", "make evals", "The teacher creates the configured number of new cases from admitted source conversations.", "eval", "the readiness record says ready"],
  ["dataset", "separate data", "Cases are separated into training, development, calibration, and sealed sets.", "dataset", "the evaluation revision is complete"],
  ["training", "train student", "A temporary GPU trains the pinned Qwen3.5-0.8B student.", "train", "the dataset has enough training examples"],
  ["evaluation", "compare versions", "The same development data scores comparable model versions before one sealed check.", "evaluate", "the training record is complete"],
  ["candidate", "prepare candidate", "One explicitly chosen provider prepares the selected artifact for serving.", "route-propose-baseten or route-propose-modal", "evaluation has selected a winner"],
  ["proposal", "route proposal", "Milk Man writes an unsigned proposal; a person must approve and sign it.", "operator action", "a candidate has been prepared"],
];
const jobCopy = {
  "summary": "Count new traffic, classify a bounded sample, save a checkpoint, and decide readiness.",
  "eval": "Use a teacher model to create evaluation cases from admitted source conversations.",
  "dataset": "Separate evaluation cases and add teacher targets for student training.",
  "train": "Train the pinned Qwen3.5-0.8B student on Baseten.",
  "evaluate": "Compare the trained model versions on the same development and sealed data.",
  "route-propose-baseten": "Prepare the chosen model on Baseten and write an unsigned route proposal.",
  "route-propose-modal": "Prepare the chosen model on Modal and write an unsigned route proposal.",
  "gpu-reconcile-modal": "Check or finish an existing Modal provider operation without choosing another provider.",
  "inference-ensure": "Create or reuse Milk Man's reviewed Modal inference controller.",
  "inference-status": "Read the controller state without changing it.",
  "inference-stop": "Stop the tracked controller and verify it reached zero compute.",
};
const triggerCopy = {
  manual: "only when explicitly requested",
  crossed_capture_threshold: "a configured conversation checkpoint is crossed",
  readiness: "the latest readiness record says evaluation generation may begin",
  eval_ready: "the evaluation revision is complete",
  dataset_ready: "the separated dataset is ready",
  training_ready: "the training record is complete",
  evaluation_ready: "evaluation has selected a winner",
  provider_frontier: "a tracked provider operation needs reconciliation",
};
const prefixCopy = {
  c: "captured conversations", s: "summary checkpoints", l: "semantic labels",
  readiness: "readiness decisions", e: "evaluation cases", d: "datasets",
  t: "training jobs", m: "model records", v: "model comparisons",
  p: "route proposals", j: "job receipts", status: "current run status",
};
const nextCopy = {
  summary: "wait for traffic or write the next summary",
  eval: "generate evaluation cases",
  dataset: "prepare the separated dataset",
  train: "train the student model",
  evaluate: "compare the trained versions",
  "select-route-provider": "choose one candidate-serving provider",
  "operator-sign-route": "waiting for the operator to review and sign the proposal",
};

function node(tag, className, text) {
  const value = document.createElement(tag);
  if (className) value.className = className;
  if (text !== undefined) value.textContent = text;
  return value;
}

async function copyValue(value, label) {
  try {
    await navigator.clipboard.writeText(value);
    el("copy-state").textContent = "copied " + label;
  } catch {
    el("copy-state").textContent = "copy failed · select the text instead";
  }
}

function copyButton(display, value, label) {
  const button = node("button", "copy", display);
  button.type = "button";
  button.title = "Copy " + label;
  button.setAttribute("aria-label", "Copy " + label + ": " + display);
  button.addEventListener("click", event => { event.stopPropagation(); copyValue(value, label); });
  return button;
}

function rows(target, values, empty) {
  target.replaceChildren();
  if (!values.length) return target.append(node("p", "empty", empty));
  for (const value of values) {
    const row = node("div", "row");
    if (value.help) row.title = value.help;
    row.append(node("b", "", value.title));
    if (value.detail) row.append(node("small", value.class || "", value.detail));
    target.append(row);
  }
}

function light(id, state, label) {
  el(id + "-signal").className = "signal " + state;
  el(id + "-state").textContent = label;
}

function counts(values) {
  return Object.entries(values || {}).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(value => value[0].replaceAll("_", " ") + " " + value[1].toLocaleString()).join(" · ") || "none";
}

function percent(basisPoints) {
  return (number(basisPoints) / 100).toFixed(number(basisPoints) % 100 ? 2 : 0) + "%";
}

function fillPercent(count, points) {
  if (!points.length) return 0;
  let prior = 0;
  for (let index = 0; index < points.length; index++) {
    if (count < points[index]) return 100 * (index + (count - prior) / (points[index] - prior)) / points.length;
    prior = points[index];
  }
  return 100;
}

function duration(value) {
  const amount = number(value);
  return amount >= 1000 ? (amount / 1000).toFixed(amount % 1000 ? 1 : 0) + "s" : amount + "ms";
}

function series(value, format = item => number(item).toLocaleString(), showTail = false) {
  if (!value || !number(value.count)) return "no data";
  const result = "average " + format(number(value.mean_milli) / 1000) + " · observed " + format(value.min) + "–" + format(value.max);
  return showTail ? result + " · about 95% ≤" + format(value.p95) : result;
}

function summaryRow(label, value, help, copiedValue) {
  const row = node("div", "summary-row");
  const heading = node("b", help ? "has-help" : "", label);
  if (help) heading.title = help;
  const result = node("span");
  result.append(copiedValue ? copyButton(value, copiedValue, label) : document.createTextNode(value));
  row.append(heading, result);
  return row;
}

function distributionChart(label, values, total, help) {
  const chart = node("section", "summary-row chart");
  const heading = node("b", help ? "has-help" : "", label);
  if (help) heading.title = help;
  chart.append(heading);
  const entries = Object.entries(values || {}).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  if (!entries.length) {
    chart.append(node("span", "", "none"));
    return chart;
  }
  for (const [name, count] of entries) {
    const row = node("span", "bar");
    const caption = node("small", "", name.replaceAll("_", " "));
    caption.append(node("i", "", number(count).toLocaleString()));
    const meter = node("meter");
    meter.min = 0;
    meter.max = Math.max(1, number(total));
    meter.value = number(count);
    meter.textContent = number(count).toLocaleString() + " of " + number(total).toLocaleString();
    meter.setAttribute("aria-label", name.replaceAll("_", " ") + ": " + meter.textContent);
    row.append(caption, meter);
    chart.append(row);
  }
  return chart;
}

function renderProgress(progress = {}) {
  const count = number(progress.capture_count);
  const processed = number(progress.processed_count);
  const points = progress.thresholds || [];
  const checkpoints = progress.checkpoints || [];
  const opened = new Set(Array.from(el("milestones").querySelectorAll("details[open]"), value => value.dataset.uuid));
  el("volume").textContent = count.toLocaleString() + " conversations captured";
  el("target").textContent = progress.next_threshold
    ? processed.toLocaleString() + " summarized · " + (count >= progress.next_threshold ? "ready at " : (progress.next_threshold - count).toLocaleString() + " to ") + progress.next_threshold.toLocaleString()
    : processed.toLocaleString() + " summarized · checkpoints complete";
  const fill = Math.max(0, Math.min(100, fillPercent(count, points)));
  el("meter").value = fill;
  el("meter").textContent = Math.round(fill) + "%";
  const ticks = el("ticks");
  ticks.replaceChildren();
  for (const point of points) {
    const checkpoint = checkpoints.find(value => number(value.capture_count) >= point);
    const active = !checkpoint && (count >= point || number(progress.next_threshold) === point);
    const tick = node("span", "tick" + (checkpoint ? " done" : active ? " active" : ""), point.toLocaleString());
    const remaining = Math.max(0, point - count);
    tick.title = checkpoint
      ? "Summary checkpoint complete at " + point.toLocaleString() + " conversations."
      : count >= point
        ? "Threshold reached; its summary has not committed yet."
        : remaining.toLocaleString() + " conversations until this summary threshold.";
    tick.setAttribute("aria-label", tick.title);
    ticks.append(tick);
  }
  el("milestones").replaceChildren();
  for (const point of points) {
    const checkpoint = checkpoints.find(value => number(value.capture_count) >= point);
    const card = node(checkpoint ? "details" : "div", "checkpoint" + (checkpoint ? " reached" : count >= point ? " crossed" : ""));
    if (checkpoint) {
      card.dataset.uuid = checkpoint.uuid;
      card.open = opened.has(checkpoint.uuid);
      const disclosure = node("summary", "checkpoint-head");
      disclosure.title = "Open the structured summary for this checkpoint.";
      const identity = node("small", "", "complete · ");
      identity.append(copyButton(short(checkpoint.uuid), checkpoint.uuid, "summary ID"));
      disclosure.append(node("i", "pin"), document.createTextNode(point.toLocaleString()), identity);
      const quality = checkpoint.quality || {};
      const counters = checkpoint.counters || {};
      const traffic = checkpoint.traffic || {};
      const semantic = checkpoint.semantic || {};
      const values = checkpoint.series || {};
      const body = node("div", "summary-body");
      body.append(
        summaryRow("saved", checkpoint.created_at ? new Date(checkpoint.created_at).toLocaleString() : "timestamp unavailable"),
        summaryRow("quality", percent(quality.parse_bps) + " parsed · " + percent(quality.success_bps) + " successful · " + percent(quality.duplicate_bps) + " duplicate · " + (quality.capture_gap ? "capture gap" : "continuous capture"), "Structural checks over every captured request and response in this checkpoint."),
        summaryRow("volume", number(counters.unique_contents).toLocaleString() + " unique · " + number(semantic.classified).toLocaleString() + " classified · " + number(semantic.abstained).toLocaleString() + " abstained · peak " + number(counters.max_concurrency).toLocaleString() + " concurrent"),
        summaryRow("models", counts(traffic.model), "Model names requested by captured applications."),
        summaryRow("endpoints", counts(traffic.endpoint), "Responses and Chat Completions requests in this checkpoint."),
        summaryRow("routes", counts(traffic.route_target), "Requests served by the baseline or an approved candidate."),
        summaryRow("response", counts(traffic.status_class) + " · streaming " + counts(traffic.streaming) + " · structured " + counts(traffic.structured_output), "HTTP results plus streaming and structured-output use."),
        summaryRow("traffic", counts(traffic.modalities) + " · outcome " + counts(traffic.outcome) + " · fallback " + counts(traffic.fallback_reason), "Input modes, request outcomes, and any candidate fallback reasons."),
        summaryRow("reasoning", counts(traffic.reasoning_effort), "Reasoning-effort values requested by applications when present."),
        distributionChart("topics", semantic.domain, semantic.classified, "What the sampled conversations are about."),
        summaryRow("tasks", counts(semantic.operation), "What users are asking the model to do."),
        distributionChart("capabilities", semantic.capability, semantic.classified, "Capabilities needed to answer the sampled conversations. One conversation may need several."),
        summaryRow("grading", counts(semantic.oracle), "How each captured task could be checked."),
        summaryRow("sentiment", counts(semantic.sentiment), "The classifier's coarse tone label for each conversation."),
        distributionChart("outcomes", semantic.outcome, semantic.classified, "How the classifier judged the captured responses."),
        summaryRow("languages", counts(semantic.language), "Detected conversation languages."),
        summaryRow("total time", series(values.total_ms, duration, true), "Time from request start to the complete response."),
        summaryRow("first token", series(values.ttft_ms, duration, true), "Time from request start to the first streamed response byte when measured."),
        summaryRow("generation", series(values.tps_milli, item => (number(item) / 1000).toFixed(1) + " tok/s"), "Observed output-token generation rate when token counts are available."),
        summaryRow("input tokens", series(values.input_tokens), "Input tokens reported by the model provider."),
        summaryRow("output tokens", series(values.output_tokens), "Output tokens reported by the model provider.")
      );
      card.append(disclosure, body);
    } else {
      const title = node("h3");
      title.append(node("i", "pin"), document.createTextNode(point.toLocaleString()));
      card.append(title, node("small", "", count >= point ? "data crossed; summary waiting" : (point - count).toLocaleString() + " conversations to go"));
      card.title = count >= point ? "Milk Man has enough data and is waiting to write this summary." : "Traffic is still accumulating for this checkpoint.";
    }
    el("milestones").append(card);
  }
  if (!points.length) el("milestones").append(node("p", "empty", "no thresholds configured"));
}

let selectedStage = null;
let stageNotes = {};
function selectStage(index, openCard = false) {
  selectedStage = Math.max(0, Math.min(stages.length - 1, index));
  const [key, label] = stages[selectedStage];
  const state = stageNotes[key] || "waiting";
  const position = String(selectedStage + 1).padStart(2, "0");
  el("stage-scrubber").value = selectedStage + 1;
  el("stage-scrubber").setAttribute("aria-valuetext", `${position} of 09, ${label}, ${state}`);
  el("stage-output").textContent = `${position} / 09 · ${label} · ${state}`;
  Array.from(el("stage-stops").children).forEach((stop, stopIndex) => stop.classList.toggle("selected", stopIndex === selectedStage));
  if (openCard) Array.from(el("rail").children).forEach((card, cardIndex) => { card.open = cardIndex === selectedStage; });
}

function renderLoop(status) {
  const value = status || {};
  const opened = new Set(Array.from(el("rail").querySelectorAll("details[open]"), item => item.dataset.stage));
  const done = {
    traffic: number(value.capture_count) > 0,
    summary: Boolean(value.summary),
    readiness: value.readiness?.ready === true,
    eval: Boolean(value.eval) && !value.eval_generation,
    dataset: Boolean(value.dataset),
    training: Boolean(value.training),
    evaluation: Boolean(value.evaluation),
    candidate: Boolean(value.candidate),
    proposal: Boolean(value.proposal),
  };
  const notes = {
    traffic: number(value.capture_count) + " captured",
    summary: value.summary ? "checkpoint " + short(value.summary.uuid) : "waiting",
    readiness: value.readiness ? (value.readiness.ready ? "ready" : "not ready") : "waiting",
    eval: value.eval_generation ? value.eval_generation.completed_case_count + " / " + value.eval_generation.target_case_count : value.eval ? value.eval.case_count + " cases" : "waiting",
    dataset: value.dataset ? "revision " + short(value.dataset.uuid) : "waiting",
    training: value.training ? "model " + short(value.training.uuid) : "waiting",
    evaluation: value.evaluation ? value.evaluation.winner_branch + " selected" : "waiting",
    candidate: value.candidate ? "prepared · " + short(value.candidate.uuid) : "waiting",
    proposal: value.proposal ? "awaiting operator signature" : nextCopy[value.next_action] || value.next_action || "waiting",
  };
  const records = {
    summary: value.summary?.uuid,
    readiness: value.readiness?.uuid,
    eval: value.eval?.uuid || value.eval_generation?.uuid,
    dataset: value.dataset?.uuid,
    training: value.training?.uuid,
    evaluation: value.evaluation?.uuid,
    candidate: value.candidate?.uuid,
    proposal: value.proposal?.uuid,
  };
  stageNotes = notes;
  if (selectedStage === null) {
    const pending = stages.findIndex(([key]) => !done[key]);
    selectedStage = pending < 0 ? stages.length - 1 : pending;
  }
  const stops = el("stage-stops");
  stops.replaceChildren();
  stages.forEach(([key], index) => stops.append(node("span", done[key] ? "done" : "", String(index + 1).padStart(2, "0"))));
  let marked = false;
  el("rail").replaceChildren();
  stages.forEach(([key, label, help, job, startsWhen], index) => {
    const card = node("details", "stage");
    card.dataset.stage = key;
    card.open = opened.has(key);
    card.title = help;
    card.setAttribute("aria-label", label + ". " + help + " Current state: " + notes[key]);
    if (done[key]) card.classList.add("done");
    else if (!marked) { card.classList.add("next"); marked = true; }
    const heading = node("summary", "stage-head");
    heading.append(node("b", "", String(index + 1).padStart(2, "0")), node("i", "pin"), node("strong", "", label), node("small", "", notes[key]));
    const body = node("div", "stage-body");
    body.append(
      node("p", "", help),
      summaryRow("job", job),
      summaryRow("starts when", startsWhen)
    );
    if (records[key]) body.append(summaryRow("record", short(records[key]), "The first eight characters of the stored record UUID.", records[key]));
    card.append(heading, body);
    card.addEventListener("toggle", () => { if (card.open) selectStage(index); });
    el("rail").append(card);
  });
  selectStage(selectedStage);
}

function renderRun(status = {}) {
  const profile = status.profile || "unknown";
  const badge = el("run-profile");
  badge.textContent = profile.toUpperCase() + " RUN";
  badge.title = profile === "mechanics"
    ? "A mechanics run proves the parts connect. It does not prove model quality or production readiness."
    : profile === "production"
      ? "A production run uses the production traffic and readiness policy for this scope."
      : "The current scope profile is not known.";
  el("run-now").textContent = nextCopy[status.next_action] || String(status.next_action || "waiting for object memory").replaceAll("-", " ");
  const scope = status.scope_id || "";
  const scopeNode = el("run-scope");
  scopeNode.replaceChildren(scope ? document.createTextNode("scope ") : document.createTextNode("scope unknown"));
  if (scope) scopeNode.append(copyButton(short(scope), scope, "scope ID"));
  scopeNode.title = scope || "No scope is configured.";
}

function environmentList(label, values, optional = false) {
  const section = node("section", "environment");
  section.append(node("b", "", label));
  if (!values.length) {
    section.append(node("small", "", "none"));
    return section;
  }
  const list = node("div", "env-list");
  for (const value of values) {
    const item = node("span", "env " + (value.set ? "set" : "missing"));
    item.title = (value.set ? "Set" : "Not set") + " in this dashboard process. The value is never shown.";
    item.append(node("i", "pin"), copyButton(value.name, value.name, "environment name"), node("small", "", value.set ? "set" : optional ? "unset" : "missing"));
    list.append(item);
  }
  section.append(list);
  return section;
}

function renderContract(contract = {}) {
  const target = el("jobs");
  const opened = new Set(Array.from(target.querySelectorAll("details.job[open]"), item => item.dataset.job));
  const controls = new Set(Array.from(target.querySelectorAll("details.controls[open]"), item => item.dataset.job));
  target.replaceChildren();
  if (contract.error) {
    target.append(node("p", "empty", contract.error));
    return;
  }
  for (const job of contract.jobs || []) {
    const missing = (job.required || []).filter(value => !value.set);
    const card = node("details", "job " + (missing.length ? "needs-config" : "configured"));
    card.dataset.job = job.name;
    card.open = opened.has(job.name);
    const heading = node("summary", "job-head");
    heading.title = jobCopy[job.name] || job.description || "A repository job.";
    heading.append(
      node("i", "pin"),
      node("b", "", job.name),
      node("small", "", missing.length ? "missing " + missing.length + " required name" + (missing.length === 1 ? "" : "s") : "required names set")
    );
    const body = node("div", "job-body");
    body.append(node("p", "", jobCopy[job.name] || job.description || "A repository job."));
    const facts = node("div", "facts");
    facts.append(
      summaryRow("starts when", triggerCopy[job.trigger] || String(job.trigger || "manual").replaceAll("_", " ")),
      summaryRow("run", job.command, "Run this exact reviewed job explicitly.", job.command),
      summaryRow("schedule", job.automatic ? "checked by bin/milk operate --once" : "run explicitly"),
      summaryRow("reads", (job.inputs || []).map(value => prefixCopy[value] || value).join(" · ") || "no object inputs"),
      summaryRow("writes", (job.outputs || []).map(value => prefixCopy[value] || value).join(" · ") || "no object outputs"),
      summaryRow("prompt", job.prompt || "deterministic code only", job.prompt ? "The repository-owned system prompt used by this job." : "This job uses deterministic code and no model prompt.", job.prompt || undefined),
      summaryRow("time limit", job.timeout || "not configured", "Environment name controlling the job timeout.", job.timeout || undefined)
    );
    body.append(facts, environmentList("required environment", job.required || []));
    const optional = node("details", "controls");
    optional.dataset.job = job.name;
    optional.open = controls.has(job.name);
    optional.append(node("summary", "", "optional controls + defaults"), environmentList("optional environment", job.optional || [], true));
    body.append(optional);
    card.append(heading, body);
    target.append(card);
  }
}

let activityKey = "";
function renderMan(man) {
  const state = man.state || (man.active ? "working" : man.trajectory_id ? "idle" : "setup");
  const driver = man.driver || {};
  const driverStatus = [driver.provider, driver.model, driver.api_mode && driver.api_mode.replaceAll("_", " "), driver.reasoning_effort]
    .filter(Boolean).join(" · ");
  const jobs = (man.local_jobs || []).reduce((total, job) => total + Number(job.count || 0), 0);
  const jobNames = (man.local_jobs || []).map(job => job.count + " " + job.name).join(" · ");
  const jobStatus = jobs ? " · " + jobNames + (jobs === 1 ? " job active" : " jobs active") : "";
  const labels = {
    working: man.connection === "discovered" ? "Milk Man online · working outside this page" : "Milk Man online · working" + jobStatus + (man.queued ? " · next instruction queued" : ""),
    queued: "Milk Man online · instruction queued",
    failed: "Milk Man online · last turn failed",
    waiting: "Milk Man online · watching for progress",
    paused: "Milk Man paused",
    stopped: "Milk Man stopped",
    idle: "Milk Man online · chat waiting" + jobStatus,
    setup: "Milk Man online · session setup needed",
  };
  light("man", state === "failed" ? "degraded" : man.online ? "up" : "down", (labels[state] || labels.setup) + (driverStatus ? " · " + driverStatus : "") + (man.trajectory_id ? " · " + short(man.trajectory_id) : ""));
  const pulse = man.heartbeat || {};
  const heartbeatOnline = pulse.online === true;
  const heartbeatStarting = !heartbeatOnline && man.connection === "attached" && man.active;
  const heartbeatRetained = !heartbeatOnline && Boolean(pulse.state || pulse.checked_at || pulse.next_wake);
  const heartbeatState = heartbeatOnline ? (pulse.state || "idle") : heartbeatStarting ? "starting" : heartbeatRetained ? "stopped" : "not started";
  light("heartbeat", heartbeatOnline ? (pulse.state === "failed" ? "degraded" : "up") : heartbeatStarting ? "ready" : "down", "heartbeat · " + heartbeatState);
  const workActive = heartbeatOnline && (pulse.state === "running" || man.active);
  for (const [id, stamp] of [["last", pulse.checked_at], ["next", heartbeatOnline && !workActive && pulse.state !== "paused" ? pulse.next_wake : null]]) {
    const target = el("heartbeat-" + id);
    target.textContent = stamp ? new Date(stamp * 1000).toLocaleTimeString() : id === "next" && workActive ? "after current work" : id === "next" && heartbeatStarting ? "after startup" : "not scheduled";
    target.dateTime = stamp ? new Date(stamp * 1000).toISOString() : "";
  }
  el("heartbeat-count").textContent = (pulse.turns || 0) + " wakeups · " + (pulse.polls || 0) + " idle checks";
  el("heartbeat-task").textContent = pulse.task || "No task saved yet.";
  el("heartbeat-brief").hidden = !pulse.brief;
  el("heartbeat-brief").textContent = pulse.brief ? "Latest instruction: " + pulse.brief : "";
  const nextWake = workActive ? " · next check after current work" : heartbeatOnline && pulse.next_wake ? " · next check " + new Date(pulse.next_wake * 1000).toLocaleTimeString() : "";
  el("conversation-state").textContent = (man.online ? "online" : "stopped") + " · " + state + jobStatus + nextWake + (man.queued && state === "working" ? " · next queued" : "") + (state === "failed" && Number.isInteger(man.last_exit_code) ? " · exit " + man.last_exit_code : "");
  el("conversation-state").title = pulse.checked_at ? "Heartbeat last checked " + new Date(pulse.checked_at * 1000).toLocaleString() + ". Unchanged idle checks use no model tokens." : "Heartbeat starts with your next task. Closing this page does not stop it.";
  if (!runLoading) {
    runState(man.active ? "Milk Man is working. Output will appear above."
      : man.queued ? "Instruction queued behind the current run."
      : state === "failed" ? "The last turn failed. Review its output, then send a correction."
      : state === "waiting" ? "Milk Man will continue when the watched job changes or its next review is due."
      : state === "paused" ? "Automatic continuation is paused. Send an instruction to continue."
      : state === "setup" ? "Send an instruction to start a saved local session."
      : jobs ? "Milk jobs are running outside chat. Their results will appear in object memory."
      : "Milk Man is ready for the next instruction.", state === "failed");
  }
  if (man.workspaces) rows(el("workspaces"), man.workspaces.map(workspace => ({
    title: workspace.name + " · " + (workspace.head || "no git"),
    detail: workspace.changes.length ? workspace.changes.length + " changed file" + (workspace.changes.length === 1 ? "" : "s") + "\n" + workspace.changes.join("\n") : "clean · " + workspace.path,
    class: workspace.changes.length ? "changes" : "path",
  })), "no workspaces");
  if (man.memory) rows(el("memory"), man.memory.map(memory => ({ title: memory.ts || "memory", detail: memory.content })), "no saved memory");

  const target = el("activity");
  target.setAttribute("aria-busy", man.active ? "true" : "false");
  const nextActivityKey = String(man.active) + JSON.stringify(man.activity);
  if (nextActivityKey === activityKey) return;
  activityKey = nextActivityKey;
  const follow = target.scrollHeight - target.scrollTop - target.clientHeight < 64;
  const scroll = target.scrollTop;
  const opened = new Set(Array.from(target.querySelectorAll("details.message[open]"), value => value.dataset.key));
  target.replaceChildren();
  if (!man.activity.length) target.append(node("article", "message milk-man", "No conversation yet."));
  for (let index = 0; index < man.activity.length;) {
    const event = man.activity[index];
    if (["shell-output", "process-output"].includes(event.type)) {
      const group = [event];
      while (man.activity[index + group.length]?.type === event.type) group.push(man.activity[index + group.length]);
      const message = node("details", "message tool");
      message.dataset.key = index + ":" + (event.ts || event.type);
      message.open = opened.has(message.dataset.key);
      const label = event.type === "process-output" ? (man.active ? "working details" : "run details") : "tool details";
      const last = group[group.length - 1];
      message.append(
        node("summary", "", label + " · " + group.length + (group.length === 1 ? " entry" : " entries") + (last.ts ? " · " + last.ts : "")),
        node("pre", "", group.map(value => value.content).join("\n\n"))
      );
      target.append(message);
      index += group.length;
      continue;
    }
    const role = event.type === "prompt" ? "you" : "milk-man";
    if (role === "milk-man" && (event.content.length > 1200 || event.content.startsWith("```"))) {
      const message = node("details", "message milk-man folded");
      message.dataset.key = index + ":" + (event.ts || event.type);
      message.open = opened.has(message.dataset.key);
      const label = event.content.startsWith("```") ? "milk man · proposed command" : "milk man · long reply";
      message.append(node("summary", "", label + (event.ts ? " · " + event.ts : "")), node("pre", "", event.content));
      target.append(message);
      index++;
      continue;
    }
    const message = node("article", "message " + role);
    message.append(node("b", "", role.replace("-", " ")), node("pre", "", event.content));
    if (event.ts) message.append(node("time", "", event.ts));
    target.append(message);
    index++;
  }
  target.scrollTop = follow ? target.scrollHeight : scroll;
}

let runLoading = false;
function runState(message = "", error = false) {
  el("run").disabled = runLoading;
  el("prompt-state").className = "prompt-state" + (error ? " error" : "");
  el("prompt-state").textContent = message;
}

async function startRun(event) {
  event.preventDefault();
  if (runLoading) return;
  const prompt = el("prompt-text").value.trim();
  if (!prompt) return runState("Enter a prompt first.", true);
  runLoading = true;
  runState("Starting Milk Man. Output will appear above.");
  try {
    const response = await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt }) });
    const result = await response.json();
    if (!response.ok) throw Error(result.error || "Unable to start Milk Man.");
    el("prompt-text").value = "";
    runState(result.state === "queued" ? "Instruction queued behind the current run." : "Milk Man is working. Output will appear above.");
    await refreshLocal();
  } catch (error) {
    runState(error.message || "Unable to start Milk Man.", true);
  } finally {
    runLoading = false;
    el("run").disabled = false;
  }
}

function renderCloud(data) {
  const gateway = data.gateway || {};
  const milk = data.milk || {};
  const monitor = data.monitor || {};
  if (monitor.error) {
    light("gateway", "degraded", "Milk Parlor status unknown");
    light("store", "degraded", "object memory status unknown");
  } else {
    light("gateway", gateway.state || "detached", gateway.state === "up" ? "Milk Parlor reachable · capture active" : gateway.state === "degraded" ? "Milk Parlor reachable · capture degraded" : gateway.state === "down" ? "Milk Parlor unavailable" : "Milk Parlor not configured");
    light("store", milk.error ? "down" : milk.missing && milk.missing.length ? "detached" : "up", milk.error ? "object memory unavailable" : milk.missing && milk.missing.length ? "object memory not configured" : "object memory readable");
  }
  el("checked").textContent = (monitor.error ? "status watcher failed " : "status updated ") + new Date(data.now).toLocaleString();
  const jobs = data.contract?.jobs || [];
  const readyJobs = jobs.filter(job => !(job.required || []).some(value => !value.set)).length;
  el("job-count").textContent = readyJobs + " / " + jobs.length + " ready";
  el("watch-state").textContent = "Describe one outcome. Milk Man chooses the steps. " + readyJobs + " of " + jobs.length + " jobs are configured. Unchanged idle checks use no model. Commands and raw output stay folded.";
  const status = milk.status || {};
  renderRun(status);
  renderProgress(milk.progress);
  renderLoop(status);
  renderContract(data.contract || {});
  rows(el("object"), milk.error ? [{ title: "unavailable", detail: milk.error }] : milk.missing.length ? [{ title: "not configured", detail: milk.missing.join("\n") }] : [
    { title: "next job", detail: nextCopy[status.next_action] || String(status.next_action || "waiting").replaceAll("-", " "), help: "The next deterministic action implied by the stored run status." },
    { title: "run type", detail: status.profile === "mechanics" ? "mechanics · wiring proof only" : status.profile || "unknown", help: "Mechanics traffic proves that components connect; it does not qualify a production route." },
    { title: "scope", detail: status.scope_id ? short(status.scope_id) : "unknown", help: status.scope_id || "No scope is configured." },
    { title: "capture writer", detail: number(gateway.observed) + " received · " + number(gateway.persisted) + " stored · " + number(gateway.dropped) + " dropped", help: "Milk Parlor totals since its current process started." },
  ], "waiting for status");
  el("foot").textContent = "local only · remote status updated " + data.now;
}

let cloudLoading = false;
async function refreshCloud(force = false) {
  if (cloudLoading) return;
  cloudLoading = true;
  el("refresh").disabled = true;
  el("refresh").textContent = "refreshing";
  try {
    const response = await fetch(force ? "/api/state?refresh=1" : "/api/state", { cache: "no-store" });
    if (!response.ok) throw Error("status " + response.status);
    const data = await response.json();
    renderMan(data.man);
    renderCloud(data);
  } catch {
    light("gateway", "down", "Milk Parlor status unavailable");
    light("store", "down", "object memory status unavailable");
    el("checked").textContent = "status refresh failed " + new Date().toLocaleString();
  } finally {
    cloudLoading = false;
    el("refresh").disabled = false;
    el("refresh").textContent = "count traffic + refresh status";
  }
}

async function refreshLocal() {
  if (document.hidden) return;
  try {
    const response = await fetch("/api/local", { cache: "no-store" });
    if (!response.ok) throw Error();
    renderMan((await response.json()).man);
  } catch {
    light("man", "detached", "dashboard disconnected from Milk Man");
    light("heartbeat", "down", "heartbeat · connection lost");
    el("heartbeat-next").textContent = "unknown while disconnected";
  }
}

el("refresh").addEventListener("click", () => refreshCloud(true));
el("stage-scrubber").addEventListener("input", event => selectStage(number(event.target.value) - 1, true));
document.querySelectorAll("[data-copy]").forEach(button => button.addEventListener("click", () => copyValue(button.dataset.copy, button.dataset.copyLabel)));
el("run-form").addEventListener("submit", startRun);
el("prompt-text").addEventListener("keydown", event => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    el("run-form").requestSubmit();
  }
});
refreshCloud();
setInterval(refreshLocal, 1000);
setInterval(refreshCloud, 30000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshCloud(); });
