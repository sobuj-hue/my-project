"""
Generate a clean, minimalist PDF report for the IGZO TFT sweat biosensor.

Run:
    python3 generate_report.py
Produces:
    biosensor_report.pdf
"""

from __future__ import annotations

import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

import biosensor_tft as bs


# ---------------------------------------------------------------------------
# Register a Unicode-capable font (DejaVu) so subscripts, superscripts,
# Greek letters and the micro sign render correctly.
# ---------------------------------------------------------------------------
_DEJAVU = "/usr/share/fonts/truetype/dejavu"
_MPL = "/usr/local/lib/python3.11/dist-packages/matplotlib/mpl-data/fonts/ttf"
pdfmetrics.registerFont(TTFont("Body",
                               f"{_DEJAVU}/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("Body-Bold",
                               f"{_DEJAVU}/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Body-Italic",
                               f"{_MPL}/DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont("Body-BoldItalic",
                               f"{_MPL}/DejaVuSans-BoldOblique.ttf"))
pdfmetrics.registerFont(TTFont("Mono",
                               f"{_DEJAVU}/DejaVuSansMono.ttf"))

from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("Body", normal="Body", bold="Body-Bold",
                   italic="Body-Italic", boldItalic="Body-BoldItalic")


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    ink = colors.HexColor("#1a1a1a")
    muted = colors.HexColor("#555555")
    accent = colors.HexColor("#1f4e79")

    styles: dict[str, ParagraphStyle] = {}
    styles["Title"] = ParagraphStyle(
        "Title", parent=base["Title"], fontName="Body-Bold",
        fontSize=18, leading=22, textColor=ink, alignment=0,
        spaceAfter=6,
    )
    styles["Subtitle"] = ParagraphStyle(
        "Subtitle", parent=base["Normal"], fontName="Body",
        fontSize=10.5, leading=14, textColor=muted, spaceAfter=18,
    )
    styles["H1"] = ParagraphStyle(
        "H1", parent=base["Heading1"], fontName="Body-Bold",
        fontSize=13, leading=16, textColor=accent,
        spaceBefore=14, spaceAfter=6,
    )
    styles["H2"] = ParagraphStyle(
        "H2", parent=base["Heading2"], fontName="Body-Bold",
        fontSize=11, leading=14, textColor=ink,
        spaceBefore=10, spaceAfter=4,
    )
    styles["Body"] = ParagraphStyle(
        "Body", parent=base["BodyText"], fontName="Body",
        fontSize=10, leading=14, textColor=ink, alignment=4,
        spaceAfter=6,
    )
    styles["Bullet"] = ParagraphStyle(
        "Bullet", parent=styles["Body"], leftIndent=14,
        bulletIndent=4, spaceAfter=2,
    )
    styles["Caption"] = ParagraphStyle(
        "Caption", parent=base["Italic"], fontName="Body-Italic",
        fontSize=9, leading=12, textColor=muted,
        alignment=1, spaceAfter=10,
    )
    styles["Code"] = ParagraphStyle(
        "Code", parent=base["Code"], fontName="Mono",
        fontSize=8.2, leading=10.5, textColor=ink,
        leftIndent=8, rightIndent=8, spaceAfter=8,
        backColor=colors.HexColor("#f5f5f5"),
        borderPadding=6,
    )
    return styles


# ---------------------------------------------------------------------------
# Document template with minimal header / footer
# ---------------------------------------------------------------------------
def _draw_chrome(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#dddddd"))
    canvas.setLineWidth(0.4)
    canvas.line(2.0 * cm, A4[1] - 1.7 * cm,
                A4[0] - 2.0 * cm, A4[1] - 1.7 * cm)
    canvas.setFont("Body", 8)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawString(2.0 * cm, A4[1] - 1.4 * cm,
                      "IGZO TFT Flexible Sweat Biosensor")
    canvas.drawRightString(A4[0] - 2.0 * cm, A4[1] - 1.4 * cm,
                           "Technical Report")
    canvas.drawCentredString(A4[0] / 2.0, 1.2 * cm,
                             f"{doc.page}")
    canvas.restoreState()


def make_doc(path: str) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        path, pagesize=A4,
        leftMargin=2.0 * cm, rightMargin=2.0 * cm,
        topMargin=2.2 * cm, bottomMargin=1.8 * cm,
        title="IGZO TFT Flexible Sweat Biosensor",
        author="Biosensor Lab",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="main",
                  leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id="body", frames=[frame],
                                      onPage=_draw_chrome))
    return doc


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------
def p(text: str, style) -> Paragraph:
    return Paragraph(text, style)


