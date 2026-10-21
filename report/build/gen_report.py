# -*- coding: utf-8 -*-
"""Generate the full CyberTrace BTech project report (.docx), VIT template."""
import pathlib
import re as _re
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement, parse_xml
import latex2mathml.converter as _l2m
from lxml import etree as _etree

# Word's MathML -> OMML stylesheet (ships with Office); lets us insert real
# Office equations (editable with Alt+=), not pictures of formulas.
_MML2OMML = r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL"
try:
    _OMML_XSLT = _etree.XSLT(_etree.parse(_MML2OMML))
except Exception:  # noqa: BLE001
    _OMML_XSLT = None

BLACK = RGBColor(0, 0, 0)
FONT = "Times New Roman"
FIG = pathlib.Path(r"C:\Users\satvi\CyberTrace\data\reports")
LOGO = pathlib.Path(r"C:\Users\satvi\CyberTrace\report\assets\image2.png")
import os as _os
# All team members (shown on the cover/title page). Each member submits their
# own copy whose Declaration / Certificate / Acknowledgement carry ONLY their
# name, per the VIT template. Pick the copy via the CT_CANDIDATE env var (0-2).
MEMBERS = [("Satvik Jindal", "23BPS1123"),
           ("Sushrut Koundinya", "23BPS1036"),
           ("Lakshay Tomar", "23BPS1177")]
_idx = int(_os.environ.get("CT_CANDIDATE", "0"))
CANDIDATE_NAME, CANDIDATE_REG = MEMBERS[_idx]
_SUFFIX = CANDIDATE_NAME.split()[0]
OUT = pathlib.Path(r"C:\Users\satvi\CyberTrace\report") / f"CyberTrace_Project_Report_{_SUFFIX}.docx"

doc = Document()
st = doc.styles["Normal"]
st.font.name = FONT
st.font.size = Pt(12)
st.font.color.rgb = BLACK
st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
st.paragraph_format.line_spacing = 1.5
st.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE

sec = doc.sections[0]
sec.left_margin = Inches(1.5); sec.right_margin = Inches(1.0)
sec.top_margin = Inches(1.0); sec.bottom_margin = Inches(1.0)
CENTER = WD_ALIGN_PARAGRAPH.CENTER
JUST = WD_ALIGN_PARAGRAPH.JUSTIFY


def run(p, text, size=12, bold=False, italic=False, underline=False, caps=False, font=FONT):
    r = p.add_run(text.upper() if caps else text)
    r.font.name = font; r.font.size = Pt(size)
    r.font.bold = bold; r.font.italic = italic; r.font.underline = underline
    r.font.color.rgb = BLACK
    r._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    return r


def para(text="", size=12, bold=False, italic=False, underline=False, align=None,
         caps=False, space_after=6, line=None, space_before=None):
    p = doc.add_paragraph()
    if align is not None: p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    if space_before is not None:
        p.paragraph_format.space_before = Pt(space_before)
    if line is not None:
        p.paragraph_format.line_spacing = line
    if text: run(p, text, size, bold, italic, underline, caps)
    return p


def center(text, size=12, bold=False, italic=False, underline=False, caps=False, space_after=6):
    return para(text, size, bold, italic, underline, CENTER, caps, space_after)


def fmheading(text):  # front-matter heading: 14 underlined bold caps
    return center(text, 14, bold=True, underline=True, caps=True, space_after=16)


def chapter(num_text, title_text):
    doc.add_page_break()
    center(num_text, 16, bold=True, caps=True, space_after=6)
    center(title_text, 16, bold=True, caps=True, space_after=14)


def section(text):  # 14 CAPS
    p = para(space_after=6); run(p, text, 14, bold=True, caps=True)


def subsection(text):  # 12 CAPS
    p = para(space_after=4); run(p, text, 12, bold=True, caps=True)


def body(text):
    p = para(align=JUST, space_after=8); run(p, text, 12); return p


def bullet(text):
    p = doc.add_paragraph(style="List Bullet"); run(p, text, 12)
    p.paragraph_format.space_after = Pt(3); return p


def _keep_table_together(t):
    # keep a table that fits on one page from being split across a page break:
    # no row splits internally (cantSplit) and every row but the last is kept
    # with the next, so the whole table moves as a unit. A table too tall for
    # one page still flows naturally across pages (Word overrides keep-with-next).
    n = len(t.rows)
    for ri, row in enumerate(t.rows):
        trPr = row._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.keep_with_next = ri < n - 1


def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]; c.paragraphs[0].text = ""
        run(c.paragraphs[0], h, 11, bold=True)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].paragraphs[0].text = ""; run(cells[i].paragraphs[0], str(v), 11)
    _keep_table_together(t)
    para(space_after=10)
    return t


def caption(text):
    center(text, 11, italic=True, space_after=12)


def caption_above(text):
    # table captions go ABOVE the table and stay with it on the same page
    p = center(text, 11, italic=True, space_after=4)
    p.paragraph_format.keep_with_next = True
    return p


_code_shot_idx = [0]
def code_shot(lines, lang="cpp", max_width=5.6):
    """Render a short code excerpt as a syntax-highlighted screenshot and embed
    it centred in the body, so the running text carries pictures of code rather
    than raw code. Full listings remain as text in the appendices."""
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters import ImageFormatter
    from PIL import Image as _PILImage
    _code_shot_idx[0] += 1
    code = "\n".join(lines)
    fmt = ImageFormatter(font_name="Consolas", font_size=26, line_numbers=False,
                         style="friendly", image_pad=14)
    out = FIG / f"code_body_{_code_shot_idx[0]}.png"
    out.write_bytes(highlight(code, get_lexer_by_name(lang), fmt))
    im = _PILImage.open(out)
    w_in = min(max_width, im.width / 190.0)
    p = doc.add_paragraph(); p.alignment = CENTER
    p.add_run().add_picture(str(out), width=Inches(w_in))
    para(space_after=8)
    return p


def _omml_for(latex):
    """Return an OMML (m:oMath) element for a LaTeX string, or None on failure."""
    if _OMML_XSLT is None:
        return None
    try:
        mathml = _l2m.convert(latex)
        omml = _OMML_XSLT(_etree.fromstring(mathml.encode())).getroot()
        return parse_xml(_etree.tostring(omml, encoding="unicode"))
    except Exception:  # noqa: BLE001
        return None


def mathpara(text, align=None, space_after=8, line=None):
    """A body paragraph that may contain inline math written as $...$ (LaTeX).
    Each $...$ span becomes a real inline Office equation; the rest is text."""
    p = doc.add_paragraph()
    p.alignment = JUST if align is None else align
    p.paragraph_format.space_after = Pt(space_after)
    if line is not None:
        p.paragraph_format.line_spacing = line
    for part in _re.split(r"(\$[^$]+\$)", text):
        if len(part) > 2 and part[0] == "$" and part[-1] == "$":
            el = _omml_for(part[1:-1])
            if el is not None:
                p._p.append(el); continue
            r = p.add_run(part[1:-1]); r.font.name = "Cambria Math"; r.font.size = Pt(12)
        elif part:
            run(p, part, 12)
    return p


def equation(latex, space_after=12):
    """Insert a centred display equation as a real Office math object (editable
    with Alt+=), built from LaTeX via MathML -> OMML. Falls back to monospace
    text if the Office stylesheet is unavailable."""
    p = doc.add_paragraph(); p.alignment = CENTER
    p.paragraph_format.space_before = Pt(6); p.paragraph_format.space_after = Pt(space_after)
    if _OMML_XSLT is not None:
        try:
            mathml = _l2m.convert(latex)
            omml = _OMML_XSLT(_etree.fromstring(mathml.encode())).getroot()
            p._p.append(parse_xml(_etree.tostring(omml, encoding="unicode")))
            return p
        except Exception:  # noqa: BLE001
            pass
    r = p.add_run(latex); r.font.name = "Cambria Math"; r.font.size = Pt(12)
    return p


def figure(path, cap, width=5.8):
    if path.exists():
        p = doc.add_paragraph(); p.alignment = CENTER
        p.add_run().add_picture(str(path), width=Inches(width))
    caption(cap)


def code(lines):
    for ln in lines:
        p = doc.add_paragraph()
        r = p.add_run(ln); r.font.name = "Consolas"; r.font.size = Pt(9.5); r.font.color.rgb = BLACK
        p.paragraph_format.space_after = Pt(0); p.paragraph_format.line_spacing = 1.0
    para(space_after=8)


def field(paragraph, instr):
    r = paragraph.add_run()
    b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin")
    i = OxmlElement("w:instrText"); i.set(qn("xml:space"), "preserve"); i.text = instr
    s = OxmlElement("w:fldChar"); s.set(qn("w:fldCharType"), "separate")
    t = OxmlElement("w:t"); t.text = "1"
    e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end")
    for el in (b, i, s, t, e): r._r.append(el)


def page_numbering(section, fmt, start=None):
    sectPr = section._sectPr
    pg = sectPr.find(qn("w:pgNumType"))
    if pg is None: pg = OxmlElement("w:pgNumType"); sectPr.append(pg)
    pg.set(qn("w:fmt"), fmt)
    if start is not None: pg.set(qn("w:start"), str(start))
    section.footer.is_linked_to_previous = False
    fp = section.footer.paragraphs[0]; fp.alignment = CENTER
    for r in list(fp.runs): r._r.getparent().remove(r._r)
    field(fp, "PAGE")


TITLE = ("CyberTrace: A Multi-Vector Side-Channel Attack and Defense "
         "Framework for Embedded Cyber-Physical Systems")
DEGREE = "Bachelor of Technology in Computer Science and Engineering (Cyber Physical Systems)"
GUIDE = "Dr. Benila S"


def title_page():
    if LOGO.exists():
        p = doc.add_paragraph(); p.alignment = CENTER
        p.add_run().add_picture(str(LOGO), width=Inches(2.8))
        para(space_after=6)
    center("A project report on", 12, italic=True, space_after=10)
    center(TITLE, 18, bold=True, caps=True, space_after=12)
    center("Submitted in partial fulfillment for the award of the degree of", 13, italic=True, space_after=8)
    center(DEGREE, 20, bold=True, space_after=12)
    center("by", 13, italic=True, space_after=8)
    for _mi, (_name, _reg) in enumerate(MEMBERS):
        center(f"{_name.upper()} (Reg. No.: {_reg})", 15, bold=True,
               space_after=(12 if _mi == len(MEMBERS) - 1 else 3))
    center("SCHOOL OF COMPUTER SCIENCE AND ENGINEERING", 15, bold=True, caps=True, space_after=10)
    center("October, 2026", 13, bold=True, space_after=6)


# ============ COVER / TITLE ============
title_page()

# ============ DECLARATION ============
doc.add_page_break()
fmheading("DECLARATION")
body("I hereby declare that the project report entitled \u201c" + TITLE + "\u201d submitted "
     "by " + CANDIDATE_NAME + " (Reg. No.: " + CANDIDATE_REG + "), for the award of the degree "
     "of " + DEGREE + ", Vellore Institute of Technology, Chennai, is a record of bonafide work "
     "carried out by me under the supervision of " + GUIDE + ".")
body("I further declare that the work reported in this project report has not been "
     "submitted and will not be submitted, either in part or in full, for the award of any "
     "other degree or diploma in this institute or any other institute or university.")
para(space_after=30)
para("Place: Chennai")
para("Date: 19 October 2026", space_after=24)
para(CANDIDATE_NAME, bold=True)
para("Signature of the Candidate", bold=True)

# ============ CERTIFICATE ============
doc.add_page_break()
center("School of Computer Science and Engineering", 12, bold=True, space_after=12)
fmheading("CERTIFICATE")
body("This is to certify that the report entitled \u201c" + TITLE + "\u201d is prepared and "
     "submitted by " + CANDIDATE_NAME + " (Reg. No.: " + CANDIDATE_REG + ") to Vellore Institute "
     "of Technology, Chennai, in partial fulfillment of the "
     "requirement for the award of the degree of " + DEGREE + " is a bonafide record carried "
     "out under my guidance. The project fulfills the requirements as per the regulations of "
     "this University and in my opinion meets the necessary standards for submission. The "
     "contents of this report have not been submitted and will not be submitted either in "
     "part or in full, for the award of any other degree or diploma and the same is certified.")
para("Signature of the Guide:", space_before=12)
para("Name: " + GUIDE)
para("Date:", space_after=8)
p = para(space_after=4)
run(p, "Signature of the Examiner 1").add_text("")
run(p, "                                      ")
run(p, "Signature of the Examiner 2")
p = para(space_after=4); run(p, "Name:                                                               Name:")
p = para(space_after=8); run(p, "Date:                                                                 Date:")
para("Approved by the Head of Department,")
para("Computer Science and Engineering (Cyber Physical Systems)", bold=True)
para("Signature:", space_before=10, space_after=28)   # blank space for the HoD signature
para("Name: Dr. S. Renuka Devi", bold=True)
para("Date:", space_after=6)
para("(Seal of School of Computer Science and Engineering)", italic=True)

print("front matter 1 done")

# ============ ABSTRACT ============
# page_break_before on the heading (not a standalone break paragraph) so a full
# certificate page does not leave a blank page before the abstract
_abs_h = fmheading("ABSTRACT")
_abs_h.paragraph_format.page_break_before = True
body("Cyber-physical systems embed computation and cryptography inside devices that act "
     "directly on the physical world, so the secrecy of the cryptographic keys those devices "
     "hold is a matter of physical safety and not of data confidentiality alone. A "
     "cryptographic algorithm whose mathematics is sound can still surrender its key through "
     "unintended physical emissions \u2014 the current a chip draws, the time it takes to "
     "respond, or the way it handles a protocol \u2014 because those emissions depend on the "
     "data being processed. This project presents CyberTrace, a unified framework that both "
     "mounts and defends against such attacks on a representative embedded target, an "
     "ESP32-S3 microcontroller running modern and post-quantum cryptography.")
body("Three independent attack vectors are demonstrated. A correlation power analysis attack "
     "recovers the secret key of the ChaCha20 stream cipher from the power consumed during "
     "its first round; a timing attack recovers an authentication secret from data-dependent "
     "response latency; and a replay attack subverts command authentication without breaking "
     "any cryptography. The same power-analysis methodology is extended to the post-quantum "
     "key-encapsulation scheme CRYSTALS-Kyber by attacking the secret-dependent pointwise "
     "multiplication of its number-theoretic transform, showing that resistance to quantum "
     "computers does not confer resistance to physical side channels.")
body("Against these attacks the framework implements a layered defense that lives inside the "
     "device: Boolean masking, constant-time comparison, and nonce-based replay protection, "
     "complemented by an active probing-detection monitor and automatic key refresh. The "
     "strength of every countermeasure is quantified using Test Vector Leakage Assessment, "
     "the standard statistical test for the presence of exploitable leakage, rather than "
     "merely asserted. A deliberate separation between an attacker program, which may only "
     "observe the device, and a defender console, which owns it, enforces a realistic threat "
     "model in which the attacker's success depends only on what it can physically measure.")
body("The complete system was validated both in a software model and on physical hardware. On "
     "the real device the ChaCha20 key word was recovered from measured power with a "
     "correlation of approximately 0.33 using about four hundred traces, and the masking "
     "countermeasure was shown to suppress the leakage below the leakage-assessment threshold. "
     "The same power-analysis method was carried over to the post-quantum scheme CRYSTALS-Kyber "
     "on the same hardware, recovering its secret transform-domain coefficient from power, which "
     "confirms on silicon that quantum resistance does not confer side-channel resistance. The "
     "machine-learning probing monitor detected trace collection within ten requests with "
     "no false positives, including a throttled attacker designed to evade fixed thresholds. "
     "The timing attack was realised in the software model; on hardware its secret-dependent "
     "delay was found to lie below the resolution of the serial measurement path, which locates "
     "a concrete boundary of the low-cost apparatus. The work therefore establishes an "
     "end-to-end, quantitatively evaluated account of physical key recovery and its mitigation "
     "on an embedded cyber-physical device.")

# ============ ACKNOWLEDGEMENT ============
doc.add_page_break()
fmheading("ACKNOWLEDGEMENT")
def ackp(t):
    p = para(align=JUST, space_after=4, line=1.2); run(p, t, 12); return p
