"""Render pages of the report to PNG for visual inspection.

    python report/build/preview.py           # render pages 1-8
    python report/build/preview.py 30 36      # render pages 30-36
    python report/build/preview.py 5          # render page 5 only

Images are written to report/build/_preview/pgNN.png and the paths printed.
Exports a fresh PDF via Word first, so it always reflects the saved .docx.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).parent
REPO = HERE.parents[1]
DOCX = REPO / "report" / "CyberTrace_Project_Report_Satvik.docx"
OUTDIR = HERE / "_preview"


def main():
    args = [int(a) for a in sys.argv[1:] if a.isdigit()]
    if not args:
        lo, hi = 1, 8
    elif len(args) == 1:
        lo = hi = args[0]
    else:
        lo, hi = args[0], args[1]

    sys.path.insert(0, str(HERE))
    import _word
    import fitz
    pdf_path = HERE / "_preview.pdf"
    pages = _word.export_pdf(str(DOCX), str(pdf_path))
    OUTDIR.mkdir(exist_ok=True)
    pdf = fitz.open(str(pdf_path))
    hi = min(hi, pdf.page_count)
    out = []
    for i in range(lo - 1, hi):
        p = OUTDIR / f"pg{i + 1:02d}.png"
        pdf[i].get_pixmap(dpi=110).save(str(p))
        out.append(str(p))
    pdf.close()
    print(f"total pages: {pages}")
    for p in out:
        print(p)


if __name__ == "__main__":
    main()
