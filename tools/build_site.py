"""Build the static site from run artefacts. No extra dependencies.

GitHub Pages only serves files, so everything is rendered here and nothing runs
in the browser. The visual language is a monochrome terminal: one typeface,
black on white, box rules, timecodes. See docs/BRAND.md, section "Static
viewer", which records this surface as a deliberate exception to the product
palette.
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

FONTS = "https://fonts.googleapis.com/css2?family=Courier+Prime:ital,wght@0,400;0,700;1,400;1,700&display=swap"

GATES = (
    "one thesis",
    "traceable",
    "paid",
    "sounds without sound",
    "no dead air",
    "worth six months from now",
    "distinctive",
)

STYLE = """
:root{
--bg:#000000; --ink:#ffffff; --dim:#ababab; --dim2:#dcdcdc;
--rule:#333333; --rule2:#575757;
--mono:"Courier Prime","Courier New",Courier,monospace;
}
*{box-sizing:border-box}
html{-webkit-font-smoothing:antialiased;background:var(--bg)}
body{
margin:0;background:var(--bg);color:var(--ink);
font:15px/1.75 var(--mono);letter-spacing:.005em;
}
body::after{
content:"";position:fixed;inset:0;pointer-events:none;z-index:99;
background:
repeating-linear-gradient(180deg,rgba(255,255,255,.04) 0 1px,transparent 1px 3px),
radial-gradient(ellipse at 50% 45%,transparent 62%,rgba(0,0,0,.5) 100%);
}
a{color:inherit;text-decoration:none}
::selection{background:#fff;color:#000}
.wrap{max-width:940px;margin:0 auto;padding:0 24px}
.wrap.wide{max-width:1120px}

/* masthead */
.mast{padding:26px 0 0;font-size:12px;color:var(--dim)}
.mast .row{display:flex;justify-content:space-between;gap:16px;align-items:baseline;flex-wrap:wrap}
.mast .name{color:var(--ink);letter-spacing:.42em;text-transform:uppercase;font-weight:700}
.mast .tag{letter-spacing:.2em;text-transform:uppercase}
.mast nav a{letter-spacing:.16em;text-transform:uppercase;color:var(--dim);margin-left:20px}
.mast nav a:hover{color:var(--ink)}
.hr{border-top:1px solid var(--rule);margin:14px 0 0}

/* terminal block */
.term{padding:44px 0 10px}
.line{display:flex;gap:10px;font-size:13.5px;color:var(--dim2);padding:2px 0}
.line .sig{color:var(--ink);flex:none}
.line .cmd{color:var(--ink)}
.cursor{display:inline-block;width:8px;height:15px;background:var(--ink);vertical-align:-2px;animation:b 1.1s steps(1) infinite}
@keyframes b{0%,49%{opacity:1}50%,100%{opacity:0}}
@media (prefers-reduced-motion:reduce){.cursor{animation:none}}

h1{
font-size:clamp(26px,4.4vw,42px);line-height:1.14;font-weight:700;
letter-spacing:-.015em;text-transform:uppercase;margin:34px 0 20px;
}
h1 u{text-decoration:none;border-bottom:3px solid var(--ink);padding-bottom:2px}

/* ledger */
.ledger{margin:34px 0 8px;font-size:12.5px;letter-spacing:.08em}
.ledger .l{display:flex;align-items:baseline;gap:8px;padding:6px 0;text-transform:uppercase;color:var(--dim)}
.ledger .dots{flex:1;border-bottom:1px dotted var(--rule2);transform:translateY(-3px)}
.ledger .v{color:var(--ink);font-weight:700}

/* section heading */
.sec{padding:46px 0 0}
.sec-h{display:flex;align-items:center;gap:12px;font-size:11.5px;letter-spacing:.24em;text-transform:uppercase;color:var(--ink);margin:0 0 22px}
.sec-h::before{content:"";height:1px;flex:1;background:var(--rule);order:-1}
.sec-h span{order:0}
.sec-h span::before{content:"\\25A0";font-size:9px;vertical-align:2px;margin-right:10px;color:var(--dim2)}
.sec-h em{color:var(--dim);font-style:normal;letter-spacing:.12em;order:1}

/* script entries */
.entry{border:1px solid var(--rule);margin-bottom:14px;transition:border-color .15s,background .15s}
.entry:hover{border-color:var(--rule2);background:#070707}
.entry a{display:grid;grid-template-columns:1fr auto;gap:0;align-items:stretch}
.entry .main{padding:22px 24px}
.entry .kicker{font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--dim);margin:0 0 12px}
.entry h3{font-size:24px;line-height:1.25;font-weight:700;margin:0 0 12px;letter-spacing:-.01em}
.entry .hook{margin:0 0 16px;color:var(--dim2);font-style:italic;font-size:14.5px}
.entry .hook::before{content:"\\201C"}
.entry .hook::after{content:"\\201D"}
.entry .meta{display:flex;flex-wrap:wrap;gap:6px 20px;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim)}
.entry .meta b{color:var(--ink);font-weight:700}
.entry .side{border-left:1px solid var(--rule);padding:22px 20px;display:flex;flex-direction:column;justify-content:flex-start;align-items:flex-end;min-width:150px;gap:10px}
.entry .tc{font-size:12px;letter-spacing:.12em;color:var(--dim2)}
.entry .tc2{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);text-align:right;line-height:1.7}
.entry .open{font-size:12px;letter-spacing:.18em;text-transform:uppercase;font-weight:700;white-space:nowrap;margin-top:auto}
.entry:hover .open{background:var(--ink);color:#000}
.bmap{display:flex;align-items:center;gap:10px;margin-top:14px;padding-top:12px;border-top:1px dotted var(--rule)}
.bmap .cells{font-size:15px;line-height:1;letter-spacing:.22em;color:var(--ink)}
.bmap .cap{font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--dim)}
.legend{font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);margin-top:14px}
.legend b{font-weight:400;color:var(--dim2);letter-spacing:.2em}

