"""
Weatherproof Controller Box + Pole-Top Camera Hub (3D-printable)
================================================================
Parametric solid (B-rep) model built with CadQuery. No meshes: every part is
a true CAD solid exported as STEP. Bambu Studio, OrcaSlicer and PrusaSlicer
import STEP directly.

System (top to bottom)
  - Controller box (base + lid + TPU gasket) sitting on top of the hub
  - Camera hub: slides over an 80 x 80 square pole, locked with two M8
    through-bolts; 4 faces carry the 4 Hikvision DS-2DE2C400MWG-E wall
    plates (47 x 57 hole pattern); a cable chamber under the box collects
    the camera cables and the AC feed coming up inside the pole.

Inside the box
  - Orange Pi 5 Ultra (89 x 57) on a slotted tray, long axis front-back.
    Short-edge ports (USB/LAN) face the front, long-edge ports (HDMI/USB-C)
    face the centre; both have a 30 mm free zone that the clearance check
    enforces.
  - TP-Link LS1005 (83.6 x 45.7 x 22.8) on the right, ports facing inward.
  - 12 V PSU 128 x 97.5 x 30 standing against the back wall, terminals left.
  - 12 V -> 5 V buck converter standing behind the Orange Pi.
  - Fans 60 x 60 x 37.5: intake (left wall), exhaust (right wall, high) and
    one on a bracket directly above the Orange Pi.
  - 2x WAGO 221-415 under the exhaust fan.
  - Cable glands in the floor, inside the hub chamber: 4x M16 cameras,
    1x M16 spare, 1x M20 AC.

Weather protection
  - Tongue-and-groove lid with a TPU gasket + overlapping skirt.
  - Fans breathe through rain cowls that open DOWNWARD only.
  - All cables enter from below, inside the hub chamber.
  - With fans: rain/splash-proof (about IPX4), not submersible.

Units: mm. Box-local: interior floor top is Z=0, interior centred on X=0, Y=0.
Assembly: pole top at Z=0. Front = -Y.

Run:
    pip install cadquery
    python controller_box.py
"""

import importlib.util
import os

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Parameters: box
# ---------------------------------------------------------------------------

IN_X, IN_Y = 200.0, 200.0      # interior footprint (square)
IN_Z_BASE = 100.0
LID_IN_Z = 10.0
WALL = 3.0
FLOOR = 3.0
EDGE_CH = 8.0

FLANGE_OUT = 16.0
FLANGE_H = 24.0
GROOVE_W, GROOVE_D = 3.0, 3.0
GASKET_H = 3.5
TONGUE_W, TONGUE_H = 2.0, 0.6
SKIRT_T, SKIRT_H, SKIRT_CLR = 2.4, 8.0, 0.4
LID_TOP = 3.0

INSERT_M5 = (6.4, 7.0)
INSERT_M4 = (5.6, 8.0)
INSERT_M3 = (4.2, 6.0)

FAN = (60.0, 60.0, 37.5)
FAN_HOLE_PITCH = 50.0
FAN_IN_Y, FAN_IN_Z = -10.0, 6.0      # intake fan centre Y, bottom Z (left wall)
FAN_OUT_Y, FAN_OUT_Z = 58.0, 18.0    # exhaust fan centre Y, bottom Z (right wall)
COWL_DEPTH = 22.0
COWL_W = 72.0

PSU = (128.0, 97.5, 30.0)            # length, height (standing), thickness
PSU_X0 = -70.0                       # PSU left end (terminal end)
OPI = (89.0, 57.0, 1.6)              # length (Y), width (X), thickness
OPI_COOLER_H = 20.0
OPI_TRAY = (-56.0, 1.0, -48.0, 41.0)  # x0, x1, y0, y1
SWITCH = (83.6, 45.7, 22.8)          # length (Y here), width (X), height
SW_POS = (53.0, -60.0)               # min corner (x, y); ports face -X
BUCK = (65.0, 40.0, 22.0)            # standing on edge: 65 (X) x 22 (Y) x 40 (Z)
BUCK_POS = (-6.0, 44.0)
WAGO = (31.0, 19.0, 8.5)
WAGO_POS = [(63.0, 30.0), (63.0, 53.0)]
PORT_FREE = 30.0                     # free space in front of every port row

TOPFAN_GAP = 2.4
BRACKET_POSTS = [(-48.0, 49.0), (-18.0, 49.0)]
POST_BOSS_H = 4.0

GLANDS = [(-45, -66, "M16"), (-20, -66, "M16"), (5, -66, "M16"), (30, -66, "M16"),
          (40, -30, "M16"), (-70, 54, "M20")]
GLAND_D = {"M16": 16.3, "M20": 20.3}

HUB_BOLTS = [(90, 90), (-90, 90), (90, -90), (-90, -90)]

# ---------------------------------------------------------------------------
# Parameters: hub / pole / cameras  (assembly Z: pole top = 0)
# ---------------------------------------------------------------------------

POLE_W = 80.0
POLE_LEN = 400.0
HUB_IN = POLE_W / 2 + 1.0            # sleeve inner half-width (1 mm clearance)
HUB_OUT = 51.0                       # camera zone outer half-width (10 mm wall)
HUB_OUT_LOW = 48.0                   # lower sleeve over the pole (7 mm wall)
HUB_Z0 = -80.0                       # sleeve bottom (80 mm engagement)
CAM_PAD = 5.0                        # camera mounting pads on each face
CAM_PLATE_TOP_Z = 77.0               # top of camera wall plate
FLARE_Z0 = 80.0
CHAMBER_OUT = 96.0                   # chamber outer half-width
CHAMBER_IN = 84.0
FLARE_T = 6.0
RING_Z0 = FLARE_Z0 + (CHAMBER_OUT - HUB_OUT)   # 45-degree flare
HUB_TOP = RING_Z0 + 22.0             # = box floor underside
LOCK_BOLTS = [(-25.0, "x"), (-58.0, "y")]       # M8 through-bolts (z, axis)

