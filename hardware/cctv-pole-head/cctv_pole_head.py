"""
CCTV Pole Head — 4x Hikvision DS-2DE2C400MWG-E + controller box
=================================================================
Parametric solid (B-rep) model built with CadQuery. No meshes are used:
every part is a true CAD solid and is exported as STEP (open in Fusion 360,
FreeCAD, SolidWorks, Onshape, etc.).

Units: millimetres. Z is up. Pole axis is at X=0, Y=0. Top of pole is Z=0.

Run:
    pip install cadquery
    python cctv_pole_head.py

Output (./out):
    cctv_pole_head_assembly.step   full coloured assembly
    parts/*.step                   each fabricated part on its own
"""

import math
import os

import cadquery as cq

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

# Pole (square tube, 4 faces)
POLE_W = 80.0          # outside width of square pole
POLE_T = 3.0           # wall thickness
POLE_LEN = 450.0       # length shown in the model (below the head)

# Sleeve that slips over the top of the pole
SLEEVE_GAP = 1.0
SLEEVE_T = 5.0
SLEEVE_H = 130.0
SLEEVE_DROP = 110.0    # how far the sleeve hangs below the pole top

# Spider plate (carries the box and the 4 camera arms)
PLATE_T = 8.0
PLATE_CORE = 236.0     # square core under the box
ARM_W = 76.0
ARM_REACH = 214.0      # from pole axis to arm tip
CAM_R = 168.0          # from pole axis to camera mount centre

# Controller box
BOX_W = 226.0          # outside, square
BOX_H = 122.0
BOX_WALL = 3.0
BOX_CHAMFER = 14.0     # vertical edge chamfer (faceted look)
BOX_LIFT = 0.0         # box sits right on the plate

# Rain roof
ROOF_W = 300.0
ROOF_H = 48.0
ROOF_TOP_W = 70.0
ROOF_T = 3.0
ROOF_SKIRT = 12.0
ROOF_GAP = 10.0        # air gap between box lid and roof (heat escape)

# Camera envelope (DS-2DE2C400MWG-E datasheet: 163.9 x 185.8 x 131.9 mm, 600 g)
CAM_W = 163.9
CAM_H = 185.8
CAM_D = 131.9

# Internal components (envelopes)
PSU = (159.0, 97.0, 30.0)        # 12 V 10 A 120 W enclosed PSU (Mean Well LRS-150-12 class)
OPI = (100.0, 75.0, 1.6)         # Orange Pi 5 Plus PCB
OPI_SINK = (64.0, 64.0, 18.0)    # heatsink + fan block
SWITCH = (158.0, 101.0, 25.0)    # 8-port gigabit desktop switch envelope

# Colours
C_BODY = cq.Color(0.16, 0.17, 0.18)    # graphite / RAL 7021-ish, matte
C_STEEL = cq.Color(0.32, 0.33, 0.35)   # gunmetal
C_ROOF = cq.Color(0.13, 0.14, 0.15)
C_CAM = cq.Color(0.90, 0.90, 0.88)
C_GLASS = cq.Color(0.04, 0.05, 0.06)
C_PSU = cq.Color(0.70, 0.71, 0.72)
C_PCB = cq.Color(0.08, 0.20, 0.12)
C_SINK = cq.Color(0.20, 0.20, 0.22)
C_SW = cq.Color(0.10, 0.10, 0.11)
C_ACCENT = cq.Color(0.85, 0.45, 0.10)  # small amber status LED only

# Derived heights
Z_PLATE = SLEEVE_H - SLEEVE_DROP            # plate underside
Z_BOX = Z_PLATE + PLATE_T + BOX_LIFT        # box underside
Z_LID = Z_BOX + BOX_H                       # box top
Z_ROOF = Z_LID + ROOF_GAP                   # roof skirt underside


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rot_z(shape, deg):
    return shape.rotate((0, 0, 0), (0, 0, 1), deg)


def chamfered_box(w, d, h, c):
    """Box with chamfered vertical edges, base at z=0."""
    return (
        cq.Workplane("XY")
        .rect(w, d)
        .extrude(h)
        .edges("|Z")
        .chamfer(c)
    )


# ---------------------------------------------------------------------------
# Parts
# ---------------------------------------------------------------------------

def make_pole():
    outer = cq.Workplane("XY").rect(POLE_W, POLE_W).extrude(-POLE_LEN)
    inner = cq.Workplane("XY").rect(POLE_W - 2 * POLE_T, POLE_W - 2 * POLE_T).extrude(-POLE_LEN)
    return outer.cut(inner).edges("|Z").fillet(2.0)