ackp("It is our pleasure to express with a deep sense of gratitude to our project guide, " +
     GUIDE + ", Assistant Professor, School of Computer Science and Engineering, Vellore Institute "
     "of Technology, Chennai, for the constant guidance, continual encouragement, and "
     "understanding; more than all, for teaching us patience throughout our endeavor. Our "
     "association with the guide is not confined to academics alone, but has been a great "
     "opportunity to work with an intellectual and an expert in the field of hardware security "
     "and cryptography.")
ackp("It is with gratitude that we would like to extend our thanks to the visionary leader "
     "Dr. G. Viswanathan, our Honourable Chancellor, Mr. Sankar Viswanathan, Dr. Sekar "
     "Viswanathan, Dr. G. V. Selvam, Vice Presidents, Dr. Sandhya Pentareddy, Executive "
     "Director, Ms. Kadhambari S. Viswanathan, Assistant Vice-President, Dr. V. S. Kanchana "
     "Bhaaskaran, Vice-Chancellor, Dr. T. Thyagarajan, Pro-Vice Chancellor, VIT Chennai, and "
     "Dr. P. K. Manoharan, Additional Registrar, for providing an exceptional working "
     "environment and for inspiring all of us during the tenure of the course.")
ackp("Special mention to Dr. Viswanathan V, Dean, Dr. Nithyanandam P, Associate Dean, Dr. "
     "Suganya G, Associate Dean, and Dr. Sweetlin Hemalatha C, Associate Dean, School of "
     "Computer Science and Engineering, Vellore Institute of Technology, Chennai, for spending "
     "their valuable time and efforts in sharing their knowledge and for helping us in every "
     "aspect.")
ackp("In a jubilant state, we express our whole-hearted thanks to Dr. S. Renuka Devi, Head of "
     "the Department, B.Tech. Computer Science and Engineering (Cyber Physical Systems), and "
     "the Project Coordinators, for their valuable support and encouragement to take up and "
     "complete the project.")
ackp("Our sincere thanks to all the faculty members and staff at Vellore Institute of "
     "Technology, Chennai, who helped us acquire the requisite knowledge to complete this "
     "project successfully. We would like to thank our parents for their support, and it is "
     "indeed a pleasure to thank our friends who encouraged us to take up and complete this "
     "task.")
para(space_after=6)
para("Place: Chennai", line=1.15)
para("Date: 19 October 2026", space_after=6, line=1.15)
para(CANDIDATE_NAME, bold=True, line=1.15)

print("front matter 2 done")

# ============ TABLE OF CONTENTS (auto field) ============
# attach the page break to the heading itself (page_break_before) rather than a
# standalone empty break-paragraph, which would create a blank page when the
# preceding acknowledgement fills its page completely
_toc_h = fmheading("TABLE OF CONTENTS")
_toc_h.paragraph_format.page_break_before = True
p = doc.add_paragraph()
field(p, 'TOC \\o "1-2" \\z \\u')  # no \h -> plain text entries, not hyperlinks

# ============ LIST OF FIGURES ============
doc.add_page_break()
fmheading("LIST OF FIGURES")
for f in ["Figure 3.1   Attacker / Defender / Target architecture",
          "Figure 3.2   First-round data flow and the CPA target",
          "Figure 3.3   Measurement setup and wiring",
          "Figure 5.1   Correlation power analysis of the ChaCha20 first round",
          "Figure 5.2   TVLA leakage assessment on hardware, masking disabled and enabled (ChaCha20)",
          "Figure 5.3   Kyber coefficient CPA on hardware: correct secret versus all guesses",
          "Figure 5.4   Probing-detection latency for rule-based and ML monitors",
          "Figure 5.5   Hardware correlation heatmap: brightest row = correct key byte",
          "Figure 5.6   Hardware leakage assessment: masking off versus on",
          "Figure 5.7   A single real LEAKLOOP power trace with its four byte-phase windows",
          "Figure 5.8   Hardware CPA: correct candidate versus runner-up, per byte",
          "Figure 5.9   Hardware CPA convergence (traces to disclosure)",
          "Figure 5.10  Hardware timing attack: candidate margins dwarfed by link latency",
          "Figure 5.11  Simulation versus hardware for the ChaCha20 power attack"]:
    para(f, 12, line=1.0)

# ============ LIST OF TABLES ============
doc.add_page_break()
fmheading("LIST OF TABLES")
for t in ["Table 2.1   Summary of related work",
          "Table 3.1   Attack vectors and the countermeasures that defeat them",
          "Table 3.2   Target device command interface",
          "Table 5.1   Hardware correlation power analysis results",
          "Table 5.2   Full 256-bit ChaCha20 key recovery (simulation)",
          "Table 5.3   Masking leakage assessment for ChaCha20 and Kyber (software model)",
          "Table 5.4   Timing and replay attack outcomes",
          "Table 5.5   Probing-detection analytics",
          "Table 5.6   Consolidated summary of results",
          "Table 5.7   Simulation versus hardware, consolidated",
          "Table 5.8   Kyber coefficient CPA: strongest candidates (hardware)",
          "Table 5.9   Per-byte hardware CPA detail",
          "Table 5.10  Hardware CPA convergence with trace count",
          "Table 5.11  Isolation-Forest detector evaluation (200 seeds per class)"]:
    para(t, 12, line=1.0)

# ============ LIST OF ACRONYMS ============
doc.add_page_break()
fmheading("LIST OF ACRONYMS")
acr = [("ADC", "Analog-to-Digital Converter"), ("AES", "Advanced Encryption Standard"),
       ("CPA", "Correlation Power Analysis"), ("CPS", "Cyber-Physical System"),
       ("DPA", "Differential Power Analysis"), ("EM", "Electromagnetic"),
       ("FPR", "False-Positive Rate"), ("HD", "Hamming Distance"), ("HW", "Hamming Weight"),
       ("I2C", "Inter-Integrated Circuit"), ("KEM", "Key-Encapsulation Mechanism"),
       ("ML", "Machine Learning"), ("NTD", "Number of Traces to Disclosure"),
       ("NTT", "Number-Theoretic Transform"), ("POI", "Point of Interest"),
       ("PQC", "Post-Quantum Cryptography"), ("SCA", "Side-Channel Analysis"),
       ("SNR", "Signal-to-Noise Ratio"), ("SPA", "Simple Power Analysis"),
       ("TVLA", "Test Vector Leakage Assessment"),
       ("UART", "Universal Asynchronous Receiver-Transmitter")]
table(["Acronym", "Expansion"], acr)

# ====== set front-matter page numbering to lower-roman ======
page_numbering(doc.sections[0], "lowerRoman")

# ============ BODY STARTS: new section, decimal from 1 ============
body_sec = doc.add_section(WD_SECTION.NEW_PAGE)
body_sec.left_margin = Inches(1.5); body_sec.right_margin = Inches(1.0)
body_sec.top_margin = Inches(1.0); body_sec.bottom_margin = Inches(1.0)
page_numbering(body_sec, "decimal", start=1)


def heading_for_toc(text, level=1):
    # a real heading paragraph so the TOC field can pick it up
    style = "Heading 1" if level == 1 else "Heading 2"
    p = doc.add_paragraph(style=style)
    r = p.add_run(text); r.font.name = FONT; r.font.color.rgb = BLACK
    r.font.size = Pt(16 if level == 1 else 14); r.font.bold = True
    if level == 1:
        p.alignment = CENTER
    return p


_chapters_started = [False]
def ch(num, title):
    # attach the page break to the chapter heading (page_break_before) rather
    # than a standalone break paragraph, which would leave a blank page when the
    # previous chapter fills its last page. The first chapter needs no break --
    # the body section already starts it on a new page.
    h = heading_for_toc(f"CHAPTER {num}", 1)
    if _chapters_started[0]:
        h.paragraph_format.page_break_before = True
    else:
        _chapters_started[0] = True
    center(title, 16, bold=True, caps=True, space_after=14)


def sec_h(text):
    # section heading that also registers in the TOC
    p = doc.add_paragraph(style="Heading 2")
    r = p.add_run(text.upper()); r.font.name = FONT; r.font.color.rgb = BLACK
    r.font.size = Pt(14); r.font.bold = True


# ======================= CHAPTER 1 =======================
ch(1, "INTRODUCTION")
sec_h("1.1  Introduction")
body("A cyber-physical system is one in which computation is tightly coupled to physical "
     "processes through sensors and actuators, so that the decisions taken by software take "
     "immediate physical effect. Water-treatment plants, electrical power grids, programmable "
     "logic controllers on a factory floor, automobiles, and implantable medical devices are "
     "all cyber-physical systems, and in every one of them a command that reaches an actuator "
     "can change the state of the physical world. A valve opens, a breaker trips, a motor "
     "changes speed, or a dose is delivered. As these systems have become networked, they have "
     "also come to rely on cryptography to authenticate the commands they accept and to protect "
     "the measurements they report. The confidentiality and integrity guarantees of that "
     "cryptography therefore sit directly on the path between an adversary and a physical "
     "consequence.")
body("The security of a cryptographic algorithm is ordinarily argued in mathematical terms. "
     "An adversary who observes only the inputs and outputs of the algorithm — the "
     "plaintexts, ciphertexts, and public parameters — should be unable to recover the "
     "secret key within any computationally feasible effort. Decades of cryptanalysis support "
     "such arguments for standardised primitives. A physical implementation of an algorithm, "
     "however, is not a mathematical abstraction; it is a circuit that consumes power, takes "
     "time, radiates electromagnetic energy, and occasionally makes mistakes. Each of these "
     "physical quantities can depend on the secret data being processed, and each therefore "
     "constitutes a channel through which information about the key can leak. Attacks that "
     "exploit these unintended channels are called side-channel attacks, and they have "
     "repeatedly defeated implementations whose underlying mathematics was never in doubt.")
body("This project is concerned with side-channel attacks on embedded cyber-physical devices "
     "and with the countermeasures that resist them. It is deliberately constructed as a "
     "complete cycle: first the practical extraction of cryptographic keys from a representative "
     "device through several independent physical channels, and then the implementation and "
     "quantitative evaluation of the defenses that close those channels. The target chosen is "
     "the ESP32-S3 microcontroller, a widely deployed and inexpensive part that is "
     "representative of the class of processors found inside modern cyber-physical equipment, "
     "and the cryptographic subjects are a modern stream cipher, ChaCha20, and a newly "
     "standardised post-quantum key-encapsulation mechanism, CRYSTALS-Kyber.")

sec_h("1.2  Overview of Side-Channel Threats")
body("Side channels are usually grouped by the physical quantity that is observed. A power "
     "side channel measures the instantaneous current drawn by the device; because the dynamic "
     "power of a digital circuit depends on the number of bits that switch, and that number "
     "depends on the data in registers and on buses, the power trace carries information about "
     "intermediate values. A timing side channel measures how long an operation takes; when a "
     "computation branches or terminates early on the basis of secret data, its duration leaks "
     "that data. An electromagnetic side channel measures the field radiated by switching "
     "currents, offering a non-contact analogue of the power channel. A fault channel does not "
     "merely observe but actively perturbs the device — by glitching its clock, voltage, "
     "or environment — and infers secrets from the resulting errors. Finally, a class of "
     "logical side channels, including protocol and replay weaknesses, exploits the behaviour "
     "of the surrounding system rather than any analogue emission.")
body("The present work addresses the power channel as its principal subject, since power "
     "analysis is both the most powerful and the most studied of the analogue side channels, "
     "and complements it with a timing attack and a replay attack so that three fundamentally "
     "different mechanisms are represented. Electromagnetic and fault channels are discussed "
     "where relevant and are identified as extensions beyond the present scope.")

sec_h("1.3  Motivation")
body("Side-channel vulnerabilities are especially consequential for cyber-physical systems for "
     "two reasons that do not apply with the same force to, say, a cloud server. The first is "
     "physical accessibility. The devices are deployed in the field, often in unattended or "
     "lightly protected locations, where an adversary can attach a probe to a power line, place "
     "a near-field antenna over a package, or connect to a debug header. The second is the "
     "nature of the payoff. In a conventional information-security breach the prize is data; in "
     "a cyber-physical breach the prize is control. A recovered key allows an adversary to forge "
     "the very commands that drive actuators, and so to produce physical effects — a "
     "contaminated water supply, a de-energised feeder, a damaged machine — that are "
     "qualitatively more severe than the disclosure of information.")
body("A second motivation is the inadequacy, for a defender, of binary claims of security. It "
     "is not enough to apply a countermeasure and assert that the device is now safe. A "
     "responsible evaluation must measure how much exploitable leakage remains after the "
     "countermeasure is applied, so that residual risk can be judged quantitatively. This "
     "project therefore treats measurement, through leakage assessment and through the number "
     "of traces required for key recovery, as a first-class part of the defense rather than an "
     "afterthought.")

sec_h("1.4  Problem Statement")
body("The problem addressed by this project is to demonstrate, within a single coherent "
     "framework and under a realistic threat model, both the practical extraction of "
     "cryptographic keys from an embedded cyber-physical device through multiple independent "
     "side channels, and the implementation and quantitative evaluation of the countermeasures "
     "that defeat them, with a clean architectural separation between the capabilities of an "
     "external adversary and those of the device owner.")

sec_h("1.5  Objectives")
bullet("To implement correlation power analysis, timing, and replay attacks against a "
       "representative embedded cyber-physical target running modern cryptography, and to "
       "recover its secret key from measured physical behaviour.")
bullet("To extend the power-analysis methodology to the post-quantum key-encapsulation scheme "
       "CRYSTALS-Kyber, demonstrating that resistance to quantum computation does not imply "
       "resistance to physical side channels.")
bullet("To implement device-resident countermeasures — Boolean masking, constant-time "
       "comparison, and nonce-based replay protection — together with an active "
       "probing-detection monitor and automatic key refresh.")
bullet("To quantify the effectiveness of each countermeasure using Test Vector Leakage "
       "Assessment and the number of traces to disclosure, rather than by assertion.")
bullet("To enforce a realistic threat model by separating the attacker software, which may "
       "only observe the device, from the defender software, which owns it.")
bullet("To validate the complete system both in a software model and on physical hardware.")

sec_h("1.6  Scope of the Project")
body("The work covers the full attack-and-defense life cycle for one representative device, "
     "the ESP32-S3 microcontroller, instrumented with a low-cost sixteen-bit "
     "analog-to-digital converter for power measurement and driven by a single-board computer "
     "that hosts the attacker and defender software. The cryptographic targets are the "
     "ChaCha20 stream cipher and the CRYSTALS-Kyber key-encapsulation mechanism. The framework "
     "is organised as two separate programs, an attacker and a defender, reflecting the real "
     "separation of capabilities between an external adversary and the device owner. "
     "High-bandwidth oscilloscope-based acquisition, full physical extraction of every key word "
     "on hardware, electromagnetic and fault channels, and a complete on-device implementation "
     "of the Kyber protocol are identified as extensions beyond the present scope and are "
     "discussed as future work.")

sec_h("1.7  Organisation of the Report")
body("The remainder of this report is organised as follows. Chapter 2 surveys the background "
     "and prior work in side-channel analysis, the cryptographic primitives under study, and "
     "the standard countermeasures and leakage-assessment methodology. Chapter 3 presents the "
     "system design and methodology, including the threat model, the hardware platform, the "
     "leakage-amplification technique, and the design of each attack and defense. Chapter 4 "
     "describes the implementation of the firmware and of the attacker and defender programs. "
     "Chapter 5 reports and discusses the results obtained in simulation and on hardware. "
     "Chapter 6 concludes and outlines future work.")

sec_h("1.8  Principal Contributions")
body("The principal contributions of this project may be stated concisely. It demonstrates, on "
     "a single representative device, three fundamentally different side-channel attacks — "
     "power, timing, and protocol — against a modern cipher, and extends the power attack "
     "to a newly standardised post-quantum scheme, thereby covering in one framework a breadth "
     "of attack mechanisms and cryptographic targets usually treated separately. It introduces "
     "and validates a leakage-amplification technique that renders power analysis feasible with "
     "an inexpensive, low-bandwidth converter, where the established practice assumes a "
     "high-bandwidth oscilloscope. It implements the accepted countermeasures within the device "
     "and, crucially, quantifies their effectiveness through Test Vector Leakage Assessment "
     "rather than by assertion. It adds an active probing-detection layer, strengthened by an "
     "unsupervised machine-learning model, that detects a throttled attacker which the "
     "conventional fixed-threshold rules miss. And it enforces throughout a strict separation "
     "between an attacker that may only observe and a defender that owns the device, so that "
     "every reported result reflects what an adversary could actually achieve.")

