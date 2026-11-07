"""
CCTV Pole Head: 4x Hikvision DS-2DE2C400MWG-E + controller box
=================================================================
Parametric solid (B-rep) model built with CadQuery. No meshes are used:
every part is a true CAD solid and is exported as STEP (open in Fusion 360,
FreeCAD, SolidWorks, Onshape, etc.).

Units: millimetres. Z is up. Pole axis is at X=0, Y=0. Top of pole is Z=0.

Camera geometry is taken from the dimension drawing in the official
datasheet (DS-2DE2C400MWG-E_Datasheet_20250115.pdf, "Dimension" section):
  - overall 163.9 (depth incl. bracket) x 185.8 (height incl. bracket) x 131.9 (dia.)
  - body height below bracket: 162.3
  - wall-plate hole pattern 47 x 57
Minor features (grille ring, face ring, window sizes) are scaled from the
same drawing (approx. +/- 1 mm).

Run:
    pip install cadquery
    python cctv_pole_head.py

Output (./out):
    cctv_pole_head_assembly.step   full coloured assembly
    parts/*.step                   each fabricated part on its own
"""

import os

import cadquery as cq

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

# Pole (square tube, 4 faces)
POLE_W = 80.0
POLE_T = 3.0
POLE_LEN = 450.0

# Core column: slips over the pole, the 4 cameras bolt to its 4 faces
COL_W = 100.0          # outside width (camera wall plates bolt here)
COL_GAP = 1.0          # clearance to pole
COL_BOTTOM = -150.0    # column bottom (below pole top)
COL_CHAMFER = 5.0

# Camera placement
CAM_PLATE_TOP = 40.0   # Z of the top of each camera's wall plate

# Controller box (monolith)
BOX_W = 226.0
BOX_TUB_H = 104.0      # tub height (incl. bottom chamfer)
BOX_LID_H = 16.0
BOX_GAP = 2.0          # shadow gap between tub and lid
BOX_WALL = 3.0
BOX_VCHAMFER = 10.0    # vertical edges
BOX_BCHAMFER = 24.0    # bottom 45-degree chamfer
CAM_BOX_CLEAR = 8.0    # camera bracket top -> box underside

# Floating canopy (rain + sun shield)
CANOPY_W = 262.0
CANOPY_EDGE_T = 5.0    # thickness at the edge (knife-edge look)
CANOPY_RISE = 7.0      # shallow 4-way slope to the centre
CANOPY_GAP = 8.0       # air gap above the lid

# Internal components (envelopes)
PSU = (159.0, 97.0, 30.0)        # 12 V 10 A 120 W enclosed PSU (Mean Well LRS-150-12 class)
OPI = (100.0, 75.0, 1.6)         # Orange Pi 5 Plus PCB
OPI_SINK = (64.0, 64.0, 18.0)    # heatsink + fan block
SWITCH = (158.0, 101.0, 25.0)    # 8-port gigabit desktop switch envelope

# Colours
C_BODY = cq.Color(0.15, 0.16, 0.17)    # graphite, matte
C_CANOPY = cq.Color(0.11, 0.115, 0.12)
C_STEEL = cq.Color(0.30, 0.31, 0.33)   # gunmetal
C_CAM_W = cq.Color(0.93, 0.93, 0.92)   # camera white
C_CAM_K = cq.Color(0.05, 0.05, 0.055)  # camera black
C_CAM_FACE = cq.Color(0.20, 0.20, 0.21)
C_GLASS = cq.Color(0.02, 0.02, 0.025)
C_PSU = cq.Color(0.70, 0.71, 0.72)
C_PCB = cq.Color(0.08, 0.20, 0.12)
C_SINK = cq.Color(0.20, 0.20, 0.22)
C_SW = cq.Color(0.10, 0.10, 0.11)
C_ACCENT = cq.Color(0.95, 0.55, 0.12)  # single amber status bar

# Derived
Z_BOX = CAM_PLATE_TOP + CAM_BOX_CLEAR
Z_LID = Z_BOX + BOX_TUB_H + BOX_GAP
Z_TOP = Z_LID + BOX_LID_H
Z_CANOPY = Z_TOP + CANOPY_GAP


