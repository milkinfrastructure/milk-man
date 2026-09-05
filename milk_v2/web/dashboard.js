const el = id => document.getElementById(id);
const short = value => typeof value === "string" ? value.slice(0, 8) : "waiting";
const number = value => Number.isFinite(Number(value)) ? Number(value) : 0;
const stages = [
  ["traffic", "collect", "Milk Parlor stores eligible request and returned-response bodies after each exchange ends.", "Milk Parlor", "each eligible gateway exchange"],
  ["summary", "summarize", "Count saved exchanges and describe their topics, tasks, timing, and outcomes.", "summary", "a configured conversation threshold is crossed"],
  ["readiness", "check data", "Check whether there are enough distinct, usable source tasks to create evaluation examples.", "summary", "each summary checkpoint completes"],
  ["eval", "create examples", "A teacher model creates new example tasks from the captured conversations.", "eval", "the readiness record says ready"],
  ["dataset", "separate data", "Cases are separated into training, development, calibration, and sealed sets.", "dataset", "the evaluation revision is complete"],
  ["training", "train student", "A temporary GPU trains the pinned Qwen3.5-0.8B student.", "train", "the dataset has enough training examples"],
  ["evaluation", "compare versions", "The same development data scores comparable model versions before one sealed check.", "evaluate", "the training record is complete"],
  ["candidate", "prepare candidate", "One explicitly chosen provider prepares the selected artifact for serving.", "route-propose-baseten or route-propose-modal", "evaluation has selected a winner"],
  ["proposal", "route proposal", "Milk Man writes an unsigned proposal; a person must approve and sign it.", "operator action", "a candidate has been prepared"],
];
const jobCopy = {
  "serve-modal": "Start, inspect, or stop a model server on your Modal GPUs.",
  "serve-baseten": "Start, inspect, or stop a model server on your Baseten GPUs.",
  "benchmark": "Measure answer correctness, response time, and token rate on the configured endpoint.",
  "agent-trial": "Give a separate Milk Man instance one task and save its commands, answer, and timing.",
  "native-trial": "Ask a model for its next action using one saved context. The action is recorded, not executed.",
  "native-capture": "Read one saved exchange as messages and tool calls without flattening their order.",
  "checkpoint": "Read the counts and contents of one saved summary without calling a model.",
  "progress": "Read how much traffic is saved, how much is summarized, and the next data step.",
  "research": "Read or save the research goal, experiments, conclusions, and proposed next step.",
  "summary": "Count new traffic, classify a bounded sample, save a checkpoint, and decide readiness.",
  "eval": "Use a teacher model to create evaluation cases from admitted source conversations.",
  "dataset": "Separate evaluation cases and add teacher targets for student training.",
  "train": "Train the pinned Qwen3.5-0.8B student on Baseten.",
  "evaluate": "Compare the trained model versions on the same development and sealed data.",
  "route-propose-baseten": "Prepare the chosen model on Baseten and write an unsigned route proposal.",
  "route-propose-modal": "Prepare the chosen model on Modal and write an unsigned route proposal.",
  "gpu-reconcile-modal": "Check or finish an existing Modal provider operation without choosing another provider.",
  "inference-ensure": "Start or reuse the preset Modal model service. Use 'serve a model on Modal' to configure a different model server.",
  "inference-status": "Check the preset Modal model service without changing it.",
  "inference-stop": "Stop the preset Modal model service and check that it has no active containers.",
};
const jobLabels = {
  summary: "summarize traffic", eval: "create example tasks", dataset: "prepare training data",
  train: "train the student", evaluate: "compare model versions",
  "serve-modal": "serve a model on Modal", "serve-baseten": "serve a model on Baseten",
  benchmark: "measure model speed + answers", "agent-trial": "give a model one agent task",
  "native-trial": "try one next action", "native-capture": "read a saved tool exchange",
  checkpoint: "read a saved summary", progress: "count traffic + progress", research: "save research results",
  "inference-ensure": "start the preset Modal service", "inference-status": "check the preset Modal service",
  "inference-stop": "stop the preset Modal service", "gpu-reconcile-modal": "check a Modal operation",
  "route-propose-baseten": "prepare a Baseten route", "route-propose-modal": "prepare a Modal route",
};
const triggerCopy = {
  manual: "when Milk Man selects it or you run its command",
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

const views = {
  talk: ["Your workspace", "Describe an outcome. Milk Man chooses the commands and reports back here."],
  traffic: ["What has been collected?", "Requests and answers become saved summaries. Open a checkpoint to read what was learned."],
  research: ["What did the experiments show?", "Compare results before choosing what to try next. Losing experiments stay in the record too."],
  jobs: ["What can Milk Man do?", "Find a tool, check its settings, then ask Milk Man to use it. Opening a tool runs nothing."],
  connect: ["Keep your OpenAI calls", "Point the official SDK at Milk Parlor. Your application still calls the same API."],
};
function showView() {
  const target = el(location.hash.slice(1));
  const view = target?.dataset.view || "talk";
  document.querySelectorAll("[data-view]").forEach(section => { section.hidden = section.dataset.view !== view; });
  document.querySelectorAll(".view-nav a").forEach(link => {
    if (el(link.hash.slice(1))?.dataset.view === view) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  el("view-title").textContent = views[view][0];
  el("view-description").textContent = views[view][1];
  const panel = target || el("talk");
  if (panel.tagName === "DETAILS") panel.open = true;
  if (view === "talk") requestAnimationFrame(latestReply);
}
function draftPrompt(text) {
  location.hash = "talk";
  showView();
  const prompt = el("prompt-text");
  if (prompt.value.trim()) runState("Your unsent message was kept. Clear it to use a suggested task.");
  else { prompt.value = text; runState("Draft ready. Review it, then send when you want Milk Man to act."); }
  prompt.focus();
}

function rows(target, values, empty) {
  target.replaceChildren();
  if (!values.length) return target.append(node("p", "empty", empty));
  for (const value of values) {
    const row = node("div", "row");
    if (value.help) row.title = value.help;
    row.append(helpHeading(value.title, value.help));
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
  return amount >= 1000 ? (amount / 1000).toFixed(amount % 1000 ? 1 : 0) + "s" : amount.toLocaleString(undefined, {maximumFractionDigits: 1}) + "ms";
}

function series(value, format = item => number(item).toLocaleString(), showTail = false) {
  if (!value || !number(value.count)) return "no data";
  const result = "average " + format(number(value.mean_milli) / 1000) + " · observed " + format(value.min) + "–" + format(value.max);
  return (showTail ? result + " · about 95% ≤" + format(value.p95) : result) + " · " + number(value.count).toLocaleString() + " samples";
}

function helpHeading(label, help) {
  const heading = node("b", "field-heading", label);
  if (help) {
    const button = node("button", "help", "?");
    button.type = "button";
    button.title = help;
    button.setAttribute("aria-label", "About " + label);
    heading.append(button);
  }
  return heading;
}

// Render only text and simple tables. Model output never becomes executable HTML.
function replyBody(text) {
  const body = node("div", "reply-body");
  const blocks = text.split(/\n\s*\n/);
  const long = text.length > 1500 && blocks.length > 3;
  const rest = node("details", "reply-rest");
  rest.append(node("summary", "", "rest of reply + saved references"));
  blocks.forEach((block, index) => {
    const lines = block.trim().split("\n");
    let part;
    if (lines.length > 2 && /^\|?\s*:?-{3,}/.test(lines[1]) && lines[0].includes("|")) {
      part = node("div", "table-scroll");
      const table = node("table", "experiment-comparison");
      lines.filter((_, i) => i !== 1).forEach((line, rowIndex) => {
        const row = node("tr");
        line.replace(/^\||\|$/g, "").split("|").forEach(cell => {
          const item = node(rowIndex ? "td" : "th", "", cell.trim());
          if (!rowIndex) item.scope = "col";
          row.append(item);
        });
        table.append(row);
      });
      part.append(table);
    } else part = node("p", "", block);
    (long && index >= 3 ? rest : body).append(part);
  });
  if (long) body.append(rest);
  return body;
}

function latestReply() {
  const target = el("activity");
  const latest = Array.from(target.querySelectorAll("article.message.milk-man")).at(-1) || target.lastElementChild;
  if (latest) target.scrollTop += latest.getBoundingClientRect().top - target.getBoundingClientRect().top - 16;
}

function summaryRow(label, value, help, copiedValue) {
  const row = node("div", "summary-row");
  const heading = helpHeading(label, help);
  const result = node("span");
  result.append(copiedValue ? copyButton(value, copiedValue, label) : document.createTextNode(value));
  row.append(heading, result);
  return row;
}

function distributionChart(label, values, total, help) {
  const chart = node("section", "summary-row chart");
  const heading = helpHeading(label, help);
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

let progressKey;
function renderProgress(progress = {}) {
  const key = JSON.stringify(progress);
  if (key === progressKey) return;
  progressKey = key;
  const counted = Number.isInteger(progress.capture_count);
  const count = number(progress.capture_count);
  const processed = number(progress.processed_count);
  const points = progress.thresholds || [];
  const checkpoints = progress.checkpoints || [];
  const opened = new Set(Array.from(el("milestones").querySelectorAll("details[open]"), value => value.dataset.uuid));
  const deliveryOpened = new Set(Array.from(el("milestones").querySelectorAll(".summary-delivery[open]"), value => value.parentElement.dataset.uuid));
  el("volume").textContent = counted ? count.toLocaleString() + " exchanges captured" : "capture count not checked";
  el("volume").title = "Each saved request and response is one exchange. An agent trajectory can contain many exchanges; these are not independent training examples.";
  el("target").textContent = !counted ? "count traffic to refresh" : progress.next_threshold
    ? processed.toLocaleString() + " summarized · " + (count >= progress.next_threshold ? "next summary not saved" : (progress.next_threshold - count).toLocaleString() + " to " + progress.next_threshold.toLocaleString())
    : processed.toLocaleString() + " summarized · checkpoints complete";
  el("count-checked").textContent = progress.counted_at
    ? "Traffic counted " + new Date(progress.counted_at).toLocaleString() + ". Newer exchanges may not be included."
    : counted ? "Count from saved status; use ‘count saved traffic’ for a fresh total." : "No traffic count available yet.";
  const fill = Math.max(0, Math.min(100, fillPercent(count, points)));
  el("meter").value = fill;
  el("meter").textContent = Math.round(fill) + "%";
  const ticks = el("ticks");
  ticks.replaceChildren();
  for (const point of points) {
    const checkpoint = checkpoints.find(value => number(value.capture_count) >= point);
    const active = !checkpoint && (count >= point || number(progress.next_threshold) === point);
    const tick = node("button", "tick" + (checkpoint ? " done" : active ? " active" : ""), point.toLocaleString());
    tick.type = "button";
    const remaining = Math.max(0, point - count);
    tick.title = checkpoint
      ? "Summary checkpoint complete at " + point.toLocaleString() + " exchanges."
      : !counted ? "Count traffic to check this threshold."
      : count >= point
        ? "Threshold reached; its summary has not been saved. This does not mean a job is running."
        : remaining.toLocaleString() + " exchanges until this summary threshold.";
    tick.setAttribute("aria-label", tick.title);
    tick.addEventListener("click", () => {
      el("summaries").open = true;
      const card = Array.from(el("milestones").children).find(item => Number(item.dataset.threshold) === point);
      if (card?.tagName === "DETAILS") card.open = true;
      (card || el("summaries")).scrollIntoView({block: "center"});
    });
    ticks.append(tick);
  }
  el("milestones").replaceChildren();
  const savedPoints = [...new Set([...points, ...checkpoints.map(value => number(value.capture_count))])].sort((a, b) => a - b);
  for (const point of savedPoints) {
    const checkpoint = checkpoints.find(value => number(value.capture_count) >= point);
    const card = node(checkpoint ? "details" : "div", "checkpoint" + (checkpoint ? " reached" : count >= point ? " crossed" : ""));
    card.dataset.threshold = point;
    if (checkpoint) {
      card.dataset.uuid = checkpoint.uuid;
      card.open = opened.has(checkpoint.uuid);
      const disclosure = node("summary", "checkpoint-head");
      disclosure.title = "Open the structured summary for this checkpoint.";
      const identity = node("small", "", "saved · ");
      identity.append(copyButton(short(checkpoint.uuid), checkpoint.uuid, "summary ID"));
      disclosure.append(node("i", "pin"), document.createTextNode(point.toLocaleString() + (number(checkpoint.capture_count) === point ? " exchanges" : " threshold · " + number(checkpoint.capture_count).toLocaleString() + " exchanges included")), identity);
      const quality = checkpoint.quality || {};
      const counters = checkpoint.counters || {};
      const traffic = checkpoint.traffic || {};
      const semantic = checkpoint.semantic || {};
      const values = checkpoint.series || {};
      const body = node("div", "summary-body");
      body.append(
        summaryRow("exchanges included", number(checkpoint.capture_count).toLocaleString() + " captured · " + number(counters.unique_contents).toLocaleString() + " unique", "One exchange is one request and its response, not necessarily a complete conversation or successful task."),
        summaryRow("source groups", counters.source_groups ? number(counters.source_groups) + " groups · " + number(counters.trajectory_groups) + " tagged tasks · " + number(counters.untagged_request_groups) + " untagged requests" : "not recorded", "Exchanges within a tagged task stay together. Untagged requests are grouped by request content; group counts do not prove independent tasks."),
        summaryRow("sample reviewed", number(semantic.classified).toLocaleString() + " of " + number(checkpoint.capture_count).toLocaleString() + " exchanges · " + number(semantic.abstained) + " left unlabeled by the model", "Topic and task labels come from the reviewed sample, not all saved traffic. The model may decline to label a reviewed exchange. Labels are estimates, not verified task outcomes."),
        distributionChart("topics", semantic.domain, semantic.classified, "What the sampled exchanges are about. Counts refer only to the classified sample."),
        distributionChart("tasks", semantic.operation, semantic.classified, "What users asked the model to do."),
        distributionChart("reported outcomes", semantic.outcome, semantic.classified, "The classifier's estimate, not a correctness test. Unknown means no outcome was established."),
        distributionChart("capabilities", semantic.capability, semantic.classified, "Skills the sampled tasks require. One exchange can receive multiple labels, so these counts may overlap."),
        summaryRow("how to check answers", counts(semantic.oracle), "Suggested ways to grade these tasks, not checks that have already run."),
        summaryRow("language + tone", counts(semantic.language) + " · " + counts(semantic.sentiment), "Languages and broad sentiment labels detected in the classified sample.")
      );
      const delivery = node("details", "summary-delivery");
      delivery.open = deliveryOpened.has(checkpoint.uuid);
      const measurements = node("div", "summary-body");
      measurements.append(
        summaryRow("traffic through", checkpoint.created_at ? new Date(checkpoint.created_at).toLocaleString() : "timestamp unavailable", "Completion time of the latest exchange added to this checkpoint."),
        summaryRow("request integrity", percent(quality.parse_bps) + " parsed · " + percent(quality.success_bps) + " HTTP success · " + percent(quality.duplicate_bps) + " duplicate", "HTTP success means a 2xx response. It does not prove a correct answer, completed task, or uninterrupted capture."),
        summaryRow("capture observations", (quality.capture_gap ? "gap recorded" : "no gap recorded") + " · peak " + number(counters.max_concurrency) + " concurrent", "These are recorded observations, not a guarantee that every request was captured."),
        summaryRow("models", counts(traffic.model), "Model names requested by captured applications."),
        summaryRow("endpoints", counts(traffic.endpoint), "Responses and Chat Completions requests in this checkpoint."),
        summaryRow("routes", counts(traffic.route_target), "Requests served by the baseline or an approved candidate."),
        summaryRow("response", counts(traffic.status_class) + " · streaming " + counts(traffic.streaming) + " · structured " + counts(traffic.structured_output), "HTTP results plus streaming and structured-output use."),
        summaryRow("traffic", counts(traffic.modalities) + " · outcome " + counts(traffic.outcome) + " · fallback " + counts(traffic.fallback_reason), "Input modes, request outcomes, and any candidate fallback reasons."),
        summaryRow("reasoning", counts(traffic.reasoning_effort), "Reasoning-effort values requested by applications when present."),
        summaryRow("total time", series(values.total_ms, duration, true), "Time from request start to the complete response."),
        summaryRow("first response byte", series(values.ttft_ms, duration, true), "Time to the first response byte. With a non-streaming response this can be the full wait, not time to the first generated token."),
        summaryRow("generation", series(values.tps_milli, item => (number(item) / 1000).toFixed(1) + " tok/s"), "Observed output-token generation rate when token counts are available."),
        summaryRow("input tokens", series(values.input_tokens), "Input tokens reported by the model provider."),
        summaryRow("output tokens", series(values.output_tokens), "Output tokens reported by the model provider.")
      );
      delivery.append(node("summary", "", "delivery, model settings + timing"), measurements);
      card.append(disclosure, body, delivery);
    } else {
      const title = node("h3");
      title.append(node("i", "pin"), document.createTextNode(point.toLocaleString()));
      card.append(title, node("small", "", !counted ? "capture count not checked" : count >= point ? "threshold reached · summary not saved" : (point - count).toLocaleString() + " exchanges to go"));
      card.title = count >= point ? "This threshold has been reached. A summary has not been saved; no running job is implied." : "Traffic is still accumulating for this checkpoint.";
    }
    el("milestones").append(card);
  }
  if (!savedPoints.length) el("milestones").append(node("p", "empty", "no thresholds configured"));
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
    traffic: Number.isInteger(value.capture_count) ? value.capture_count + " captured" : "not counted",
    summary: value.summary ? "saved · " + short(value.summary.uuid) : "no summary yet",
    readiness: value.readiness ? (value.readiness.ready ? "ready" : "not ready") : "waiting",
    eval: value.eval_generation ? value.eval_generation.completed_case_count + " / " + value.eval_generation.target_case_count : value.eval ? value.eval.case_count + " cases" : "waiting",
    dataset: value.dataset ? "revision " + short(value.dataset.uuid) : "waiting",
    training: value.training ? "model " + short(value.training.uuid) : "waiting",
    evaluation: value.evaluation ? value.evaluation.winner_branch + " selected" : "waiting",
    candidate: value.candidate ? "prepared · " + short(value.candidate.uuid) : "waiting",
    proposal: value.proposal ? "awaiting operator signature" : "no proposal yet",
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
      summaryRow("needed before running", startsWhen, "A prerequisite, not proof that this step is currently scheduled or running.")
    );
    if (records[key]) body.append(summaryRow("record", short(records[key]), "The first eight characters of the stored record UUID.", records[key]));
    card.append(heading, body);
    card.addEventListener("toggle", () => { if (card.open) selectStage(index); });
    el("rail").append(card);
  });
  selectStage(selectedStage);
}

function renderRun(status = {}, progress = {}) {
  const profile = status.profile || "unknown";
  const badge = el("run-profile");
  badge.textContent = profile === "mechanics" ? "DEVELOPMENT SETTINGS" : profile.toUpperCase() + " SETTINGS";
  badge.title = profile === "mechanics"
    ? "This scope uses the mechanics policy to try the workflow. This is not a label for where the data came from or which training split it belongs to."
    : profile === "production"
      ? "A production run uses the production traffic and readiness policy for this scope."
      : "The current scope profile is not known.";
  el("run-now").textContent = nextCopy[status.next_action] || String(status.next_action || "waiting for object memory").replaceAll("-", " ");
  if (status.next_action === "summary" && progress.next_threshold && Number.isInteger(progress.capture_count)) {
    el("run-now").textContent = progress.capture_count >= progress.next_threshold
      ? progress.next_threshold.toLocaleString() + "-exchange threshold reached · summary not saved"
      : (progress.next_threshold - progress.capture_count).toLocaleString() + " more exchanges before the next summary";
  }
  const scope = status.scope_id || "";
  const scopeNode = el("run-scope");
  scopeNode.replaceChildren(scope ? document.createTextNode("scope ") : document.createTextNode("scope unknown"));
  if (scope) scopeNode.append(copyButton(short(scope), scope, "scope ID"));
  scopeNode.title = scope || "No scope is configured.";
}

function environmentHelp(name) {
  const specific = {
    MILK_SCOPE_ID: "The UUID that keeps this run's traffic and results together in storage.",
    MILK_STORE_KIND: "Select local files or an S3-compatible object store, such as Cloudflare R2.",
    MILK_SUMMARY_THRESHOLDS: "Saved-exchange counts at which to make summaries. These are the ticks on the traffic bar.",
    MILK_CASES_PER_CONVERSATION: "How many new example cases to generate for each selected conversation.",
    MILK_EVAL_SOURCE_CONVERSATIONS: "How many source conversations to select for example generation.",
    MILK_SUMMARY_REPRESENTATIVE_SAMPLE: "How many exchanges to sample for a broad picture of the traffic.",
    MILK_SUMMARY_TAIL_SAMPLE: "How many unusual or less common exchanges to sample as well.",
    MILK_MAN_MAX_ITERATIONS: "Maximum model replies in one agent turn, not the lifetime of the heartbeat.",
  };
  if (specific[name]) return specific[name];
  const rules = [
    [/SECRET_NAME$/, "Name of a secret already saved with the provider; not the secret value itself."],
    [/SECRET_MAP_JSON$/, "JSON mapping of job environment names to secrets saved with the provider."],
    [/SECRET|TOKEN_SECRET|API_KEY$|ACCESS_KEY|SESSION_TOKEN|HF_TOKEN/, "Credential used by this job. The dashboard shows only whether it is set, never the value."],
    [/BASE_URL$|API_URL$|ENDPOINT$/, "The address this job connects to. Different jobs can use different providers."],
    [/REASONING_EFFORT$/, "Reasoning level requested from the selected model."],
    [/API_MODE$/, "Choose the Responses or Chat Completions request format supported by the endpoint."],
    [/REVISION$/, "Pinned model-weight version, so repeated runs use the same files."],
    [/MODEL$/, "Model this job requests or serves. It can differ from the model driving chat."],
    [/IMAGE$/, "Container image for the remote runtime. Model weights are loaded separately."],
    [/GPU_COUNT$/, "Number of GPUs for the model server."],
    [/GPU$|ACCELERATOR$/, "GPU type requested from the selected provider."],
    [/VLLM_ARGS_JSON$/, "Extra vLLM serving arguments as a JSON array; used to tune the model server."],
    [/SCALEDOWN_SECONDS$/, "Idle time before the provider scales down this server."],
    [/CONCURRENCY$/, "Number of concurrent requests the serving job is configured to handle."],
    [/TIMEOUT/, "Time limit for this job or operation, in seconds."],
    [/MAX.*TOKENS$/, "Maximum token allowance for this operation; reasoning can consume part of it."],
    [/SHA256$/, "Expected file or object digest. The job checks it before using that input."],
    [/FILE$/, "Path to this job's input or saved configuration file."],
  ];
  return rules.find(([pattern]) => pattern.test(name))?.[1] || "Setting read by this job's script. Its meaning and default are defined in the repository; click the name to copy it.";
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
    const help = environmentHelp(value.name) + " " + (value.set ? "Present" : "Not set") + " in the dashboard environment; this does not verify provider access.";
    item.append(node("i", "pin"), copyButton(value.name, value.name, "environment name"), node("small", "", value.set ? "set" : optional ? "unset" : "missing"));
    const button = helpHeading(value.name, help).querySelector("button");
    item.append(button);
    list.append(item);
  }
  section.append(list);
  return section;
}

let contractKey;
function filterJobs() {
  const query = el("job-search").value.trim().toLowerCase();
  const cards = Array.from(el("jobs").querySelectorAll("details.job"));
  for (const card of cards) card.hidden = !card.textContent.toLowerCase().includes(query);
  el("job-matches").textContent = query ? cards.filter(card => !card.hidden).length + " matching actions" : "";
}
function renderContract(contract = {}) {
  const key = JSON.stringify(contract);
  if (key === contractKey) return;
  contractKey = key;
  const target = el("jobs");
  const opened = new Set(Array.from(target.querySelectorAll("details.job[open]"), item => item.dataset.job));
  const controls = new Set(Array.from(target.querySelectorAll("details.controls[open]"), item => item.dataset.job));
  target.replaceChildren();
  if (contract.error) {
    target.append(node("p", "empty", contract.error));
    el("job-matches").textContent = "";
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
      node("b", "", jobLabels[job.name] || job.name),
      node("small", "", missing.length ? missing.length + " setting" + (missing.length === 1 ? "" : "s") + " needed" : "settings present")
    );
    const body = node("div", "job-body");
    body.append(node("p", "", jobCopy[job.name] || job.description || "A repository job."));
    const facts = node("div", "facts");
    facts.append(
      summaryRow("needed before running", triggerCopy[job.trigger] || String(job.trigger || "manual").replaceAll("_", " "), "A prerequisite, not proof that this action is running or scheduled."),
      summaryRow("run", job.command, "Run this exact reviewed job explicitly.", job.command),
      summaryRow("scheduling", job.automatic ? "included in the traffic workflow" : "runs when explicitly selected"),
      summaryRow("reads", (job.inputs || []).map(value => prefixCopy[value] || value).join(" · ") || "not listed by this script"),
      summaryRow("writes", (job.outputs || []).map(value => prefixCopy[value] || value).join(" · ") || "not listed by this script"),
      summaryRow("instructions", job.prompt || "defined by the job script", "The script defines whether this job calls a model and what it asks.", job.prompt || undefined),
      summaryRow("time limit", job.timeout || "not configured", "Environment name controlling the job timeout.", job.timeout || undefined)
    );
    body.append(facts, environmentList("required environment", job.required || []));
    const optional = node("details", "controls");
    optional.dataset.job = job.name;
    optional.open = controls.has(job.name);
    optional.append(node("summary", "", "optional settings"), environmentList("optional environment", job.optional || [], true));
    const action = node("button", "", "ask Milk Man about this tool");
    action.type = "button";
    action.dataset.draft = "Explain how to use the " + job.name + " job with our current environment, including any missing settings. Do not run it or change resources.";
    const actions = node("div", "drafts");
    actions.append(action, node("small", "", "Prepares a message; it does not run the job."));
    body.append(optional, actions);
    card.append(heading, body);
    target.append(card);
  }
  filterJobs();
}