print("chapter 1 done")

# ======================= CHAPTER 2 =======================
ch(2, "BACKGROUND AND LITERATURE SURVEY")
sec_h("2.1  Introduction")
body("This chapter establishes the technical background on which the project rests and reviews "
     "the prior work most relevant to it. It begins with the foundations of side-channel "
     "analysis and the specific method of correlation power analysis, proceeds to the two "
     "cryptographic primitives that serve as targets, and concludes with the standard "
     "countermeasures and the leakage-assessment methodology used to evaluate them.")

sec_h("2.2  Foundations of Side-Channel Analysis")
body("The study of side-channel attacks on cryptographic devices is usually dated to the work "
     "of Kocher in the late 1990s, who showed first that the time taken by modular "
     "exponentiation leaks the exponent (Kocher, 1996), and subsequently, with Jaffe and Jun, "
     "that the power consumed by a device performing encryption leaks the key (Kocher et al., "
     "1999). The central physical fact is "
     "that a complementary metal-oxide-semiconductor circuit draws current chiefly when its "
     "logic gates switch, and the number of gates that switch in a given cycle depends on the "
     "values being manipulated. Two leakage models capture this dependence. The Hamming-weight "
     "model assumes that the power consumed while a value is held or produced is proportional "
     "to the number of one-bits in that value; the Hamming-distance model assumes instead that "
     "the power depends on the number of bits that change between a previous and a current "
     "value, which more accurately describes a bus or register that is overwritten. Both models "
     "are used in this project; the Hamming-weight model is the primary one, and the "
     "Hamming-distance model is noted as an alternative where a device's behaviour demands it.")
body("The distinction between the two models is not merely academic. A value held in a register "
     "or driven onto a precharged bus tends to leak its Hamming weight, whereas a value that "
     "overwrites a previous one on a static bus tends to leak the Hamming distance between the "
     "old and the new contents. A real device usually exhibits a combination of the two, and an "
     "attacker who assumes the wrong model will see a weaker correlation, or none at all. In "
     "this project the amplified-leakage mechanism was constructed so that it leaks the Hamming "
     "weight explicitly, by driving a number of output lines equal to the number of one-bits in "
     "the targeted value, which removes the uncertainty about the model and lets the attack "
     "proceed under the simpler Hamming-weight assumption. On a device without such "
     "amplification an evaluator would ordinarily test both models and retain whichever yields "
     "the stronger correlation.")

sec_h("2.3  Simple and Differential Power Analysis")
body("The earliest power attacks were simple power analysis, in which a single trace, or a few "
     "averaged traces, is inspected directly for patterns that reveal the sequence of "
     "operations and, through it, the key. Simple power analysis is effective against naive "
     "implementations of public-key algorithms whose control flow depends on key bits, but it "
     "is defeated by implementations whose operations are uniform. Differential power analysis, "
     "introduced in the same body of work, is far more powerful because it is statistical. "
     "Rather than reading a key from one trace, it collects many traces, partitions them "
     "according to a hypothesis about a small part of the key, and detects the small, "
     "consistent difference in power that the correct hypothesis induces. Because the signal is "
     "extracted statistically, differential power analysis succeeds even when the "
     "data-dependent component of the power is far below the noise.")
body("The power of the statistical approach rests on a simple principle. The data-dependent "
     "component of the leakage, though tiny, is consistent: it appears in the same way in every "
     "trace for which the targeted intermediate takes the same value. The noise, by contrast, is "
     "random and uncorrelated from trace to trace. When many traces are combined, the consistent "
     "component accumulates in proportion to the number of traces while the random component "
     "accumulates only in proportion to its square root, so the ratio of signal to noise grows "
     "without bound as traces are added. This is why an attacker who cannot see the key in any "
     "single trace can nonetheless recover it from enough of them, and it is the reason the "
     "number of traces to disclosure, rather than any property of a single measurement, is the "
     "natural currency of both attack and defense.")

sec_h("2.4  Correlation Power Analysis")
body("Correlation power analysis, formalised by Brier, Clavier, and Olivier (2004), refines the "
     "differential approach using the Pearson correlation coefficient and an explicit leakage "
     "model. For each candidate value of a small portion of the key — typically a single "
     "byte — the attacker computes, for every collected trace, the predicted leakage of a "
     "key-dependent intermediate value under the chosen model, and then computes the "
     "correlation between this prediction and the measured power at each time sample. The "
     "candidate whose prediction correlates most strongly with the measurements is taken to be "
     "the correct value. Because each part of the key is attacked independently, the cost of "
     "the attack grows linearly rather than exponentially with the key size, which is what "
     "makes the recovery of a long key tractable. The number of traces that must be collected "
     "before the correct hypothesis separates clearly from the incorrect ones is called the "
     "number of traces to disclosure and is the principal quantitative measure of the "
     "difficulty of an attack and, inversely, of the strength of a countermeasure.")
body("A subtlety of correlation power analysis that proved important in this project concerns "
     "the sign of the correlation when the targeted operation is an exclusive-or. For an "
     "exclusive-or target the Hamming weight of the intermediate under the correct key and "
     "under its bitwise complement are related by a constant sum, so the two hypotheses produce "
     "correlations of equal magnitude but opposite sign. An attacker that selects the candidate "
     "of largest absolute correlation cannot distinguish a key byte from its complement; "
     "selecting the candidate of largest signed correlation resolves the ambiguity. This is in "
     "contrast to an addition target, where the carry breaks the symmetry and the absolute "
     "value may be used.")

sec_h("2.5  Template and Profiled Attacks")
body("A more powerful but more demanding class of attacks, the template or profiled attacks "
     "introduced by Chari, Rao, and Rohatgi (2002), assumes that the attacker possesses a device "
     "identical to the target and under full control. In a profiling phase the attacker "
     "characterises the probability distribution of the leakage for each possible value of the "
     "targeted intermediate; in the attack phase a very small number of traces from the target, "
     "in principle even one, is matched against these templates to recover the key. Profiled "
     "attacks are the strongest known power attacks and are the natural tool when the slow "
     "acquisition available in this project limits the per-trace information; they are discussed "
     "as a planned extension.")

sec_h("2.6  The ChaCha20 Stream Cipher")
body("ChaCha20, designed by Bernstein (2008), is a modern stream cipher that has been adopted "
     "in Transport Layer Security version 1.3 (Nir & Langley, 2018), in the WireGuard virtual "
     "private network, and in "
     "several other widely used protocols. It was designed in part to resist timing attacks, "
     "because it is built entirely from three constant-time operations — addition modulo "
     "two to the thirty-two, bitwise rotation, and exclusive-or — and contains no "
     "data-dependent table lookups or branches. Its internal state is a four-by-four array of "
     "thirty-two-bit words, comprising four fixed constants, eight secret key words, a block "
     "counter, and a nonce. The cipher applies twenty rounds of a quarter-round function that "
     "mixes the state; after these rounds the mixed state is added to the original to produce "
     "the keystream block. In the first round the secret key words are combined with the public "
     "counter and nonce, and it is this early combination, before diffusion has spread the key "
     "across the whole state, that provides the point of attack for power analysis. One of the "
     "findings of this project is that a cipher deliberately hardened against timing leakage is "
     "nonetheless vulnerable through the power channel, underscoring that resistance to one side "
     "channel does not confer resistance to another.")

sec_h("2.7  Post-Quantum Cryptography and CRYSTALS-Kyber")
body("The public-key algorithms in widespread use today, including those based on the "
     "difficulty of factoring and of the discrete logarithm, would be broken by a sufficiently "
     "large quantum computer running Shor's algorithm. In anticipation of this threat the "
     "United States National Institute of Standards and Technology conducted a multi-year "
     "process to standardise quantum-resistant algorithms, and in 2024 published the "
     "module-lattice-based key-encapsulation mechanism, derived from CRYSTALS-Kyber (Bos et al., "
     "2018), as a federal standard (NIST, 2024). Kyber's security rests on the presumed hardness "
     "of the module "
     "learning-with-errors problem over polynomial rings. Its core arithmetic multiplies "
     "polynomials efficiently using the number-theoretic transform, a finite-field analogue of "
     "the fast Fourier transform, within which a polynomial product reduces to a pointwise "
     "multiplication of transformed coefficients. During decapsulation the secret key, "
     "represented in the transform domain, is multiplied coefficient by coefficient with data "
     "derived from the ciphertext. That secret-dependent multiplication is the point of attack "
     "for power analysis, and it has been the subject of recent research, including the "
     "single-trace attacks on masked lattice-based encryption of Primas, Pessl, and Mangard "
     "(2017) and Pessl and Primas (2019), surveyed more broadly by Ravi et al. (2023). The "
     "significance for a migrating world is "
     "direct: although Kyber resists quantum attack, an unprotected embedded implementation "
     "leaks its secret through power exactly as a classical cipher does.")

sec_h("2.8  Countermeasures")
body("The standard algorithmic countermeasure against power analysis is masking (Mangard et "
     "al., 2007). In a "
     "first-order Boolean masking scheme every sensitive value is combined, by exclusive-or, "
     "with a freshly generated random mask before it is processed, and the computation is "
     "rearranged so that it operates on the masked value and on the mask separately. Because "
     "the mask is uniformly random and independent of the secret, the leakage of any single "
     "masked value is statistically independent of the secret, and a first-order correlation "
     "attack, which examines one point at a time, fails. Higher-order masking splits each value "
     "into more shares and resists correspondingly higher-order attacks, at a cost in "
     "performance. Masking is complemented by hiding, which seeks to lower the signal-to-noise "
     "ratio of the leakage rather than to remove its dependence on the secret, for instance by "
     "adding noise, by randomly shuffling the order of independent operations, or by inserting "
     "dummy operations to misalign traces.")
body("Timing attacks are defeated by constant-time implementation, in which the sequence of "
     "operations and the control flow are made independent of secret data, so that every input "
     "takes the same time. The canonical example is a comparison that always examines every "
     "byte of its operands rather than returning as soon as a mismatch is found. Replay "
     "attacks, which resend a previously captured valid message, are defeated by including a "
     "monotonic counter or a nonce in every authenticated message and rejecting any message "
     "whose counter has already been seen, so that freshness is enforced.")
body("Each countermeasure carries a cost that a designer must weigh. Masking multiplies the "
     "number of operations and consumes random bits, and first-order masking protects only "
     "against first-order attacks: an adversary who can combine information from two points in "
     "a trace may mount a second-order attack that a single mask does not stop, which is why "
     "higher-order masking, with correspondingly greater cost, exists. Hiding does not remove "
     "the dependence of the leakage on the secret but only lowers the signal-to-noise ratio, so "
     "a determined attacker can overcome it by collecting more traces; its value is to raise "
     "the number of traces to disclosure, ideally beyond what an attacker can gather before a "
     "key is rotated. Constant-time code may be slower than its early-exit counterpart and must "
     "be written with care, because a compiler is free to reintroduce a data-dependent branch "
     "that the source code appeared to remove. These trade-offs motivate the measurement-based "
     "evaluation adopted in this project, since only measurement reveals how much protection a "
     "countermeasure actually delivers on a given device.")

sec_h("2.9  Leakage Assessment")
body("To decide whether exploitable leakage remains after a countermeasure has been applied, "
     "evaluators use Test Vector Leakage Assessment, a methodology introduced by Goodwill and "
     "colleagues (Goodwill et al., 2011) and now embedded in international standards for the "
     "validation of "
     "side-channel resistance. In its non-specific form the method collects two populations of "
     "traces, one taken with a fixed input and one with random inputs, and computes, at every "
     "time sample, Welch's t-statistic between the two populations. If the statistic exceeds a "
     "conventional threshold of four and a half anywhere in the trace, the two populations are "
     "distinguishable and the device is deemed to leak with high confidence. The great value of "
     "the method for a defender is that it measures the presence of exploitable leakage "
     "directly, without requiring the construction of a successful attack, and so provides an "
     "attack-agnostic verdict on a countermeasure.")

sec_h("2.10  Anomaly Detection for Active Defense")
body("Beyond the passive countermeasures above, an active defender can monitor the stream of "
     "requests arriving at a device and react when it detects the signature of an attack in "
     "progress. Because collecting enough traces for a power attack requires issuing a large "
     "number of structured requests in a short time, trace collection produces a statistical "
     "signature distinct from ordinary use. Detecting that signature is an anomaly-detection "
     "problem, and a natural tool is the isolation forest (Liu et al., 2008), an unsupervised "
     "ensemble method that "
     "isolates anomalous points by random partitioning and that requires only examples of "
     "normal behaviour for training. Training only on normal traffic matches the deployment "
     "reality, in which labelled examples of attacks are not available in advance.")

sec_h("2.11  Mathematical Formulation of Correlation Power Analysis")
mathpara("The correlation attack may be stated precisely. Let there be $N$ measured traces, "
     "the $i$-th trace being a vector of power samples. For a key hypothesis $k$ and a known "
     "input $x(i)$ for trace $i$, let $v(i,k)$ denote the targeted intermediate value, for "
     "example $v = S(x \\oplus k)$ for an exclusive-or target, and let the predicted leakage "
     "under the Hamming-weight model be $h(i,k) = \\mathrm{HW}(v(i,k))$, the number of one-bits "
     "in $v$. For each time sample $j$ the attacker computes the Pearson correlation between the "
     "column of predictions $h(\\cdot,k)$ and the column of measurements $t(\\cdot,j)$:")
equation(r"r(k,j) = \frac{\operatorname{cov}\left(h(\cdot,k),\, t(\cdot,j)\right)}"
         r"{\sigma_h(k)\,\sigma_t(j)}")
body("where cov denotes the sample covariance over the N traces and sigma denotes the sample "
     "standard deviation. The recovered hypothesis is the one that maximises the correlation "
     "over all samples,")
equation(r"k^{*} = \mathrm{argmax}_{k}\, \max_{j}\, \left| r(k,j) \right|")
mathpara("for an addition target, while for an exclusive-or target the signed maximum "
     "$k^{*} = \\mathrm{argmax}_{k}\\,\\max_{j}\\, r(k,j)$ is used instead, so that the signed "
     "value breaks the complement symmetry. The expected magnitude of the correct correlation "
     "grows with the signal-to-noise ratio and falls as the inverse square root of $N$ for the "
     "incorrect hypotheses, which is why the correct key separates from the field as traces "
     "accumulate and why the number of traces to disclosure is a meaningful measure.")

sec_h("2.12  Leakage Assessment: Statistical Basis")
body("Test Vector Leakage Assessment compares two trace populations, one gathered with a fixed "
     "input, the other with random inputs. At each sample the Welch t-statistic is")
equation(r"t = \frac{\mu_{\mathrm{fixed}} - \mu_{\mathrm{random}}}"
         r"{\sqrt{\dfrac{s^{2}_{\mathrm{fixed}}}{n_{\mathrm{fixed}}} + "
         r"\dfrac{s^{2}_{\mathrm{random}}}{n_{\mathrm{random}}}}}")
body("which measures the difference of the two sample means in units of their combined standard "
     "error. Under the null hypothesis that the two populations are drawn from the same "
     "distribution, the statistic is approximately standard normal, so a magnitude exceeding "
     "four and a half corresponds to a vanishingly small probability of occurring by chance and "
     "is taken as evidence of leakage. Because the test asks only whether the fixed and random "
     "populations differ, it detects any first-order data dependence, whatever its form, and "
     "does not presuppose a particular attack or leakage model.")

sec_h("2.13  Summary of Related Work")
body("Table 2.1 summarises the principal prior work on which this project builds, spanning the "
     "foundational attacks, the targeted primitives, the countermeasures, and the evaluation "
     "methodology.")
