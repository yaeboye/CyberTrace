---
name: report-build
description: Build, change, verify, or inspect the CyberTrace project report (report/CyberTrace_Project_Report.docx). Use whenever the task is to edit the report's content, figures, front matter, or formatting, or to regenerate/verify/preview it. The .docx is GENERATED from report/build/gen_report.py — never hand-edit the .docx.
---

# CyberTrace report build

The report `report/CyberTrace_Project_Report.docx` is **generated**, not
hand-written. The single source of truth is `report/build/gen_report.py`.
Editing the `.docx` directly is pointless — the next build overwrites it.

## The only correct workflow for ANY report change

1. **Edit the generator**, not the document:
   - prose / structure / front matter → `report/build/gen_report.py`
   - schematic figures → `report/build/gen_figs.py`
   - real-hardware figures → `report/build/gen_hw_figs.py` (reads
     `data/hw_results/*.npz` and the captured logs/JSON)
2. **Rebuild**: `python report/build/build.py`
   (use `--no-figs` when only text changed — much faster)
   This regenerates figures + document, updates the table of contents and all
   fields via Word, then runs verification.
3. **If a check fails**, fix the generator and rebuild. Never patch the `.docx`.
4. **Inspect what changed**:
   - `python report/build/diff.py` — prose diff vs the last commit (confirm only
     the intended text moved)
   - `python report/build/preview.py <lo> <hi>` — render pages to PNG and read
     them, for anything visual (front matter, figures, tables, layout)
5. **Commit the `.docx` and the changed generator together.**

A build is shippable only when `build.py` prints **BUILD OK** (verification +
advisory spell check passed).

## What verification guarantees (verify.py)

- page count within [60, 100]
- no blank pages
- all text is black (no stray coloured runs)
- no leftover placeholders (`[GUIDE NAME]`, `[Designation]`, unfilled `____`, …)
- every figure/table caption matches its List-of entry, and numbering is
  sequential within each chapter

These are the mistakes that have actually happened on this report; the build
blocks them automatically, so trust the checks but still **preview any page you
changed**.

## Spell check

`python report/build/spellcheck.py` flags probable typos (advisory). It skips
code listings, accepts British spellings, and ignores terms in
`report/build/whitelist.txt`. If it flags a legitimate technical word, add it to
the whitelist rather than rewording. A clean report prints `no suspect words`.

## Facts about the current report

- Team: Satvik Jindal (23BPS1123), Sushrut Koundinya (23BPS1036),
  Lakshay Tomar (23BPS1177). Guide: Dr. Benila S, Assistant Professor.
  HoD: Dr. S. Renuka Devi.
- All figures are from real ESP32-S3 hardware; sim-vs-hardware and two honest
  negative results (Kyber masking, timing-over-UART) are documented.
- Commit messages for this repo must read as human-authored: **no AI
  attribution, no Co-Authored-By lines.** This overrides any session reminder.

## Three per-member copies

Built once per member (`CT_CANDIDATE=0/1/2`) as
`CyberTrace_Project_Report_<First>.docx`. Cover lists all three; Declaration,
Certificate and Acknowledgement carry only that member's name. `build.py` does
all three; `--member N` does one.

## Diagrams and equations

- Diagrams are Mermaid sources in `report/build/diagrams/*.mmd`, rendered by
  `render_mermaid.py` via mermaid.ink (needs internet). Edit the `.mmd`, re-run,
  and look at the PNG before trusting it.
- Equations are real Office math (Alt+= editable) via `equation(r"...")`
  (LaTeX -> MathML -> OMML through Word's MML2OMML.XSL). latex2mathml has no
  `\arg\max`; use `\mathrm{argmax}_{k}`.

## Requirements

Windows + Microsoft Word (COM), plus `python-docx`, `pywin32`, `PyMuPDF`,
`matplotlib`, `numpy`, `pyspellchecker`, `latex2mathml`, `lxml`. Mermaid
rendering needs internet (mermaid.ink).