def rot_z(shape, deg):
    return shape.rotate((0, 0, 0), (0, 0, 1), deg)


def chamfered_box(w, d, h, c):
    return cq.Workplane("XY").rect(w, d).extrude(h).edges("|Z").chamfer(c)


# ---------------------------------------------------------------------------
# Camera: DS-2DE2C400MWG-E (from datasheet dimension drawing)
# Local frame: top of the white housing at z=0, lens faces +X,
# wall bracket at -X (back of the plate at x = -98).
# ---------------------------------------------------------------------------

CAM_BODY_H = 162.3
CAM_BRACKET_ABOVE = 185.8 - 162.3     # 23.5
CAM_PLATE_BACK = 163.9 - 131.9 / 2    # 98.0 from camera axis
CAM_PLATE = (11.0, 61.0, 71.0)        # thickness, width, height
CAM_HOLES = (47.0, 57.0)


def make_camera():
    """Returns dict name -> (shape, colour) in camera-local coordinates."""
    parts = {}

    # White upper housing: tapered top cap + main cylinder (revolved profile)
    white = (
        cq.Workplane("XZ")
        .polyline([
            (0, 0), (46.5, 0), (49.5, -3), (52.0, -12.0), (64.0, -13.5),
            (65.5, -15.5), (65.5, -70.5), (64.5, -72.0), (0, -72.0),
        ]).close()
        .revolve(360, (0, 0, 0), (0, 1, 0))
    )
    # Small speaker grille dots on the front of the white housing
    for i in range(10):
        y = -13.5 + i * 3.0
        dot = cq.Workplane("YZ", origin=(64.6, y, -28)).circle(0.7).extrude(3)
        white = white.cut(dot)
    parts["housing_white"] = (white, C_CAM_W)

    # Black vent ring under the white housing
    ring = (
        cq.Workplane("XZ")
        .polyline([(0, -72.0), (65.9, -72.0), (63.0, -79.0), (0, -79.0)]).close()
        .revolve(360, (0, 0, 0), (0, 1, 0))
    )
    for k in range(72):
        g = (
            cq.Workplane("XY", origin=(64.5, 0, -78.0)).rect(4, 1.0).extrude(5.0)
        )
        ring = ring.cut(rot_z(g, k * 5))

    # Black pan hood (dome) with a front opening for the tilt head
    hood = (
        cq.Workplane("XZ")
        .moveTo(0, -79.0)
        .lineTo(53.0, -79.0)
        .lineTo(52.5, -106.0)
        .spline([(47.5, -134.0), (35.0, -152.5), (0, -161.0)], includeCurrent=True)
        .close()
        .revolve(360, (0, 0, 0), (0, 1, 0))
    )
    opening = (
        cq.Workplane("XY", origin=(45, 0, -168))
        .rect(60, 80).extrude(82)
        .edges("|X and >Z").fillet(30)
    )
    hood = hood.cut(opening)
    parts["hood_black"] = (ring.union(hood), C_CAM_K)

    # Tilt head: ball + front face ring
    zc = -112.5
    ball = cq.Workplane("XY").sphere(45.0).translate((0, 0, zc - 2))
    ball = ball.intersect(
        cq.Workplane("XZ").moveTo(0, -80).lineTo(60, -80).lineTo(60, -161.5).lineTo(0, -161.5).close()
        .revolve(360, (0, 0, 0), (0, 1, 0))
    )
    face_ring = (
        cq.Workplane("YZ", origin=(30.0, 0, zc)).circle(37.2).extrude(17.0)
        .faces(">X").edges().fillet(3.0)
    )
    head = ball.union(face_ring)
    parts["head_black"] = (head, C_CAM_K)

    face = cq.Workplane("YZ", origin=(46.0, 0, zc)).circle(31.5).extrude(1.6)
    win_cut = cq.Workplane("YZ", origin=(46.6, 0, zc + 4.0)).rect(39, 21).extrude(2).edges("|X").fillet(2.5)
    led_cut = cq.Workplane("YZ", origin=(46.6, 0, zc - 17.5)).slot2D(20, 8).extrude(2)
    face = face.cut(win_cut).cut(led_cut)
    parts["face"] = (face, C_CAM_FACE)

    glass = (
        cq.Workplane("YZ", origin=(46.6, 0, zc + 4.0)).rect(37, 19).extrude(0.6)
        .union(cq.Workplane("YZ", origin=(46.6, 0, zc - 17.5)).slot2D(18, 6).extrude(0.6))
    )
    parts["glass"] = (glass, C_GLASS)
    lens = cq.Workplane("YZ", origin=(47.0, 0, zc + 4.0)).circle(7.0).extrude(0.6)
    parts["lens"] = (lens, cq.Color(0.12, 0.13, 0.16))

    # Wall bracket: neck ring on the cap, arm, vertical wall plate
    neck = cq.Workplane("XY").circle(35).extrude(6).faces(">Z").edges().chamfer(1)
    arm = (
        cq.Workplane("XY", origin=(0, 0, 6))
        .moveTo(-CAM_PLATE_BACK + CAM_PLATE[0], -21.5)
        .lineTo(-22, -21.5)
        .threePointArc((0.0, 0), (-22, 21.5))
        .lineTo(-CAM_PLATE_BACK + CAM_PLATE[0], 21.5)
        .close()
        .extrude(12)
        .edges("|Z").fillet(1.5)
    )
    arm = arm.cut(cq.Workplane("XY", origin=(-30, 0, 6)).slot2D(14, 6, 0).extrude(12))
    pt, pw, ph = CAM_PLATE
    plate_zc = CAM_BRACKET_ABOVE - ph / 2
    plate = (
        cq.Workplane("XY", origin=(-CAM_PLATE_BACK + pt / 2, 0, plate_zc - ph / 2))
        .rect(pt, pw).extrude(ph)
        .edges("|X").fillet(4)
    )
    # waffle ribs on the plate face (as in the drawing)
    for y in (-11, 11):
        plate = plate.cut(
            cq.Workplane("XY", origin=(-CAM_PLATE_BACK + pt - 3, y, plate_zc - ph / 2 + 6))
            .rect(6.0, 14).extrude(ph - 12)
        )
    for (sy, sz) in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
        slot = (
            cq.Workplane("YZ", origin=(-CAM_PLATE_BACK, sy * CAM_HOLES[0] / 2, plate_zc + sz * CAM_HOLES[1] / 2))
            .slot2D(10, 5.5, 90).extrude(pt)
        )
        plate = plate.cut(slot)
    web = (
        cq.Workplane("XZ", origin=(0, 0, 0))
        .polyline([
            (-CAM_PLATE_BACK + pt, 6), (-CAM_PLATE_BACK + pt + 22, 6),
            (-CAM_PLATE_BACK + pt, 6 - 18),
        ]).close()
        .extrude(6, both=True)
    )
    parts["bracket"] = (neck.union(arm).union(plate).union(web), C_CAM_W)
    return parts


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def make_pole():
    outer = cq.Workplane("XY").rect(POLE_W, POLE_W).extrude(-POLE_LEN)
    inner = cq.Workplane("XY").rect(POLE_W - 2 * POLE_T, POLE_W - 2 * POLE_T).extrude(-POLE_LEN)
    return outer.cut(inner).edges("|Z").fillet(2.0)


