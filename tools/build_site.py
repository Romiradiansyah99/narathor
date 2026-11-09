"""Build the static site from run artefacts. No extra dependencies.

GitHub Pages only serves files, so everything is rendered here and nothing
runs in the browser. The visual language follows docs/BRAND.md: Fraunces for
display, Inter for body, JetBrains Mono for timestamps and ids, Cobalt as the
single accent, panels without borders.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
SITE_DIR = ROOT / "site"

FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;1,9..144,400"
    "&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap"
)

STYLE = """
:root{
--bg:#090B0F; --panel:#15191F; --panel-2:#1B2029;
--ink:#E9EDF3; --fog:#C9D2DD; --muted:#9BA6B6;
--cobalt:#3B63E8; --cobalt-ink:#7E9BFF; --cobalt-dim:#22408F; --steel:#7C9BC7;
--mist:#C8D4E4; --ember:#C2413B;
--display:"Fraunces",Georgia,serif; --body:"Inter",system-ui,sans-serif;
--mono:"JetBrains Mono",ui-monospace,monospace;
}
*{box-sizing:border-box}
html{-webkit-font-smoothing:antialiased}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 var(--body)}
a{color:inherit;text-decoration:none}
.wrap{max-width:1060px;margin:0 auto;padding:0 28px}
.narrow{max-width:760px;margin-left:0}

.top{border-bottom:1px solid rgba(201,210,221,.07);padding:22px 0}
.top .wrap{display:flex;align-items:center;justify-content:space-between;gap:20px}
.brand{font-family:var(--display);font-size:17px;letter-spacing:.01em}
.brand span{color:var(--muted);font-family:var(--mono);font-size:11px;letter-spacing:.16em;margin-left:12px;text-transform:uppercase}
.top nav{display:flex;gap:22px;font-size:13px;color:var(--muted)}
.top nav a:hover{color:var(--ink)}

.hero{padding:88px 0 56px}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--cobalt-ink);margin:0 0 22px}
h1{font-family:var(--display);font-weight:400;font-size:clamp(34px,5.2vw,58px);line-height:1.06;letter-spacing:-.02em;margin:0 0 22px;max-width:21ch}
h1 em{font-style:italic;color:var(--mist)}
.lede{font-size:17px;line-height:1.6;color:var(--fog);max-width:62ch;margin:0 0 34px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:24px;padding-top:26px;border-top:1px solid rgba(201,210,221,.08)}
.stat .n{font-family:var(--mono);font-size:26px;color:var(--ink);letter-spacing:-.03em;line-height:1}
.stat .n small{font-size:13px;color:var(--muted);letter-spacing:0;margin-left:2px}
.stat .l{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-top:4px}

section{padding:14px 0 54px}
h2{font-family:var(--mono);font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);font-weight:500;margin:0 0 20px}