/* table */
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-size:10.5px;letter-spacing:.18em;text-transform:uppercase;color:var(--dim);font-weight:400;padding:0 14px 10px 0;border-bottom:1px solid var(--rule)}
td{padding:11px 14px 11px 0;border-bottom:1px dotted var(--rule);vertical-align:top;color:var(--dim2)}
td.id{white-space:nowrap;color:var(--ink);font-size:12px;letter-spacing:.04em}
td.fit{white-space:nowrap;letter-spacing:.08em;width:70px}
td.kind{white-space:nowrap;font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--dim)}
th.len{text-align:right;white-space:nowrap}
td.len{text-align:right;white-space:nowrap;color:var(--dim);font-size:12px;letter-spacing:.04em}
tr:last-child td{border-bottom:none}

/* article */
.back{display:inline-block;font-size:11.5px;letter-spacing:.18em;text-transform:uppercase;color:var(--dim);margin:34px 0 30px}
.back:hover{color:var(--ink)}
.s-title{font-size:clamp(27px,4.2vw,40px);line-height:1.08;font-weight:700;letter-spacing:-.015em;margin:0 0 18px}
.s-meta{display:flex;flex-wrap:wrap;gap:6px 22px;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);margin-bottom:34px;padding-bottom:22px;border-bottom:1px solid var(--rule)}
.s-meta b{color:var(--ink);font-weight:700}

.hookbox{border-left:3px solid var(--ink);padding:2px 0 2px 20px;margin:0 0 48px}
.hookbox .lbl{font-size:10.5px;letter-spacing:.24em;text-transform:uppercase;color:var(--dim);margin-bottom:10px}
.hookbox .q{font-size:clamp(19px,2.6vw,25px);line-height:1.4;font-style:italic}
.hookbox .q::before{content:"\\201C"}
.hookbox .q::after{content:"\\201D"}

.ruler{position:relative;height:26px;border-bottom:1px solid var(--rule2)}
.ruler i{position:absolute;bottom:0;height:18px;background:var(--ink)}
.ruler i.off{background:transparent;border:1px solid var(--rule2);border-bottom:none}
.ticks{display:flex;justify-content:space-between;font-size:10.5px;letter-spacing:.12em;color:var(--dim);margin:8px 0 40px}

.meter{display:inline-flex;gap:4px;vertical-align:middle}
.meter i{display:block;width:9px;height:9px;border:1px solid #787878}
.meter i.on{background:var(--ink);border-color:var(--ink)}

.beat{display:grid;grid-template-columns:82px 1fr;gap:22px;padding:20px 0;border-top:1px solid var(--rule)}
.beat:first-of-type{border-top:1px solid var(--rule2)}
.beat .ts{font-size:12px;color:var(--dim);letter-spacing:.06em;padding-top:2px}
.beat .tx{font-size:15.5px;line-height:1.7}
.chips{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:10px;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--dim)}
.chip::before{content:"["}
.chip::after{content:"]"}
.chip.cited{color:var(--ink)}