# Colours (preview only)
C_BOX = cq.Color(0.16, 0.17, 0.18)
C_LID = cq.Color(0.13, 0.14, 0.15)
C_HUB = cq.Color(0.20, 0.21, 0.22)
C_TPU = cq.Color(0.85, 0.40, 0.10)
C_PSU = cq.Color(0.72, 0.73, 0.74)
C_PCB = cq.Color(0.08, 0.20, 0.12)
C_SINK = cq.Color(0.22, 0.22, 0.24)
C_PORT = cq.Color(0.62, 0.62, 0.64)
C_SW = cq.Color(0.95, 0.95, 0.95)
C_FAN = cq.Color(0.10, 0.10, 0.11)
C_BUCK = cq.Color(0.10, 0.25, 0.55)
C_WAGO = cq.Color(0.55, 0.62, 0.70)
C_GLAND = cq.Color(0.20, 0.20, 0.20)
C_TRAY = cq.Color(0.30, 0.31, 0.33)
C_STEEL = cq.Color(0.45, 0.46, 0.48)
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
GROOVE_C = WALL + 3.5
SCREW_C = WALL + FLANGE_OUT - 5.5
PSU_Y0 = HY - PSU[2] - 1.0
OPI_CX = (OPI_TRAY[0] + OPI_TRAY[1]) / 2
OPI_CY = (OPI_TRAY[2] + OPI_TRAY[3]) / 2
PCB_Z = 4 + 3 + 6
SINK_TOP = PCB_Z + OPI[2] + OPI_COOLER_H
FRAME_T = 3.0
FRAME_Z0 = SINK_TOP + TOPFAN_GAP
TOPFAN_Z0 = FRAME_Z0 + FRAME_T
BOX_Z = HUB_TOP + FLOOR              # assembly offset of the box-local frame


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def octagon(w, d, c):
    hw, hd = w / 2, d / 2
    return [(-hw + c, -hd), (hw - c, -hd), (hw, -hd + c), (hw, hd - c),
            (hw - c, hd), (-hw + c, hd), (-hw, hd - c), (-hw, -hd + c)]


def oct_prism(w, d, c, z0, h):
    return cq.Workplane("XY", origin=(0, 0, z0)).polyline(octagon(w, d, c)).close().extrude(h)


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


def rot_z(shape, deg):
    return shape.rotate((0, 0, 0), (0, 0, 1), deg)


def flange_screw_points():
    s = HX + SCREW_C
    pts = []
    for v in (-62.0, 0.0, 62.0):
        pts += [(s, v), (-s, v), (v, s), (v, -s)]
    return pts


def teardrop_x(x0, length, y, z, r):
    """Horizontal hole along X with a 45-degree pointed top (prints without support)."""
    c = cq.Workplane("YZ", origin=(x0, y, z)).circle(r).extrude(length)
    t = (cq.Workplane("YZ", origin=(x0, y, z))
         .polyline([(-r * 0.7071, r * 0.7071), (0, r * 1.4142), (r * 0.7071, r * 0.7071)]).close()
         .extrude(length))
    return c.union(t)


# ---------------------------------------------------------------------------
# Box base
# ---------------------------------------------------------------------------

def grille(x0, yc, zc):
    cuts = []
    r, pitch = 27.0, 6.0
    y = -r + pitch / 2
    while y < r:
        half = (r * r - y * y) ** 0.5 - 1.0
        if half > 4:
            cuts.append(box(x0, x0 + WALL + 1, yc + y - 1.6, yc + y + 1.6, zc - half, zc + half))
        y += pitch
    return union_all(cuts)


def make_cowl(sx, yc):
    cz1 = Z_RIM - FLANGE_H
    x_in, x_out = (OX, OX + COWL_DEPTH) if sx > 0 else (-OX - COWL_DEPTH, -OX)
    cowl = box(x_in, x_out, yc - COWL_W / 2, yc + COWL_W / 2, -FLOOR, cz1)
    cowl = cowl.edges("|Z and " + (">X" if sx > 0 else "<X")).chamfer(6)
    hollow = box(x_in - 1 if sx > 0 else x_in + 2.4, x_out - 2.4 if sx > 0 else x_out + 1,
                 yc - COWL_W / 2 + 2.4, yc + COWL_W / 2 - 2.4, -FLOOR - 1, cz1 - 2.4)
    roof = (cq.Workplane("XZ")
            .polyline([(x_out - 2.4 * sx, cz1 - 2.4), (x_out - 2.4 * sx, cz1 - COWL_DEPTH),
                       (OX * sx, cz1 - 2.4)]).close()
            .extrude(COWL_W / 2 - 2.4, both=True).translate((0, yc, 0)))
    cowl = cowl.cut(hollow.cut(roof))
    for sy in (-1, 1):
        x_a, x_b = sorted((OX * sx + sx * 6.2, OX * sx + sx * 7.8))
        y_a, y_b = sorted((yc + sy * (COWL_W / 2 - 2.4), yc + sy * (COWL_W / 2 - 1.2)))
        cowl = cowl.cut(box(x_a, x_b, y_a, y_b, -FLOOR, cz1 - 25))
    return cowl


