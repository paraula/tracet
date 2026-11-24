"""
Repaso de calidad de los UFO de sources/. Se ejecuta el último:

  python scripts/componer_acentos.py
  python scripts/trazos_svg.py
  python scripts/calidad.py

1. Limpia los contornos: quita contornos vacíos, segmentos de longitud
   casi cero, puntos que sobran en medio de una recta y endereza las rectas
   casi verticales u horizontales (desviaciones de 1-2 unidades de Fontself).
2. Kerning de ď ľ ť Ľ: el apóstrofo no puede chocar con la letra siguiente.
3. La i, la j y la į pierden el punto cuando llevan un acento combinable
   encima (í = i + ◌́), con la feature ccmp.
Se puede volver a ejecutar.
"""
import glob, math, os, sys
import ufoLib2
import pathops
from fontTools.pens.recordingPen import RecordingPen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from componer_acentos import CubicPen, cbounds  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_SEG = 1.5            # segmentos más cortos se eliminan
SNAP = math.tan(math.radians(2))   # rectas a menos de 2° de la vertical/horizontal
TOP_MARKS = ["gravecomb", "acutecomb", "uni0302", "tildecomb", "uni0304", "uni0306",
             "uni0307", "uni0308", "uni030A", "uni030B", "uni030C"]
APOS = ["dcaron", "lcaron", "tcaron", "Lcaron"]
FEA_MARK = "# --- calidad.py ---"


# ------------------------------------------------------------- contornos
def contour_segments(contour):
    """Contorno -> (inicio, [('L', p) | ('C', c1, c2, p)]), cerrado y explícito."""
    r = RecordingPen()
    contour.draw(r)
    start, segs = None, []
    for op, a in r.value:
        if op == "moveTo":
            start = a[0]
        elif op == "lineTo":
            segs.append(["L", a[0]])
        elif op == "curveTo":
            segs.append(["C", a[0], a[1], a[2]])
        elif op == "qCurveTo":
            raise ValueError("curva cuadrática")
    if not segs:
        return None, []
    if math.dist(segs[-1][-1], start) > 0.01:
        segs.append(["L", start])
    return start, segs


def area(start, segs):
    pts = [start] + [s[-1] for s in segs]
    return 0.5 * sum(pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1] for i in range(len(pts) - 1))


def clean_contour(contour):
    start, segs = contour_segments(contour)
    if not segs:
        return None, 0
    xs = [p[0] for s in segs for p in s[1:]]
    ys = [p[1] for s in segs for p in s[1:]]
    if (max(xs) - min(xs) < 3 and max(ys) - min(ys) < 3) or len(segs) < 2:
        return None, 1
    fixes = 0
    changed = True
    while changed:
        changed = False
        n = len(segs)
        for i in range(n):
            prev = segs[i - 1][-1]
            s = segs[i]
            # segmento casi nulo
            if all(math.dist(prev, p) < MIN_SEG for p in s[1:]) and n > 2:
                nxt = segs[(i + 1) % n]
                if nxt[0] == "C":
                    nxt[1] = (nxt[1][0] + prev[0] - s[-1][0], nxt[1][1] + prev[1] - s[-1][1])
                segs.pop(i)
                fixes += 1
                changed = True
                break
            if s[0] != "L":
                continue
            q = s[1]
            dx, dy = q[0] - prev[0], q[1] - prev[1]
            # recta casi vertical / horizontal -> se endereza
            delta = None
            if abs(dy) > 10 and 0 < abs(dx) <= abs(dy) * SNAP and abs(dx) < 3:
                delta = (-dx, 0)
            elif abs(dx) > 10 and 0 < abs(dy) <= abs(dx) * SNAP and abs(dy) < 3:
                delta = (0, -dy)
            if delta:
                s[1] = (q[0] + delta[0], q[1] + delta[1])
                nxt = segs[(i + 1) % n]
                if nxt[0] == "C":
                    nxt[1] = (nxt[1][0] + delta[0], nxt[1][1] + delta[1])
                fixes += 1
                changed = True
                break
            # punto en medio de una recta
            nxt = segs[(i + 1) % n]
            if nxt[0] == "L" and n > 3:
                r = nxt[1]
                cross = (q[0] - prev[0]) * (r[1] - prev[1]) - (q[1] - prev[1]) * (r[0] - prev[0])
                along = (q[0] - prev[0]) * (r[0] - q[0]) + (q[1] - prev[1]) * (r[1] - q[1])
                if abs(cross) < 0.5 * math.dist(prev, r) and along > 0:
                    segs.pop(i)
                    fixes += 1
                    changed = True
                    break
    if abs(area(segs[-1][-1], segs)) < 15 and len(segs) <= 3:
        return None, fixes + 1
    return (segs[-1][-1], segs), fixes