def make_column():
    h = Z_BOX - COL_BOTTOM
    col = (
        cq.Workplane("XY", origin=(0, 0, COL_BOTTOM))
        .rect(COL_W, COL_W).extrude(h)
        .edges("|Z").chamfer(COL_CHAMFER)
        .faces("<Z").edges().chamfer(2.0)
    )
    w_in = POLE_W + 2 * COL_GAP
    col = col.cut(cq.Workplane("XY", origin=(0, 0, COL_BOTTOM)).rect(w_in, w_in).extrude(h))
    # Per face: cable entry behind the camera plate + tapped hole pattern,
    # and flush socket-head lock screws near the bottom.
    pt, pw, ph = CAM_PLATE
    plate_zc = CAM_PLATE_TOP - ph / 2
    for k in range(4):
        cuts = (
            cq.Workplane("YZ", origin=(COL_W / 2 - 10, 0, plate_zc)).rect(18, 26).extrude(12)
            .edges("|X").fillet(4)
        )
        for (sy, sz) in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
            cuts = cuts.union(
                cq.Workplane("YZ", origin=(COL_W / 2 - 10, sy * CAM_HOLES[0] / 2, plate_zc + sz * CAM_HOLES[1] / 2))
                .circle(2.5).extrude(12)
            )
        for y in (-22, 22):
            cuts = cuts.union(
                cq.Workplane("YZ", origin=(COL_W / 2 - 3, y, COL_BOTTOM + 35)).circle(8).extrude(5)
            )
        col = col.cut(rot_z(cuts, 90 * k))
    screws = None
    for k in range(4):
        for y in (-22, 22):
            s = cq.Workplane("YZ", origin=(COL_W / 2 - 3, y, COL_BOTTOM + 35)).circle(7.6).extrude(2.2)
            s = s.cut(cq.Workplane("YZ", origin=(COL_W / 2 - 1.5, y, COL_BOTTOM + 35)).polygon(6, 7).extrude(2))
            s = rot_z(s, 90 * k)
            screws = s if screws is None else screws.union(s)
    return col, screws