def make_base():
    body = oct_prism(2 * OX, 2 * OY, EDGE_CH, -FLOOR, FLOOR + Z_RIM)
    fl_z0 = Z_RIM - FLANGE_H
    under = oct_loft(2 * OX, 2 * OY, EDGE_CH, 2 * FLX, 2 * FLY, EDGE_CH + FLANGE_OUT * 0.4142,
                     fl_z0, FLANGE_OUT)
    lip = oct_prism(2 * FLX, 2 * FLY, EDGE_CH + FLANGE_OUT * 0.4142,
                    fl_z0 + FLANGE_OUT, FLANGE_H - FLANGE_OUT)
    body = body.union(under).union(lip)
    body = body.union(make_cowl(-1, FAN_IN_Y)).union(make_cowl(1, FAN_OUT_Y))

    body = body.cut(oct_prism(2 * HX, 2 * HY, EDGE_CH - 1.2, 0, Z_RIM + 1))

    body = body.cut(oct_ring(2 * (HX + GROOVE_C), 2 * (HY + GROOVE_C), EDGE_CH + GROOVE_C * 0.4142,
                             GROOVE_W, Z_RIM - GROOVE_D, GROOVE_D + 1))
    for (x, y) in flange_screw_points():
        body = body.cut(cq.Workplane("XY", origin=(x, y, Z_RIM - INSERT_M4[1]))
                        .circle(INSERT_M4[0] / 2).extrude(INSERT_M4[1] + 1))

    zc_in = FAN_IN_Z + FAN[1] / 2
    zc_out = FAN_OUT_Z + FAN[1] / 2
    body = body.cut(grille(-HX - WALL - 0.5, FAN_IN_Y, zc_in))
    body = body.cut(grille(HX - 0.5, FAN_OUT_Y, zc_out))
    for (xw, yc, zc, s) in ((-HX, FAN_IN_Y, zc_in, 1), (HX, FAN_OUT_Y, zc_out, -1)):
        for dy in (-FAN_HOLE_PITCH / 2, FAN_HOLE_PITCH / 2):
            for dz in (-FAN_HOLE_PITCH / 2, FAN_HOLE_PITCH / 2):
                b = cq.Workplane("YZ", origin=(xw, yc + dy, zc + dz)).circle(4.5).extrude(3 * s)
                b = b.cut(cq.Workplane("YZ", origin=(xw - s * 3, yc + dy, zc + dz))
                          .circle(INSERT_M3[0] / 2).extrude(s * INSERT_M3[1]))
                body = body.union(b)

    body = body.union(make_floor_features())
    body = body.union(make_tie_anchors())

    for (x, y, size) in GLANDS:
        d = GLAND_D[size]
        body = body.cut(cq.Workplane("XY", origin=(x, y, -FLOOR - 1)).circle(d / 2).extrude(FLOOR + 2))
    # Hub bolts: M5 inserts from below into floor bosses (blind, stays sealed)
    for (x, y) in HUB_BOLTS:
        body = body.cut(cq.Workplane("XY", origin=(x, y, -FLOOR - 0.01)).circle(INSERT_M5[0] / 2)
                        .extrude(INSERT_M5[1]))
    # Front face styling grooves
    for i, z in enumerate((30, 36, 42)):
        body = body.cut(box(-60 + i * 8, 60 - i * 8, -OY - 0.1, -OY + 0.8, z, z + 1.6))
    return body


def make_floor_features():
    feats = []
    tx0, tx1, ty0, ty1 = OPI_TRAY
    for (x, y) in [(tx0 + 5, ty0 + 5), (tx1 - 5, ty0 + 5), (tx0 + 5, ty1 - 5), (tx1 - 5, ty1 - 5)]:
        b = cq.Workplane("XY", origin=(x, y, 0)).circle(4.5).extrude(4)
        b = b.cut(cq.Workplane("XY", origin=(x, y, 4 - INSERT_M3[1])).circle(INSERT_M3[0] / 2).extrude(INSERT_M3[1]))
        feats.append(b)
    # Switch cradle (4 L-corners)
    sx0, sy0 = SW_POS
    sx1, sy1 = sx0 + SWITCH[1], sy0 + SWITCH[0]
    for (cx, cy, dx, dy) in [(sx0, sy0, 1, 1), (sx1, sy0, -1, 1), (sx0, sy1, 1, -1), (sx1, sy1, -1, -1)]:
        a = box(*sorted((cx, cx + dx * 10)), *sorted((cy, cy - dy * 2)), 0, 8)
        b = box(*sorted((cx, cx - dx * 2)), *sorted((cy, cy + dy * 10)), 0, 8)
        feats.append(a.union(b))
    # Buck: standing slot holder
    bx0, by0 = BUCK_POS
    for x in (bx0 + 6, bx0 + BUCK[0] - 6):
        h = box(x - 5, x + 5, by0 - 2.5, by0 + BUCK[2] + 2.5, 0, 12)
        h = h.cut(box(x - 6, x + 6, by0, by0 + BUCK[2], 2, 13))
        feats.append(h)
    # PSU U-channels
    for x in (PSU_X0 + 15, PSU_X0 + PSU[0] - 15):
        u = box(x - 8, x + 8, PSU_Y0 - 3, HY, 0, 12)
        u = u.cut(box(x - 9, x + 9, PSU_Y0, PSU_Y0 + PSU[2], 2, 13))
        feats.append(u)
    # WAGO pockets
    for (x, y) in WAGO_POS:
        w = box(x - 2, x + WAGO[0] + 2, y - 2, y + WAGO[1] + 2, 0, 4)
        feats.append(w.cut(box(x, x + WAGO[0], y, y + WAGO[1], 1.5, 5)))
    # Top-fan bracket post bosses
    for (x, y) in BRACKET_POSTS:
        b = cq.Workplane("XY", origin=(x, y, 0)).circle(5.5).extrude(POST_BOSS_H)
        feats.append(b.cut(cq.Workplane("XY", origin=(x, y, POST_BOSS_H - INSERT_M3[1] + 2))
                           .circle(INSERT_M3[0] / 2).extrude(INSERT_M3[1])))
    # Hub bolt bosses (floor + boss = 8 mm for the M5 inserts)
    for (x, y) in HUB_BOLTS:
        feats.append(cq.Workplane("XY", origin=(x, y, 0)).circle(5.5).extrude(5))
    return union_all(feats)