def clean_glyph(g):
    out, fixes = [], 0
    for c in g.contours:
        res, f = clean_contour(c)
        fixes += f
        if res:
            out.append(res)
    if not fixes:
        return 0
    g.clearContours()
    pen = g.getPen()
    for start, segs in out:
        pen.moveTo(start)
        for s in segs[:-1]:
            pen.lineTo(s[1]) if s[0] == "L" else pen.curveTo(*s[1:])
        last = segs[-1]
        if last[0] == "C":
            pen.curveTo(*last[1:])
        pen.closePath()
    return fixes


# ------------------------------------------------------------- kerning
def glyph_path(g):
    p = pathops.Path()
    g.draw(p.getPen())
    return p


def left_in_band(u, name, y0, y1):
    r = pathops.Path()
    pen = r.getPen()
    pen.moveTo((-3000, y0)); pen.lineTo((5000, y0)); pen.lineTo((5000, y1)); pen.lineTo((-3000, y1)); pen.closePath()
    b = pathops.op(glyph_path(u[name]), r, pathops.PathOp.INTERSECTION).bounds
    return None if b == (0, 0, 0, 0) else b[0]


def apostrophe_kerning(u):
    """Kerning positivo tras ď ľ ť Ľ cuando la letra siguiente sube hasta
    la altura del apóstrofo. Separación mínima = la que hay entre dos l."""
    l = u["l"]
    lb = cbounds(l.contours)
    target = (l.width - lb[2]) + lb[0]
    rights = [g.name for g in u if g.unicodes and g.contours and g.name not in APOS + ["space"]
              and u.lib.get("public.openTypeCategories", {}).get(g.name) != "mark"]
    count = 0
    for name in APOS:
        g = u[name]
        base = "L" if name == "Lcaron" else name[0]
        # el apóstrofo: los contornos que no están en la letra base
        diff = pathops.op(glyph_path(g), glyph_path(u[base]), pathops.PathOp.DIFFERENCE)
        ab = diff.bounds if diff.bounds != (0, 0, 0, 0) else None
        if not ab or ab[1] < cbounds(u[base].contours)[3] * 0.4:
            print(f"   aviso: no encuentro el apóstrofo de {name}")
            continue
        for r in rights:
            x = left_in_band(u, r, ab[1], ab[3])
            if x is None:
                continue
            gap = (g.width - ab[2]) + x
            need = target - gap
            if need > 4:
                u.kerning[(name, r)] = int(round(need / 5) * 5)
                count += 1
    return count


# ------------------------------------------------------------- i/j sin punto
def soft_dotted(u):
    dl = u["dotlessi"]
    top = cbounds(dl.contours)[3]
    src = u["iogonek"]
    g = u.newGlyph("iogonek.dotless") if "iogonek.dotless" not in u else u["iogonek.dotless"]
    g.clearContours(); g.clearAnchors()
    pen = g.getPen()
    for c in src.contours:
        if cbounds([c])[1] <= top + 1:
            c.draw(pen)
    g.width = src.width
    g.unicodes = []
    for a in dl.anchors:
        g.appendAnchor({"name": a.name, "x": a.x, "y": a.y})
    cats = u.lib["public.openTypeCategories"]
    cats["iogonek.dotless"] = "base"
    order = u.lib["public.glyphOrder"]
    if "iogonek.dotless" not in order:
        order.append("iogonek.dotless")
    u.glyphOrder = order
    marks = [m for m in TOP_MARKS if m in u]
    fea = u.features.text.split(FEA_MARK)[0].rstrip() + "\n\n" + FEA_MARK + "\n" + f"""
@TopMarks = [{' '.join(marks)}];

# la i, la j y la į pierden el punto si llevan un acento encima
lookup SoftDotted {{
    sub i' @TopMarks by dotlessi;
    sub j' @TopMarks by uni0237;
    sub iogonek' @TopMarks by iogonek.dotless;
}} SoftDotted;

feature ccmp {{
    lookup SoftDotted;
}} ccmp;
"""
    u.features.text = fea


def main():
    for path in sorted(glob.glob(os.path.join(ROOT, "sources", "TracetPal*.ufo"))):
        u = ufoLib2.Font.open(path)
        fixes = sum(clean_glyph(g) for g in u)
        soft_dotted(u)
        k = apostrophe_kerning(u)
        u.save(overwrite=True)
        print(f"{os.path.basename(path):32} {fixes} arreglos de contorno, {k} pares de kerning ď ľ ť Ľ")


if __name__ == "__main__":
    main()