def make_sleeve():
    w_in = POLE_W + 2 * SLEEVE_GAP
    w_out = w_in + 2 * SLEEVE_T
    z0 = -SLEEVE_DROP
    s = (
        cq.Workplane("XY", origin=(0, 0, z0))
        .rect(w_out, w_out)
        .extrude(SLEEVE_H)
        .edges("|Z")
        .chamfer(4.0)
    )
    s = s.cut(cq.Workplane("XY", origin=(0, 0, z0)).rect(w_in, w_in).extrude(SLEEVE_H))
    # Cable pass-through window at top (cables go down inside the pole)
    # Lock bolts: 2 per face, M10 hex heads
    bolts = None
    for k in range(4):
        for zz in (z0 + 25, z0 + 65):
            b = (
                cq.Workplane("YZ", origin=(w_out / 2, 0, zz))
                .polygon(6, 17.0)
                .extrude(7)
                .faces(">X").edges().chamfer(0.8)
            )
            b = rot_z(b, 90 * k)
            bolts = b if bolts is None else bolts.union(b)
    return s.union(bolts)


def make_spider_plate():
    core = chamfered_box(PLATE_CORE, PLATE_CORE, PLATE_T, 30.0)
    plate = core
    for k in range(4):
        arm = (
            cq.Workplane("XY")
            .center(ARM_REACH / 2, 0)
            .rect(ARM_REACH, ARM_W)
            .extrude(PLATE_T)
            .edges("|Z and >X")
            .chamfer(18.0)
        )
        plate = plate.union(rot_z(arm, 90 * k))
    plate = plate.translate((0, 0, Z_PLATE))
    # Central cable hole down into the pole
    plate = plate.cut(
        cq.Workplane("XY", origin=(0, 0, Z_PLATE)).rect(POLE_W - 2 * POLE_T - 10, POLE_W - 2 * POLE_T - 10)
        .extrude(PLATE_T).edges("|Z").fillet(6)
    )
    # Lightening slots in each arm (tactical, also lighter)
    for k in range(4):
        slot = (
            cq.Workplane("XY", origin=(0, 0, Z_PLATE))
            .center((PLATE_CORE / 2 + CAM_R - 55) / 2 + 5, 0)
            .slot2D(42, 16)
            .extrude(PLATE_T)
        )
        plate = plate.cut(rot_z(slot, 90 * k))
    # Gussets under each arm, welded to sleeve
    w_out = POLE_W + 2 * SLEEVE_GAP + 2 * SLEEVE_T
    for k in range(4):
        for side in (-1, 1):
            g = (
                cq.Workplane("XZ", origin=(0, side * (ARM_W / 2 - 6), 0))
                .polyline([
                    (w_out / 2, Z_PLATE),
                    (CAM_R - 62, Z_PLATE),
                    (w_out / 2, Z_PLATE - 85),
                ]).close()
                .extrude(3, both=True)
            )
            plate = plate.union(rot_z(g, 90 * k))
    # Camera adapter pads (under arm tip)
    for k in range(4):
        pad = (
            cq.Workplane("XY", origin=(CAM_R, 0, Z_PLATE - 6))
            .circle(52).extrude(6)
            .faces("<Z").edges().chamfer(1.5)
        )
        plate = plate.union(rot_z(pad, 90 * k))
    # M8 bolt heads on top of the plate (box fixing + arm fixing)
    heads = None
    pts = [(PLATE_CORE / 2 - 14, PLATE_CORE / 2 - 50), (PLATE_CORE / 2 - 14, -(PLATE_CORE / 2 - 50))]
    pts += [(CAM_R + 24, 18), (CAM_R + 24, -18)]
    for k in range(4):
        for (x, y) in pts:
            h = (
                cq.Workplane("XY", origin=(x, y, Z_PLATE + PLATE_T))
                .polygon(6, 13).extrude(5.3)
                .faces(">Z").edges().chamfer(0.6)
            )
            h = rot_z(h, 90 * k)
            heads = h if heads is None else heads.union(h)
    return plate.union(heads)


