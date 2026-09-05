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
  talk: ["Chat", "Give Milk Man a task. Read its replies and check its progress here."],
  traffic: ["Data and summaries", "Every exchange is a request and its response. A summary counts them; a model labels a sample."],
  research: ["Experiment results", "See what changed, how it performed, and what remains untested."],
  jobs: ["Tools and settings", "Find an action and the settings it needs. Opening one runs nothing."],
  connect: ["Keep your OpenAI calls", "Point the official SDK at Milk Parlor. Your application still calls the same API."],
};
let chatVisited = false;
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
  if (view === "talk" && !chatVisited) {
    chatVisited = true;
    requestAnimationFrame(latestReply);
  }
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

function plainLabel(value) {
  return ({plan_or_tool_use: "Planning and tool use", instruction_following: "Following instructions", tool_use: "Using tools", structured_output: "Formatted output", math_science: "Math and science", unknown: "Unknown", partial: "Partly completed", executable: "Run the task and check", pairwise_judge: "Compare two answers", en: "English", true: "Yes", false: "No", baseline: "Original model"})[value] || value.replaceAll("_", " ");
}

function counts(values) {
  return Object.entries(values || {}).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(value => plainLabel(value[0]) + " " + value[1].toLocaleString()).join(" · ") || "not recorded";
}

function percent(basisPoints) {
  if (!Number.isFinite(basisPoints)) return "not recorded";
  return (number(basisPoints) / 100).toFixed(number(basisPoints) % 100 ? 2 : 0) + "%";
}

function qualityCount(value, total, basisPoints) {
  const ratio = Number.isInteger(value) && Number.isInteger(total) ? value.toLocaleString() + " / " + total.toLocaleString() : "count not recorded";
  return ratio + (Number.isFinite(basisPoints) ? " · " + percent(basisPoints) : "");
}

function seriesCount(stat = {}) {
  if (!Number.isInteger(stat.count) || stat.count <= 0 || !Number.isFinite(stat.mean_milli)) return "not recorded";
  const average = (stat.mean_milli / 1000).toLocaleString(undefined, {maximumFractionDigits: 1});
  return average + " average" + (Number.isFinite(stat.min) && Number.isFinite(stat.max) ? " · " + stat.min.toLocaleString() + "–" + stat.max.toLocaleString() + " observed" : "") + " · " + stat.count.toLocaleString() + " exchanges";
}

function duration(value) {
  const amount = number(value);
  return amount >= 1000 ? (amount / 1000).toFixed(amount % 1000 ? 1 : 0) + "s" : amount.toLocaleString(undefined, {maximumFractionDigits: 1}) + "ms";
}

function countBar(value, total, label) {
  const bar = node("div", "count-bar");
  const known = Number.isFinite(value) && Number.isFinite(total) && total >= 0;
  bar.setAttribute("role", "img");
  bar.setAttribute("aria-label", known ? value.toLocaleString() + " of " + total.toLocaleString() + " " + label : "Count not recorded");
  const fill = known && total > 0 ? Math.max(0, Math.min(1, value / total)) * 20 : 0;
  for (let index = 0; index < 20; index++) {
    const segment = node("i"), ink = node("b");
    ink.style.width = Math.max(0, Math.min(1, fill - index)) * 100 + "%";
    segment.append(ink); bar.append(segment);
  }
  return bar;
}

