"""
Builds the PDF design report (Bahasa Indonesia) with dimensioned drawings
generated directly from the CadQuery models.

    python make_report.py      ->  Laporan_Desain_Controller_CCTV.pdf
"""

import datetime
import importlib.util
import os
import sys

import cadquery as cq
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import drawing as D  # noqa: E402

BUILD = os.environ.get("REPORT_BUILD", os.path.join(HERE, "build"))
os.makedirs(BUILD, exist_ok=True)
OUT_PDF = os.path.join(HERE, "Laporan_Desain_Controller_CCTV.pdf")
OLD_REV_IMG = os.environ.get("OLD_REV_IMG", os.path.join(HERE, "img", "rev_controller_box_klem.png"))


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HW, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CB = load("controller_box", "controller-box/controller_box.py")
PB = load("proto_box", "controller-box-proto/proto_box.py")
BE = load("bench", "controller-bench/bench.py")


def f(v, nd=1):
    s = f"{v:.{nd}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def png(name):
    return os.path.join(BUILD, name)


# ===========================================================================
# Drawings
# ===========================================================================

def dwg_main_assembly():
    asm, printed, comps, cables = CB.build(with_cables=False)
    shapes = []
    for ch in asm.children:
        n = ch.name
        if n in ("base", "lid", "camera_hub", "lock_bolts_m8") or (n.startswith("camera_") and n[7].isdigit()):
            shapes.append(ch.obj.val().moved(ch.loc))
        elif n == "pole_80x80":
            shapes.append(ch.obj.val().intersect(cq.Solid.makeBox(200, 200, 160, cq.Vector(-100, -100, -160))))
    comp = cq.Compound.makeCompound(shapes)

    fig, ax = D.new_sheet(180, 150)
    x0, x1, y0, y1 = D.draw(ax, comp, "front", lw=0.5)
    top = CB.BOX_Z + CB.Z_RIM + CB.LID_IN_Z + CB.LID_TOP
    D.dim_h(ax, x0, x1, y1, y1 + 18, f"{x1 - x0:.0f} (bentang kamera)")
    lx0 = -(CB.FLX + CB.SKIRT_CLR + CB.SKIRT_T)
    D.dim_h(ax, lx0, -lx0, top, top + 8, f"{-2 * lx0:.1f} (tutup)")
    D.dim_v(ax, 0, top, x1, x1 + 14, f"{top:.0f} di atas ujung tiang")
    D.dim_v(ax, CB.BOX_Z - CB.FLOOR, top, x0, x0 - 10, f"{top - CB.BOX_Z + CB.FLOOR:.0f} box")
    D.dim_v(ax, CB.HUB_Z0, CB.HUB_TOP, x0, x0 - 24, f"{CB.HUB_TOP - CB.HUB_Z0:.0f} hub")
    D.dim_h(ax, -CB.POLE_W / 2, CB.POLE_W / 2, -160, -172, f"tiang {CB.POLE_W:.0f}x{CB.POLE_W:.0f}")
    ax.plot([x0 - 30, x1 + 30], [0, 0], color=D.DIM, lw=0.3, ls=(0, (6, 3)))
    ax.text(x1 + 26, 2, "ujung tiang (Z=0)", fontsize=5.5, color=D.DIM, ha="right", va="bottom")
    D.finish(fig, ax, (x0 - 45, x1 + 45), (-185, top + 32), png("a_assembly_front.png"))

    fig, ax = D.new_sheet(180, 150)
    sh_top = cq.Compound.makeCompound([s for s in shapes])
    x0, x1, y0, y1 = D.draw(ax, sh_top, "top", lw=0.45)
    r = CB.HUB_OUT + CB.CAM_PAD + 98.0
    D.dim_h(ax, -r, r, 0, y1 + 14, f"{2 * r:.0f} (sumbu kamera ke sumbu kamera)")
    D.dim_v(ax, y0, y1, x1, x1 + 12, f"{y1 - y0:.0f}")
    D.finish(fig, ax, (x0 - 25, x1 + 40), (y0 - 15, y1 + 28), png("a_assembly_top.png"))


def dwg_main_base():
    base = CB.make_base()
    fig, ax = D.new_sheet(180, 140)
    x0, x1, y0, y1 = D.draw(ax, base, "top", lw=0.45)
    D.dim_h(ax, x0, x1, y1 - 30, y1 + 10, f"{x1 - x0:.0f} (termasuk rain cowl)")
    D.dim_h(ax, -CB.FLX, CB.FLX, y0 + 5, y0 - 10, f"{2 * CB.FLX:.0f} flange")
    D.dim_v(ax, -CB.FLY, CB.FLY, x1, x1 + 12, f"{2 * CB.FLY:.0f} flange")
    D.dim_v(ax, -CB.HY, CB.HY, -CB.HX, x0 - 10, f"{2 * CB.HY:.0f} interior")
    D.dim_h(ax, -CB.HX, CB.HX, -CB.HY + 20, -CB.HY + 20, f"{2 * CB.HX:.0f} interior")
    D.finish(fig, ax, (x0 - 25, x1 + 30), (y0 - 22, y1 + 22), png("a_base_top.png"))

    fig, ax = D.new_sheet(180, 80)
    x0, x1, y0, y1 = D.draw(ax, base, "front", hidden=False, lw=0.45)
    D.dim_v(ax, y0, y1, x1, x1 + 10, f"{y1 - y0:.0f}")
    D.dim_v(ax, CB.Z_RIM - CB.FLANGE_H, CB.Z_RIM, -CB.FLX, x0 - 6, f"{CB.FLANGE_H:.0f} flange")
    D.dim_v(ax, -CB.FLOOR, CB.Z_RIM - CB.FLANGE_H, -CB.OX - CB.COWL_DEPTH, x0 - 18,
            f"{CB.Z_RIM - CB.FLANGE_H + CB.FLOOR:.0f} cowl")
    D.dim_h(ax, CB.OX, CB.OX + CB.COWL_DEPTH, y0, y0 - 8, f"{CB.COWL_DEPTH:.0f}")
    D.dim_h(ax, -CB.OX, CB.OX, y0, y0 - 8, f"{2 * CB.OX:.0f} badan")
    D.finish(fig, ax, (x0 - 35, x1 + 25), (y0 - 18, y1 + 8), png("a_base_front.png"))


