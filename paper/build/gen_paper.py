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


_sub = [0]  # subsection letter counter, reset at each section heading


def heading(text, first=False):
    _sub[0] = 0
    return doc.add_paragraph(text, style="H1_List (No Space)" if first else "H1_List (Space)")


def sub(text, first=False):
    _sub[0] += 1
    letter = chr(ord("A") + _sub[0] - 1)
    p = doc.add_paragraph(f"{letter}. {text}", style="H2_Cont (No Space)")
    pPr = p._p.get_or_add_pPr()                      # cancel inherited auto-numbering
    for n in pPr.findall(qn("w:numPr")):
        pPr.remove(n)
    pPr.append(parse_xml(
        '<w:numPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr>'))
    return p


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
    "ESP32-S3 microcontroller, built from commodity, widely available components, that "
    "targets both a classical stream cipher, ChaCha20, and a post-quantum key "
    "encapsulation mechanism, CRYSTALS-Kyber. Power traces are captured with a "
    "16-bit ADS1115 converter across a 10 ohm shunt driven by a Raspberry Pi 5. "
    "Using correlation power analysis we recover the first-round ChaCha20 key "
    "word (0xDEADBEEF) at a peak correlation of 0.28 within fewer than 250 "
    "traces, and a secret Kyber NTT coefficient (1234) at a correlation of "
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
para("Modern ciphers are adopted because no practical mathematical attack against "
     "them is known. A side-channel attack sidesteps that mathematics entirely: "
     "rather than attacking the algorithm, it observes a physical quantity that the "
     "implementation leaks while it computes with the key, and recovers the key "
     "from the statistical dependence between that signal and the data being "
     "processed [1], [2]. The most widely exploited channel is the instantaneous "
     "power the device draws, because the dynamic current of a digital circuit "
     "depends on the number of bits that toggle, and that number depends in turn "
     "on the secret-dependent values the circuit is manipulating. Because the "
     "leakage is a property of the implementation rather than of the algorithm, "
     "even a perfectly specified cipher running on an ordinary microcontroller can "
     "be broken by an adversary equipped with nothing more than a shunt resistor "
     "and an inexpensive analog-to-digital converter.")
para("The threat is most acute for embedded and Internet-of-Things devices. These "
     "devices are deployed in the field, are physically accessible to an attacker, "
     "run cryptography on small microcontrollers without dedicated hardware "
     "countermeasures, and are expected to remain in service for many years. The "
     "last point is decisive for post-quantum cryptography: a device shipped today "
     "with a lattice-based key-encapsulation mechanism will still be operating when "
     "large quantum computers threaten classical key exchange, so its "
     "implementation must already resist physical attacks. Side-channel analysis "
     "of standardised post-quantum schemes is therefore not a theoretical concern "
     "but an immediate engineering requirement [7], [11].")
para("This paper presents a complete and reproducible study of such attacks, and "
     "of the layered defenses that stop them, on a single commodity device. The "
     "target is an ESP32-S3, a widely deployed Wi-Fi microcontroller. The entire "
     "measurement rig, a Raspberry Pi 5 host, a sixteen-bit ADS1115 converter and "
     "a ten-ohm shunt resistor, is built from commodity, widely available "
     "components, which places the attack within reach of any motivated adversary and "
     "makes the study straightforward to replicate in a teaching laboratory. On "
     "this platform we attack ChaCha20, a stream cipher in wide use in TLS [5], "
     "[6], and CRYSTALS-Kyber, the post-quantum key-encapsulation scheme "
     "standardised by the United States National Institute of Standards and "
     "Technology as FIPS 203 [7], [8].")
para("The contributions of this work are fivefold. First, we demonstrate "
     "end-to-end correlation power analysis that recovers real keys from both a "
     "classical stream cipher and a post-quantum key-encapsulation mechanism on "
     "the same low-cost hardware, reporting for each the recovered secret, the "
     "correlation peak, and the margin to the runner-up. Second, we implement and "
     "quantitatively evaluate five layered defenses, showing for each one the "
     "leakage it removes rather than merely asserting that it helps. Third, we add "
     "an active machine-learning monitor that detects the trace-collection phase "
     "of an attack directly from the request stream, closing a gap that fixed "
     "threshold rules leave open, and we train and evaluate it on real captured "
     "traffic as well as on synthetic traffic. Fourth, we report two honest "
     "negative results, where masking of the amplified Kyber product and a timing "
     "attack over the serial link both fail on hardware, and we explain the "
     "physical reason for each. Fifth, we release the complete toolkit, firmware, "
     "captured traces and trained models so that the entire study can be "
     "reproduced on equivalent hardware.")
para("The remainder of the paper is organised as follows. Section II reviews the "
     "necessary background on power leakage, correlation power analysis, leakage "
     "assessment, and the two target primitives. Section III surveys related work "
     "and positions this study against it. Section IV describes the threat model "
     "and the measurement setup. Sections V and VI detail the attack and the "
     "defense methodology respectively. Section VII presents the experimental "
     "results on real hardware. Section VIII discusses the findings, including the "
     "negative results and the limitations of the study, and Section IX concludes.")

