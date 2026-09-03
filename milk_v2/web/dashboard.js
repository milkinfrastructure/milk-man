const el = id => document.getElementById(id);
const short = value => typeof value === "string" ? value.slice(0, 8) : "waiting";
const number = value => Number.isFinite(Number(value)) ? Number(value) : 0;
const stages = [["traffic", "traffic"], ["summary", "summary"], ["readiness", "ready"], ["eval", "evals"], ["dataset", "dataset"], ["training", "student"], ["evaluation", "winner"], ["candidate", "candidate"], ["proposal", "route"]];

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

function topCounts(values) {
  return Object.entries(values || {}).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 3).map(value => value[0] + " " + value[1]).join(" · ") || "none";
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

function renderProgress(progress = {}) {
  const count = number(progress.capture_count);
  const processed = number(progress.processed_count);
  const points = progress.thresholds || [];
  const checkpoints = progress.checkpoints || [];
  el("volume").textContent = count.toLocaleString() + " conversations captured";
  el("target").textContent = progress.next_threshold
    ? processed.toLocaleString() + " summarized · " + (count >= progress.next_threshold ? "ready at " : (progress.next_threshold - count).toLocaleString() + " to ") + progress.next_threshold.toLocaleString()
    : processed.toLocaleString() + " summarized · checkpoints complete";
  const fill = Math.max(0, Math.min(100, fillPercent(count, points)));
  el("meter").value = fill;
  el("meter").textContent = Math.round(fill) + "%";
  el("milestones").replaceChildren();
  for (const point of points) {
    const checkpoint = checkpoints.find(value => number(value.capture_count) >= point);
    const card = node("div", "checkpoint" + (checkpoint ? " reached" : count >= point ? " crossed" : ""));
    const title = node("h3");
    title.append(node("i", "pin"), document.createTextNode(point.toLocaleString()));
    card.append(title);
    if (checkpoint) {
      card.append(
        node("small", "", short(checkpoint.uuid) + " · " + checkpoint.capture_count.toLocaleString() + " rows"),
        node("small", "", percent(checkpoint.parse_bps) + " parsed · " + percent(checkpoint.success_bps) + " success"),
        node("small", "", checkpoint.unique_count.toLocaleString() + " unique · " + checkpoint.classified_count.toLocaleString() + " classified"),
        node("small", "", checkpoint.p95_total_ms ? "95% under " + (checkpoint.p95_total_ms / 1000).toFixed(1) + "s · median " + (checkpoint.p50_tps_milli / 1000).toFixed(1) + " tok/s" : "no timing data"),
        node("small", "", "topics " + topCounts(checkpoint.domain)),
        node("small", "", "tasks " + topCounts(checkpoint.operation)),
        node("small", "", "sentiment " + topCounts(checkpoint.sentiment)),
        node("small", "", "capabilities " + topCounts(checkpoint.capability))
      );
    } else {
      card.append(node("small", "", count >= point ? "data crossed; summary waiting" : (point - count).toLocaleString() + " conversations to go"));
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
  stages.forEach(([key, label], index) => {
    const card = node("div", "stage");
    if (done[key]) card.classList.add("done");
    else if (!marked) { card.classList.add("next"); marked = true; }
    card.append(node("b", "", String(index + 1).padStart(2, "0")), node("h2", "", label), node("p", "", notes[key]));
    el("rail").append(card);
  });
}

function renderMan(man) {
  const state = man.connection || (man.active ? "discovered" : man.trajectory_id ? "detached" : "missing");
  const labels = { attached: "Milk Man attached", discovered: "Milk Man working outside this page", detached: "Milk Man detached · saved session", missing: "no Milk Man session" };
  light("man", state, (labels[state] || labels.missing) + (man.trajectory_id ? " · " + short(man.trajectory_id) : ""));
  rows(el("workspaces"), man.workspaces.map(workspace => ({ title: workspace.name + " · " + (workspace.head || "no git"), detail: workspace.changes.length ? workspace.changes.join("\n") : workspace.path, class: workspace.changes.length ? "changes" : "path" })), "no workspaces");
  rows(el("memory"), man.memory.map(memory => ({ title: memory.ts || "memory", detail: memory.content })), "no saved memory");

  const target = el("activity");
  const follow = target.scrollHeight - target.scrollTop - target.clientHeight < 64;
  target.replaceChildren();
  if (!man.activity.length) target.append(node("article", "message milk-man", "No conversation yet."));
  for (const event of man.activity) {
    const role = event.type === "prompt" ? "you" : event.type === "shell-output" ? "tool" : "milk-man";
    const message = node("article", "message " + role);
    message.append(node("b", "", role === "tool" ? "tool" : role.replace("-", " ")), node("pre", "", event.content));
    if (event.ts) message.append(node("time", "", event.ts));
    target.append(message);
  }
  if (follow) target.scrollTop = target.scrollHeight;
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
  runState("Starting Milk Man.");
  try {
    const response = await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt }) });
    const result = await response.json();
    if (!response.ok) throw Error(result.error || "Unable to start Milk Man.");
    el("prompt").value = "";
    runState(result.state === "queued" ? "Prompt queued for the current run." : "Milk Man started.");
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
  el("checked").textContent = "last checked " + new Date(data.now).toLocaleString();
  const status = milk.status || {};
  renderProgress(milk.progress);
  renderLoop(status);
  rows(el("object"), milk.error ? [{ title: "unavailable", detail: milk.error }] : milk.missing.length ? [{ title: "not configured", detail: milk.missing.join("\n") }] : [
    { title: status.next_action || "waiting", detail: number(milk.progress.capture_count) + " captured · " + number(milk.progress.processed_count) + " summarized" },
    { title: status.profile || "scope", detail: status.scope_id || "" },
    { title: "gateway since restart", detail: number(gateway.observed) + " observed · " + number(gateway.persisted) + " persisted · " + number(gateway.dropped) + " dropped" },
  ], "waiting for status");
  el("foot").textContent = "local only · cloud checked " + data.now;
}

let cloudLoading = false;
async function refreshCloud() {
  if (cloudLoading) return;
  cloudLoading = true;
  el("refresh").disabled = true;
  el("refresh").textContent = "checking";
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw Error("status " + response.status);
    const data = await response.json();
    renderMan(data.man);
    renderCloud(data);
  } catch {
    light("gateway", "down", "dashboard cannot reach gateway");
    light("store", "down", "dashboard cannot reach object store");
    el("checked").textContent = "last checked " + new Date().toLocaleString();
  } finally {
    cloudLoading = false;
    el("refresh").disabled = false;
    el("refresh").textContent = "check cloud";
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
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") el("run-form").requestSubmit();
});
refreshCloud();
setInterval(refreshLocal, 1000);
setInterval(refreshCloud, 30000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshCloud(); });
