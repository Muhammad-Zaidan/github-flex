"""
Weatherproof Controller Box (3D-printable)
==========================================
Parametric solid (B-rep) model built with CadQuery. No meshes: every part is
a true CAD solid exported as STEP. Bambu Studio, OrcaSlicer and PrusaSlicer
import STEP directly.

Contents
  - Orange Pi 5 Ultra (89 x 57 mm) on an adjustable slotted tray
  - TP-Link LS1005 switch (83.6 x 45.7 x 22.8 mm)
  - 12 V PSU, 128 x 97.5 x 30 mm (stood on its long edge against the back wall)
  - 12 V -> 5 V buck converter (for the Orange Pi and the switch)
  - 2x 60 x 60 x 37.5 mm wall fans: intake low-left, exhaust high-right
  - WAGO 221 distribution blocks
  - 3rd fan (60 x 60 x 37.5) on a bracket directly above the Orange Pi
  - 6 cable glands in the floor (5x M16, 1x M20 for AC)

Weather protection
  - Box + lid sealed with a printed TPU gasket in a tongue-and-groove joint,
    and the lid skirt overlaps the flange (double barrier).
  - Both fans breathe through rain cowls that open DOWNWARD only, with slots
    for a filter sheet. All cables enter from the floor.
  - With fans this is splash/rain-proof (about IPX4), not submersible.

Print (no supports needed)
  - base: opening up. lid: top face down. gasket: flat, TPU 95A.
  - All overhangs are chamfered to 45 degrees.

Units: mm. Interior floor top is Z=0; interior centred on X=0, Y=0.
Front = -Y (gland row), back = +Y (pole/wall mount rails).

Run:
    pip install cadquery
    python controller_box.py
"""

import os

import cadquery as cq

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

IN_X, IN_Y = 200.0, 170.0      # interior footprint
IN_Z_BASE = 100.0              # base wall height above the floor
LID_IN_Z = 10.0                # extra interior height inside the lid
WALL = 3.0
FLOOR = 3.0
EDGE_CH = 8.0                  # vertical-edge chamfer (outside)

FLANGE_OUT = 16.0              # flange reach beyond the wall
FLANGE_H = 24.0                # flange block height (incl. 45 deg underside)
GROOVE_W, GROOVE_D = 3.0, 3.0  # gasket groove
GASKET_H = 3.5                 # printed gasket height
TONGUE_W, TONGUE_H = 2.0, 0.6  # lid tongue
SKIRT_T, SKIRT_H, SKIRT_CLR = 2.4, 8.0, 0.4

LID_TOP = 3.0

INSERT_M4 = (5.6, 8.0)         # heat-set insert hole (dia, depth)
INSERT_M3 = (4.2, 6.0)
INSERT_M25 = (3.6, 5.0)

FAN = (60.0, 60.0, 37.5)
FAN_HOLE_PITCH = 50.0
FAN_Y = -28.0                  # fan centre in Y (both fans)
FAN_IN_Z = 3.0                 # intake fan bottom
FAN_OUT_Z = 18.0               # exhaust fan bottom

COWL_DEPTH = 22.0
COWL_W = 76.0

PSU = (128.0, 97.5, 30.0)      # length, height (standing), thickness
OPI = (89.0, 57.0, 1.6)
OPI_COOLER_H = 20.0            # heatsink height (passive; the top fan cools it)
TOPFAN_GAP = 2.4               # heatsink top -> bracket frame
BRACKET_POSTS_X = 36.5         # bracket posts stand on the floor right of the tray
BRACKET_POSTS_Y = (-54.0, -1.0)
SWITCH = (83.6, 45.7, 22.8)
BUCK = (65.0, 40.0, 22.0)
WAGO = (31.0, 19.0, 8.5)       # WAGO 221-415 lying flat

GLANDS = [(-75, "M16"), (-45, "M16"), (-15, "M16"), (15, "M16"), (45, "M16"), (75, "M20")]
GLAND_Y = -72.0
GLAND_D = {"M16": 16.3, "M20": 20.3}

# Colours (preview only)
C_BOX = cq.Color(0.16, 0.17, 0.18)
C_LID = cq.Color(0.13, 0.14, 0.15)
C_TPU = cq.Color(0.85, 0.40, 0.10)
C_PSU = cq.Color(0.72, 0.73, 0.74)
C_PCB = cq.Color(0.08, 0.20, 0.12)
C_SINK = cq.Color(0.22, 0.22, 0.24)
C_SW = cq.Color(0.95, 0.95, 0.95)
C_FAN = cq.Color(0.10, 0.10, 0.11)
C_BUCK = cq.Color(0.10, 0.25, 0.55)
C_WAGO = cq.Color(0.55, 0.62, 0.70)
C_GLAND = cq.Color(0.20, 0.20, 0.20)
C_TRAY = cq.Color(0.30, 0.31, 0.33)
CABLE_C = {
    "ac": cq.Color(0.05, 0.05, 0.05),
    "12v": cq.Color(0.80, 0.10, 0.10),
    "5v": cq.Color(0.95, 0.55, 0.05),
    "eth": cq.Color(0.10, 0.35, 0.85),
}