def make_box():
    outer = chamfered_box(BOX_W, BOX_W, BOX_H, BOX_CHAMFER)
    inner = (
        chamfered_box(BOX_W - 2 * BOX_WALL, BOX_W - 2 * BOX_WALL, BOX_H - 2 * BOX_WALL, BOX_CHAMFER - 1.2)
        .translate((0, 0, BOX_WALL))
    )
    box = outer.cut(inner)
    # Lid split line (shadow gap) 18 mm below the top
    groove_z = BOX_H - 18
    groove = (
        chamfered_box(BOX_W + 2, BOX_W + 2, 2.0, BOX_CHAMFER)
        .cut(chamfered_box(BOX_W - 2.0, BOX_W - 2.0, 2.0, BOX_CHAMFER - 0.4))
        .translate((0, 0, groove_z))
    )
    box = box.cut(groove)
    # Recessed side panels (1.2 mm deep) on all 4 faces
    for k in range(4):
        panel = (
            cq.Workplane("YZ", origin=(BOX_W / 2 - 1.2, 0, 14))
            .center(0, (groove_z - 10 - 14) / 2)
            .rect(BOX_W - 2 * BOX_CHAMFER - 26, groove_z - 10 - 14)
            .extrude(2)
            .edges("|X").fillet(3)
        )
        box = box.cut(rot_z(panel, 90 * k))
    # Louver grooves on 2 opposite faces. Blind (1.4 mm deep), NOT through:
    # the box stays sealed (IP65 target); heat leaves through the walls and
    # the shaded air gap under the roof.
    for k in (1, 3):
        for i in range(5):
            z = groove_z - 22 - i * 9
            louver = (
                cq.Workplane("YZ", origin=(BOX_W / 2 - 1.2 - 1.4, 0, z))
                .slot2D(BOX_W - 2 * BOX_CHAMFER - 70, 4.0)
                .extrude(3)
            )
            box = box.cut(rot_z(louver, 90 * k))
    # Top lid: slight raised plinth with chamfer
    plinth = (
        chamfered_box(BOX_W - 30, BOX_W - 30, 3, BOX_CHAMFER - 4)
        .faces(">Z").edges().chamfer(2)
        .translate((0, 0, BOX_H))
    )
    box = box.union(plinth)
    # Lid screws (M5) on top corners
    for (x, y) in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
        s = (
            cq.Workplane("XY", origin=(x * (BOX_W / 2 - 24), y * (BOX_W / 2 - 24), BOX_H))
            .circle(5).extrude(2.2).faces(">Z").edges().fillet(1.0)
        )
        box = box.union(s)
    return box.translate((0, 0, Z_BOX))


def make_roof_standoffs():
    pins = None
    for (x, y) in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
        p = (
            cq.Workplane("XY", origin=(x * (BOX_W / 2 - 50), y * (BOX_W / 2 - 50), Z_LID + 3))
            .polygon(6, 18).extrude(ROOF_GAP - 3 + ROOF_SKIRT + 6)
        )
        pins = p if pins is None else pins.union(p)
    return pins


def make_roof():
    # Hip (pyramid) roof with a vertical drip skirt; 3 mm shell.
    def solid(w_base, w_top, h, skirt):
        sk = chamfered_box(w_base, w_base, skirt, BOX_CHAMFER + 8)
        hip = (
            cq.Workplane("XY", origin=(0, 0, skirt))
            .rect(w_base, w_base)
            .workplane(offset=h)
            .rect(w_top, w_top)
            .loft()
        )
        return sk.union(hip)

    outer = solid(ROOF_W, ROOF_TOP_W, ROOF_H, ROOF_SKIRT)
    t = ROOF_T
    inner = solid(ROOF_W - 2 * t, ROOF_TOP_W - 2 * t, ROOF_H - t, ROOF_SKIRT).translate((0, 0, -0.01))
    roof = outer.cut(inner)
    # Low top cap (flat, chamfered) — clean silhouette
    cap = (
        chamfered_box(ROOF_TOP_W + 6, ROOF_TOP_W + 6, 6, 6)
        .faces(">Z").edges().chamfer(2.5)
        .translate((0, 0, ROOF_SKIRT + ROOF_H))
    )
    # Drip rib along the skirt bottom
    rib = (
        chamfered_box(ROOF_W + 4, ROOF_W + 4, 3, BOX_CHAMFER + 9)
        .cut(chamfered_box(ROOF_W - 2 * t, ROOF_W - 2 * t, 3, BOX_CHAMFER + 7))
    )
    roof = roof.union(cap).union(rib)
    return roof.translate((0, 0, Z_ROOF))