function responseStats(values, group) {
  const wrapper = node("div", "table-scroll");
  const table = node("table", "experiment-comparison");
  table.append(node("caption", "", group === "tokens" ? "Provider-reported tokens. Samples can differ when usage was not returned." : "Timings for the summarized exchanges, including the model provider."));
  const head = node("tr");
  for (const title of ["Measurement", "Average", "Observed range", "Approx. 95% below", "Samples"]) {
    const cell = node("th"); cell.scope = "col";
    cell.append(helpHeading(title, title === "Approx. 95% below" ? "An upper-bound estimate from grouped measurements. At least about 95% fall below it. It can exceed the observed maximum; it is not an exact percentile." : null));
    head.append(cell);
  }
  const header = node("thead"); header.append(head); table.append(header);
  const body = node("tbody");
  for (const [key, label, format, help] of [
    ["total_ms", "Full response", duration, "Request start to complete response."],
    ["ttft_ms", "First response byte", duration, "For a non-streaming request, this can be the full wait. It is not always the first generated token."],
    ["tps_milli", "End-to-end output rate", value => (value / 1000).toFixed(1) + " tok/s", "Output tokens divided by full request time, including waiting. This is not the model's decode speed."],
    ["input_tokens", "Input tokens", value => value.toLocaleString(undefined, {maximumFractionDigits: 1}), "Input tokens reported by the provider."],
    ["output_tokens", "Output tokens", value => value.toLocaleString(undefined, {maximumFractionDigits: 1}), "Output tokens reported by the provider."],
    ["cached_tokens", "Cached input tokens", value => value.toLocaleString(undefined, {maximumFractionDigits: 1}), "Input tokens reported as served from cache. These are part of input usage, not extra tokens."],
    ["reasoning_tokens", "Reasoning tokens", value => value.toLocaleString(undefined, {maximumFractionDigits: 1}), "Reasoning tokens reported by the provider, where available. These may be part of output usage; do not add them to output tokens."],
  ]) {
    if (group === "tokens" ? !key.endsWith("_tokens") : key.endsWith("_tokens")) continue;
    const stat = values[key] || {};
    const measured = Number.isFinite(stat.count) && stat.count > 0;
    const row = node("tr"), heading = node("th"); heading.scope = "row";
    heading.append(helpHeading(label, help)); row.append(heading);
    row.append(node("td", "", measured && Number.isFinite(stat.mean_milli) ? format(stat.mean_milli / 1000) : "not recorded"), node("td", "", measured && Number.isFinite(stat.min) && Number.isFinite(stat.max) ? format(stat.min) + "–" + format(stat.max) : "not recorded"), node("td", "", measured && Number.isFinite(stat.p95) ? format(stat.p95) : "not recorded"), node("td", "", Number.isFinite(stat.count) ? stat.count.toLocaleString() : "not recorded"));
    body.append(row);
  }
  table.append(body); wrapper.append(table);
  return wrapper;
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

function inlineReply(text) {
  const fragment = document.createDocumentFragment();
  for (const part of text.split(/(`[^`\n]+`|\*\*[^*\n]+\*\*)/)) {
    fragment.append(part.startsWith("`") && part.endsWith("`") ? node("code", "", part.slice(1, -1))
      : part.startsWith("**") && part.endsWith("**") ? node("strong", "", part.slice(2, -2)) : document.createTextNode(part));
  }
  return fragment;
}

// Text, emphasis and tables only. Model output never becomes executable HTML.
function replyBody(text) {
  const body = node("div", "reply-body");
  const blocks = text.split(/(```[\s\S]*?(?:```|$))/).flatMap(block => block.startsWith("```") ? [block] : block.split(/\n\s*\n/)).filter(block => block.trim());
  const long = text.length > 1500 && blocks.length > 3;
  const rest = node("details", "reply-rest");
  rest.append(node("summary", "", "rest of reply + saved references"));
  blocks.forEach((block, index) => {
    const lines = block.trim().split("\n");
    let part;
    if (block.startsWith("```")) {
      part = node("details", "reply-code");
      part.append(node("summary", "", "Code + commands"), node("pre", "", block.replace(/^```[^\n]*\n?/, "").replace(/```\s*$/, "")));
    } else if (lines.length > 2 && /^\|?\s*:?-{3,}/.test(lines[1]) && lines[0].includes("|")) {
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
    } else if (lines.every(line => /^\s*[-*] /.test(line))) {
      part = node("ul");
      lines.forEach(line => { const item = node("li"); item.append(inlineReply(line.replace(/^\s*[-*] /, ""))); part.append(item); });
    } else { part = node("p"); part.append(inlineReply(block)); }
    (long && index >= 3 ? rest : body).append(part);
  });
  if (long) body.append(rest);
  return body;
}

function latestReply() {
  const target = el("activity");
  const latest = Array.from(target.querySelectorAll("article.result")).at(-1) || target.lastElementChild;
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
  chart.append(node("small", "chart-basis", Number.isInteger(total) ? "Of " + total.toLocaleString() + " labeled exchanges" : "Sample size not recorded"));
  const entries = Object.entries(values || {}).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  if (!entries.length) {
    chart.append(node("span", "", "no labels recorded"));
    return chart;
  }
  const more = node("details", "chart-more");
  more.dataset.chart = label;
  more.append(node("summary", "", "Show " + Math.max(0, entries.length - 5) + " more"));
  for (const [index, [name, count]] of entries.entries()) {
    const row = node("span", "bar" + (name === "unknown" ? " unknown" : ""));
    const caption = node("small", "", plainLabel(name));
    const known = Number.isFinite(count) && count >= 0;
    caption.append(node("i", "", known ? count.toLocaleString() : "not recorded"));
    row.append(caption);
    if (!known || !Number.isFinite(total) || total <= 0) {
      (index < 5 ? chart : more).append(row);
      continue;
    }
    const meter = node("meter");
    meter.min = 0;
    meter.max = Math.max(1, number(total));
    meter.value = number(count);
    meter.textContent = number(count).toLocaleString() + " of " + number(total).toLocaleString();
    meter.setAttribute("aria-label", plainLabel(name) + ": " + meter.textContent);
    row.append(meter);
    (index < 5 ? chart : more).append(row);
  }
  if (entries.length > 5) chart.append(more);
  return chart;
}

let progressKey, selectedCheckpoint, savedProgress = {}, runningSummaryThreshold = null;
function renderSummaryMilestone() {
  let running = false;
  for (const tick of el("ticks").children) {
    const active = !tick.dataset.checkpoint && Number(tick.dataset.threshold) === runningSummaryThreshold;
    running ||= active;
    tick.querySelector("small").textContent = active ? "generating summary" : tick.dataset.caption;
    const label = active ? "The summary job is running for this milestone. The displayed traffic count may be older." : tick.dataset.label;
    tick.title = label;
    tick.dataset.help = label;
    tick.setAttribute("aria-label", label);
  }
  if (el("target").dataset.caption !== undefined) el("target").textContent = running
    ? "generating summary at " + runningSummaryThreshold.toLocaleString() : el("target").dataset.caption;
}
function selectCheckpoint(uuid, open = true) {
  const cards = Array.from(el("milestones").querySelectorAll(".checkpoint"));
  const selected = cards.find(card => card.dataset.uuid === uuid) || cards[0];
  if (!selected) return;
  selectedCheckpoint = selected.dataset.uuid;
  el("checkpoint-select").value = selectedCheckpoint;
  cards.forEach(card => { card.hidden = card !== selected; });
  if (open) selected.open = true;
  const index = cards.indexOf(selected);
  const checkpoint = savedProgress.checkpoints.find(value => value.uuid === selectedCheckpoint);
  const total = checkpoint.capture_count, classified = checkpoint.semantic?.classified;
  el("summary-count").textContent = Number.isInteger(total) ? total.toLocaleString() : "not recorded";
  el("labeled-count").textContent = Number.isInteger(classified) ? classified.toLocaleString() : "not recorded";
  el("summary-basis").textContent = index === 0 ? "latest saved summary" : "earlier saved summary";
  el("sample-basis").textContent = Number.isInteger(total) ? "out of " + total.toLocaleString() + " summarized exchanges" : "sample size not recorded";
  el("checkpoint-position").textContent = index === 0 ? "Latest summary selected. New summaries appear here automatically." : "Earlier summary selected. Saved traffic and the next milestone remain current.";
  document.querySelectorAll(".tick").forEach(tick => tick.classList.toggle("selected", tick.dataset.checkpoint === selectedCheckpoint));
}
function renderProgress(progress = {}) {
  const key = JSON.stringify(progress);
  if (key === progressKey) return;
  progressKey = key;
  const counted = Number.isInteger(progress.capture_count);
  const count = number(progress.capture_count);
  const processed = number(progress.processed_count);
  const points = progress.thresholds || [];
  const checkpoints = [...new Map((progress.checkpoints || []).map(item => [item.uuid, item])).values()].sort((a, b) => number(b.capture_count) - number(a.capture_count));
  const followLatest = !selectedCheckpoint || selectedCheckpoint === savedProgress.checkpoints?.[0]?.uuid;
  savedProgress = { ...progress, checkpoints };
  const displayed = new Set(Array.from(el("milestones").querySelectorAll(".checkpoint"), value => value.dataset.uuid));
  const detailKey = value => value.dataset.detail || (value.dataset.chart ? value.closest(".checkpoint").dataset.uuid + ":" + value.dataset.chart : value.dataset.uuid);
  const opened = new Set(Array.from(el("milestones").querySelectorAll("details[open]"), detailKey));
  el("volume").textContent = counted ? count.toLocaleString() : "not counted";
  el("pending-count").textContent = counted && Number.isInteger(progress.processed_count) ? processed > count ? "The latest summary is newer than this traffic count. Refresh to recount saved exchanges." : "Latest summary covers " + processed.toLocaleString() + " of " + count.toLocaleString() + " saved exchanges · " + (count - processed).toLocaleString() + " not yet summarized" : "Latest summary coverage not recorded.";
  el("collection-meter").replaceChildren(countBar(progress.processed_count, progress.capture_count, "saved exchanges summarized"));
  el("volume").title = "Each saved request and response is one exchange. An agent trajectory can contain many exchanges; these are not independent training examples.";
  el("target").textContent = !points.length ? "none configured" : !counted ? "count traffic to refresh" : progress.next_threshold
    ? (count >= progress.next_threshold ? "next summary due" : (progress.next_threshold - count).toLocaleString() + " more to reach " + progress.next_threshold.toLocaleString())
    : "all configured milestones reached";
  el("target").dataset.caption = el("target").textContent;
  el("count-checked").textContent = progress.counted_at
    ? "Last counted " + new Date(progress.counted_at).toLocaleString()
    : counted ? "Saved count; select ‘refresh counts’ to count again." : "No traffic count available yet.";
  const ticks = el("ticks");
  ticks.replaceChildren();
  for (const point of points) {
    const checkpoint = checkpoints.findLast(value => number(value.capture_count) >= point);
    const due = !checkpoint && counted && count >= point;
    const tick = node("button", "tick" + (checkpoint ? " done" : due ? " due" : ""));
    tick.type = "button";
    tick.dataset.threshold = point;
    if (checkpoint) tick.dataset.checkpoint = checkpoint.uuid;
    const remaining = Math.max(0, point - count);
    tick.title = checkpoint
      ? "A saved summary covers this milestone and includes " + checkpoint.capture_count.toLocaleString() + " exchanges."
      : !counted ? "Count traffic to check this threshold."
      : count >= point
        ? "Threshold reached; its summary has not been saved. This does not mean a job is running."
        : remaining.toLocaleString() + " exchanges until this summary threshold.";
    tick.setAttribute("aria-label", tick.title);
    tick.dataset.label = tick.title;
    const meter = node("span", "milestone-meter"), fill = node("i");
    fill.style.width = counted ? Math.max(0, Math.min(100, count / point * 100)) + "%" : "0%";
    meter.append(fill);
    tick.append(node("b", "", point.toLocaleString()), meter, node("small", "", checkpoint ? "summary saved ↗" : !counted ? "not counted" : due ? "reached · summary due" : remaining.toLocaleString() + " until summary"));
    tick.dataset.caption = tick.querySelector("small").textContent;
    tick.addEventListener("click", () => {
      el("summaries").open = true;
      const card = Array.from(el("milestones").querySelectorAll(".checkpoint")).find(item => checkpoint && item.dataset.uuid === checkpoint.uuid);
      if (card) selectCheckpoint(card.dataset.uuid);
      else el("copy-state").textContent = tick.title || tick.dataset.help;
      (card || el("summaries")).scrollIntoView({block: "center"});
    });
    ticks.append(tick);
  }
  renderSummaryMilestone();
  el("milestones").replaceChildren();
  const picker = el("checkpoint-select");
  picker.replaceChildren();
  picker.disabled = !checkpoints.length;
  for (const [index, checkpoint] of checkpoints.entries()) {
    const point = number(checkpoint.capture_count);
    const card = node("details", "checkpoint reached");
    card.dataset.threshold = point;
      card.dataset.uuid = checkpoint.uuid;
      card.open = opened.has(checkpoint.uuid) || (!displayed.has(checkpoint.uuid) && index === 0);
      const disclosure = node("summary", "checkpoint-head");
      disclosure.title = "Read the summary of these saved request and response pairs.";
      const capturedThrough = checkpoint.created_at ? new Date(checkpoint.created_at).toLocaleString() : "date not recorded";
      disclosure.append(document.createTextNode(point.toLocaleString() + " exchanges in this summary"), node("small", "", "Latest included exchange · " + capturedThrough));
      const option = node("option", "", (index === 0 ? "Latest · " : "") + point.toLocaleString() + " exchanges · through " + capturedThrough);
      option.value = checkpoint.uuid;
      picker.append(option);
      const quality = checkpoint.quality || {};
      const counters = checkpoint.counters || {};
      const traffic = checkpoint.traffic || {};
      const semantic = checkpoint.semantic || {};
      const values = checkpoint.series || {};
      const body = node("div", "summary-body sample-charts");
      body.append(
        distributionChart("Topics", semantic.domain, semantic.classified, "What the sampled requests were about. These are model-assigned labels, not all saved traffic."),
        distributionChart("Tasks", semantic.operation, semantic.classified, "What the model was asked to do in the same sample."),
        distributionChart("Estimated outcomes", semantic.outcome, semantic.classified, "A model's estimate, not a check of task success. Unknown means the saved exchange did not show enough evidence.")
      );
      const section = (label, name, contents) => {
        const detail = node("details", "summary-delivery");
        detail.dataset.detail = checkpoint.uuid + ":" + name;
        detail.open = opened.has(detail.dataset.detail);
        detail.append(node("summary", "", label), contents);
        return detail;
      };
      const sample = node("div", "summary-body");
      sample.append(
        distributionChart("Skills needed", semantic.capability, semantic.classified, "One exchange can need several skills, so these counts can add up to more than the sample size."),
        summaryRow("Suggested answer checks", counts(semantic.oracle), "Suggested ways to grade these tasks, not checks that have already run."),
        distributionChart("Tone", semantic.sentiment, semantic.classified, "Model-assigned sentiment in the same labeled sample, not a customer satisfaction score."),
        summaryRow("Languages", counts(semantic.language), "Languages detected in the classified sample."),
        summaryRow("Related requests", [["source_groups", "source groups"], ["trajectory_groups", "tagged task"], ["untagged_request_groups", "untagged requests"]].map(([key, label]) => (Number.isInteger(counters[key]) ? counters[key].toLocaleString() : "unknown") + " " + label).join(" · "), "Exchanges from one tagged task stay together. Untagged requests are grouped by matching request content. Correlated exchanges and these groups are not proof of independent tasks."),
        summaryRow("Left unlabeled", Number.isInteger(semantic.abstained) ? semantic.abstained.toLocaleString() : "not recorded", "Sampled exchanges the model declined to classify. Exchanges outside the sample are not included in this count.")
      );
      const measurements = node("div", "summary-body");
      measurements.append(
        summaryRow("Readable records", qualityCount(counters.parsed, counters.captures, quality.parse_bps), "Saved exchanges whose request and response could be parsed."),
        summaryRow("Successful HTTP responses", qualityCount(counters.successful, counters.captures, quality.success_bps), "A successful HTTP response does not prove the answer was correct. Model-estimated task outcomes are shown separately."),
        summaryRow("Repeated content", qualityCount(counters.duplicates, counters.captures, quality.duplicate_bps), "Exchanges with duplicated request and response content."),
        summaryRow("Models requested", counts(traffic.model), "Model names requested by captured applications."),
        summaryRow("API used", counts(traffic.endpoint), "Responses and Chat Completions requests in this summary."),
        summaryRow("Route used", counts(traffic.route_target), "Requests served by the original model or an approved replacement."),
        summaryRow("Streaming", counts(traffic.streaming), "True means the response arrived in chunks; false means it arrived as one response."),
        summaryRow("Structured output", counts(traffic.structured_output), "Whether requests asked for a specific output format."),
        summaryRow("Reasoning setting", counts(traffic.reasoning_effort), "The requested reasoning effort, where present."),
        summaryRow("Chat messages per exchange", counters.captures > 0 && traffic.endpoint?.responses === counters.captures ? "Not used by Responses" : seriesCount(values.message_count), "Counts the Chat Completions messages array only. Responses input items are counted separately. Zero here does not mean the exchange had no conversation history."),
        summaryRow("Responses input items per exchange", seriesCount(values.input_item_count), "Items in a Responses request. This may include messages, tool calls and tool results. It is not a count of independent conversations."),
        summaryRow("Tool definitions per exchange", seriesCount(values.tool_definitions), "Tools offered to the model, not tools it actually called."),
        summaryRow("Tool calls per exchange", seriesCount(values.tool_calls), "Recorded tool-call count. A call does not prove the tool ran successfully or the task finished.")
      );
      const identity = node("div", "row");
      identity.append(helpHeading("Saved summary ID", "Copies the full ID used to find this summary in storage."), copyButton(short(checkpoint.uuid), checkpoint.uuid, "summary ID"));
      measurements.append(identity);
      const sampleSize = semantic.classified;
      const lead = node("p", "sample-note", Number.isInteger(sampleSize) ? sampleSize > 0 ? "A model labeled " + sampleSize.toLocaleString() + " of these " + point.toLocaleString() + " exchanges. The charts describe that sample, not all saved traffic." : "Traffic counts only. No topic or task labels were saved in this summary." : "The labeled sample size was not recorded. Do not treat these labels as a summary of all traffic.");
      card.append(disclosure, node("h3", "", "What the sample tells us"), lead);
      if (Number.isInteger(semantic.classified)) card.append(countBar(semantic.classified, checkpoint.capture_count, "exchanges labeled in this summary"));
      if (number(semantic.classified)) card.append(body);
      const allStats = node("div", "row");
      allStats.append(node("p", "", "Available summary fields returned to this dashboard. Percentiles (p50, p95, p99) are histogram upper bounds and can exceed the observed maximum. Divide mean_milli by 1,000 for the average. tps_milli is the end-to-end output rate × 1,000, not decode speed."), recordFields(checkpoint));
      card.append(section("Skills, tone and related requests", "sample", sample), section("How long did replies take?", "timing", responseStats(values, "timing")), section("How many tokens were used?", "tokens", responseStats(values, "tokens")), section("Which requests were counted?", "delivery", measurements), section("Available summary fields + references", "all", allStats));
      el("milestones").append(card);
  }
  el("milestones").querySelectorAll("details[data-chart]").forEach(detail => { detail.open = opened.has(detailKey(detail)); });
  if (!checkpoints.length) {
    el("summary-count").textContent = Number.isInteger(progress.processed_count) ? processed.toLocaleString() : "not counted";
    el("labeled-count").textContent = "not recorded";
    el("summary-basis").textContent = "no saved summary to open";
    el("sample-basis").textContent = "no saved labels to read";
    picker.append(node("option", "", "No summaries yet"));
    el("checkpoint-position").textContent = "";
    el("milestones").append(node("p", "empty", "No summary saved yet. The next milestone is shown above."));
  } else selectCheckpoint(followLatest ? checkpoints[0].uuid : selectedCheckpoint, false);
  el("read-selected").disabled = !checkpoints.length;
  el("read-selected").onclick = () => {
    const card = Array.from(el("milestones").querySelectorAll(".checkpoint")).find(value => value.dataset.uuid === selectedCheckpoint);
    if (card) { el("summaries").open = true; selectCheckpoint(card.dataset.uuid); el("summaries").scrollIntoView({block: "start", behavior: "instant"}); }
  };
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
    const commands = node("div", "job-commands");
    for (const name of ["run", "status", "stop"]) {
      const command = job.commands?.[name];
      if (typeof command !== "string" || !command.trim()) continue;
      const button = copyButton("copy " + name, command, name + " command");
      button.className = "command-copy";
      button.setAttribute("aria-label", "Copy " + name + " command: " + command);
      button.replaceChildren(node("b", "", "copy " + name), node("code", "", command));
      commands.append(button);
    }
    if (commands.children.length) body.append(node("p", "command-note", "Copy a command, then run it in Bash with your job settings. These buttons only copy."), commands);
    const facts = node("div", "facts");
    facts.append(
      summaryRow("needed before running", triggerCopy[job.trigger] || String(job.trigger || "manual").replaceAll("_", " "), "A prerequisite, not proof that this action is running or scheduled."),
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
  const labels = {
    working: man.connection === "discovered" ? "working in another window" : "working" + (man.queued ? " · follow-up queued" : ""),
    queued: "instruction queued",
    failed: "last turn failed",
    waiting: "waiting for a change",
    paused: "paused",
    stopped: "stopped",
    idle: "ready for a task" + (jobs ? " · jobs active" : ""),
    setup: "session setup needed",
  };
  light("man", state === "failed" ? "degraded" : man.online ? "up" : "down", man.online ? labels[state] || labels.setup : man.trajectory_id ? "offline · session saved" : "no session yet");
  const driverSource = driver.source === "heartbeat" ? "Running agent" : "Dashboard setting";
  el("driver-detail").textContent = driverSource + ": " + (driverStatus || "not configured") + ". Session: " + (man.trajectory_id || "not started") + ".";
  el("active-model").textContent = driverSource + " · " + (driver.model || "not configured") + (driver.reasoning_effort ? " · " + driver.reasoning_effort + " reasoning" : "");
  const pulse = man.heartbeat || {};
  const heartbeatOnline = pulse.online === true;
  const heartbeatStarting = !heartbeatOnline && man.connection === "attached" && man.active;
  const heartbeatRetained = !heartbeatOnline && Boolean(pulse.state || pulse.checked_at || pulse.next_wake);
  const heartbeatState = heartbeatOnline ? (pulse.state || "idle") : heartbeatStarting ? "starting" : heartbeatRetained ? "stopped" : "not started";
  light("heartbeat", heartbeatOnline ? (pulse.state === "failed" ? "degraded" : "up") : heartbeatStarting ? "ready" : "down", "heartbeat · " + heartbeatState);
  const workActive = heartbeatOnline && (pulse.state === "running" || man.active);
  const summaryJob = pulse.summary || {};
  const summaryState = summaryJob.state;
  runningSummaryThreshold = heartbeatOnline && summaryJob.enabled === true && summaryState === "running" && Number.isInteger(summaryJob.threshold) ? summaryJob.threshold : null;
  renderSummaryMilestone();
  const summaryThreshold = Number.isInteger(summaryJob.threshold) ? summaryJob.threshold.toLocaleString() : "the next milestone";
  const summaryLabel = !heartbeatOnline ? "Summary checker disconnected"
    : summaryJob.enabled !== true ? "Automatic summaries off · set MILK_AUTO_SUMMARY=1"
    : summaryState === "running" ? "Generating summary · " + summaryThreshold
    : summaryState === "failed" ? "Summary failed · previous saved version kept"
    : summaryState === "complete" ? "Summary saved · checking for the next milestone"
    : pulse.state === "paused" ? "Summary checks paused"
    : "Counting saved objects · next summary at " + summaryThreshold;
  light("summary-job", !heartbeatOnline ? "down" : summaryJob.enabled !== true ? "ready" : summaryState === "failed" ? "degraded" : "up", summaryLabel);
  el("summary-job-checked").textContent = summaryJob.checked_at
    ? "Last check " + new Date(summaryJob.checked_at * 1000).toLocaleTimeString() + (summaryJob.error ? " · " + summaryJob.error : "") : "";
  document.body.dataset.agentState = workActive ? "working" : heartbeatOnline ? heartbeatState : "disconnected";
  const task = (pulse.task || "No task saved yet.").replace(/^Continue the saved task:\s*/, "");
  el("task-label").textContent = workActive || (heartbeatOnline && pulse.state === "waiting") ? "current task" : "last saved instruction";
  const taskPreview = task.split(/\n|(?<=[.!?])\s/)[0];
  el("current-work").textContent = taskPreview.length > 160 ? taskPreview.slice(0, 160) + "…" : taskPreview;
  el("current-instruction").hidden = !pulse.brief || pulse.brief === pulse.task;
  el("current-instruction").textContent = pulse.brief ? "Latest instruction: " + pulse.brief.split(/\n|(?<=[.!?])\s/)[0].slice(0, 220) : "";
  el("current-work-note").textContent = !heartbeatOnline ? "The task is saved, but no heartbeat owner is connected."
    : workActive ? (jobs ? "Running: " + jobNames + "." : "Working through the task. New replies appear below.")
    : pulse.state === "waiting" ? pulse.watch_state === "unknown"
      ? "The task is waiting, but its job status is unknown. This does not confirm a worker is running."
      : "Watching " + (pulse.watch_label || "saved work") + (pulse.watch_state ? " · " + pulse.watch_state : "") + ". No model call while unchanged."
    : pulse.state === "failed" ? "The last turn failed. Open its result below before continuing."
    : pulse.state === "paused" ? "Paused. Send an instruction to continue."
    : "Ready for your next instruction. Idle checks use no model calls.";
  const resource = pulse.watch_resource || {};
  const resourceRow = el("heartbeat-resource");
  resourceRow.replaceChildren();
  resourceRow.hidden = !resource.provider_status;
  if (resource.provider_status) {
    el("current-work-note").textContent = "Last server report: " + resource.provider_status.toLowerCase().replaceAll("_", " ")
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
  el("conversation-state").textContent = (man.online ? labels[state] || state : "agent offline") + (state === "failed" && Number.isInteger(man.last_exit_code) ? " · exit " + man.last_exit_code : "");
  el("conversation-state").title = pulse.checked_at ? "Heartbeat last checked " + new Date(pulse.checked_at * 1000).toLocaleString() + ". Unchanged idle checks use no model tokens." : "Heartbeat starts with your next task. Closing this page does not stop it.";
  if (!runLoading) {
    runState(el("prompt-text").value.trim() ? "Unsent message · review it, then send to Milk Man."
      : man.queued ? "Your next instruction is queued. Milk Man is finishing the current work."
      : man.active ? "Milk Man is working. A follow-up will wait its turn."
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
    if (event.type === "prompt" && event.content.startsWith("Continue the saved task:")) {
      const resumed = node("details", "resume-note");
      resumed.dataset.key = "resume:" + index + ":" + event.ts;
      resumed.open = opened.has(resumed.dataset.key);
      const title = node("summary", "", "Task resumed");
      if (event.ts) title.append(node("time", "", event.ts + " UTC"));
      resumed.append(title, node("pre", "", event.content));
      target.append(resumed);
      index++;
      continue;
    }
    if (!["prompt", "final"].includes(event.type)) {
      const group = [event];
      while (man.activity[index + group.length] && !["prompt", "final"].includes(man.activity[index + group.length].type)) group.push(man.activity[index + group.length]);
      const message = node("details", "work-log");
      message.dataset.key = "work:" + index + ":" + (event.ts || event.type);
      message.open = opened.has(message.dataset.key);
      const commands = group.filter(value => value.type === "shell-output").length;
      const updates = group.length - commands;
      const failures = group.filter(value => value.type === "shell-output" && /\nexit (?!0\s*$)\S+\s*$/.test(value.content)).length;
      const update = group.filter(value => !["shell-output", "process-output"].includes(value.type)).map(value => value.content.split("```")[0].trim().split(/\n\s*\n/)[0]).filter(Boolean).at(-1);
      if (update) {
        const preview = node("article", "message work-update");
        preview.append(node("b", "", "Milk Man · update"), node("p", "", update.length > 240 ? update.slice(0, 240) + "…" : update));
        target.append(preview);
      }
      const heading = node("summary", "", "Work details");
      heading.append(node("small", "", [commands ? commands + " command" + (commands === 1 ? "" : "s") : "", updates ? updates + " update" + (updates === 1 ? "" : "s") : "", failures ? failures + " nonzero exit" + (failures === 1 ? "" : "s") : ""].filter(Boolean).join(" · ")));
      message.append(heading);
      group.forEach((entry, part) => {
        const detail = node("details", "work-entry");
        detail.dataset.key = message.dataset.key + ":" + part;
        detail.open = opened.has(detail.dataset.key);
        const exit = entry.type === "shell-output" ? entry.content.match(/\nexit (\S+)\s*$/)?.[1] : null;
        const label = entry.type === "shell-output" ? "Command output" : entry.type === "process-output" ? "Process log" : "Model step";
        const title = node("summary", "", label + (exit != null ? " · exit " + exit : ""));
        if (entry.ts) title.append(node("time", "", entry.ts + " UTC"));
        detail.append(title, node("pre", "", entry.content));
        message.append(detail);
      });
      target.append(message);
      index += group.length;
      continue;
    }
    const role = event.type === "prompt" ? "you" : "milk-man";
    const message = node("article", "message " + role + (event.type === "final" ? " result" : ""));
    const heading = node("div", "message-heading");
    heading.append(node("b", "", role === "you" ? "You" : "Milk Man"));
    if (event.ts) heading.append(node("time", "", event.ts + " UTC"));
    message.append(heading);
    if (role === "you" && event.content.length > 500) {
      const full = node("details", "reply-code");
      full.append(node("summary", "", "Full instruction"), node("pre", "", event.content));
      message.append(node("p", "", event.content.slice(0, 300) + "…"), full);
    } else message.append(event.type === "final" ? replyBody(event.content) : node("p", "", event.content));
    message.querySelectorAll("details").forEach((detail, part) => {
      detail.dataset.key = index + ":" + event.ts + ":reply:" + part;
      detail.open = opened.has(detail.dataset.key);
    });
    target.append(message);
    index++;
  }
  const latest = Array.from(target.querySelectorAll("article.result")).at(-1);
  if (latest) latest.classList.add("latest-reply");
  const unread = !follow && (newFinal || el("latest-message").classList.contains("unread"));
  el("message-position").textContent = unread ? "New reply · your reading position was kept" : "Instructions + replies · work details folded";
  el("latest-message").classList.toggle("unread", unread);
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
    if (el("prompt-text").value.trim() === prompt) el("prompt-text").value = "";
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
    light("gateway", "degraded", "status unknown");
    light("store", "degraded", "status unknown");
  } else {
    light("gateway", gateway.state || "detached", gateway.state === "up" ? "reachable · saving traffic" : gateway.state === "degraded" ? "reachable · capture impaired" : gateway.state === "down" ? "unavailable" : "not configured");
    light("store", milk.error ? "down" : milk.missing && milk.missing.length ? "detached" : "up", milk.error ? "unavailable" : milk.missing && milk.missing.length ? "not configured" : "readable");
  }
  el("checked").textContent = (monitor.error ? "status watcher failed " : "status updated ") + new Date(data.now).toLocaleString();
  const jobs = data.contract?.jobs || [];
  const readyJobs = jobs.filter(job => !(job.required || []).some(value => !value.set)).length;
  const jobStatus = data.contract?.error ? "job configuration unavailable" : readyJobs + " / " + jobs.length + " have required settings here";
  el("job-count").textContent = jobStatus;
  el("watch-state").textContent = "Follow-ups wait their turn";
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
    { title: "capture writer", detail: !["up", "degraded"].includes(gateway.state) ? "unavailable · last totals unknown" : [["observed", "received"], ["persisted", "stored"], ["dropped", "dropped"]].map(([key, label]) => (Number.isInteger(gateway[key]) ? gateway[key].toLocaleString() : "unknown") + " " + label).join(" · "), help: "Milk Parlor totals since its current process started, across its configured scopes. Not this scope's stored traffic count." },
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

function experimentLabel(value, index) {
  if (value.kind === "tiny_sequential_serving_setting_comparison") return "Compare model-server settings";
  const names = {"native-assistant-example-extraction": "Extract one saved assistant exchange", "owned-120b-checkpoint-job": "Read a summary using the hosted 120B model"};
  const name = value.name;
  return typeof name === "string" && name.length <= 90 && !/[\n\\]|^(?:\/|file:)|[a-f\d]{32}/i.test(name)
    ? names[name] || name.replaceAll("_", " ").replaceAll("-", " ") : "Experiment " + (index + 1);
}

function experimentChange(value) {
  const baseline = value.configurations?.baseline?.mean_e2e_ms;
  const candidate = value.configurations?.candidate?.mean_e2e_ms;
  if (!Number.isFinite(baseline) || baseline <= 0 || !Number.isFinite(candidate) || candidate < 0) return "";
  const change = 100 * (candidate / baseline - 1);
  return change === 0 ? "Same average reply time" : Math.abs(change).toFixed(1) + "% " + (change > 0 ? "slower" : "faster") + " full reply";
}

function experimentDate(value) {
  const stamp = value.finished_at || value.created_at;
  const date = typeof stamp === "string" && /^\d{4}-\d{2}-\d{2}T/.test(stamp) ? new Date(stamp) : null;
  return date && Number.isFinite(date.getTime()) ? date.toLocaleDateString() : "";
}

function experimentCard(value, index, heading = true) {
  const card = node("article", "experiment");
  if (heading) card.append(node("h3", "", experimentLabel(value, index)));
  const change = experimentChange(value);
  if (change) card.append(node("p", "comparison-change", change + " with the trial setting"));
  else card.append(node("p", "experiment-status", value.state === "failed" ? "Failed attempt · see the saved result below" : "Saved result · open the details for its recorded outcome"));
  const workload = value.workload || {};
  const measured = workload.measured_requests_per_configuration;
  const warmup = workload.warmup_requests_per_configuration;
  if (Number.isInteger(measured) && measured > 0) {
    card.append(node("p", "experiment-sample", measured + " timed replies per setting" + (Number.isInteger(warmup) && warmup >= 0 ? " + " + warmup + " warm-up" : "") + ". This small run does not establish overall answer quality."));
  }
  if (heading && experimentDate(value)) card.append(node("small", "", "Recorded " + experimentDate(value)));
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
    if (Number.isInteger(measured) && measured > 0 && [baseline, candidate].every(item => Number.isInteger(item.measured_correct) && item.measured_correct >= 0 && item.measured_correct <= measured)) {
      const row = node("tr");
      const label = node("th", "", "passed the answer check"); label.scope = "row";
      row.append(label, node("td", "", baseline.measured_correct + " / " + measured), node("td", "", candidate.measured_correct + " / " + measured));
      body.append(row);
    }
    const header = node("thead"); header.append(head); table.append(header, body);
    if (body.children.length) { const scroll = node("div", "table-scroll"); scroll.append(table); card.append(scroll); }
  }
  const detail = node("details");
  detail.dataset.field = "experiment-" + index + "-notes";
  detail.append(node("summary", "", "What changed + full saved result"), recordFields(value));
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
  target.replaceChildren();
  const experiments = record.experiments || [];
  if (experiments.length) {
    const latest = node("div", "row latest-result");
    latest.append(helpHeading("Latest saved result", "The newest saved entry, not live provider status. Its measurements and notes are recorded results, not an independent verification."), experimentCard(experiments.at(-1), experiments.length - 1));
    target.append(latest);
  } else target.append(node("p", "empty", "No experiment results saved yet. The research setup is below."));
  for (let index = experiments.length - 2; index >= 0; index--) {
    const experiment = experiments[index];
    const detail = node("details");
    detail.dataset.field = "experiment-" + index;
    const state = experimentChange(experiment) || (experiment.state === "failed" ? "failure recorded" : "saved notes");
    detail.append(node("summary", "", [experimentLabel(experiment, index), state, experimentDate(experiment)].filter(Boolean).join(" · ")));
    const body = node("div", "row");
    body.append(experimentCard(experiment, index, false));
    detail.append(body);
    target.append(detail);
  }
  const setup = node("details");
  setup.dataset.field = "setup";
  setup.append(node("summary", "", "research setup + saved plan"));
  for (const [field, label, help] of [
    ["objective", "Research goal"],
    ["next_action", "Last saved plan", "This note can lag behind the chat. It is not a running task or a schedule."],
    ["targets", "What counts as better", "Quality, speed, and cost targets for this collection."],
    ["baseline", "Reference model", "The model and settings used for the comparison."],
    ["evaluation", "Tasks kept out of training", "Use the same untouched tasks to compare answers fairly."],
    ["best", "Selected model", "A saved selection, not the chat model or a currently running GPU."],
    ["wake", "Proposed next check", "The heartbeat must register this watch before it can run."],
  ]) {
    const row = node("div", "row");
    row.append(helpHeading(label, help), recordFields(record[field]));
    setup.append(row);
  }
  const revision = node("div", "row");
  revision.append(node("small", "", "saved version"), copyButton(short(value.revision), value.revision, "research revision"));
  setup.append(revision);
  target.append(setup);
  target.querySelectorAll("details[data-field]").forEach(detail => { detail.open = opened.has(detail.dataset.field); });
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
    el("refresh").textContent = "refresh counts";
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
    light("summary-job", "down", "Summary status unknown · connection lost");
    el("summary-job-checked").textContent = "Reconnect to check whether the summary is still running.";
    runningSummaryThreshold = null;
    renderSummaryMilestone();
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
el("latest-message").addEventListener("click", () => { latestReply(); el("latest-message").classList.remove("unread"); el("message-position").textContent = "Latest reply"; });
el("checkpoint-select").addEventListener("change", event => selectCheckpoint(event.target.value));
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