def tie_anchor_floor(x, y, along_x=True):
    a = box(x - 5, x + 5, y - 4, y + 4, 0, 7).edges("|Z").chamfer(1.5)
    if along_x:
        return a.cut(box(x - 6, x + 6, y - 2, y + 2, 2.0, 4.5))
    return a.cut(box(x - 2, x + 2, y - 6, y + 6, 2.0, 4.5))


def tie_anchor_wall_front(x, z):
    a = box(x - 5, x + 5, -HY, -HY + 7, z - 5, z + 5)
    a = a.cut(box(x - 2, x + 2, -HY + 2, -HY + 4.5, z - 6, z + 6))
    wedge = (cq.Workplane("YZ", origin=(x - 5, 0, 0))
             .polyline([(-HY + 7, z - 5), (-HY, z - 12), (-HY, z - 5)]).close().extrude(10))
    return a.union(wedge)


def make_tie_anchors():
    anchors = [tie_anchor_wall_front(x, 44) for x in (-70, -25, 20, 55)]
    anchors += [tie_anchor_floor(-88, 32, along_x=False), tie_anchor_floor(15, -12, along_x=False)]
    return union_all(anchors)


# ---------------------------------------------------------------------------
# Lid, gasket, tray, fan bracket
# ---------------------------------------------------------------------------

def make_lid():
    z0 = Z_RIM
    top_z = z0 + LID_IN_Z + LID_TOP
    sk_c = EDGE_CH + FLANGE_OUT * 0.4142 + (SKIRT_CLR + SKIRT_T) * 0.4142
    lid = oct_prism(2 * (FLX + SKIRT_CLR + SKIRT_T), 2 * (FLY + SKIRT_CLR + SKIRT_T), sk_c,
                    z0 - SKIRT_H, SKIRT_H + LID_IN_Z + LID_TOP)
    lid = lid.faces(">Z").edges().chamfer(2.0)
    lid = lid.cut(oct_prism(2 * (FLX + SKIRT_CLR), 2 * (FLY + SKIRT_CLR),
                            EDGE_CH + FLANGE_OUT * 0.4142 + SKIRT_CLR * 0.4142, z0 - SKIRT_H - 1, SKIRT_H + 1))
    lid = lid.cut(oct_prism(2 * HX, 2 * HY, EDGE_CH - 1.2, z0, LID_IN_Z))
    lid = lid.union(oct_ring(2 * (HX + GROOVE_C), 2 * (HY + GROOVE_C), EDGE_CH + GROOVE_C * 0.4142,
                             TONGUE_W, z0 - TONGUE_H, TONGUE_H))
    for (x, y) in flange_screw_points():
        lid = lid.cut(cq.Workplane("XY", origin=(x, y, z0 - 1)).circle(2.25).extrude(LID_IN_Z + LID_TOP + 2))
        lid = lid.cut(cq.Workplane("XY", origin=(x, y, top_z - 4.5)).circle(4.0).extrude(5))
    lid = lid.cut(oct_prism(2 * HX - 40, 2 * HY - 40, EDGE_CH, top_z - 0.8, 1))
    for i in range(3):
        y = -12 + i * 12
        lid = lid.union(box(-HX + 40, HX - 40, y - 1.5, y + 1.5, top_z - 0.8, top_z))
    for x in (PSU_X0 + 30, PSU_X0 + PSU[0] - 30):
        lid = lid.union(box(x - 10, x + 10, PSU_Y0 + 3, PSU_Y0 + PSU[2] - 3, 2 + PSU[1] + 2.0, top_z - LID_TOP))
    for x in (-50, 0, 50):
        lid = lid.union(box(x - 1.2, x + 1.2, -HY + 6, HY - 6, top_z - LID_TOP - 6, top_z - LID_TOP))
    return lid


def make_gasket():
    return oct_ring(2 * (HX + GROOVE_C), 2 * (HY + GROOVE_C), EDGE_CH + GROOVE_C * 0.4142,
                    GROOVE_W - 0.3, Z_RIM - GROOVE_D, GASKET_H)


def make_opi_tray():
    tx0, tx1, ty0, ty1 = OPI_TRAY
    t = 3.0
    tray = box(tx0, tx1, ty0, ty1, 4, 4 + t).edges("|Z").chamfer(3)
    for (x, y) in [(tx0 + 5, ty0 + 5), (tx1 - 5, ty0 + 5), (tx0 + 5, ty1 - 5), (tx1 - 5, ty1 - 5)]:
        tray = tray.cut(cq.Workplane("XY", origin=(x, y, 3)).circle(1.7).extrude(t + 2))
        tray = tray.cut(cq.Workplane("XY", origin=(x, y, 4 + t - 1.8)).circle(3.2).extrude(2))
    # Slotted pillars: hole spacing adjustable 58..82 along the board length (Y)
    # and 49..50 across (X). Board can be flipped 180 degrees.
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = OPI_CX + sx * 24.75, OPI_CY + sy * 35.0
            p = cq.Workplane("XY", origin=(px, py, 4 + t)).rect(8, 18).extrude(6).edges("|Z").chamfer(1.5)
            p = p.cut(cq.Workplane("XY", origin=(px, py, 4 + t - 1)).slot2D(14.5, 2.8, 90).extrude(8))
            tray = tray.union(p)
    return tray.cut(cq.Workplane("XY", origin=(OPI_CX, OPI_CY, 3)).rect(26, 40).extrude(t + 2).edges("|Z").fillet(4))


