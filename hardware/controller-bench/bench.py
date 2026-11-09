"""
Controller Bench: open-frame quick-print prototype
==================================================
Parametric solid (B-rep) model built with CadQuery, exported as STEP (no mesh).

Fastest way to get the electronics running: a lightened base plate with a
stiffening rim, cradles for every part, zip-tie anchors, and two fan
brackets. No walls, no lid, so every port is reachable while testing.

  - Orange Pi 5 Ultra on the same slotted tray as the full design
  - TP-Link LS1005, 12 V PSU 128 x 97.5 x 30 (flat), 12->5 V buck, 2x WAGO
  - Fan 1 (60 x 60 x 37.5) over the Orange Pi, blowing down
  - Fan 2 (60 x 60 x 37.5) over the buck converter, blowing down

Same component positions as ../controller-box-proto, so wiring done here
carries over to the closed prototype box.

Units: mm. Plate top Z=0, centred on X=0, Y=0. Front = -Y.
"""

import importlib.util
import os

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PB = _load("proto_box", "../controller-box-proto/proto_box.py")
CB = PB.CB
box, oct_prism, union_all = CB.box, CB.oct_prism, CB.union_all

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

PLATE_T = 2.4
RIM_H, RIM_T = 8.0, 2.0
EDGE_CH = 8.0
OX, OY = PB.OX, PB.OY                 # same outline as the prototype box
INSERT_M3 = PB.INSERT_M3
FAN = PB.FAN
FAN_PITCH = PB.FAN_PITCH

OPI_TRAY = PB.OPI_TRAY
SW_POS, SWITCH = PB.SW_POS, PB.SWITCH
BUCK_POS, BUCK = PB.BUCK_POS, PB.BUCK
PSU_POS, PSU = PB.PSU_POS, PB.PSU
WAGO_POS, WAGO = PB.WAGO_POS, PB.WAGO

SINK_TOP = PB.PCB_Z + PB.OPI[2] + PB.OPI_COOLER_H
FAN1 = dict(c=PB.FAN1_C, z0=SINK_TOP + 2.4, posts=[(-100.0, 17.0), (-60.0, 17.0)])
FAN2 = dict(c=(76.5, -60.0), z0=BUCK[2] + 3.0, posts=[(58.0, -20.0), (95.0, -20.0)])
POST_BOSS_H = 4.0
FRAME_T = 3.0

MOUNT_HOLES = [(115, 80), (-115, 80), (115, -80), (-115, -80)]

C_PLATE = cq.Color(0.16, 0.17, 0.18)
C_BRK = cq.Color(0.30, 0.31, 0.33)


# ---------------------------------------------------------------------------
# Base plate
# ---------------------------------------------------------------------------

def window(x0, x1, y0, y1):
    return box(x0, x1, y0, y1, -PLATE_T - 1, 1).edges("|Z").chamfer(4)