let activityKey = "", finalKey = "";
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
    idle: "Milk Man online · ready for a task" + jobStatus,
    setup: "Milk Man online · session setup needed",
  };
  light("man", state === "failed" ? "degraded" : man.online ? "up" : "down", man.online ? labels[state] || labels.setup : man.trajectory_id ? "Milk Man offline · session saved" : "Start a session from Bash");
  el("driver-detail").textContent = "Model: " + (driverStatus || "not configured") + ". Session: " + (man.trajectory_id || "not started") + ".";
  el("active-model").textContent = "chat model: " + (driver.model || "not configured") + (driver.reasoning_effort ? " · " + driver.reasoning_effort + " reasoning" : "");
  const pulse = man.heartbeat || {};
  const heartbeatOnline = pulse.online === true;
  const heartbeatStarting = !heartbeatOnline && man.connection === "attached" && man.active;
  const heartbeatRetained = !heartbeatOnline && Boolean(pulse.state || pulse.checked_at || pulse.next_wake);
  const heartbeatState = heartbeatOnline ? (pulse.state || "idle") : heartbeatStarting ? "starting" : heartbeatRetained ? "stopped" : "not started";
  light("heartbeat", heartbeatOnline ? (pulse.state === "failed" ? "degraded" : "up") : heartbeatStarting ? "ready" : "down", "heartbeat · " + heartbeatState);
  const workActive = heartbeatOnline && (pulse.state === "running" || man.active);
  const task = (pulse.task || "No task saved yet.").replace(/^Continue the saved task:\s*/, "");
  el("task-label").textContent = workActive || (heartbeatOnline && pulse.state === "waiting") ? "current task" : "last saved instruction";
  el("current-work").textContent = task.split(/\n|(?<=[.!?])\s/)[0].slice(0, 220);
  el("current-instruction").hidden = !pulse.brief || pulse.brief === pulse.task;
  el("current-instruction").textContent = pulse.brief ? "Latest instruction: " + pulse.brief.split(/\n|(?<=[.!?])\s/)[0].slice(0, 220) : "";
  el("current-work-note").textContent = !heartbeatOnline ? "The task is saved, but no heartbeat owner is connected."
    : workActive ? (jobs ? "Running: " + jobNames + "." : "Working through the task. New replies appear below.")
    : pulse.state === "waiting" ? pulse.watch_state === "unknown"
      ? "The task is waiting, but its job status is unknown. This does not confirm a worker is running."
      : "Watching " + (pulse.watch_label || "saved work") + (pulse.watch_pid ? " · process " + pulse.watch_pid : "") + (pulse.watch_state ? " · " + pulse.watch_state : "") + ". Unchanged checks use no model calls."
    : pulse.state === "failed" ? "The last turn failed. Open its result below before continuing."
    : pulse.state === "paused" ? "Paused. Send an instruction to continue."
    : "Ready for your next instruction. Idle checks use no model calls.";
  const resource = pulse.watch_resource || {};
  const resourceRow = el("heartbeat-resource");
  resourceRow.replaceChildren();
  resourceRow.hidden = !resource.provider_status;
  if (resource.provider_status) {
    el("current-work-note").textContent = "Model server " + resource.provider_status.toLowerCase().replaceAll("_", " ")
      + (Number.isInteger(resource.active_replicas) ? " · " + resource.active_replicas + " active replicas" : "") + ".";
    resourceRow.append(node("span", "", "Last reported by the watched job. Zero replicas during a build does not mean it has been stopped. "));
    for (const [key, label] of [["model_id", "model"], ["deployment_id", "deployment"]]) {
      if (resource[key]) resourceRow.append(copyButton(label + " " + resource[key], resource[key], label + " ID"));
    }
  }
  for (const [id, stamp] of [["last", pulse.checked_at], ["next", heartbeatOnline && !workActive && pulse.state !== "paused" ? pulse.next_wake : null]]) {
    const target = el("heartbeat-" + id);
    target.textContent = stamp ? new Date(stamp * 1000).toLocaleTimeString() : id === "next" && workActive ? "after current work" : id === "next" && heartbeatStarting ? "after startup" : "not scheduled";
    target.dateTime = stamp ? new Date(stamp * 1000).toISOString() : "";
  }
  el("heartbeat-count").textContent = (pulse.turns || 0) + " work sessions · " + (pulse.polls || 0) + " idle checks";
  el("heartbeat-task").textContent = pulse.task || "No task saved yet.";
  el("heartbeat-brief").hidden = !pulse.brief;
  el("heartbeat-brief").textContent = pulse.brief ? "Latest instruction: " + pulse.brief : "";
  el("conversation-state").textContent = state + (man.queued ? " · next instruction queued" : "") + (state === "failed" && Number.isInteger(man.last_exit_code) ? " · exit " + man.last_exit_code : "");
  el("conversation-state").title = pulse.checked_at ? "Heartbeat last checked " + new Date(pulse.checked_at * 1000).toLocaleString() + ". Unchanged idle checks use no model tokens." : "Heartbeat starts with your next task. Closing this page does not stop it.";
  if (!runLoading) {
    runState(el("prompt-text").value.trim() ? "Unsent message · review it, then send to Milk Man."
      : man.active ? "Milk Man is working. Output will appear above."
      : man.queued ? "Instruction queued behind the current run."
      : state === "failed" ? "The last turn failed. Review its output, then send a correction."
      : state === "waiting" ? "Milk Man will continue when the watched job changes or its next review is due."
      : state === "paused" ? "Automatic continuation is paused. Send an instruction to continue."
      : state === "setup" ? "Start your first session from Bash; see connect an app → local agent setup."
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
  const initial = !activityKey;
  const nextFinalKey = JSON.stringify(man.activity.findLast(event => event.type === "final"));
  const newFinal = nextFinalKey !== finalKey;
  finalKey = nextFinalKey;
  const follow = initial || target.scrollHeight - target.scrollTop - target.clientHeight < 64;
  activityKey = nextActivityKey;
  const scroll = target.scrollTop;
  const opened = new Set(Array.from(target.querySelectorAll("details[open]"), value => value.dataset.key));
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
      const label = event.type === "process-output" ? "live process log" : "command output";
      const last = group[group.length - 1];
      const exits = group.map(value => value.content.match(/\nexit (\S+)$/)?.[1]).filter(Boolean);
      message.append(
        node("summary", "", label + (exits.length ? " · exit " + exits.join(", ") : " · " + group.length + " lines") + (last.ts ? " · " + last.ts + " UTC" : "")),
        node("pre", "", group.map(value => value.content).join("\n\n"))
      );
      target.append(message);
      index += group.length;
      continue;
    }
    const role = event.type === "prompt" ? "you" : "milk-man";
    if ((role === "you" && event.content.length > 500) || (role === "milk-man" && event.type !== "final" && (event.content.length > 1200 || event.content.startsWith("```")))) {
      const message = node("details", "message " + role + " folded");
      message.dataset.key = index + ":" + (event.ts || event.type);
      message.open = opened.has(message.dataset.key);
      const intro = event.content.split("```")[0].trim();
      if (role === "milk-man" && intro) {
        const reply = node("article", "message milk-man");
        reply.append(node("b", "", "milk man"), node("p", "", intro.slice(0, 1200)));
        target.append(reply);
      }
      const label = role === "you" ? "instruction · " + event.content.split(/\n|(?<=[.!?])\s/)[0].slice(0, 100) : "command + full reply";
      message.append(node("summary", "", label + (event.ts ? " · " + event.ts + " UTC" : "")), node("pre", "", event.content));
      target.append(message);
      index++;
      continue;
    }
    const message = node("article", "message " + role);
    message.append(node("b", "", role === "you" ? "instruction" : "milk man"), event.type === "final" ? replyBody(event.content) : node("pre", "", event.content));
    const rest = message.querySelector(".reply-rest");
    if (rest) {
      rest.dataset.key = index + ":" + event.ts + ":reply";
      rest.open = opened.has(rest.dataset.key);
    }
    if (event.ts) message.append(node("time", "", event.ts + " UTC"));
    target.append(message);
    index++;
  }
  if (follow && (initial || newFinal)) latestReply();
  else if (follow) target.scrollTop = target.scrollHeight;
  else target.scrollTop = scroll;
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
  const jobStatus = data.contract?.error ? "job configuration unavailable" : readyJobs + " / " + jobs.length + " have required settings here";
  el("job-count").textContent = jobStatus;
  el("watch-state").textContent = "Replies appear here as Milk Man works. You can send a correction while it runs; it will pick it up at the next safe step.";
  const status = milk.status || {};
  renderRun(status, milk.progress);
  renderProgress(milk.progress);
  renderLoop(status);
  renderContract(data.contract || {});
  renderResearch(milk.research || {});
  rows(el("object"), milk.error ? [{ title: "unavailable", detail: milk.error }] : milk.missing.length ? [{ title: "not configured", detail: milk.missing.join("\n") }] : [
    { title: "next data step", detail: nextCopy[status.next_action] || String(status.next_action || "waiting").replaceAll("-", " "), help: "The next action suggested by saved data, not proof that a job is scheduled or running." },
    { title: "data policy", detail: status.profile === "mechanics" ? "development settings" : status.profile || "unknown", help: "The selected rules for trying the workflow. This does not identify the origin of the traffic or establish model quality." },
    { title: "scope", detail: status.scope_id ? short(status.scope_id) : "unknown", help: status.scope_id || "No scope is configured." },
    { title: "capture writer", detail: !["up", "degraded"].includes(gateway.state) ? "unavailable · last totals unknown" : number(gateway.observed) + " received · " + number(gateway.persisted) + " stored · " + number(gateway.dropped) + " dropped", help: "Milk Parlor totals since its current process started, across its configured scopes. Not this scope's stored traffic count." },
  ], "waiting for status");
  el("foot").textContent = "Local dashboard · status checked " + new Date(data.now).toLocaleTimeString();
}