def octagon(w, c):
    h = w / 2
    return [(-h + c, -h), (h - c, -h), (h, -h + c), (h, h - c),
            (h - c, h), (-h + c, h), (-h, h - c), (-h, -h + c)]


def tapered_box(w, h, vc, bc, z0=0.0):
    """Square box with chamfered vertical edges and a 45-degree bottom taper."""
    taper = (
        cq.Workplane("XY", origin=(0, 0, z0))
        .polyline(octagon(w - 2 * bc, max(vc - bc * 0.4142, 0.5))).close()
        .workplane(offset=bc)
        .polyline(octagon(w, vc)).close()
        .loft()
    )
    body = (
        cq.Workplane("XY", origin=(0, 0, z0 + bc))
        .polyline(octagon(w, vc)).close().extrude(h - bc)
    )
    return taper.union(body)


def make_box_tub():
    tub = tapered_box(BOX_W, BOX_TUB_H, BOX_VCHAMFER, BOX_BCHAMFER)
    inner = tapered_box(BOX_W - 2 * BOX_WALL, BOX_TUB_H, BOX_VCHAMFER - 1.2, BOX_BCHAMFER - 1.2, BOX_WALL)
    tub = tub.cut(inner)
    # cable pass-through into the column
    tub = tub.cut(cq.Workplane("XY").rect(64, 64).extrude(BOX_WALL + 1).edges("|Z").fillet(8))
    # shadow-gap spigot (sits inside the lid line)
    spigot = (
        chamfered_box(BOX_W - 4, BOX_W - 4, BOX_GAP, BOX_VCHAMFER - 0.8)
        .cut(chamfered_box(BOX_W - 4 - 2 * BOX_WALL, BOX_W - 4 - 2 * BOX_WALL, BOX_GAP, BOX_VCHAMFER - 2))
        .translate((0, 0, BOX_TUB_H))
    )
    tub = tub.union(spigot)
    # Status light bar (recess) on each face, upper right
    for k in range(4):
        bar = (
            cq.Workplane("YZ", origin=(BOX_W / 2 - 1.0, -(BOX_W / 2 - BOX_VCHAMFER - 24), BOX_TUB_H - 16))
            .slot2D(22, 3.0).extrude(2)
        )
        tub = tub.cut(rot_z(bar, 90 * k))
    return tub.translate((0, 0, Z_BOX))


def make_status_bars():
    bars = None
    for k in range(4):
        b = (
            cq.Workplane("YZ", origin=(BOX_W / 2 - 1.0, -(BOX_W / 2 - BOX_VCHAMFER - 24), Z_BOX + BOX_TUB_H - 16))
            .slot2D(21, 2.4).extrude(0.8)
        )
        b = rot_z(b, 90 * k)
        bars = b if bars is None else bars.union(b)
    return bars


def make_box_lid():
    lid = (
        chamfered_box(BOX_W, BOX_W, BOX_LID_H, BOX_VCHAMFER)
        .faces(">Z").edges().chamfer(1.5)
    )
    lid = lid.cut(
        chamfered_box(BOX_W - 2 * BOX_WALL, BOX_W - 2 * BOX_WALL, BOX_LID_H - BOX_WALL, BOX_VCHAMFER - 1.2)
    )
    return lid.translate((0, 0, Z_LID))