def make_plate():
    p = oct_prism(2 * OX, 2 * OY, EDGE_CH, -PLATE_T, PLATE_T)
    p = p.faces("<Z").edges().chamfer(0.8)
    # Stiffening rim (low, so ports and plugs stay clear)
    rim = oct_prism(2 * OX, 2 * OY, EDGE_CH, 0, RIM_H).cut(
        oct_prism(2 * (OX - RIM_T), 2 * (OY - RIM_T), EDGE_CH - 0.8, -1, RIM_H + 2))
    rim = rim.faces(">Z").edges().chamfer(0.6)
    # Notch the rim in front of the switch ports
    rim = rim.cut(box(SW_POS[0] - 2, SW_POS[0] + SWITCH[0] + 2, -OY - 1, -OY + RIM_T + 1, 1.0, RIM_H + 1))
    p = p.union(rim)

    # Lightening windows (only where nothing needs support)
    px0, py0 = PSU_POS
    for w in [
        window(px0 + 14, px0 + PSU[0] - 14, py0 + 14, py0 + PSU[1] - 14),          # under PSU
        window(SW_POS[0] + 10, SW_POS[0] + SWITCH[0] - 10, SW_POS[1] + 9, SW_POS[1] + SWITCH[1] - 9),
        window(BUCK_POS[0] + 8, BUCK_POS[0] + BUCK[0] - 8, BUCK_POS[1] + 8, BUCK_POS[1] + BUCK[1] - 8),
        window(OPI_TRAY[0] + 12, OPI_TRAY[1] - 12, OPI_TRAY[2] + 12, OPI_TRAY[3] - 12),
        window(-106, -58, 26, 72),                                               # left-back free area
        window(92, 110, 2, 66),                                                  # right of PSU
    ]:
        p = p.cut(w)

    feats = []
    # Orange Pi tray bosses
    tx0, tx1, ty0, ty1 = OPI_TRAY
    for (x, y) in [(tx0 + 5, ty0 + 5), (tx1 - 5, ty0 + 5), (tx0 + 5, ty1 - 5), (tx1 - 5, ty1 - 5)]:
        b = cq.Workplane("XY", origin=(x, y, 0)).circle(4.5).extrude(4)
        feats.append(b.cut(cq.Workplane("XY", origin=(x, y, 4 - INSERT_M3[1])).circle(INSERT_M3[0] / 2)
                           .extrude(INSERT_M3[1])))
    # Corner cradles for switch, buck, PSU (+ zip-tie slot in each)
    for (name, x0, y0, w, d) in [("sw", SW_POS[0], SW_POS[1], SWITCH[0], SWITCH[1]),
                                 ("buck", BUCK_POS[0], BUCK_POS[1], BUCK[0], BUCK[1]),
                                 ("psu", px0, py0, PSU[0], PSU[1])]:
        x1, y1 = x0 + w, y0 + d
        for (cx, cy, dx, dy) in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
            b = box(*sorted((cx, cx - dx * 2)), *sorted((cy, cy + dy * 12)), 0, 7)
            if name == "sw" and dy == 1:      # keep the switch port side clear for plugs
                feats.append(b)
                continue
            a = box(*sorted((cx, cx + dx * 12)), *sorted((cy, cy - dy * 2)), 0, 7)
            feats.append(a.union(b))
    # WAGO pockets
    for (x, y) in WAGO_POS:
        w = box(x - 1.6, x + WAGO[0] + 1.6, y - 1.6, y + WAGO[1] + 1.6, 0, 3)
        feats.append(w.cut(box(x, x + WAGO[0], y, y + WAGO[1], 1.2, 4)))
    # Fan bracket bosses
    for fan in (FAN1, FAN2):
        for (x, y) in fan["posts"]:
            b = cq.Workplane("XY", origin=(x, y, 0)).circle(5.5).extrude(POST_BOSS_H)
            feats.append(b.cut(cq.Workplane("XY", origin=(x, y, POST_BOSS_H - INSERT_M3[1] + 2))
                               .circle(INSERT_M3[0] / 2).extrude(INSERT_M3[1])))
    # Zip-tie anchors along the cable runs
    for (x, y, along_x) in [(40, -24, True), (100, -30, False), (100, 40, False),
                            (-80, 18, True), (-114, -40, False)]:
        a = box(x - 5, x + 5, y - 4, y + 4, 0, 7).edges("|Z").chamfer(1.5)
        a = a.cut(box(x - 6, x + 6, y - 2, y + 2, 2, 4.5) if along_x else box(x - 2, x + 2, y - 6, y + 6, 2, 4.5))
        feats.append(a)
    # Mounting holes (M4) in the corners, with pads
    p = p.union(union_all(feats))
    for (x, y) in MOUNT_HOLES:
        p = p.union(cq.Workplane("XY", origin=(x, y, 0)).circle(5).extrude(2))
        p = p.cut(cq.Workplane("XY", origin=(x, y, -PLATE_T - 1)).circle(2.2).extrude(PLATE_T + 4))
    return p


# ---------------------------------------------------------------------------
# Fan brackets (print upside down: frame on the bed)
# ---------------------------------------------------------------------------

