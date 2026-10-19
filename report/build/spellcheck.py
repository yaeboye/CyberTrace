"""Flag probable typos in the report body text (advisory, never fails a build).

    python report/build/spellcheck.py

Designed for low noise on a technical report:
  - code listings (Consolas font) are skipped
  - hyphenated compounds are checked part by part
  - British spellings (-ise/-our/-re/-yse ...) are accepted
  - capitalised words (proper nouns, sentence starts) are skipped
  - domain terms in whitelist.txt are never flagged

What survives all that is very likely a real typo. Add legitimate technical
words to whitelist.txt rather than reword the report.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
REPO = HERE.parents[1]
DOCX = REPO / "report" / "CyberTrace_Project_Report.docx"
WHITELIST = HERE / "whitelist.txt"

# British -> US suffix rewrites; a word is accepted if either form is known.
_BRIT = [("isation", "ization"), ("isations", "izations"), ("ised", "ized"),
         ("ises", "izes"), ("ising", "izing"), ("ise", "ize"),
         ("yse", "yze"), ("ysed", "yzed"), ("ysing", "yzing"),
         ("our", "or"), ("ours", "ors"), ("oured", "ored"),
         ("tre", "ter"), ("tres", "ters"), ("ogue", "og"),
         ("lled", "led"), ("lling", "ling"), ("ller", "ler")]


def load_whitelist():
    words = set()
    if WHITELIST.exists():
        for line in WHITELIST.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                words.add(line.lower())
    return words


def _variants(w):
    yield w
    for b, u in _BRIT:
        if w.endswith(b):
            yield w[: -len(b)] + u


def main():
    from docx import Document
    from spellchecker import SpellChecker

    docx = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DOCX
    wl = load_whitelist()
    sp = SpellChecker(distance=1)

    def known(tok):
        tok = tok.lower().strip("'-")
        if not tok or tok in wl:
            return True
        return any(not sp.unknown([v]) for v in _variants(tok))

    doc = Document(str(docx))
    seen = {}
    for p in doc.paragraphs:
        if any((r.font.name or "") == "Consolas" for r in p.runs):
            continue  # code listing
        for m in re.finditer(r"[A-Za-z][A-Za-z'-]{2,}", p.text):
            w = m.group(0)
            if w[0].isupper():          # proper noun / sentence start
                continue
            parts = [x for x in w.split("-") if x]
            if all(known(part) for part in parts):
                continue
            lw = w.lower()
            if lw not in seen:
                ctx = p.text[max(0, m.start() - 22):m.end() + 22]
                seen[lw] = (w, ctx.strip())

    if not seen:
        print("no suspect words")
        return
    print(f"{len(seen)} suspect word(s) for review "
          f"(add real terms to whitelist.txt):\n")
    for lw in sorted(seen):
        w, ctx = seen[lw]
        print(f"  {w:<22} …{ctx}…")


if __name__ == "__main__":
    main()