# Derived
HX, HY = IN_X / 2, IN_Y / 2
OX, OY = HX + WALL, HY + WALL
Z_RIM = IN_Z_BASE
FLX, FLY = OX + FLANGE_OUT, OY + FLANGE_OUT
GROOVE_C = WALL + 3.5                          # groove centre from interior edge
SCREW_C = WALL + FLANGE_OUT - 5.5              # screw centre from interior edge
FAN_IN_X0 = -HX                                # intake fan against left wall
FAN_OUT_X1 = HX                                # exhaust fan against right wall


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def octagon(w, d, c):
    hw, hd = w / 2, d / 2
    return [(-hw + c, -hd), (hw - c, -hd), (hw, -hd + c), (hw, hd - c),
            (hw - c, hd), (-hw + c, hd), (-hw, hd - c), (-hw, -hd + c)]


def oct_prism(w, d, c, z0, h):
    return (cq.Workplane("XY", origin=(0, 0, z0))
            .polyline(octagon(w, d, c)).close().extrude(h))


def oct_loft(w0, d0, c0, w1, d1, c1, z0, h):
    return (cq.Workplane("XY", origin=(0, 0, z0))
            .polyline(octagon(w0, d0, c0)).close()
            .workplane(offset=h)
            .polyline(octagon(w1, d1, c1)).close()
            .loft())


def oct_ring(w, d, c, width, z0, h):
    return oct_prism(w + width, d + width, c + width * 0.4142, z0, h).cut(
        oct_prism(w - width, d - width, max(c - width * 0.4142, 0.5), z0, h))


def box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY", origin=((x0 + x1) / 2, (y0 + y1) / 2, z0))
            .rect(x1 - x0, y1 - y0).extrude(z1 - z0))


def union_all(shapes):
    out = None
    for s in shapes:
        out = s if out is None else out.union(s)
    return out


def flange_screw_points():
    sx = HX + SCREW_C
    sy = HY + SCREW_C
    return [(sx, 0), (-sx, 0), (sx, sy - 34), (-sx, sy - 34), (sx, -sy + 34), (-sx, -sy + 34),
            (0, sy), (0, -sy), (65, sy), (-65, sy), (65, -sy), (-65, -sy)]


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

