"""The console page: one screen where a channel becomes scripts.

Served by the backend, not by GitHub Pages, because this screen writes. The
visual language matches the static readout: one typeface, black and white,
squares and rules, no colour.
"""

from __future__ import annotations

import json
from typing import Any

STYLE = """
:root{--bg:#000;--ink:#fff;--dim:#a4a4a4;--dim2:#d8d8d8;--rule:#333;--rule2:#5a5a5a;
--mono:"Courier Prime","Courier New",Courier,monospace}
*{box-sizing:border-box}
html{-webkit-font-smoothing:antialiased;background:var(--bg)}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 var(--mono);letter-spacing:.005em}
body::after{content:"";position:fixed;inset:0;pointer-events:none;z-index:9;
background:repeating-linear-gradient(180deg,rgba(255,255,255,.03) 0 1px,transparent 1px 3px)}
a{color:inherit}
.wrap{max-width:900px;margin:0 auto;padding:0 22px 80px}
.mast{padding:24px 0 0;font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--dim)}
.mast .row{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;align-items:baseline}
.mast .name{color:var(--ink);letter-spacing:.4em;font-weight:700}
.mast .hr{border-top:1px solid var(--rule);margin-top:14px}
.log{font-size:13px;padding:26px 0 0;color:var(--dim2)}
.log div{padding:1px 0}
.log .sig{color:var(--ink);margin-right:10px}
.log .cursor{display:inline-block;width:8px;height:14px;background:var(--ink);vertical-align:-2px;animation:b 1.1s steps(1) infinite}
@keyframes b{0%,49%{opacity:1}50%,100%{opacity:0}}
h1{font-size:clamp(24px,4.4vw,38px);line-height:1.12;font-weight:700;text-transform:uppercase;letter-spacing:-.01em;margin:26px 0 6px}
.sub{color:var(--dim);font-size:12px;letter-spacing:.16em;text-transform:uppercase;margin:0 0 30px}
.sec{padding:30px 0 0}
.sec-h{display:flex;align-items:center;gap:12px;font-size:11.5px;letter-spacing:.24em;text-transform:uppercase;margin:0 0 20px}
.sec-h::before{content:"";height:1px;flex:1;background:var(--rule);order:-1}
.sec-h b{font-weight:400;color:var(--dim2);font-size:9px;vertical-align:2px}
.sec-h em{font-style:normal;color:var(--dim);letter-spacing:.12em}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px 22px}
.grid .full{grid-column:1/-1}
label{display:block;font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--dim);margin-bottom:6px}
input,textarea,select{
width:100%;background:transparent;color:var(--ink);border:1px solid var(--rule);
border-radius:0;padding:9px 11px;font:14px/1.5 var(--mono);outline:none;
}
input:focus,textarea:focus,select:focus{border-color:var(--ink)}
textarea{resize:vertical;min-height:64px}
select{appearance:none;background-image:none}
select option{background:#000;color:#fff}
.hint{font-size:10px;letter-spacing:.08em;color:#7d7d7d;margin-top:5px;text-transform:uppercase}
.actions{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:18px}
button{
background:transparent;color:var(--ink);border:1px solid var(--ink);border-radius:0;
padding:11px 20px;font:13px/1 var(--mono);letter-spacing:.18em;text-transform:uppercase;cursor:pointer;
}
button:hover{background:var(--ink);color:#000}
button:disabled{border-color:var(--rule2);color:#6d6d6d;cursor:not-allowed;background:transparent}
button.ghost{border-color:var(--rule2);color:var(--dim)}
button.ghost:hover{border-color:var(--ink);color:#000}
.note{font-size:11.5px;letter-spacing:.06em;color:var(--dim);margin-top:12px;line-height:1.7;white-space:pre-wrap}
.note.err{color:var(--ink);border-left:2px solid var(--ink);padding-left:12px}
.note.ok{color:var(--dim2)}
.console{border:1px solid var(--rule);padding:14px 16px;min-height:120px;max-height:320px;overflow-y:auto;
font-size:12.5px;line-height:1.8;color:var(--dim2);white-space:pre-wrap}
.console .t{color:#7d7d7d}
.console .e{color:#fff}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.chip{border:1px solid var(--rule2);padding:3px 9px;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim)}
.foot{margin-top:46px;border-top:1px solid var(--rule);padding-top:14px;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:#7d7d7d}
.foot b{font-weight:400;color:var(--dim)}
@media(max-width:680px){
.grid{grid-template-columns:1fr}
h1{font-size:24px}
}
"""


def page(state: dict[str, Any]) -> str:
    """Render the console with its initial state baked in."""
    boot = json.dumps(state).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Narathor Console</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Courier+Prime:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">
