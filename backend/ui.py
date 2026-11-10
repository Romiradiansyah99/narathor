"""The console page: one column, a prompt at the bottom, nothing else.

Served by the backend, not by GitHub Pages, because this screen runs the
pipeline. Black, white, one typeface, no cards, no counters, no badges. What you
see is the conversation and the work it started. The line in the corner is the
only ornament, and it stays out of the way of the text.
"""

from __future__ import annotations

from typing import Any

STYLE = """
:root{--bg:#000;--ink:#fff;--dim:#8d8d8d;--dim2:#c8c8c8;--rule:#262626;
--mono:"Courier Prime","Courier New",Courier,monospace}
*{box-sizing:border-box}
html,body{height:100%}
html{background:var(--bg);-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 var(--mono);
-webkit-font-smoothing:antialiased;overflow:hidden}
#app{display:flex;flex-direction:column;height:100dvh;max-width:760px;margin:0 auto}
header{padding:16px 18px 0;font-size:11px;letter-spacing:.06em;color:#5f5f5f;
user-select:none;flex:0 0 auto}
#flow{flex:1;overflow-y:auto;padding:20px 18px 12px;overscroll-behavior:contain}
#flow::-webkit-scrollbar{width:6px}
#flow::-webkit-scrollbar-thumb{background:#2b2b2b}
.turn{margin:0 0 20px;white-space:pre-wrap;word-break:break-word}
.turn.user{color:var(--dim)}
.turn.user .sig{color:#5f5f5f}
.turn.bot{color:var(--ink)}
.turn.log{color:#6f6f6f;font-size:13px;line-height:1.75}
.turn.log .t{color:#4a4a4a}
.turn.block{color:var(--ink);font-size:13.5px;line-height:1.85;border-left:2px solid var(--rule);
padding-left:14px;margin-left:1px}
.turn.block .cite{color:#7a7a7a}
.turn.typing{color:#6f6f6f}
.turn.typing::after{content:"";display:inline-block;width:7px;height:13px;background:#8d8d8d;
vertical-align:-2px;margin-left:6px;animation:b 1.05s steps(1) infinite}
@keyframes b{0%,49%{opacity:1}50%,100%{opacity:0}}
#menu{display:none;border-top:1px solid var(--rule);max-height:38vh;overflow-y:auto;
background:var(--bg);padding:6px 0}
#menu.on{display:block}
#menu .row{display:flex;gap:14px;padding:7px 18px;cursor:pointer;align-items:baseline}
#menu .row.on{background:#111}
#menu .row .u{color:var(--ink);white-space:nowrap;font-size:13.5px}
#menu .row .d{color:#6f6f6f;font-size:12.5px;overflow:hidden;text-overflow:ellipsis;
white-space:nowrap}
form{border-top:1px solid var(--rule);padding:12px 18px calc(12px + env(safe-area-inset-bottom));
display:flex;gap:10px;align-items:flex-start;background:var(--bg)}
form .sig{color:var(--dim);padding-top:6px;user-select:none}
textarea{flex:1;background:transparent;border:0;outline:none;color:var(--ink);
font:15px/1.6 var(--mono);resize:none;padding:4px 0;max-height:40vh;min-height:28px;overflow-y:auto}
form.busy textarea{color:#7a7a7a}
@media(min-width:681px){body{font-size:15.5px}}
"""

TAGLINE = "attention is all you need"


def page(state: dict[str, Any] | None = None) -> str:
    """Render the console. `state` is accepted for compatibility and not shown."""
    return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#000000">
<title>Narathor</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Courier+Prime:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<style>{STYLE}</style>
</head>
<body>
<div id="app">
<header>{TAGLINE}</header>
<main id="flow"></main>
<div id="menu"></div>
<form id="bar" autocomplete="off">
  <span class="sig">&gt;</span>
  <textarea id="prompt" rows="1" enterkeyhint="send"></textarea>
</form>
</div>
<script>
const flow = document.getElementById('flow');
const bar = document.getElementById('bar');
const prompt = document.getElementById('prompt');
const menu = document.getElementById('menu');
let running = false;
let skills = [];
let shown = [];
let cursor = 0;

function atBottom() {{
  return flow.scrollHeight - flow.scrollTop - flow.clientHeight < 80;
}}
function stick(wasBottom) {{
  if (wasBottom) flow.scrollTop = flow.scrollHeight;
}}
function turn(text, cls) {{
  const wasBottom = atBottom();
  const el = document.createElement('div');
  el.className = 'turn ' + cls;
  el.textContent = text;
  flow.appendChild(el);
  stick(wasBottom);
  return el;
}}
function userTurn(text) {{
  const wasBottom = atBottom();
  const el = document.createElement('div');
  el.className = 'turn user';
  const sig = document.createElement('span');
  sig.className = 'sig';
  sig.textContent = '> ';
  el.appendChild(sig);
  el.appendChild(document.createTextNode(text));
  flow.appendChild(el);
  stick(wasBottom);
}}
function blockTurn(text) {{
  const el = turn('', 'block');
  el.textContent = text;
  return el;
}}
function setBusy(on) {{
  running = on;
  bar.classList.toggle('busy', on);
}}

