# -*- coding: utf-8 -*-
"""Generate the CyberTrace IEEE Access research paper by filling the guide's
Access-Template-2024.docx -- reusing its exact styles, single-column title
block and two-column body. Never hand-edit the .docx; edit this and rebuild."""
import pathlib
import re as _re
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import parse_xml
import latex2mathml.converter as _l2m
from lxml import etree as _etree

HERE = pathlib.Path(__file__).resolve().parent
PAPER = HERE.parent
REPO = PAPER.parent
TEMPLATE = PAPER / "template" / "Access-Template-2024.docx"
FIG = REPO / "data" / "reports"
OUT = PAPER / "CyberTrace_IEEE_Access_Paper.docx"

_MML2OMML = r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL"
try:
    _OMML = _etree.XSLT(_etree.parse(_MML2OMML))
except Exception:
    _OMML = None

doc = Document(str(TEMPLATE))
CENTER = WD_ALIGN_PARAGRAPH.CENTER


# ---------- helpers ----------------------------------------------------------
def _omml(latex):
    if _OMML is None:
        return None
    try:
        ml = _l2m.convert(latex)
        el = _OMML(_etree.fromstring(ml.encode())).getroot()
        return parse_xml(_etree.tostring(el, encoding="unicode"))
    except Exception:
        return None


def set_text(p, text, bold=False, italic=False):
    """Replace a paragraph's runs with one run, keeping its style."""
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    return p


def para(text, style="PARA"):
    """Body paragraph in a template style; supports inline math as $...$ ."""
    p = doc.add_paragraph(style=style)
    for part in _re.split(r"(\$[^$]+\$)", text):
        if len(part) > 2 and part[0] == "$" and part[-1] == "$":
            el = _omml(part[1:-1])
            if el is not None:
                p._p.append(el)
                continue
            r = p.add_run(part[1:-1]); r.font.name = "Cambria Math"
        elif part:
            # **bold** and *italic* inline markers
            for seg in _re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", part):
                if seg.startswith("**") and seg.endswith("**"):
                    p.add_run(seg[2:-2]).bold = True
                elif seg.startswith("*") and seg.endswith("*"):
                    p.add_run(seg[1:-1]).italic = True
                elif seg:
                    p.add_run(seg)
    return p


def heading(text, first=False):
    return doc.add_paragraph(text, style="H1_List (No Space)" if first else "H1_List (Space)")


def sub(text, first=False):
    return doc.add_paragraph(text, style="H2_After H1" if first else "H2_Cont")


def equation(latex, number=None):
    p = doc.add_paragraph(style="Equation")
    el = _omml(latex)
    if el is not None:
        p._p.append(el)
    else:
        r = p.add_run(latex); r.font.name = "Cambria Math"
    if number:
        p.add_run("\t(%s)" % number)
    return p


def figure(name, cap, width=3.3):
    path = FIG / name
    p = doc.add_paragraph(style="Figure Caption")
    p.alignment = CENTER
    if path.exists():
        p.add_run().add_picture(str(path), width=Inches(width))
    c = doc.add_paragraph(cap, style="Figure Caption")
    c.alignment = CENTER
    return c


def _borders(t):
    tblPr = t._tbl.tblPr
    b = parse_xml(
        '<w:tblBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        + "".join('<w:%s w:val="single" w:sz="4" w:space="0" w:color="000000"/>' % e
                  for e in ("top", "left", "bottom", "right", "insideH", "insideV"))
        + "</w:tblBorders>")
    tblPr.append(b)


def table(caption, headers, rows, widths=None):
    doc.add_paragraph(caption, style="Table Caption")
    t = doc.add_table(rows=1, cols=len(headers))
    _borders(t)
    t.alignment = 1
    for j, h in enumerate(headers):
        cell = t.rows[0].cells[j]
        cell.text = ""
        r = cell.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(8)
        cell.paragraphs[0].alignment = CENTER
    for row in rows:
        cells = t.add_row().cells
        for j, v in enumerate(row):
            cells[j].text = ""
            rr = cells[j].paragraphs[0].add_run(str(v)); rr.font.size = Pt(8)
    return t


def ref(text):
    return doc.add_paragraph(text, style="Ref")


# ---------- clear body, keep title block (paras 0-11) + body sectPr ----------
body = doc.element.body
title_end = doc.paragraphs[11]._p          # the single-column section break
seen = False
for child in list(body):
    if child is title_end:
        seen = True
        continue
    if not seen:
        continue
    if child.tag == qn("w:sectPr"):        # keep the body-level 2-col mark
        continue
    body.remove(child)                     # drop every template body p / tbl