def make_base():
    # Outer shell
    body = oct_prism(2 * OX, 2 * OY, EDGE_CH, -FLOOR, FLOOR + Z_RIM)
    # Flange with a 45-degree underside (support-free)
    fl_z0 = Z_RIM - FLANGE_H
    under = oct_loft(2 * OX, 2 * OY, EDGE_CH,
                     2 * FLX, 2 * FLY, EDGE_CH + FLANGE_OUT * 0.4142,
                     fl_z0, FLANGE_OUT)
    lip = oct_prism(2 * FLX, 2 * FLY, EDGE_CH + FLANGE_OUT * 0.4142,
                    fl_z0 + FLANGE_OUT, FLANGE_H - FLANGE_OUT)
    body = body.union(under).union(lip)

    # Rain cowls on both X walls (full height, open at the bottom)
    for sx in (-1, 1):
        cz1 = fl_z0
        x_in, x_out = (OX, OX + COWL_DEPTH) if sx > 0 else (-OX - COWL_DEPTH, -OX)
        cowl = box(x_in, x_out, FAN_Y - COWL_W / 2, FAN_Y + COWL_W / 2, -FLOOR, cz1)
        cowl = cowl.edges("|Z and " + (">X" if sx > 0 else "<X")).chamfer(6)
        hollow = box(x_in - 1 if sx > 0 else x_in + 2.4,
                     x_out - 2.4 if sx > 0 else x_out + 1,
                     FAN_Y - COWL_W / 2 + 2.4, FAN_Y + COWL_W / 2 - 2.4,
                     -FLOOR - 1, cz1 - 2.4)
        # 45-degree inner roof so the cowl prints without support
        roof_wedge = (
            cq.Workplane("XZ", origin=(0, 0, 0))
            .polyline([
                (x_out - 2.4 * sx, cz1 - 2.4),
                (x_out - 2.4 * sx, cz1 - 2.4 - (COWL_DEPTH - 2.4)),
                (OX * sx, cz1 - 2.4),
            ]).close()
            .extrude(COWL_W / 2 - 2.4, both=True)
            .translate((0, FAN_Y, 0))
        )
        hollow = hollow.cut(roof_wedge)
        cowl = cowl.cut(hollow)
        # Filter slots (1.6 mm sheet, slides in from below)
        for sy in (-1, 1):
            slot = box(min(OX * sx + sx * 6.2, OX * sx + sx * 7.8), max(OX * sx + sx * 6.2, OX * sx + sx * 7.8),
                       min(FAN_Y + sy * (COWL_W / 2 - 2.4), FAN_Y + sy * (COWL_W / 2 - 1.2)),
                       max(FAN_Y + sy * (COWL_W / 2 - 2.4), FAN_Y + sy * (COWL_W / 2 - 1.2)),
                       -FLOOR, cz1 - 25)
            cowl = cowl.cut(slot)
        body = body.union(cowl)

    # Back mounting rails with hose-clamp slots (pole or wall)
    for x in (-60, 60):
        rail = box(x - 9, x + 9, OY, OY + 10, -FLOOR, Z_RIM - FLANGE_H)
        rail = rail.edges("|Z and >Y").chamfer(3)
        for z in (12, 52):
            rail = rail.cut(box(x - 10, x + 10, OY + 2.5, OY + 6.5, z, z + 14))
        rail = rail.cut(
            cq.Workplane("XZ", origin=(x, OY + 10, Z_RIM - FLANGE_H - 18)).circle(3.2).extrude(-10)
        )
        body = body.union(rail)

    # Hollow out the interior
    body = body.cut(oct_prism(2 * HX, 2 * HY, EDGE_CH - 1.2, 0, Z_RIM + 1))

    # Gasket groove + lid screw inserts in the flange top
    groove = oct_ring(2 * (HX + GROOVE_C), 2 * (HY + GROOVE_C), EDGE_CH + GROOVE_C * 0.4142,
                      GROOVE_W, Z_RIM - GROOVE_D, GROOVE_D + 1)
    body = body.cut(groove)
    for (x, y) in flange_screw_points():
        body = body.cut(cq.Workplane("XY", origin=(x, y, Z_RIM - INSERT_M4[1])).circle(INSERT_M4[0] / 2)
                        .extrude(INSERT_M4[1] + 1))

    # Fan openings (grilles) into the cowls
    zc_in = FAN_IN_Z + FAN[1] / 2
    zc_out = FAN_OUT_Z + FAN[1] / 2
    body = body.cut(grille(-HX - WALL - 0.5, zc_in))
    body = body.cut(grille(HX - 0.5, zc_out))

    # Fan bosses (M3 inserts), on the inside of each X wall
    for (xw, zc, s) in ((-HX, zc_in, 1), (HX, zc_out, -1)):
        for dy in (-FAN_HOLE_PITCH / 2, FAN_HOLE_PITCH / 2):
            for dz in (-FAN_HOLE_PITCH / 2, FAN_HOLE_PITCH / 2):
                b = cq.Workplane("YZ", origin=(xw, FAN_Y + dy, zc + dz)).circle(4.5).extrude(3 * s)
                b = b.cut(cq.Workplane("YZ", origin=(xw - s * 3, FAN_Y + dy, zc + dz))
                          .circle(INSERT_M3[0] / 2).extrude(s * (INSERT_M3[1])))
                body = body.union(b)

    # Cable glands through the floor
    for (x, size) in GLANDS:
        body = body.cut(cq.Workplane("XY", origin=(x, GLAND_Y, -FLOOR - 1))
                        .circle(GLAND_D[size] / 2).extrude(FLOOR + 2))
        # flat spot-face ring around each gland (helps the O-ring seal)
        body = body.cut(cq.Workplane("XY", origin=(x, GLAND_Y, -FLOOR - 0.01))
                        .circle(GLAND_D[size] / 2 + 5).circle(GLAND_D[size] / 2).extrude(0.4))

    # Floor mounting features
    body = body.union(make_floor_features())
    # Zip-tie anchors along the cable paths
    body = body.union(make_tie_anchors())
    # Decorative horizontal grooves on the front face
    for i, z in enumerate((30, 36, 42)):
        g = box(-60 + i * 8, 60 - i * 8, -OY - 0.1, -OY + 0.8, z, z + 1.6)
        body = body.cut(g)
    return body


def grille(x0, zc):
    cuts = []
    r = 27.0
    pitch = 6.0
    y = -r + pitch / 2
    while y < r:
        half = (r * r - y * y) ** 0.5 - 1.0
        if half > 4:
            cuts.append(box(x0, x0 + WALL + 1, FAN_Y + y - 1.6, FAN_Y + y + 1.6, zc - half, zc + half))
        y += pitch
    return union_all(cuts)


# ---------------------------------------------------------------------------
# Floor features: standoffs, cradles, PSU holder
# ---------------------------------------------------------------------------

OPI_TRAY = (-58.0, 31.0, -56.0, 1.0)     # x0, x1, y0, y1 of the tray
SW_POS = (-58.0, 4.0)                    # switch min corner
BUCK_POS = (34.5, 6.0)
PSU_Y0 = HY - PSU[2] - 1.0               # PSU against the back wall
WAGO_POS = [(64.0, -54.0), (64.0, -32.0)]

OPI_CX = (OPI_TRAY[0] + OPI_TRAY[1]) / 2
OPI_CY = (OPI_TRAY[2] + OPI_TRAY[3]) / 2
PCB_Z = 4 + 3 + 6                                   # tray boss + tray + pillar
SINK_TOP = PCB_Z + OPI[2] + OPI_COOLER_H
FRAME_T = 3.0
FRAME_Z0 = SINK_TOP + TOPFAN_GAP                    # bracket frame underside
TOPFAN_Z0 = FRAME_Z0 + FRAME_T                      # top fan sits on the frame
POST_BOSS_H = 4.0


