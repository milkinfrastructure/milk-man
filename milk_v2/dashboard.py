from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

from .store import open_store, settings_from_environment


HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Milk Man</title><style>
:root{color-scheme:dark;--bg:#0b0c0b;--panel:#151715;--line:#343734;--ink:#f3efe4;--dim:#969990;--pink:#ff6b9e;--mint:#7ce6c2;--gold:#ffd166}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}main{width:min(1180px,calc(100% - 28px));margin:auto;padding:34px 0 60px}header{display:flex;justify-content:space-between;gap:20px;align-items:end;border-bottom:1px solid var(--line);padding-bottom:18px}.brand{color:var(--pink);font-size:11px;letter-spacing:.16em;text-transform:uppercase}h1,h2,p{margin:0}h1{font-size:25px;letter-spacing:-.05em}.live{color:var(--dim)}.live b{color:var(--mint)}.rail{display:grid;grid-template-columns:repeat(9,1fr);border:1px solid var(--line);margin:26px 0}.stage{min-height:92px;padding:10px;border-right:1px solid var(--line)}.stage:last-child{border:0}.stage b{color:var(--dim);font-size:9px}.stage h2{font-size:11px;margin:13px 0 6px}.stage p{color:var(--dim);font-size:10px;overflow-wrap:anywhere}.stage.done{background:#12231d}.stage.done h2{color:var(--mint)}.stage.next{box-shadow:inset 0 -3px var(--gold)}.grid{display:grid;grid-template-columns:1fr 1fr 1.35fr;gap:1px;background:var(--line);border:1px solid var(--line)}section{background:var(--panel);padding:16px;min-width:0}section>h2{color:var(--dim);font-size:10px;letter-spacing:.13em;text-transform:uppercase;margin-bottom:13px}.row{padding:9px 0;border-top:1px solid var(--line)}.row:first-of-type{border:0}.row b,.row small{display:block}.row small,.empty,.time{color:var(--dim)}.path,.content{white-space:pre-wrap;overflow-wrap:anywhere}.path{font-size:10px;color:var(--dim)}.changes{color:var(--gold)}.activity{grid-column:1/-1;max-height:42vh;overflow:auto}.event{display:grid;grid-template-columns:78px 94px 1fr;gap:10px;padding:9px 0;border-top:1px solid var(--line)}.event:first-of-type{border:0}.kind{color:var(--pink)}.content{margin:0;color:var(--ink)}footer{margin-top:18px;color:var(--dim);font-size:10px}@media(max-width:850px){.rail{grid-template-columns:repeat(3,1fr)}.stage{border-bottom:1px solid var(--line)}.grid{grid-template-columns:1fr}.activity{grid-column:auto}}@media(max-width:520px){header{align-items:start;flex-direction:column}.rail{grid-template-columns:1fr 1fr}.event{grid-template-columns:1fr}.time{display:none}}
</style></head><body><main><header><div><div class="brand">milkinfrastructure.com</div><h1>Milk Man</h1></div><div class="live" id="live">loading</div></header><div class="rail" id="rail"></div><div class="grid"><section><h2>workspaces</h2><div id="workspaces"></div></section><section><h2>memory</h2><div id="memory"></div></section><section><h2>object memory</h2><div id="object"></div></section><section class="activity"><h2>local activity</h2><div id="activity"></div></section></div><footer id="foot"></footer></main><script>
const el=id=>document.getElementById(id), short=v=>typeof v==='string'?v.slice(0,8):'waiting';
const stages=[['traffic','traffic'],['summary','summary'],['readiness','ready'],['eval','evals'],['dataset','dataset'],['training','student'],['evaluation','winner'],['candidate','candidate'],['proposal','route']];
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n}
function rows(target,values,empty){target.replaceChildren();if(!values.length){target.append(node('p','empty',empty));return}for(const value of values){const row=node('div','row');row.append(node('b','',value.title));if(value.detail)row.append(node('small',value.class||'',value.detail));target.append(row)}}
function renderLoop(s){const done={traffic:(s.capture_count||0)>0,summary:!!s.summary,readiness:!!s.readiness,eval:!!s.eval&&!s.eval_generation,dataset:!!s.dataset,training:!!s.training,evaluation:!!s.evaluation,candidate:!!s.candidate,proposal:!!s.proposal};const notes={traffic:(s.capture_count||0)+' captured',summary:s.summary?'checkpoint '+short(s.summary.uuid):'waiting',readiness:s.readiness?(s.readiness.ready?'ready':'not ready'):'waiting',eval:s.eval_generation?s.eval_generation.completed_case_count+' / '+s.eval_generation.target_case_count:s.eval?s.eval.case_count+' cases':'waiting',dataset:s.dataset?'revision '+short(s.dataset.uuid):'waiting',training:s.training?'model '+short(s.training.uuid):'waiting',evaluation:s.evaluation?s.evaluation.winner_branch+' selected':'waiting',candidate:s.candidate?'endpoint '+short(s.candidate.uuid):'zero',proposal:s.proposal?'awaiting signature':(s.next_action||'waiting')};let marked=false;el('rail').replaceChildren();stages.forEach(([key,label],i)=>{const card=node('div','stage');const next=!done[key]&&!marked;if(done[key])card.classList.add('done');else if(next){card.classList.add('next');marked=true}card.append(node('b','',String(i+1).padStart(2,'0')),node('h2','',label),node('p','',notes[key]));el('rail').append(card)})}
function render(d){el('live').replaceChildren(node('b','',d.man.active?'working':'idle'),document.createTextNode(' · '+(d.man.trajectory_id?short(d.man.trajectory_id):'no session')));rows(el('workspaces'),d.man.workspaces.map(w=>({title:w.name+' · '+(w.head||'no git'),detail:w.changes.length?w.changes.join('\n'):w.path,class:w.changes.length?'changes':'path'})),'no workspaces');rows(el('memory'),d.man.memory.map(m=>({title:m.ts||'memory',detail:m.content,class:'content'})),'no saved memory');const s=d.milk.status||{};renderLoop(s);rows(el('object'),d.milk.error?[{title:'unavailable',detail:d.milk.error}]:d.milk.missing.length?[{title:'not configured',detail:d.milk.missing.join('\n')}]:[{title:(s.next_action||'waiting'),detail:(s.capture_count||0)+' captured · '+(s.processed_count||0)+' summarized'},{title:s.profile||'scope',detail:s.scope_id||''}],'waiting for status');el('activity').replaceChildren();if(!d.man.activity.length)el('activity').append(node('p','empty','no activity'));for(const e of d.man.activity){const row=node('div','event');row.append(node('span','kind',e.type),node('span','time',e.ts||''),node('pre','content',e.content));el('activity').append(row)}el('foot').textContent='local only · refreshed '+d.now+' · credentials remain in the Milk Man process environment'}
let loading=false;async function refresh(){if(loading||document.hidden)return;loading=true;try{const response=await fetch('/api/state',{cache:'no-store'});if(!response.ok)throw Error('status '+response.status);render(await response.json())}catch(error){el('live').textContent='unavailable · '+error.message}finally{loading=false}}refresh();setInterval(refresh,3000);document.addEventListener('visibilitychange',refresh);
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


def _milk_status() -> dict:
    required = ["MILK_SCOPE_ID", "MILK_STORE_KIND"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        return {"status": None, "missing": missing, "error": None}
    try:
        settings = settings_from_environment()
        item = open_store(settings).get(settings.scope_prefix + "status/current.json")
        value = json.loads(item.body)
        if not isinstance(value, dict) or value.get("schema_version") != "milk.status.v2":
            raise ValueError("invalid status")
        return {"status": value, "missing": [], "error": None}
    except FileNotFoundError:
        return {"status": None, "missing": [], "error": "no status object yet"}
    except Exception:
        return {"status": None, "missing": [], "error": "object store unavailable"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            self._send(200, "text/html; charset=utf-8", HTML.encode())
            return
        if path == "/api/state":
            body = json.dumps(
                {
                    "schema_version": "milk.dashboard.v1",
                    "now": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "man": _man_state(),
                    "milk": _milk_status(),
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