def make_canopy_standoffs():
    pins = None
    for (x, y) in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
        p = (
            cq.Workplane("XY", origin=(x * 62, y * 62, Z_TOP))
            .circle(9).extrude(CANOPY_GAP + 1)
        )
        pins = p if pins is None else pins.union(p)
    return pins


def make_canopy():
    c = CANOPY_W
    base = (
        cq.Workplane("XY").rect(c, c).extrude(CANOPY_EDGE_T)
        .edges("|Z").chamfer(BOX_VCHAMFER + 8)
    )
    rise = (
        cq.Workplane("XY", origin=(0, 0, CANOPY_EDGE_T))
        .rect(c - 2 * 18, c - 2 * 18)
        .workplane(offset=CANOPY_RISE)
        .rect(c * 0.42, c * 0.42)
        .loft()
    )
    # make the rise follow the chamfered outline: intersect with an extruded outline
    rise = rise.intersect(
        cq.Workplane("XY", origin=(0, 0, CANOPY_EDGE_T)).rect(c, c).extrude(CANOPY_RISE)
        .edges("|Z").chamfer(BOX_VCHAMFER + 8)
    )
    flat = (
        cq.Workplane("XY", origin=(0, 0, CANOPY_EDGE_T))
        .rect(c - 2 * 18, c - 2 * 18).extrude(0.01)
    )
    canopy = base.union(rise)
    # knife edge: underside chamfer
    canopy = canopy.faces("<Z").edges().chamfer(3.5)
    # drip groove under the edge
    groove = (
        chamfered_box(c - 16, c - 16, 1.8, BOX_VCHAMFER + 4)
        .cut(chamfered_box(c - 22, c - 22, 1.8, BOX_VCHAMFER + 2))
    )
    canopy = canopy.cut(groove)
    return canopy.translate((0, 0, Z_CANOPY))


def make_internals():
    floor = Z_BOX + BOX_BCHAMFER + 2
    parts = {}
    bp_w = BOX_W - 2 * BOX_WALL - 8
    parts["backplate"] = (
        chamfered_box(bp_w, bp_w, 2.0, BOX_VCHAMFER - 3).translate((0, 0, floor)),
        C_STEEL,
    )
    # brackets holding the backplate above the chamfer zone
    legs = None
    for (x, y) in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
        l = cq.Workplane("XY", origin=(x * 70, y * 70, Z_BOX + BOX_WALL)).rect(8, 8).extrude(floor - Z_BOX - BOX_WALL)
        legs = l if legs is None else legs.union(l)
    parts["backplate_posts"] = (legs, C_STEEL)
    base = floor + 2
    inner_half = (BOX_W - 2 * BOX_WALL) / 2 - 6
    px = -inner_half + PSU[1] / 2 + 6
    parts["psu_12v_10a"] = (
        cq.Workplane("XY", origin=(px, 0, base)).rect(PSU[1], PSU[0]).extrude(PSU[2])
        .faces(">Z").workplane().rarray(8, 1, 9, 1).rect(4, 60).cutBlind(-1),
        C_PSU,
    )
    ox = inner_half - OPI[1] / 2 - 4
    oy = -inner_half + OPI[0] / 2 + 8
    so = 8.0
    parts["orangepi5plus_pcb"] = (
        cq.Workplane("XY", origin=(ox, oy, base + so)).rect(OPI[1], OPI[0]).extrude(OPI[2]),
        C_PCB,
    )
    parts["orangepi5plus_standoffs"] = (
        cq.Workplane("XY", origin=(ox, oy, base))
        .rect(OPI[1] - 8, OPI[0] - 8, forConstruction=True).vertices()
        .polygon(6, 5.5).extrude(so),
        C_STEEL,
    )
    fins = cq.Workplane("XY", origin=(ox, oy, base + so + OPI[2])).rect(OPI_SINK[0], OPI_SINK[1]).extrude(4)
    fins = fins.union(
        cq.Workplane("XY", origin=(ox, oy, base + so + OPI[2] + 4))
        .rarray(5.5, 1, 11, 1).rect(2.0, OPI_SINK[1]).extrude(OPI_SINK[2] - 4)
    )
    parts["orangepi5plus_heatsink"] = (fins, C_SINK)
    shelf_z = base + PSU[2] + 10
    sw_cx = -inner_half + SWITCH[1] / 2 + 12
    shelf = cq.Workplane("XY", origin=(sw_cx, 0, shelf_z - 2)).rect(SWITCH[1] + 12, SWITCH[0] + 8).extrude(2)
    shelf_legs = (
        cq.Workplane("XY", origin=(sw_cx, 0, base))
        .rect(SWITCH[1] + 4, SWITCH[0] + 2, forConstruction=True).vertices()
        .rect(6, 6).extrude(shelf_z - 2 - base)
    )
    parts["switch_shelf"] = (shelf.union(shelf_legs), C_STEEL)
    parts["network_switch_8p"] = (
        cq.Workplane("XY", origin=(sw_cx, 0, shelf_z)).rect(SWITCH[1], SWITCH[0]).extrude(SWITCH[2])
        .edges("|Z").fillet(4),
        C_SW,
    )
    parts["terminal_block"] = (
        cq.Workplane("XY", origin=(inner_half - 18, inner_half - 52, base)).rect(16, 80).extrude(30),
        cq.Color(0.15, 0.30, 0.55),
    )
    return parts


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def camera_location(k):
    """Camera k (0..3) on column face k, facing outward."""
    x = COL_W / 2 + CAM_PLATE_BACK
    z = CAM_PLATE_TOP - CAM_BRACKET_ABOVE
    return cq.Location((0, 0, 0), (0, 0, 1), 90 * k) * cq.Location((x, 0, z))