def make_floor_features():
    feats = []
    # OPi tray bosses (M3 inserts), tray screws on top
    tx0, tx1, ty0, ty1 = OPI_TRAY
    for (x, y) in [(tx0 + 5, ty0 + 5), (tx1 - 5, ty0 + 5), (tx0 + 5, ty1 - 5), (tx1 - 5, ty1 - 5)]:
        b = cq.Workplane("XY", origin=(x, y, 0)).circle(4.5).extrude(4)
        b = b.cut(cq.Workplane("XY", origin=(x, y, 4 - INSERT_M3[1])).circle(INSERT_M3[0] / 2).extrude(INSERT_M3[1]))
        feats.append(b)
    # Switch cradle: 4 L-corners 10 mm tall + zip-tie strap slots
    sx0, sy0 = SW_POS
    sx1, sy1 = sx0 + SWITCH[0], sy0 + SWITCH[1]
    for (cx, cy, dx, dy) in [(sx0, sy0, 1, 1), (sx1, sy0, -1, 1), (sx0, sy1, 1, -1), (sx1, sy1, -1, -1)]:
        L = box(cx - dx * 2 if dx > 0 else cx, cx + dx * 12 if dx > 0 else cx + 2,
                cy - 2 if dy > 0 else cy, cy if dy > 0 else cy + 2, 0, 10)
        L2 = box(cx - 2 if dx > 0 else cx, cx if dx > 0 else cx + 2,
                 cy - dy * 2 if dy > 0 else cy + dy * 12, cy + dy * 12 if dy > 0 else cy + 2, 0, 10)
        feats.append(L.union(L2))
    # Buck cradle
    bx0, by0 = BUCK_POS
    bx1, by1 = bx0 + BUCK[0], by0 + BUCK[1]
    for (cx, cy, dx, dy) in [(bx0, by0, 1, 1), (bx1, by0, -1, 1), (bx0, by1, 1, -1), (bx1, by1, -1, -1)]:
        a = box(min(cx, cx + dx * 10), max(cx, cx + dx * 10), min(cy, cy - dy * 2), max(cy, cy - dy * 2), 0, 8)
        b = box(min(cx, cx - dx * 2), max(cx, cx - dx * 2), min(cy, cy + dy * 10), max(cy, cy + dy * 10), 0, 8)
        feats.append(a.union(b))
    # PSU: U-channel on the floor holding its bottom edge + standoff pads
    px0, px1 = -PSU[0] / 2, PSU[0] / 2
    for x in (px0 + 15, px1 - 15):
        u = box(x - 8, x + 8, PSU_Y0 - 3, HY, 0, 12)
        u = u.cut(box(x - 9, x + 9, PSU_Y0, PSU_Y0 + PSU[2], 2, 13))
        feats.append(u)
    # WAGO pockets
    for (x, y) in WAGO_POS:
        w = box(x - 2, x + WAGO[0] + 2, y - 2, y + WAGO[1] + 2, 0, 4)
        w = w.cut(box(x, x + WAGO[0], y, y + WAGO[1], 1.5, 5))
        feats.append(w)
    # Bosses for the top-fan bracket posts (M3 inserts)
    for y in BRACKET_POSTS_Y:
        b = cq.Workplane("XY", origin=(BRACKET_POSTS_X, y, 0)).circle(5.5).extrude(POST_BOSS_H)
        b = b.cut(cq.Workplane("XY", origin=(BRACKET_POSTS_X, y, POST_BOSS_H - INSERT_M3[1] + 2))
                  .circle(INSERT_M3[0] / 2).extrude(INSERT_M3[1]))
        feats.append(b)
    return union_all(feats)


def tie_anchor_floor(x, y, along_x=True):
    a = box(x - 5, x + 5, y - 4, y + 4, 0, 7).edges("|Z").chamfer(1.5)
    if along_x:
        a = a.cut(box(x - 6, x + 6, y - 2, y + 2, 2.0, 4.5))
    else:
        a = a.cut(box(x - 2, x + 2, y - 6, y + 6, 2.0, 4.5))
    return a


def tie_anchor_wall_front(x, z):
    """Anchor on the inside of the front wall; tie slot runs vertically."""
    a = box(x - 5, x + 5, -HY, -HY + 7, z - 5, z + 5)
    a = a.cut(box(x - 2, x + 2, -HY + 2, -HY + 4.5, z - 6, z + 6))
    # 45-degree underside so it prints without support
    wedge = (cq.Workplane("YZ", origin=(x - 5, 0, 0))
             .polyline([(-HY + 7, z - 5), (-HY + 7, z - 12), (-HY, z - 12), (-HY, z - 5)]).close()
             .extrude(10))
    wedge = wedge.cut(cq.Workplane("YZ", origin=(x - 6, 0, 0))
                      .polyline([(-HY + 7, z - 5.01), (-HY + 7, z - 12.1), (-HY - 0.1, z - 12.1)]).close()
                      .extrude(12))
    return a.union(wedge)


