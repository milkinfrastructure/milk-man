const el = id => document.getElementById(id);
const short = value => typeof value === "string" ? value.slice(0, 8) : "waiting";
const number = value => Number.isFinite(Number(value)) ? Number(value) : 0;
const stages = [
  ["traffic", "traffic", "Parlor stores completed request and response pairs."],
  ["summary", "summary", "Milk Man measures traffic and classifies a bounded sample at each configured count."],
  ["readiness", "ready", "Fixed checks decide whether the data can generate evaluations."],
  ["eval", "evals", "The teacher creates the configured number of cases per source conversation."],
  ["dataset", "dataset", "Cases are separated into train, development, calibration, and sealed sets."],
  ["training", "student", "Qwen3.5-0.8B is trained from the prepared dataset."],
  ["evaluation", "winner", "Comparable model versions are scored and the winner is checked on sealed data."],
  ["candidate", "candidate", "One provider serves the selected artifact."],
  ["proposal", "route", "An unsigned proposal waits for an operator signature."],
];

function node(tag, className, text) {
  const value = document.createElement(tag);
  if (className) value.className = className;
  if (text !== undefined) value.textContent = text;
  return value;
}

function rows(target, values, empty) {
  target.replaceChildren();
  if (!values.length) return target.append(node("p", "empty", empty));
  for (const value of values) {
    const row = node("div", "row");
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

function summaryRow(label, value, help) {
  const row = node("div", "summary-row");
  const heading = node("b", help ? "has-help" : "", label);
  if (help) heading.title = help;
  row.append(heading, node("span", "", value));
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
      disclosure.append(node("i", "pin"), document.createTextNode(point.toLocaleString()), node("small", "", "complete · " + short(checkpoint.uuid)));
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
        summaryRow("models", counts(traffic.model)),
        summaryRow("endpoints", counts(traffic.endpoint)),
        summaryRow("routes", counts(traffic.route_target)),
        summaryRow("response", counts(traffic.status_class) + " · streaming " + counts(traffic.streaming) + " · structured " + counts(traffic.structured_output)),
        summaryRow("traffic", counts(traffic.modalities) + " · outcome " + counts(traffic.outcome) + " · fallback " + counts(traffic.fallback_reason)),
        summaryRow("reasoning", counts(traffic.reasoning_effort)),
        distributionChart("topics", semantic.domain, semantic.classified, "What the sampled conversations are about."),
        summaryRow("tasks", counts(semantic.operation), "What users are asking the model to do."),
        distributionChart("capabilities", semantic.capability, semantic.classified, "Capabilities needed to answer the sampled conversations. One conversation may need several."),
        summaryRow("grading", counts(semantic.oracle), "How an answer could be checked."),
        summaryRow("sentiment", counts(semantic.sentiment)),
        distributionChart("outcomes", semantic.outcome, semantic.classified, "How the classifier judged the captured responses."),
        summaryRow("languages", counts(semantic.language)),
        summaryRow("total time", series(values.total_ms, duration, true)),
        summaryRow("first token", series(values.ttft_ms, duration, true)),
        summaryRow("generation", series(values.tps_milli, item => (number(item) / 1000).toFixed(1) + " tok/s")),
        summaryRow("input tokens", series(values.input_tokens)),
        summaryRow("output tokens", series(values.output_tokens))
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

function renderLoop(status) {
  const value = status || {};
  const done = {
    traffic: number(value.capture_count) > 0,
    summary: Boolean(value.summary),
    readiness: Boolean(value.readiness),
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
    candidate: value.candidate ? "artifact " + short(value.candidate.uuid) : "zero",
    proposal: value.proposal ? "ready for operator" : value.next_action || "waiting",
  };
  let marked = false;
  el("rail").replaceChildren();
  stages.forEach(([key, label, help], index) => {
    const card = node("div", "stage has-help");
    card.title = help;
    card.setAttribute("aria-label", label + ". " + help + " Current state: " + notes[key]);
    if (done[key]) card.classList.add("done");
    else if (!marked) { card.classList.add("next"); marked = true; }
    card.append(node("b", "", String(index + 1).padStart(2, "0")), node("h2", "", label), node("p", "", notes[key]));
    el("rail").append(card);
  });
}

let activityKey = "";
function renderMan(man) {
  const connection = man.connection || (man.active ? "discovered" : man.trajectory_id ? "detached" : "missing");
  const state = connection === "detached" ? "ready" : connection;
  const labels = { attached: "Milk Man working · output live", discovered: "Milk Man working outside this page", ready: "Milk Man ready · saved session", missing: "Milk Man needs setup" };
  light("man", state, (labels[state] || labels.missing) + (man.trajectory_id ? " · " + short(man.trajectory_id) : ""));
  rows(el("workspaces"), man.workspaces.map(workspace => ({ title: workspace.name + " · " + (workspace.head || "no git"), detail: workspace.changes.length ? workspace.changes.join("\n") : workspace.path, class: workspace.changes.length ? "changes" : "path" })), "no workspaces");
  rows(el("memory"), man.memory.map(memory => ({ title: memory.ts || "memory", detail: memory.content })), "no saved memory");

  const target = el("activity");
  const nextActivityKey = String(man.active) + JSON.stringify(man.activity);
  if (nextActivityKey === activityKey) return;
  activityKey = nextActivityKey;
  const follow = target.scrollHeight - target.scrollTop - target.clientHeight < 64;
  const scroll = target.scrollTop;
  const opened = new Set(Array.from(target.querySelectorAll("details.tool[open]"), value => value.dataset.key));
  target.replaceChildren();
  if (!man.activity.length) target.append(node("article", "message milk-man", "No conversation yet."));
  for (let index = 0; index < man.activity.length;) {
    const event = man.activity[index];
    if (["shell-output", "process-output"].includes(event.type)) {
      const group = [event];
      while (man.activity[index + group.length]?.type === event.type) group.push(man.activity[index + group.length]);
      const message = node("details", "message tool");
      message.dataset.key = index + ":" + (event.ts || event.type);
      message.open = opened.has(message.dataset.key) || (man.active && event.type === "process-output");
      const label = event.type === "process-output" ? "live output" : "tool output";
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
  const prompt = el("prompt").value.trim();
  if (!prompt) return runState("Enter a prompt first.", true);
  runLoading = true;
  runState("Starting Milk Man. Output will appear above.");
  try {
    const response = await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt }) });
    const result = await response.json();
    if (!response.ok) throw Error(result.error || "Unable to start Milk Man.");
    el("prompt").value = "";
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
  light("gateway", gateway.state || "detached", gateway.state === "up" ? "gateway active" : gateway.state === "degraded" ? "gateway degraded" : gateway.state === "down" ? "gateway unavailable" : "gateway not configured");
  const milk = data.milk || {};
  light("store", milk.error ? "down" : milk.missing && milk.missing.length ? "detached" : "up", milk.error ? "object store unavailable" : milk.missing && milk.missing.length ? "object store not configured" : "object store active");
  el("checked").textContent = "status updated " + new Date(data.now).toLocaleString();
  const status = milk.status || {};
  renderProgress(milk.progress);
  renderLoop(status);
  rows(el("object"), milk.error ? [{ title: "unavailable", detail: milk.error }] : milk.missing.length ? [{ title: "not configured", detail: milk.missing.join("\n") }] : [
    { title: status.next_action || "waiting", detail: number(milk.progress.capture_count) + " captured · " + number(milk.progress.processed_count) + " summarized" },
    { title: status.profile || "scope", detail: status.scope_id || "" },
    { title: "gateway since restart", detail: number(gateway.observed) + " observed · " + number(gateway.persisted) + " persisted · " + number(gateway.dropped) + " dropped" },
  ], "waiting for status");
  el("foot").textContent = "local only · remote status updated " + data.now;
}

let cloudLoading = false;
async function refreshCloud() {
  if (cloudLoading) return;
  cloudLoading = true;
  el("refresh").disabled = true;
  el("refresh").textContent = "refreshing";
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw Error("status " + response.status);
    const data = await response.json();
    renderMan(data.man);
    renderCloud(data);
  } catch {
    light("gateway", "down", "dashboard cannot reach gateway");
    light("store", "down", "dashboard cannot reach object store");
    el("checked").textContent = "status refresh failed " + new Date().toLocaleString();
  } finally {
    cloudLoading = false;
    el("refresh").disabled = false;
    el("refresh").textContent = "refresh gateway + object store";
  }
}

async function refreshLocal() {
  if (document.hidden) return;
  try {
    const response = await fetch("/api/local", { cache: "no-store" });
    if (!response.ok) throw Error();
    renderMan((await response.json()).man);
  } catch {
    light("man", "detached", "dashboard detached from Milk Man");
  }
}

el("refresh").addEventListener("click", refreshCloud);
el("run-form").addEventListener("submit", startRun);
el("prompt").addEventListener("keydown", event => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    el("run-form").requestSubmit();
  }
});
refreshCloud();
setInterval(refreshLocal, 1000);
setInterval(refreshCloud, 30000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshCloud(); });
