"""Bangun situs statis dari artefak run. Tanpa dependensi tambahan.

Dipakai untuk GitHub Pages: Pages hanya menyajikan berkas, jadi seluruh isi
dirender di sini dan tidak ada proses yang berjalan di browser.
"""

from __future__ import annotations

import html
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
SITE_DIR = ROOT / "site"

STYLE = """
:root{--bg:#0b0b0d;--panel:#14141a;--line:#2b2b35;--ink:#f2efe9;--muted:#a39d94;--accent:#c9a227}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:48px 20px 80px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
h1{font-size:26px;line-height:1.25;margin:0 0 6px;letter-spacing:-.01em}
h2{font-size:15px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin:36px 0 12px;font-weight:600}
.sub{color:var(--muted);font-size:14px;margin:0 0 28px}
.card{display:block;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:0 0 12px;transition:border-color .15s}
.card:hover{border-color:#3a3a46;text-decoration:none}
.card .t{color:var(--ink);font-weight:600;font-size:16px;margin:0 0 4px}
.card .m{color:var(--muted);font-size:13px}
.hook{font-size:20px;line-height:1.4;margin:0 0 28px;padding:18px 20px;border-left:2px solid var(--accent);background:var(--panel)}
.beat{display:grid;grid-template-columns:58px 1fr;gap:14px;padding:12px 0;border-bottom:1px solid var(--line)}
.beat:last-child{border-bottom:0}
.beat .ts{color:var(--accent);font-variant-numeric:tabular-nums;font-size:13px;padding-top:2px}
.beat .tx{white-space:pre-wrap}
.ov{display:inline-block;margin-top:6px;font-size:12px;color:var(--muted);border:1px solid var(--line);border-radius:5px;padding:2px 7px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--muted);font-weight:600;border-bottom:1px solid var(--line);padding:8px 10px 8px 0}
td{border-bottom:1px solid var(--line);padding:9px 10px 9px 0;vertical-align:top}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;color:#d9d4c9}
.q{color:#cfc9bd}
ul{padding-left:18px;color:var(--muted)}
li{margin:4px 0}
.foot{margin-top:56px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}
"""


@dataclass
class RunView:
    """Satu run yang siap dirender."""

    narrative: str
    channel: str
    base: Path
    summary: dict
    run: dict
    scripts: list[dict]


def _read_json(path: Path, fallback: dict | None = None) -> dict:
    """Baca JSON, kembalikan fallback bila tidak ada."""
    if not path.exists():
        return fallback or {}
    return json.loads(path.read_text(encoding="utf-8"))


def collect(output_dir: Path) -> list[RunView]:
    """Kumpulkan seluruh run dari direktori output."""
    views: list[RunView] = []
    if not output_dir.exists():
        return views
    for run_dir in sorted(output_dir.glob("*/*")):
        if not run_dir.is_dir():
            continue
        summary = _read_json(run_dir / "summary.json")
        run = _read_json(run_dir / "run.json")
        scripts = []
        for path in sorted((run_dir / "scripts").glob("*.json")):
            scripts.append(_read_json(path))
        if not scripts and not run:
            continue
        views.append(
            RunView(
                narrative=run_dir.parent.name,
                channel=run_dir.name,
                base=run_dir,
                summary=summary,
                run=run,
                scripts=scripts,
            )
        )
    return views


def _page(title: str, body: str, depth: int = 0) -> str:
    """Bungkus isi halaman. depth dipakai bila nanti ada subfolder."""
    _ = depth

    """Bungkus isi halaman dengan gaya dan header."""
    return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">
{body}
<div class="foot">Narathor. Naskah dengan sitasi per detik. Dibangun dari <code>SOUL.md</code> v{1}.</div>
</div>
</body>
</html>
"""


def render_index(views: list[RunView]) -> str:
    """Halaman daftar naskah."""
    cards: list[str] = []
    total = 0
    for view in views:
        for script in view.scripts:
            total += 1
            beats = len(script.get("beats", []))
            claims = sum(1 for beat in script.get("beats", []) if beat.get("is_claim"))
            cards.append(
                f"""<a class="card" href="scripts/{html.escape(script["script_id"])}.html">