def make_tie_anchors():
    anchors = [tie_anchor_wall_front(x, 44) for x in (-70, -25, 20, 55)]
    anchors += [tie_anchor_floor(-88, 30, along_x=False), tie_anchor_floor(50, 0, along_x=False)]
    return union_all(anchors)


# ---------------------------------------------------------------------------
# Lid, gasket, tray
# ---------------------------------------------------------------------------

def make_lid():
    z0 = Z_RIM
    top_z = z0 + LID_IN_Z + LID_TOP
    sk_w, sk_d = 2 * (FLX + SKIRT_CLR + SKIRT_T), 2 * (FLY + SKIRT_CLR + SKIRT_T)
    sk_c = EDGE_CH + FLANGE_OUT * 0.4142 + (SKIRT_CLR + SKIRT_T) * 0.4142
    lid = oct_prism(sk_w, sk_d, sk_c, z0 - SKIRT_H, SKIRT_H + LID_IN_Z + LID_TOP)
    # Top edge chamfer for a crisp look (on the bed side when printing)
    lid = lid.faces(">Z").edges().chamfer(2.0)
    # Skirt pocket over the flange
    lid = lid.cut(oct_prism(2 * (FLX + SKIRT_CLR), 2 * (FLY + SKIRT_CLR),
                            EDGE_CH + FLANGE_OUT * 0.4142 + SKIRT_CLR * 0.4142,
                            z0 - SKIRT_H - 1, SKIRT_H + 1))
    # Interior cavity (matches the base interior)
    lid = lid.cut(oct_prism(2 * HX, 2 * HY, EDGE_CH - 1.2, z0, LID_IN_Z))
    # Tongue pressing the gasket
    tongue = oct_ring(2 * (HX + GROOVE_C), 2 * (HY + GROOVE_C), EDGE_CH + GROOVE_C * 0.4142,
                      TONGUE_W, z0 - TONGUE_H, TONGUE_H)
    lid = lid.union(tongue)
    # Screw holes + counterbores (M4)
    for (x, y) in flange_screw_points():
        lid = lid.cut(cq.Workplane("XY", origin=(x, y, z0 - 1)).circle(2.25).extrude(LID_IN_Z + LID_TOP + 2))
        lid = lid.cut(cq.Workplane("XY", origin=(x, y, top_z - 4.5)).circle(4.0).extrude(5))
    # Top styling: shallow recessed panel + three ribs (tactical, still clean)
    panel = oct_prism(2 * HX - 40, 2 * HY - 40, EDGE_CH, top_z - 0.8, 1)
    lid = lid.cut(panel)
    for i in range(3):
        y = -12 + i * 12
        lid = lid.union(box(-HX + 40, HX - 40, y - 1.5, y + 1.5, top_z - 0.8, top_z))
    # PSU hold-down pads (press the PSU into its floor channels; add 2 mm foam)
    for x in (-40, 40):
        lid = lid.union(box(x - 10, x + 10, PSU_Y0 + 3, PSU_Y0 + PSU[2] - 3, 2 + PSU[1] + 2.0, top_z - LID_TOP))
    # Internal stiffening ribs under the top
    for x in (-50, 0, 50):
        lid = lid.union(box(x - 1.2, x + 1.2, -HY + 6, HY - 6, top_z - LID_TOP - 6, top_z - LID_TOP))
    return lid


def make_gasket():
    return oct_ring(2 * (HX + GROOVE_C), 2 * (HY + GROOVE_C), EDGE_CH + GROOVE_C * 0.4142,
                    GROOVE_W - 0.3, Z_RIM - GROOVE_D, GASKET_H)