function closeMenu() {{
  menu.classList.remove('on');
  menu.innerHTML = '';
  shown = [];
  cursor = 0;
}}
function paint() {{
  menu.innerHTML = '';
  shown.forEach((s, i) => {{
    const row = document.createElement('div');
    row.className = 'row' + (i === cursor ? ' on' : '');
    const u = document.createElement('span');
    u.className = 'u';
    u.textContent = s.usage;
    const d = document.createElement('span');
    d.className = 'd';
    d.textContent = s.about;
    row.append(u, d);
    row.addEventListener('mousedown', ev => {{
      ev.preventDefault();
      pick(i);
    }});
    menu.appendChild(row);
  }});
  menu.classList.add('on');
}}
function openMenu() {{
  const value = prompt.value;
  if (!value.startsWith('/') || value.includes(' ')) return closeMenu();
  const q = value.slice(1).toLowerCase();
  shown = skills.filter(s => s.name.slice(1).toLowerCase().startsWith(q));
  if (!shown.length) return closeMenu();
  if (cursor > shown.length - 1) cursor = 0;
  paint();
}}
function pick(index) {{
  const s = shown[index];
  if (!s) return;
  closeMenu();
  prompt.value = s.usage;
  prompt.focus();
  resize();
  if (!s.takes_args) send(s.usage);
}}
function move(step) {{
  if (!shown.length) return;
  cursor = (cursor + step + shown.length) % shown.length;
  paint();
}}
function resize() {{
  prompt.style.height = 'auto';
  prompt.style.height = Math.min(prompt.scrollHeight, window.innerHeight * 0.4) + 'px';
}}

async function post(body) {{
  const r = await fetch('api/chat', {{
    method: 'POST',
    headers: {{'content-type': 'application/json'}},
    body: JSON.stringify(body)
  }});
  if (!r.ok) throw new Error('http ' + r.status);
  return r.json();
}}

async function poll(jobId) {{
  const bubble = turn('', 'log');
  let printed = 0;
  while (true) {{
    await new Promise(res => setTimeout(res, 1100));
    let job;
    try {{
      const r = await fetch('api/jobs/' + jobId);
      job = await r.json();
    }} catch (err) {{
      bubble.textContent += '\\nkoneksi putus, coba muat ulang';
      return null;
    }}
    const lines = job.log || [];
    if (lines.length > printed) {{
      const fresh = lines.slice(printed).join('\\n');
      const wasBottom = atBottom();
      bubble.textContent = bubble.textContent ? bubble.textContent + '\\n' + fresh : fresh;
      printed = lines.length;
      stick(wasBottom);
    }}
    if (job.status === 'done' || job.status === 'failed') {{
      if (job.status === 'failed') {{
        turn((job.error || 'gagal'), 'log');
        return null;
      }}
      const block = job.result && job.result.block;
      if (block) blockTurn(block);
      return job;
    }}
  }}
}}

async function send(text) {{
  if (running) return;
  setBusy(true);
  prompt.value = '';
  prompt.style.height = 'auto';
  closeMenu();
  userTurn(text);
  const dots = turn('', 'typing');
  try {{
    let data = await post({{message: text}});
    dots.remove();
    (data.reply || []).forEach(line => turn(line, 'bot'));
    while (data.job_id) {{
      const job = await poll(data.job_id);
      if (!job) break;
      data = await post({{advance: true}});
      (data.reply || []).forEach(line => turn(line, 'bot'));
    }}
  }} catch (err) {{
    dots.remove();
    turn('putus. cek koneksi, lalu kirim ulang.', 'log');
  }} finally {{
    setBusy(false);
    prompt.focus();
  }}
}}

bar.addEventListener('submit', ev => {{
  ev.preventDefault();
  if (shown.length) return pick(cursor);
  const text = prompt.value.trim();
  if (!text) return;
  send(text);
}});
prompt.addEventListener('keydown', ev => {{
  if (ev.key === 'Escape') return closeMenu();
  if (shown.length && (ev.key === 'ArrowDown' || ev.key === 'ArrowUp')) {{
    ev.preventDefault();
    return move(ev.key === 'ArrowDown' ? 1 : -1);
  }}
  if (ev.key === 'Tab' && shown.length) {{
    ev.preventDefault();
    return pick(cursor);
  }}
  if (ev.key === 'Enter' && !ev.shiftKey) {{
    ev.preventDefault();
    bar.requestSubmit();
  }}
}});
prompt.addEventListener('input', () => {{
  resize();
  openMenu();
}});
prompt.addEventListener('blur', () => setTimeout(closeMenu, 120));

(async function boot() {{
  try {{
    const r = await fetch('api/skills');
    skills = (await r.json()).skills || [];
  }} catch (err) {{}}
  try {{
    const r = await fetch('api/chat/history');
    const data = await r.json();
    (data.messages || []).forEach(msg => {{
      if (msg.role === 'tool') return;
      if (msg.role === 'user') userTurn(msg.text);
      else turn(msg.text, 'bot');
    }});
  }} catch (err) {{}}
  flow.scrollTop = flow.scrollHeight;
  prompt.focus();
}})();
</script>
</body>
</html>
"""
