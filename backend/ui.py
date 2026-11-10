"""The console page: one column, a prompt at the bottom, nothing else.

Served by the backend, not by GitHub Pages, because this screen runs the
pipeline. Black, white, one typeface, no cards, no counters, no badges. What you
see is the conversation and the work it started.
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
header{padding:14px 18px 0;font-size:11px;letter-spacing:.32em;text-transform:uppercase;color:var(--dim)}
#flow{flex:1;overflow-y:auto;padding:26px 18px 12px;overscroll-behavior:contain}
#flow::-webkit-scrollbar{width:6px}
#flow::-webkit-scrollbar-thumb{background:#2b2b2b}
.claim{color:var(--ink);font-size:clamp(17px,4.4vw,22px);line-height:1.5;margin:0 0 8px}
.claim b{font-weight:700}
.turn{margin:0 0 20px;white-space:pre-wrap;word-break:break-word}
.turn.user{color:var(--dim)}
.turn.user .sig{color:#5f5f5f}
.turn.bot{color:var(--ink)}
.turn.log{color:#6f6f6f;font-size:13px;line-height:1.75}
.turn.log .t{color:#4a4a4a}
.turn.block{color:var(--ink);font-size:13.5px;line-height:1.85;border-left:2px solid var(--rule);
padding-left:14px;margin-left:1px}
.turn.block .cite{color:#7a7a7a}
.wait{color:#6f6f6f;font-size:12.5px}
.wait::after{content:"";display:inline-block;width:7px;height:13px;background:#8d8d8d;
vertical-align:-2px;margin-left:6px;animation:b 1.05s steps(1) infinite}
@keyframes b{0%,49%{opacity:1}50%,100%{opacity:0}}
form{border-top:1px solid var(--rule);padding:12px 18px calc(12px + env(safe-area-inset-bottom));
display:flex;gap:10px;align-items:flex-start;background:var(--bg)}
form .sig{color:var(--dim);padding-top:6px;user-select:none}
textarea{flex:1;background:transparent;border:0;outline:none;color:var(--ink);
font:15px/1.6 var(--mono);resize:none;padding:4px 0;max-height:40vh;min-height:28px;overflow-y:auto}
textarea::placeholder{color:#5a5a5a}
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
<header>narathor</header>
<main id="flow">
  <p class="claim">{TAGLINE}</p>
</main>
<form id="bar" autocomplete="off">
  <span class="sig">&gt;</span>
  <textarea id="prompt" rows="1" placeholder="tulis apa aja" enterkeyhint="send"></textarea>
</form>
</div>
<script>
const flow = document.getElementById('flow');
const bar = document.getElementById('bar');
const prompt = document.getElementById('prompt');
let running = false;

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
  prompt.placeholder = on ? 'lagi jalan...' : 'tulis apa aja';
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
  let shown = 0;
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
    if (lines.length > shown) {{
      const fresh = lines.slice(shown).join('\\n');
      const wasBottom = atBottom();
      bubble.textContent = bubble.textContent ? bubble.textContent + '\\n' + fresh : fresh;
      shown = lines.length;
      stick(wasBottom);
    }}
    if (job.status === 'done' || job.status === 'failed') {{
      if (job.status === 'failed') {{
        turn((job.error || 'gagal') , 'log');
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
  userTurn(text);
  try {{
    let data = await post({{message: text}});
    (data.reply || []).forEach(line => turn(line, 'bot'));
    while (data.job_id) {{
      const job = await poll(data.job_id);
      if (!job) break;
      data = await post({{advance: true}});
      (data.reply || []).forEach(line => turn(line, 'bot'));
    }}
  }} catch (err) {{
    turn('putus. cek koneksi, lalu kirim ulang.', 'log');
  }} finally {{
    setBusy(false);
    prompt.focus();
  }}
}}

bar.addEventListener('submit', ev => {{
  ev.preventDefault();
  const text = prompt.value.trim();
  if (!text) return;
  prompt.value = '';
  prompt.style.height = 'auto';
  send(text);
}});
prompt.addEventListener('keydown', ev => {{
  if (ev.key === 'Enter' && !ev.shiftKey) {{
    ev.preventDefault();
    bar.requestSubmit();
  }}
}});
prompt.addEventListener('input', () => {{
  prompt.style.height = 'auto';
  prompt.style.height = Math.min(prompt.scrollHeight, window.innerHeight * 0.4) + 'px';
}});

(async function boot() {{
  try {{
    const r = await fetch('api/chat/history');
    const data = await r.json();
    (data.messages || []).forEach(msg => {{
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
