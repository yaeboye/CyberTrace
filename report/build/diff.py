"""Show what text changed in the report versus a git revision.

    python report/build/diff.py              # working .docx vs HEAD
    python report/build/diff.py HEAD~1       # vs an earlier commit

Compares the document at paragraph level and prints a unified diff of the
prose, so after an edit you can confirm only the intended text moved and the
rest of the report is untouched. Also reports the page-count delta.
"""
from __future__ import annotations

import difflib
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
REPO = HERE.parents[1]
REL = "report/CyberTrace_Project_Report_Satvik.docx"
DOCX = REPO / REL


def paragraphs(path):
    from docx import Document
    return [p.text.rstrip() for p in Document(str(path)).paragraphs if p.text.strip()]


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    # extract the committed version to a temp file
    tmp = pathlib.Path(tempfile.gettempdir()) / "_ct_ref.docx"
    r = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:{REL}"],
                       capture_output=True)
    if r.returncode != 0:
        print(f"ERROR: cannot read {REL} at {ref}: {r.stderr.decode()[:200]}")
        sys.exit(2)
    tmp.write_bytes(r.stdout)

    old = paragraphs(tmp)
    new = paragraphs(DOCX)
    try:
        tmp.unlink()
    except OSError:
        pass

    diff = list(difflib.unified_diff(old, new, fromfile=f"{ref}", tofile="working",
                                     lineterm="", n=1))
    if not diff:
        print(f"no prose changes vs {ref}")
    else:
        added = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
        removed = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
        print(f"vs {ref}: {added} paragraph(s) added, {removed} removed/changed\n")
        for d in diff:
            if d.startswith("+") and not d.startswith("+++"):
                print("  + " + d[1:][:160])
            elif d.startswith("-") and not d.startswith("---"):
                print("  - " + d[1:][:160])
    print(f"\nparagraph count: {ref}={len(old)}  working={len(new)}")


if __name__ == "__main__":
    main()