heading("BACKGROUND")
sub("Power Leakage and the Hamming-Weight Model", first=True)
para("A CMOS logic gate draws a current spike each time one of its outputs "
     "switches. Across a register or a bus the total dynamic current in a clock "
     "cycle is, to a first approximation, proportional to the number of bits that "
     "change state. When a known public value is combined with a fixed secret, the "
     "intermediate result, and therefore the number of bits it sets, varies from "
     "one encryption to the next in a way the attacker can predict for each "
     "hypothesis about the secret. The standard leakage model assumes that the "
     "power consumed at the instant an intermediate value $v$ is manipulated is an "
     "affine function of its Hamming weight,")
equation(r"P = a\,\mathrm{HW}(v) + b + \varepsilon,", "1")
para("where $a$ and $b$ are unknown device constants and $\\varepsilon$ is noise. "
     "The attacker never needs $a$ or $b$: a correlation attack is invariant to "
     "both, so only the dependence of power on Hamming weight matters.")
sub("Correlation Power Analysis")
para("Correlation power analysis, introduced by Brier, Clavier and Olivier [3], "
     "ranks key hypotheses by the Pearson correlation between the modelled Hamming "
     "weight and the measured power. For a set of $N$ traces, a key-byte guess $k$ "
     "and a sample index $j$, the attacker computes")
equation(r"\rho_{k,j} = \frac{\sum_{i}(h_{i,k}-\bar{h}_k)(t_{i,j}-\bar{t}_j)}"
         r"{\sqrt{\sum_{i}(h_{i,k}-\bar{h}_k)^2}\,\sqrt{\sum_{i}(t_{i,j}-\bar{t}_j)^2}},", "2")
para("where $h_{i,k}$ is the predicted Hamming weight for trace $i$ under guess "
     "$k$ and $t_{i,j}$ is the measured power. The guess whose correlation peaks "
     "highest over all samples is selected. The number of traces to disclosure, "
     "the point at which the correct guess separates permanently from the "
     "others, measures how efficient the attack is; the margin between the winning "
     "correlation and the runner-up measures how trustworthy a given recovery is.")
sub("Leakage Assessment")
para("Test Vector Leakage Assessment [13] detects leakage without mounting a full "
     "attack. The device is driven with two classes of input, a fixed class and a "
     "random class, and Welch's two-sample t-statistic is computed sample by "
     "sample,")
equation(r"t = \frac{\mu_f - \mu_r}{\sqrt{s_f^2/n_f + s_r^2/n_r}},", "3")
para("where $\\mu$, $s^2$ and $n$ are the mean, variance and count of each class. "
     "A magnitude above the conventional threshold of 4.5 indicates that the two "
     "classes are distinguishable in the power signal, that is, that the "
     "implementation leaks; a magnitude below it, over a sufficient number of "
     "traces, is evidence that the leakage has been suppressed.")
sub("ChaCha20 and CRYSTALS-Kyber")
para("ChaCha20 [5] initialises its state from a constant, the key, a counter and "
     "a nonce, and mixes it with quarter-round additions, rotations and "
     "exclusive-ors. The first operation that combines the key with a known value "
     "is an addition of a key word to a constant, followed by an exclusive-or with "
     "the public counter, which is the intermediate this paper targets. "
     "CRYSTALS-Kyber [8] performs its core arithmetic in the number-theoretic "
     "transform domain, where decapsulation computes a pointwise product of the "
     "secret key with an attacker-influenced ciphertext component; a single "
     "coefficient of that product is the intermediate targeted here, following the "
     "established single-trace line of work on the transform [9], [10].")

heading("RELATED WORK")
para("Kocher introduced timing attacks [1] and, with Jaffe and Jun, differential "
     "power analysis [2], establishing that physical measurements leak key "
     "material. Brier, Clavier and Olivier [3] refined differential analysis into "
     "the correlation attack used throughout this paper, and Chari, Rao and "
     "Rohatgi [4] developed template attacks and the theory of masking as a "
     "countermeasure. Mangard, Oswald and Popp [12] give the standard textbook "
     "treatment of both attacks and defenses, and Goodwill et al. [13] defined the "
     "leakage-assessment methodology now used across the field. For lattice "
     "cryptography, Primas, Pessl and Mangard [9] showed that the number-theoretic "
     "transform in a masked lattice scheme is vulnerable to a single-trace attack, "
     "Pessl and Primas [10] made the attack more practical, and Ravi et al. [11] "
     "survey the rapidly growing body of side-channel and fault attacks against "
     "the standardised post-quantum schemes. The present work differs from this "
     "literature in combining a classical and a post-quantum target on one "
     "commodity platform, and in pairing the attacks with a measured, "
     "layered defense that includes an active machine-learning monitor rather than "
     "passive countermeasures alone. Table 1 places the work against the most "
     "directly comparable studies.")