def make_opi_fan_bracket():
    """Cantilever bracket holding a 60 mm fan directly above the Orange Pi,
    blowing down onto the heatsink. Two slim posts on the right so the
    left->right cross-flow stays open. Print it upside down (frame on the bed):
    no supports."""
    half = FAN[0] / 2 + 2
    z0, z1 = FRAME_Z0, FRAME_Z0 + FRAME_T
    frame = box(OPI_CX - half, OPI_CX + half, OPI_CY - half, OPI_CY + half, z0, z1)
    frame = frame.edges("|Z").chamfer(4)
    frame = frame.cut(cq.Workplane("XY", origin=(OPI_CX, OPI_CY, z0 - 1)).circle(28.5).extrude(FRAME_T + 2))
    # finger guard bars across the opening
    for a in (0, 90):
        bar = box(OPI_CX - 29, OPI_CX + 29, OPI_CY - 1.2, OPI_CY + 1.2, z0, z1)
        frame = frame.union(bar.rotate((OPI_CX, OPI_CY, 0), (OPI_CX, OPI_CY, 1), a + 45))
    frame = frame.union(cq.Workplane("XY", origin=(OPI_CX, OPI_CY, z0)).circle(8).extrude(FRAME_T))
    # arm from the frame to the posts (two rails, open between for airflow)
    x_arm0 = OPI_CX + half - 4
    x_post = BRACKET_POSTS_X
    arms = []
    for y in BRACKET_POSTS_Y:
        arms.append(box(x_arm0, x_post + 4, y - 4, y + 4, z0, z1))
        arms.append(box(OPI_CX + FAN[0] / 2 + 0.6, x_post + 4, y - 4, y + 4, z1, z1 + 3))
        # post
        arms.append(box(x_post - 4, x_post + 4, y - 4, y + 4, POST_BOSS_H + 3, z1 + 3))
        # foot
        foot = box(x_post - 7, x_post + 7, y - 6, y + 6, POST_BOSS_H, POST_BOSS_H + 3).edges("|Z").chamfer(2)
        arms.append(foot)
        # 45-degree gusset post -> arm (prints fine upside down)
        g = (cq.Workplane("XZ", origin=(0, y, 0))
             .polyline([(x_post - 4, z0), (x_post - 4 - 14, z0), (x_post - 4, z0 - 14)]).close()
             .extrude(2.5, both=True))
        arms.append(g)
    # cross tie between the two posts, high up (above the airflow path of the PCB)
    arms.append(box(x_post - 4, x_post + 4, BRACKET_POSTS_Y[0], BRACKET_POSTS_Y[1], z1, z1 + 3))
    br = frame.union(union_all(arms))
    # fan screw holes (M3 through, fan holes on a 50 mm pitch)
    for dx in (-FAN_HOLE_PITCH / 2, FAN_HOLE_PITCH / 2):
        for dy in (-FAN_HOLE_PITCH / 2, FAN_HOLE_PITCH / 2):
            br = br.cut(cq.Workplane("XY", origin=(OPI_CX + dx, OPI_CY + dy, z0 - 1)).circle(1.7).extrude(FRAME_T + 2))
    # foot screw holes (M3 into the floor bosses)
    for y in BRACKET_POSTS_Y:
        br = br.cut(cq.Workplane("XY", origin=(x_post + 0, y, POST_BOSS_H - 1)).circle(1.7).extrude(5))
    return br


def make_opi_tray():
    tx0, tx1, ty0, ty1 = OPI_TRAY
    t = 3.0
    tray = box(tx0, tx1, ty0, ty1, 4, 4 + t).edges("|Z").chamfer(3)
    # mounting to bosses
    for (x, y) in [(tx0 + 5, ty0 + 5), (tx1 - 5, ty0 + 5), (tx0 + 5, ty1 - 5), (tx1 - 5, ty1 - 5)]:
        tray = tray.cut(cq.Workplane("XY", origin=(x, y, 3)).circle(1.7).extrude(t + 2))
        tray = tray.cut(cq.Workplane("XY", origin=(x, y, 4 + t - 1.8)).circle(3.2).extrude(2))
    # Slotted SBC pillars: hole spacing adjustable 58..82 (X) and 49..50 (Y)
    cx, cy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            px = cx + sx * 35.0
            py = cy + sy * 24.75
            pillar = (cq.Workplane("XY", origin=(px, py, 4 + t)).rect(18, 8).extrude(6)
                      .edges("|Z").chamfer(1.5))
            pillar = pillar.cut(cq.Workplane("XY", origin=(px, py, 4 + t - 1)).slot2D(14.5, 2.8).extrude(8))
            tray = tray.union(pillar)
    # Lightening + airflow windows
    tray = tray.cut(cq.Workplane("XY", origin=(cx, cy, 3)).rect(40, 26).extrude(t + 2).edges("|Z").fillet(4))
    return tray


# ---------------------------------------------------------------------------
# Components (preview / clearance check only — not printed)
# ---------------------------------------------------------------------------