<div class="mast"><div class="row">
<span class="name">Narathor</span>
<span>Assembly console</span>
<span>v1</span>
</div><div class="hr"></div></div>

<div class="log" id="boot">
<div><span class="sig">$</span>narathor console</div>
</div>

<h1>Channel in,<br>scripts out</h1>
<p class="sub">three steps: point at a channel, write the brief, assemble</p>

<div class="sec">
<div class="sec-h"><b>&#9632;</b> 01 &nbsp;Channel<em>where the words come from</em></div>
<div class="grid">
<div class="full">
<label for="ch-url">YouTube channel url</label>
<input id="ch-url" placeholder="https://www.youtube.com/@handle" autocomplete="off">
<p class="hint">any form works: /@handle, /channel/ID, /c/name &middot; only the videos tab is read</p>
</div>
<div>
<label for="ch-limit">Videos to list</label>
<input id="ch-limit" type="number" min="1" max="200" value="25">
</div>
<div>
<label for="ch-min">Minimum duration (s)</label>
<input id="ch-min" type="number" min="0" value="180">
<p class="hint">brief gate: shorter videos are skipped</p>
</div>
</div>
<div class="actions">
<button id="btn-channel">Fetch videos</button>
<span id="st-channel" class="note"></span>
</div>
</div>

<div class="sec">
<div class="sec-h"><b>&#9632;</b> 02 &nbsp;Brief<em>what the script is for</em></div>
<div class="grid">
<div><label for="b-id">id</label><input id="b-id" placeholder="frugal-habits" autocomplete="off"></div>
<div><label for="b-register">Register level</label>
<select id="b-register">
<option value="1">1 &mdash; plain, no jargon</option>
<option value="2" selected>2 &mdash; conversational</option>
<option value="3">3 &mdash; informed</option>
<option value="4">4 &mdash; technical</option>
</select></div>
<div class="full"><label for="b-title">Title</label><input id="b-title" placeholder="Uang bukan soal jumlah"></div>
<div class="full"><label for="b-audience">Audience</label><input id="b-audience" placeholder="pekerja muda Jakarta, gaji pertama"></div>
<div class="full"><label for="b-thesis">Thesis &mdash; the one claim</label>
<textarea id="b-thesis" placeholder="Masalah keuangan bukan soal jumlah pemasukan, tapi ke mana uang pergi."></textarea></div>
<div class="full"><label for="b-outcome">Learning outcome &mdash; what the viewer can do after</label>
<textarea id="b-outcome" placeholder="Bisa menunjuk satu kebocoran pengeluaran sendiri dalam 30 detik."></textarea></div>
<div><label for="b-tone">Tone</label><input id="b-tone" placeholder="tenang, langsung, tanpa menyalahkan"></div>
<div><label for="b-avoid">Tone avoided</label><input id="b-avoid" placeholder="menggurui, jargon">
<p class="hint">never write clickbait or tanpa sitasi here, the brief is refused</p></div>
<div><label for="b-values">Values allowed</label><input id="b-values" placeholder="transparansi, tanggung_jawab_personal"></div>
<div><label for="b-blocked">Values blocked</label><input id="b-blocked" placeholder="fomo, konsumerisme"></div>
<div><label for="b-scripts">Scripts</label><input id="b-scripts" type="number" min="1" max="20" value="1"></div>
<div><label for="b-duration">Target duration (s)</label>
<input id="b-duration" type="number" min="13" max="60" value="15">
<p class="hint">13 to 20, or 60 &middot; 30 is refused</p></div>
</div>
<div class="actions">
<button id="btn-brief">Save brief</button>
<button id="btn-load" class="ghost">Load existing</button>
<span id="st-brief" class="note"></span>
</div>
</div>

<div class="sec">
<div class="sec-h"><b>&#9632;</b> 03 &nbsp;Assemble<em>transcripts then scripts</em></div>
<div class="actions">
<input id="a-limit" type="number" min="1" max="50" value="5" style="max-width:110px">
<button id="btn-ingest">Ingest transcripts</button>
<button id="btn-run">Assemble scripts</button>
</div>
<div class="actions">
<label style="margin:0"><input id="a-force" type="checkbox" style="width:auto;margin-right:8px">refetch cached transcripts</label>
</div>
<div class="console" id="console">-- idle --</div>
<div class="actions"><span id="st-job" class="note"></span></div>
</div>

<div class="sec" id="library-sec">
<div class="sec-h"><b>&#9632;</b> Library<em id="lib-label">-</em></div>
<div class="chips" id="lib-chips"></div>
</div>

<div class="foot">soul <b id="f-soul">-</b> &nbsp; channel <b id="f-channel">-</b> &nbsp; videos <b id="f-videos">0</b> &nbsp; transcripts <b id="f-transcripts">0</b> &nbsp; briefs <b id="f-briefs">0</b></div>
</div>