.cite{border-top:1px dotted var(--rule);padding:14px 0 14px 0}
.cite .h{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--dim);margin-bottom:8px;display:flex;flex-wrap:wrap;gap:16px}
.cite .h .vid{color:var(--ink)}
.cite .q{display:block;font-style:italic;color:var(--dim2);font-size:14.5px;line-height:1.65;border-left:1px solid var(--rule2);padding-left:14px}
.cite .q::before{content:"\\201C"}
.cite .q::after{content:"\\201D"}

.gates{font-size:13px;letter-spacing:.08em}
.gates .g{display:flex;gap:12px;padding:8px 0;border-bottom:1px dotted var(--rule);color:var(--dim2);text-transform:uppercase;font-size:11.5px;letter-spacing:.14em}
.gates .g i{font-style:normal;color:var(--ink);flex:none}
.gates .g i.bad{color:var(--dim)}
.gates .g i.bad::after{content:" /"}

.ulist{list-style:none;padding:0;margin:0;font-size:14px;color:var(--dim2)}
.ulist li{padding:9px 0 9px 18px;border-bottom:1px dotted var(--rule);position:relative}
.ulist li::before{content:"-";position:absolute;left:0;color:var(--dim)}

.body-text{font-size:15px;line-height:1.75;color:var(--dim2);margin:0}

/* footer */
.foot{margin-top:60px;padding:0 0 90px}
.foot .in{border-top:1px solid var(--rule);padding-top:20px;font-size:11.5px;letter-spacing:.1em;color:var(--dim);line-height:1.9}
.foot .eof{color:var(--ink);letter-spacing:.4em;margin-bottom:14px}
.foot .fin{display:grid;grid-template-columns:1fr 280px;gap:40px;align-items:start}
.foot .disc{margin:0;max-width:56ch;line-height:1.8}
.foot .telem{margin:0;text-align:right;line-height:2;text-transform:uppercase;font-size:11px;letter-spacing:.14em}
.foot .telem b{color:var(--dim2);font-weight:400}
@media(max-width:640px){.foot .fin{grid-template-columns:1fr;gap:16px}.foot .telem{text-align:left}}
.empty{border:1px dashed var(--rule2);padding:26px;font-size:13px;color:var(--dim);letter-spacing:.06em}

/* fixture warning */
.warn{border:1px solid var(--ink);padding:14px 18px;margin:26px 0 0;font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;display:flex;gap:14px;align-items:baseline;flex-wrap:wrap}
.warn b{font-weight:700}
.warn span{color:var(--dim);letter-spacing:.1em}

@media(max-width:640px){
.entry a{grid-template-columns:1fr}
.entry .side{border-left:none;border-top:1px solid var(--rule);flex-direction:row;align-items:center;justify-content:space-between;min-width:0;padding:14px 22px}
.beat{grid-template-columns:1fr;gap:4px}
.ledger{font-size:11.5px}
}
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

    @property
    def is_fixture(self) -> bool:
        """True when this run was built on synthetic transcripts, not a real channel."""
        return bool(self.run.get("fixture"))


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


def timecode(seconds: float) -> str:
    """Format seconds as HH:MM:SS, the way a playback deck would show it."""
    total = round(seconds)
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def meter(beats: list[dict]) -> str:
    """One square per beat, filled when the beat carries a citation."""
    cells = "".join('<i class="on"></i>' if b.get("citation") else "<i></i>" for b in beats)
    return f'<span class="meter">{cells}</span>'


def fitmeter(fit: int) -> str:
    """Five-step brand-fit meter, left filled."""
    cells = "".join('<i class="on"></i>' if i < fit else "<i></i>" for i in range(5))
    return f'<span class="meter">{cells}</span>'


def ruler(beats: list[dict], total: float) -> str:
    """Timeline segments, one per beat, solid when cited."""
    if total <= 0:
        return ""
    marks = []
    for index, beat in enumerate(beats):
        start = beat.get("at_s", 0)
        end = beats[index + 1].get("at_s", total) if index + 1 < len(beats) else total
        left = (start / total) * 100
        width = max(((end - start) / total) * 100, 0.7)
        cls = "" if beat.get("citation") else ' class="off"'
        marks.append(f'<i{cls} style="left:{left:.3f}%;width:calc({width:.3f}% - 2px)"></i>')
    return "".join(marks)


def page(title: str, body: str) -> str:
    """Wrap a page body with document head, fonts, and style."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="Narathor — short-script assembly with every claim traced to the second it was spoken.">
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


def header(depth: int = 0, current: str = "") -> str:
    """Masthead, styled as a terminal title bar."""
    root = "../" * depth
    return f"""<div class="mast"><div class="wrap wide">