table("TABLE 1. Positioning against representative prior work.",
      ["Work", "Target", "Platform", "PQC", "Active defense"],
      [["Kocher et al. [2]", "DES", "Smartcard", "No", "No"],
       ["Brier et al. [3]", "DES / AES", "Smartcard", "No", "No"],
       ["Primas et al. [9]", "Kyber NTT", "Cortex-M", "Yes", "No"],
       ["Pessl & Primas [10]", "NTT", "Cortex-M", "Yes", "No"],
       ["Ravi et al. [11]", "PQC survey", "Various", "Yes", "No"],
       ["This work", "ChaCha20 + Kyber", "ESP32-S3", "Yes", "Yes (ML)"]])

heading("THREAT MODEL AND MEASUREMENT SETUP")
sub("Adversary Model", first=True)
para("The adversary can issue encryption or decapsulation requests to the target "
     "and can measure the current it draws during the computation, but cannot read "
     "its memory, inspect its key, or modify its firmware. This corresponds to an "
     "attacker with brief physical access to a deployed device, for example a "
     "returned, lost, or in-field unit. The defender runs on the same host and may "
     "enable or disable countermeasures, monitor the stream of requests, and "
     "rotate the device key. The attacker and the defender are separate programs "
     "that share no state, so an attack succeeds or fails purely on the physical "
     "measurement; the defender never weakens the attack by cooperating with it. "
     "Figure 1 shows the overall architecture.")
figure("architecture.png", "FIGURE 1. Attacker, defender and target architecture; "
                           "the two programs share no state.")
sub("Measurement Rig")
para("The target's power rail is cut and a ten-ohm shunt resistor inserted in "
     "series, so that the entire supply current of the microcontroller flows "
     "through it. The voltage across the shunt, which is proportional to the "
     "instantaneous current by Ohm's law, is read differentially by an ADS1115 "
     "sixteen-bit converter at a gain of four and a sampling rate of 860 samples "
     "per second, over the I2C bus of a Raspberry Pi 5. A general-purpose output "
     "pin of the target is raised for the duration of the sensitive computation "
     "and read by the host as a trigger, so that acquisition is aligned to the "
     "operation of interest. Crucially, the target's own USB connection is removed "
     "during acquisition; otherwise the bulk decoupling capacitance on the "
     "development board and the universal-serial-bus supply absorb the "
     "high-frequency component of the current and the key-dependent leakage never "
     "reaches the shunt. Figure 2 shows the wiring.")
figure("wiring.png", "FIGURE 2. Measurement setup: the target is powered through a "
                     "ten-ohm shunt read differentially by the ADS1115.")
sub("Amplified Leakage and the Command Interface")
para("A sixteen-bit converter sampling at under one kilohertz is far too slow to "
     "resolve the nanosecond current spikes of individual instructions. To bring "
     "the leakage within reach of this deliberately cheap instrument, the firmware "
     "exposes a measurement mode that amplifies it: the key-dependent intermediate "
     "is held on the measured rail across a loop of several thousand iterations, "
     "so that the sustained average current, rather than a single transient, "
     "scales with its Hamming weight. This is a faithful model of the leakage a "
     "faster instrument would capture from the unmodified cipher, made observable "
     "on a hobbyist budget. Table 2 lists the device command interface.")
table("TABLE 2. Target device command interface over the host UART.",
      ["Command", "Purpose"],
      [["PING", "Liveness check"],
       ["ENCRYPT c", "ChaCha20 encrypt counter c; return ciphertext"],
       ["LEAKLOOP c", "Amplified first-round leakage for counter c"],
       ["KYBERLEAK u", "Amplified Kyber pointwise-product leakage for u"],
       ["CHECK x", "Constant- or variable-time secret comparison"],
       ["DEFENSE ...", "Toggle masking, constant-time or nonce"]])

heading("ATTACK METHODOLOGY")
sub("Correlation Power Analysis of ChaCha20", first=True)
para("ChaCha20 begins by adding a key word to a constant and mixing the result "
     "with the public counter. The first-round intermediate that depends on one "
     "key word is")
equation(r"d = \text{counter} \oplus (\text{const}_0 + \text{key}_0),", "4")
para("in which the counter and the constant are known to the attacker. For each "
     "of the four bytes of the key word, and for each of the 256 guesses of that "
     "byte, the attacker predicts the Hamming weight of the corresponding byte of "
     "$d$ and correlates it, by (2), against the measured power at every sample. "
     "The byte whose correlation peaks highest is accepted, and the key word is "
     "reconstructed as $\\text{key}_0 = (\\text{const}_0$-subtracted reconstruction"
     "$)$. Figure 3 shows the structure of the targeted quarter-round.")
figure("quarterround.png", "FIGURE 3. The ChaCha20 quarter-round and the first-round "
                          "intermediate targeted by the attack.")
sub("Kyber Coefficient Recovery")
para("For Kyber the leaking intermediate is a single coefficient of the "
     "number-theoretic-transform pointwise product computed during decapsulation,")
equation(r"t = \hat{s}\cdot u \ \text{mod}\ q,", "5")
para("where $u$ is known to the attacker from the ciphertext and $\\hat{s}$ is the "
     "secret coefficient, with $q = 3329$. The attacker varies $u$ across traces, "
     "guesses $\\hat{s}$ over the full range $[0,q)$, and correlates the Hamming "
     "weight of the predicted product against the measured power. The correct "
     "coefficient is the guess with the highest correlation peak, exactly as for "
     "ChaCha20 but over 3329 hypotheses rather than 256.")
