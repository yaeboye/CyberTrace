"""Verify the generated report against every rule we care about.

Run:  python report/build/verify.py
Exit code 0 = all checks pass, 1 = at least one failure.

Checks:
  1. page count within [60, 100]
  2. no blank/near-empty pages
  3. all body text is black (no stray coloured runs)
  4. no leftover template placeholders
  5. every figure caption appears in the List of Figures (and vice-versa)
  6. every table caption appears in the List of Tables (and vice-versa)
  7. figure and table numbers are sequential within each chapter
"""
from __future__ import annotations

import html
import pathlib
import re
import sys
import tempfile

REPO = pathlib.Path(r"C:\Users\satvi\CyberTrace")
DOCX = REPO / "report" / "CyberTrace_Project_Report_Satvik.docx"
GEN = REPO / "report" / "build" / "gen_report.py"

PLACEHOLDERS = ["[GUIDE NAME]", "[Designation]", "[TEAMMATE NAME]", "[Teammate Name]",
                "TODO", "TBD", "XXX", "____"]  # ____ = 4+ underscores (unfilled blank)

PAGE_MIN, PAGE_MAX = 60, 100

_fails: list[str] = []
_passes: list[str] = []


def ok(msg):
    _passes.append(msg)


def fail(msg):
    _fails.append(msg)


def _doc_text(docx):
    import zipfile
    raw = zipfile.ZipFile(docx).read("word/document.xml").decode("utf-8", "ignore")
    return html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"</w:p>", "\n", raw)))


def check_pages_and_empties(docx):
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import _word
    import fitz
    pdf_path = pathlib.Path(tempfile.gettempdir()) / "_ct_verify.pdf"
    pages = _word.export_pdf(str(docx), str(pdf_path))
    if PAGE_MIN <= pages <= PAGE_MAX:
        ok(f"page count {pages} within [{PAGE_MIN}, {PAGE_MAX}]")
    else:
        fail(f"page count {pages} OUTSIDE [{PAGE_MIN}, {PAGE_MAX}]")
    pdf = fitz.open(str(pdf_path))
    empties = [i + 1 for i in range(pdf.page_count)
               if len(pdf[i].get_text().strip()) < 5]
    pdf.close()
    try:
        pdf_path.unlink()
    except OSError:
        pass
    if empties:
        fail(f"blank pages: {empties}")
    else:
        ok("no blank pages")


def check_black_text(docx):
    from docx import Document
    doc = Document(str(docx))
    bad = []
    for p in doc.paragraphs:
        for r in p.runs:
            c = r.font.color
            if c is not None and c.rgb is not None and str(c.rgb) != "000000":
                bad.append((str(c.rgb), r.text[:30]))
    if bad:
        fail(f"{len(bad)} non-black run(s), e.g. {bad[:3]}")
    else:
        ok("all text is black")


def check_placeholders(docx):
    t = _doc_text(docx)
    hits = []
    for ph in PLACEHOLDERS:
        if ph == "____":
            n = len(re.findall(r"_{4,}", t))
        else:
            n = t.count(ph)
        if n:
            hits.append(f"{ph}x{n}")
    if hits:
        fail(f"leftover placeholders: {', '.join(hits)}")
    else:
        ok("no leftover placeholders")


def _parse_source(gen):
    src = gen.read_text(encoding="utf-8")
    # figures actually placed:  figure(FIG / "x.png", "Figure 5.1  caption")
    fig_used = re.findall(r'figure\(FIG / "[^"]+",\s*"(Figure [\d.]+)\s+([^"]+)"', src)
    tab_used = re.findall(r'caption\("(Table [\d.]+)\s+([^"]+)"', src)
    # the List of Figures / List of Tables blocks
    lof = re.findall(r'"(Figure [\d.]+)\s+([^"]+)"', src)
    lot = re.findall(r'"(Table [\d.]+)\s+([^"]+)"', src)
    # lof/lot include the used ones too; separate by whether they sit in the list arrays
    # simpler: the list entries are the ones NOT inside a figure(/caption( call -> compare numbers only
    return fig_used, tab_used, lof, lot


def check_fig_table_consistency(gen):
    src = gen.read_text(encoding="utf-8")
    fig_used = {n for n, _ in re.findall(r'figure\(FIG / "[^"]+",\s*"(Figure [\d.]+)\s+([^"]+)"', src)}
    tab_used = {n for n, _ in re.findall(r'caption(?:_above)?\("(Table [\d.]+)\s+([^"]+)"', src)}
    # List-of blocks: capture entries inside the two for-loops
    lof_block = re.search(r'LIST OF FIGURES.*?for f in \[(.*?)\]:', src, re.S)
    lot_block = re.search(r'LIST OF TABLES.*?for t in \[(.*?)\]:', src, re.S)
    lof = set(re.findall(r'"(Figure [\d.]+)', lof_block.group(1))) if lof_block else set()
    lot = set(re.findall(r'"(Table [\d.]+)', lot_block.group(1))) if lot_block else set()

    for label, used, listed in [("figure", fig_used, lof), ("table", tab_used, lot)]:
        missing_from_list = used - listed
        extra_in_list = listed - used
        if missing_from_list:
            fail(f"{label}s placed but absent from its List: {sorted(missing_from_list)}")
        if extra_in_list:
            fail(f"{label}s in the List but never placed: {sorted(extra_in_list)}")
        if not missing_from_list and not extra_in_list:
            ok(f"{label} captions and List entries match ({len(used)} items)")

    # sequential numbering within each chapter prefix
    for label, used in [("figure", fig_used), ("table", tab_used)]:
        by_ch: dict[str, list[int]] = {}
        for item in used:
            num = item.split()[1]
            ch, idx = num.split(".")
            by_ch.setdefault(ch, []).append(int(idx))
        for ch, idxs in by_ch.items():
            idxs.sort()
            expected = list(range(1, len(idxs) + 1))
            if idxs != expected:
                fail(f"{label} numbering gap/dup in chapter {ch}: {idxs}")
            else:
                ok(f"{label}s in chapter {ch} sequential 1..{len(idxs)}")


def main():
    docx = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DOCX
    gen = GEN
    if not docx.exists():
        print(f"ERROR: {docx} not found"); sys.exit(2)
    check_pages_and_empties(docx)
    check_black_text(docx)
    check_placeholders(docx)
    if gen.exists():
        check_fig_table_consistency(gen)

    print("=" * 60)
    for m in _passes:
        print(f"  [PASS] {m}")
    for m in _fails:
        print(f"  [FAIL] {m}")
    print("=" * 60)
    if _fails:
        print(f"RESULT: {len(_fails)} FAILURE(S)")
        sys.exit(1)
    print(f"RESULT: ALL {len(_passes)} CHECKS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
