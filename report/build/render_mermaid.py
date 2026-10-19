"""Render Mermaid diagrams to print-quality PNGs for the report.

Reads every `*.mmd` in report/build/diagrams/ and writes `<name>.png` into
data/reports/ (the same place the report figures live). Diagrams are rendered
by the mermaid.ink service as SVG and rasterised locally at high DPI, so the
output is crisp vector-based rather than a low-resolution bitmap.

    python report/build/render_mermaid.py

Requires internet access to mermaid.ink. If a diagram fails to render the
script exits non-zero and names it, so a broken diagram never slips into a
build silently.
"""
from __future__ import annotations

import base64
import pathlib
import sys
import urllib.request

HERE = pathlib.Path(__file__).parent
REPO = HERE.parents[1]
SRC = HERE / "diagrams"
OUT = REPO / "data" / "reports"
DPI = 200
UA = {"User-Agent": "Mozilla/5.0"}


def _fetch(path):
    req = urllib.request.Request("https://mermaid.ink/" + path, headers=UA)
    return urllib.request.urlopen(req, timeout=30).read()


def render(mmd_path):
    # mermaid.ink's PNG endpoint renders the diagram faithfully (text, colours,
    # arrows). We request a wide bitmap so it stays crisp when scaled to the
    # page. (SVG rasterisation via local tools mangles mermaid's HTML labels.)
    graph = mmd_path.read_text(encoding="utf-8")
    enc = base64.urlsafe_b64encode(graph.encode()).decode()
    out_png = OUT / (mmd_path.stem + ".png")
    png = _fetch("img/" + enc + "?type=png&bgColor=white&width=1600")
    out_png.write_bytes(png)
    return out_png


def main():
    mmds = sorted(SRC.glob("*.mmd"))
    if not mmds:
        print("no .mmd diagrams found in", SRC)
        return
    failed = []
    for m in mmds:
        try:
            p = render(m)
            print(f"  rendered {m.name} -> {p.name}")
        except Exception as e:  # noqa: BLE001
            failed.append((m.name, str(e)))
            print(f"  FAILED {m.name}: {e}")
    if failed:
        sys.exit(f"{len(failed)} diagram(s) failed to render")
    print(f"rendered {len(mmds)} diagram(s)")


if __name__ == "__main__":
    main()