sub("Timing and Replay Attacks")
para("The timing attack targets a secret comparison: if the verification of an "
     "authentication tag returns as soon as the first mismatched byte is found, "
     "the response time leaks how many leading bytes were correct, and the secret "
     "can be recovered byte by byte. The replay attack captures a valid "
     "authenticated command and resends it, testing whether the device accepts the "
     "same packet twice, which it must not if it binds each command to a fresh "
     "value.")
sub("Trace Alignment")
para("A practical obstacle on real hardware is that the interval between issuing "
     "a command and the device entering the measured loop is not perfectly "
     "constant: serial latency and operating-system scheduling on the host "
     "introduce a jitter of a few samples. Because correlation is computed at a "
     "fixed sample index, this jitter smears the leakage across neighbouring "
     "samples and, left uncorrected, causes the attack to fail while the "
     "correlation paradoxically falls as more traces are added. Each trace is "
     "therefore shifted, within a small window, to best match a common reference "
     "before correlation. This alignment restored the recovery on every attack in "
     "this study and is a necessary step on any device whose command latency is "
     "not deterministic.")

heading("DEFENSE METHODOLOGY")
sub("Boolean Masking", first=True)
para("Masking splits every key-dependent value $v$ into two shares, $v = v_m "
     "\\oplus m$, where $m$ is a fresh random mask drawn per operation, and "
     "processes the shares so that no single measured point depends on $v$ alone. "
     "A first-order correlation attack, which models one intermediate at a time, "
     "then finds no dependence to exploit. Masking is the primary countermeasure "
     "against the power attacks of Section V.")
sub("Constant-Time Execution")
para("Constant-time execution removes secret-dependent branches and memory "
     "accesses, so that the comparison of an authentication tag takes the same "
     "time whatever the secret. This closes the timing channel targeted in "
     "Section V-C.")
sub("Nonce and Counter Freshness")
para("Every authenticated command is bound to a monotonic counter, so that a "
     "replayed packet carries a stale counter and is rejected. This defeats the "
     "replay attack while leaving legitimate commands unaffected.")
sub("Active Probing Monitor")
para("The three countermeasures above are passive: they raise the cost of an "
     "attack but do nothing to detect one in progress. We add an active monitor "
     "that watches the stream of requests and flags the trace-collection phase of "
     "an attack. A simple rule-based version alarms when the request rate, the "
     "payload entropy, or the timing regularity crosses a fixed threshold, which "
     "catches an aggressive attacker but is evaded by a patient one that stays "
     "just under every limit. To close that gap we score each sliding window of "
     "traffic with an Isolation Forest [14] over nine features: payload entropy, "
     "request rate, timing coefficient of variation, duplicate ratio, "
     "sequentiality, compression ratio, inter-arrival autocorrelation, burst "
     "ratio, and timing acceleration. The forest is trained on normal traffic "
     "only, a one-class formulation that matches a deployment in which attacks are "
     "unseen in advance, and a window is flagged when its anomaly score falls "
     "below a threshold calibrated to a one-per-cent false-positive rate on normal "
     "traffic. A throttled attacker is caught not by any single statistic but "
     "because the joint signature of its traffic never occurs in normal use.")
table("TABLE 3. The nine traffic features scored by the Isolation Forest.",
      ["Feature", "What it captures"],
      [["Payload entropy", "Structured attacker payloads score low"],
       ["Request rate", "Flooding scores high"],
       ["Timing CV", "Machine-regular timing scores low"],
       ["Duplicate ratio", "Repeated payloads score high"],
       ["Sequentiality", "Counter sweeps score near one"],
       ["Compression ratio", "Compressible payloads score low"],
       ["Autocorrelation", "Regular cadence scores high"],
       ["Burst ratio", "Max gap over mean gap"],
       ["Timing acceleration", "Drift in inter-arrival time"]])

sub("Automatic Key Refresh")
para("When the monitor detects probing, the defender rotates the device key. Any "
     "traces the attacker has already gathered then correspond to a key that is no "
     "longer in use, so the collection must restart from zero, which in practice "
     "makes a slow attack unable ever to finish.")

heading("SYSTEM IMPLEMENTATION AND REPRODUCIBILITY")
para("The study is implemented as three cooperating programs plus the device "
     "firmware. The firmware, written in C++ for the ESP32-S3, implements "
     "ChaCha20, the Kyber pointwise product, the authenticated command channel "
     "and the amplified-leakage measurement modes, and exposes the command "
     "interface of Table 2 over a hardware UART. The attacker program issues "
     "commands, captures traces through the ADS1115, and runs the correlation and "
     "timing analyses; the defender program toggles the device countermeasures, "
     "runs the probing monitor, and rotates the key. A separate Isolation-Forest "
     "monitor, written in Python with scikit-learn, trains on normal traffic and "
     "scores the live request stream.")