def make_components():
    c = {}
    tx0, tx1, ty0, ty1 = OPI_TRAY
    cx, cy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
    pcb_z = PCB_Z
    c["orangepi5ultra_pcb"] = (box(cx - OPI[0] / 2, cx + OPI[0] / 2, cy - OPI[1] / 2, cy + OPI[1] / 2,
                                   pcb_z, pcb_z + OPI[2]), C_PCB)
    sink = box(cx - 20, cx + 36, cy - 22, cy + 22, pcb_z + OPI[2], pcb_z + OPI[2] + 4)
    sink = sink.union(
        cq.Workplane("XY", origin=(cx + 8, cy, pcb_z + OPI[2] + 4)).rarray(5, 1, 11, 1).rect(1.8, 44)
        .extrude(OPI_COOLER_H - 4))
    c["orangepi5ultra_cooler"] = (sink, C_SINK)
    # ports block on the -X edge (Ethernet + USB)
    c["orangepi5ultra_ports"] = (box(cx - OPI[0] / 2, cx - OPI[0] / 2 + 21, cy - 26, cy + 26,
                                     pcb_z + OPI[2], pcb_z + OPI[2] + 15), cq.Color(0.6, 0.6, 0.62))

    sx0, sy0 = SW_POS
    c["switch_tplink_ls1005"] = (box(sx0, sx0 + SWITCH[0], sy0, sy0 + SWITCH[1], 2, 2 + SWITCH[2])
                                 .edges("|Z").fillet(3), C_SW)
    bx0, by0 = BUCK_POS
    buck = box(bx0, bx0 + BUCK[0], by0, by0 + BUCK[1], 2, 3.6)
    buck = buck.union(box(bx0 + 8, bx0 + 30, by0 + 8, by0 + 32, 3.6, 2 + BUCK[2]))
    c["buck_12v_to_5v"] = (buck, C_BUCK)
    c["psu_12v"] = (box(-PSU[0] / 2, PSU[0] / 2, PSU_Y0, PSU_Y0 + PSU[2], 2, 2 + PSU[1]), C_PSU)
    for i, (x, y) in enumerate(WAGO_POS):
        c[f"wago_221_{i + 1}"] = (box(x, x + WAGO[0], y, y + WAGO[1], 1.5, 1.5 + WAGO[2]), C_WAGO)

    # Fans
    def fan(x0, x1, zb):
        f = box(x0, x1, FAN_Y - FAN[0] / 2, FAN_Y + FAN[0] / 2, zb, zb + FAN[1]).edges("|X").chamfer(3)
        f = f.cut(cq.Workplane("YZ", origin=(x0 - 1, FAN_Y, zb + FAN[1] / 2)).circle(28).extrude(x1 - x0 + 2))
        hub = cq.Workplane("YZ", origin=(x0, FAN_Y, zb + FAN[1] / 2)).circle(13).extrude(x1 - x0)
        return f.union(hub)

    c["fan_intake"] = (fan(-HX + 3, -HX + 3 + FAN[2], FAN_IN_Z), C_FAN)
    # top fan above the Orange Pi (axis vertical, blowing down)
    tf = box(OPI_CX - FAN[0] / 2, OPI_CX + FAN[0] / 2, OPI_CY - FAN[1] / 2, OPI_CY + FAN[1] / 2,
             TOPFAN_Z0, TOPFAN_Z0 + FAN[2]).edges("|Z").chamfer(3)
    tf = tf.cut(cq.Workplane("XY", origin=(OPI_CX, OPI_CY, TOPFAN_Z0 - 1)).circle(28).extrude(FAN[2] + 2))
    tf = tf.union(cq.Workplane("XY", origin=(OPI_CX, OPI_CY, TOPFAN_Z0)).circle(13).extrude(FAN[2]))
    c["fan_top_opi"] = (tf, C_FAN)
    c["fan_exhaust"] = (fan(HX - 3 - FAN[2], HX - 3, FAN_OUT_Z), C_FAN)

    # Glands (nut inside + dome outside)
    gl = []
    for (x, size) in GLANDS:
        d = GLAND_D[size]
        nut = cq.Workplane("XY", origin=(x, GLAND_Y, 0)).polygon(6, d + 6).extrude(5)
        body = cq.Workplane("XY", origin=(x, GLAND_Y, -FLOOR)).polygon(6, d + 6).extrude(-6)
        dome = (cq.Workplane("XY", origin=(x, GLAND_Y, -FLOOR - 6)).circle(d / 2 + 1.5).extrude(-10)
                .faces("<Z").edges().fillet(3))
        gl.append(nut.union(body).union(dome))
    c["cable_glands"] = (union_all(gl), C_GLAND)
    return c


def cable(points, r=2.2):
    segs = []
    for (a, b) in zip(points[:-1], points[1:]):
        v = cq.Vector(*b) - cq.Vector(*a)
        L = v.Length
        if L < 1e-6:
            continue
        seg = cq.Solid.makeCylinder(r, L, cq.Vector(*a), v.normalized())
        segs.append(cq.Workplane().add(seg))
    for p in points[1:-1]:
        segs.append(cq.Workplane().add(cq.Solid.makeSphere(r, cq.Vector(*p), angleDegrees1=-90, angleDegrees2=90)))
    return union_all(segs)