function recordFields(value) {
  if (value == null) return node("p", "", "Not measured or recorded yet.");
  if (Array.isArray(value)) {
    const list = node("div");
    if (!value.length) list.append(node("p", "", "No results saved yet."));
    value.forEach(item => { const row = node("div", "record-item"); row.append(recordFields(item)); list.append(row); });
    return list;
  }
  if (typeof value !== "object") return node("span", "", String(value));
  const list = node("dl", "record-fields");
  Object.entries(value).forEach(([key, item]) => {
    const label = key.replaceAll("_", " ");
    const detail = node("dd");
    if (typeof item === "string" && /(?:sha256|uuid|revision|_id|_key|_file)$/.test(key)) detail.append(copyButton(item.length > 64 ? item.slice(0, 60) + "…" : item, item, label));
    else detail.append(recordFields(item));
    list.append(node("dt", "", label), detail);
  });
  return list;
}

function experimentCard(value, index) {
  const card = node("article", "experiment");
  const label = String(value.name || (value.kind === "tiny_sequential_serving_setting_comparison" ? "Compare model-server settings" : value.kind) || "saved result").replaceAll(/[_-]/g, " ");
  card.append(node("h3", "", (index + 1) + " · " + label));
  const conclusion = value.conclusion || value.decision || value.comparison?.conclusion || value.limitations;
  if (typeof conclusion === "string") card.append(node("p", "", conclusion));
  const baseline = value.configurations?.baseline;
  const candidate = value.configurations?.candidate;
  if (baseline && candidate) {
    const table = node("table", "experiment-comparison");
    table.append(node("caption", "", "Recorded comparison · lower time is better"));
    const head = node("tr");
    for (const label of ["measurement", "previous setting", "trial setting"]) {
      const cell = node("th", "", label); cell.scope = "col"; head.append(cell);
    }
    const body = node("tbody");
    for (const [key, label] of [["mean_e2e_ms", "average full reply"], ["mean_ttft_ms", "average first text"]]) {
      if (!Number.isFinite(baseline[key]) || !Number.isFinite(candidate[key])) continue;
      const row = node("tr");
      const heading = node("th", "", label); heading.scope = "row";
      row.append(heading);
      for (const amount of [baseline[key], candidate[key]]) {
        const cell = node("td", "", duration(amount));
        const bar = node("meter", "comparison-bar");
        bar.min = 0; bar.max = Math.max(baseline[key], candidate[key], 1); bar.value = amount;
        bar.setAttribute("aria-label", label + ": " + duration(amount));
        cell.append(bar); row.append(cell);
      }
      body.append(row);
    }
    const header = node("thead"); header.append(head); table.append(header, body);
    if (body.children.length) {
      card.append(table);
      const change = baseline.mean_e2e_ms > 0 && Number.isFinite(candidate.mean_e2e_ms) ? 100 * (candidate.mean_e2e_ms / baseline.mean_e2e_ms - 1) : null;
      if (change !== null) card.append(node("p", "comparison-change", Math.abs(change).toFixed(1) + "% " + (change > 0 ? "slower" : change < 0 ? "faster" : "change") + " full reply with the trial setting. This measures speed, not overall answer quality."));
    }
  }
  if (typeof value.scope === "string") card.append(node("p", "", value.scope));
  const detail = node("details");
  detail.append(node("summary", "", "measurements + saved references"), recordFields(value));
  card.append(detail);
  return card;
}