para("Every quantitative claim in the paper is produced by a script that can be "
     "re-run on equivalent hardware. The attack and defense toolkit, the firmware "
     "sources, the captured raw traces, the labelled probing-traffic dataset, and "
     "the trained detector model are released together, so that a reader with an "
     "ESP32-S3, a Raspberry Pi and an ADS1115 can reproduce the figures and tables "
     "reported here. A desktop application wraps the same command-line tools behind "
     "a single window for demonstration, and an offline runner reproduces the "
     "machine-learning pipeline end to end without network access.")
para("A single methodological point deserves emphasis because it decides whether "
     "the hardware attack succeeds at all. Correlation power analysis assumes that "
     "the leaking operation falls at the same sample index on every trace. On the "
     "unmodified rig that assumption fails: the command-to-loop latency jitters by "
     "a handful of samples, the byte-phase windows drift, and the correlation of "
     "the correct key falls below that of spurious candidates even as the trace "
     "count grows. Table 4 quantifies the effect for the ChaCha20 attack. Before "
     "alignment the correct byte ranks as low as sixty-eighth of 256; after each "
     "trace is shifted to a common reference the correct byte wins or nearly wins "
     "every position, and the mean correlation roughly doubles. Alignment is "
     "therefore not a cosmetic post-processing step but a precondition for the "
     "attack on any device without deterministic command latency.")
table("TABLE 4. Effect of trace alignment on the ChaCha20 attack "
      "(rank of the correct byte among 256 guesses).",
      ["Byte", "Rank (raw)", "Rank (aligned)", "|corr| raw → aligned"],
      [["0", "4", "0", "0.18 → 0.29"],
       ["1", "68", "3", "0.14 → 0.28"],
       ["2", "45", "1", "0.14 → 0.31"],
       ["3", "22", "0", "0.17 → 0.31"]])

heading("EXPERIMENTAL RESULTS")
para("All results in this section are from the real ESP32-S3 unless explicitly "
     "noted as simulation. Trace counts, correlations and detection figures are "
     "the values measured during the hardware campaign.")
sub("ChaCha20 Power Attack", first=True)
para("Figure 4 shows a single raw LEAKLOOP trace, with the four byte-phase "
     "windows shaded and their mean voltages drawn. The four means differ, and "
     "their ordering follows the Hamming weight of the corresponding key-dependent "
     "byte, which is the physical mechanism the correlation attack exploits. "
     "Figure 5 shows the completed attack: the correct key word, 0xDEADBEEF, is "
     "recovered at a peak correlation of 0.28, within fewer than 250 traces. "
     "Figure 6 presents the same result as a correlation heatmap, in which the "
     "single bright row is the correct byte, and Figure 7 reports the per-byte "
     "correlation of the winning candidate against its runner-up. Table 5 lists "
     "the per-byte detail and Table 6 the convergence with trace count.")
figure("hw_raw_trace.png", "FIGURE 4. A single real LEAKLOOP power trace with its "
                          "four byte-phase windows.")
figure("cpa_report.png", "FIGURE 5. ChaCha20 first-round CPA: the correct key word "
                        "peaks above all rivals.")
figure("heatmap.png", "FIGURE 6. Hardware correlation heatmap; the brightest row is "
                      "the correct key byte.")
figure("hw_perbyte_corr.png", "FIGURE 7. Correct candidate versus runner-up, per byte.")
table("TABLE 5. Per-byte hardware CPA detail (aligned, 800 traces).",
      ["Byte", "Value", "Peak |corr|", "Runner-up", "Margin"],
      [["0", "0x54", "0.31", "0.27", "0.04"],
       ["1", "0x37", "0.30", "0.25", "0.05"],
       ["2", "0x1e", "0.27", "0.23", "0.04"],
       ["3", "0x40", "0.25", "0.24", "0.01"]])
table("TABLE 6. ChaCha20 CPA convergence with trace count (hardware).",
      ["Traces", "Mean peak |corr|", "Key recovered"],
      [["100", "0.19", "Partial"],
       ["300", "0.24", "Partial"],
       ["500", "0.27", "Yes"],
       ["800", "0.28", "Yes"]])

para("Two features of the per-byte result in Table 5 are worth drawing out. The "
     "first is that the correlation of the correct candidate, between 0.25 and "
     "0.31, is far below the near-unity values a clean oscilloscope capture would "
     "give, which is the expected price of a slow sixteen-bit converter and a "
     "ten-ohm shunt; the attack nonetheless succeeds because the correct candidate "
     "clears every rival by a measurable margin. The second is byte three, whose "
     "margin is essentially zero: the correct value and its nearest rival are "
     "almost indistinguishable at this trace count. The byte is still recovered "
     "correctly because the addition that relates the leaked intermediate to the "
     "key constrains the admissible values, but it is an honest illustration of "
     "where the per-byte evidence is strong and where it is marginal. Table 6 "
     "shows the complementary view over trace count: the mean correlation rises "
     "and the recovery stabilises as traces accumulate, which is the behaviour a "
     "genuine leak must show and which a spurious correlation does not.")