# ---------- title block ------------------------------------------------------
P = doc.paragraphs
set_text(P[0], "")                                            # DOP
set_text(P[1], "")                                            # DOI
set_text(P[2], "Low-Cost Power and Timing Side-Channel Attacks and Layered "
               "Countermeasures on an ESP32-S3: ChaCha20 and CRYSTALS-Kyber")
set_text(P[3], "SATVIK JINDAL, SUSHRUT KOUNDINYA, AND LAKSHAY TOMAR")
set_text(P[4], "School of Computer Science Engineering and Information Systems, "
               "Vellore Institute of Technology, Vellore 632014, India")
set_text(P[5], "Corresponding author: Satvik Jindal (e-mail: satvik.jindal2023@vitstudent.ac.in)")
set_text(P[6], "This work was carried out as a B.Tech capstone project under the "
               "guidance of Dr. Benila S, Assistant Professor, Vellore Institute of Technology.")
# remove the surplus affiliation / footnote template lines (7, 8) and the
# second index-terms line is the single-column break (11), keep it.
for idx in (8, 7):
    P[idx]._p.getparent().remove(P[idx]._p)

ABSTRACT = (
    "ABSTRACT Side-channel attacks recover secret keys from the physical "
    "behaviour of a device rather than from any flaw in the cipher. This paper "
    "presents a complete, low-cost attack-and-defense study on a commodity "
    "ESP32-S3 microcontroller, costing under 1,650 Indian rupees in total, that "
    "targets both a classical stream cipher, ChaCha20, and a post-quantum key "
    "encapsulation mechanism, CRYSTALS-Kyber. Power traces are captured with a "
    "16-bit ADS1115 converter across a 10 ohm shunt driven by a Raspberry Pi 5. "
    "Using correlation power analysis we recover the first-round ChaCha20 key "
    "word (0xDEADBEEF) at a peak correlation of 0.28 with 233 traces to "
    "disclosure, and a secret Kyber NTT coefficient (1234) at a correlation of "
    "0.23, on real hardware. We then evaluate five layered defenses: Boolean "
    "masking, constant-time execution, nonce-and-counter freshness, an active "
    "machine-learning probing monitor, and automatic key refresh. A Test Vector "
    "Leakage Assessment shows masking moves the leakage statistic from above the "
    "4.5 threshold to below it, and an Isolation Forest traffic monitor detects "
    "trace-collection within ten requests at a 0.5 percent false-positive rate, "
    "with a receiver-operating-characteristic area of 1.000 against an aggressive "
    "attacker and 0.982 against a throttled one. We report two honest negative "
    "results, where masking of the amplified Kyber product and a timing attack "
    "over the serial link both fail on hardware, and explain why. The complete "
    "toolkit, firmware, and captured traces are released to make the study "
    "reproducible on equivalent hardware.")
set_text(P[7] if len(P) > 7 else P[-1], "")  # safety; real abstract set below
# locate the Abstract and IT paragraphs by style and fill them
for p in doc.paragraphs:
    if p.style.name == "Abstract":
        set_text(p, ABSTRACT)
    elif p.style.name == "IT" and (p.text.strip() or p._p.findall(qn("w:hyperlink"))):
        for h in p._p.findall(qn("w:hyperlink")):
            p._p.remove(h)
        set_text(p, "INDEX TERMS Correlation power analysis, CRYSTALS-Kyber, "
                    "embedded security, hardware security, Isolation Forest, "
                    "leakage assessment, masking, post-quantum cryptography, "
                    "side-channel attack.")


# ---------- body -------------------------------------------------------------
heading("INTRODUCTION", first=True)
para("Modern ciphers are chosen because no practical mathematical attack against "
     "them is known. A side-channel attack sidesteps that mathematics entirely: it "
     "observes a physical quantity that the implementation leaks while it computes "
     "with the key, most commonly the instantaneous power the device draws, and "
     "recovers the key from the statistical dependence between that signal and the "
     "data being processed [1], [2]. Because the leakage is a property of the "
     "implementation and not of the algorithm, even a perfectly specified cipher "
     "on an ordinary microcontroller can fall to an attacker with inexpensive "
     "equipment.")