def make_cables():
    """Indicative routing (preview only)."""
    ps_end = (PSU[0] / 2 + 3, PSU_Y0 + 15)
    w1 = (WAGO_POS[0][0] + 15, WAGO_POS[0][1] + 9)
    w2 = (WAGO_POS[1][0] + 15, WAGO_POS[1][1] + 9)
    routes = {
        # AC in: M20 gland -> PSU AC terminals (right end)
        "cable_ac_in": ("ac", [(75, GLAND_Y, 4), (75, GLAND_Y + 8, 14), (52, -45, 30), (52, 2, 30),
                               (ps_end[0], 50, 30), (ps_end[0], ps_end[1], 40)], 3.0),
        # 12 V: PSU -> WAGO (+/-)
        "cable_12v_main": ("12v", [(ps_end[0], ps_end[1], 20), (ps_end[0] - 2, 50, 30), (56, 0, 30),
                                   (56, -30, 12), (w2[0], w2[1], 6)], 2.4),
        # 12 V: WAGO -> exhaust fan
        "cable_12v_fan_out": ("12v", [(w2[0] + 10, w2[1], 6), (90, -10, 14), (90, FAN_Y + 26, 24)], 1.4),
        # 12 V: WAGO -> intake fan, along the front wall anchors
        "cable_12v_fan_in": ("12v", [(w1[0] - 8, w1[1] - 6, 6), (55, -HY + 4, 38), (-25, -HY + 4, 38),
                                     (-70, -HY + 4, 38), (-80, FAN_Y - 26, 40)], 1.4),
        # 12 V: WAGO -> buck input
        "cable_12v_buck": ("12v", [(w2[0], w2[1] + 4, 6), (60, -5, 10), (BUCK_POS[0] + BUCK[0] - 6, BUCK_POS[1] + 4, 8)], 1.6),
        # 12 V out to the 4 cameras through the front glands
        "cable_12v_cams": ("12v", [(w1[0] - 12, w1[1] - 4, 6), (30, -62, 6), (-75, -62, 6), (-75, GLAND_Y, 4)], 1.8),
        # 5 V: buck -> Orange Pi (USB-C) and -> switch
        "cable_5v_opi": ("5v", [(BUCK_POS[0] + 6, BUCK_POS[1] + 10, 8), (30, 3, 12), (24, -30, 15)], 1.6),
        # 12 V: WAGO -> top fan (up beside the bracket post)
        "cable_12v_fan_top": ("12v", [(w1[0] - 14, w1[1] + 6, 6), (46, -40, 14), (44, -30, FRAME_Z0 + 8),
                                       (OPI_CX + 31, -30, TOPFAN_Z0 + 18)], 1.4),
        "cable_5v_switch": ("5v", [(BUCK_POS[0] + 6, BUCK_POS[1] + 30, 8), (SW_POS[0] + SWITCH[0] + 1, 30, 10)], 1.4),
        # Ethernet: 4 cameras -> switch (via left wall, above the intake fan)
        "cable_eth_cams": ("eth", [(-45, GLAND_Y, 4), (-45, GLAND_Y + 8, 10), (-88, -60, 20), (-88, -45, 70),
                                   (-88, 20, 70), (-88, 30, 20), (SW_POS[0] - 2, 30, 12)], 3.0),
        # Ethernet: uplink/spare gland -> Orange Pi
        "cable_eth_opi": ("eth", [(SW_POS[0] + 10, SW_POS[1], 12), (SW_POS[0] + 10, -2, 18), (-46, -20, 20)], 1.8),
    }
    return {k: (cable(pts, r), CABLE_C[kind]) for k, (kind, pts, r) in routes.items()}


# ---------------------------------------------------------------------------
# Build / export
# ---------------------------------------------------------------------------

def build(with_cables=True):
    printed = {
        "base": make_base(),
        "lid": make_lid(),
        "gasket_tpu": make_gasket(),
        "opi_tray": make_opi_tray(),
        "opi_fan_bracket": make_opi_fan_bracket(),
    }
    asm = cq.Assembly(name="controller_box")
    asm.add(printed["base"], name="base", color=C_BOX)
    asm.add(printed["lid"], name="lid", color=C_LID)
    asm.add(printed["gasket_tpu"], name="gasket_tpu", color=C_TPU)
    asm.add(printed["opi_tray"], name="opi_tray", color=C_TRAY)
    asm.add(printed["opi_fan_bracket"], name="opi_fan_bracket", color=C_TRAY)
    comps = make_components()
    for k, (s, col) in comps.items():
        asm.add(s, name=k, color=col)
    cables = make_cables() if with_cables else {}
    for k, (s, col) in cables.items():
        asm.add(s, name=k, color=col)
    return asm, printed, comps, cables


def clearance_report(printed, comps):
    """Volume of overlap between components and printed parts (should be ~0)."""
    issues = []
    names = list(comps)
    solids = {k: v[0].val() for k, v in comps.items()}
    for k in names:
        for p in ("base", "lid", "opi_tray", "opi_fan_bracket"):
            v = solids[k].intersect(printed[p].val()).Volume()
            if v > 1.0 and not (k == "cable_glands" and p == "base"):
                issues.append(f"{k} x {p}: {v:.0f} mm3")
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            v = solids[a].intersect(solids[b]).Volume()
            if v > 1.0:
                issues.append(f"{a} x {b}: {v:.0f} mm3")
    return issues


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "out")
    os.makedirs(os.path.join(out, "print"), exist_ok=True)

    asm, printed, comps, cables = build()
    asm.export(os.path.join(out, "controller_box_assembly.step"))
    for name, wp in printed.items():
        cq.exporters.export(wp, os.path.join(out, "print", f"{name}.step"))

    issues = clearance_report(printed, comps)
    print("Clearance:", "OK" if not issues else "\n  " + "\n  ".join(issues))
    bb = printed["base"].val().BoundingBox()
    lb = printed["lid"].val().BoundingBox()
    print(f"Base print footprint: {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f} mm")
    print(f"Lid  print footprint: {lb.xlen:.1f} x {lb.ylen:.1f} x {lb.zlen:.1f} mm")
    ab = asm.toCompound().BoundingBox()
    print(f"Assembled: {ab.xlen:.0f} x {ab.ylen:.0f} x {ab.zlen:.0f} mm (incl. glands)")


if __name__ == "__main__":
    main()