def make_opi_fan_bracket():
    """60 mm fan directly above the Orange Pi, blowing down. Two posts BEHIND
    the board (no ports there). Print upside down (frame on the bed)."""
    half = FAN[0] / 2 + 2
    z0, z1 = FRAME_Z0, FRAME_Z0 + FRAME_T
    fr = box(OPI_CX - half, OPI_CX + half, OPI_CY - half, OPI_CY + half, z0, z1).edges("|Z").chamfer(4)
    fr = fr.cut(cq.Workplane("XY", origin=(OPI_CX, OPI_CY, z0 - 1)).circle(28.5).extrude(FRAME_T + 2))
    for a in (45, 135):
        bar = box(OPI_CX - 29, OPI_CX + 29, OPI_CY - 1.2, OPI_CY + 1.2, z0, z1)
        fr = fr.union(bar.rotate((OPI_CX, OPI_CY, 0), (OPI_CX, OPI_CY, 1), a))
    fr = fr.union(cq.Workplane("XY", origin=(OPI_CX, OPI_CY, z0)).circle(8).extrude(FRAME_T))
    parts = [fr]
    y_arm0 = OPI_CY + half - 4
    for (x, y) in BRACKET_POSTS:
        parts.append(box(x - 4, x + 4, y_arm0, y + 4, z0, z1))
        parts.append(box(x - 4, x + 4, OPI_CY + FAN[1] / 2 + 0.6, y + 4, z1, z1 + 3))
        parts.append(box(x - 4, x + 4, y - 4, y + 4, POST_BOSS_H + 3, z1 + 3))
        parts.append(box(x - 7, x + 7, y - 6, y + 6, POST_BOSS_H, POST_BOSS_H + 3).edges("|Z").chamfer(2))
        g = (cq.Workplane("YZ", origin=(x, 0, 0))
             .polyline([(y - 4, z0), (y - 18, z0), (y - 4, z0 - 14)]).close()
             .extrude(2.5, both=True))
        parts.append(g)
    (xa, ya), (xb, _) = BRACKET_POSTS
    parts.append(box(xa, xb, ya - 4, ya + 4, z1, z1 + 3))
    br = union_all(parts)
    for dx in (-FAN_HOLE_PITCH / 2, FAN_HOLE_PITCH / 2):
        for dy in (-FAN_HOLE_PITCH / 2, FAN_HOLE_PITCH / 2):
            br = br.cut(cq.Workplane("XY", origin=(OPI_CX + dx, OPI_CY + dy, z0 - 1)).circle(1.7).extrude(FRAME_T + 2))
    for (x, y) in BRACKET_POSTS:
        br = br.cut(cq.Workplane("XY", origin=(x, y, POST_BOSS_H - 1)).circle(1.7).extrude(5))
    return br


# ---------------------------------------------------------------------------
# Hub (assembly coordinates: pole top at Z=0)
# ---------------------------------------------------------------------------

def make_hub():
    # Sleeve
    # Lower sleeve (over the pole, 7 mm wall) -> 45-degree step -> camera zone (10 mm wall)
    step = HUB_OUT - HUB_OUT_LOW
    hub = box(-HUB_OUT_LOW, HUB_OUT_LOW, -HUB_OUT_LOW, HUB_OUT_LOW, HUB_Z0, -step).edges("|Z").chamfer(4)
    hub = hub.union(oct_loft(2 * HUB_OUT_LOW, 2 * HUB_OUT_LOW, 4, 2 * HUB_OUT, 2 * HUB_OUT, 4, -step, step))
    hub = hub.union(box(-HUB_OUT, HUB_OUT, -HUB_OUT, HUB_OUT, 0, FLARE_Z0).edges("|Z").chamfer(4))
    # 45-degree flare up to the chamber, then the chamber ring
    flare = oct_loft(2 * HUB_OUT, 2 * HUB_OUT, 4, 2 * CHAMBER_OUT, 2 * CHAMBER_OUT, 10,
                     FLARE_Z0, RING_Z0 - FLARE_Z0)
    ring = oct_prism(2 * CHAMBER_OUT, 2 * CHAMBER_OUT, 10, RING_Z0, HUB_TOP - RING_Z0)
    hub = hub.union(flare).union(ring)
    # Camera pads on the 4 faces
    pt, pw, ph = 11.0, 61.0, 71.0
    for k in range(4):
        pad = box(HUB_OUT - 0.5, HUB_OUT + CAM_PAD, -pw / 2 - 3, pw / 2 + 3, CAM_PLATE_TOP_Z - ph - 3, CAM_PLATE_TOP_Z + 1)
        pad = pad.edges("|X").chamfer(2)
        hub = hub.union(rot_z(pad, 90 * k))
    # Hollow: pole bore + chamber
    hub = hub.cut(box(-HUB_IN, HUB_IN, -HUB_IN, HUB_IN, HUB_Z0 - 1, FLARE_Z0 + 0.01))
    inner_flare = oct_loft(2 * HUB_IN, 2 * HUB_IN, 1, 2 * (CHAMBER_IN), 2 * CHAMBER_IN, 6,
                           FLARE_Z0, RING_Z0 - FLARE_Z0)
    hub = hub.cut(inner_flare)
    hub = hub.cut(oct_prism(2 * CHAMBER_IN, 2 * CHAMBER_IN, 6, RING_Z0, HUB_TOP - RING_Z0 + 1))
    # Pole stop: 4 small ledges at the pole top so the hub sits on the pole
    for k in range(4):
        hub = hub.union(rot_z(box(HUB_IN - 6, HUB_IN, -12, 12, 0, 4), 90 * k))
    # Camera mounting: insert holes (M4) + cable entry behind each plate
    plate_zc = CAM_PLATE_TOP_Z - ph / 2
    for k in range(4):
        cuts = []
        for (sy, sz) in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
            cuts.append(cq.Workplane("YZ", origin=(HUB_OUT + CAM_PAD - INSERT_M4[1], sy * 23.5, plate_zc + sz * 28.5))
                        .circle(INSERT_M4[0] / 2).extrude(INSERT_M4[1] + 1))
        cuts.append(teardrop_x(HUB_IN - 2, HUB_OUT + CAM_PAD - HUB_IN + 3, 0, plate_zc, 11))
        hub = hub.cut(rot_z(union_all(cuts), 90 * k))
    # Lock bolts M8 through hub + pole
    for (z, ax) in LOCK_BOLTS:
        h = teardrop_x(-HUB_OUT_LOW - 2, 2 * HUB_OUT_LOW + 4, 0, z, 4.3)
        hub = hub.cut(h if ax == "x" else rot_z(h, 90))
    # Box bolts: M5 clearance + counterbore from below (exits the flare outside)
    for (x, y) in HUB_BOLTS:
        hub = hub.cut(cq.Workplane("XY", origin=(x, y, RING_Z0 - 40)).circle(2.8).extrude(HUB_TOP - RING_Z0 + 41))
        hub = hub.cut(cq.Workplane("XY", origin=(x, y, RING_Z0 - 60)).circle(5.5).extrude(60 + 10))
    return hub