def make_fan_bracket(fan):
    cx, cy = fan["c"]
    z0 = fan["z0"]
    z1 = z0 + FRAME_T
    half = FAN[0] / 2 + 2
    fr = box(cx - half, cx + half, cy - half, cy + half, z0, z1).edges("|Z").chamfer(4)
    fr = fr.cut(cq.Workplane("XY", origin=(cx, cy, z0 - 1)).circle(28.5).extrude(FRAME_T + 2))
    for a in (45, 135):
        bar = box(cx - 29, cx + 29, cy - 1.2, cy + 1.2, z0, z1)
        fr = fr.union(bar.rotate((cx, cy, 0), (cx, cy, 1), a))
    fr = fr.union(cq.Workplane("XY", origin=(cx, cy, z0)).circle(8).extrude(FRAME_T))
    parts = [fr]
    y_arm0 = cy + half - 4
    for (x, y) in fan["posts"]:
        parts.append(box(x - 4, x + 4, y_arm0, y + 4, z0, z1))
        parts.append(box(x - 4, x + 4, cy + FAN[1] / 2 + 0.6, y + 4, z1, z1 + 3))
        parts.append(box(x - 4, x + 4, y - 4, y + 4, POST_BOSS_H + 3, z1 + 3))
        parts.append(box(x - 7, x + 7, y - 6, y + 6, POST_BOSS_H, POST_BOSS_H + 3).edges("|Z").chamfer(2))
        g_h = min(14.0, z0 - POST_BOSS_H - 4)
        if g_h > 3:
            parts.append(cq.Workplane("YZ", origin=(x, 0, 0))
                         .polyline([(y - 4, z0), (y - 4 - g_h, z0), (y - 4, z0 - g_h)]).close()
                         .extrude(2.5, both=True))
    (xa, ya), (xb, _) = fan["posts"]
    parts.append(box(xa, xb, ya - 4, ya + 4, z1, z1 + 3))
    br = union_all(parts)
    for dx in (-FAN_PITCH / 2, FAN_PITCH / 2):
        for dy in (-FAN_PITCH / 2, FAN_PITCH / 2):
            br = br.cut(cq.Workplane("XY", origin=(cx + dx, cy + dy, z0 - 1)).circle(1.7).extrude(FRAME_T + 2))
    for (x, y) in fan["posts"]:
        br = br.cut(cq.Workplane("XY", origin=(x, y, POST_BOSS_H - 1)).circle(1.7).extrude(5))
    return br


# ---------------------------------------------------------------------------
# Components / checks / build
# ---------------------------------------------------------------------------

def make_components():
    c = {k: v for k, v in PB.make_components().items() if not k.startswith("fan_")}
    for name, fan in (("fan_1_over_opi", FAN1), ("fan_2_over_buck", FAN2)):
        fx, fy = fan["c"]
        zb = fan["z0"] + FRAME_T
        f = box(fx - 30, fx + 30, fy - 30, fy + 30, zb, zb + FAN[2]).edges("|Z").chamfer(3)
        f = f.cut(cq.Workplane("XY", origin=(fx, fy, zb - 1)).circle(28).extrude(FAN[2] + 2))
        c[name] = (f.union(cq.Workplane("XY", origin=(fx, fy, zb)).circle(13).extrude(FAN[2])), CB.C_FAN)
    return c


def port_zones():
    z = PB.port_zones()
    z.pop("ac_in_slot")
    z.pop("dc_out_slot")
    return z


def check(printed, comps):
    issues = []
    sol = {k: v[0].val() for k, v in comps.items()}
    names = list(sol)
    for k in names:
        for pn, p in printed.items():
            v = sol[k].intersect(p.val()).Volume()
            if v > 1:
                issues.append(f"{k} x {pn}: {v:.0f}")
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            v = sol[a].intersect(sol[b]).Volume()
            if v > 1:
                issues.append(f"{a} x {b}: {v:.0f}")
    for zn, z in port_zones().items():
        for pn, p in printed.items():
            v = z.val().intersect(p.val()).Volume()
            if v > 1:
                issues.append(f"PORT {zn} blocked by {pn}: {v:.0f}")
        for k in names:
            if k.startswith("orangepi5ultra_ports"):
                continue
            v = z.val().intersect(sol[k]).Volume()
            if v > 1:
                issues.append(f"PORT {zn} blocked by {k}: {v:.0f}")
    return issues


def build():
    printed = {
        "base_plate": make_plate(),
        "opi_tray": PB.make_tray(),
        "fan_bracket_opi": make_fan_bracket(FAN1),
        "fan_bracket_buck": make_fan_bracket(FAN2),
    }
    comps = make_components()
    asm = cq.Assembly(name="controller_bench")
    for n, wp in printed.items():
        asm.add(wp, name=n, color=C_PLATE if n == "base_plate" else C_BRK)
    for k, (s, col) in comps.items():
        asm.add(s, name=k, color=col)
    return asm, printed, comps


def main():
    out = os.path.join(HERE, "out")
    os.makedirs(os.path.join(out, "print"), exist_ok=True)
    asm, printed, comps = build()
    asm.export(os.path.join(out, "controller_bench_assembly.step"))
    for n, wp in printed.items():
        cq.exporters.export(wp, os.path.join(out, "print", f"{n}.step"))
    issues = check(printed, comps)
    print("Check:", "OK" if not issues else "\n  " + "\n  ".join(issues))
    total = 0.0
    for n, wp in printed.items():
        s = wp.val()
        bb = s.BoundingBox()
        total += s.Volume()
        print(f"{n:17s} {bb.xlen:6.1f} x {bb.ylen:6.1f} x {bb.zlen:5.1f} mm   {s.Volume() / 1000:5.1f} cm3")
    print(f"total volume {total / 1000:.1f} cm3")


if __name__ == "__main__":
    main()