<div class="row">
<span class="name">Narathor</span>
<span class="tag">Short-script assembly</span>
<nav><a href="{root}index.html">Index</a><a href="{root}index.html#library">Library</a></nav>
</div>
<div class="hr"></div>
</div></div>"""


def warn_banner(fixture: bool) -> str:
    """Loud notice when the page shows fixture data instead of a real run."""
    if not fixture:
        return ""
    return """<div class="warn"><b>Demo data</b><span>synthetic transcripts shipped with the repo. no channel was ingested, no brief was written by the owner.</span></div>"""


def footer(run: dict) -> str:
    """Colophon and the trace."""
    soul = html.escape(str(run.get("soul_version", "-")))
    prompt = html.escape(str(run.get("prompt_version", "-")))
    models = run.get("models") or {}
    writer_raw = str(models.get("writer", "-"))
    writer = html.escape(writer_raw.rsplit("/", 1)[-1])
    return f"""<div class="foot"><div class="wrap">
<div class="in">
<div class="eof">EOF</div>
<div class="fin">
<p class="disc">Every claim is matched against the source transcript before it is stored. A quote that is not there is rejected, not warned.</p>
<p class="telem"><b>soul</b> v{soul}<br><b>prompt</b> {prompt}<br><b>writer</b> {writer}</p>
</div>
</div></div></div>"""


def render_index(views: list[RunView]) -> str:
    """Front page: session opener, ledger, scripts, segment library."""
    scripts = [(v, s) for v in views for s in v.scripts]
    segments = [(v, seg) for v in views for seg in v.segments]
    run = views[0].run if views else {}
    channel = views[0].channel if views else "-"

    fixture = any(view.is_fixture for view in views)

    entries = []
    for view, script in scripts:
        beats = script.get("beats", [])
        claims = sum(1 for beat in beats if beat.get("is_claim"))
        total = max([beat.get("at_s", 0) for beat in beats] + [script.get("target_duration_s", 1)])
        bar = meter(beats)
        entries.append(
            f"""<article class="entry"><a href="scripts/{html.escape(script["script_id"])}.html">
<div class="main">
<p class="kicker">{html.escape(view.narrative)} / {html.escape(view.channel)} / {html.escape(script.get("combo_id", ""))}</p>
<h3>{html.escape(script.get("title") or script["script_id"])}</h3>
<p class="hook">{html.escape(script.get("hook", ""))}</p>
<p class="meta"><span>beats <b>{len(beats)}</b></span>
<span>cited <b>{claims}</b></span>
<span>payoff <b>{script.get("payoff_at_s", 0):.0f}s</b></span>
<span>target <b>{script.get("target_duration_s", 0)}s</b></span></p>
<div class="bmap"><span class="cells">{bar}</span><span class="cap">beat map &middot; solid = cited</span></div>
</div>
<div class="side">
<span class="tc">{timecode(total)}</span>
<span class="tc2">{len(beats)} beats<br>{claims} cited</span>
<span class="open">read &rarr;</span>
</div>
</a></article>"""
        )

    rows = []
    for _view, seg in segments:
        rows.append(
            f"""<tr><td class="id">{html.escape(seg["segment_id"])}</td>
<td class="fit">{fitmeter(seg["fit"])}</td>
<td class="kind">{html.escape(seg["kind"])}</td>
<td>{html.escape(seg["quote"][:160])}</td>
<td class="len">{seg["t1"] - seg["t0"]:.0f}s</td></tr>"""
        )

    body = f"""{header()}
<div class="wrap">

<div class="term">
<div class="line"><span class="sig">$</span><span class="cmd">narathor report --channel {html.escape(channel)}</span></div>
<div class="line"><span class="sig">&gt;</span><span>{len(segments)} segments indexed from the library</span></div>
<div class="line"><span class="sig">&gt;</span><span>{len(scripts)} script assembled, {sum(sum(1 for b in s.get("beats", []) if b.get("citation")) for _v, s in scripts)} claims traced to transcript</span></div>
<div class="line"><span class="sig">&gt;</span><span>last gate: {html.escape(str(run.get("status", "unknown")))}<span class="cursor"></span></span></div>
</div>

{warn_banner(fixture)}

<h1>Every sentence<br>traces back to<br>the second <u>it was spoken</u></h1>

<div class="ledger">
<div class="l"><span>scripts</span><span class="dots"></span><span class="v">{len(scripts)}</span></div>
<div class="l"><span>indexed segments</span><span class="dots"></span><span class="v">{len(segments)}</span></div>
<div class="l"><span>runs</span><span class="dots"></span><span class="v">{len(views)}</span></div>
<div class="l"><span>constitution</span><span class="dots"></span><span class="v">v{html.escape(str(run.get("soul_version", "-")))}</span></div>
</div>