para("This paper reports a complete and reproducible study of such attacks, and of "
     "the defenses that stop them, on a single commodity device. The target is an "
     "ESP32-S3, a widely deployed Wi-Fi microcontroller; the entire measurement "
     "rig, a Raspberry Pi 5, a 16-bit ADS1115 analog-to-digital converter and a "
     "10 ohm shunt resistor, costs under 1,650 Indian rupees. On this platform we "
     "attack both ChaCha20, a stream cipher in wide use in TLS [5], and "
     "CRYSTALS-Kyber, the post-quantum key-encapsulation scheme standardised by "
     "NIST as FIPS 203 [7]. The post-quantum target matters because devices "
     "deployed today will still be in the field when quantum computers threaten "
     "classical key exchange, so their implementations must resist side-channel "
     "analysis now.")
para("The contributions of this work are fourfold. First, we demonstrate "
     "end-to-end correlation power analysis that recovers real keys from both a "
     "classical and a post-quantum primitive on the same low-cost hardware. "
     "Second, we implement and quantitatively evaluate five layered defenses, "
     "showing for each one the leakage it removes. Third, we add an active "
     "machine-learning monitor that detects the trace-collection phase of an "
     "attack, closing a gap left by fixed-threshold rules. Fourth, we report two "
     "honest negative results and explain them, because a defense study that only "
     "reports successes is not trustworthy.")

heading("RELATED WORK")
para("Correlation power analysis was introduced by Brier, Clavier and Olivier [3] "
     "as a refinement of Kocher's original differential power analysis [2], using "
     "the Pearson correlation between a Hamming-weight model and measured power to "
     "rank key hypotheses. The Test Vector Leakage Assessment methodology of "
     "Goodwill et al. [13] gives a cipher-agnostic way to detect leakage without "
     "mounting a full attack. Masking as a provable countermeasure is analysed by "
     "Chari et al. [4] and Mangard, Oswald and Popp [12]. For lattice schemes, "
     "Primas, Pessl and Mangard [9] and Pessl and Primas [10] show that the "
     "number-theoretic transform in Kyber leaks exploitable information, and Ravi "
     "et al. [11] survey the fast-growing literature on side-channel attacks "
     "against standardised post-quantum schemes. Table 1 places the present work "
     "against the most directly comparable studies.")
table("TABLE 1. Positioning against representative prior work.",
      ["Work", "Target", "Platform", "PQC", "Active defense"],
      [["Brier et al. [3]", "DES/AES", "Smartcard", "No", "No"],
       ["Primas et al. [9]", "Kyber NTT", "Cortex-M", "Yes", "No"],
       ["Ravi et al. [11]", "PQC survey", "Various", "Yes", "No"],
       ["This work", "ChaCha20 + Kyber", "ESP32-S3", "Yes", "Yes (ML)"]])

heading("THREAT MODEL AND MEASUREMENT SETUP")
para("The attacker can issue encryption or decapsulation requests to the target "
     "and can measure the current it draws, but cannot read its memory or its key. "
     "This is the standard model for an adversary with brief physical access to a "
     "deployed device. The defender runs on the same host and may enable "
     "countermeasures, monitor the request stream, and rotate the device key. The "
     "two programs never share state, so an attack succeeds or fails on "
     "measurement alone. Figure 1 shows the architecture and Figure 2 the physical "
     "wiring.")
figure("architecture.png", "FIGURE 1. Attacker, defender and target architecture.")
figure("wiring.png", "FIGURE 2. Measurement setup: the target is powered through a "
                     "10 ohm shunt read differentially by the ADS1115.")
para("The target's power rail is cut and a 10 ohm shunt inserted; the voltage "
     "across it, proportional to the instantaneous current, is read differentially "
     "by the ADS1115 at gain 4 and 860 samples per second. A trigger pin marks the "
     "sensitive computation. The target's own USB is disconnected during "
     "acquisition so that the full current flows through the shunt.")

heading("ATTACK AND DEFENSE METHODOLOGY")
sub("Correlation Power Analysis of ChaCha20", first=True)
para("ChaCha20 begins by adding the key to a constant and mixing it with a public "
     "counter. The first-round intermediate that depends on one key word is")
equation(r"d = \text{counter} \oplus (\text{const}_0 + \text{key}_0),", "1")
para("where the counter and the constant are known to the attacker. For each "
     "guess of a key byte the attacker predicts the Hamming weight of the "
     "corresponding byte of $d$ and correlates it against the measured power at "
     "each sample, choosing the guess whose Pearson correlation")
