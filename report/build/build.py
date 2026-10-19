"""Build the CyberTrace report end-to-end for every team member, then verify.

    python report/build/build.py             # all members, full build + verify
    python report/build/build.py --no-figs   # skip figure/diagram regen (faster)
    python report/build/build.py --member 0  # build only member 0 (Satvik)

Each member gets their own .docx (CyberTrace_Project_Report_<First>.docx) whose
Declaration / Certificate / Acknowledgement carry only their name. Figures and
diagrams are generated once and shared by all three.

Steps per member: regenerate the document -> update fields + table of contents
-> verify. Figures (matplotlib) and Mermaid diagrams are regenerated once up
front. Lock-safe: lingering Word instances are killed before each COM step.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
REPO = HERE.parents[1]
PY = sys.executable

MEMBERS = ["Satvik", "Sushrut", "Lakshay"]


def run(desc, argv, env=None):
    print(f"\n>>> {desc}")
    e = dict(os.environ); e.update(env or {})
    r = subprocess.run([PY, *argv], capture_output=True, text=True, env=e)
    for line in (r.stdout or "").strip().splitlines()[-3:]:
        print("    " + line)
    if r.returncode != 0:
        print("    STDERR:", (r.stderr or "").strip()[-600:])
        raise SystemExit(f"step failed: {desc}")


def docx_for(i):
    return REPO / "report" / f"CyberTrace_Project_Report_{MEMBERS[i]}.docx"


def main():
    sys.path.insert(0, str(HERE))
    import _word

    no_figs = "--no-figs" in sys.argv
    only = None
    if "--member" in sys.argv:
        only = int(sys.argv[sys.argv.index("--member") + 1])

    if not no_figs:
        run("regenerate base figures", [str(HERE / "gen_figs.py")])
        run("regenerate hardware figures", [str(HERE / "gen_hw_figs.py")])
        run("render Mermaid diagrams", [str(HERE / "render_mermaid.py")])

    targets = [only] if only is not None else range(len(MEMBERS))
    for i in targets:
        name = MEMBERS[i]
        _word._kill_word()
        run(f"regenerate document ({name})", [str(HERE / "gen_report.py")],
            env={"CT_CANDIDATE": str(i)})
        print(f"\n>>> update fields + TOC ({name})")
        pages = _word.update_fields_and_save(str(docx_for(i)))
        print(f"    saved, {pages} pages")
        print(f"\n>>> verify ({name})")
        r = subprocess.run([PY, str(HERE / "verify.py"), str(docx_for(i))], text=True)
        if r.returncode != 0:
            raise SystemExit(f"VERIFICATION FAILED for {name} - do not ship")

    print("\n>>> spell check (advisory, Satvik copy)")
    subprocess.run([PY, str(HERE / "spellcheck.py"), str(docx_for(0))], text=True)
    print("\nBUILD OK")


if __name__ == "__main__":
    main()