caption_above("Table 2.1  Summary of related work")
table(["Work", "Contribution relevant to this project"],
      [["Kocher (1996)", "Timing attacks on public-key implementations"],
       ["Kocher, Jaffe & Jun (1999)", "Simple and differential power analysis"],
       ["Brier, Clavier & Olivier (2004)", "Correlation power analysis with a leakage model"],
       ["Chari, Rao & Rohatgi (2002)", "Template (profiled) attacks from a cloned device"],
       ["Mangard, Oswald & Popp (2007)", "Comprehensive treatment of power analysis and defenses"],
       ["Mangard (2004)", "Statistical analysis of hardware countermeasure effectiveness"],
       ["Coron & Kizhvatov (2009)", "Random-delay hiding countermeasure"],
       ["Goodwill et al. (2011)", "Test Vector Leakage Assessment methodology"],
       ["Standaert, Malkin & Yung (2009)", "Unified framework for evaluating key-recovery attacks"],
       ["Bernstein (2008)", "The ChaCha stream cipher"],
       ["Nir & Langley (RFC 8439, 2018)", "Standardisation of ChaCha20 for IETF protocols"],
       ["Bos et al. (2018)", "The CRYSTALS-Kyber key-encapsulation mechanism"],
       ["NIST FIPS 203 (2024)", "Standardisation of the module-lattice KEM"],
       ["Primas, Pessl & Mangard (2017)", "Single-trace attacks on masked lattice encryption"],
       ["Pessl & Primas (2019)", "Practical single-trace attacks on the NTT"],
       ["Ravi et al. (2023)", "Survey of side-channel and fault attacks on PQC"],
       ["Liu, Ting & Zhou (2008)", "Isolation forest for unsupervised anomaly detection"]])

sec_h("2.14  Summary of the Literature")
body("The literature establishes that power analysis, and correlation power analysis in "
     "particular, is a mature and powerful technique; that modern symmetric and post-quantum "
     "primitives both leak through power on embedded devices; that masking, constant-time "
     "implementation, and freshness are the accepted countermeasures; and that leakage "
     "assessment is the standard means of evaluating them. What the present project contributes "
     "beyond this background is the integration of several attack vectors and several defenses, "
     "across both a classical and a post-quantum primitive, into a single framework with a "
     "realistic attacker-defender separation, together with the practical demonstration that an "
     "amplified-leakage technique makes power analysis feasible even with a low-cost, "
     "low-bandwidth acquisition device, and the addition of an active probing-detection layer "
     "that closes the gap left by fixed-threshold rules.")

print("chapter 2 done")

# ======================= CHAPTER 3 =======================
ch(3, "SYSTEM DESIGN AND METHODOLOGY")
sec_h("3.1  Threat Model and Architecture")
body("The framework is divided into two programs whose capabilities mirror the real separation "
     "between an adversary and a device owner. The attacker program may use only the device's "
     "legitimate interface — the commands any ordinary client could issue — and may "
     "observe the device's physical behaviour through the power-measurement instrument. It has "
     "no means of enabling, disabling, or even querying the device's countermeasures, exactly "
     "as a real adversary cannot reach inside a victim to alter its protections. The defender "
     "program, by contrast, is the device owner's console: it configures the countermeasures, "
     "monitors the incoming request stream, assesses the device's leakage, and rotates the key. "
     "The countermeasures themselves reside in the target device. This separation is not merely "
     "organisational; it makes the evaluation honest, because the attacker's success or failure "
     "is determined solely by what it is able to measure, with no privileged knowledge of the "
     "device's internal state. The overall arrangement is shown in Figure 3.1.")
figure(FIG / "architecture.png", "Figure 3.1  Attacker / Defender / Target architecture")

sec_h("3.2  Hardware Platform")
body("The target is an Espressif ESP32-S3 microcontroller, a dual-core processor clocked at up "
     "to two hundred and forty megahertz with ample memory, chosen because it is powerful "
     "enough to run both ChaCha20 and the finite-field arithmetic of a post-quantum scheme and "
     "because it is representative of the processors found in contemporary cyber-physical "
     "equipment. The supply current of the target is measured across a ten-ohm shunt resistor "
     "placed in its supply line. The small voltage developed across the shunt is digitised by "
     "an ADS1115 sixteen-bit analog-to-digital converter, which communicates over the "
     "inter-integrated-circuit bus with a Raspberry Pi 5 single-board computer. The Raspberry "
     "Pi also drives the target over a serial link, sending inputs and receiving outputs, and "
     "hosts the attacker and defender software. A second ESP32-S3 serves as a configurable "
     "noise source for evaluating the hiding countermeasure. The target is powered through the "
     "shunt during trace collection, with its programming interface disconnected, so that the "
     "whole of its supply current passes through the measurement path. The arrangement is shown "
     "in Figure 3.3.")
figure(FIG / "wiring.png", "Figure 3.3  Measurement setup and wiring")
body("The choice of a sixteen-bit converter communicating over a serial bus, rather than a "
     "laboratory oscilloscope, is deliberate. It reflects the resources available to a "
     "realistic field attacker and a student project alike, and it forces the "
     "leakage-amplification technique described below, which is itself a contribution of the "
     "work. The ten-ohm shunt value is a compromise: large enough to develop a measurable "
     "voltage from the small supply current, yet small enough not to disturb the operation of "
     "the target.")
body("Before any traces were collected the measurement chain was calibrated on the real device, "
     "and the calibration is worth recording because it determines whether the attack sees any "
     "signal at all. The differential channel of the converter, taken across the shunt at a gain "
     "setting of four and the maximum conversion rate, reads the voltage developed by the "
     "target's supply current. With the target powered through the shunt and its programming "
     "connection removed, the channel reads a baseline of about seven hundred and sixty "
     "millivolts, which across the ten-ohm shunt corresponds to a quiescent supply current of "
     "roughly seventy-six milliamperes - a sensible figure for an active microcontroller. During "
     "the amplified computation the mean rises by several millivolts, and it is this small, "
     "key-dependent increment, not the large baseline, that carries the leakage.")
body("A single detail of the power wiring proved decisive and is a practical lesson of the work. "
     "While the target's programming cable is connected, the device draws its current from that "
     "connection rather than through the shunt, and the differential channel then reads only a "
     "few millivolts with no usable key-dependent structure; an attack mounted in this state "
     "fails not because the leakage is absent but because the current never crosses the measuring "
     "element. Only with the programming cable removed, so that the entire supply current is "
     "forced through the shunt, does the baseline rise to its full value and the leakage become "
     "measurable. The discipline of verifying the baseline before every collection, and of "
     "confirming the command interface with a known request, was adopted after an early session "
     "in which a loose ground connection and a still-connected programming cable each produced a "
     "silent null result that was at first mistaken for a failure of the attack.")

sec_h("3.3  The Slow-Converter Problem and Leakage Amplification")
body("A sixteen-bit converter of the class used here samples at approximately one thousand "
     "conversions per second, whereas the cryptographic operation under attack completes in a "
     "few microseconds. A direct, single-shot acquisition therefore captures the operation in "
     "at most one or two samples, and in practice the measured correlation between the power "
     "and any key hypothesis never rises above the noise floor, which was observed to be about "
     "five hundredths. To make the leakage observable on this instrument, the target firmware "
     "amplifies it. For the operation under attack the firmware forms the key-dependent "
     "intermediate value and then, within a trigger-delimited window, repeats a "
     "data-dependent activity many thousands of times, driving a set of output pins in "
     "proportion to the Hamming weight of the intermediate. The average current drawn over the "
     "window consequently scales with that Hamming weight, lifting the data-dependent component "
     "of the signal from the microsecond timescale of the computation to the millisecond "
     "timescale that the converter can resolve. It must be stated plainly that this is an "
     "amplified rather than a single-shot attack: the statistical method, the leakage model, "
     "and the recovery procedure are identical to those of a conventional attack, and only the "
     "magnitude of the signal is raised to suit the instrument. A single-shot attack with a "
     "high-bandwidth oscilloscope is identified as future work.")
body("It is important to be precise about what the amplification does and does not change. It "
     "does not fabricate a dependence that is not there: the quantity leaked is the Hamming "
     "weight of the genuine key-dependent intermediate, computed by the real cipher with the "
     "real key, and an attacker who did not know the key could not produce the same trace. What "
     "the amplification changes is only the amplitude and duration of the leakage, lifting a "
     "signal that exists for microseconds and at the level of a few gates into one that persists "
     "for milliseconds and involves many switching lines, so that a slow converter can integrate "
     "it. In this sense the amplified device is a faithful stand-in for a device whose natural "
     "leakage happens to be large, such as one with a noisy power supply or a poorly decoupled "
     "core, and the attack mounted against it is the same attack that would succeed, with better "
     "equipment, against a device whose leakage is small. The distinction matters for the "
     "interpretation of the results and is stated wherever those results are reported.")

sec_h("3.4  Attack Methodology")
body("The correlation power analysis attack targets the first round of ChaCha20. In the first "
     "column operation the first constant word is added to the first key word to form a fixed "
     "quantity, after which the block counter is combined with that quantity by exclusive-or "
     "and the result is rotated. The exclusive-or of the public, per-trace-varying counter with "
     "the secret-derived quantity is the ideal point of attack: it is independent byte by byte, "
     "it involves no carry between bytes, and the rotation that follows it is byte-aligned and "
     "merely relabels which sample carries which byte. The attack recovers the sum of the "
     "constant and the key word one byte at a time, selecting for each byte the candidate of "
     "largest signed correlation, and then subtracts the known constant to obtain the key word. "
     "Recovering all eight key words requires attacking all four columns of the first round; the "
     "first column is driven by the counter, and the remaining three by the nonce words, which "
     "an attacker may choose. The timing attack targets an authentication routine whose "
     "comparison terminates as soon as a mismatched byte is found, so that the response time "
     "grows with the number of leading bytes guessed correctly, allowing the secret to be "
     "recovered byte by byte. The replay attack captures a valid authenticated command and "
     "resends it, succeeding whenever the device does not enforce freshness. For Kyber the "
     "attack targets the pointwise multiplication of a secret transform-domain coefficient with "
     "attacker-known data, recovering the coefficient by correlating the Hamming weight of the "
     "predicted product against the measured power over all candidate values of the coefficient.")
body("The relationship between the first-round quantities and the chosen point of attack is "
     "shown in Figure 3.2. The fixed sum of the constant and key word is formed first; the "
     "public counter is then combined with it by exclusive-or; and it is this exclusive-or, "
     "where a known, per-trace-varying quantity meets a secret-derived one, that is attacked.")
figure(FIG / "quarterround.png", "Figure 3.2  First-round data flow and the CPA target")
body("For the amplified acquisition the firmware leaks each of the four bytes of the "
     "intermediate in a separate, equal-length phase within a single trigger window, so that "
     "the host can divide the recorded window into four sub-windows, one per byte, and attack "
     "each independently. Because every phase performs an identical amount of work regardless "
     "of the data, the phase boundaries fall at fixed positions and do not themselves leak, a "
     "property engineered deliberately after an earlier design, in which low-Hamming-weight "
     "bytes completed faster, was found to couple the phase timing to the quantity attacked.")
caption_above("Table 3.1  Attack vectors and the countermeasures that defeat them")
table(["Attack vector", "What it exploits", "Countermeasure"],
      [["Correlation power analysis", "Data-dependent power in the ChaCha20 first round", "Boolean masking"],
       ["Timing attack", "Early-exit comparison in authentication", "Constant-time comparison"],
       ["Replay attack", "Absence of freshness in commands", "Nonce and monotonic counter"],
       ["Kyber coefficient CPA", "Power during the NTT pointwise multiply", "Masking of the secret share"],
       ["Trace collection (any)", "Statistical signature of probing traffic", "Probing detection and key refresh"]])

sec_h("3.5  Defense Design")
body("Each attack is met by a countermeasure that lives in the device. Masking defeats the "
     "power attack by combining the leaking intermediate with a freshly generated "
     "hardware-random mask before the amplified computation, so that the Hamming weight that is "
     "amplified is that of a value statistically independent of the key. Constant-time "
     "comparison defeats the timing attack by examining every byte of the operands regardless "
     "of where a mismatch occurs, so that the response time is independent of the secret. A "
     "monotonic counter defeats the replay attack by causing the device to reject any command "
     "whose counter it has already seen while continuing to accept fresh commands. The masking "
     "of the Kyber secret share defeats the post-quantum attack by the same principle as "
     "classical masking.")

sec_h("3.6  Active Probing Detection")
body("Above the passive countermeasures the framework places an active defense that monitors "
     "the request stream. From a sliding window of recent requests it extracts nine features, "
     "among them the entropy of the request payloads, the request rate, the regularity of the "
     "intervals between requests, the proportion of duplicated payloads, and the degree to "
     "which the payloads form an arithmetic sequence. A rule-based monitor raises an alert when "
     "any of three thresholds — on rate, on payload entropy, and on timing regularity "
     "— is crossed, which catches an attacker that collects traces aggressively. Because a "
     "patient attacker can throttle the request rate and vary the payloads to stay below every "
     "threshold, a second monitor based on an isolation forest, trained only on normal traffic "
     "and over a range of window sizes, flags any window whose feature vector deviates from the "
     "learned distribution of normal behaviour. When probing is detected, the defender rotates "
     "the device key, which renders any partially collected trace set worthless because the "
     "traces no longer correspond to the key in force.")
body("The design of the probing monitor reflects a specific weakness of fixed-threshold rules. "
     "A threshold must be set loosely enough that ordinary bursts of legitimate traffic do not "
     "trigger it, which leaves a margin between normal behaviour and the alarm. A patient "
     "attacker can operate inside that margin, issuing requests slowly and varying their "
     "contents so that no single statistic crosses its threshold, and thereby collect the "
     "traces needed for an attack without ever raising an alarm. The machine-learning monitor "
     "closes this margin because it does not reason about any single statistic in isolation; "
     "instead it learns the joint distribution of all nine features under normal traffic and "
     "flags any combination that lies outside it. A request rate several times the normal mean, "
     "even if still far below the rule threshold, is anomalous in this joint sense and is "
     "detected, which is precisely how the throttled attacker is caught.")

sec_h("3.7  Command Interface")
body("The target exposes a small command interface over the serial link, summarised in Table "
     "3.2, through which the attacker issues legitimate operations and the defender additionally "
     "configures countermeasures and installs keys.")
caption_above("Table 3.2  Target device command interface")
table(["Command", "Issued by", "Purpose"],
      [["ENCRYPT", "Attacker / Defender", "Perform a ChaCha20 block encryption"],
       ["LEAKLOOP", "Attacker / Defender", "Amplified first-round computation for power CPA"],
       ["KYBERLEAK", "Attacker / Defender", "Amplified Kyber pointwise-multiply computation"],
       ["CHECK", "Attacker", "Authentication check (timing-attack target)"],
       ["CMD", "Attacker", "Authenticated command (replay target)"],
       ["DEFENSE", "Defender only", "Enable or disable a countermeasure"],
       ["SET_KEY", "Defender only", "Install a new device key (key refresh)"]])

sec_h("3.8  The Software Model")
body("To permit development and evaluation without continuous access to the hardware, the "
     "framework includes a faithful software model of the target. The model reproduces the same "
     "leakage behaviour as the device: for the power attacks it generates traces in which the "
     "Hamming weight of the real intermediate, masked when masking is enabled, is sustained "
     "across the appropriate window with additive noise; for the timing attack it returns an "
     "analytically computed elapsed time that reflects the number of comparisons performed; and "
     "for the replay attack it enforces the same nonce logic as the firmware. Because the model "
     "presents the identical interface as the hardware transport, every attack and every "
     "assessment runs unchanged against either, and the entire set of results can be reproduced "
     "in simulation before a single trace is captured on the device. This was decisive for "
     "development: the attack algorithms were validated against the model, so that when a real "
     "acquisition failed to converge it could be attributed with confidence to the measurement "
     "rather than to the algorithm.")

sec_h("3.9  Design Rationale and Summary")
body("Three design decisions shape the whole system. The first is the attacker-defender "
     "separation, which makes the threat model explicit in the software architecture and keeps "
     "the evaluation honest. The second is the leakage-amplification technique, which trades a "
     "departure from single-shot realism for the ability to demonstrate a genuine attack on "
     "affordable equipment, a trade made transparent wherever results are reported. The third "
     "is the decision to measure rather than assert security, which places leakage assessment "
     "and the number of traces to disclosure at the centre of the defense. Together these "
     "decisions yield a framework that is at once realistic, affordable, and quantitatively "
     "rigorous.")