let researchKey;
function renderResearch(value) {
  const key = JSON.stringify(value);
  if (key === researchKey) return;
  researchKey = key;
  const record = value.record;
  const target = el("research");
  el("research-state").textContent = value.error || (record ? (record.experiments || []).length + " saved results" : "no objective saved");
  if (!record) return rows(target, [], value.error || "Ask Milk Man to save a research objective for this scope using the research job.");
  const opened = new Set(Array.from(target.querySelectorAll("details[open]"), item => item.dataset.field));
  rows(target, [
    { title: "research goal", detail: record.objective },
    { title: "saved next-step note", detail: record.next_action, help: "A note from the saved research record, not a live schedule. It can lag behind the latest chat result." },
  ]);
  const comparison = node("div", "comparison-status");
  for (const [field, label, help] of [
    ["baseline", "reference model", "The model and settings used for comparison. A serving-speed experiment alone does not establish a model-quality reference."],
    ["evaluation", "evaluation tasks", "Tasks kept out of training, used to compare answers fairly."],
    ["best", "best model", "A model selected from measured comparisons on this scope's tasks. Not the chat model or a currently running GPU."],
  ]) comparison.append(summaryRow(label, record[field] ? "recorded · details below" : {baseline: "Not selected for task comparison", evaluation: "No comparison tasks saved", best: "No best model selected"}[field], help));
  target.append(comparison);
  if (record.experiments?.length) {
    const latest = node("div", "row latest-result");
    latest.append(helpHeading("latest saved result", "The most recently appended research entry. It may describe an earlier run; opening it starts nothing."), experimentCard(record.experiments.at(-1), record.experiments.length - 1));
    target.append(latest);
  }
  const revision = node("div", "row");
  revision.append(node("small", "", "saved version"), copyButton(short(value.revision), value.revision, "research revision"));
  target.append(revision);
  for (const [field, label, help] of [["targets", "what counts as better", "The quality, speed, and cost targets for this scope."], ["baseline", "reference model", "The existing model and settings each candidate is compared against."], ["evaluation", "tasks kept out of training", "The same untouched tasks must be used for a fair comparison."], ["best", "best measured result", "A saved candidate needs comparable measurements before it can be called better."], ["experiments", "past experiments", "Completed experiments, including failed attempts and losses. Saved notes are not independent verification."], ["wake", "when to check again", "A proposed wake condition. It runs only after the heartbeat registers a matching watch."]]) {
    const detail = node("details");
    detail.dataset.field = field;
    detail.open = opened.has(field);
    const heading = node("summary", "", label);
    heading.title = help;
    detail.append(heading);
    const body = node("div", "row");
    if (field === "experiments" && record.experiments?.length) record.experiments.forEach((item, index) => body.append(experimentCard(item, index)));
    else body.append(recordFields(record[field]));
    detail.append(body);
    target.append(detail);
  }
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
    el("refresh").textContent = "count saved traffic";
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
    el("current-work-note").textContent = "Dashboard connection lost. The task may still be running; reconnect before sending another instruction.";
    el("conversation-state").textContent = "connection lost";
    runState("Cannot reach the local dashboard server. Your task may still be running.", true);
  }
}

