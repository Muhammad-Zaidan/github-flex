"""
Controller Box: quick-print PROTOTYPE (indoor / bench use)
==========================================================
Parametric solid (B-rep) model built with CadQuery, exported as STEP (no mesh).

Simple two-part box (base + lid) for testing the electronics:
  - Orange Pi 5 Ultra on the same slotted tray as the full design
  - TP-Link LS1005, 12 V PSU (128 x 97.5 x 30) lying flat, 12->5 V buck,
    2x WAGO 221-415
  - 2 fans 60 x 60 x 37.5, both hanging from the lid:
      fan 1 directly above the Orange Pi, blowing DOWN (intake)
      fan 2 above the PSU, blowing UP (exhaust)
  - Cable exits: Orange Pi port windows (front + left), switch port window
    (front, plug camera cables straight in), AC IN and DC OUT slots (right).

Not weatherproof: open grilles in the lid. For bench/indoor use.

Print: base floor-down, lid top-down. No supports (window tops are short
bridges, everything else is vertical or flat).

Units: mm. Interior floor top Z=0, interior centred on X=0, Y=0. Front = -Y.
"""

import importlib.util
import os

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "controller_box", os.path.join(HERE, "..", "controller-box", "controller_box.py"))
CB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CB)
box, oct_prism, oct_ring, union_all = CB.box, CB.oct_prism, CB.oct_ring, CB.union_all

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

IN_X, IN_Y, IN_Z = 240.0, 172.0, 80.0   # interior (Z = floor to lid underside)
WALL, FLOOR, LID_T = 2.4, 2.0, 2.4
EDGE_CH = 8.0
LIP_H, LIP_T, LIP_CLR = 4.0, 1.6, 0.3   # lid locating lip
INSERT_M3 = (4.2, 6.0)

FAN = (60.0, 60.0, 37.5)
FAN_PITCH = 50.0

OPI = (89.0, 57.0, 1.6)                  # length (Y), width (X)
OPI_TRAY = (-108.0, -51.0, -80.0, 9.0)   # x0, x1, y0, y1
OPI_COOLER_H = 20.0
PCB_Z = 4 + 3 + 6                        # boss + tray + pillar
SWITCH = (83.6, 45.7, 22.8)              # length (X here), depth (Y), height
SW_POS = (-44.0, -86.0 + 1.0)            # min corner, ports face the front wall
BUCK = (65.0, 40.0, 22.0)
BUCK_POS = (44.0, -84.0)
PSU = (128.0, 97.5, 30.0)                # lying flat: 128 (X) x 97.5 (Y) x 30 (Z)
PSU_POS = (-44.0, -12.0)                 # terminals on the +X end
WAGO = (31.0, 19.0, 8.5)
WAGO_POS = [(-42.0, -33.0), (-6.0, -33.0)]

FAN1_C = ((OPI_TRAY[0] + OPI_TRAY[1]) / 2, (OPI_TRAY[2] + OPI_TRAY[3]) / 2)   # over the Orange Pi
FAN2_C = (20.0, 37.0)                                                         # over the PSU
LID_SCREWS = [(114, 80), (-114, 80), (114, -80), (-114, -80)]

HX, HY = IN_X / 2, IN_Y / 2
OX, OY = HX + WALL, HY + WALL

C_BOX = cq.Color(0.16, 0.17, 0.18)
C_LID = cq.Color(0.13, 0.14, 0.15)
C_ACC = cq.Color(0.85, 0.45, 0.10)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

def window_front(x0, x1, z0, z1):
    return box(x0, x1, -OY - 1, -HY + 1, z0, z1).edges("|Y").chamfer(1.5)


def window_side(sx, y0, y1, z0, z1):
    xa, xb = (HX - 1, OX + 1) if sx > 0 else (-OX - 1, -HX + 1)
    return box(xa, xb, y0, y1, z0, z1).edges("|X").chamfer(1.5)