def make_pole():
    p = box(-POLE_W / 2, POLE_W / 2, -POLE_W / 2, POLE_W / 2, -POLE_LEN, 0)
    p = p.cut(box(-POLE_W / 2 + 3, POLE_W / 2 - 3, -POLE_W / 2 + 3, POLE_W / 2 - 3, -POLE_LEN - 1, 1))
    for (z, ax) in LOCK_BOLTS:
        h = cq.Workplane("YZ", origin=(-POLE_W, 0, z)).circle(4.3).extrude(2 * POLE_W)
        p = p.cut(h if ax == "x" else rot_z(h, 90))
    return p


def make_lock_bolts():
    out = []
    for (z, ax) in LOCK_BOLTS:
        L = 2 * HUB_OUT_LOW + 16
        b = cq.Workplane("YZ", origin=(-HUB_OUT_LOW - 6, 0, z)).circle(4).extrude(L)
        b = b.union(cq.Workplane("YZ", origin=(-HUB_OUT_LOW - 6, 0, z)).polygon(6, 14.6).extrude(-5.5))
        b = b.union(cq.Workplane("YZ", origin=(HUB_OUT_LOW + 1, 0, z)).polygon(6, 14.6).extrude(7))
        out.append(b if ax == "x" else rot_z(b, 90))
    return union_all(out)


# ---------------------------------------------------------------------------
# Components, keep-out zones, cables (box-local)
# ---------------------------------------------------------------------------

def make_components():
    c = {}
    tx0, tx1, ty0, ty1 = OPI_TRAY
    x0, x1 = OPI_CX - OPI[1] / 2, OPI_CX + OPI[1] / 2
    y0, y1 = OPI_CY - OPI[0] / 2, OPI_CY + OPI[0] / 2
    c["orangepi5ultra_pcb"] = (box(x0, x1, y0, y1, PCB_Z, PCB_Z + OPI[2]), C_PCB)
    zt = PCB_Z + OPI[2]
    sink = box(OPI_CX - 22, OPI_CX + 16, OPI_CY - 18, OPI_CY + 26, zt, zt + 4)
    sink = sink.union(cq.Workplane("XY", origin=(OPI_CX - 2, OPI_CY + 4, zt + 4))
                      .rarray(5, 1, 8, 1).rect(1.8, 44).extrude(OPI_COOLER_H - 4))
    c["orangepi5ultra_heatsink"] = (sink, C_SINK)
    # Short edge (front): 2x USB stacks + RJ45
    c["orangepi5ultra_ports_front"] = (box(x0 + 2, x1 - 2, y0 - 2, y0 + 18, zt, zt + 15), C_PORT)
    # Long edge (+X): USB-C, 2x HDMI, audio
    c["orangepi5ultra_ports_side"] = (box(x1 - 11, x1 + 1, y0 + 26, y1 - 6, zt, zt + 7), C_PORT)

    sx0, sy0 = SW_POS
    c["switch_tplink_ls1005"] = (box(sx0, sx0 + SWITCH[1], sy0, sy0 + SWITCH[0], 2, 2 + SWITCH[2])
                                 .edges("|Z").fillet(3), C_SW)
    bx0, by0 = BUCK_POS
    buck = box(bx0, bx0 + BUCK[0], by0 + 9, by0 + 10.6, 2, 2 + BUCK[1])
    buck = buck.union(box(bx0 + 8, bx0 + 34, by0 + 10.6, by0 + BUCK[2], 8, 34))
    c["buck_12v_to_5v"] = (buck, C_BUCK)
    c["psu_12v"] = (box(PSU_X0, PSU_X0 + PSU[0], PSU_Y0, PSU_Y0 + PSU[2], 2, 2 + PSU[1]), C_PSU)
    for i, (x, y) in enumerate(WAGO_POS):
        c[f"wago_221_{i + 1}"] = (box(x, x + WAGO[0], y, y + WAGO[1], 1.5, 1.5 + WAGO[2]), C_WAGO)

    def wall_fan(x0, x1, yc, zb):
        f = box(x0, x1, yc - FAN[0] / 2, yc + FAN[0] / 2, zb, zb + FAN[1]).edges("|X").chamfer(3)
        f = f.cut(cq.Workplane("YZ", origin=(x0 - 1, yc, zb + FAN[1] / 2)).circle(28).extrude(x1 - x0 + 2))
        return f.union(cq.Workplane("YZ", origin=(x0, yc, zb + FAN[1] / 2)).circle(13).extrude(x1 - x0))

    c["fan_intake"] = (wall_fan(-HX + 3, -HX + 3 + FAN[2], FAN_IN_Y, FAN_IN_Z), C_FAN)
    c["fan_exhaust"] = (wall_fan(HX - 3 - FAN[2], HX - 3, FAN_OUT_Y, FAN_OUT_Z), C_FAN)
    tf = box(OPI_CX - 30, OPI_CX + 30, OPI_CY - 30, OPI_CY + 30, TOPFAN_Z0, TOPFAN_Z0 + FAN[2]).edges("|Z").chamfer(3)
    tf = tf.cut(cq.Workplane("XY", origin=(OPI_CX, OPI_CY, TOPFAN_Z0 - 1)).circle(28).extrude(FAN[2] + 2))
    tf = tf.union(cq.Workplane("XY", origin=(OPI_CX, OPI_CY, TOPFAN_Z0)).circle(13).extrude(FAN[2]))
    c["fan_top_opi"] = (tf, C_FAN)

    gl = []
    for (x, y, size) in GLANDS:
        d = GLAND_D[size]
        nut = cq.Workplane("XY", origin=(x, y, 0)).polygon(6, d + 6).extrude(5)
        body = cq.Workplane("XY", origin=(x, y, -FLOOR)).polygon(6, d + 6).extrude(-6)
        dome = (cq.Workplane("XY", origin=(x, y, -FLOOR - 6)).circle(d / 2 + 1.5).extrude(-10)
                .faces("<Z").edges().fillet(3))
        gl.append(nut.union(body).union(dome))
    c["cable_glands"] = (union_all(gl), C_GLAND)
    return c