def dwg_main_lid():
    lid = CB.make_lid()
    fig, ax = D.new_sheet(180, 120)
    x0, x1, y0, y1 = D.draw(ax, lid, "top", lw=0.45)
    s = CB.HX + CB.SCREW_C
    D.dim_h(ax, x0, x1, y1, y1 + 10, f"{x1 - x0:.1f}")
    D.dim_v(ax, y0, y1, x1, x1 + 10, f"{y1 - y0:.1f}")
    D.dim_h(ax, -s, s, -s, y0 - 8, f"{2 * s:.0f} pola baut")
    D.dim_h(ax, 0, 62, s, s - 14, "62")
    D.note(ax, (s, 62), (x1 + 4, y1 - 20), "12x M4\ncounterbore")
    D.finish(fig, ax, (x0 - 15, x1 + 40), (y0 - 16, y1 + 18), png("a_lid_top.png"))

    fig, ax = D.new_sheet(180, 40)
    x0, x1, y0, y1 = D.draw(ax, lid, "front", lw=0.45)
    D.dim_v(ax, y0, y1, x1, x1 + 8, f"{y1 - y0:.0f}")
    D.dim_v(ax, y0, CB.Z_RIM, x0, x0 - 8, f"{CB.SKIRT_H:.0f} skirt")
    D.finish(fig, ax, (x0 - 25, x1 + 20), (y0 - 6, y1 + 6), png("a_lid_front.png"))


def dwg_main_hub():
    hub = CB.make_hub()
    fig, ax = D.new_sheet(180, 160)
    x0, x1, y0, y1 = D.draw(ax, hub, "front", hidden=True, lw=0.5)
    D.dim_h(ax, x0, x1, y1, y1 + 10, f"{x1 - x0:.0f}")
    D.dim_h(ax, -CB.HUB_OUT_LOW, CB.HUB_OUT_LOW, y0, y0 - 8, f"{2 * CB.HUB_OUT_LOW:.0f} (dinding 7)")
    D.dim_h(ax, -CB.HUB_OUT - CB.CAM_PAD, CB.HUB_OUT + CB.CAM_PAD, CB.CAM_PLATE_TOP_Z - 74, 2,
            f"{2 * (CB.HUB_OUT + CB.CAM_PAD):.0f} pad")
    xr = x1 + 8
    for (za, zb, t) in [(CB.HUB_Z0, 0, "80 masuk tiang"), (0, CB.FLARE_Z0, f"{CB.FLARE_Z0:.0f} zona kamera"),
                        (CB.FLARE_Z0, CB.RING_Z0, f"{CB.RING_Z0 - CB.FLARE_Z0:.0f} flare 45°"),
                        (CB.RING_Z0, CB.HUB_TOP, f"{CB.HUB_TOP - CB.RING_Z0:.0f} chamber")]:
        D.dim_v(ax, za, zb, CB.HUB_OUT, xr, t)
    D.dim_v(ax, CB.HUB_Z0, CB.HUB_TOP, x0, x0 - 10, f"{CB.HUB_TOP - CB.HUB_Z0:.0f}")
    pz = CB.CAM_PLATE_TOP_Z - 71 / 2
    D.dim_h(ax, -23.5, 23.5, pz + 28.5, pz + 46, "47")
    D.dim_v(ax, pz - 28.5, pz + 28.5, -23.5, -38, "57")
    D.note(ax, (0, pz + 8), (25, pz + 52), "lubang kabel Ø22")
    D.note(ax, (0, -58), (22, -40), "baut kunci M8 (Y), Z=-58")
    D.note(ax, (CB.HUB_OUT_LOW, -25), (CB.HUB_OUT_LOW + 12, -12), "baut kunci M8 (X), Z=-25")
    ax.plot([x0 - 18, x1 + 4], [0, 0], color=D.DIM, lw=0.3, ls=(0, (6, 3)))
    ax.text(x0 - 18, 1.5, "ujung tiang Z=0", fontsize=5.5, color=D.DIM, va="bottom")
    D.finish(fig, ax, (x0 - 30, x1 + 50), (y0 - 16, y1 + 18), png("a_hub_front.png"))

    fig, ax = D.new_sheet(180, 120)
    x0, x1, y0, y1 = D.draw(ax, hub, "top", lw=0.45)
    D.dim_h(ax, x0, x1, y1, y1 + 10, f"{x1 - x0:.0f}")
    D.dim_h(ax, -CB.CHAMBER_IN, CB.CHAMBER_IN, -CB.CHAMBER_IN, -CB.CHAMBER_IN + 12,
            f"{2 * CB.CHAMBER_IN:.0f} chamber")
    D.dim_v(ax, -90, 90, 90, x1 + 10, "180 pola baut M5")
    D.dim_h(ax, -CB.HUB_IN, CB.HUB_IN, 0, 0, f"{2 * CB.HUB_IN:.0f} lubang tiang")
    D.finish(fig, ax, (x0 - 15, x1 + 30), (y0 - 10, y1 + 18), png("a_hub_top.png"))


