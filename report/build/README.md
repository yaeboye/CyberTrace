# Report build system

The project report is **generated**, not hand-edited. `gen_report.py` is the
single source of truth for `report/CyberTrace_Project_Report.docx`. Never edit
the `.docx` by hand — edit the generator and rebuild, or the next build wipes
the manual change.

## Files

| File | Purpose |
|---|---|
| `gen_report.py` | Builds the whole document (python-docx). **Edit this to change the report.** |
| `gen_figs.py` | Generates the schematic/synthetic figures (architecture, wiring, …). |
| `gen_hw_figs.py` | Generates the real-hardware figures from `data/hw_results/*.npz` and the captured JSON/logs. Overwrites `heatmap.png` and `masking_bar.png` with hardware versions, so it must run **after** `gen_figs.py`. |
| `build.py` | One command: figures → document → update TOC/fields → verify. |
| `verify.py` | Fails the build on page count, blank pages, coloured text, leftover placeholders, or figure/table ↔ List mismatches. |
| `preview.py` | Renders page ranges to PNG for visual inspection. |
| `_word.py` | Robust Word COM helpers (kills stray WINWORD, retries on lock). |

## Usage

```bash
# full rebuild + verify (run from repo root)
python report/build/build.py

# faster: skip figure regeneration when only text changed
python report/build/build.py --no-figs

# verify an existing .docx without rebuilding
python report/build/verify.py

# look at pages 30-36
python report/build/preview.py 30 36
```

A build is only shippable when `verify.py` prints `ALL CHECKS PASSED` and
`build.py` ends with `BUILD OK`.

## Making a change safely

1. Edit `gen_report.py` (or a figure script).
2. `python report/build/build.py`
3. If a check fails, fix the generator and rebuild — do not patch the `.docx`.
4. `python report/build/preview.py <lo> <hi>` to eyeball any page you touched.
5. Commit the `.docx` **and** the changed generator together.

## Requirements

Windows with Microsoft Word installed (COM automation), plus Python packages
`python-docx`, `pywin32`, `PyMuPDF` (`fitz`), `matplotlib`, `numpy`.