def make_glands():
    """PG9 cable glands, one per camera arm, on the box bottom edge."""
    g_all = None
    for k in range(4):
        body = (
            cq.Workplane("YZ", origin=(BOX_W / 2, 32, Z_BOX + 22))
            .polygon(6, 22).extrude(8)
        )
        dome = (
            cq.Workplane("YZ", origin=(BOX_W / 2 + 8, 32, Z_BOX + 22))
            .circle(8.5).extrude(9)
            .faces(">X").edges().fillet(3)
        )
        g = rot_z(body.union(dome), 90 * k)
        g_all = g if g_all is None else g_all.union(g)
    return g_all


def make_status_led():
    return (
        cq.Workplane("YZ", origin=(BOX_W / 2 - 0.5, -(BOX_W / 2 - BOX_CHAMFER - 22), Z_LID - 30))
        .circle(3.0).extrude(1.5)
    )


# ---- Camera (envelope model of DS-2DE2C400MWG-E) -------------------------

def make_camera_parts():
    """Returns (housing, glass) for one camera, mount top at z=0, facing +X."""
    head_h = 112.0
    head_d = 112.0
    head_x = CAM_D - 48.0 - head_d / 2 - 4.0   # head centre x (front bezel adds 4)
    head_zc = -CAM_H + head_h / 2

    base = (
        cq.Workplane("XY").circle(48).extrude(-22)
        .faces("<Z").edges().fillet(6)
    )
    neck = cq.Workplane("XY", origin=(0, 0, -22)).circle(40).extrude(-56)
    yoke = (
        cq.Workplane("XY", origin=(head_x * 0.5, 0, -70))
        .rect(70, 120).extrude(-10)
        .edges("|Z").fillet(20)
    )
    head = (
        cq.Workplane("XY", origin=(head_x, 0, head_zc - head_h / 2))
        .rect(head_d, CAM_W).extrude(head_h)
        .edges("|X").fillet(48)
        .edges("|Y").fillet(22)
    )
    bezel = (
        cq.Workplane("YZ", origin=(head_x + head_d / 2 - 6, 0, head_zc))
        .rect(CAM_W - 30, 66).extrude(10)
        .edges("|X").fillet(30)
    )
    housing = base.union(neck).union(yoke).union(head).union(bezel)
    front_x = head_x + head_d / 2 + 4
    # Recess the front window
    win = (
        cq.Workplane("YZ", origin=(front_x - 2.5, 0, head_zc))
        .rect(CAM_W - 42, 54).extrude(3)
        .edges("|X").fillet(26)
    )
    housing = housing.cut(win)
    # Glass: lens + 2 hybrid-light windows
    glass = (
        cq.Workplane("YZ", origin=(front_x - 2.5, 0, head_zc))
        .rect(CAM_W - 44, 52).extrude(1.0)
        .edges("|X").fillet(25)
    )
    lens = cq.Workplane("YZ", origin=(front_x - 1.5, 0, head_zc)).circle(17).extrude(1.6)
    leds = None
    for y in (-48, 48):
        l = cq.Workplane("YZ", origin=(front_x - 1.5, y, head_zc)).circle(11).extrude(1.2)
        leds = l if leds is None else leds.union(l)
    glass = glass.union(lens).union(leds)
    return housing, glass


# ---- Internals ------------------------------------------------------------