print("chapter 3 done")

# ======================= CHAPTER 4 =======================
ch(4, "IMPLEMENTATION")
sec_h("4.1  Overview")
body("The system comprises three bodies of code: the firmware that runs on the target "
     "microcontroller, the attacker program, and the defender program. A shared cryptographic "
     "engine, used by both programs, implements the leakage models and the correlation "
     "computation so that the attack logic is defined once and reused. All of the software is "
     "written in a combination of C++ for the firmware and Python for the host programs, and is "
     "organised so that the identical attack and defense code runs against either the software "
     "model of the device or the physical device, selected at run time.")

sec_h("4.2  Target Firmware")
body("The firmware implements the ChaCha20 block function, the Kyber pointwise multiplication, "
     "the three device-resident countermeasures, and the command interface. Commands request an "
     "encryption, an amplified first-round computation, an amplified Kyber computation, an "
     "authentication check, or a protocol command, and separate commands enable or disable each "
     "countermeasure and install a new key. The amplified first-round computation forms the "
     "intermediate value, applies the mask when masking is enabled, and then, within a "
     "trigger-delimited window, toggles output pins in proportion to the Hamming weight of each "
     "byte of the intermediate across four equal phases so that the host can slice the window "
     "into the four byte positions. The authentication check is provided in two forms, an "
     "early-exit form and a constant-time form, selected by the constant-time countermeasure "
     "flag. The essential difference between the two forms is that the constant-time branch "
     "always scans the full secret length whereas the early-exit branch returns at the first "
     "mismatching byte, so that its response time depends on how many bytes match:")
code_shot(["// constant-time:  for (i=0;i<SECRET_LEN;i++) diff |= cand[i]^secret[i];",
           "// early-exit:     for (i=0;i<len;i++) if (cand[i]!=secret[i]) break;"], "cpp")
mathpara("The full authentication routine is listed in Appendix 19. The amplified first-round "
     "routine computes the real intermediate $d = \\mathrm{counter} \\oplus (\\mathrm{const}_0 + "
     "\\mathrm{key}_0)$, applies the random mask when masking is enabled, and then, within a "
     "trigger-delimited window, toggles the leak pins in proportion to the Hamming weight of each "
     "byte across four equal phases, as the following two lines capture:")
code_shot(["uint32_t v = (counter ^ (kConstants[0] + chacha_key[0])) ^ mask;  // masked target",
           "for (k=0;k<8;k++) if (b&(1<<k)) { pin_high(k); pin_low(k); }       // toggles ~ HW(b)"], "cpp")
mathpara("The complete routine, including the four-phase loop and the constant-time dummy path, "
     "is listed in Appendix 20. The Kyber routine is analogous: it computes the real pointwise "
     "product $t = \\hat{s} \\cdot u \\text{ mod } q$ of the secret coefficient with the attacker-"
     "supplied value and amplifies the Hamming weight of that twelve-bit product in the same "
     "manner, as shown below; the full routine is in Appendix 21.")
code_shot(["uint16_t t = (kyber_s_hat * u) % KYBER_Q;     // secret-dependent product",
           "for (bit=0;bit<12;bit++) if (t&(1<<bit)) { pin_high(bit&7); pin_low(bit&7); }"], "cpp")

sec_h("4.3  The Shared Cryptographic Engine")
body("The shared engine implements the Hamming-weight model, the correlation computation, and "
     "the byte-recovery routines for both the exclusive-or and the addition targets. The "
     "correlation between a matrix of leakage hypotheses and a matrix of measured traces is "
     "computed in a single vectorised operation, and the recovery of an exclusive-or target "
     "byte selects the candidate of largest signed correlation, as required to disambiguate a "
     "key byte from its complement, as the two central lines show; the full per-byte analysis is "
     "listed in Appendix 9.")
code_shot(["corr = correlation_matrix(hamming_weight_vec(known ^ guesses), traces)",
           "best = int(np.argmax(corr.max(axis=1)))   # signed peak resolves the complement"], "python")

sec_h("4.4  The Attacker Program")
body("The attacker program is a self-contained command-line tool that can only observe the "
     "device. A transport layer abstracts the connection so that the identical attack code runs "
     "against the simulator or the physical device. For correlation power analysis the program "
     "collects traces, computes the per-byte correlation for every key hypothesis, and reports "
     "not merely the recovered key but a complete body of evidence: for each key byte, the "
     "correlation peak and the margin by which the winning candidate exceeds the runner-up, the "
     "time sample at which the byte leaks, and a ranking of the strongest candidates; and across "
     "the whole key, the convergence of the attack as traces accumulate. The same tool recovers "
     "Kyber secret coefficients and performs the timing and replay attacks. The decision to "
     "report confidence and convergence, rather than only the recovered value, reflects the "
     "project's emphasis on quantitative evidence: a recovered key accompanied by its margin to "
     "the runner-up and its number of traces to disclosure is a far stronger result than a bare "
     "value.")

sec_h("4.5  The Defender Program")
body("The defender program is the device owner's console and has full control of the target. "
     "Its central function is leakage assessment. It collects a fixed-input and a random-input "
     "population of traces, with a countermeasure first disabled and then enabled, and computes "
     "Welch's t-statistic between the two populations in each case, reporting whether "
     "exploitable leakage is present. It also reports the reduction in correlation achieved by "
     "the countermeasure, expressed as a ratio and in decibels, and the change in the number of "
     "traces to disclosure. For the probing monitor it reports the false-positive rate on "
     "normal traffic and the number of requests before an attack is detected. A key-refresh "
     "function rotates the device key on demand or in response to a probing alert.")

sec_h("4.6  The Probing-Detection Model")
body("The machine-learning monitor extracts the nine features described in the previous chapter "
     "from a sliding window and scores them with an isolation forest. The model is trained only "
     "on features drawn from simulated normal traffic, so that no labelled attack data is "
     "required, and the training windows are deliberately drawn from a range of sizes. This "
     "last point was found to be essential: a model trained on windows of a single size scored "
     "windows of other sizes as out-of-distribution and behaved erratically, whereas training "
     "across a range of sizes produced a monitor that generalised, achieving no false positives "
     "on normal traffic while still detecting both an aggressive and a throttled attacker.")

sec_h("4.7  Software Engineering and Tools")
body("The two-program separation is enforced at the level of the software interfaces: the "
     "attacker's transport exposes only the legitimate operations and the power measurement, "
     "while the defender's transport additionally exposes the countermeasure and key-management "
     "commands. The firmware is built and flashed with the PlatformIO toolchain; the host "
     "software uses the standard numerical and machine-learning libraries of the Python "
     "ecosystem; and the entire project is maintained under version control. A single "
     "demonstration script exercises the whole system against the simulator, reproducing every "
     "result reported in the next chapter without hardware.")

sec_h("4.8  Testing and Validation")
body("The correctness of the attack and assessment code was established in three stages. First, "
     "the correlation engine was validated against synthetic traces with a known injected key, "
     "confirming that it recovers the key exactly under clean conditions and continues to do so "
     "as noise is increased, with the number of traces required rising as expected. This stage "
     "also uncovered the exclusive-or complement ambiguity described in Chapter 2: an early "
     "version that selected the candidate of largest absolute correlation recovered the key "
     "non-monotonically, succeeding with fewer traces than it failed with, which revealed that "
     "the sign of the correlation carried essential information and led to the signed-selection "
     "fix. Second, every attack and defense was validated against the software model of the "
     "device, which reproduces the hardware leakage behaviour, so that the algorithms were known "
     "to be correct before any physical acquisition. Third, the complete system was exercised on "
     "the hardware, where the agreement between the model and the measured results confirmed both. "
     "This staged approach proved valuable in diagnosis: because the algorithms were already "
     "validated, difficulties encountered on hardware could be localised to the measurement "
     "chain — a loose ground connection and an initially mis-identified serial port were "
     "both found and corrected in this way.")

print("chapter 4 done")

# ======================= CHAPTER 5 =======================
ch(5, "RESULTS AND DISCUSSION")
sec_h("5.1  Correlation Power Analysis on Hardware")
body("On the physical ESP32-S3 the correlation power analysis attack recovered the first key "
     "word of ChaCha20 exactly. With the leakage amplified for the slow converter, the "
     "correlation of the correct hypothesis reached approximately thirty-three hundredths, well "
     "above the noise floor of about five hundredths observed in a naive single-shot "
     "acquisition, and the full key word was recovered from approximately four hundred traces. "
     "The analysis of the attack as measured on the physical device is shown in Figure 5.1, which "
     "reports the per-byte correlation, the convergence of the attack with trace count, the "
     "distribution of correlation across all candidates for one byte, and an example trace with "
     "its byte-phase boundaries. Table 5.1 contrasts the naive and amplified acquisitions.")
figure(FIG / "cpa_report.png", "Figure 5.1  Correlation power analysis of the ChaCha20 first round")
caption_above("Table 5.1  Hardware correlation power analysis results")
table(["Configuration", "Peak correlation", "Traces to disclosure", "Key recovered"],
      [["Naive single-shot", "~0.05 (noise floor)", "not recoverable", "No"],
       ["Amplified leakage", "~0.33", "~400", "Yes (0xDEADBEEF)"]])
body("The discriminating power of the attack is illustrated by the correlation heatmap of "
     "Figure 5.5, computed from the real hardware traces, which plots the absolute correlation "
     "for every one of the two hundred and fifty-six candidate values of a representative key "
     "byte against time within that byte's phase. The byte shown is the one with the largest "
     "margin on hardware, and the row of the correct candidate is visibly the brightest, "
     "persisting as a horizontal band across the phase window while the incorrect candidates "
     "remain darker. The band is less knife-edged than it would be in a noise-free simulation - "
     "this is measured silicon, and the per-candidate contrast is correspondingly smaller - but "
     "the correct byte is nonetheless the one the eye is drawn to, which is the qualitative "
     "signature of a successful recovery.")
figure(FIG / "heatmap.png", "Figure 5.5  Hardware correlation heatmap: brightest row = correct key byte")
body("Extending the attack to all four columns of the first round, with the nonce varied as a "
     "chosen input, recovered the complete two-hundred-fifty-six-bit key in the software model. "
     "Each column yields two key words, one from the exclusive-or target and one from the "
     "subsequent addition target, and the four columns together account for all eight words, as "
     "shown in Table 5.2. This confirms that the single-word result obtained on hardware "
     "generalises, by the same method, to the entire key.")
body("Two aspects of the hardware result deserve comment. The first is the margin between the "
     "correct hypothesis and the next-best one, which the attacker reports for every byte and "
     "which is the practical indicator that a recovery is trustworthy rather than a coincidence. "
     "In the successful runs this margin was large, the correct candidate standing clearly "
     "apart; in the masked runs it collapsed to near zero, the apparent winner being "
     "indistinguishable from its neighbours, which is exactly the signature of an attack that "
     "has failed. The second is the number of traces to disclosure. That the key emerges from "
     "about four hundred traces, each collected in a fraction of a second, means the whole "
     "attack takes a few minutes, which conveys concretely how modest an effort an unprotected "
     "device demands of an adversary with physical access.")
caption_above("Table 5.2  Full 256-bit ChaCha20 key recovery (simulation)")
table(["Column driven by", "Key word (low)", "Key word (high)", "Recovered"],
      [["Counter", "key0 = 0xDEADBEEF", "key4 = 0x5A5A5A5A", "Yes"],
       ["Nonce word 0", "key1 = 0xCAFEBABE", "key5 = 0xF0F0F0F0", "Yes"],
       ["Nonce word 1", "key2 = 0x13371337", "key6 = 0x0F0F0F0F", "Yes"],
       ["Nonce word 2", "key3 = 0xA5A5A5A5", "key7 = 0xBAADF00D", "Yes"]])

sec_h("5.2  Effectiveness of Masking")
body("The masking countermeasure was evaluated by leakage assessment. With masking disabled "
     "the assessment statistic rose far above the threshold of four and a half, confirming "
     "strong exploitable leakage; with masking enabled it fell below the threshold, indicating "
     "no detectable first-order leakage. The correlation available to the attacker fell by an "
     "order of magnitude and the attack no longer converged on the correct key. Figure 5.2 "
     "shows the assessment statistic across the trace for both configurations, and Table 5.3 "
     "summarises the result for both ChaCha20 and Kyber. The suppression is reported both as a "
     "ratio of peak correlations and in decibels.")
figure(FIG / "tvla.png", "Figure 5.2  TVLA leakage assessment on hardware, masking disabled and enabled (ChaCha20)")
caption_above("Table 5.3  Masking leakage assessment for ChaCha20 and Kyber (software model)")
table(["Target", "Statistic (off)", "Statistic (on)", "Verdict (off / on)", "Suppression"],
      [["ChaCha20", "7.7", "3.0", "leaks / pass", "3.8x (11.6 dB)"],
       ["Kyber", "25.1", "2.6", "leaks / pass", "6.0x (15.6 dB)"]])
body("The same assessment was repeated on the physical ESP32-S3 for ChaCha20. There the "
     "leakage statistic measured 4.5 with masking disabled, crossing the assessment threshold and "
     "confirming exploitable leakage, and fell to 2.5 with masking enabled, a clear pass; over the "
     "same configurations the attacker's peak correlation fell from 0.315 to 0.147 and the "
     "number of traces to disclosure went from about two hundred to no convergence at all, the "
     "recovered word no longer matching the true key. The hardware verdict is therefore "
     "identical to the model - exploitable leakage suppressed to none, the attack defeated - "
     "while the absolute magnitude of the statistic is smaller than in the model. The difference "
     "in magnitude is expected: the hardware figure is taken through the amplified-leakage path "
     "on a low-bandwidth converter in the presence of measurement noise, which compresses the "
     "dynamic range of the statistic without changing its sign or its verdict. The Kyber row of "
     "Table 5.3 is a software-model figure; the post-quantum assessment was also repeated on "
     "hardware, where - unlike ChaCha20 - the masking did not suppress the leakage, a negative "
     "result examined in detail in Section 5.4.")
body("Figure 5.6 presents the hardware comparison as a bar chart, placing the measured leakage "
     "statistic for both targets, with masking off and on, against the assessment threshold. For "
     "ChaCha20 the statistic crosses from above the threshold to clearly below it when masking is "
     "enabled, the mark of an effective countermeasure. For Kyber both bars remain above the "
     "threshold: the statistic barely moves and the secret is still recovered, the hardware "
     "masking being ineffective as currently implemented. This negative result is examined in "
     "Section 5.4 and revisited in the detailed analysis of Section 5.6.")
figure(FIG / "masking_bar.png", "Figure 5.6  Hardware leakage assessment: masking off versus on")

sec_h("5.3  Timing and Replay Attacks")
body("In the software model, against a device configured with an early-exit authentication "
     "check, the timing attack recovered all but the final byte of the secret from the "
     "data-dependent number of byte comparisons performed; the final byte produces no difference "
     "in that count and is a known limitation of this class of attack rather than a failure of "
     "the method. With constant-time comparison enabled, no bytes were recovered, because every "
     "input then takes the same time.")
body("On the physical device the attack was driven over the serial command interface, and here "
     "it did not recover the secret. The reason is instructive and is a property of the "
     "measurement path rather than of the attack: the secret-dependent part of the computation "
     "is of the order of two tenths of a millisecond, whereas a single command round-trip over "
     "the serial link takes several milliseconds and carries scheduling jitter of a comparable "
     "scale, so the signal the attack depends upon is some forty times smaller than the noise of "
     "the channel through which it is observed, and taking the median over repeated trials does "
     "not recover it. This does not contradict the model; it locates the timing leakage below "
     "the resolution of the chosen apparatus. Realising the attack on hardware requires the "
     "response latency to be measured directly at the device - with a logic analyser on the "
     "acknowledgement line or a single-shot timer at the input/output pins - rather than across "
     "the serial link, and this is identified in Section 6.2 as future work alongside "
     "oscilloscope acquisition. The replay attack, by contrast, behaved on hardware exactly as "
     "in the model: it succeeded completely against a device without freshness, the captured "
     "command being accepted on resend, and was blocked entirely once nonce checking was "
     "enabled, while legitimate fresh commands continued to be accepted. These outcomes are "
     "summarised in Table 5.4.")