def make_keepouts():
    """Free space required in front of connectors (checked, not exported)."""
    x0, x1 = OPI_CX - OPI[1] / 2, OPI_CX + OPI[1] / 2
    y0, y1 = OPI_CY - OPI[0] / 2, OPI_CY + OPI[0] / 2
    zt = PCB_Z + OPI[2]
    sx0, sy0 = SW_POS
    return {
        "opi_front_ports": box(x0, x1, y0 - 2 - PORT_FREE, y0 - 2, zt - 3, zt + 22),
        "opi_side_ports": box(x1 + 1, x1 + 1 + PORT_FREE, y0 + 26, y1 - 6, zt - 3, zt + 15),
        "switch_ports": box(sx0 - PORT_FREE, sx0, sy0, sy0 + SWITCH[0], 8, 2 + SWITCH[2] + 4),
        "psu_terminals": box(PSU_X0 - 25, PSU_X0, PSU_Y0, PSU_Y0 + 24, 10, 2 + PSU[1]),
    }


def cable(points, r=2.2):
    segs = []
    for (a, b) in zip(points[:-1], points[1:]):
        v = cq.Vector(*b) - cq.Vector(*a)
        if v.Length < 1e-6:
            continue
        segs.append(cq.Workplane().add(cq.Solid.makeCylinder(r, v.Length, cq.Vector(*a), v.normalized())))
    for p in points[1:-1]:
        segs.append(cq.Workplane().add(cq.Solid.makeSphere(r, cq.Vector(*p), angleDegrees1=-90, angleDegrees2=90)))
    return union_all(segs)


def make_cables():
    w1 = (WAGO_POS[0][0] + 10, WAGO_POS[0][1] + 9)
    w2 = (WAGO_POS[1][0] + 10, WAGO_POS[1][1] + 9)
    term = (PSU_X0 - 3, PSU_Y0 + 15)
    sw_port_x = SW_POS[0] - 1
    routes = {
        "cable_ac_in": ("ac", [(-70, 54, 4), (-74, 60, 20), (term[0], term[1], 30)], 3.0),
        "cable_12v_main": ("12v", [(term[0], term[1], 60), (-62, 67.5, 50), (57, 67.5, 50),
                                   (57, 67.5, 14), (w2[0], w2[1], 8)], 2.4),
        "cable_12v_fan_out": ("12v", [(w1[0] + 12, w1[1], 8), (88, 40, 16), (88, FAN_OUT_Y - 26, 22)], 1.4),
        "cable_12v_buck": ("12v", [(w2[0] - 8, w2[1], 8), (57, 62, 14), (BUCK_POS[0] + BUCK[0] - 4, 62, 18)], 1.6),
        "cable_12v_fan_in": ("12v", [(w1[0], w1[1] - 6, 8), (70, 26, 34), (70, -75, 34), (60, -HY + 4, 44),
                                     (-70, -HY + 4, 44), (-82, FAN_IN_Y - 26, 40)], 1.4),
        "cable_12v_cams": ("12v", [(w1[0] - 6, w1[1] - 6, 8), (48, 20, 6), (48, -50, 6), (30, -66, 6),
                                   (-45, -66, 6)], 1.8),
        "cable_12v_fan_top": ("12v", [(w1[0] - 8, w1[1], 8), (40, 36, 30), (10, 36, 60),
                                      (OPI_CX + 31, OPI_CY + 10, TOPFAN_Z0 + 20)], 1.4),
        "cable_5v_opi": ("5v", [(BUCK_POS[0] + 10, BUCK_POS[1], 20), (8, 30, 18),
                                (OPI_CX + OPI[1] / 2 + 3, OPI_CY - 10, PCB_Z + 5)], 1.6),
        "cable_5v_switch": ("5v", [(BUCK_POS[0] + 50, BUCK_POS[1], 14), (46, 30, 12), (sw_port_x, 15, 12)], 1.4),
        "cable_eth_cams": ("eth", [(-20, -66, 6), (-5, -80, 26), (40, -80, 26), (46, -40, 16),
                                   (sw_port_x, -30, 14)], 3.0),
        "cable_eth_opi": ("eth", [(OPI_CX, OPI_CY - OPI[0] / 2 - 4, 22), (20, -76, 30), (44, -50, 18),
                                  (sw_port_x, -48, 14)], 1.8),
    }
    return {k: (cable(pts, r), CABLE_C[kind]) for k, (kind, pts, r) in routes.items()}


# ---------------------------------------------------------------------------
# Cameras (from the pole-head model, datasheet-accurate)
# ---------------------------------------------------------------------------