def make_internals():
    floor = Z_BOX + BOX_WALL
    parts = {}
    # Mounting back plate (aluminium)
    bp_w = BOX_W - 2 * BOX_WALL - 16
    parts["backplate"] = (
        chamfered_box(bp_w, bp_w, 2.0, BOX_CHAMFER - 6).translate((0, 0, floor + 4)),
        C_STEEL,
    )
    base = floor + 6
    inner_half = (BOX_W - 2 * BOX_WALL) / 2 - 8
    # PSU: rotated so long side runs along Y, on the -X side
    px = -inner_half + PSU[1] / 2 + 6
    parts["psu_12v_10a"] = (
        cq.Workplane("XY", origin=(px, 0, base)).rect(PSU[1], PSU[0]).extrude(PSU[2])
        .faces(">Z").workplane().rarray(8, 1, 9, 1).rect(4, 60).cutBlind(-1),
        C_PSU,
    )
    # Orange Pi 5 Plus on standoffs, +X side, -Y half
    ox = inner_half - OPI[1] / 2 - 4
    oy = -inner_half + OPI[0] / 2 + 6
    so = 8.0
    pcb = cq.Workplane("XY", origin=(ox, oy, base + so)).rect(OPI[1], OPI[0]).extrude(OPI[2])
    standoffs = (
        cq.Workplane("XY", origin=(ox, oy, base))
        .rect(OPI[1] - 8, OPI[0] - 8, forConstruction=True).vertices()
        .polygon(6, 5.5).extrude(so)
    )
    parts["orangepi5plus_pcb"] = (pcb, C_PCB)
    parts["orangepi5plus_standoffs"] = (standoffs, C_STEEL)
    fins = cq.Workplane("XY", origin=(ox, oy, base + so + OPI[2])).rect(OPI_SINK[0], OPI_SINK[1]).extrude(4)
    fins = fins.union(
        cq.Workplane("XY", origin=(ox, oy, base + so + OPI[2] + 4))
        .rarray(5.5, 1, 11, 1).rect(2.0, OPI_SINK[1]).extrude(OPI_SINK[2] - 4)
    )
    parts["orangepi5plus_heatsink"] = (fins, C_SINK)
    # Switch on a shelf above the PSU
    shelf_z = base + PSU[2] + 12
    sw_cx = -inner_half + SWITCH[1] / 2 + 6 + 10
    shelf = cq.Workplane("XY", origin=(sw_cx, 0, shelf_z - 2)).rect(SWITCH[1] + 14, SWITCH[0] + 10).extrude(2)
    legs = (
        cq.Workplane("XY", origin=(sw_cx, 0, base))
        .rect(SWITCH[1] + 6, SWITCH[0] + 2, forConstruction=True).vertices()
        .rect(6, 6).extrude(shelf_z - 2 - base)
    )
    parts["switch_shelf"] = (shelf.union(legs), C_STEEL)
    parts["network_switch_8p"] = (
        cq.Workplane("XY", origin=(sw_cx, 0, shelf_z)).rect(SWITCH[1], SWITCH[0]).extrude(SWITCH[2])
        .edges("|Z").fillet(4),
        C_SW,
    )
    # Terminal block / fuse strip, +X side, +Y half
    tb = (
        cq.Workplane("XY", origin=(inner_half - 22, inner_half - 50, base))
        .rect(16, 80).extrude(30)
    )
    parts["terminal_block"] = (tb, cq.Color(0.15, 0.30, 0.55))
    return parts


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def build():
    asm = cq.Assembly(name="cctv_pole_head")
    fabricated = {}

    pole = make_pole()
    asm.add(pole, name="pole_80x80", color=C_STEEL)

    sleeve = make_sleeve()
    asm.add(sleeve, name="pole_sleeve", color=C_BODY)
    fabricated["pole_sleeve"] = sleeve

    plate = make_spider_plate()
    asm.add(plate, name="spider_plate", color=C_BODY)
    fabricated["spider_plate"] = plate

    box = make_box()
    asm.add(box, name="controller_box", color=C_BODY)
    fabricated["controller_box"] = box

    asm.add(make_glands(), name="cable_glands", color=C_SW)
    asm.add(make_status_led(), name="status_led", color=C_ACCENT)
    asm.add(make_roof_standoffs(), name="roof_standoffs", color=C_STEEL)

    roof = make_roof()
    asm.add(roof, name="rain_roof", color=C_ROOF)
    fabricated["rain_roof"] = roof

    for name, (shape, col) in make_internals().items():
        asm.add(shape, name=name, color=col)

    housing, glass = make_camera_parts()
    for k in range(4):
        loc = cq.Location((0, 0, 0), (0, 0, 1), 90 * k) * cq.Location((CAM_R, 0, Z_PLATE - 6))
        asm.add(housing, name=f"camera_{k + 1}_housing", color=C_CAM, loc=loc)
        asm.add(glass, name=f"camera_{k + 1}_glass", color=C_GLASS, loc=loc)

    return asm, fabricated


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "out")
    os.makedirs(os.path.join(out, "parts"), exist_ok=True)

    asm, fabricated = build()
    asm.save(os.path.join(out, "cctv_pole_head_assembly.step"))
    for name, wp in fabricated.items():
        cq.exporters.export(wp, os.path.join(out, "parts", f"{name}.step"))

    housing, glass = make_camera_parts()
    cq.exporters.export(housing.union(glass), os.path.join(out, "parts", "camera_envelope_DS-2DE2C400MWG-E.step"))

    bb = asm.toCompound().BoundingBox()
    print(f"Overall: {bb.xlen:.0f} x {bb.ylen:.0f} x {bb.zlen:.0f} mm (incl. {POLE_LEN:.0f} mm pole stub)")
    print(f"Head height above pole top: {Z_ROOF + ROOF_SKIRT + ROOF_H + 6:.0f} mm")
    print(f"Lowest camera point below pole top: {Z_PLATE - 6 - CAM_H:.0f} mm")
    return asm


if __name__ == "__main__":
    main()