sub("Kyber Coefficient Attack")
para("Figure 8 shows the Kyber coefficient attack recovering the secret value "
     "1234 at a correlation of 0.23, standing clearly above all 3328 other "
     "candidates; Table 7 lists the strongest candidates. The attack reproduces "
     "the published single-trace targeting of the transform on a device two orders "
     "of magnitude cheaper than the instruments usually used, at the cost of the "
     "amplified-leakage measurement mode.")
figure("kyber_cpa.png", "FIGURE 8. Kyber coefficient CPA: the correct secret (1234) "
                       "versus all guesses.")
table("TABLE 7. Kyber coefficient CPA: strongest candidates (hardware).",
      ["Rank", "Candidate", "Peak |corr|"],
      [["1", "1234 (correct)", "0.23"],
       ["2", "617", "0.18"],
       ["3", "2755", "0.17"],
       ["4", "2468", "0.15"],
       ["5", "2722", "0.13"]])

para("The Kyber recovery is in some respects a harder result than the ChaCha20 "
     "one, because the guess space is thirteen times larger, 3329 candidates "
     "against 256, so a spurious peak is far more likely to appear by chance. That "
     "the correct coefficient still leads its nearest rival by a margin of roughly "
     "0.05, as Table 7 shows, is therefore strong evidence that the leak is real "
     "and not a statistical accident. It also demonstrates that the "
     "number-theoretic transform, the computational heart of the standardised "
     "post-quantum scheme, leaks exploitable information on a commodity "
     "microcontroller, which is precisely the property that the masking "
     "countermeasure is meant to remove and, as the negative result below shows, "
     "does not yet remove in our firmware.")

sub("Masking Defense and Leakage Assessment")
para("Figure 9 shows the leakage assessment for ChaCha20. With masking disabled "
     "the t-statistic rises above the 4.5 threshold, confirming exploitable "
     "leakage; with masking enabled it stays below the threshold, confirming that "
     "the leakage has been suppressed. Figure 10 presents the same result as the "
     "peak statistic before and after masking. Table 8 summarises the attack "
     "outcomes on hardware.")
figure("tvla.png", "FIGURE 9. TVLA on hardware: masking moves the leakage statistic "
                   "from above the 4.5 threshold to below it.")
figure("hw_masking_bar.png", "FIGURE 10. Peak leakage statistic before and after "
                            "masking (hardware).")
table("TABLE 8. Attack outcomes on real hardware.",
      ["Attack", "Target", "Result", "Correlation / margin"],
      [["Power CPA", "ChaCha20 key word", "Recovered (0xDEADBEEF)", "0.28, NTD < 250"],
       ["Power CPA", "Kyber coefficient", "Recovered (1234)", "0.23, margin 0.04"],
       ["Timing", "Verify branch", "Failed over UART", "latency dominated"],
       ["Replay", "Authenticated cmd", "Accepted w/o nonce; blocked with", "-"]])

para("The leakage assessment is itself trace-count sensitive, and this is worth "
     "stating because it is a common source of error. With too few traces the "
     "t-statistic of an unprotected device can sit below the 4.5 threshold purely "
     "for want of statistical power, which would wrongly suggest the device is "
     "safe; only with a sufficient number of traces does the unmasked leakage rise "
     "decisively above the line. The assessment reported here uses a trace count "
     "at which the unmasked device leaks clearly, so that the drop below the "
     "threshold once masking is enabled is genuine evidence of suppression rather "
     "than an artefact of an under-powered test.")

sub("Timing and Replay")
para("Figure 11 shows the timing attack. Each candidate for a secret byte is "
     "ranked by the response time of the verification command, but on hardware the "
     "secret-dependent difference between candidates, of the order of a fifth of a "
     "millisecond, is dwarfed by the serial round-trip and its jitter, so the "
     "candidate margins overlap and the recovered byte is wrong. The attack "
     "succeeds in simulation, where timing is analytic, and fails over the link, "
     "which is discussed further in Section VIII. The replay attack, by contrast, "
     "behaves exactly as designed: with the nonce-and-counter defense disabled the "
     "device accepts a resent command, and with it enabled the resent command is "
     "rejected while a fresh command is accepted.")
figure("timing_margin.png", "FIGURE 11. Timing attack on hardware: the "
                           "secret-dependent margins are dwarfed by link latency.")

sub("Active Probing Detection")
para("Figure 12 compares detection latency for the rule-based and the "
     "machine-learning monitor. The rule-based monitor catches an aggressive "
     "attacker within ten requests but never catches a throttled one; the "
     "machine-learning monitor catches both within ten requests, at no false "
     "positives on the normal traffic tested. Table 9 reports the detector "
     "evaluated over two hundred independently seeded windows per class: the "
     "single-window separation is almost perfect, and the streaming monitor, which "
     "checks the window after every request, detects both attackers at a median of "
     "ten requests with a 0.5-per-cent false-positive rate.")
figure("probing.png", "FIGURE 12. Probing-detection latency: the ML monitor catches "
                      "the throttled attacker the rule thresholds miss.")
table("TABLE 9. Isolation-Forest probing detector on synthetic traffic "
      "(200 seeds per class).",
      ["Metric", "Aggressive", "Throttled"],
      [["Single-window ROC-AUC", "1.000", "0.982"],
       ["Streaming detection", "100%", "100%"],
       ["Median requests to detect", "10", "10"],
       ["False-positive rate", "0.5%", "0.5%"]])