def build():
    asm = cq.Assembly(name="cctv_pole_head")
    fabricated = {}

    asm.add(make_pole(), name="pole_80x80", color=C_STEEL)

    col, screws = make_column()
    asm.add(col, name="core_column", color=C_BODY)
    asm.add(screws, name="column_lock_screws", color=C_STEEL)
    fabricated["core_column"] = col

    tub = make_box_tub()
    asm.add(tub, name="controller_box_tub", color=C_BODY)
    fabricated["controller_box_tub"] = tub
    lid = make_box_lid()
    asm.add(lid, name="controller_box_lid", color=C_BODY)
    fabricated["controller_box_lid"] = lid
    asm.add(make_status_bars(), name="status_light_bars", color=C_ACCENT)

    asm.add(make_canopy_standoffs(), name="canopy_standoffs", color=C_STEEL)
    canopy = make_canopy()
    asm.add(canopy, name="canopy", color=C_CANOPY)
    fabricated["canopy"] = canopy

    for name, (shape, colr) in make_internals().items():
        asm.add(shape, name=name, color=colr)

    cam = make_camera()
    for k in range(4):
        loc = camera_location(k)
        for pname, (shape, colr) in cam.items():
            asm.add(shape, name=f"camera_{k + 1}_{pname}", color=colr, loc=loc)

    return asm, fabricated, cam


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "out")
    os.makedirs(os.path.join(out, "parts"), exist_ok=True)

    asm, fabricated, cam = build()
    asm.export(os.path.join(out, "cctv_pole_head_assembly.step"))
    for name, wp in fabricated.items():
        cq.exporters.export(wp, os.path.join(out, "parts", f"{name}.step"))

    cam_asm = cq.Assembly(name="DS-2DE2C400MWG-E")
    for pname, (shape, colr) in cam.items():
        cam_asm.add(shape, name=pname, color=colr)
    cam_asm.export(os.path.join(out, "parts", "camera_DS-2DE2C400MWG-E.step"))
    cbb = cam_asm.toCompound().BoundingBox()
    print(f"Camera bbox: {cbb.xlen:.1f} x {cbb.ylen:.1f} x {cbb.zlen:.1f} mm (datasheet 163.9 x 131.9 x 185.8)")

    bb = asm.toCompound().BoundingBox()
    print(f"Overall: {bb.xlen:.0f} x {bb.ylen:.0f} x {bb.zlen:.0f} mm (incl. {POLE_LEN:.0f} mm pole stub)")
    print(f"Top of canopy above pole top: {bb.zmax:.0f} mm")
    print(f"Lowest camera point: {CAM_PLATE_TOP - 185.8:.0f} mm")
    return asm


if __name__ == "__main__":
    main()