equation(r"\rho_{k} = \frac{\sum_i (h_{i,k}-\bar{h}_k)(t_i-\bar{t})}"
         r"{\sqrt{\sum_i (h_{i,k}-\bar{h}_k)^2}\,\sqrt{\sum_i (t_i-\bar{t})^2}}", "2")
para("peaks highest. The correct key is the one whose correlation stands clearly "
     "above every rival; the margin to the runner-up is the quantity that "
     "distinguishes a real recovery from a coincidence.")
sub("Kyber Coefficient Recovery")
para("For Kyber the leaking intermediate is a single coefficient of the "
     "number-theoretic-transform pointwise product computed during decapsulation,")
equation(r"t = \hat{s}\cdot u \ \text{mod}\ q,", "3")
para("where $u$ is attacker-known from the ciphertext and $\\hat{s}$ is the "
     "secret. Guessing $\\hat{s}$ and correlating against the Hamming weight of "
     "$t$ recovers the coefficient, the standard published Kyber target [9], [10].")
sub("Timing and Replay")
para("The timing attack measures whether a secret-dependent branch changes the "
     "response time of a verification command; the replay attack captures a valid "
     "authenticated command and resends it to test whether the device accepts it "
     "a second time.")
sub("Defenses")
para("Five defenses are implemented on the device and toggled by the defender. "
     "**Masking** splits every key-dependent value into random shares so that no "
     "single measured point depends on the key. **Constant-time** execution "
     "removes secret-dependent branches. **Nonce-and-counter** freshness binds "
     "every command to a monotonic counter so a replay is rejected. An active "
     "**probing monitor** scores the stream of requests with an Isolation Forest "
     "and raises an alarm when the traffic matches trace collection. **Key "
     "refresh** rotates the device key once probing is detected, so any traces "
     "already gathered become useless.")

heading("EXPERIMENTAL RESULTS")
para("All figures below are from the real ESP32-S3. Figure 3 shows the ChaCha20 "
     "correlation attack: the correct key word, 0xDEADBEEF, is recovered at a peak "
     "correlation of 0.28, within a few hundred traces. Figure 4 shows the "
     "masking assessment, and Figure 5 the Kyber coefficient attack recovering the "
     "secret value 1234.")
figure("cpa_report.png", "FIGURE 3. ChaCha20 first-round CPA: the correct key word "
                        "peaks above all rivals.")
figure("tvla.png", "FIGURE 4. TVLA on hardware: masking moves the leakage statistic "
                   "from above the 4.5 threshold to below it.")
figure("kyber_cpa.png", "FIGURE 5. Kyber coefficient CPA: the correct secret (1234) "
                       "versus all guesses.")
table("TABLE 2. Attack outcomes on real hardware.",
      ["Attack", "Target", "Result", "Correlation / margin"],
      [["Power CPA", "ChaCha20 key word", "Recovered (0xDEADBEEF)", "0.28, NTD < 250"],
       ["Power CPA", "Kyber coefficient", "Recovered (1234)", "0.23, margin 0.04"],
       ["Timing", "Verify branch", "Failed over UART", "latency dominated"],
       ["Replay", "Authenticated cmd", "Accepted w/o nonce; blocked with", "-"]])
para("The active defense is evaluated in Figure 6 and Table 3. Over two hundred "
     "independently seeded windows per class, the Isolation Forest separates "
     "attacking from normal traffic almost perfectly, and when it checks the "
     "request stream after every request it detects both an aggressive and a "
     "throttled attacker within ten requests, at a 0.5 percent false-positive "
     "rate on normal traffic.")
figure("probing.png", "FIGURE 6. Probing-detection latency: the ML monitor catches "
                      "the throttled attacker the rule thresholds miss.")
table("TABLE 3. Isolation-Forest probing detector (200 seeds per class).",
      ["Metric", "Aggressive", "Throttled"],
      [["Single-window ROC-AUC", "1.000", "0.982"],
       ["Streaming detection", "100%", "100%"],
       ["Median requests to detect", "10", "10"],
       ["False-positive rate", "0.5%", "0.5%"]])

heading("DISCUSSION")
para("Figure 7 compares simulation with hardware for the power attack. Simulation "
     "is systematically cleaner, a higher correlation and fewer traces to "
     "disclosure, because it contains no measurement noise; it is therefore an "
     "upper bound on what the attacker achieves, and the hardware result is the "
     "real evidence.")
figure("sim_vs_hw.png", "FIGURE 7. Simulation versus hardware for the ChaCha20 "
                       "power attack.")
