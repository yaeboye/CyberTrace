"""Build the CyberTrace report end-to-end, then verify it.

    python report/build/build.py            # full build + verify
    python report/build/build.py --no-figs  # skip figure regen (faster)

Steps:
  1. regenerate figures (gen_figs.py, gen_hw_figs.py)   [unless --no-figs]
  2. regenerate the document (gen_report.py)
  3. update fields + table of contents, repaginate, save (Word COM)
  4. run verify.py and surface the result

Deterministic and lock-safe: lingering Word instances are killed before each
COM step. Exit code is non-zero if the build or any verification check fails.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
REPO = HERE.parents[1]
DOCX = REPO / "report" / "CyberTrace_Project_Report.docx"
PY = sys.executable


def run(desc, argv):
    print(f"\n>>> {desc}")
    r = subprocess.run([PY, *argv], capture_output=True, text=True)
    tail = (r.stdout or "").strip().splitlines()[-3:]
    for line in tail:
        print("    " + line)
    if r.returncode != 0:
        print("    STDERR:", (r.stderr or "").strip()[-500:])
        raise SystemExit(f"step failed: {desc}")


def main():
    sys.path.insert(0, str(HERE))
    import _word

    no_figs = "--no-figs" in sys.argv
    if not no_figs:
        run("regenerate base figures", [str(HERE / "gen_figs.py")])
        run("regenerate hardware figures", [str(HERE / "gen_hw_figs.py")])

    # release any lingering Word lock before writing the .docx
    _word._kill_word()
    run("regenerate document", [str(HERE / "gen_report.py")])

    print("\n>>> update fields + table of contents (Word)")
    pages = _word.update_fields_and_save(str(DOCX))
    print(f"    saved, {pages} pages")

    print("\n>>> verify")
    r = subprocess.run([PY, str(HERE / "verify.py")], text=True)
    if r.returncode != 0:
        raise SystemExit("VERIFICATION FAILED - do not ship this build")
    print("\nBUILD OK")


if __name__ == "__main__":
    main()