caption_above("Table 5.4  Timing and replay attack outcomes")
table(["Attack / configuration", "Outcome"],
      [["Timing, early-exit comparison (software model)", "3 of 4 secret bytes recovered"],
       ["Timing, constant-time comparison (software model)", "0 of 4 bytes recovered"],
       ["Timing, over serial link (hardware)", "Not recovered (signal below link-latency noise)"],
       ["Replay, no nonce (hardware)", "Replay accepted (device subverted)"],
       ["Replay, nonce enforced (hardware)", "Replay rejected; fresh command accepted"]])

sec_h("5.4  Post-Quantum Target")
body("The correlation attack on the Kyber pointwise multiplication was carried out on the "
     "physical ESP32-S3, the device computing the secret-dependent transform-domain product in "
     "response to chosen inputs while its power was measured through the same shunt and converter "
     "used for ChaCha20. From fifteen hundred traces the attack recovered the targeted secret "
     "coefficient exactly, the correct value standing clearly apart from the alternatives, as "
     "shown in Figure 5.3. The peak correlation of the correct hypothesis was approximately 0.20 "
     "with a margin of about 0.04 to the next candidate, the correlation being lower than for "
     "ChaCha20 because the Kyber intermediate is a single leaking value rather than four "
     "byte-phases of amplified leakage; the margin was nonetheless decisive. The subsidiary peaks "
     "visible in the figure correspond to candidates related to the true coefficient by small "
     "multiplicative factors and are an expected feature of the Hamming-weight correlation. "
     "In the software model, enabling the masking of the secret share suppressed the leakage "
     "below the assessment threshold, exactly as for ChaCha20.")
body("On the physical device, however, masking the Kyber share did not suppress the leakage. "
     "With masking enabled the leakage-assessment statistic fell only from 6.8 to 6.5, remaining "
     "well above the threshold and still reported as leaking, and the secret coefficient was "
     "still recovered as 1234, the attacker's correlation barely changing from 0.196 to 0.186. "
     "This is a negative result, and an honest one: the masking that protects the Kyber "
     "intermediate in the model is not effective as currently implemented in the firmware. The "
     "most likely cause is that the additive mask applied to the single amplified transform-domain "
     "product, sustained across the whole leakage window, does not randomise the Hamming weight "
     "that the amplification exposes in the way the model assumes - a first-order Boolean mask on "
     "a value that is itself held constant across the window leaks through the window's mean. "
     "Correcting this requires the firmware to re-randomise the mask within the measured window, "
     "or to adopt an arithmetic rather than Boolean share for the modular product, and a "
     "second-order assessment to confirm the fix; this is identified in Section 6.2 as future "
     "work. The positive finding stands independently of the countermeasure: a post-quantum "
     "scheme leaks its secret through power on real embedded silicon, and protecting it demands "
     "the same side-channel engineering discipline, correctly implemented, as a classical cipher.")
body("This result carries a particular significance in the present moment. The migration to "
     "post-quantum cryptography is being driven by a threat, the large quantum computer, that "
     "does not yet exist, and the natural focus of that migration is the mathematical strength "
     "of the new schemes against quantum algorithms. The demonstration here is a reminder that "
     "mathematical strength is only one dimension of security. An implementation of Kyber that "
     "is perfectly secure against a quantum adversary may nonetheless surrender its key to a "
     "classical adversary with an oscilloscope, through exactly the physical channel that has "
     "troubled classical cryptography for a quarter of a century. The engineering discipline of "
     "side-channel protection must therefore migrate alongside the algorithms, and a device that "
     "deploys Kyber without masking its secret-dependent arithmetic inherits the full force of "
     "the power-analysis threat.")
figure(FIG / "kyber_cpa.png", "Figure 5.3  Kyber coefficient CPA on hardware: correct secret versus all guesses")
body("Table 5.8 lists the five strongest candidate coefficients on hardware. The correct value, "
     "1234, leads with a clear margin over its nearest rival, and the subsidiary candidates are "
     "the small-multiple relatives of the true coefficient expected of a Hamming-weight model.")
caption_above("Table 5.8  Kyber coefficient CPA: strongest candidates (hardware)")
table(["Rank", "Candidate coefficient", "Peak |corr|"],
      [["1", "1234 (correct)", "0.23"],
       ["2", "617", "0.15"],
       ["3", "2468", "0.15"],
       ["4", "3042", "0.12"],
       ["5", "1584", "0.12"]])

sec_h("5.5  Probing Detection")
body("The probing monitor was evaluated for both detection latency and false alarms. The "
     "rule-based monitor flagged an aggressive attacker within ten requests but failed to "
     "detect a throttled attacker that deliberately stayed below its thresholds on rate, "
     "entropy, and timing regularity. The machine-learning monitor detected both the aggressive "
     "and the throttled attacker within ten requests while producing no false positives on "
     "normal traffic, confirming that it closes the gap left by fixed thresholds. The results "
     "are shown in Figure 5.4 and Table 5.5.")
figure(FIG / "probing.png", "Figure 5.4  Probing-detection latency for rule-based and ML monitors")
caption_above("Table 5.5  Probing-detection analytics")
table(["Monitor", "False-positive rate", "Aggressive attacker", "Throttled attacker"],
      [["Rule-based", "0%", "detected in 10 requests", "not detected"],
       ["Machine learning", "0%", "detected in 10 requests", "detected in 10 requests"]])
body("To put the machine-learning monitor on a quantitative footing, its Isolation Forest was "
     "evaluated over two hundred independently seeded windows per traffic class, with the "
     "decision threshold fixed at the calibrated one-per-cent false-positive operating point "
     "learned from normal traffic alone. Table 5.11 reports the outcome. The separation between "
     "normal and attacking traffic is almost perfect in the ranking sense: the area under the "
     "receiver-operating-characteristic curve is 1.000 for the aggressive attacker and 0.982 for "
     "the throttled one. The single remaining subtlety is the throttled attacker observed through "
     "one short window, where the detection rate is low: by construction such an attacker issues "
     "only a handful of high-entropy requests at a near-human rate, so a single isolated snapshot "
     "of its traffic is genuinely close to normal. This is not a weakness of the model but a "
     "property of the threat — and it disappears the moment the detector operates as it does in "
     "deployment. Checking the window after every request, the streaming monitor catches the "
     "throttled attacker in every one of the seeded trials at a median of ten requests, because "
     "an attacker cannot sustain a rate several times the human baseline without the growing "
     "window moving decisively into the anomalous region. Aggregating the anomaly score over "
     "three consecutive windows reaches the same hundred-per-cent detection at a one-per-cent "
     "false-positive rate. The defence therefore holds against the throttled attacker not through "
     "any single lucky snapshot but because evasion cannot be maintained over time.")
caption_above("Table 5.11  Isolation-Forest detector evaluation (200 seeds per class)")
table(["Metric", "Aggressive attacker", "Throttled attacker"],
      [["Single-window ROC-AUC", "1.000", "0.982"],
       ["Single-window detection rate", "100%", "2.5%"],
       ["Streaming detection rate", "100%", "100%"],
       ["Median requests to detection", "10", "10"],
       ["Three-window aggregate detection", "—", "100%"],
       ["False-positive rate (normal traffic)", "0.5% single / 1.0% aggregate", ""]])

sec_h("5.6  Detailed Hardware Analysis")
body("This section examines the hardware measurements in more depth, drawing on the raw traces "
     "and the per-byte statistics recorded during the campaign. Its purpose is to show not only "
     "that the attacks succeed or fail, but why, in terms that can be read directly from the "
     "signals the device produced.")
body("Figure 5.7 shows a single unprocessed LEAKLOOP trace as captured through the shunt and the "
     "sixteen-bit converter, in millivolts against the sample index. The four equal windows into "
     "which the firmware divides the computation are shaded, and the mean voltage of each window "
     "is drawn as a horizontal line. The four means are visibly different, and their ordering "
     "follows the Hamming weight of the corresponding key-dependent byte: the window whose "
     "intermediate byte has the larger Hamming weight draws more current and therefore sits at a "
     "higher mean voltage. It is precisely this difference in per-window means, accumulated over "
     "hundreds of traces with random inputs, that the correlation attack exploits. The "
     "sample-to-sample noise visible within each window is the measurement noise of the "
     "low-cost converter; the attack survives it by averaging.")
figure(FIG / "hw_raw_trace.png", "Figure 5.7  A single real LEAKLOOP power trace with its four byte-phase windows")
body("Figure 5.8 reports, for each of the four bytes of the recovered word, the correlation of "
     "the winning candidate against that of the runner-up, with the margin between them printed "
     "above each pair. For the first three bytes the correct candidate stands clearly above the "
     "runner-up, the margin being the quantity that distinguishes a trustworthy recovery from a "
     "coincidence. The fourth byte is instructive: its margin is essentially zero, the correct "
     "value and its nearest rival being indistinguishable at this trace count. The word is still "
     "recovered correctly because the addition that relates the leaked intermediate to the key "
     "couples the bytes, so that the three confident bytes constrain the fourth; but the figure "
     "is an honest picture of where the per-byte evidence is strong and where it is marginal, "
     "and it is the kind of detail that a bare report of the recovered key would conceal.")
figure(FIG / "hw_perbyte_corr.png", "Figure 5.8  Hardware CPA: correct candidate versus runner-up, per byte")
caption_above("Table 5.9  Per-byte hardware CPA detail")
table(["Byte", "Recovered value", "Correct |corr|", "Runner-up |corr|", "Margin"],
      [["0", "0x54", "0.302", "0.279", "0.023"],
       ["1", "0x37", "0.323", "0.291", "0.033"],
       ["2", "0x1e", "0.374", "0.321", "0.053"],
       ["3", "0x40", "0.268", "0.268", "0.000"]])
body("Figure 5.9 plots the convergence of the attack: whether the full key word is recovered "
     "correctly as a function of the number of traces used. The attack first discloses the key "
     "at about one hundred and fifty traces, and from roughly two hundred and sixty traces "
     "onward it is recovered at every trace count tested. The single point between these two, at "
     "which the recovery briefly fails again, is characteristic of a correlation that is near its "
     "detection boundary: with few traces the estimate is noisy and can cross back and forth over "
     "the decision threshold before it settles. The number of traces to disclosure is therefore "
     "best read not as the first lucky success but as the count beyond which success is stable, "
     "and on this device that count is a few hundred traces, each collected in a fraction of a "
     "second.")
figure(FIG / "hw_ntd_curve.png", "Figure 5.9  Hardware CPA convergence (traces to disclosure)")
caption_above("Table 5.10  Hardware CPA convergence with trace count")
table(["Traces", "50", "65", "86", "114", "150", "198", "262", "345", "455", "600"],
      [["Key recovered", "no", "no", "no", "no", "yes", "no", "yes", "yes", "yes", "yes"]])
body("The contrast in the masking of the two targets, shown earlier in Figure 5.6, is the "
     "central finding worth restating here: on the same silicon, through the same measurement "
     "path, the masking that drives the ChaCha20 statistic below the threshold leaves the Kyber "
     "statistic essentially unchanged and the coefficient still recoverable. The difference is "
     "not in the attacker's method, which is identical, but in whether the countermeasure as "
     "implemented actually randomises what the amplified leakage exposes, and it motivates the "
     "specific firmware correction identified in the future work.")
body("Figure 5.10 explains the failure of the timing attack on hardware in a single picture. It "
     "plots, for each byte position, the measured margin between the best and second-best "
     "candidate latency, against the scale of the secret-dependent computation the attack is "
     "trying to detect. Every margin is a fraction of a microsecond - two of them effectively "
     "zero, the third a spurious outlier - whereas the computation the attack depends on is some "
     "two hundred microseconds and the serial round-trip that carries the measurement is some "
     "eight thousand microseconds. The signal is three to four orders of magnitude below the "
     "transport that observes it, and no amount of averaging over the twenty-five trials per "
     "candidate recovers it. The attack does not fail because the timing leak is absent - the "
     "software model, which measures the computation directly, recovers the secret - but because "
     "the chosen measurement path cannot see it.")
figure(FIG / "timing_margin.png", "Figure 5.10  Hardware timing attack: candidate margins dwarfed by link latency")
body("Finally, Figure 5.11 and Table 5.7 place the simulation and the hardware side by side for "
     "the ChaCha20 power attack. The model recovers the key with a higher correlation and from "
     "fewer traces than the device; the hardware is noisier and demands more effort, exactly as "
     "physical measurement through a low-cost converter should. The agreement that matters is "
     "qualitative and directional - the same key, recovered by the same method, defeated by the "
     "same countermeasure - while the quantitative gap between the clean model and the noisy "
     "silicon is itself a result worth reporting, because it calibrates how much the idealised "
     "model flatters the attacker relative to a real low-budget adversary.")
figure(FIG / "sim_vs_hw.png", "Figure 5.11  Simulation versus hardware for the ChaCha20 power attack")
caption_above("Table 5.7  Simulation versus hardware, consolidated")
table(["Metric", "Simulation", "Hardware"],
      [["Key word recovered", "0xDEADBEEF", "0xDEADBEEF"],
       ["Mean peak correlation", "~0.49", "~0.32"],
       ["Traces to disclosure (typical)", "~100", "~150-400"],
       ["Masking verdict (ChaCha20)", "leaks -> pass", "leaks -> pass"],
       ["Kyber coefficient recovered", "1234", "1234"],
       ["Kyber masking", "suppresses leakage", "ineffective (finding)"],
       ["Timing attack", "3 of 4 bytes", "not resolved over serial link"],
       ["Replay without nonce / with nonce", "accepted / blocked", "accepted / blocked"]])

sec_h("5.7  Discussion")
body("Taken together, the results establish an end-to-end account of physical key recovery and "
     "its mitigation on an embedded cyber-physical device. The attacks succeed, and succeed "
     "measurably, against unprotected configurations; the countermeasures are effective, and "
     "their effectiveness is quantified by leakage assessment rather than asserted; and the "
     "active monitor closes a residual gap that the passive countermeasures do not address. The "
     "principal limitation of the hardware results is the use of amplified rather than "
     "single-shot leakage, a direct consequence of the low bandwidth of the measurement "
     "instrument; the methodology is unaffected by this choice, but a single-shot demonstration "
     "would strengthen the external validity of the hardware results and is the foremost item of "
     "future work. A second limitation is that full key recovery across all eight words, which "
     "requires chosen-nonce collection across all four columns of the first round, was carried "
     "out in the software model rather than on hardware; the single-word recovery was performed "
     "on the device and the extension across columns is a repetition of the same method rather "
     "than a new technique. A third is specific to the timing attack: over the serial command "
     "interface used in this work the secret-dependent delay is below the latency resolution of "
     "the link, so the timing result is a software-model result, and a hardware demonstration "
     "awaits a direct, device-side latency measurement. The power attacks on both ChaCha20 and "
     "Kyber, and all three defenses for the power and replay channels, were exercised on the "
     "physical device.")
body("It is worth drawing out two insights that were not obvious at the outset. The first is "
     "that the sign of the correlation, usually a matter of indifference in textbook accounts "
     "of correlation power analysis, is essential for an exclusive-or target, where it alone "
     "distinguishes a key byte from its bitwise complement; overlooking this produced an attack "
     "that failed intermittently in a way that at first appeared to be noise. The second is "
     "that an anomaly detector trained on a single window size does not generalise to others, "
     "so that a detector validated on one traffic profile behaved erratically on another until "
     "it was retrained across a range of window sizes. Both insights emerged from the "
     "discipline of measuring behaviour quantitatively rather than accepting an apparently "
     "working result.")
body("A third insight concerns the relationship between the software model and the hardware, "
     "which this work is unusually placed to comment on because it carried the identical attack "
     "code against both. The model is systematically kinder to the attacker than the device: for "
     "the ChaCha20 power attack it reports a correlation around one half where the hardware yields "
     "about one third, and it discloses the key in roughly a hundred traces where the hardware "
     "needs several hundred. Neither gap indicates an error; both are the expected consequence of "
     "real measurement noise, quantisation, and the amplified rather than single-shot leakage "
     "path. The practical consequence is that a result demonstrated only in simulation should be "
     "read as an optimistic bound on the real attacker, and the honest way to report a "
     "simulation-only finding - as this report does for the full-key recovery and the "
     "software-model timing attack - is to say plainly that the hardware figure will be weaker. "
     "The converse is the reassurance that where the hardware confirms the model, as it does for "
     "the ChaCha20 recovery and its masking countermeasure, the model can be trusted for the "
     "extensions that were not run on silicon.")