def make_base():
    body = oct_prism(2 * OX, 2 * OY, EDGE_CH, -FLOOR, FLOOR + IN_Z)
    body = body.faces("<Z").edges().chamfer(1.0)
    body = body.cut(oct_prism(2 * HX, 2 * HY, EDGE_CH - 1.0, 0, IN_Z + 1))

    feats = []
    # Lid screw columns in the corners (M3 inserts)
    for (x, y) in LID_SCREWS:
        col = cq.Workplane("XY", origin=(x, y, 0)).circle(4.5).extrude(IN_Z - LIP_H - 0.5)
        col = col.cut(cq.Workplane("XY", origin=(x, y, IN_Z - LIP_H - 0.5 - INSERT_M3[1]))
                      .circle(INSERT_M3[0] / 2).extrude(INSERT_M3[1] + 1))
        feats.append(col)
    # Orange Pi tray bosses
    tx0, tx1, ty0, ty1 = OPI_TRAY
    for (x, y) in [(tx0 + 5, ty0 + 5), (tx1 - 5, ty0 + 5), (tx0 + 5, ty1 - 5), (tx1 - 5, ty1 - 5)]:
        b = cq.Workplane("XY", origin=(x, y, 0)).circle(4.5).extrude(4)
        feats.append(b.cut(cq.Workplane("XY", origin=(x, y, 4 - INSERT_M3[1])).circle(INSERT_M3[0] / 2)
                           .extrude(INSERT_M3[1])))
    # Switch, buck, PSU: low corner cradles (zip-tie or double-sided tape)
    for (x0, y0, w, d) in [(SW_POS[0], SW_POS[1], SWITCH[0], SWITCH[1]),
                           (BUCK_POS[0], BUCK_POS[1], BUCK[0], BUCK[1]),
                           (PSU_POS[0], PSU_POS[1], PSU[0], PSU[1])]:
        x1, y1 = x0 + w, y0 + d
        for (cx, cy, dx, dy) in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
            a = box(*sorted((cx, cx + dx * 10)), *sorted((cy, cy - dy * 1.6)), 0, 6)
            b = box(*sorted((cx, cx - dx * 1.6)), *sorted((cy, cy + dy * 10)), 0, 6)
            feats.append(a.union(b))
    # WAGO pockets
    for (x, y) in WAGO_POS:
        w = box(x - 1.6, x + WAGO[0] + 1.6, y - 1.6, y + WAGO[1] + 1.6, 0, 3)
        feats.append(w.cut(box(x, x + WAGO[0], y, y + WAGO[1], 1.2, 4)))
    # Zip-tie bridges next to the right-wall cable slots (strain relief)
    for y in (25.0, 55.0):
        a = box(HX - 14, HX - 6, y - 4, y + 4, 0, 7)
        feats.append(a.cut(box(HX - 15, HX - 5, y - 2, y + 2, 2, 4.5)))
    body = body.union(union_all(feats))

    # --- Cable exits ---
    zt = PCB_Z + OPI[2]
    # Orange Pi short edge (USB/LAN) -> front wall
    body = body.cut(window_front(tx0 + 3, tx1 - 3, zt - 2, zt + 18))
    # Orange Pi long edge (USB-C/HDMI/audio) -> left wall
    body = body.cut(window_side(-1, ty0 + 24, ty1 - 4, zt - 2, zt + 10))
    # Switch ports (5x RJ45 + DC) -> front wall
    body = body.cut(window_front(SW_POS[0] + 1, SW_POS[0] + SWITCH[0] - 1, 1.5, SWITCH[2] + 2))
    # AC IN and DC OUT slots -> right wall
    for (y, w) in ((55.0, 16.0), (25.0, 22.0)):
        body = body.cut(window_side(1, y - w / 2, y + w / 2, 4, 18))

    # Styling: two thin grooves along the front, label recesses over the windows
    for z in (IN_Z - 14, IN_Z - 18):
        body = body.cut(box(-HX + 20, HX - 20, -OY - 0.1, -OY + 0.6, z, z + 1.2))
    return body


# ---------------------------------------------------------------------------
# Lid (fans hang from it)
# ---------------------------------------------------------------------------

def grille(cx, cy, z0, h):
    cuts = []
    r, pitch = 28.0, 5.5
    x = -r + pitch / 2
    while x < r:
        half = (r * r - x * x) ** 0.5 - 1.2
        if half > 3:
            cuts.append(box(cx + x - 1.5, cx + x + 1.5, cy - half, cy + half, z0, z0 + h))
        x += pitch
    return union_all(cuts)