def load_camera():
    path = os.path.join(HERE, "..", "cctv-pole-head", "cctv_pole_head.py")
    spec = importlib.util.spec_from_file_location("cctv_pole_head", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.make_camera(), mod.CAM_PLATE_BACK, mod.CAM_BRACKET_ABOVE


# ---------------------------------------------------------------------------
# Build / export
# ---------------------------------------------------------------------------

def build(with_cables=True, with_system=True):
    printed = {
        "base": make_base(),
        "lid": make_lid(),
        "gasket_tpu": make_gasket(),
        "opi_tray": make_opi_tray(),
        "opi_fan_bracket": make_opi_fan_bracket(),
        "camera_hub": make_hub(),
    }
    comps = make_components()
    cables = make_cables() if with_cables else {}

    asm = cq.Assembly(name="controller_box_on_pole")
    box_loc = cq.Location((0, 0, BOX_Z))
    asm.add(printed["base"], name="base", color=C_BOX, loc=box_loc)
    asm.add(printed["lid"], name="lid", color=C_LID, loc=box_loc)
    asm.add(printed["gasket_tpu"], name="gasket_tpu", color=C_TPU, loc=box_loc)
    asm.add(printed["opi_tray"], name="opi_tray", color=C_TRAY, loc=box_loc)
    asm.add(printed["opi_fan_bracket"], name="opi_fan_bracket", color=C_TRAY, loc=box_loc)
    for k, (s, col) in comps.items():
        asm.add(s, name=k, color=col, loc=box_loc)
    for k, (s, col) in cables.items():
        asm.add(s, name=k, color=col, loc=box_loc)
    if with_system:
        asm.add(printed["camera_hub"], name="camera_hub", color=C_HUB)
        asm.add(make_pole(), name="pole_80x80", color=C_STEEL)
        asm.add(make_lock_bolts(), name="lock_bolts_m8", color=C_STEEL)
        cam, plate_back, above = load_camera()
        for k in range(4):
            loc = (cq.Location((0, 0, 0), (0, 0, 1), 90 * k)
                   * cq.Location((HUB_OUT + CAM_PAD + plate_back, 0, CAM_PLATE_TOP_Z - above)))
            for pname, (shape, col) in cam.items():
                asm.add(shape, name=f"camera_{k + 1}_{pname}", color=col, loc=loc)
    return asm, printed, comps, cables


def clearance_report(printed, comps):
    issues = []
    solids = {k: v[0].val() for k, v in comps.items()}
    names = list(solids)
    box_parts = ("base", "lid", "opi_tray", "opi_fan_bracket")
    for k in names:
        for p in box_parts:
            v = solids[k].intersect(printed[p].val()).Volume()
            if v > 1.0 and not (k == "cable_glands" and p == "base"):
                issues.append(f"{k} x {p}: {v:.0f} mm3")
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            v = solids[a].intersect(solids[b]).Volume()
            if v > 1.0:
                issues.append(f"{a} x {b}: {v:.0f} mm3")
    # Connector free zones must be empty
    for kname, kz in make_keepouts().items():
        kv = kz.val()
        for n, s in solids.items():
            if n.startswith("orangepi5ultra_ports") or n == "cable_glands":
                continue
            v = kv.intersect(s).Volume()
            if v > 1.0:
                issues.append(f"PORT BLOCKED {kname} by {n}: {v:.0f} mm3")
        for p in box_parts:
            v = kv.intersect(printed[p].val()).Volume()
            if v > 1.0:
                issues.append(f"PORT BLOCKED {kname} by {p}: {v:.0f} mm3")
    # Hub vs glands (below the floor) and vs pole
    hub = printed["camera_hub"].val()
    g = comps["cable_glands"][0].translate((0, 0, BOX_Z)).val()
    v = hub.intersect(g).Volume()
    if v > 1.0:
        issues.append(f"cable_glands x camera_hub: {v:.0f} mm3")
    v = hub.intersect(make_pole().val()).Volume()
    if v > 1.0:
        issues.append(f"pole x camera_hub: {v:.0f} mm3")
    return issues


def main():
    out = os.path.join(HERE, "out")
    os.makedirs(os.path.join(out, "print"), exist_ok=True)
    asm, printed, comps, cables = build()
    # Main assembly: pivot at the bottom centre (Z=0 / Y=0 at the lowest point).
    #   *_assembly.step       Y-up (Fusion 360, SolidWorks, Blender, Unity)
    #   *_assembly_Zup.step   Z-up (FreeCAD, Onshape, Bambu Studio, Inventor)
    lift = cq.Location((0, 0, POLE_LEN))
    to_yup = cq.Location((0, 0, 0), (1, 0, 0), -90)      # Z -> Y, front (-Y) -> +Z
    for name, frame in (("controller_box_on_pole_assembly_Zup.step", lift),
                        ("controller_box_on_pole_assembly.step", to_yup * lift)):
        a = cq.Assembly(name="controller_box_on_pole")
        for ch in asm.children:
            a.add(ch.obj, name=ch.name, color=ch.color, loc=frame * ch.loc)
        a.export(os.path.join(out, name))
    for name, wp in printed.items():
        cq.exporters.export(wp, os.path.join(out, "print", f"{name}.step"))
    issues = clearance_report(printed, comps)
    print("Clearance:", "OK" if not issues else "\n  " + "\n  ".join(issues))
    for n in ("base", "lid", "camera_hub"):
        bb = printed[n].val().BoundingBox()
        print(f"{n:11s} print size: {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f} mm")
    ab = asm.toCompound().BoundingBox()
    print(f"Assembled (incl. {POLE_LEN:.0f} mm pole stub): {ab.xlen:.0f} x {ab.ylen:.0f} x {ab.zlen:.0f} mm,"
          f" top of lid {BOX_Z + Z_RIM + LID_IN_Z + LID_TOP:.0f} mm above pole top")


if __name__ == "__main__":
    main()