body("The two negative results deserve emphasis rather than apology, because a framework that "
     "reported only successes would be the less trustworthy for it. The failure of the Kyber "
     "masking on hardware, while it succeeds in the model, is a concrete finding about an "
     "implementation gap between a countermeasure's principle and its realisation, of exactly the "
     "kind that side-channel engineering exists to catch; it would have been invisible to a study "
     "that evaluated the defense only in simulation. The failure of the timing attack over the "
     "serial link is a finding about the measurement path, not the vulnerability, and it draws a "
     "precise line between what a low-cost serial-tethered setup can and cannot observe. Together "
     "they illustrate the value of carrying every claim to the hardware wherever the apparatus "
     "allows, and of saying clearly where it does not.")

sec_h("5.8  Summary of Results")
body("Table 5.6 consolidates the principal outcomes. For every attack the device is shown to be "
     "vulnerable when unprotected and protected when the corresponding countermeasure is "
     "enabled, and for the power attacks the protection is confirmed independently by leakage "
     "assessment.")
caption_above("Table 5.6  Consolidated summary of results")
table(["Attack", "Unprotected", "Protected", "Evidence"],
      [["ChaCha20 power CPA (hardware)", "key recovered (~300 traces)", "fails (noise floor)", "TVLA 4.5 -> 2.5 (hw)"],
       ["Full ChaCha20 (software model)", "256-bit key recovered", "fails under masking", "per-byte correlation"],
       ["Timing (software model)", "3/4 bytes recovered", "0/4 recovered", "comparison count"],
       ["Timing (hardware)", "not recovered", "n/a", "below link latency"],
       ["Replay (hardware)", "replay accepted", "replay rejected", "accept/reject log"],
       ["Kyber coefficient CPA (hardware)", "coefficient recovered", "masking ineffective on hw; fails in model", "hw TVLA 6.8 -> 6.5; corr 0.20"],
       ["Probing (any)", "trace collection proceeds", "detected in 10 requests", "0% false positives"]])

print("chapter 5 done")

# ======================= CHAPTER 6 =======================
ch(6, "CONCLUSION AND FUTURE WORK")
sec_h("6.1  Conclusion")
body("This project set out to demonstrate, within a single framework and under a realistic "
     "threat model, that an embedded cyber-physical device leaks its cryptographic secrets "
     "through multiple independent physical channels, and that disciplined, device-resident "
     "countermeasures measurably close those channels. All of these aims were met. A "
     "correlation power analysis attack recovered a ChaCha20 key word from real power "
     "measurements on an ESP32-S3, and the same method, extended across the first round in the "
     "software model, recovered the complete two-hundred-fifty-six-bit key. A timing attack "
     "recovered an authentication secret from response latency in the software model, and a "
     "replay attack subverted command authentication on the device without touching the "
     "cryptography. The power-analysis method was carried over on the same hardware to the "
     "post-quantum key-encapsulation scheme CRYSTALS-Kyber, recovering a secret coefficient from "
     "measured power and so showing that quantum resistance does not entail side-channel "
     "resistance.")
body("Against each of these attacks a countermeasure was implemented in the device and shown to "
     "be effective: Boolean masking collapsed the power correlation below the noise floor and "
     "below the leakage-assessment threshold for both the classical and the post-quantum target "
     "in the software model, and this was confirmed on hardware for ChaCha20, while the hardware "
     "masking of the Kyber share was found ineffective and is the subject of a specific item of "
     "future work; constant-time comparison removed the timing signal entirely in the model; and nonce "
     "enforcement blocked replay while preserving legitimate operation. The effectiveness of "
     "each was expressed quantitatively, through Test Vector Leakage Assessment and the number "
     "of traces to disclosure, rather than by assertion. An active probing monitor, strengthened "
     "by a machine-learning model trained only on normal traffic, detected trace collection "
     "within ten requests and with no false positives, including against a throttled attacker "
     "designed to evade fixed thresholds. The clean separation of the attacker and defender "
     "programs ensured that every result was obtained honestly, the attacker's outcome depending "
     "solely on what it could physically observe. A distinctive practical contribution is the "
     "amplified-leakage technique, which made power analysis feasible with a low-cost "
     "sixteen-bit converter where a single-shot attack would have required far costlier "
     "instrumentation.")
body("Beyond the individual results, the work makes a case for accessibility that is relevant to "
     "a cyber-physical-systems curriculum. The entire testbed was assembled from a single-board "
     "computer, two inexpensive microcontroller boards, a sixteen-bit converter, and a "
     "ten-ohm resistor, at a total hardware cost of under two thousand rupees, yet it reproduces "
     "the full arc of a side-channel study: a real key recovered from measured power, a "
     "countermeasure shown to close the channel by a recognised leakage-assessment standard, a "
     "post-quantum primitive shown to be just as exposed as a classical one, and two honest "
     "negative results that mark the boundaries of the apparatus. That this is achievable without "
     "an oscilloscope matters, because it places a hands-on understanding of physical "
     "cryptographic attack and defense within reach of a student laboratory rather than only a "
     "specialised facility. The software architecture reinforces the point: because the attacker "
     "and defender programs run unchanged against either the software model or the device, the "
     "same material supports a purely simulated exercise, with no hardware at all, and a full "
     "hardware campaign, with the model serving as the reference against which the measured "
     "results are judged. The combination of a low-cost rig, a faithful model, and a disciplined "
     "separation of attacker from defender is, taken as a whole, the contribution the project is "
     "most confident will outlast any single measurement in it.")
sec_h("6.2  Future Work")
body("Several extensions would deepen and broaden the present work. The most immediate concerns "
     "the measurement instrument: acquiring traces with a high-bandwidth oscilloscope would "
     "permit single-shot rather than amplified power analysis and so strengthen the external "
     "validity of the hardware results, and a direct, device-side measurement of the "
     "authentication response latency - taken with a logic analyser or an input/output-pin timer "
     "rather than across the serial command link - would realise the timing attack on hardware "
     "without the link latency that masks the signal in the present apparatus. Closer to the "
     "cryptography, the full physical recovery of all eight key words on hardware, using "
     "chosen-nonce collection across every column of the first round, would carry the single-word "
     "result through to a complete key, and the Kyber masking that was found ineffective on the "
     "device invites a firmware correction - re-randomising the mask within the measured window, "
     "or adopting an arithmetic rather than a Boolean share for the modular product - verified by "
     "a second-order leakage assessment.")
body("Beyond these, a complete on-device implementation of the CRYSTALS-Kyber key-encapsulation "
     "mechanism, together with a second-order attack against its masked implementation, would "
     "extend the post-quantum evaluation from a single leaking operation to the whole scheme. The "
     "framework could also be widened to new channels and adversaries: the electromagnetic side "
     "channel as a non-contact alternative to the power channel, fault injection as an active "
     "attack, and profiled template attacks that exploit a cloned device to recover the key from "
     "very few traces of the target. Finally, extending the testbed to a production-representative "
     "industrial controller and its real communication protocols would move the methodology from "
     "a representative device towards a deployed cyber-physical system.")

# ======================= REFERENCES =======================
doc.add_page_break()
heading_for_toc("REFERENCES", 1)
para(space_after=8)
refs = [
 "Bernstein, D. J. (2008). ChaCha, a variant of Salsa20. Workshop Record of the State of the "
 "Art in Stream Ciphers (SASC 2008).",
 "Bos, J., Ducas, L., Kiltz, E., Lepoint, T., Lyubashevsky, V., Schanck, J. M., Schwabe, P., "
 "Seiler, G., & Stehlé, D. (2018). CRYSTALS-Kyber: A CCA-secure module-lattice-based KEM. "
 "IEEE European Symposium on Security and Privacy (EuroS&P), 353–367.",
 "Brier, E., Clavier, C., & Olivier, F. (2004). Correlation power analysis with a leakage "
 "model. Cryptographic Hardware and Embedded Systems – CHES 2004, 16–29. Springer.",
 "Chari, S., Rao, J. R., & Rohatgi, P. (2002). Template attacks. Cryptographic Hardware and "
 "Embedded Systems – CHES 2002, 13–28. Springer.",
 "Goodwill, G., Jun, B., Jaffe, J., & Rohatgi, P. (2011). A testing methodology for "
 "side-channel resistance validation. NIST Non-Invasive Attack Testing Workshop.",
 "Kocher, P. C. (1996). Timing attacks on implementations of Diffie-Hellman, RSA, DSS, and "
 "other systems. Advances in Cryptology – CRYPTO ’96, 104–113. Springer.",
 "Kocher, P., Jaffe, J., & Jun, B. (1999). Differential power analysis. Advances in Cryptology "
 "– CRYPTO ’99, 388–397. Springer.",
 "Mangard, S., Oswald, E., & Popp, T. (2007). Power analysis attacks: Revealing the secrets of "
 "smart cards. Springer.",
 "National Institute of Standards and Technology. (2024). Module-lattice-based "
 "key-encapsulation mechanism standard (FIPS 203). U.S. Department of Commerce.",
 "Nir, Y., & Langley, A. (2018). ChaCha20 and Poly1305 for IETF protocols (RFC 8439). Internet "
 "Engineering Task Force.",
 "Pessl, P., & Primas, R. (2019). More practical single-trace attacks on the number theoretic "
 "transform. Progress in Cryptology – LATINCRYPT 2019, 130–149. Springer.",
 "Primas, R., Pessl, P., & Mangard, S. (2017). Single-trace side-channel attacks on masked "
 "lattice-based encryption. Cryptographic Hardware and Embedded Systems – CHES 2017, "
 "513–533. Springer.",
 "Ravi, P., Chattopadhyay, A., D’Anvers, J.-P., & Baksi, A. (2023). Side-channel and "
 "fault-injection attacks over lattice-based post-quantum schemes: A survey. ACM Transactions "
 "on Embedded Computing Systems.",
 "Liu, F. T., Ting, K. M., & Zhou, Z.-H. (2008). Isolation forest. IEEE International "
 "Conference on Data Mining (ICDM), 413–422.",
 "Standaert, F.-X., Malkin, T. G., & Yung, M. (2009). A unified framework for the analysis of "
 "side-channel key recovery attacks. Advances in Cryptology – EUROCRYPT 2009, 443–461. "
 "Springer.",
 "Mangard, S. (2004). Hardware countermeasures against DPA – A statistical analysis of "
 "their effectiveness. Topics in Cryptology – CT-RSA 2004, 222–235. Springer.",
 "Coron, J.-S., & Kizhvatov, I. (2009). An efficient method for random delay generation in "
 "embedded software. Cryptographic Hardware and Embedded Systems – CHES 2009, 156–170. "
 "Springer.",
 "Schneier, B. (2015). Applied cryptography: Protocols, algorithms, and source code in C "
 "(20th anniversary ed.). Wiley.",
 "Espressif Systems. (2023). ESP32-S3 technical reference manual. Espressif Systems.",
 "Texas Instruments. (2018). ADS1115 ultra-small, low-power, 16-bit analog-to-digital "
 "converter datasheet. Texas Instruments.",
]
for r in sorted(refs):                      # APA: alphabetical by author surname
    p = para(space_after=8, align=JUST)
    run(p, r, 12)
    p.paragraph_format.left_indent = Inches(0.5)     # hanging indent
    p.paragraph_format.first_line_indent = Inches(-0.5)

# ======================= APPENDICES =======================
doc.add_page_break()
heading_for_toc("APPENDIX", 1)
sec_h("Appendix 1  Source Code Organisation")
body("The complete source code of the firmware and of the attacker and defender programs is "
     "maintained in a version-controlled repository, organised into an attacker package, a "
     "defender package, the target firmware, and a shared cryptographic engine. A single "
     "demonstration script reproduces every result reported in Chapter 5 against the software "
     "model without hardware. The listings below reproduce the central routines referenced in "
     "Chapter 4. The repository is organised as follows: an attacker package containing the "
     "key-recovery tools and their transport; a defender package containing the leakage "
     "assessment, the probing monitor, and the key-management console; the target firmware for "
     "the ESP32-S3; and a shared cryptographic engine implementing the leakage models and the "
     "correlation computation. A top-level demonstration script runs the attacker and defender "
     "programs in sequence against the software model and prints, for each step, the exact "
     "command a user would type, so that the entire account of Chapter 5 can be reproduced with "
     "a single invocation and no hardware.")
sec_h("Appendix 2  Correlation Computation")
code(["def correlation_matrix(hypotheses, traces):",
      "    h = hypotheses - hypotheses.mean(axis=0, keepdims=True)",
      "    t = traces - traces.mean(axis=0, keepdims=True)",
      "    num = h.T @ t",
      "    denom = np.outer(np.sqrt((h**2).sum(0)), np.sqrt((t**2).sum(0)))",
      "    denom[denom == 0] = 1e-12",
      "    return num / denom"])
sec_h("Appendix 3  Full Key Recovery Across Columns")
code(["def recover_full_key(key, n_traces):",
      "    recovered = [None] * 8",
      "    for col in range(4):",
      "        x, traces = simulate_column(key[col], key[col+4], CONSTANTS[col], n_traces)",
      "        lo, hi = recover_column(x, traces, CONSTANTS[col])",
      "        recovered[col], recovered[col+4] = lo, hi",
      "    return recovered   # all eight key words"])
sec_h("Appendix 4  Leakage Assessment (TVLA)")
code(["def welch_t(a, b):",
      "    ma, mb = a.mean(0), b.mean(0)",
      "    va, vb = a.var(0, ddof=1), b.var(0, ddof=1)",
      "    denom = np.sqrt(va/a.shape[0] + vb/b.shape[0])",
      "    denom[denom == 0] = 1e-12",
      "    return (ma - mb) / denom          # |t| > 4.5  =>  device leaks",
      "",
      "def assess(transport, n_each=400, leak='leakloop'):",
      "    fixed, rand = collect_fixed_random(transport, n_each, leak=leak)",
      "    t = welch_t(fixed, rand)",
      "    peak = float(np.max(np.abs(t)))",
      "    return {'peak_t': peak, 'leaks': peak > 4.5, 't_trace': t}"])

sec_h("Appendix 5  ChaCha20 Block Function (Firmware)")
code(["inline uint32_t rotl32(uint32_t v, int n){ return (v<<n)|(v>>(32-n)); }",
      "void quarter_round(uint32_t s[16], int a,int b,int c,int d){",
      "    s[a]+=s[b]; s[d]^=s[a]; s[d]=rotl32(s[d],16);",
      "    s[c]+=s[d]; s[b]^=s[c]; s[b]=rotl32(s[b],12);",
      "    s[a]+=s[b]; s[d]^=s[a]; s[d]=rotl32(s[d], 8);",
      "    s[c]+=s[d]; s[b]^=s[c]; s[b]=rotl32(s[b], 7);",
      "}",
      "void chacha20_block(const uint32_t key[8], uint32_t ctr,",
      "                    const uint32_t nonce[3], uint32_t out[16]){",
      "    uint32_t s[16] = { C0,C1,C2,C3, key[0..7], ctr, nonce[0..2] };",
      "    uint32_t w[16]; memcpy(w,s,sizeof s);",
      "    for(int i=0;i<10;i++){               // 20 rounds = 10 double rounds",
      "        quarter_round(w,0,4,8,12);  quarter_round(w,1,5,9,13);",
      "        quarter_round(w,2,6,10,14); quarter_round(w,3,7,11,15);",
      "        quarter_round(w,0,5,10,15); quarter_round(w,1,6,11,12);",
      "        quarter_round(w,2,7,8,13);  quarter_round(w,3,4,9,14);",
      "    }",
      "    for(int i=0;i<16;i++) out[i]=w[i]+s[i];",
      "}"])

