"""CyberTrace desktop application.

A native window that drives the attacker and defender command-line tools and
shows their output and analysis figures -- no browser, no server. Each action
runs the real CLI in a background thread so the window stays responsive.

Run:  python gui/app.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

from PIL import Image, ImageTk

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = sys.executable
FIG = ROOT / "data" / "reports"

BG = "#121417"; PANEL = "#1a1d21"; LINE = "#2b3038"
TEXT = "#e6e8ea"; DIM = "#9aa1a9"; ACCENT = "#4aa3c7"
OK = "#3fb27f"; BAD = "#d4645c"; MONO = ("Cascadia Mono", 10)


class CyberTraceApp:
    def __init__(self, root):
        self.root = root
        root.title("CyberTrace — Side-Channel Attack & Defense")
        root.configure(bg=BG)
        root.geometry("1180x820")
        root.minsize(980, 600)
        self._busy = False
        self._photo = None

        self._style()
        self._build()

    # ---------------- styling ----------------
    def _style(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL,
                    bordercolor=LINE, font=("Segoe UI", 10))
        s.configure("TFrame", background=BG)
        s.configure("Panel.TLabelframe", background=PANEL, bordercolor=LINE)
        s.configure("Panel.TLabelframe.Label", background=PANEL, foreground=DIM,
                    font=("Segoe UI", 10, "bold"))
        s.configure("TButton", background=PANEL, foreground=TEXT, bordercolor=LINE,
                    focusthickness=0, padding=6)
        s.map("TButton", background=[("active", "#242931")],
              bordercolor=[("active", ACCENT)])
        s.configure("Accent.TButton", background="#20343d")
        s.configure("TLabel", background=PANEL, foreground=TEXT)
        s.configure("Dim.TLabel", background=PANEL, foreground=DIM)
        s.configure("TCheckbutton", background=PANEL, foreground=TEXT)
        s.configure("TSpinbox", fieldbackground="#20242a", foreground=TEXT, arrowcolor=TEXT)

    # ---------------- layout ----------------
    def _build(self):
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(top, text="CyberTrace", bg=BG, fg=TEXT,
                 font=("Segoe UI", 17, "bold")).pack(side="left")
        tk.Label(top, text="  esp32-s3 side-channel testbed", bg=BG, fg=DIM,
                 font=MONO).pack(side="left")
        self.status = tk.Label(top, text="● ready", bg=BG, fg=DIM, font=MONO)
        self.status.pack(side="right")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=8)

        # scrollable left control column (so nothing is clipped at high DPI)
        left_outer = tk.Frame(body, bg=BG, width=340)
        left_outer.pack(side="left", fill="y")
        left_outer.pack_propagate(False)
        lcanvas = tk.Canvas(left_outer, bg=BG, highlightthickness=0, width=318)
        lvsb = ttk.Scrollbar(left_outer, orient="vertical", command=lcanvas.yview)
        lcanvas.configure(yscrollcommand=lvsb.set)
        lvsb.pack(side="right", fill="y")
        lcanvas.pack(side="left", fill="both", expand=True)
        left = tk.Frame(lcanvas, bg=BG)
        lcanvas.create_window((0, 0), window=left, anchor="nw", width=312)
        left.bind("<Configure>",
                  lambda e: lcanvas.configure(scrollregion=lcanvas.bbox("all")))
        lcanvas.bind_all("<MouseWheel>",
                         lambda e: lcanvas.yview_scroll(int(-e.delta / 120), "units"))

        # parameters
        par = ttk.LabelFrame(left, text="Parameters", style="Panel.TLabelframe")
        par.pack(fill="x", pady=(0, 12))
        row = tk.Frame(par, bg=PANEL); row.pack(fill="x", padx=10, pady=8)
        tk.Label(row, text="Traces", bg=PANEL, fg=TEXT).pack(side="left")
        self.traces = tk.IntVar(value=1500)
        ttk.Spinbox(row, from_=200, to=10000, increment=100, width=8,
                    textvariable=self.traces).pack(side="right")
        self.masked = tk.BooleanVar(value=False)
        ttk.Checkbutton(par, text="Device under test has masking ON",
                        variable=self.masked).pack(anchor="w", padx=10, pady=(0, 8))

        # attacker
        atk = ttk.LabelFrame(left, text="Attacker  (key recovery only)",
                             style="Panel.TLabelframe")
        atk.pack(fill="x", pady=(0, 12))
        self._btn(atk, "Power CPA  (ChaCha20)", self.run_cpa, accent=True)
        self._btn(atk, "Kyber CPA  (post-quantum)", self.run_kyber)
        self._btn(atk, "Full 256-bit key recovery", self.run_full)
        self._btn(atk, "Timing attack", self.run_timing)
        self._btn(atk, "Replay attack", self.run_replay)

        # defender
        dfn = ttk.LabelFrame(left, text="Defender  (device owner)",
                             style="Panel.TLabelframe")
        dfn.pack(fill="x", pady=(0, 12))
        self._btn(dfn, "Leakage assessment  (ChaCha20)",
                  lambda: self.run_assess("chacha"), accent=True)
        self._btn(dfn, "Leakage assessment  (Kyber)",
                  lambda: self.run_assess("kyber"))
        self._btn(dfn, "Probing detection analytics", self.run_monitor)

        self._btn(left, "Clear output", self.clear)

        # right: output + figure
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(14, 0))

        outf = ttk.LabelFrame(right, text="Output", style="Panel.TLabelframe")
        outf.pack(fill="both", expand=True)
        self.out = scrolledtext.ScrolledText(outf, bg="#15181c", fg=TEXT,
                                             insertbackground=TEXT, font=MONO,
                                             relief="flat", wrap="none", height=16)
        self.out.pack(fill="both", expand=True, padx=2, pady=2)
        self.out.tag_config("ok", foreground=OK)
        self.out.tag_config("bad", foreground=BAD)
        self.out.tag_config("hdr", foreground=ACCENT)

        figf = ttk.LabelFrame(right, text="Analysis figure", style="Panel.TLabelframe")
        figf.pack(fill="x", pady=(12, 0))
        self.fig_label = tk.Label(figf, bg=PANEL, fg=DIM,
                                  text="run Power CPA or Leakage assessment to see a figure")
        self.fig_label.pack(fill="x", padx=6, pady=6)

    def _btn(self, parent, text, cmd, accent=False):
        b = ttk.Button(parent, text=text, command=cmd,
                       style="Accent.TButton" if accent else "TButton")
        b.pack(fill="x", padx=10, pady=4)
        return b

    # ---------------- helpers ----------------
    def log(self, text, tag=None):
        self.out.insert("end", text + "\n", tag or ())
        self.out.see("end")

    def clear(self):
        self.out.delete("1.0", "end")
        self.fig_label.configure(image="", text="(cleared)")
        self._photo = None

    def set_busy(self, busy, label=""):
        self._busy = busy
        self.status.configure(text=("● " + label) if busy else "● ready",
                              fg=(ACCENT if busy else DIM))

    def _run(self, title, argv, cwd, fig=None):
        if self._busy:
            return
        self.set_busy(True, title)
        self.log("")
        self.log("$ " + " ".join(str(a) for a in argv), "hdr")

        def worker():
            try:
                proc = subprocess.Popen([PY, *argv], cwd=str(cwd),
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, bufsize=1)
                for line in proc.stdout:
                    line = line.rstrip("\n")
                    tag = None
                    low = line.lower()
                    if "match" in low and "true" in low or "recovered" in low and "deadbeef" in low:
                        tag = "ok"
                    elif "mismatch" in low or "leaks" in low or "vulnerable" in low:
                        tag = "bad"
                    self.root.after(0, self.log, line, tag)
                proc.wait()
                if fig:
                    self.root.after(0, self.show_fig, fig)
            except Exception as e:
                self.root.after(0, self.log, f"error: {e}", "bad")
            finally:
                self.root.after(0, self.set_busy, False)

        threading.Thread(target=worker, daemon=True).start()

    def show_fig(self, name):
        path = FIG / name
        if not path.exists():
            return
        img = Image.open(path)
        maxw = 760
        if img.width > maxw:
            img = img.resize((maxw, int(img.height * maxw / img.width)))
        self._photo = ImageTk.PhotoImage(img)
        self.fig_label.configure(image=self._photo, text="")

    def _common(self):
        args = ["--traces", str(self.traces.get())]
        if self.masked.get():
            args.append("--masked")
        return args

    # ---------------- actions ----------------
    def run_cpa(self):
        self._run("CPA", ["ct_attack.py", "cpa", *self._common()],
                  ROOT / "attacker", fig="cpa_report.png")

    def run_kyber(self):
        self._run("Kyber CPA", ["ct_attack.py", "kyber", "--traces", str(self.traces.get())]
                  + (["--masked"] if self.masked.get() else []), ROOT / "attacker")

    def run_full(self):
        self._run("Full key recovery", ["chacha_full.py", "--traces", "4000"],
                  ROOT / "attacker")

    def run_timing(self):
        self._run("Timing", ["ct_attack.py", "timing"]
                  + (["--masked"] if self.masked.get() else []), ROOT / "attacker")

    def run_replay(self):
        self._run("Replay", ["ct_attack.py", "replay"], ROOT / "attacker")

    def run_assess(self, target):
        self._run(f"Assess {target}",
                  ["ct_defend.py", "assess", "--target", target,
                   "--traces", str(self.traces.get())],
                  ROOT / "defender", fig="tvla.png")

    def run_monitor(self):
        self._run("Monitor", ["ct_defend.py", "monitor"], ROOT / "defender")


def main():
    root = tk.Tk()
    CyberTraceApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