.cards{display:grid;gap:14px}
.card{display:grid;grid-template-columns:1fr 150px;gap:26px;align-items:center;background:var(--panel);border-radius:14px;padding:26px 0 26px 0;transition:background .18s}
.card .body{padding-left:0}
.card:hover{background:var(--panel-2);transform:translateY(-1px)}
.card .kicker{font-family:var(--mono);font-size:11px;color:#A9B6C8;letter-spacing:.12em;margin-bottom:10px}
.card h3{font-family:var(--display);font-weight:400;font-size:26px;line-height:1.22;letter-spacing:-.01em;margin:0 0 14px}
.card .hook{color:var(--fog);font-size:15px;margin:0 0 18px;font-style:italic;font-family:var(--display)}
.card .meta{display:flex;flex-wrap:wrap;gap:18px;font-family:var(--mono);font-size:11.5px;color:var(--muted)}
.card .go{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#9DB2FF;text-align:right}
.card .spark{display:flex;gap:4px;justify-content:flex-end;margin-top:12px;width:100%}
.card .spark i{display:block;flex:1;height:4px;border-radius:2px;background:rgba(201,210,221,.18)}
.card .spark i.on{background:var(--cobalt)}
.card .meta b{color:var(--mist);font-weight:500}

.lib{width:100%;border-collapse:collapse;font-size:14px}
.lib th{text-align:left;font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:#AEB9C8;font-weight:500;padding:0 14px 10px 0}
.lib td{padding:14px 14px 14px 0;border-top:1px solid rgba(201,210,221,.07);vertical-align:top}
.lib td.id{font-family:var(--mono);font-size:12px;color:var(--steel);white-space:nowrap;width:1%}
.lib td.fit{width:52px}
.lib th:nth-child(3){width:96px}
.lib td.fit{font-family:var(--mono);font-size:12px;white-space:nowrap;width:52px}
.fit5{color:var(--cobalt-ink)} .fit3{color:var(--mist)} .fit1{color:var(--muted)} .fit0{color:var(--ember)}
.lib td.q{color:var(--fog)}

/* script page */
.back{font-family:var(--mono);font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);display:inline-flex;align-items:center;gap:8px;margin-bottom:40px}
.back:hover{color:var(--ink)}
.s-title{font-family:var(--display);font-weight:400;font-size:clamp(30px,4.4vw,46px);line-height:1.1;letter-spacing:-.02em;margin:0 0 18px}
.s-meta{display:flex;flex-wrap:wrap;gap:20px;font-family:var(--mono);font-size:11.5px;color:var(--muted);margin-bottom:44px}
.s-meta b{color:var(--mist);font-weight:500}

.hookbox{background:linear-gradient(180deg,var(--panel-2),var(--panel));border-radius:16px;padding:34px 36px;margin-bottom:52px}
.hookbox .lbl{font-family:var(--mono);font-size:10.5px;letter-spacing:.18em;text-transform:uppercase;color:var(--cobalt-ink);margin-bottom:14px}
.hookbox q{font-family:var(--display);font-style:italic;font-size:clamp(22px,3vw,30px);line-height:1.3;color:var(--ink);quotes:none}

.timeline{position:relative;margin:0 0 12px;height:5px;background:rgba(201,210,221,.09);border-radius:3px;overflow:hidden}
.timeline i{position:absolute;top:0;bottom:0;background:var(--cobalt);opacity:.85;border-radius:3px}
.tick{font-family:var(--mono);font-size:10.5px;color:var(--muted);margin-bottom:40px;display:flex;justify-content:space-between}

.beat{display:grid;grid-template-columns:74px 1fr;gap:26px;padding:24px 0;border-top:1px solid rgba(201,210,221,.07)}
.beat .ts{font-family:var(--mono);font-size:12px;color:var(--cobalt-ink);padding-top:3px}
.beat .tx{font-size:16.5px;line-height:1.6;color:var(--ink)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.chip{font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;color:var(--mist);background:rgba(200,212,228,.07);border-radius:20px;padding:4px 11px}
.chip.cited{color:var(--cobalt-ink);background:rgba(59,99,232,.12)}

.cite{background:var(--panel);border-radius:12px;padding:20px 22px;margin-bottom:10px}
.cite .h{display:flex;flex-wrap:wrap;gap:14px;font-family:var(--mono);font-size:11px;color:var(--muted);margin-bottom:10px}
.cite .vid{color:var(--steel)}
.cite q{font-family:var(--display);font-style:italic;font-size:16px;line-height:1.5;color:var(--fog);quotes:"\\201C" "\\201D"}

.gates{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.gate{background:var(--panel);border-radius:10px;padding:14px 16px;font-size:12.5px;color:var(--fog);display:flex;align-items:center;gap:9px}
.dot{width:6px;height:6px;border-radius:50%;background:var(--cobalt);flex:none}
.dot.bad{background:var(--ember)}

.ulist{list-style:none;padding:0;margin:0}
.ulist li{padding:11px 0;border-top:1px solid rgba(201,210,221,.07);color:var(--muted);font-size:14px}

.foot{margin-top:30px;font-family:var(--mono);font-size:11.5px;color:#9BA6B6;line-height:1.9}
.foot .wrap{border-top:1px solid rgba(201,210,221,.09);padding:34px 28px 72px;max-width:1060px}
.foot p{max-width:72ch;margin:12px 0 0;color:#AEB9C8}
.foot b{color:var(--mist);font-weight:500}
.empty{background:var(--panel);border-radius:14px;padding:34px;color:var(--muted);font-size:14px}
"""


@dataclass
class RunView:
    """One run, ready to render."""

    narrative: str
    channel: str
    base: Path
    run: dict = field(default_factory=dict)
    scripts: list[dict] = field(default_factory=list)
    segments: list[dict] = field(default_factory=list)
    gates: dict[str, str] = field(default_factory=dict)


def _json(path: Path, fallback=None):
    """Read JSON, returning the fallback when missing."""
    if not path.exists():
        return fallback if fallback is not None else {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_index(markdown: str) -> tuple[list[dict], dict[str, str]]:
    """Parse index.md into segment rows and per-script gate verdicts."""
    segments: list[dict] = []
    gates: dict[str, str] = {}
    for line in markdown.splitlines():
        row = re.match(r"^- (\S+) \| (\w+) \| brand_fit (\d) \| ([\d.]+)-([\d.]+) \| (.*)$", line)
        if row:
            segments.append(
                {
                    "segment_id": row.group(1),
                    "kind": row.group(2),
                    "fit": int(row.group(3)),
                    "t0": float(row.group(4)),
                    "t1": float(row.group(5)),
                    "quote": row.group(6),
                }
            )
            continue
        gate = re.match(r"^- (\S+): (\w+) \((.*)\)$", line)
        if gate:
            gates[gate.group(1)] = f"{gate.group(2)}: {gate.group(3)}"
    return segments, gates


def collect(output_dir: Path = OUTPUT_DIR) -> list[RunView]:
    """Collect every run under the output directory."""
    views: list[RunView] = []
    if not output_dir.exists():
        return views
    for run_dir in sorted(output_dir.glob("*/*")):
        if not run_dir.is_dir():
            continue
        index_path = run_dir / "index.md"
        segments, gates = (
            parse_index(index_path.read_text(encoding="utf-8")) if index_path.exists() else ([], {})
        )
        scripts = [_json(p) for p in sorted((run_dir / "scripts").glob("*.json"))]
        run = _json(run_dir / "run.json")
        if not scripts and not run:
            continue
        views.append(
            RunView(
                narrative=run_dir.parent.name,
                channel=run_dir.name,
                base=run_dir,
                run=run,
                scripts=scripts,
                segments=segments,
                gates=gates,
            )
        )
    return views


def page(title: str, body: str, depth: int = 0) -> str:
    """Wrap a page body with document head, fonts, and style."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS}" rel="stylesheet">
<style>{STYLE}</style>
</head>
<body>
{body}
</body>
</html>
"""


def header(depth: int = 0) -> str:
    """Site header."""
    root = "../" * depth
    return f"""<div class="top"><div class="wrap">
<a class="brand" href="{root}index.html">Narathor<span>short-script assembly</span></a>
<nav><a href="{root}index.html">Scripts</a><a href="{root}index.html#library">Library</a></nav>
</div></div>"""


def footer(run: dict) -> str:
    """Site footer with the trace."""
    soul = html.escape(str(run.get("soul_version", "-")))
    prompt = html.escape(str(run.get("prompt_version", "-")))
    models = run.get("models") or {}
    writer = html.escape(str(models.get("writer", "-")))
    return f"""<div class="foot"><div class="wrap">
<b>SOUL</b> v{soul} &nbsp;·&nbsp; <b>prompt</b> {prompt} &nbsp;·&nbsp; <b>writer</b> {writer}
<p>Every claim is matched against the source transcript before it is stored. A quote that is not there is rejected, not warned.</p>
</div></div>"""


def render_index(views: list[RunView]) -> str:
    """Front page: scripts, then the segment library."""
    scripts = [(v, s) for v in views for s in v.scripts]
    segments = [(v, seg) for v in views for seg in v.segments]
    run = views[0].run if views else {}
    cards = []
    for view, script in scripts:
        beats = script.get("beats", [])
        claims = sum(1 for beat in beats if beat.get("is_claim"))
        spark = "".join(
            f'<i class="{"on" if beat.get("citation") else ""}" ></i>'
            for beat in beats
        )
        cards.append(
            f"""<a class="card" href="scripts/{html.escape(script['script_id'])}.html">
<div class="body">
<p class="kicker">{html.escape(view.narrative)} &nbsp;/&nbsp; {html.escape(view.channel)}</p>
<h3>{html.escape(script.get('title') or script['script_id'])}</h3>
<p class="hook">&ldquo;{html.escape(script.get('hook', ''))}&rdquo;</p>
<p class="meta"><span><b>{len(beats)}</b> beats</span>
<span><b>{claims}</b> cited</span>
<span>payoff <b>{script.get('payoff_at_s', 0):.0f}s</b></span>
<span>target <b>{script.get('target_duration_s', 0)}s</b></span></p>
</div>
<div><div class="go">Read &rarr;</div><div class="spark">{spark}</div></div>
</a>"""
        )
    rows = []
    for _view, seg in segments:
        rows.append(
            f"""<tr><td class="id">{html.escape(seg["segment_id"])}</td>
<td class="fit fit{seg["fit"]}">{seg["fit"]}</td>
<td class="id">{html.escape(seg["kind"])}</td>
<td class="q">{html.escape(seg["quote"][:150])}</td></tr>"""
        )
    body = f"""{header()}
<div class="wrap">
<div class="hero">
<p class="eyebrow">Compiler, not generator</p>
<h1>Every sentence traces back to <em>the second it was spoken</em>.</h1>
<p class="lede">Narathor indexes the video library of one channel, combines segments from different
videos into a single thesis, writes the full short script, and refuses to store a claim it cannot
trace to the transcript.</p>
<div class="stats">
<div class="stat"><div class="n">{len(scripts)}</div><div class="l">script{"" if len(scripts) == 1 else "s"}</div></div>
<div class="stat"><div class="n">{len(segments)}</div><div class="l">indexed segments</div></div>
<div class="stat"><div class="n">{len(views)}</div><div class="l">run{"" if len(views) == 1 else "s"}</div></div>
<div class="stat"><div class="n">{html.escape(str(run.get("soul_version", "-")))}</div><div class="l">constitution version</div></div>
</div>
</div>

<section>
<h2>Scripts</h2>
<div class="cards">{"".join(cards) if cards else '<div class="empty">No scripts yet.</div>'}</div>
</section>

<section id="library">
<h2>Segment library</h2>
<table class="lib">
<thead><tr><th>Segment</th><th>Fit</th><th>Kind</th><th>Key quote</th></tr></thead>
<tbody>{"".join(rows) if rows else '<tr><td colspan="4" class="q">Nothing indexed yet.</td></tr>'}</tbody>
</table>
</section>
</div>
{footer(run)}"""
    return page("Narathor", body)


def render_script(script: dict, view: RunView) -> str:
    """One script: hook, beats over a timeline, citations, gates, discards."""
    beats = script.get("beats", [])
    total = max([beat.get("at_s", 0) for beat in beats] + [1]) + 3
    bars = []
    step = total / max(len(beats), 1)
    for beat in beats:
        left = (beat.get("at_s", 0) / total) * 100
        width = (step / total) * 100 * 0.82
        bars.append(f'<i style="left:{left:.2f}%;width:{width:.2f}%"></i>')
    beat_html = []
    for beat in beats:
        citation = beat.get("citation")
        chips = []
        if citation:
            chips.append(
                f'<span class="chip cited">{html.escape(citation["video_id"])} '
                f"{citation['t0']:.1f}&ndash;{citation['t1']:.1f}s</span>"
            )
        if beat.get("overlay"):
            chips.append(f'<span class="chip">{html.escape(beat["overlay"])}</span>')
        beat_html.append(
            f"""<div class="beat"><div class="ts">{beat.get("at_s", 0):.1f}s</div>
<div><div class="tx">{html.escape(beat.get("text", ""))}</div>
<div class="chips">{"".join(chips)}</div></div></div>"""
        )
    cites = [
        f"""<div class="cite"><div class="h"><span class="vid">{html.escape(b["citation"]["video_id"])}</span>
<span>{b["citation"]["t0"]:.1f} &ndash; {b["citation"]["t1"]:.1f}s</span>
<span>beat at {b.get("at_s", 0):.1f}s</span></div>
<q>{html.escape(b["citation"]["quote"])}</q></div>"""
        for b in beats
        if b.get("citation")
    ]
    gates = view.gates.get(script["script_id"], "")
    gate_items = "".join(
        f'<div class="gate"><span class="dot{" bad" if "return" in gates or "deny" in gates else ""}"></span>{html.escape(name)}</div>'
        for name in (
            "one thesis",
            "traceable",
            "paid",
            "sounds without sound",
            "no dead air",
            "worth six months from now",
            "distinctive",
        )
    )
    discarded = (
        "".join(f"<li>{html.escape(item)}</li>" for item in script.get("discarded", []))
        or "<li>Nothing discarded.</li>"
    )
    body = f"""{header(1)}
<div class="wrap narrow">
<a class="back" href="../index.html">&larr; All scripts</a>
<h1 class="s-title">{html.escape(script.get("title") or script["script_id"])}</h1>
<div class="s-meta"><span><b>{html.escape(view.narrative)}</b></span>
<span>{html.escape(view.channel)}</span>
<span>{html.escape(script.get("combo_id", ""))}</span>
<span>target <b>{script.get("target_duration_s", 0)}s</b></span>
<span>payoff <b>{script.get("payoff_at_s", 0):.0f}s</b></span></div>

<div class="hookbox"><div class="lbl">Hook</div><q>{html.escape(script.get("hook", ""))}</q></div>

<div class="timeline">{"".join(bars)}</div>
<div class="tick"><span>0s</span><span>{total:.0f}s</span></div>

{"".join(beat_html)}

<section>
<h2>Citations</h2>
{"".join(cites) if cites else '<div class="empty">No factual claims in this script.</div>'}
</section>

<section>
<h2>Gates</h2>
<div class="gates">{gate_items}</div>
</section>

<section>
<h2>Thesis</h2>
<p class="lede">{html.escape(script.get("single_minded_proposition", ""))}</p>
</section>

<section>
<h2>Not used</h2>
<ul class="ulist">{discarded}</ul>
</section>
</div>
{footer(view.run)}"""
    return page(script.get("title") or script["script_id"], body)


def build(output_dir: Path = OUTPUT_DIR, site_dir: Path = SITE_DIR) -> int:
    """Build the whole site. Returns the number of scripts rendered."""
    views = collect(output_dir)
    if site_dir.exists():
        shutil.rmtree(site_dir)
    (site_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text(render_index(views), encoding="utf-8")
    count = 0
    for view in views:
        for script in view.scripts:
            (site_dir / "scripts" / f"{script['script_id']}.html").write_text(
                render_script(script, view), encoding="utf-8"
            )
            count += 1
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")
    return count


if __name__ == "__main__":
    print(f"{build()} scripts rendered to {SITE_DIR}")