el("refresh").addEventListener("click", () => refreshCloud(true));
el("job-search").addEventListener("input", filterJobs);
window.addEventListener("hashchange", showView);
showView();
el("latest-message").addEventListener("click", latestReply);
el("stage-scrubber").addEventListener("input", event => selectStage(number(event.target.value) - 1, true));
document.querySelectorAll("[data-copy]").forEach(button => button.addEventListener("click", () => copyValue(button.dataset.copy, button.dataset.copyLabel)));
document.addEventListener("click", event => {
  const button = event.target.closest?.("[data-draft]");
  if (button) draftPrompt(button.dataset.draft);
});
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

// One tooltip for static and freshly rendered fields; touch can tap a help button.
const helpTip = el("help-tip");
let helpOwner, helpTimer;
function hideHelp() {
  helpTip.hidden = true;
  if (helpOwner) {
    const remaining = (helpOwner.getAttribute("aria-describedby") || "").split(" ").filter(id => id && id !== "help-tip").join(" ");
    if (remaining) helpOwner.setAttribute("aria-describedby", remaining);
    else helpOwner.removeAttribute("aria-describedby");
    helpOwner = null;
  }
}
function showHelp(target) {
  const owner = target.closest?.(".help, .copy, .tick, .view-nav a, [data-tooltip]");
  if (!owner) return;
  clearTimeout(helpTimer);
  hideHelp();
  const text = owner.getAttribute("title") || owner.dataset.help;
  if (!text) return;
  owner.dataset.help = text;
  owner.removeAttribute("title");
  helpOwner = owner;
  owner.setAttribute("aria-describedby", [owner.getAttribute("aria-describedby"), "help-tip"].filter(Boolean).join(" "));
  helpTip.textContent = text;
  helpTip.hidden = false;
  const box = owner.getBoundingClientRect();
  helpTip.style.left = Math.max(8, Math.min(box.left, innerWidth - helpTip.offsetWidth - 8)) + "px";
  helpTip.style.top = Math.max(8, box.bottom + helpTip.offsetHeight + 8 < innerHeight ? box.bottom + 4 : box.top - helpTip.offsetHeight - 4) + "px";
}
document.addEventListener("pointerover", event => { if (helpTip.contains(event.target)) clearTimeout(helpTimer); else showHelp(event.target); });
document.addEventListener("pointerout", () => { helpTimer = setTimeout(hideHelp, 150); });
document.addEventListener("focusin", event => showHelp(event.target));
document.addEventListener("focusout", hideHelp);
document.addEventListener("click", event => {
  if (event.target.closest?.(".help")) showHelp(event.target);
  else if (!helpTip.contains(event.target)) hideHelp();
});
document.addEventListener("keydown", event => { if (event.key === "Escape") hideHelp(); });
document.addEventListener("scroll", hideHelp, true);
