"""
En las fuentes Dotted, cada punto es un contorno de 12 puntos repetido cientos
de miles de veces (en la Lligada Dotted, 365.000). En TTF eso hace archivos
enormes. Este script sustituye cada punto por una referencia (componente) a un
único glifo "_dot", desplazada a su sitio. El dibujo no cambia (como mucho,
medio punto de unidad al redondear la posición).

  python scripts/puntos_componentes.py sources/TracetLligadaDotted-Regular.ufo

Se puede volver a ejecutar.
"""
import collections, sys
import ufoLib2
from fontTools.pens.boundsPen import BoundsPen

TOL = 1.6        # diferencia máxima, en unidades, con el punto modelo
DOT = "_dot"


def bounds(c):
    b = BoundsPen(None)
    c.draw(b)
    return b.bounds


def shape(c):
    """Puntos del contorno relativos a su centro, empezando por el más bajo-izquierdo."""
    x0, y0, x1, y1 = bounds(c)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    pts = [(p.x - cx, p.y - cy, p.type) for p in c.points]
    k = min(range(len(pts)), key=lambda i: (pts[i][2] is None, pts[i][1], pts[i][0]))
    return pts[k:] + pts[:k], (cx, cy)


def model(u):
    """El punto más frecuente de la fuente."""
    cnt = collections.Counter()
    ex = {}
    for g in u:
        for c in g.contours:
            if len(c.points) == 12:
                s, _ = shape(c)
                key = tuple((round(x), round(y), t) for x, y, t in s)
                cnt[key] += 1
                ex.setdefault(key, s)
    key, n = cnt.most_common(1)[0]
    return ex[key], n


def same(s, m):
    return len(s) == len(m) and all(a[2] == b[2] and abs(a[0] - b[0]) <= TOL and abs(a[1] - b[1]) <= TOL
                                    for a, b in zip(s, m))


def main(path):
    u = ufoLib2.Font.open(path)
    m, n = model(u)
    if DOT not in u:
        dot = u.newGlyph(DOT)
    dot = u[DOT]
    dot.clearContours()
    pen = dot.getPen()
    # el modelo, redondeado y centrado en el origen
    on = [i for i, p in enumerate(m) if p[2]]
    pen_pts = [(round(x), round(y)) for x, y, _ in m]
    pen.moveTo(pen_pts[on[0]])
    i = on[0]
    for _ in range(len(on)):
        a, b, c = pen_pts[(i + 1) % 12], pen_pts[(i + 2) % 12], pen_pts[(i + 3) % 12]
        pen.curveTo(a, b, c)
        i = (i + 3) % 12
    pen.closePath()
    dot.width = 0
    replaced = kept = 0
    for g in u:
        if g.name == DOT:
            continue
        keep = []
        offs = []
        for c in g.contours:
            s, (cx, cy) = shape(c) if len(c.points) == 12 else (None, (0, 0))
            if s and same(s, m):
                offs.append((round(cx), round(cy)))
            else:
                keep.append(c)
        if not offs:
            kept += len(keep)
            continue
        g.clearContours()
        for c in keep:
            g.contours.append(c)
        for x, y in offs:
            g.components.append(ufoLib2.objects.Component(DOT, transformation=(1, 0, 0, 1, x, y)))
        replaced += len(offs)
        kept += len(keep)
    order = u.lib.get("public.glyphOrder", [])
    if DOT not in order:
        u.lib["public.glyphOrder"] = order + [DOT]
    u.save(overwrite=True)
    print(f"{path}: {replaced} puntos como componente, {kept} contornos sin cambiar")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