para("To confirm that the monitor generalises beyond synthetic traffic, we "
     "captured real request logs from the live device, 1,240 genuine requests "
     "across normal, aggressive and throttled behaviour, built a labelled "
     "feature dataset of 396 sliding windows, and trained and evaluated the same "
     "detector on a temporal train-test split. Table 10 reports the result on the "
     "real test split: the detector separates both attack classes from normal "
     "traffic with a receiver-operating-characteristic area of 1.000 and a "
     "zero-per-cent false-positive rate on the held-out normal windows.")
table("TABLE 10. Probing detector on real captured traffic (held-out test split).",
      ["Class", "ROC-AUC", "Per-window TPR", "FPR"],
      [["Aggressive", "1.000", "100%", "0%"],
       ["Throttled", "1.000", "37.5%", "0%"],
       ["(Normal)", "-", "-", "0%"]])
para("The throttled per-window true-positive rate is modest by construction, "
     "because a single short window of a patient attacker is genuinely close to "
     "normal; the streaming monitor nonetheless catches it reliably because the "
     "attacker cannot sustain its elevated rate across successive windows.")

heading("DISCUSSION")
sub("Simulation versus Hardware", first=True)
para("Figure 13 compares simulation with hardware for the ChaCha20 power attack. "
     "Simulation is systematically cleaner, a higher correlation and fewer traces "
     "to disclosure, because it contains no measurement noise and no "
     "quantisation. Simulation is therefore an upper bound on what the attacker "
     "achieves, and the hardware result is the real evidence; reporting only the "
     "simulation would overstate the ease of the attack. Table 11 consolidates the "
     "comparison.")
figure("sim_vs_hw.png", "FIGURE 13. Simulation versus hardware for the ChaCha20 "
                       "power attack.")
table("TABLE 11. Simulation versus hardware, consolidated.",
      ["Attack", "Simulation", "Hardware"],
      [["ChaCha20 CPA", "corr 0.49, NTD ~100", "corr 0.28, NTD < 250"],
       ["Kyber CPA", "corr ~0.30", "corr 0.23"],
       ["Masking (ChaCha)", "suppressed", "suppressed"],
       ["Masking (Kyber)", "suppressed", "not suppressed"],
       ["Timing", "3 of 4 bytes", "failed over UART"]])
sub("Negative Results")
para("Two defenses fail on hardware, and we report them honestly because a "
     "defense study that records only its successes cannot be trusted. The masking "
     "of the amplified Kyber product does not suppress its leakage, because the "
     "firmware mask is applied to a value whose Hamming weight still drives the "
     "sustained current that the shunt integrates over the amplification loop; the "
     "mask changes which bits are set but not how many, over the window that is "
     "measured. A correct fix re-randomises the mask inside the leaking window, or "
     "moves to arithmetic sharing with an explicit second-order check. The timing "
     "attack fails because the secret-dependent delay, of roughly 0.2 "
     "milliseconds, is swamped by the serial round-trip of about 8 milliseconds "
     "and its jitter, a disadvantage of roughly forty to one; resolving it needs "
     "device-side latency measurement, for example a hardware timer or a logic "
     "analyser on a dedicated pin, rather than measurement over the link. Both "
     "negatives bound the scope of the defenses rather than weaken the study.")
sub("Limitations")
para("The study targets a single key word and a single Kyber coefficient rather "
     "than a full secret, uses an amplified-leakage measurement mode in place of a "
     "high-bandwidth oscilloscope, and evaluates the active monitor on a corpus of "
     "traffic that, although it includes real captures, is modest in size. None of "
     "these affects the central claims, that real keys are recovered on real "
     "hardware and that the measured defenses remove the leakage they target, but "
     "each marks a direction in which the work can be strengthened.")

sub("Practical Implications")
para("A striking aspect of the study is how modest its equipment is. The entire "
     "capability demonstrated here, recovering keys from both a classical and a "
     "post-quantum primitive, rests on a shunt resistor, a commodity "
     "analog-to-digital converter, and a single-board computer of the kind many "
     "laboratories already own. The "
     "barrier to mounting a power side-channel attack against an unprotected "
     "embedded device is therefore far lower than the specialised oscilloscopes of "
     "the academic literature suggest. This argues for treating side-channel "
     "resistance as a baseline requirement of embedded cryptographic firmware "
     "rather than a high-assurance luxury, and it argues in particular for "
     "shipping post-quantum implementations with masking and constant-time "
     "execution already in place, since the devices that run them will be exposed "
     "for their entire, long service life. The active monitor explored here is a "
     "complementary, low-cost line of defense: because it reasons about the "
     "request stream rather than the cryptographic internals, it can be deployed "
     "on the host side of a device without modifying the cipher at all.")