<script>
const BOOT = {boot};
const $ = (id) => document.getElementById(id);

function line(text, cls) {{
  const el = document.createElement('div');
  el.textContent = text;
  if (cls) el.className = cls;
  $('console').appendChild(el);
  $('console').scrollTop = $('console').scrollHeight;
}}
function clearConsole() {{ $('console').textContent = ''; }}
function setNote(id, text, cls) {{
  const el = $(id);
  el.textContent = text || '';
  el.className = 'note' + (cls ? ' ' + cls : '');
  el.style.whiteSpace = 'pre-wrap';
}}
function listToArr(value) {{
  return (value || '').split(',').map(s => s.trim()).filter(Boolean);
}}

async function boot() {{
  try {{
    const r = await fetch('api/state');
    const s = await r.json();
    paint(s);
  }} catch (err) {{
    setNote('st-channel', 'backend unreachable: ' + err, 'err');
  }}
}}

function paint(s) {{
  $('f-soul').textContent = 'v' + (s.soul ? s.soul.version : '-');
  $('f-channel').textContent = s.channel ? s.channel.name : 'none';
  $('f-videos').textContent = s.videos;
  $('f-transcripts').textContent = s.transcripts;
  $('f-briefs').textContent = s.briefs;
  $('lib-label').textContent = s.channel ? s.channel.name : 'empty';
  const chips = $('lib-chips');
  chips.textContent = '';
  if (!s.channel) {{
    const c = document.createElement('span'); c.className = 'chip'; c.textContent = 'no channel yet'; chips.appendChild(c);
  }} else {{
    [['videos', s.videos], ['transcripts', s.transcripts], ['briefs', s.briefs], ['scripts', s.scripts]].forEach(([k, v]) => {{
      const c = document.createElement('span'); c.className = 'chip'; c.textContent = k + ' ' + v; chips.appendChild(c);
    }});
  }}
  const log = $('boot');
  log.textContent = '';
  const rows = [
    'narathor console',
    'library ' + (s.channel ? s.channel.name : 'empty') + ' / ' + s.videos + ' videos / ' + s.transcripts + ' transcripts',
    'constitution v' + (s.soul ? s.soul.version : '-') + ' ' + (s.soul && s.soul.ok ? 'verified' : 'MISMATCH'),
  ];
  rows.forEach((t, i) => {{
    const d = document.createElement('div');
    const sp = document.createElement('span'); sp.className = 'sig'; sp.textContent = i === 0 ? '$' : '>';
    d.appendChild(sp); d.appendChild(document.createTextNode(t));
    if (i === rows.length - 1) {{
      const cur = document.createElement('span'); cur.className = 'cursor'; d.appendChild(cur);
    }}
    log.appendChild(d);
  }});
  if (s.briefs_existing && s.briefs_existing.length) {{
    $('b-id').value = s.briefs_existing[0];
  }}
}}

async function poll(jobId, statusEl, onDone) {{
  setNote(statusEl, 'running ' + jobId, 'ok');
  const timer = setInterval(async () => {{
    let job;
    try {{
      const r = await fetch('api/jobs/' + jobId);
      job = await r.json();
    }} catch (err) {{
      setNote(statusEl, 'poll failed: ' + err, 'err');
      clearInterval(timer); return;
    }}
    const seen = $('console').dataset.seen || '';
    const shown = seen.split('|').filter(Boolean);
    job.log.forEach((l, i) => {{
      if (!shown.includes(String(i))) line(l);
    }});
    $('console').dataset.seen = job.log.map((_, i) => i).join('|');
    if (job.status === 'done' || job.status === 'failed') {{
      clearInterval(timer);
      setNote(statusEl, job.status === 'done' ? 'done ' + jobId : 'failed ' + jobId, job.status === 'done' ? 'ok' : 'err');
      if (job.status === 'failed') line(job.error || 'failed', 'e');
      boot();
      if (onDone) onDone(job);
    }}
  }}, 1200);
}}

$('btn-channel').addEventListener('click', async () => {{
  const url = $('ch-url').value.trim();
  if (!url) {{ setNote('st-channel', 'channel url is empty', 'err'); return; }}
  clearConsole(); $('console').dataset.seen = '';
  line('$ narathor channel --url ' + url);
  $('btn-channel').disabled = true;
  try {{
    const r = await fetch('api/channels', {{
      method: 'POST', headers: {{'content-type': 'application/json'}},
      body: JSON.stringify({{ url, limit: Number($('ch-limit').value) || 25 }})
    }});
    const d = await r.json();
    if (!r.ok) {{ setNote('st-channel', JSON.stringify(d.detail || d), 'err'); $('btn-channel').disabled = false; return; }}
    poll(d.job_id, 'st-channel', () => {{ $('btn-channel').disabled = false; }});
  }} catch (err) {{
    setNote('st-channel', 'request failed: ' + err, 'err');
    $('btn-channel').disabled = false;
  }}
}});