def make_lid():
    z0 = IN_Z
    lid = oct_prism(2 * OX, 2 * OY, EDGE_CH, z0, LID_T).faces(">Z").edges().chamfer(1.2)
    # locating lip
    lid = lid.union(oct_ring(2 * (HX - LIP_CLR - LIP_T / 2), 2 * (HY - LIP_CLR - LIP_T / 2),
                             EDGE_CH - 1.0 - LIP_CLR, LIP_T, z0 - LIP_H, LIP_H))
    # notch the lip around the corner screw columns
    for (x, y) in LID_SCREWS:
        lid = lid.cut(cq.Workplane("XY", origin=(x, y, z0 - LIP_H - 1)).circle(5.2).extrude(LIP_H + 1))
        lid = lid.cut(cq.Workplane("XY", origin=(x, y, z0 - 1)).circle(1.7).extrude(LID_T + 2))
        lid = lid.cut(cq.Workplane("XY", origin=(x, y, z0 + LID_T - 1.6)).circle(3.1).extrude(2))
    # fan grilles + fan bosses (M3 inserts) on the underside
    for (cx, cy) in (FAN1_C, FAN2_C):
        lid = lid.cut(grille(cx, cy, z0 - 1, LID_T + 2))
        ring = (cq.Workplane("XY", origin=(cx, cy, z0 + LID_T - 0.6)).circle(32).circle(31).extrude(0.6))
        lid = lid.cut(ring)
        for dx in (-FAN_PITCH / 2, FAN_PITCH / 2):
            for dy in (-FAN_PITCH / 2, FAN_PITCH / 2):
                b = cq.Workplane("XY", origin=(cx + dx, cy + dy, z0 - 3)).circle(4.0).extrude(3)
                b = b.cut(cq.Workplane("XY", origin=(cx + dx, cy + dy, z0 - 3.5)).circle(1.45).extrude(3.5 + LID_T - 0.8))
                lid = lid.union(b)
    # top styling line
    lid = lid.cut(oct_ring(2 * (OX - 8), 2 * (OY - 8), EDGE_CH, 0.8, z0 + LID_T - 0.5, 1))
    return lid


def make_tray():
    """Same slotted tray as the full design (long axis along Y)."""
    tx0, tx1, ty0, ty1 = OPI_TRAY
    cx, cy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
    t = 3.0
    tray = box(tx0, tx1, ty0, ty1, 4, 4 + t).edges("|Z").chamfer(3)
    for (x, y) in [(tx0 + 5, ty0 + 5), (tx1 - 5, ty0 + 5), (tx0 + 5, ty1 - 5), (tx1 - 5, ty1 - 5)]:
        tray = tray.cut(cq.Workplane("XY", origin=(x, y, 3)).circle(1.7).extrude(t + 2))
        tray = tray.cut(cq.Workplane("XY", origin=(x, y, 4 + t - 1.8)).circle(3.2).extrude(2))
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = cx + sx * 24.75, cy + sy * 35.0
            p = cq.Workplane("XY", origin=(px, py, 4 + t)).rect(8, 18).extrude(6).edges("|Z").chamfer(1.5)
            p = p.cut(cq.Workplane("XY", origin=(px, py, 4 + t - 1)).slot2D(14.5, 2.8, 90).extrude(8))
            tray = tray.union(p)
    return tray.cut(cq.Workplane("XY", origin=(cx, cy, 3)).rect(26, 40).extrude(t + 2).edges("|Z").fillet(4))


# ---------------------------------------------------------------------------
# Components + port zones (preview / checks only)
# ---------------------------------------------------------------------------

def make_components():
    c = {}
    tx0, tx1, ty0, ty1 = OPI_TRAY
    cx, cy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
    x0, x1, y0, y1 = cx - OPI[1] / 2, cx + OPI[1] / 2, cy - OPI[0] / 2, cy + OPI[0] / 2
    zt = PCB_Z + OPI[2]
    c["orangepi5ultra_pcb"] = (box(x0, x1, y0, y1, PCB_Z, zt), CB.C_PCB)
    sink = box(cx - 15, cx + 22, cy - 18, cy + 26, zt, zt + 4)
    sink = sink.union(cq.Workplane("XY", origin=(cx + 2, cy + 4, zt + 4)).rarray(5, 1, 8, 1).rect(1.8, 44)
                      .extrude(OPI_COOLER_H - 4))
    c["orangepi5ultra_heatsink"] = (sink, CB.C_SINK)
    c["orangepi5ultra_ports_front"] = (box(x0 + 3, x1 - 3, y0 - 2, y0 + 18, zt, zt + 15), CB.C_PORT)
    c["orangepi5ultra_ports_side"] = (box(x0 - 1, x0 + 11, y0 + 26, y1 - 6, zt, zt + 7), CB.C_PORT)
    sx0, sy0 = SW_POS
    c["switch_tplink_ls1005"] = (box(sx0, sx0 + SWITCH[0], sy0, sy0 + SWITCH[1], 0, SWITCH[2])
                                 .edges("|Z").fillet(3), CB.C_SW)
    bx0, by0 = BUCK_POS
    buck = box(bx0, bx0 + BUCK[0], by0, by0 + BUCK[1], 0, 1.6)
    c["buck_12v_to_5v"] = (buck.union(box(bx0 + 8, bx0 + 30, by0 + 8, by0 + 32, 1.6, BUCK[2])), CB.C_BUCK)
    px0, py0 = PSU_POS
    c["psu_12v"] = (box(px0, px0 + PSU[0], py0, py0 + PSU[1], 0, PSU[2]), CB.C_PSU)
    for i, (x, y) in enumerate(WAGO_POS):
        c[f"wago_221_{i + 1}"] = (box(x, x + WAGO[0], y, y + WAGO[1], 1.2, 1.2 + WAGO[2]), CB.C_WAGO)
    for name, (fx, fy) in (("fan_1_over_opi", FAN1_C), ("fan_2_exhaust", FAN2_C)):
        zb = IN_Z - 3 - FAN[2]
        f = box(fx - 30, fx + 30, fy - 30, fy + 30, zb, zb + FAN[2]).edges("|Z").chamfer(3)
        f = f.cut(cq.Workplane("XY", origin=(fx, fy, zb - 1)).circle(28).extrude(FAN[2] + 2))
        c[name] = (f.union(cq.Workplane("XY", origin=(fx, fy, zb)).circle(13).extrude(FAN[2])), CB.C_FAN)
    return c