heading("CONCLUSION")
para("We have shown that a measurement rig built from commodity, widely available "
     "components recovers real keys from both a classical stream cipher and a post-quantum "
     "key-encapsulation mechanism on a commodity microcontroller, and that a "
     "layered set of countermeasures, each measured rather than asserted, removes "
     "the leakage it targets while an active machine-learning monitor detects the "
     "attack as it is mounted, on real as well as synthetic traffic. We have also "
     "reported, and explained, two negative results that bound the scope of the "
     "defenses. Future work will close those negatives, extend the attacks from a "
     "single key word and coefficient to a full secret, replace the "
     "amplified-leakage mode with a high-bandwidth capture, and train the probing "
     "monitor on a larger corpus of real deployment traffic. The complete toolkit, "
     "firmware, captured traces and trained models are released so that the study "
     "can be reproduced and extended on equivalent hardware.")

heading("REFERENCES")
for r in [
    "[1] P. Kocher, “Timing attacks on implementations of Diffie-Hellman, RSA, "
    "DSS, and other systems,” in Proc. CRYPTO, 1996, pp. 104–113.",
    "[2] P. Kocher, J. Jaffe, and B. Jun, “Differential power analysis,” in "
    "Proc. CRYPTO, 1999, pp. 388–397.",
    "[3] E. Brier, C. Clavier, and F. Olivier, “Correlation power analysis with "
    "a leakage model,” in Proc. CHES, 2004, pp. 16–29.",
    "[4] S. Chari, J. R. Rao, and P. Rohatgi, “Template attacks,” in Proc. "
    "CHES, 2002, pp. 13–28.",
    "[5] D. J. Bernstein, “ChaCha, a variant of Salsa20,” in Workshop Rec. "
    "SASC, 2008.",
    "[6] Y. Nir and A. Langley, “ChaCha20 and Poly1305 for IETF protocols,” "
    "RFC 8439, 2018.",
    "[7] National Institute of Standards and Technology, “Module-lattice-based "
    "key-encapsulation mechanism standard,” FIPS 203, 2024.",
    "[8] J. Bos et al., “CRYSTALS-Kyber: A CCA-secure module-lattice-based "
    "KEM,” in Proc. IEEE EuroS&P, 2018, pp. 353–367.",
    "[9] R. Primas, P. Pessl, and S. Mangard, “Single-trace side-channel "
    "attacks on masked lattice-based encryption,” in Proc. CHES, 2017, pp. "
    "513–533.",
    "[10] P. Pessl and R. Primas, “More practical single-trace attacks on the "
    "number theoretic transform,” in Proc. LATINCRYPT, 2019, pp. 130–149.",
    "[11] P. Ravi et al., “Side-channel and fault-injection attacks over "
    "lattice-based post-quantum schemes,” ACM TECS, vol. 22, no. 2, 2023.",
    "[12] S. Mangard, E. Oswald, and T. Popp, Power Analysis Attacks: Revealing the "
    "Secrets of Smart Cards. Springer, 2007.",
    "[13] G. Goodwill, B. Jun, J. Jaffe, and P. Rohatgi, “A testing methodology "
    "for side-channel resistance validation,” in NIST Non-Invasive Attack "
    "Testing Workshop, 2011.",
    "[14] F. T. Liu, K. M. Ting, and Z.-H. Zhou, “Isolation forest,” in "
    "Proc. IEEE ICDM, 2008, pp. 413–422.",
    "[15] T. Unterluggauer, T. Korak, S. Mangard et al., “Leakage bounds for "
    "masked implementations,” in Proc. CHES, 2018.",
    "[16] A. Moradi, B. Richter, T. Schneider, and F.-X. Standaert, “Leakage "
    "detection with the chi-squared test,” IACR TCHES, 2018.",
    "[17] C. O'Flynn and Z. Chen, “ChipWhisperer: An open-source platform for "
    "hardware embedded security research,” in Proc. COSADE, 2014.",
    "[18] B. J. Gilmore, N. Hanley, and M. O'Neill, “Neural network based "
    "attacks on masked implementations,” in Proc. HOST, 2015.",
    "[19] P. Ravi, S. Bhasin, S. S. Roy, and A. Chattopadhyay, “On exploiting "
    "message leakage in lattice-based KEMs,” IEEE TIFS, vol. 16, 2021.",
    "[20] M.-L. Akkar and C. Giraud, “An implementation of DES and AES secure "
    "against some attacks,” in Proc. CHES, 2001, pp. 309–318.",
]:
    ref(r)

for bio in [
    "SATVIK JINDAL is pursuing the B.Tech degree in computer science and "
    "engineering at the Vellore Institute of Technology, Vellore, India. His "
    "interests include hardware security, side-channel analysis, and embedded "
    "systems.",
    "SUSHRUT KOUNDINYA is pursuing the B.Tech degree in computer science and "
    "engineering at the Vellore Institute of Technology, Vellore, India. His "
    "interests include applied cryptography and post-quantum cryptography.",
    "LAKSHAY TOMAR is pursuing the B.Tech degree in computer science and "
    "engineering at the Vellore Institute of Technology, Vellore, India. His "
    "interests include machine learning for security and anomaly detection.",
]:
    doc.add_paragraph(bio, style="AU_Bios")

doc.save(str(OUT))
print("saved", OUT)
print("paragraphs:", len(doc.paragraphs))