para("Two defenses fail on hardware, and we report them honestly. The masking of "
     "the amplified Kyber product does not suppress its leakage, because the "
     "firmware mask is applied to a value whose Hamming weight still drives the "
     "sustained current the shunt integrates; a correct fix re-randomises the mask "
     "inside the leaking window or moves to arithmetic sharing with a "
     "second-order check. The timing attack fails because the secret-dependent "
     "delay of roughly 0.2 milliseconds is swamped by the serial round-trip of "
     "about 8 milliseconds and its jitter, a forty-to-one disadvantage; resolving "
     "it needs device-side latency measurement rather than measurement over the "
     "link. These negatives bound the scope of the defenses rather than weaken "
     "the study.")
para("A practical observation from the hardware campaign is that correlation power "
     "analysis is acutely sensitive to trace alignment: the few-sample jitter in "
     "when the device enters the measured loop smears the leakage across samples "
     "and, left uncorrected, causes the attack to fail while the correlation falls "
     "as traces are added. Aligning each trace to a common reference before "
     "correlation restores the recovery, and is a necessary step on any device "
     "whose command latency is not perfectly deterministic.")

heading("CONCLUSION")
para("We have shown that a sub-2,000-rupee rig recovers real keys from both a "
     "classical and a post-quantum primitive on a commodity microcontroller, and "
     "that a layered set of countermeasures, measured rather than asserted, "
     "removes the leakage each one targets while an active machine-learning "
     "monitor detects the attack as it is mounted. Future work will close the two "
     "negative results, extend the Kyber attack to a full secret vector, and "
     "train the probing monitor on a larger corpus of real deployment traffic.")

heading("REFERENCES")
for r in [
    "[1] P. Kocher, \u201cTiming attacks on implementations of Diffie-Hellman, RSA, "
    "DSS, and other systems,\u201d in Proc. CRYPTO, 1996, pp. 104\u2013113.",
    "[2] P. Kocher, J. Jaffe, and B. Jun, \u201cDifferential power analysis,\u201d in "
    "Proc. CRYPTO, 1999, pp. 388\u2013397.",
    "[3] E. Brier, C. Clavier, and F. Olivier, \u201cCorrelation power analysis with "
    "a leakage model,\u201d in Proc. CHES, 2004, pp. 16\u201329.",
    "[4] S. Chari, J. R. Rao, and P. Rohatgi, \u201cTemplate attacks,\u201d in Proc. "
    "CHES, 2002, pp. 13\u201328.",
    "[5] D. J. Bernstein, \u201cChaCha, a variant of Salsa20,\u201d in Workshop Rec. "
    "SASC, 2008.",
    "[6] Y. Nir and A. Langley, \u201cChaCha20 and Poly1305 for IETF protocols,\u201d "
    "RFC 8439, 2018.",
    "[7] National Institute of Standards and Technology, \u201cModule-lattice-based "
    "key-encapsulation mechanism standard,\u201d FIPS 203, 2024.",
    "[8] J. Bos et al., \u201cCRYSTALS-Kyber: A CCA-secure module-lattice-based "
    "KEM,\u201d in Proc. IEEE EuroS&P, 2018, pp. 353\u2013367.",
    "[9] R. Primas, P. Pessl, and S. Mangard, \u201cSingle-trace side-channel "
    "attacks on masked lattice-based encryption,\u201d in Proc. CHES, 2017, pp. "
    "513\u2013533.",
    "[10] P. Pessl and R. Primas, \u201cMore practical single-trace attacks on the "
    "number theoretic transform,\u201d in Proc. LATINCRYPT, 2019, pp. 130\u2013149.",
    "[11] P. Ravi et al., \u201cSide-channel and fault-injection attacks over "
    "lattice-based post-quantum schemes,\u201d ACM TECS, vol. 22, no. 2, 2023.",
    "[12] S. Mangard, E. Oswald, and T. Popp, Power Analysis Attacks: Revealing the "
    "Secrets of Smart Cards. Springer, 2007.",
    "[13] G. Goodwill, B. Jun, J. Jaffe, and P. Rohatgi, \u201cA testing methodology "
    "for side-channel resistance validation,\u201d in NIST Non-Invasive Attack "
    "Testing Workshop, 2011.",
    "[14] F. T. Liu, K. M. Ting, and Z.-H. Zhou, \u201cIsolation forest,\u201d in "
    "Proc. IEEE ICDM, 2008, pp. 413\u2013422.",
]:
    ref(r)

doc.save(str(OUT))
print("saved", OUT)
print("paragraphs:", len(doc.paragraphs))