COMP_LABELS = [
    ("psu_12v", "PSU 12 V"), ("orangepi5ultra_pcb", "Orange Pi 5 Ultra"),
    ("switch_tplink_ls1005", "LS1005"), ("buck_12v_to_5v", "Buck 12V-5V"),
    ("wago_221_1", "WAGO 1"), ("wago_221_2", "WAGO 2"), ("fan_intake", "Kipas intake"),
    ("fan_exhaust", "Kipas exhaust"), ("fan_top_opi", "Kipas atas OPi"),
]


def dwg_main_layout():
    base = CB.make_base()
    comps = CB.make_components()
    keep = [k for k in comps if k not in ("cable_glands", "fan_top_opi")]
    sh = cq.Compound.makeCompound([base.val()] + [comps[k][0].val() for k in keep])
    fig, ax = D.new_sheet(180, 170)
    x0, x1, y0, y1 = D.draw(ax, sh, "top", lw=0.4)
    # keep-out zones
    for n, kz in CB.make_keepouts().items():
        bb = kz.val().BoundingBox()
        ax.add_patch(__import__("matplotlib").patches.Rectangle((bb.xmin, bb.ymin), bb.xlen, bb.ylen,
                                                                fc=(0.77, 0.31, 0.10, 0.10), ec=D.DIM,
                                                                lw=0.4, ls="--"))
    # glands
    for (x, y, size) in CB.GLANDS:
        ax.add_patch(__import__("matplotlib").patches.Circle((x, y), CB.GLAND_D[size] / 2, fc="none",
                                                             ec="#2a6fd6", lw=0.6))
    label_at = {"wago_221_1": (90, 39.5), "wago_221_2": (90, 62.5), "fan_exhaust": (68, 82),
                "fan_top_opi": (-27.5, 30), "orangepi5ultra_pcb": (-27.5, -22)}
    for i, (k, lab) in enumerate(COMP_LABELS, 1):
        bb = comps[k][0].val().BoundingBox()
        cx, cy = label_at.get(k, ((bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2))
        ax.text(cx, cy, str(i), fontsize=7, weight="bold", ha="center", va="center", color="white",
                bbox=dict(boxstyle="circle,pad=0.25", fc=D.DIM, ec="none"))
    D.dim_h(ax, -CB.HX, CB.HX, CB.HY, y1 + 8, f"{2 * CB.HX:.0f} interior")
    D.dim_v(ax, -CB.HY, CB.HY, CB.HX, x1 + 8, f"{2 * CB.HY:.0f} interior")
    ax.text(0, y0 - 6, "Arsir oranye = ruang kosong 30 mm di depan port.   Lingkaran biru = cable gland.",
            fontsize=6, color=D.DIM, ha="center", va="top")
    D.finish(fig, ax, (x0 - 10, x1 + 25), (y0 - 14, y1 + 18), png("a_layout_top.png"))


def dwg_proto():
    base, lid = PB.make_base(), PB.make_lid()
    fig, ax = D.new_sheet(180, 70)
    x0, x1, y0, y1 = D.draw(ax, base, "front", lw=0.45)
    D.dim_h(ax, x0, x1, y1, y1 + 8, f"{x1 - x0:.1f}")
    D.dim_v(ax, y0, y1, x1, x1 + 8, f"{y1 - y0:.0f}")
    tx0, tx1 = PB.OPI_TRAY[0] + 3, PB.OPI_TRAY[1] - 3
    zt = PB.PCB_Z + PB.OPI[2]
    D.dim_h(ax, tx0, tx1, zt + 18, zt + 26, f"{tx1 - tx0:.0f}")
    D.dim_v(ax, zt - 2, zt + 18, tx0, tx0 - 6, f"{20:.0f}")
    sx0, sx1 = PB.SW_POS[0] + 1, PB.SW_POS[0] + PB.SWITCH[0] - 1
    D.dim_h(ax, sx0, sx1, PB.SWITCH[2] + 2, PB.SWITCH[2] + 14, f"{sx1 - sx0:.1f}")
    D.dim_v(ax, 1.5, PB.SWITCH[2] + 2, sx1, sx1 + 6, f"{PB.SWITCH[2] + 0.5:.1f}")
    D.dim_v(ax, y0, zt - 2, tx1, tx1 + 5, f"{zt - 2 - y0:.1f}")
    D.finish(fig, ax, (x0 - 18, x1 + 20), (y0 - 8, y1 + 16), png("b_base_front.png"))

    fig, ax = D.new_sheet(180, 130)
    x0, x1, y0, y1 = D.draw(ax, lid, "top", lw=0.45)
    D.dim_h(ax, x0, x1, y1, y1 + 8, f"{x1 - x0:.1f}")
    D.dim_v(ax, y0, y1, x1, x1 + 8, f"{y1 - y0:.1f}")
    for (cx, cy), t in ((PB.FAN1_C, "kipas 1"), (PB.FAN2_C, "kipas 2")):
        D.note(ax, (cx, cy), (cx + 45, cy - 28) if cy < 0 else (cx + 18, cy - 46), f"{t}: pusat ({f(cx)}, {f(cy)})")
    D.dim_h(ax, PB.FAN1_C[0], PB.FAN2_C[0], 8, 8, f"{PB.FAN2_C[0] - PB.FAN1_C[0]:.1f} antar pusat kipas (X)")
    D.dim_h(ax, -114, 114, -80, -80 - 0.01, "228 pola baut M3")
    D.finish(fig, ax, (x0 - 10, x1 + 25), (y0 - 8, y1 + 16), png("b_lid_top.png"))

    fig, ax = D.new_sheet(180, 70)
    x0, x1, y0, y1 = D.draw(ax, base, "right", lw=0.45)
    for (y, w, t) in ((55.0, 16.0, "AC IN"), (25.0, 22.0, "DC OUT")):
        D.dim_h(ax, y - w / 2, y + w / 2, 18, 24 if t == "AC IN" else 30, f"{t} {w:.0f}x14")
    D.dim_v(ax, y0, 4, x1, x1 + 6, f"{4 - y0:.0f}")
    D.finish(fig, ax, (x0 - 10, x1 + 20), (y0 - 8, y1 + 10), png("b_base_right.png"))


def dwg_bench():
    plate = BE.make_plate()
    fig, ax = D.new_sheet(180, 135)
    x0, x1, y0, y1 = D.draw(ax, plate, "top", lw=0.45)
    D.dim_h(ax, x0, x1, y1, y1 + 8, f"{x1 - x0:.1f}")
    D.dim_v(ax, y0, y1, x1, x1 + 8, f"{y1 - y0:.1f}")
    D.dim_h(ax, -115, 115, -80, y0 - 6, "230 (lubang M4)")
    D.dim_v(ax, -80, 80, -115, x0 - 8, "160 (lubang M4)")
    D.finish(fig, ax, (x0 - 22, x1 + 22), (y0 - 16, y1 + 16), png("c_plate_top.png"))

    b1, b2 = BE.make_fan_bracket(BE.FAN1), BE.make_fan_bracket(BE.FAN2)
    fig, ax = D.new_sheet(180, 60)
    a0, a1, c0, c1 = D.draw(ax, b1, "right", lw=0.5, offset=(-BE.FAN1["c"][1], 0))
    b0, b1x, d0, d1 = D.draw(ax, b2, "right", lw=0.5, offset=(-BE.FAN2["c"][1] + 120, 0))
    D.dim_v(ax, c0, c1, a1, a1 + 6, f"{c1 - c0:.0f}")
    D.dim_v(ax, d0, d1, b1x, b1x + 6, f"{d1 - d0:.0f}")
    D.dim_h(ax, a0, a1, c1, c1 + 6, f"{a1 - a0:.1f}")
    D.dim_h(ax, b0, b1x, d1, d1 + 6, f"{b1x - b0:.1f}")
    D.label(ax, (a0 + a1) / 2, c0 - 3, "Bracket kipas Orange Pi", fs=6.5)
    D.label(ax, (b0 + b1x) / 2, d0 - 3, "Bracket kipas buck", fs=6.5)
    D.finish(fig, ax, (a0 - 12, b1x + 20), (min(c0, d0) - 12, max(c1, d1) + 14), png("c_brackets_side.png"))


def dwg_camera():
    cam = CB.load_camera()[0]
    comp = cq.Compound.makeCompound([s.val() for s, _ in cam.values()])
    fig, ax = D.new_sheet(180, 85)
    x0, x1, y0, y1 = D.draw(ax, comp, "right", lw=0.45, offset=(0, 0))
    D.dim_v(ax, y0, y1, x1, x1 + 8, f"{y1 - y0:.1f}")
    D.dim_h(ax, x0, x1, y0, y0 - 8, f"{x1 - x0:.1f}")
    a0, a1, c0, c1 = D.draw(ax, comp, "front", lw=0.45, offset=(260, 0))
    D.dim_h(ax, a0, a1, c0, c0 - 8, f"{a1 - a0:.1f}")
    D.dim_v(ax, c0, c1 - 23.5, a1, a1 + 8, "162.3")
    D.label(ax, (x0 + x1) / 2, y1 + 14, "Depan", fs=6.5)
    D.label(ax, (a0 + a1) / 2, c1 + 14, "Samping", fs=6.5)
    D.finish(fig, ax, (x0 - 15, a1 + 25), (y0 - 18, y1 + 20), png("cam_views.png"))


# ===========================================================================
# PDF
# ===========================================================================

pdfmetrics.registerFont(TTFont("DV", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
INK = colors.HexColor("#1d1f22")
ACC = colors.HexColor("#c4501a")
MUTED = colors.HexColor("#5f6368")
RULE = colors.HexColor("#d9dce0")
HEAD_BG = colors.HexColor("#25282c")
ZEBRA = colors.HexColor("#f4f5f7")

S = {
    "title": ParagraphStyle("t", fontName="DVB", fontSize=24, leading=29, textColor=INK),
    "sub": ParagraphStyle("s", fontName="DV", fontSize=12, leading=16, textColor=MUTED),
    "h1": ParagraphStyle("h1", fontName="DVB", fontSize=16, leading=20, textColor=INK, spaceBefore=4, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="DVB", fontSize=11.5, leading=15, textColor=INK, spaceBefore=8, spaceAfter=4),
    "body": ParagraphStyle("b", fontName="DV", fontSize=9, leading=13, textColor=INK, spaceAfter=4),
    "small": ParagraphStyle("sm", fontName="DV", fontSize=7.5, leading=10, textColor=MUTED),
    "cap": ParagraphStyle("c", fontName="DV", fontSize=7.5, leading=10, textColor=MUTED, alignment=TA_CENTER,
                          spaceAfter=6),
    "cell": ParagraphStyle("cell", fontName="DV", fontSize=7.8, leading=10, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="DVB", fontSize=7.8, leading=10, textColor=colors.white),
}
CONTENT_W = A4[0] - 36 * mm


def P(t, st="body"):
    return Paragraph(t, S[st])


def table(rows, widths, head=True):
    data = [[Paragraph(str(c), S["cellb"] if (head and i == 0) else S["cell"]) for c in r]
            for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * CONTENT_W for w in widths], repeatRows=1 if head else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if head:
        st += [("BACKGROUND", (0, 0), (-1, 0), HEAD_BG)]
    for i in range(1 if head else 0, len(rows)):
        if i % 2 == 0:
            st.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    t.setStyle(TableStyle(st))
    return t


def img(path, w_frac=1.0, max_h=None):
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(path).getSize()
    w = CONTENT_W * w_frac
    h = w * ih / iw
    if max_h and h > max_h:
        h = max_h
        w = h * iw / ih
    return Image(path, width=w, height=h)


def img_row(paths, caps, h=None):
    n = len(paths)
    cw = CONTENT_W / n
    cells = []
    for p_, c in zip(paths, caps):
        from reportlab.lib.utils import ImageReader
        iw, ih = ImageReader(p_).getSize()
        w = cw - 4
        hh = w * ih / iw
        if h and hh > h:
            hh = h
            w = hh * iw / ih
        cells.append([Image(p_, width=w, height=hh), Paragraph(c, S["cap"])])
    t = Table([[c[0] for c in cells], [c[1] for c in cells]], colWidths=[cw] * n)
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    return t


def fig_block(path, cap, w_frac=1.0, max_h=None):
    return KeepTogether([img(path, w_frac, max_h), P(cap, "cap")])


def on_page(c, doc):
    c.saveState()
    c.setFont("DV", 7)
    c.setFillColor(MUTED)
    c.drawString(18 * mm, 10 * mm, "Laporan Desain: Controller Box & Hub Kamera CCTV")
    c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Halaman {doc.page}")
    c.setStrokeColor(RULE)
    c.setLineWidth(0.4)
    c.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
    c.restoreState()


def on_first(c, doc):
    c.saveState()
    c.setFillColor(ACC)
    c.rect(0, A4[1] - 8 * mm, A4[0], 8 * mm, stroke=0, fill=1)
    c.restoreState()


def build_pdf():
    R = lambda d, n: os.path.join(HW, d, "renders", n)  # noqa: E731
    today = datetime.date.today()
    bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September",
             "Oktober", "November", "Desember"][today.month - 1]
    st = []

    # ---------------- Cover ----------------
    st += [Spacer(1, 14 * mm), P("Laporan Desain", "sub"),
           P("Controller Box &amp; Hub Kamera CCTV", "title"), Spacer(1, 3 * mm),
           P("4× Hikvision DS-2DE2C400MWG-E · Orange Pi 5 Ultra · TP-Link LS1005 · PSU 12 V", "sub"),
           Spacer(1, 8 * mm), img(R("controller-box", "01_on_pole_iso.png"), 0.78, 120 * mm), Spacer(1, 6 * mm)]
    st.append(table([
        ["Desain", "Fungsi", "Ukuran luar (mm)", "Part cetak"],
        ["A. Utama: box + hub di atas tiang", "Pemasangan final outdoor, tahan hujan (sekitar IPX4)",
         "Bentang 440 · tinggi 263 di atas tiang", "6 (base, lid, gasket TPU, tray, bracket, hub)"],
        ["B. Prototipe box", "Uji elektronik di dalam ruangan, box tertutup", "244.8 × 176.8 × 84.4", "3"],
        ["C. Open-frame bench", "Uji elektronik tercepat, semua port terbuka", "244.8 × 176.8 × 10.4 (+bracket)", "4"],
    ], [0.27, 0.33, 0.22, 0.18]))
    st += [Spacer(1, 5 * mm),
           P(f"Tanggal: {today.day} {bulan} {today.year}. Semua ukuran dalam milimeter (mm). "
             "Gambar teknik dibuat langsung dari model CAD parametrik (CadQuery, solid B-rep), "
             "jadi angka di gambar sama dengan file STEP.", "small"),
           PageBreak()]

    # ---------------- Common components ----------------
    st += [P("1. Komponen &amp; Asumsi", "h1"),
           P("Ukuran komponen yang dipakai di ketiga desain. Kamera diambil dari gambar dimensi di datasheet resmi "
             "Hikvision. Komponen lain dari spesifikasi pabrikan atau ukuran yang Anda berikan."),
           table([
               ["Komponen", "Ukuran (mm)", "Catatan"],
               ["Hikvision DS-2DE2C400MWG-E", "163.9 (dalam) × 131.9 (Ø) × 185.8 (tinggi)",
                "Tinggi badan tanpa bracket 162.3. Plat dinding 61 × 71, pola lubang 47 × 57. Berat 600 g, "
                "12 VDC maks. 9 W / PoE 802.3af"],
               ["Orange Pi 5 Ultra", "89 × 57 × 1.6 (PCB)",
                "Heatsink pasif maks. 20 mm di bawah kipas atas. Posisi port per sisi diasumsikan (lihat bawah)"],
               ["TP-Link LS1005", "83.6 × 45.7 × 22.8", "5 port 10/100, input 5 V 0.6 A"],
               ["PSU 12 V", "128 × 97.5 × 30", "Sementara (ukuran dari Anda). Disarankan minimal 8 A untuk desain A"],
               ["Buck converter 12 V → 5 V", "65 × 40 × 22 (envelope)", "Minimal 5 V 6 A (Orange Pi + switch)"],
               ["Kipas", "60 × 60 × 37.5", "Pola lubang 50 × 50"],
               ["WAGO 221-415", "31 × 19 × 8.5", "Distribusi 12 V (+) dan (−)"],
               ["Cable gland", "M16 (Ø16.3), M20 (Ø20.3)", "Hanya desain A"],
           ], [0.26, 0.28, 0.46]),
           Spacer(1, 4 * mm), fig_block(png("cam_views.png"),
                                        "Gambar 1. Model kamera DS-2DE2C400MWG-E sesuai datasheet (depan dan samping). "
                                        "Datasheet: 131.9 × 163.9 × 185.8.",
                                        0.9),
           P("<b>Asumsi penting:</b> urutan port per sisi pada Orange Pi 5 Ultra tidak ada di dokumen publik. "
             "Model mengikuti tata letak ala Raspberry Pi: USB 3.0/2.0 + LAN di satu sisi pendek, USB-C + HDMI "
             "out/in + audio di satu sisi panjang. Tray dengan lubang slot bisa diputar 180°, dan jarak lubangnya "
             "bisa disetel (58–82 × 49–50). <b>Cocokkan dengan board asli sebelum mencetak.</b>"),
           P("<b>Konvensi sumbu:</b> part cetak memakai Z ke atas. Assembly utama tersedia dalam versi Y ke atas "
             "(Fusion 360, SolidWorks, Blender) dan Z ke atas (FreeCAD, Onshape, Bambu Studio), dengan titik pivot "
             "di tengah dasar."),
           PageBreak()]

    # ---------------- Design A ----------------
    top = CB.BOX_Z + CB.Z_RIM + CB.LID_IN_Z + CB.LID_TOP
    st += [P("2. Desain A: Box + Hub Kamera di Atas Tiang (Utama)", "h1"),
           P("Box controller tahan hujan dipasang di atas hub cetak. Hub dimasukkan ke tiang 80 × 80 dan dikunci "
             "2 baut M8 tembus. Keempat kamera dibaut ke 4 sisi hub, kabelnya masuk ke ruang kabel (chamber) di "
             "bawah box. Kipas bernapas lewat rain cowl yang hanya terbuka ke bawah."),
           img_row([R("controller-box", "01_on_pole_iso.png"), R("controller-box", "02_on_pole_low.png"),
                    R("controller-box", "04_layout_top.png")],
                   ["Tampak iso", "Tampak bawah", "Layout dalam (tanpa tutup)"], h=62 * mm),
           P("Ringkasan ukuran", "h2"),
           table([
               ["Item", "Ukuran (mm)"],
               ["Bentang kamera (luar ke luar)", "440"],
               ["Jarak sumbu kamera ke sumbu kamera", f"{2 * (CB.HUB_OUT + CB.CAM_PAD + 98):.0f}"],
               ["Tinggi di atas ujung tiang (sampai atas tutup)", f"{top:.0f}"],
               ["Box: interior", f"{2 * CB.HX:.0f} × {2 * CB.HY:.0f} × {CB.IN_Z_BASE + CB.LID_IN_Z:.0f}"],
               ["Box: base (luas cetak, termasuk cowl dan flange)", "250 × 238 × 103"],
               ["Box: tutup", "243.6 × 243.6 × 21"],
               ["Hub: luas cetak", "192 × 192 × 227"],
               ["Hub: masuk ke tiang / zona kamera / flare / chamber",
                f"80 / {CB.FLARE_Z0:.0f} / {CB.RING_Z0 - CB.FLARE_Z0:.0f} / {CB.HUB_TOP - CB.RING_Z0:.0f}"],
               ["Hub: dinding sleeve bawah / zona kamera / area pad", "7 / 10 / 15"],
               ["Tiang", "80 × 80 (kotak)"],
           ], [0.62, 0.38]),
           PageBreak(),
           P("2.1 Gambar Assembly", "h2"),
           fig_block(png("a_assembly_front.png"), "Gambar 2. Assembly tampak depan (tiang dipotong 160 mm).", 1.0,
                     125 * mm),
           fig_block(png("a_assembly_top.png"), "Gambar 3. Assembly tampak atas.", 0.85, 105 * mm),
           PageBreak(),
           P("2.2 Base Box", "h2"),
           fig_block(png("a_base_top.png"), "Gambar 4. Base tampak atas: interior 200 × 200, flange 238, rain cowl "
                                            "di kiri dan kanan.", 1.0, 120 * mm),
           fig_block(png("a_base_front.png"), "Gambar 5. Base tampak depan.", 1.0, 70 * mm),
           PageBreak(),
           P("2.3 Tutup", "h2"),
           fig_block(png("a_lid_top.png"), "Gambar 6. Tutup tampak atas, 12 baut M4 di luar garis gasket.", 0.9,
                     120 * mm),
           fig_block(png("a_lid_front.png"), "Gambar 7. Tutup tampak depan: skirt 8 mm menutupi flange.", 1.0,
                     30 * mm),
           P("Sambungan tutup: tongue 2 × 0.6 mm menekan gasket TPU 2.7 × 3.5 mm di alur 3 × 3 mm (kompresi "
             "sekitar 30 %). Skirt tutup (tebal 2.4, celah 0.4) menutupi flange dari luar. Ke-12 baut M4 berada di "
             "luar garis gasket, jadi air yang masuk lewat lubang baut tidak sampai ke dalam box."),
           PageBreak(),
           P("2.4 Hub Kamera", "h2"),
           fig_block(png("a_hub_front.png"), "Gambar 8. Hub tampak depan (garis putus-putus = tersembunyi). Pad "
                                             "kamera dengan 4 insert M4 pola 47 × 57 dan lubang kabel Ø22.", 1.0,
                     135 * mm),
           fig_block(png("a_hub_top.png"), "Gambar 9. Hub tampak atas: chamber 168, pola baut box 180 × 180 (M5), "
                                           "lubang tiang 82.", 0.75, 85 * mm),
           PageBreak(),
           P("2.5 Layout Dalam Box", "h2"),
           fig_block(png("a_layout_top.png"), "Gambar 10. Layout komponen di dalam base (tampak atas). Kipas atas "
                                              "Orange Pi (no. 9) berada tepat di atas no. 2 dan tidak digambar supaya board terlihat.", 1.0, 128 * mm)]

    comps = CB.make_components()
    rows = [["No", "Komponen", "X (min … max)", "Y (min … max)", "Z (min … max)"]]
    for i, (k, lab) in enumerate(COMP_LABELS, 1):
        bb = comps[k][0].val().BoundingBox()
        rows.append([str(i), lab, f"{f(bb.xmin)} … {f(bb.xmax)}", f"{f(bb.ymin)} … {f(bb.ymax)}",
                     f"{f(bb.zmin)} … {f(bb.zmax)}"])
    st += [P("Koordinat dari pusat interior, Z=0 di atas lantai dalam box, depan = −Y.", "small"),
           table(rows, [0.06, 0.26, 0.23, 0.23, 0.22]),
           Spacer(1, 3 * mm),
           table([
               ["Port / terminal", "Arah", "Ruang kosong"],
               ["Orange Pi sisi pendek (USB, LAN)", "Menghadap depan", "30 mm"],
               ["Orange Pi sisi panjang (USB-C, HDMI, audio)", "Menghadap tengah", "30 mm"],
               ["Switch LS1005 (5× RJ45 + DC)", "Menghadap tengah", "30 mm"],
               ["Terminal PSU", "Ujung kiri", "25 mm"],
           ], [0.5, 0.25, 0.25]),
           Spacer(1, 2 * mm),
           P("Gland di lantai box (di dalam chamber hub): " + ", ".join(
               f"{s} di ({x}, {y})" for (x, y, s) in CB.GLANDS) + ".", "small"),
           PageBreak()]

    st += [P("2.6 Cetak, Hardware, Daya", "h2"),
           table([
               ["Part", "Ukuran cetak", "Orientasi", "Setting"],
               ["base", "250 × 238 × 103", "Lantai di bed", "4 dinding, 25 % gyroid, 5 lapis atas/bawah"],
               ["lid", "243.6 × 243.6 × 21", "Permukaan atas di bed", "Sama dengan base"],
               ["camera_hub", "192 × 192 × 227", "Sleeve di bed (tegak)",
                "6 dinding, 40–50 % gyroid, modifier 100 % di zona pad kamera"],
               ["opi_fan_bracket", "64 × 90.5 × 39", "Terbalik (frame di bed)", "4 dinding, 40 %"],
               ["opi_tray", "57.5 × 89 × 9", "Datar", "3 dinding"],
               ["gasket_tpu", "215.7 × 215.7 × 3.5", "Datar", "TPU 95A, 100 %"],
           ], [0.18, 0.22, 0.25, 0.35]),
           Spacer(1, 3 * mm),
           table([
               ["Lokasi", "Insert", "Baut"],
               ["Flange box (tutup)", "12× M4", "M4 × 16"],
               ["Kipas dinding", "8× M3", "M3 × 45"],
               ["Kipas atas", "–", "4× M3 × 45 + mur"],
               ["Tray + kaki bracket", "6× M3", "M3 × 8"],
               ["Lantai box ke hub", "4× M5 (dari bawah, buntu)", "M5 × 20 + ring"],
               ["Pad kamera di hub", "16× M4", "M4 × 12"],
               ["Kunci ke tiang", "–", "2× M8 × 110 + mur nyloc + ring"],
           ], [0.4, 0.3, 0.3]),
           Spacer(1, 3 * mm),
           table([
               ["Beban", "Daya"],
               ["Orange Pi 5 Ultra", "10–20 W"], ["LS1005", "2 W"], ["3 kipas 60 × 38", "3–15 W"],
               ["4 kamera (12 V, maks. 9 W)", "36 W"], ["Total", "sekitar 50–75 W, jadi PSU 12 V minimal 8 A"],
           ], [0.6, 0.4]),
           Spacer(1, 3 * mm),
           P("<b>Perkiraan cetak (Bambu Lab A1 / P1S):</b> sekitar 2.1 kg filament, sekitar 48 jam dengan nozzle 0.4, "
             "atau sekitar 25–30 jam dengan nozzle 0.6 dan layer 0.28. Material outdoor: PETG atau ASA (PLA hanya "
             "untuk uji pasang). Gasket: TPU."),
           PageBreak()]

    # ---------------- Design B ----------------
    st += [P("3. Desain B: Prototipe Box (Dalam Ruangan)", "h1"),
           P("Box tertutup sederhana untuk uji elektronik. PSU direbahkan, kedua kipas digantung di bawah tutup "
             "(kipas 1 di atas Orange Pi sebagai intake, kipas 2 di atas PSU sebagai exhaust). Port Orange Pi dan "
             "switch diakses langsung dari luar lewat jendela. Tidak tahan air."),
           img_row([R("controller-box-proto", "01_iso.png"), R("controller-box-proto", "04_open.png"),
                    R("controller-box-proto", "02_front_ports.png")],
                   ["Tampak iso", "Isi (tutup dilepas)", "Jendela port depan"], h=55 * mm),
           fig_block(png("b_base_front.png"), "Gambar 11. Base tampak depan: jendela port Orange Pi (kiri) dan "
                                              "switch (tengah).", 1.0, 62 * mm),
           fig_block(png("b_base_right.png"), "Gambar 12. Base tampak kanan: slot AC IN dan DC OUT.", 0.9, 55 * mm),
           PageBreak(),
           fig_block(png("b_lid_top.png"), "Gambar 13. Tutup tampak atas: posisi grill dan kedua kipas.", 1.0,
                     115 * mm),
           table([
               ["Item", "Ukuran (mm)"],
               ["Base (luas cetak)", "244.8 × 176.8 × 82"],
               ["Tutup", "244.8 × 176.8 × 6.4"],
               ["Interior", f"{PB.IN_X:.0f} × {PB.IN_Y:.0f} × {PB.IN_Z:.0f}"],
               ["Tebal dinding / lantai / tutup", f"{PB.WALL} / {PB.FLOOR} / {PB.LID_T}"],
               ["Jendela Orange Pi depan (USB/LAN)", "51 × 20, dasar 12.6 dari lantai dalam"],
               ["Jendela Orange Pi kiri (USB-C/HDMI)", "61 × 12, dasar 12.6 dari lantai dalam"],
               ["Jendela switch depan", "81.6 × 23.3, dasar 1.5 dari lantai dalam"],
               ["Slot AC IN / DC OUT (kanan)", "16 × 14 / 22 × 14, dasar 4 dari lantai dalam"],
               ["Jarak kipas 1 ke heatsink Orange Pi", f"{PB.IN_Z - 3 - PB.FAN[2] - (PB.PCB_Z + PB.OPI[2] + PB.OPI_COOLER_H):.1f}"],
           ], [0.55, 0.45]),
           Spacer(1, 3 * mm),
           table([
               ["Part", "Orientasi", "Perkiraan A1 (nozzle 0.4 / 0.6)"],
               ["base", "Lantai di bed", "~6.5–7.5 jam / ~4–4.5 jam"],
               ["lid + opi_tray", "Lid terbalik, tray datar (1 plate)", "~3–3.5 jam / ~1.5–2 jam"],
               ["Total (~450 g PLA)", "", "~9.5–11 jam / ~5.5–6.5 jam"],
           ], [0.3, 0.35, 0.35]),
           P("Hardware: 4× insert M3 + M3 × 8 (tutup), 8× M3 × 40 self-tapping (kipas), 4× insert M3 (tray). "
             "Switch, buck, dan PSU dikunci dengan double tape atau zip-tie.", "small"),
           PageBreak()]

    # ---------------- Design C ----------------
    st += [P("4. Desain C: Open-Frame Bench (Cetak Tercepat)", "h1"),
           P("Pelat dasar berongga dengan bibir tepi untuk kekakuan, cradle untuk setiap komponen, anchor zip-tie, "
             "dan dua bracket kipas: di atas Orange Pi dan di atas buck converter. Posisi komponen sama dengan "
             "desain B, jadi kabel bisa langsung dipindah. <b>Perkiraan cetak A1:</b> sekitar 160 g PLA, sekitar 3 jam "
             "(nozzle 0.4) atau sekitar 2 jam (nozzle 0.6), dalam 2 plate. Terminal AC PSU terbuka, jadi jangan "
             "disentuh saat listrik menyala."),
           img_row([R("controller-bench", "01_iso.png"), R("controller-bench", "03_plate.png")],
                   ["Tampak iso dengan komponen", "Pelat dasar"], h=40 * mm),
           fig_block(png("c_plate_top.png"), "Gambar 14. Pelat dasar tampak atas: 4 lubang M4 pola 230 × 160.", 1.0,
                     82 * mm),
           fig_block(png("c_brackets_side.png"), "Gambar 15. Kedua bracket kipas, tampak samping.", 0.95, 40 * mm),
           table([
               ["Part", "Ukuran (mm)", "Orientasi cetak"],
               ["base_plate", "244.8 × 176.8 × 10.4 (pelat 2.4 + bibir 8)", "Datar"],
               ["opi_tray", "57.5 × 89 × 9", "Datar"],
               ["fan_bracket_opi", "64 × 90.5 × 39", "Terbalik"],
               ["fan_bracket_buck", "64 × 78 × 27", "Terbalik"],
           ], [0.25, 0.5, 0.25]),
           PageBreak()]

    # ---------------- Appendix ----------------
    st += [P("5. Lampiran", "h1"), P("5.1 Riwayat Revisi", "h2"),
           table([
               ["Revisi", "Perubahan"],
               ["Kepala tiang v1", "Box + spider plate + kamera envelope. Diganti setelah ada datasheet kamera."],
               ["Kepala tiang v2", "Kamera sesuai datasheet, kamera dibaut ke kolom 100 mm, kanopi melayang."],
               ["Controller box (klem tiang)", "Box cetak 3D tahan air, dipasang dengan klem selang di sisi tiang. "
                                               "Diganti karena port Orange Pi terhalang dan box dipindah ke atas tiang."],
               ["Desain A (sekarang)", "Box di atas hub cetak, port punya ruang kosong 30 mm, dinding hub 10 mm di "
                                       "zona kamera, assembly Y-up dengan pivot di dasar."],
           ], [0.28, 0.72])]
    if OLD_REV_IMG and os.path.exists(OLD_REV_IMG):
        st += [Spacer(1, 3 * mm), img_row([OLD_REV_IMG, R("cctv-pole-head", "01_iso.png")],
                                          ["Controller box versi klem tiang (diganti)", "Kepala tiang v2"], h=60 * mm)]
    st += [P("5.2 Daftar File", "h2"),
           table([
               ["Folder", "Isi"],
               ["hardware/controller-box/", "Desain A: controller_box.py, out/print/*.step, out/print_stl/*.stl, "
                                            "assembly .step (Y-up) dan _Zup.step, preview .glb"],
               ["hardware/controller-box-proto/", "Desain B: proto_box.py, out/print/*.step, assembly, .glb"],
               ["hardware/controller-bench/", "Desain C: bench.py, out/print/*.step, assembly, .glb"],
               ["hardware/cctv-pole-head/", "Kepala tiang v2 (referensi) dan model kamera"],
               ["hardware/report/", "Laporan ini dan generator-nya (make_report.py, drawing.py)"],
           ], [0.32, 0.68]),
           Spacer(1, 3 * mm),
           P("Semua model parametrik. Ubah nilai di bagian <i>Parameters</i> pada script masing-masing, lalu jalankan "
             "ulang script dan <i>make_report.py</i> untuk memperbarui file STEP dan laporan ini.", "small")]

    doc = SimpleDocTemplate(OUT_PDF, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=18 * mm, title="Laporan Desain Controller Box & Hub Kamera CCTV",
                            author="Claude Code", subject="Desain 3D controller box CCTV")
    doc.build(st, onFirstPage=on_first, onLaterPages=on_page)
    return OUT_PDF


def main():
    steps = [dwg_camera, dwg_main_assembly, dwg_main_base, dwg_main_lid, dwg_main_hub, dwg_main_layout,
             dwg_proto, dwg_bench]
    for s in steps:
        print("drawing", s.__name__, flush=True)
        s()
    print("pdf", build_pdf())


if __name__ == "__main__":
    main()