$('btn-brief').addEventListener('click', async () => {{
  const payload = {{
    id: $('b-id').value.trim().toLowerCase().replace(/[^a-z0-9-]+/g, '-'),
    title: $('b-title').value.trim(),
    learning_outcome: $('b-outcome').value.trim(),
    thesis: $('b-thesis').value.trim(),
    audience: {{
      primary: $('b-audience').value.trim(),
      literacy_level: Number($('b-register').value) <= 2 ? 'menengah' : 'tinggi',
      pain_points: []
    }},
    values_allowed: listToArr($('b-values').value),
    values_blocked: listToArr($('b-blocked').value),
    register_level: Number($('b-register').value),
    tone: {{ target: $('b-tone').value.trim(), avoid: listToArr($('b-avoid').value) }},
    seasonal_context: {{ as_of: new Date().toISOString().slice(0, 10), period: null, moments: [], trend_notes: '' }},
    sources: {{
      channels: [$('ch-url').value.trim() || 'unknown'],
      recency_preference: 'any',
      min_duration_s: Number($('ch-min').value) || 180
    }},
    output: {{
      scripts: Number($('b-scripts').value) || 1,
      target_duration_s: Number($('b-duration').value) || 15,
      language: 'id',
      montages: 0
    }}
  }};
  try {{
    const r = await fetch('api/briefs', {{
      method: 'POST', headers: {{'content-type': 'application/json'}}, body: JSON.stringify(payload)
    }});
    const d = await r.json();
    if (!r.ok) {{
      const detail = d.detail || d;
      const reasons = Array.isArray(detail.rejections) ? detail.rejections.map(x => x.code + ' ' + x.message).join('\\n') : JSON.stringify(detail);
      setNote('st-brief', 'refused:\\n' + reasons, 'err');
      return;
    }}
    setNote('st-brief', 'saved ' + d.brief_id + ' / hash ' + d.brief_hash.slice(0, 12), 'ok');
    boot();
  }} catch (err) {{
    setNote('st-brief', 'request failed: ' + err, 'err');
  }}
}});

$('btn-load').addEventListener('click', async () => {{
  const id = $('b-id').value.trim();
  if (!id) {{ setNote('st-brief', 'fill the id first', 'err'); return; }}
  try {{
    const r = await fetch('api/briefs/' + id);
    const d = await r.json();
    if (!r.ok) {{ setNote('st-brief', 'not found: ' + id, 'err'); return; }}
    const b = d.brief;
    $('b-title').value = b.title; $('b-outcome').value = b.learning_outcome;
    $('b-thesis').value = b.thesis; $('b-audience').value = b.audience.primary;
    $('b-register').value = String(b.register_level);
    $('b-tone').value = b.tone.target; $('b-avoid').value = (b.tone.avoid || []).join(', ');
    $('b-values').value = (b.values_allowed || []).join(', ');
    $('b-blocked').value = (b.values_blocked || []).join(', ');
    $('b-scripts').value = b.output.scripts; $('b-duration').value = b.output.target_duration_s;
    setNote('st-brief', 'loaded ' + id, 'ok');
  }} catch (err) {{
    setNote('st-brief', 'request failed: ' + err, 'err');
  }}
}});

async function startJob(path, body, button, statusEl) {{
  const id = $('b-id').value.trim();
  if (!id) {{ setNote(statusEl, 'save a brief first', 'err'); return; }}
  clearConsole(); $('console').dataset.seen = '';
  line('$ narathor ' + path.split('/').pop() + ' --narrative ' + id);
  button.disabled = true;
  try {{
    const r = await fetch(path, {{
      method: 'POST', headers: {{'content-type': 'application/json'}},
      body: JSON.stringify(Object.assign({{ brief_id: id }}, body))
    }});
    const d = await r.json();
    if (!r.ok) {{ setNote(statusEl, JSON.stringify(d.detail || d), 'err'); button.disabled = false; return; }}
    poll(d.job_id, statusEl, () => {{ button.disabled = false; }});
  }} catch (err) {{
    setNote(statusEl, 'request failed: ' + err, 'err');
    button.disabled = false;
  }}
}}

$('btn-ingest').addEventListener('click', () => startJob('api/ingest', {{
  limit: Number($('a-limit').value) || 5, force: $('a-force').checked
}}, $('btn-ingest'), 'st-job'));

$('btn-run').addEventListener('click', () => startJob('api/runs', {{
  count: Number($('b-scripts').value) || 1
}}, $('btn-run'), 'st-job'));

boot();
</script>
</body>
</html>
"""