<p class="t">{html.escape(script.get("title") or script["script_id"])}</p>
<p class="m">{html.escape(view.narrative)} / {html.escape(view.channel)} &middot;
{beats} beat &middot; {claims} klaim bersitasi &middot; payoff {script.get("payoff_at_s", 0):.0f}s</p>
</a>"""
            )
    body = f"""<h1>Narathor</h1>
<p class="sub">{total} naskah dari {len(views)} run. Setiap klaim terlacak ke detik sumbernya.</p>
<h2>Naskah</h2>
{"".join(cards) if cards else '<p class="sub">Belum ada naskah.</p>'}
<h2>Run</h2>
{"".join(f'<p class="sub">{html.escape(v.narrative)} &middot; {html.escape(v.channel)} &middot; soul v{v.run.get("soul_version", "-")} &middot; {v.run.get("status", "-")}</p>' for v in views)}"""
    return _page("Narathor", body)


def render_script(script: dict, view: RunView) -> str:
    """Halaman satu naskah beserta seluruh sitasinya."""
    beats: list[str] = []
    for beat in script.get("beats", []):
        citation = beat.get("citation")
        mark = ' <span class="ov">klaim bersitasi</span>' if citation else ""
        overlay = (
            f'<div class="ov">{html.escape(beat["overlay"])}</div>' if beat.get("overlay") else ""
        )
        beats.append(
            f"""<div class="beat"><div class="ts">{beat.get("at_s", 0):.1f}s</div>
<div class="tx">{html.escape(beat.get("text", ""))}{mark}{overlay}</div></div>"""
        )
    rows: list[str] = []
    for beat in script.get("beats", []):
        citation = beat.get("citation")
        if not citation:
            continue
        rows.append(
            f"""<tr><td><code>{html.escape(citation["video_id"])}</code></td>
<td>{citation["t0"]:.1f}&ndash;{citation["t1"]:.1f}s</td>
<td class="q">&ldquo;{html.escape(citation["quote"])}&rdquo;</td></tr>"""
        )
    discarded = script.get("discarded") or []
    body = f"""<p class="sub"><a href="../index.html">&larr; semua naskah</a></p>
<h1>{html.escape(script.get("title") or script["script_id"])}</h1>
<p class="sub">{html.escape(view.narrative)} / {html.escape(view.channel)} &middot;
durasi target {script.get("target_duration_s", 0)}s &middot;
payoff {script.get("payoff_at_s", 0):.0f}s &middot; {html.escape(script.get("combo_id", ""))}</p>
<div class="hook">{html.escape(script.get("hook", ""))}</div>
<h2>Naskah</h2>
{"".join(beats)}
<h2>Sitasi</h2>
<table><thead><tr><th>Video</th><th>Rentang</th><th>Kutipan sumber</th></tr></thead>
<tbody>{"".join(rows) or '<tr><td colspan="3">Tidak ada klaim faktual.</td></tr>'}</tbody></table>
<h2>Tesis</h2>
<p>{html.escape(script.get("single_minded_proposition", ""))}</p>
<h2>Yang tidak dipakai</h2>
<ul>{"".join(f"<li>{html.escape(item)}</li>" for item in discarded) or "<li>Tidak ada</li>"}</ul>
<p class="sub">soul v{view.run.get("soul_version", "-")} &middot; prompt {html.escape(view.run.get("prompt_version", "-"))} &middot; brief {html.escape(view.run.get("brief_id", "-"))}</p>"""
    return _page(script.get("title") or script["script_id"], body, depth=1)


def build(output_dir: Path = OUTPUT_DIR, site_dir: Path = SITE_DIR) -> int:
    """Bangun seluruh situs. Kembalikan jumlah naskah yang dirender."""
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
    rendered = build()
    print(f"{rendered} naskah dirender ke {SITE_DIR}")
