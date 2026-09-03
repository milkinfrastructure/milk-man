from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request
from urllib.parse import urlsplit

from .summary import thresholds
from .store import open_store, settings_from_environment


HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Milk Man</title><style>
:root{color-scheme:dark;--bg:#0c0d0c;--panel:#181a18;--line:#383a37;--ink:#f3efe4;--dim:#8f918b;--pink:#ff6b9e;--mint:#7ce6c2;--gold:#ffd166;--red:#ff6b6b}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}main{width:min(1180px,calc(100% - 28px));margin:auto;padding:34px 0 60px}header{display:flex;justify-content:space-between;gap:20px;align-items:end;border-bottom:1px solid var(--line);padding-bottom:18px}.brand{color:var(--pink);font-size:11px;letter-spacing:.16em;text-transform:uppercase}h1,h2,p{margin:0}h1{font-size:25px;letter-spacing:-.05em}.controls{display:grid;grid-template-columns:auto auto;gap:5px 12px;align-items:center;text-align:right}.gateway,.live{color:var(--dim)}.live{grid-column:1/-1}.live b{color:var(--mint)}.signal{display:inline-block;width:11px;height:11px;margin-right:8px;border:2px solid var(--dim);vertical-align:-1px}.signal.up{background:var(--mint);border-color:var(--mint)}.signal.down{background:var(--red);border-color:var(--red)}.signal.degraded{background:var(--gold);border-color:var(--gold)}button{border:1px solid var(--line);border-radius:0;background:var(--ink);color:var(--bg);padding:7px 10px;font:700 10px/1 ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;cursor:pointer}button:hover{background:var(--pink)}button:disabled{opacity:.45;cursor:wait}.checked{grid-column:1/-1;color:var(--dim);font-size:9px}.progress{margin:26px 0 16px;border:1px solid var(--line)}.progress-head{display:flex;justify-content:space-between;gap:20px;margin-bottom:13px}.volume{font-size:17px}.target{color:var(--dim);text-align:right}.meter{height:22px;border:1px solid var(--line);background:var(--bg);padding:3px}.meter-fill{height:100%;width:0;background:var(--pink)}.milestones{display:grid;grid-template-columns:repeat(var(--points,1),minmax(0,1fr));gap:1px;background:var(--line);margin-top:15px;border:1px solid var(--line)}.checkpoint{background:var(--panel);padding:11px;min-height:140px}.checkpoint.reached{background:#14231e}.checkpoint.crossed{border-bottom:3px solid var(--gold)}.checkpoint h3{margin:0 0 8px;font-size:12px}.checkpoint .pin{display:inline-block;width:8px;height:8px;margin-right:7px;background:var(--dim)}.checkpoint.reached .pin{background:var(--mint)}.checkpoint.crossed .pin{background:var(--gold)}.checkpoint small{display:block;color:var(--dim);margin-top:4px;overflow-wrap:anywhere}.rail{display:grid;grid-template-columns:repeat(9,1fr);border:1px solid var(--line);margin:16px 0}.stage{min-height:92px;padding:10px;border-right:1px solid var(--line)}.stage:last-child{border:0}.stage b{color:var(--dim);font-size:9px}.stage h2{font-size:11px;margin:13px 0 6px}.stage p{color:var(--dim);font-size:10px;overflow-wrap:anywhere}.stage.done{background:#14231e}.stage.done h2{color:var(--mint)}.stage.next{border-bottom:3px solid var(--gold)}.grid{display:grid;grid-template-columns:1fr 1fr 1.35fr;gap:1px;background:var(--line);border:1px solid var(--line)}section{background:var(--panel);padding:16px;min-width:0}section>h2{color:var(--dim);font-size:10px;letter-spacing:.13em;text-transform:uppercase;margin-bottom:13px}.row{padding:9px 0;border-top:1px solid var(--line)}.row:first-of-type{border:0}.row b,.row small{display:block}.row small,.empty,.time{color:var(--dim)}.path,.content{white-space:pre-wrap;overflow-wrap:anywhere}.path{font-size:10px;color:var(--dim)}.changes{color:var(--gold)}.activity{grid-column:1/-1;max-height:42vh;overflow:auto}.event{display:grid;grid-template-columns:78px 94px 1fr;gap:10px;padding:9px 0;border-top:1px solid var(--line)}.event:first-of-type{border:0}.kind{color:var(--pink)}.content{margin:0;color:var(--ink)}footer{margin-top:18px;color:var(--dim);font-size:10px}@media(max-width:850px){.rail{grid-template-columns:repeat(3,1fr)}.stage{border-bottom:1px solid var(--line)}.grid{grid-template-columns:1fr}.activity{grid-column:auto}.milestones{grid-template-columns:1fr 1fr}}@media(max-width:520px){header{align-items:start;flex-direction:column}.controls{text-align:left}.rail,.milestones{grid-template-columns:1fr}.event{grid-template-columns:1fr}.time{display:none}.progress-head{display:block}.target{text-align:left;margin-top:4px}}
</style></head><body><main><header><div><div class="brand">milkinfrastructure.com</div><h1>Milk Man</h1></div><div class="controls"><div class="gateway"><i class="signal" id="signal"></i><b id="gateway">gateway unchecked</b></div><button id="refresh" type="button">check cloud</button><small class="checked" id="checked">never checked</small><div class="live" id="live">loading Milk Man</div></div></header><section class="progress"><h2>data milk</h2><div class="progress-head"><b class="volume" id="volume">waiting for object memory</b><span class="target" id="target"></span></div><div class="meter" id="meter" role="progressbar" aria-valuemin="0" aria-valuemax="100"><div class="meter-fill" id="fill"></div></div><div class="milestones" id="milestones"></div></section><div class="rail" id="rail"></div><div class="grid"><section><h2>workspaces</h2><div id="workspaces"></div></section><section><h2>memory</h2><div id="memory"></div></section><section><h2>object memory</h2><div id="object"></div></section><section class="activity"><h2>local activity</h2><div id="activity"></div></section></div><footer id="foot"></footer></main><script>
const el=id=>document.getElementById(id),short=v=>typeof v==='string'?v.slice(0,8):'waiting',num=v=>Number.isFinite(Number(v))?Number(v):0;
const stages=[['traffic','traffic'],['summary','summary'],['readiness','ready'],['eval','evals'],['dataset','dataset'],['training','student'],['evaluation','winner'],['candidate','candidate'],['proposal','route']];
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n}
function rows(target,values,empty){target.replaceChildren();if(!values.length){target.append(node('p','empty',empty));return}for(const value of values){const row=node('div','row');row.append(node('b','',value.title));if(value.detail)row.append(node('small',value.class||'',value.detail));target.append(row)}}
function topCounts(values){return Object.entries(values||{}).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).slice(0,3).map(v=>v[0]+' '+v[1]).join(' · ')||'none'}
function percent(bps){return (num(bps)/100).toFixed(num(bps)%100?2:0)+'%'}
function fillPercent(count,points){if(!points.length)return 0;let prior=0;for(let i=0;i<points.length;i++){if(count<points[i])return 100*(i+(count-prior)/(points[i]-prior))/points.length;prior=points[i]}return 100}
function renderProgress(p){p=p||{};const count=num(p.capture_count),processed=num(p.processed_count),points=p.thresholds||[],checkpoints=p.checkpoints||[];el('volume').textContent=count.toLocaleString()+' conversations captured';el('target').textContent=p.next_threshold?(processed.toLocaleString()+' summarized · '+(count>=p.next_threshold?'ready to summarize at ':(p.next_threshold-count).toLocaleString()+' to ')+p.next_threshold.toLocaleString()):processed.toLocaleString()+' summarized · all configured checkpoints reached';const fill=Math.max(0,Math.min(100,fillPercent(count,points)));el('fill').style.width=fill+'%';el('meter').setAttribute('aria-valuenow',String(Math.round(fill)));el('milestones').style.setProperty('--points',String(Math.max(1,points.length)));el('milestones').replaceChildren();for(const point of points){const checkpoint=checkpoints.find(c=>num(c.capture_count)>=point);const card=node('div','checkpoint'+(checkpoint?' reached':count>=point?' crossed':''));const title=node('h3');title.append(node('i','pin'),document.createTextNode(point.toLocaleString()));card.append(title);if(checkpoint){card.append(node('small','',short(checkpoint.uuid)+' · '+checkpoint.capture_count.toLocaleString()+' rows'),node('small','',percent(checkpoint.parse_bps)+' parsed · '+percent(checkpoint.success_bps)+' success'),node('small','',checkpoint.unique_count.toLocaleString()+' unique · '+checkpoint.classified_count.toLocaleString()+' classified'),node('small','',checkpoint.p95_total_ms?('95% under '+(checkpoint.p95_total_ms/1000).toFixed(1)+'s · median '+(checkpoint.p50_tps_milli/1000).toFixed(1)+' tok/s'):'no timing data'),node('small','category','topics '+topCounts(checkpoint.domain)),node('small','category','tasks '+topCounts(checkpoint.operation)),node('small','category','sentiment '+topCounts(checkpoint.sentiment)),node('small','category','capabilities '+topCounts(checkpoint.capability)))}else{card.append(node('small','',count>=point?'data crossed; summary waiting':(point-count).toLocaleString()+' conversations to go'))}el('milestones').append(card)}if(!points.length)el('milestones').append(node('div','checkpoint','no thresholds configured'))}
function renderLoop(s){const done={traffic:(s.capture_count||0)>0,summary:!!s.summary,readiness:!!s.readiness,eval:!!s.eval&&!s.eval_generation,dataset:!!s.dataset,training:!!s.training,evaluation:!!s.evaluation,candidate:!!s.candidate,proposal:!!s.proposal};const notes={traffic:(s.capture_count||0)+' captured',summary:s.summary?'checkpoint '+short(s.summary.uuid):'waiting',readiness:s.readiness?(s.readiness.ready?'ready':'not ready'):'waiting',eval:s.eval_generation?s.eval_generation.completed_case_count+' / '+s.eval_generation.target_case_count:s.eval?s.eval.case_count+' cases':'waiting',dataset:s.dataset?'revision '+short(s.dataset.uuid):'waiting',training:s.training?'model '+short(s.training.uuid):'waiting',evaluation:s.evaluation?s.evaluation.winner_branch+' selected':'waiting',candidate:s.candidate?'endpoint '+short(s.candidate.uuid):'zero',proposal:s.proposal?'awaiting signature':(s.next_action||'waiting')};let marked=false;el('rail').replaceChildren();stages.forEach(([key,label],i)=>{const card=node('div','stage');const next=!done[key]&&!marked;if(done[key])card.classList.add('done');else if(next){card.classList.add('next');marked=true}card.append(node('b','',String(i+1).padStart(2,'0')),node('h2','',label),node('p','',notes[key]));el('rail').append(card)})}
function renderMan(man){el('live').replaceChildren(node('b','',man.active?'working':'idle'),document.createTextNode(' · '+(man.trajectory_id?short(man.trajectory_id):'no session')));rows(el('workspaces'),man.workspaces.map(w=>({title:w.name+' · '+(w.head||'no git'),detail:w.changes.length?w.changes.join('\n'):w.path,class:w.changes.length?'changes':'path'})),'no workspaces');rows(el('memory'),man.memory.map(m=>({title:m.ts||'memory',detail:m.content,class:'content'})),'no saved memory');el('activity').replaceChildren();if(!man.activity.length)el('activity').append(node('p','empty','no activity'));for(const e of man.activity){const row=node('div','event');row.append(node('span','kind',e.type),node('span','time',e.ts||''),node('pre','content',e.content));el('activity').append(row)}}
function renderCloud(d){const g=d.gateway||{};el('signal').className='signal '+(g.state||'');el('gateway').textContent=g.state==='up'?'gateway active':g.state==='degraded'?'gateway degraded':g.state==='down'?'gateway unavailable':'gateway not configured';el('checked').textContent='last checked '+new Date(d.now).toLocaleString();const s=d.milk.status||{};renderProgress(d.milk.progress);renderLoop(s);rows(el('object'),d.milk.error?[{title:'unavailable',detail:d.milk.error}]:d.milk.missing.length?[{title:'not configured',detail:d.milk.missing.join('\n')}]:[{title:(s.next_action||'waiting'),detail:(d.milk.progress.capture_count||0)+' captured · '+(d.milk.progress.processed_count||0)+' summarized'},{title:s.profile||'scope',detail:s.scope_id||''},{title:'gateway since restart',detail:(g.observed||0)+' observed · '+(g.persisted||0)+' persisted · '+(g.dropped||0)+' dropped'}],'waiting for status');el('foot').textContent='local only · cloud checked '+d.now+' · credentials remain in the Milk Man process environment'}
let cloudLoading=false;async function refreshCloud(){if(cloudLoading)return;cloudLoading=true;el('refresh').disabled=true;el('refresh').textContent='checking';try{const r=await fetch('/api/state',{cache:'no-store'});if(!r.ok)throw Error('status '+r.status);const d=await r.json();renderMan(d.man);renderCloud(d)}catch(error){el('signal').className='signal down';el('gateway').textContent='dashboard unavailable';el('checked').textContent='last checked '+new Date().toLocaleString()}finally{cloudLoading=false;el('refresh').disabled=false;el('refresh').textContent='check cloud'}}
async function refreshLocal(){if(document.hidden)return;try{const r=await fetch('/api/local',{cache:'no-store'});if(r.ok)renderMan((await r.json()).man)}catch(error){}}
el('refresh').addEventListener('click',refreshCloud);refreshCloud();setInterval(refreshLocal,3000);document.addEventListener('visibilitychange',refreshLocal);
</script></body></html>"""


def _tail(path: Path, limit: int) -> list[dict]:
    try:
        with path.open() as source:
            lines = deque(source, maxlen=limit)
    except OSError:
        return []
    values = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            values.append(value)
    return values


def _git(path: str, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", path, *arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.decode("utf-8", "replace").strip() if result.returncode == 0 else ""


def _within(root: Path, value: object) -> Path | None:
    if not isinstance(value, str):
        return None
    path = Path(value).resolve()
    return path if path == root or root in path.parents else None


def _active(trajectory: Path | None) -> bool:
    if trajectory is None:
        return False
    try:
        result = subprocess.run(
            ["ps", "-axo", "command="],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    target = str(trajectory).encode()
    return result.returncode == 0 and any(target in line and b"shellm" in line for line in result.stdout.splitlines())


def _man_state() -> dict:
    root = Path(os.environ.get("MILK_MAN_STATE_DIR", Path.home() / ".local/state/milk-man")).resolve()
    try:
        current = json.loads((root / "current.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {"active": False, "trajectory_id": None, "workspaces": [], "memory": [], "activity": []}
    trajectory = _within(root, current.get("trajectory_file"))
    memory = _within(root, current.get("memory_file"))
    workspaces = []
    for value in current.get("workspaces", []):
        if not isinstance(value, dict) or not isinstance(value.get("path"), str):
            continue
        path = value["path"]
        workspaces.append({
            "name": str(value.get("name", "workspace"))[:64],
            "path": path,
            "head": _git(path, "rev-parse", "--short=9", "HEAD"),
            "changes": _git(path, "status", "--short").splitlines()[:24],
        })
    memories = [
        {"ts": str(value.get("ts", ""))[:32], "content": str(value.get("content", ""))[:1000]}
        for value in (_tail(memory, 12) if memory else [])
        if value.get("type") == "memory"
    ]
    activity = []
    for value in _tail(trajectory, 10) if trajectory else []:
        kind = str(value.get("type", "event"))[:32]
        if kind == "trajectory":
            continue
        content = str(value.get("content", ""))
        if kind == "shell-output":
            content = "\n".join(str(value.get("command", "")).splitlines()[:6]) + f"\nexit {value.get('exit', '?')}"
        elif kind == "reasoning":
            content = content.split("```", 1)[0].strip()
        activity.append({"type": kind, "ts": str(value.get("ts", ""))[11:19], "content": content[-800:]})
    return {
        "active": _active(trajectory),
        "trajectory_id": current.get("trajectory_id"),
        "workspaces": workspaces,
        "memory": memories,
        "activity": activity,
    }


def _capture_count(store, prefix: str) -> int:
    count, cursor = 0, None
    for _ in range(10_000):
        page = store.list(prefix, cursor)
        count += len(page.keys)
        if page.next_cursor is None:
            return count
        cursor = page.next_cursor
    raise ValueError("capture listing is too large")


def _counts(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key)[:64]: item
        for key, item in value.items()
        if isinstance(item, int) and item >= 0
    }


def _summary_view(value: dict) -> dict:
    structural = value.get("structural") if isinstance(value.get("structural"), dict) else {}
    counters = structural.get("counters") if isinstance(structural.get("counters"), dict) else {}
    quality = structural.get("quality") if isinstance(structural.get("quality"), dict) else {}
    series = structural.get("series") if isinstance(structural.get("series"), dict) else {}
    semantic_root = value.get("semantic") if isinstance(value.get("semantic"), dict) else {}
    semantic = semantic_root.get("cumulative") if isinstance(semantic_root.get("cumulative"), dict) else {}
    total = series.get("total_ms") if isinstance(series.get("total_ms"), dict) else {}
    tps = series.get("tps_milli") if isinstance(series.get("tps_milli"), dict) else {}
    return {
        "uuid": value.get("summary_uuid"),
        "capture_count": value.get("capture_count", 0),
        "parse_bps": quality.get("parse_basis_points", 0),
        "success_bps": quality.get("success_basis_points", 0),
        "unique_count": counters.get("unique_contents", 0),
        "classified_count": semantic.get("classified", 0),
        "p95_total_ms": total.get("p95", 0),
        "p50_tps_milli": tps.get("p50", 0),
        "domain": _counts(semantic.get("domain")),
        "operation": _counts(semantic.get("operation")),
        "sentiment": _counts(semantic.get("sentiment")),
        "capability": _counts(semantic.get("capability")),
    }


def _summary_chain(store, settings, pointer: object, limit: int) -> list[dict]:
    if not isinstance(pointer, dict):
        return []
    key, expected, seen, values = pointer.get("key"), pointer.get("sha256"), set(), []
    for _ in range(limit):
        if not isinstance(key, str) or not key.startswith(settings.scope_prefix + "s/") or key in seen:
            break
        seen.add(key)
        item = store.get(key)
        if not isinstance(expected, str) or hashlib.sha256(item.body).hexdigest() != expected:
            raise ValueError("summary digest differs")
        value = json.loads(item.body)
        if not isinstance(value, dict) or value.get("schema_version") != "milk.summary.v2" or value.get("scope_id") != settings.scope_id:
            raise ValueError("summary identity differs")
        values.append(_summary_view(value))
        key, expected = value.get("parent_summary_key"), value.get("parent_summary_sha256")
        if key is None:
            break
    return sorted(values, key=lambda value: value["capture_count"])


def _gateway_health() -> dict:
    raw = os.environ.get("MILK_PARLOR_BASE_URL", "")
    if not raw:
        return {"state": "", "observed": 0, "persisted": 0, "dropped": 0}
    try:
        parsed = urlsplit(raw)
        local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") not in {"", "/v1"}
            or parsed.scheme not in ({"http", "https"} if local else {"https"})
            or not parsed.netloc
        ):
            raise ValueError("invalid Parlor URL")
        request = urllib.request.Request(
            f"{parsed.scheme}://{parsed.netloc}/healthz",
            headers={"Accept": "application/json", "User-Agent": "milk-man-dashboard/1"},
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            body = response.read(65_537)
            if response.status != 200 or len(body) > 65_536:
                raise ValueError("invalid health response")
        value = json.loads(body)
        capture = value.get("capture") if isinstance(value, dict) else None
        if not isinstance(capture, dict):
            raise ValueError("invalid health response")
        state = "up" if value.get("status") == "ok" and capture.get("writer_alive") is True else "degraded"
        return {
            "state": state,
            "observed": capture.get("observed", 0),
            "persisted": capture.get("persisted", 0),
            "dropped": capture.get("dropped", 0),
        }
    except Exception:
        return {"state": "down", "observed": 0, "persisted": 0, "dropped": 0}


def _milk_status() -> dict:
    required = ["MILK_SCOPE_ID", "MILK_STORE_KIND"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        return {"status": None, "progress": {}, "missing": missing, "error": None}
    try:
        settings = settings_from_environment()
        store = open_store(settings)
        item = store.get(settings.scope_prefix + "status/current.json")
        value = json.loads(item.body)
        if not isinstance(value, dict) or value.get("schema_version") != "milk.status.v2":
            raise ValueError("invalid status")
        points = thresholds(settings.profile)
        captured = _capture_count(store, settings.scope_prefix + "c/")
        processed = value.get("processed_count", 0)
        value = {**value, "capture_count": captured}
        return {
            "status": value,
            "progress": {
                "capture_count": captured,
                "processed_count": processed,
                "thresholds": points,
                "next_threshold": next((point for point in points if point > processed), None),
                "checkpoints": _summary_chain(store, settings, value.get("summary"), len(points) + 2),
            },
            "missing": [],
            "error": None,
        }
    except FileNotFoundError:
        return {"status": None, "progress": {}, "missing": [], "error": "no status object yet"}
    except Exception:
        return {"status": None, "progress": {}, "missing": [], "error": "object store unavailable"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            self._send(200, "text/html; charset=utf-8", HTML.encode())
            return
        if path == "/api/local":
            body = json.dumps(
                {"schema_version": "milk.dashboard-local.v1", "man": _man_state()},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            self._send(200, "application/json", body)
            return
        if path == "/api/state":
            body = json.dumps(
                {
                    "schema_version": "milk.dashboard.v1",
                    "now": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "man": _man_state(),
                    "milk": _milk_status(),
                    "gateway": _gateway_health(),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            self._send(200, "application/json", body)
            return
        self._send(404, "text/plain; charset=utf-8", b"not found\n")

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, unused_format: str, *unused_arguments: object) -> None:
        return


def main() -> None:
    try:
        port = int(os.environ.get("MILK_DASHBOARD_PORT", "8765"))
    except ValueError as error:
        raise SystemExit("milk-man: MILK_DASHBOARD_PORT must be an integer") from error
    if not 1024 <= port <= 65535:
        raise SystemExit("milk-man: MILK_DASHBOARD_PORT must be in 1024..65535")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"milk-man dashboard: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
