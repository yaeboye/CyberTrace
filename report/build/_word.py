"""Robust Microsoft Word COM helpers.

Centralises the fiddly parts that kept biting us: a stray WINWORD.EXE holding
the .docx open (PermissionError on save), and TOC/field updates. Every public
function kills lingering Word instances first and retries on a lock.
"""
from __future__ import annotations

import os
import subprocess
import time


def _kill_word():
    # terminate any lingering headless Word that may hold the file open
    subprocess.run(["taskkill", "/F", "/IM", "WINWORD.EXE"],
                   capture_output=True, text=True)
    time.sleep(1.0)


def _open(app_visible=False):
    import win32com.client as win32
    app = win32.Dispatch("Word.Application")
    app.Visible = app_visible
    app.DisplayAlerts = False
    return app


def update_fields_and_save(docx_path, retries=3):
    """Open the document, update every field and the table(s) of contents,
    repaginate, save in place, and return the page count. Retries on a lock."""
    docx_path = os.path.abspath(docx_path)
    last = None
    for attempt in range(retries):
        _kill_word()
        app = None
        try:
            app = _open()
            d = app.Documents.Open(docx_path)
            d.Fields.Update()
            for toc in d.TablesOfContents:
                toc.Update()
            d.Repaginate()
            pages = int(d.ComputeStatistics(2))  # wdStatisticPages
            d.Save()
            d.Close(False)
            return pages
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5)
        finally:
            if app is not None:
                try:
                    app.Quit()
                except Exception:  # noqa: BLE001
                    pass
    raise RuntimeError(f"update_fields_and_save failed after {retries} tries: {last}")


def export_pdf(docx_path, pdf_path, retries=3):
    """Export the document to PDF (wdExportFormatPDF=17). Returns page count."""
    docx_path = os.path.abspath(docx_path)
    pdf_path = os.path.abspath(pdf_path)
    last = None
    for attempt in range(retries):
        _kill_word()
        app = None
        try:
            app = _open()
            d = app.Documents.Open(docx_path)
            d.Repaginate()
            pages = int(d.ComputeStatistics(2))
            d.ExportAsFixedFormat(pdf_path, 17)
            d.Close(False)
            return pages
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5)
        finally:
            if app is not None:
                try:
                    app.Quit()
                except Exception:  # noqa: BLE001
                    pass
    raise RuntimeError(f"export_pdf failed after {retries} tries: {last}")