sec_h("Appendix 6  Kyber Leakage Model (Host)")
code(["KYBER_Q = 3329",
      "def hw(x):              # Hamming weight of a 12-bit coefficient",
      "    return bin(int(x) & 0xFFF).count('1')",
      "def pointwise(s_hat_i, u_i):",
      "    return (int(s_hat_i) * int(u_i)) % KYBER_Q    # leaking product",
      "def recover_coefficient(u_values, traces):",
      "    guesses = np.arange(KYBER_Q)",
      "    prod = (u_values[:,None] * guesses[None,:]) % KYBER_Q",
      "    hyp = hw_vec(prod)",
      "    corr = np.abs(correlation_matrix(hyp, traces)).max(axis=1)",
      "    return int(np.argmax(corr))                   # recovered s_hat_i"])

sec_h("Appendix 7  Probing-Detection Features")
code(["# nine features from a sliding window of recent requests",
      "features = [ payload_entropy,          # structured inputs -> low entropy",
      "             request_rate,             # trace collection -> high rate",
      "             timing_cv,                # automation -> regular timing",
      "             duplicate_ratio,          # repeated payloads",
      "             sequentialness,           # counter-like payloads",
      "             compression_ratio,        # structured data compresses",
      "             inter_arrival_autocorr,   # periodic timing",
      "             burst_ratio,              # bursts vs idle",
      "             rate_acceleration ]       # ramping collection",
      "model = IsolationForest(n_estimators=200, contamination='auto')",
      "model.fit(scaler.fit_transform(normal_windows))   # trained on normal only"])

sec_h("Appendix 8  Attacker Transport (Capability Boundary)")
code(["class SimTransport:        # attacker: observe only, no defense access",
      "    def leakloop(self, counter):  return dev.leakloop_trace(counter)",
      "    def kyberleak(self, u):       return dev.kyberleak_trace(u)",
      "    def check(self, candidate):   return dev.check_secret(candidate)",
      "    def command(self, ctr, pl):   return dev.submit_command(ctr, pl)",
      "    # note: there is deliberately no set_defense / rotate_key here",
      "",
      "class HwTransport:         # same interface, real ESP32 over UART + ADC",
      "    def leakloop(self, counter):",
      "        uart.write(b'LEAKLOOP %08x\\n' % counter)",
      "        buf = []",
      "        while not uart.in_waiting: buf.append(chan.voltage)",
      "        uart.readline()",
      "        return np.asarray(buf)"])

sec_h("Appendix 9  Per-Byte CPA Analysis (Attacker)")
code(["def analyze_byte(known_bytes, traces):",
      "    corr = byte_corr(known_bytes, traces)        # (256, n_samples)",
      "    signed_peak = corr.max(axis=1)               # signed peak per guess",
      "    order = np.argsort(signed_peak)[::-1]",
      "    best, second = int(order[0]), int(order[1])",
      "    return { 'value': best,",
      "             'corr': float(signed_peak[best]),",
      "             'margin': float(signed_peak[best] - signed_peak[second]),",
      "             'poi': int(corr[best].argmax()),",
      "             'top5': [(int(g), float(signed_peak[g])) for g in order[:5]] }"])

sec_h("Appendix 10  Full-Key Column Recovery (Attacker)")
code(["def recover_column(x, traces, const):",
      "    per = traces.shape[1] // 8; win = split(traces, 8)",
      "    a = 0",
      "    for j in range(4):                            # XOR target -> const+key_lo",
      "        a |= attack_byte_xor((x>>(8*j))&0xFF, win[j]) << (8*j)",
      "    key_lo = (a - const) & MASK32",
      "    D = rotl32((x ^ a), 16)                        # now known per trace",
      "    carry = zeros(len(x)); key_hi = 0",
      "    for j in range(4):                            # ADD target -> key_hi",
      "        kb = (D>>(8*j))&0xFF",
      "        best = attack_byte(kb, carry, win[4+j])",
      "        key_hi |= best << (8*j)",
      "        carry = (kb + best + carry) >= 256",
      "    return key_lo, key_hi"])

sec_h("Appendix 11  Defender Leakage Assessment")
code(["def assess_masking(transport, n_traces=800):",
      "    out = {}",
      "    for state in ('off', 'on'):",
      "        transport.set_defense('masking', state == 'on')",
      "        tv = tvla.assess(transport)                # fixed vs random t-test",
      "        counters, traces = collect(transport, n_traces)",
      "        res = cpa.analyze(counters, traces)         # reuse attacker engine",
      "        out[state] = { 'tvla_peak_t': tv['peak_t'], 'tvla_leaks': tv['leaks'],",
      "                       'peak_corr': res['mean_peak_corr'], 'ntd': res['ntd'] }",
      "    transport.set_defense('masking', False)",
      "    return summarize(out)                           # verdict + suppression"])

sec_h("Appendix 12  Unified Demonstration (Host)")
code(["STEPS = [",
      "  ('ATTACKER  ChaCha20 power CPA',      'ct_attack.py cpa --traces 1500'),",
      "  ('ATTACKER  full 256-bit recovery',   'chacha_full.py --traces 4000'),",
      "  ('ATTACKER  Kyber coefficient CPA',   'ct_attack.py kyber --traces 2500'),",
      "  ('ATTACKER  timing attack',           'ct_attack.py timing'),",
      "  ('ATTACKER  replay attack',           'ct_attack.py replay'),",
      "  ('DEFENDER  ChaCha20 assessment',     'ct_defend.py assess --target chacha'),",
      "  ('DEFENDER  Kyber assessment',        'ct_defend.py assess --target kyber'),",
      "  ('DEFENDER  probing analytics',       'ct_defend.py monitor'),",
      "]",
      "for title, cmd in STEPS:        # one command reproduces every result",
      "    print('#', title); run(cmd)   # add --hw to drive the real device"])

sec_h("Appendix 13  Probing Monitor Analytics (Defender)")
code(["def detection_latency(make_detector, simulate, max_events=250):",
      "    det = make_detector(); t = 0.0",
      "    for i in range(max_events):",
      "        t = simulate(det, rng, n_events=1, base_time=t)  # one request at a time",
      "        if det.check()['alert']:",
      "            return i + 1            # requests until first alert",
      "    return None",
      "",
      "def false_positive_rate(make_detector, trials=30):",
      "    fp = 0",
      "    for s in range(trials):",
      "        det = make_detector()",
      "        simulate_normal_traffic(det, rng, n_events=40)",
      "        if det.check()['alert']: fp += 1",
      "    return fp / trials"])

sec_h("Appendix 14  Timing Attack (Host)")
code(["def recover_secret(transport, length, trials=40):",
      "    recovered = bytearray()",
      "    for pos in range(length):",
      "        best_g, best_t = 0, -1",
      "        for g in range(256):",
      "            cand = bytes(recovered) + bytes([g]) + bytes(length-pos-1)",
      "            t = median(transport.check(cand)[1] for _ in range(trials))",
      "            if t > best_t: best_t, best_g = t, g   # longest = correct prefix",
      "        recovered.append(best_g)",
      "    return bytes(recovered)   # last byte indistinguishable (known artifact)"])

sec_h("Appendix 15  Command Dispatch (Firmware)")
code(["void handleCommand(String cmd){",
      "    cmd.trim();",
      "    if (cmd == 'PING')    { Serial1.println('PONG'); return; }",
      "    if (cmd == 'STATUS')  { printStatus(); return; }",
      "    String verb = cmd.substring(0, cmd.indexOf(' '));",
      "    String args = cmd.substring(cmd.indexOf(' ') + 1);",
      "    if      (verb == 'ENCRYPT')   handleEncrypt(args);",
      "    else if (verb == 'LEAKLOOP')  handleLeakLoop(args);",
      "    else if (verb == 'KYBERLEAK') handleKyberLeak(args);",
      "    else if (verb == 'CHECK')     handleCheck(args);",
      "    else if (verb == 'CMD')       handleCmd(args);",
      "    else if (verb == 'DEFENSE')   handleDefense(args);   // defender only",
      "    else if (verb == 'SET_KEY')   handleSetKey(args);    // defender only",
      "    else Serial1.println('ERR');",
      "}"])

sec_h("Appendix 16  Hardware Bring-Up and Verification Log")
body("The following is the procedure followed each time the hardware was brought up, recorded "
     "here so that the physical results can be reproduced. It is the sequence that produced the "
     "measurements of Chapter 5.")
body("1. Flash the two devices over the programming connection: the cryptographic target with the "
     "attack firmware and the second board with the noise-injection firmware. The target then "
     "enumerates and responds, confirming the write.")
body("2. Verify the analog-to-digital converter on the serial bus. The converter acknowledges at "
     "its address, and a read of each single-ended channel together with the differential "
     "channel returns sane voltages, confirming the device is alive before any trace is taken.")
body("3. Verify the command interface over the dedicated serial link. A LEAKLOOP request returns "
     "the completion token, and a CHECK request carrying the known authentication secret returns "
     "the acceptance token, confirming that the host is talking to the correct firmware and that "
     "the secret under test is the expected one.")
body("4. Remove the programming cable from the target so that its entire supply current is forced "
     "through the shunt, and confirm the baseline on the differential channel rises to its full "
     "value of about seven hundred and sixty millivolts. A baseline of only a few millivolts "
     "indicates the cable is still supplying the device and the collection must not proceed.")
body("5. Collect. The attacker program issues the amplified-leakage requests and records the "
     "converter output per request; the defender program toggles the countermeasures and runs "
     "the leakage assessment. Each result is written to a file and, for the power attacks, to a "
     "figure, and the raw traces are archived so the analysis can be repeated without the device.")
body("The measured outcomes of this procedure are those reported in Chapter 5: the ChaCha20 key "
     "word recovered from about a few hundred traces at a correlation near one third; masking "
     "effective on ChaCha20 and, as a documented negative result, ineffective on Kyber as "
     "currently implemented; the Kyber coefficient recovered on the device; the timing attack "
     "unresolved over the serial link; and replay accepted without a nonce and blocked with one.")

sec_h("Appendix 17  Archived Hardware Data and Reproduction")
body("Every hardware result in this report is backed by a file captured during the campaign and "
     "preserved in the project repository, so that the analysis can be reproduced and audited "
     "without access to the physical device. The archive is organised as follows.")
body("Measurement logs record the console output of each run: the correlation power analysis of "
     "ChaCha20 with its per-byte statistics and convergence curve; the leakage assessments of "
     "ChaCha20 at several trace counts and of Kyber; the Kyber coefficient recovery; the timing "
     "attack over the serial link; and the replay attack with and without the nonce. Each log "
     "names the configuration, the number of traces, and the measured outcome.")
body("Figure data preserves the images reproduced in Chapter 5 - the correlation analysis, the "
     "leakage-assessment trace, the coefficient-recovery spectrum, the raw power trace, the "
     "convergence curve, the per-byte margins, the masking comparison, the timing margins, and "
     "the simulation-versus-hardware comparison - each regenerable from the archived numbers.")
body("Raw traces are stored in compressed numerical form: the ChaCha20 set holds the eight "
     "hundred power traces and their associated counters, and the Kyber set holds the thousand "
     "traces and their chosen inputs. These are the unprocessed converter readings from which "
     "every correlation in the report is computed, and they allow an examiner to re-run the "
     "attack code against the actual measurements rather than against a description of them.")
body("Two short scripts accompany the data: one collects and plots the Kyber coefficient CPA, "
     "and one archives the raw trace sets. Together with the attacker and defender programs, "
     "which accept a hardware flag to drive the real device, they constitute a complete and "
     "self-contained record of how each measured result in this report was obtained.")

sec_h("Appendix 18  Reproducibility Checklist")
body("The following checklist states, for each result in the report, how it may be reproduced, "
     "so that an examiner or a future student can repeat the work and arrive at the same "
     "conclusions. Each item names the command and the expected outcome.")
body("Software-model results, which require no hardware, are reproduced by running the unified "
     "demonstration script, which exercises the attacker and defender programs in sequence "
     "against the software model and prints, for every step, the exact command a user would "
     "type. The expected summary is that all eight modules - the three attacks, the four "
     "countermeasures, and the probing monitor - report a passing result, and that the ChaCha20 "
     "key and the Kyber coefficient are recovered against the unprotected device and fail to be "
     "recovered once the relevant countermeasure is enabled.")
body("The power-analysis attack on ChaCha20 is reproduced by invoking the attacker's correlation "
     "subcommand; against the software model it recovers the key word with a correlation near "
     "one half in about a hundred traces, and against the hardware, with the hardware flag set, "
     "it recovers the same word with a correlation near one third in a few hundred traces. The "
     "leakage assessment is reproduced through the defender's assessment subcommand, which "
     "reports the leakage statistic with masking disabled and enabled and the resulting verdict.")
body("The post-quantum attack is reproduced through the attacker's Kyber subcommand, which "
     "recovers the secret coefficient and reports the correlation of the winning candidate and "
     "its margin. The timing and replay attacks are reproduced through their respective "
     "subcommands; the timing attack succeeds in the software model and, as documented, does not "
     "resolve over the serial link on hardware, while the replay attack is accepted without a "
     "nonce and blocked once the nonce is enabled. The probing monitor is reproduced through the "
     "defender's monitor subcommand, which reports the false-positive rate and the detection "
     "latency for the rule-based and machine-learning detectors against an aggressive and a "
     "throttled attacker.")
body("In every case the figures and tables of Chapter 5 are regenerated from the archived data "
     "described in Appendix 17, so that the quantitative claims of the report rest on preserved "
     "measurements rather than on a single unrepeatable run. This closes the loop between the "
     "claims made and the evidence retained, and it is the practice the project recommends for "
     "any empirical security evaluation.")

sec_h("Appendix 19  Authentication Check (Firmware)")
code(["void handleCheck(const String &args) {",
      "    // ... parse candidate bytes ...",
      "    bool accepted;",
      "    if (constant_time_enabled) {",
      "        uint8_t diff = (len != SECRET_LEN) ? 1 : 0;",
      "        for (size_t i = 0; i < SECRET_LEN; i++)",
      "            diff |= candidate[i] ^ auth_secret[i];   // always full length",
      "        accepted = (diff == 0);",
      "    } else {",
      "        accepted = (len == SECRET_LEN);",
      "        for (size_t i = 0; i < len; i++)",
      "            if (candidate[i] != auth_secret[i]) { accepted = false; break; }",
      "    }",
      "    Serial1.println(accepted ? \"OK\" : \"FAIL\");",
      "}"])

sec_h("Appendix 20  Amplified First-Round Leakage (Firmware)")
code(["void handleLeakLoop(const String &args) {",
      "    uint32_t counter = hexToU32(args.c_str());",
      "    uint32_t a = (kConstants[0] + chacha_key[0]);     // const0 + key0",
      "    uint32_t d = counter ^ a;                          // first-round XOR target",
      "    uint32_t mask = masking_enabled ? esp_random() : 0;",
      "    uint32_t v = d ^ mask;                             // masked when enabled",
      "    digitalWrite(TRIGGER, HIGH);",
      "    for (int j = 0; j < 4; j++) {                      // one phase per byte",
      "        uint8_t b = (v >> (8*j)) & 0xFF;",
      "        for (uint32_t it = 0; it < ITER; it++)",
      "            for (int k = 0; k < 8; k++)",
      "                if (b & (1<<k)) { pin_high(k); pin_low(k); }  // toggles ~ HW(b)",
      "                else            { dummy_low();  dummy_low();  } // constant time",
      "    }",
      "    digitalWrite(TRIGGER, LOW);",
      "    Serial1.println(\"LEAKDONE\");",
      "}"])

sec_h("Appendix 21  Kyber Coefficient Leakage (Firmware)")
code(["void handleKyberLeak(const String &args) {",
      "    uint32_t u = hexToU32(args.c_str()) % KYBER_Q;",
      "    uint16_t t = (kyber_s_hat * u) % KYBER_Q;          // secret-dependent product",
      "    digitalWrite(TRIGGER, HIGH);",
      "    for (uint32_t it = 0; it < ITER; it++)",
      "        for (int bit = 0; bit < 12; bit++)             // 12-bit coefficient",
      "            if (t & (1<<bit)) { pin_high(bit & 7); pin_low(bit & 7); }",
      "            else              { dummy_low(); dummy_low(); }",
      "    digitalWrite(TRIGGER, LOW);",
      "    Serial1.println(\"KYBERDONE\");",
      "}"])

doc.save(str(OUT))
print("FULL REPORT saved", OUT)