<div class="sec">
<div class="sec-h"><span>Scripts</span><em>{len(scripts):02d}</em></div>
{"".join(entries) if entries else '<div class="empty">-- no scripts assembled --</div>'}
</div>

<div class="sec" id="library">
<div class="sec-h"><span>Segment library</span><em>{len(segments):02d}</em></div>
<table>
<thead><tr><th>Segment</th><th>Fit</th><th>Kind</th><th>Key quote</th><th class="len">Len</th></tr></thead>
<tbody>{"".join(rows) if rows else '<tr><td colspan="5">-- nothing indexed --</td></tr>'}</tbody>
</table>
<p class="legend">fit scale &nbsp; {fitmeter(5)} strong &nbsp; {fitmeter(1)} weak &nbsp; / five steps, left-filled</p>
</div>

</div>
{footer(run)}"""
    return page("Narathor", body)


def render_script(script: dict, view: RunView) -> str:
    """One script: hook, beats over a ruler, citations, gates, discards."""
    beats = script.get("beats", [])
    total = max(
        [beat.get("at_s", 0) for beat in beats] + [float(script.get("target_duration_s", 1))]
    )
    ruler_bar = ruler(beats, total)

    beat_html = []
    for beat in beats:
        citation = beat.get("citation")
        chips = []
        if citation:
            chips.append(
                f'<span class="chip cited">{html.escape(citation["video_id"])} '
                f"{citation['t0']:.1f}-{citation['t1']:.1f}s</span>"
            )
        if beat.get("overlay"):
            chips.append(f'<span class="chip">{html.escape(beat["overlay"])}</span>')
        beat_html.append(
            f"""<div class="beat"><div class="ts">{timecode(beat.get("at_s", 0))}</div>
<div><div class="tx">{html.escape(beat.get("text", ""))}</div>
<div class="chips">{"".join(chips)}</div></div></div>"""
        )

    cites = [
        f"""<div class="cite"><div class="h"><span class="vid">{html.escape(b["citation"]["video_id"])}</span>
<span>{b["citation"]["t0"]:.1f} - {b["citation"]["t1"]:.1f}s</span>
<span>beat at {timecode(b.get("at_s", 0))}</span></div>
<span class="q">{html.escape(b["citation"]["quote"])}</span></div>"""
        for b in beats
        if b.get("citation")
    ]

    verdict = view.gates.get(script["script_id"], "")
    failed = "deny" in verdict or "return" in verdict or "fail" in verdict
    gate_items = "".join(
        f'<div class="g"><i class="{"bad" if failed else ""}">{"FAIL" if failed else "OK"}</i><span>{html.escape(name)}</span></div>'
        for name in GATES
    )

    discarded = (
        "".join(f"<li>{html.escape(item)}</li>" for item in script.get("discarded", []))
        or "<li>nothing discarded</li>"
    )

    body = f"""{header(1)}
<div class="wrap">
<a class="back" href="../index.html">&larr; index</a>
<h1 class="s-title">{html.escape(script.get("title") or script["script_id"])}</h1>
<div class="s-meta">
<span><b>{html.escape(view.narrative)}</b></span>
<span>{html.escape(view.channel)}</span>
<span>{html.escape(script.get("combo_id", ""))}</span>
<span>target <b>{script.get("target_duration_s", 0)}s</b></span>
<span>payoff <b>{script.get("payoff_at_s", 0):.0f}s</b></span>
<span>{html.escape(script["script_id"])}</span>
</div>

{warn_banner(view.is_fixture)}

<div class="hookbox"><div class="lbl">Hook</div><span class="q">{html.escape(script.get("hook", ""))}</span></div>

<div class="ruler">{ruler_bar}</div>
<div class="ticks"><span>00:00:00</span><span>{timecode(total)}</span></div>

{"".join(beat_html)}

<div class="sec">
<div class="sec-h"><span>Citations</span><em>{len(cites):02d}</em></div>
{"".join(cites) if cites else '<div class="empty">-- no factual claims in this script --</div>'}
</div>

<div class="sec">
<div class="sec-h"><span>Critic gates</span><em>{script["script_id"]}</em></div>
<div class="gates">{gate_items}</div>
</div>

<div class="sec">
<div class="sec-h"><span>Thesis</span><em>single-minded</em></div>
<p class="body-text">{html.escape(script.get("single_minded_proposition", ""))}</p>
</div>

<div class="sec">
<div class="sec-h"><span>Not used</span><em>{len(script.get("discarded", [])):02d}</em></div>
<ul class="ulist">{discarded}</ul>
</div>

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