def port_zones():
    """Plug paths from each connector OUT through the wall (must be free)."""
    tx0, tx1, ty0, ty1 = OPI_TRAY
    cx, cy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
    x0, x1, y0, y1 = cx - OPI[1] / 2, cx + OPI[1] / 2, cy - OPI[0] / 2, cy + OPI[0] / 2
    zt = PCB_Z + OPI[2]
    sx0, sy0 = SW_POS
    px1 = PSU_POS[0] + PSU[0]
    return {
        "opi_front_ports": box(x0 + 5, x1 - 5, -OY - 20, y0 - 2.5, zt + 1, zt + 15),
        "opi_side_ports": box(-OX - 20, x0 - 1.5, y0 + 27, y1 - 7, zt + 1, zt + 7),
        "switch_ports": box(sx0 + 3, sx0 + SWITCH[0] - 3, -OY - 20, sy0 - 0.5, 3, SWITCH[2]),
        "psu_terminals": box(px1 + 2, px1 + 22, PSU_POS[1] + 5, PSU_POS[1] + PSU[1] - 5, 7, PSU[2]),
        "ac_in_slot": box(HX - 20, OX + 20, 49, 61, 8, 16),
        "dc_out_slot": box(HX - 20, OX + 20, 16, 34, 8, 16),
    }


def check(base, lid, tray, comps):
    issues = []
    sol = {k: v[0].val() for k, v in comps.items()}
    names = list(sol)
    for k in names:
        for pn, p in (("base", base), ("lid", lid), ("tray", tray)):
            v = sol[k].intersect(p.val()).Volume()
            if v > 1:
                issues.append(f"{k} x {pn}: {v:.0f}")
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            v = sol[a].intersect(sol[b]).Volume()
            if v > 1:
                issues.append(f"{a} x {b}: {v:.0f}")
    for zn, z in port_zones().items():
        for pn, p in (("base", base), ("lid", lid), ("tray", tray)):
            v = z.val().intersect(p.val()).Volume()
            if v > 1:
                issues.append(f"PORT/CABLE PATH {zn} blocked by {pn}: {v:.0f}")
        for k in names:
            if k.startswith("orangepi5ultra_ports"):
                continue
            v = z.val().intersect(sol[k]).Volume()
            if v > 1:
                issues.append(f"PORT/CABLE PATH {zn} blocked by {k}: {v:.0f}")
    return issues


def build():
    base, lid, tray = make_base(), make_lid(), make_tray()
    comps = make_components()
    asm = cq.Assembly(name="controller_box_prototype")
    asm.add(base, name="base", color=C_BOX)
    asm.add(lid, name="lid", color=C_LID)
    asm.add(tray, name="opi_tray", color=CB.C_TRAY)
    for k, (s, col) in comps.items():
        asm.add(s, name=k, color=col)
    return asm, {"base": base, "lid": lid, "opi_tray": tray}, comps


def main():
    out = os.path.join(HERE, "out")
    os.makedirs(os.path.join(out, "print"), exist_ok=True)
    asm, printed, comps = build()
    asm.export(os.path.join(out, "proto_box_assembly.step"))
    for n, wp in printed.items():
        cq.exporters.export(wp, os.path.join(out, "print", f"{n}.step"))
    issues = check(printed["base"], printed["lid"], printed["opi_tray"], comps)
    print("Check:", "OK" if not issues else "\n  " + "\n  ".join(issues))
    for n, wp in printed.items():
        s = wp.val()
        bb = s.BoundingBox()
        print(f"{n:9s} {bb.xlen:6.1f} x {bb.ylen:6.1f} x {bb.zlen:5.1f} mm   volume {s.Volume() / 1000:6.1f} cm3")


if __name__ == "__main__":
    main()
