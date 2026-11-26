"""
Orthographic technical drawings from CadQuery solids (hidden-line removed),
plotted with matplotlib at true scale, with dimension helpers.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from OCP.BRepLib import BRepLib
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
import cadquery as cq

# view name -> (normal towards the viewer, projected X axis)
VIEWS = {
    "front": ((0, -1, 0), (1, 0, 0)),   # X right, Z up
    "top": ((0, 0, 1), (1, 0, 0)),      # X right, Y up
    "right": ((1, 0, 0), (0, 1, 0)),    # Y right, Z up
    "back": ((0, 1, 0), (-1, 0, 0)),
    "left": ((-1, 0, 0), (0, -1, 0)),
    "bottom": ((0, 0, -1), (1, 0, 0)),
}

LINE = "#1d1f22"
HIDDEN = "#9aa0a6"
DIM = "#c4501a"


def _shape(obj):
    if isinstance(obj, cq.Workplane):
        vals = obj.vals()
        return vals[0] if len(vals) == 1 else cq.Compound.makeCompound(vals)
    return obj


def project(obj, view, hidden=False, tol=0.15):
    n, vx = VIEWS[view]
    shp = _shape(obj)
    hlr = HLRBRep_Algo()
    hlr.Add(shp.wrapped)
    hlr.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(), gp_Dir(*n), gp_Dir(*vx))))
    hlr.Update()
    hlr.Hide()
    h = HLRBRep_HLRToShape(hlr)

    def collect(comps):
        lines = []
        for c in comps:
            if c.IsNull():
                continue
            BRepLib.BuildCurves3d_s(c, 1e-4)
            for e in cq.Shape(c).Edges():
                cur = e._geomAdaptor()
                pts = GCPnts_QuasiUniformDeflection(cur, tol, cur.FirstParameter(), cur.LastParameter())
                if pts.IsDone() and pts.NbPoints() > 1:
                    lines.append([(pts.Value(i + 1).X(), pts.Value(i + 1).Y()) for i in range(pts.NbPoints())])
        return lines

    vis = collect([h.VCompound(), h.Rg1LineVCompound(), h.OutLineVCompound()])
    hid = collect([h.HCompound(), h.OutLineHCompound()]) if hidden else []
    return vis, hid


def bounds(lines):
    xs = [p[0] for l in lines for p in l]
    ys = [p[1] for l in lines for p in l]
    return min(xs), max(xs), min(ys), max(ys)


def draw(ax, obj, view, hidden=False, lw=0.6, color=LINE, offset=(0, 0)):
    vis, hid = project(obj, view, hidden)
    ox, oy = offset
    for l in hid:
        ax.plot([p[0] + ox for p in l], [p[1] + oy for p in l], color=HIDDEN, lw=lw * 0.6, ls=(0, (3, 2)))
    for l in vis:
        ax.plot([p[0] + ox for p in l], [p[1] + oy for p in l], color=color, lw=lw, solid_capstyle="round")
    b = bounds(vis)
    return (b[0] + ox, b[1] + ox, b[2] + oy, b[3] + oy)


def _arrow(ax, p1, p2):
    ax.annotate("", xy=p2, xytext=p1,
                arrowprops=dict(arrowstyle="<|-|>", lw=0.55, color=DIM, shrinkA=0, shrinkB=0,
                                mutation_scale=6))


def dim_h(ax, x1, x2, y_ref, y, text=None, fs=6.5):
    """Horizontal dimension between x1 and x2, drawn at height y, extension lines from y_ref."""
    for x in (x1, x2):
        ax.plot([x, x], [y_ref, y + (1.5 if y > y_ref else -1.5)], color=DIM, lw=0.35)
    _arrow(ax, (x1, y), (x2, y))
    t = text if text is not None else f"{abs(x2 - x1):.1f}".rstrip("0").rstrip(".")
    ax.text((x1 + x2) / 2, y + (1.2 if y >= y_ref else -1.2), t, ha="center",
            va="bottom" if y >= y_ref else "top", fontsize=fs, color=DIM,
            bbox=dict(fc="white", ec="none", pad=0.4))


def dim_v(ax, y1, y2, x_ref, x, text=None, fs=6.5):
    for y in (y1, y2):
        ax.plot([x_ref, x + (1.5 if x > x_ref else -1.5)], [y, y], color=DIM, lw=0.35)
    _arrow(ax, (x, y1), (x, y2))
    t = text if text is not None else f"{abs(y2 - y1):.1f}".rstrip("0").rstrip(".")
    ax.text(x + (1.0 if x >= x_ref else -1.0), (y1 + y2) / 2, t, ha="left" if x >= x_ref else "right",
            va="center", fontsize=fs, color=DIM, rotation=90,
            bbox=dict(fc="white", ec="none", pad=0.4))


def note(ax, xy, xytext, text, fs=6):
    ax.annotate(text, xy=xy, xytext=xytext, fontsize=fs, color=DIM,
                arrowprops=dict(arrowstyle="-", lw=0.35, color=DIM),
                bbox=dict(fc="white", ec="none", pad=0.3))


def label(ax, x, y, text, fs=7.5, weight="bold"):
    ax.text(x, y, text, fontsize=fs, weight=weight, color=LINE, ha="center", va="top")


def new_sheet(w_mm, h_mm, dpi=220):
    """Figure whose data units are mm on paper-ish proportions (aspect equal)."""
    fig = plt.figure(figsize=(w_mm / 25.4, h_mm / 25.4), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def finish(fig, ax, xlim, ylim, path):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    fig.savefig(path, dpi=fig.dpi, facecolor="white")
    plt.close(fig)
