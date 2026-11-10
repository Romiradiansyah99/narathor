"""Write the public page: the name, one line, nothing else.

The console writes; this page only stands there. It used to publish demo scripts built
from the synthetic transcripts in `data/`, which read as a result nobody had asked for.
Until a real run has something worth showing, the page holds the name and the line.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

TAGLINE = "attention is all you need"

PAGE = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Narathor</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Courier+Prime:ital,wght@0,400;0,700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#000;--ink:#fff;--dim:#8d8d8d;--rule:#262626;
--mono:"Courier Prime","Courier New",Courier,monospace}}
*{{box-sizing:border-box}}
html,body{{height:100%}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 var(--mono);
-webkit-font-smoothing:antialiased}}
.wrap{{display:flex;flex-direction:column;min-height:100dvh;max-width:760px;margin:0 auto;
padding:14px 18px calc(18px + env(safe-area-inset-bottom))}}
header{{font-size:11px;letter-spacing:.32em;text-transform:uppercase;color:var(--dim)}}
main{{flex:1;display:flex;align-items:center}}
p{{margin:0;font-size:clamp(17px,4.4vw,22px)}}
footer{{border-top:1px solid var(--rule);padding-top:12px;font-size:12px;color:#5f5f5f}}
</style>
</head>
<body>
<div class="wrap">
<header>narathor</header>
<main><p>{TAGLINE}</p></main>
<footer>the console that writes runs on a server, not here.</footer>
</div>
</body>
</html>
"""


def main() -> None:
    """Write `site/index.html` and clear whatever the old viewer left behind."""
    SITE.mkdir(parents=True, exist_ok=True)
    for stale in SITE.iterdir():
        if stale.is_dir():
            for child in sorted(stale.rglob("*"), reverse=True):
                child.unlink() if child.is_file() else child.rmdir()
            stale.rmdir()
        else:
            stale.unlink()
    (SITE / "index.html").write_text(PAGE, encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote {SITE / 'index.html'}")


if __name__ == "__main__":
    main()