def bullets(items, style) -> list:
    return [Paragraph(f"• {t}", style) for t in items]


def figure(path: str, caption: str, styles, width=11 * cm) -> list:
    from reportlab.platypus import KeepTogether
    img = Image(path, width=width, height=width * 0.72)
    img.hAlign = "CENTER"
    return [KeepTogether([Spacer(1, 4), img,
                          p(caption, styles["Caption"])])]


# ---------------------------------------------------------------------------
# Build the story
# ---------------------------------------------------------------------------
def build_story(styles) -> list:
    s = styles
    story: list = []

    # --- Title block ---
    story.append(p("Fabrication and Characterization of a Metal-Oxide "
                   "TFT-Based Flexible Biosensor for Real-Time Sweat "
                   "Analyte Detection", s["Title"]))
    story.append(p("A reproducible simulation and procedural report "
                   "covering device design, fabrication on a flexible "
                   "polyimide substrate, electrical characterization, "
                   "and enzymatic detection of glucose and lactate in "
                   "human sweat.", s["Subtitle"]))

    # --- Abstract ---
    story.append(p("Abstract", s["H1"]))
    story.append(p(
        "We describe the design, simulated fabrication and "
        "characterization of a flexible biosensor built around an "
        "amorphous indium-gallium-zinc-oxide (a-IGZO) thin-film "
        "transistor (TFT). The TFT is deposited on a 25 µm polyimide "
        "substrate and functionalized with glucose oxidase (GOx) or "
        "lactate oxidase (LOx) on an extended gate. A physics-based "
        "compact model reproduces the transfer and output "
        "characteristics, while a Nernstian Michaelis–Menten model "
        "couples analyte concentration to the gate potential. The "
        "accompanying Python code (biosensor_tft.py) generates every "
        "figure in this report and can be extended to arbitrary "
        "geometries and enzyme systems.", s["Body"]))

    # --- Device summary table ---
    story.append(p("1. Device parameters", s["H1"]))
    p_ = bs.TFTParams()
    data = [
        ["Parameter", "Symbol", "Value"],
        ["Channel width",          "W",         f"{p_.W*1e6:.0f} µm"],
        ["Channel length",         "L",         f"{p_.L*1e6:.0f} µm"],
        ["Al₂O₃ thickness",        "t_ox",      f"{p_.t_ox*1e9:.0f} nm"],
        ["Relative permittivity",  "ε_r",       f"{p_.eps_r:.1f}"],
        ["Gate capacitance",       "C_ox",
         f"{p_.Cox*1e3:.2f} mF/m²"],
        ["Field-effect mobility",  "µ",
         f"{p_.mu*1e4:.1f} cm²/Vs"],
        ["Threshold voltage",      "V_th",      f"{p_.Vth:.2f} V"],
        ["Subthreshold slope",     "SS",
         f"{p_.SS*1000:.0f} mV/dec"],
        ["Operating temperature",  "T",         f"{p_.T-273.15:.0f} °C"],
    ]
    table = Table(data, colWidths=[5.5 * cm, 2.5 * cm, 4.0 * cm])
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Body-Bold", 9.5),
        ("FONT", (0, 1), (-1, -1), "Body", 9.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f7fa")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6,
         colors.HexColor("#1f4e79")),
        ("LINEABOVE", (0, 0), (-1, 0), 0.6,
         colors.HexColor("#1f4e79")),
        ("LINEBELOW", (0, -1), (-1, -1), 0.4,
         colors.HexColor("#888888")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (1, 0), (-1, -1), "LEFT"),
    ]))
    story.append(table)
    story.append(Spacer(1, 8))

    # --- Fabrication procedure ---
    story.append(p("2. Fabrication procedure", s["H1"]))

    story.append(p("2.1 Substrate preparation", s["H2"]))
    story += bullets([
        "Spin-coat polyimide (PI-2611) onto a carrier Si wafer at "
        "3000 rpm to yield a 25 µm film; cure at 350 °C for 1 h "
        "under N₂.",
        "Clean with sequential acetone/IPA/DI-water ultrasonic baths "
        "and dehydrate at 120 °C for 10 min.",
    ], s["Bullet"])

    story.append(p("2.2 Gate stack", s["H2"]))
    story += bullets([
        "DC-sputter 80 nm Mo through a shadow mask to form the bottom "
        "gate electrode (base pressure 5×10⁻⁷ Torr, 100 W).",
        "Atomic-layer-deposit 100 nm Al₂O₃ at 150 °C "
        "(TMA + H₂O, 1200 cycles) as the gate dielectric.",
    ], s["Bullet"])

    story.append(p("2.3 IGZO channel", s["H2"]))
    story += bullets([
        "RF-sputter 30 nm a-IGZO (In:Ga:Zn = 1:1:1) at 100 W in "
        "Ar/O₂ (90/10 sccm).",
        "Pattern the channel (W/L = 200/20 µm) by wet etch in dilute "
        "oxalic acid.",
        "Anneal in air at 300 °C for 1 h to set mobility "
        "(~12 cm²/Vs) and stabilize V_th.",
    ], s["Bullet"])

    story.append(p("2.4 Source/drain and passivation", s["H2"]))
    story += bullets([
        "E-beam evaporate 10/80 nm Ti/Au source–drain electrodes; "
        "lift off in NMP.",
        "Deposit 100 nm SU-8 passivation, opening only the extended "
        "gate sensing window.",
    ], s["Bullet"])

    story.append(p("2.5 Bio-functionalization", s["H2"]))
    story += bullets([
        "Plasma-activate the sensing window (O₂, 50 W, 30 s).",
        "Drop-cast 2 µL of GOx or LOx (5 mg/mL in 0.1 M phosphate "
        "buffer) mixed 1:1 with 1 % chitosan.",
        "Cross-link with 0.5 % glutaraldehyde vapor for 10 min and "
        "store at 4 °C.",
    ], s["Bullet"])

    story.append(p("2.6 Release from carrier", s["H2"]))
    story += bullets([
        "Laser lift-off (308 nm excimer, 250 mJ/cm²) releases the "
        "polyimide/device stack from the Si carrier.",
        "Laminate a 50 µm PDMS microfluidic layer containing the "
        "sweat-collection channel.",
    ], s["Bullet"])

    # --- Characterization ---
    story.append(p("3. Electrical characterization", s["H1"]))

    story.append(p(
        "Transfer and output curves are measured with a "
        "Keithley 4200-SCS parameter analyzer at 30 °C to mimic skin "
        "temperature. In this report the same curves are reproduced "
        "by the compact model in <b>biosensor_tft.py</b>.",
        s["Body"]))

    story += figure("figures/fig_transfer.png",
                    "Figure 1. Simulated log-scale transfer "
                    "characteristic at V_ds = 1 V. On/off ratio "
                    "exceeds 10⁷, SS ≈ 150 mV/dec.", s)

    story += figure("figures/fig_output.png",
                    "Figure 2. Output curves at V_gs = 1.0–3.0 V "
                    "showing textbook triode/saturation behaviour.",
                    s)

    # --- Biosensor response ---
    story.append(p("4. Enzymatic transduction", s["H1"]))
    story.append(p(
        "The enzymatic reaction at the extended gate modulates the "
        "local surface potential φ through the Nernst equation, "
        "attenuated by Michaelis–Menten saturation "
        "S·log₁₀(1 + C/K_m)·C/(K_m + C). The resulting gate shift "
        "modulates the TFT drain current, producing the calibration "
        "curves in Figure 3.",
        s["Body"]))

    story += figure("figures/fig_calibration.png",
                    "Figure 3. Simulated calibration of the TFT "
                    "biosensor for glucose (GOx, K_m = 8 mM) and "
                    "lactate (LOx, K_m = 5 mM) across the "
                    "physiological sweat range.", s)

    story.append(p("5. Real-time sweat monitoring", s["H1"]))
    story.append(p(
        "A 10-minute sweat stream is synthesized with a resting "
        "glucose baseline of 0.2 mM, a post-meal spike at t = 150 s, "
        "and an exercise-induced peak at t = 420 s. Gaussian "
        "biological and 1 % electrical noise are added. The drain "
        "current tracks both excursions clearly.",
        s["Body"]))

    story += figure("figures/fig_realtime.png",
                    "Figure 4. Simultaneous analyte concentration "
                    "(top) and measured drain current (bottom) "
                    "during a simulated 10-minute wear.", s)

    # --- Step-by-step procedure summary ---
    story.append(p("6. Procedure, step by step", s["H1"]))

    steps = [
        ("Define device geometry and materials.",
         "Instantiate TFTParams() with the channel geometry, "
         "Al₂O₃ thickness, mobility and threshold voltage that match "
         "the fabricated stack."),
        ("Build the TFT compact model.",
         "tft_drain_current() uses a smooth threshold function so a "
         "single closed-form expression covers subthreshold, triode, "
         "and saturation; the model is inexpensive and differentiable."),
        ("Sweep transfer and output curves.",
         "transfer_curve() and output_curves() return NumPy arrays "
         "ready for plotting or extraction of V_th, µ, SS and the "
         "on/off ratio."),
        ("Add the enzymatic transducer.",
         "EnzymeParams encapsulates the Michaelis–Menten constant "
         "K_m and the Nernstian coefficient S. "
         "surface_potential() converts analyte concentration into a "
         "gate-potential shift."),
        ("Couple analyte → gate → current.",
         "biosensor_current() adds the enzymatic ΔV to the bias V_gs "
         "and evaluates the TFT model, yielding I_d(C)."),
        ("Generate calibration data.",
         "Sweep C over 0.01–20 mM on a logarithmic grid; fit the "
         "linear region (0.1–5 mM) to extract the sensitivity "
         "d(log₁₀ I_d)/d(log₁₀ C)."),
        ("Simulate a real-time sweat stream.",
         "simulate_realtime() synthesises a 10-minute profile with "
         "two physiological spikes plus noise, and returns both the "
         "true concentration and the measured current."),
        ("Plot and save figures.",
         "plot_transfer(), plot_output(), plot_calibration() and "
         "plot_realtime() write PNGs into ./figures/, which this "
         "PDF embeds."),
        ("Render the report.",
         "generate_report.py composes the figures, tables and "
         "narrative into biosensor_report.pdf using ReportLab."),
    ]
    for i, (title, body) in enumerate(steps, start=1):
        story.append(p(f"<b>Step {i}. {title}</b>", s["Body"]))
        story.append(p(body, s["Body"]))

    # --- Key equations ---
    story.append(p("7. Key equations", s["H1"]))
    story += bullets([
        "Gate capacitance:  C_ox = ε_r ε₀ / t_ox.",
        "Smooth TFT current:  I_d = µ C_ox (W/L) "
        "[V_ov V_ds,eff − ½ V_ds,eff²] + I_off, "
        "with V_ov = n V_T ln(1 + exp((V_gs − V_th)/(n V_T))).",
        "Enzymatic surface potential:  φ = V₀ + S log₁₀(1 + C/C₀) · "
        "C/(K_m + C).",
        "Sensor transduction:  V_gs,eff = V_gs,bias + φ.",
    ], s["Bullet"])

    # --- Conclusion ---
    story.append(p("8. Conclusion", s["H1"]))
    story.append(p(
        "The simulation reproduces the hallmark characteristics of a "
        "modern a-IGZO TFT biosensor: a sharp subthreshold turn-on, "
        "well-behaved saturation, a calibration curve that follows "
        "Michaelis–Menten kinetics, and a clean real-time response "
        "to physiological analyte spikes. Because every figure and "
        "table in this report is regenerated by a single "
        "<b>python3 generate_report.py</b> command, the workflow is "
        "fully reproducible and easy to extend to new enzymes, "
        "geometries or substrates.", s["Body"]))

    return story


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    os.makedirs("figures", exist_ok=True)
    params = bs.TFTParams()
    bs.plot_transfer(params, "figures/fig_transfer.png")
    bs.plot_output(params, "figures/fig_output.png")
    bs.plot_calibration(params, "figures/fig_calibration.png")
    bs.plot_realtime(params, "figures/fig_realtime.png")

    styles = build_styles()
    doc = make_doc("biosensor_report.pdf")
    doc.build(build_story(styles))
    print("Wrote biosensor_report.pdf")


if __name__ == "__main__":
    main()
