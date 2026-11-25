"""
Tracet Lligada: ð y þ, dibujadas con los trazos de la propia Lligada.

  python scripts/lligada_eth_thorn.py sources/TracetLligada-Regular.ufo [...]

Se ejecuta después de lligada_acentos.py y antes de puntos_componentes.py.
  ð = la d con el asta curvada hacia la izquierda y una barra inclinada.
  þ = la h con el asta prolongada bajo la línea base (la misma bajada de la p).
Cada glifo de unión con d o h (o_d.high1, o_h.type4…) tiene su versión con ð
o þ, y las reglas de unión las tratan igual que a la d y la h.
Se puede volver a ejecutar.
"""
import os, sys, re, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pathops
import lligada_acentos as la

H_STEM = -47           # el asta de la h está 47 u a la izquierda de su ancla
P_STEM = 102           # centro del asta de la p


def cubic_pts(p0, p1, p2, p3, n=40):
    out = []
    for i in range(n + 1):
        t = i / n; m = 1 - t
        out.append((m**3*p0[0]+3*m*m*t*p1[0]+3*m*t*t*p2[0]+t**3*p3[0],
                    m**3*p0[1]+3*m*m*t*p1[1]+3*m*t*t*p2[1]+t**3*p3[1]))
    return out


def curve_stroke(L, segs):
    """segs: lista de (p0,p1,p2,p3) o (p0,p1) -> trazo con extremos redondos."""
    if L.dotted:
        pts = []
        for s in segs:
            pts += cubic_pts(*s) if len(s) == 4 else [s[0], s[1]]
        return L.stroke(pts)
    p = pathops.Path(); pen = p.getPen()
    pen.moveTo(segs[0][0])
    for s in segs:
        pen.curveTo(*s[1:]) if len(s) == 4 else pen.lineTo(s[1])
    pen.endPath()
    p.stroke(L.t, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    p.convertConicsToQuads()
    return p


def remove_box(L, p, x0, y0, x1, y1):
    if L.dotted:     # quitar puntos enteros
        keep = [c for c in la.contours(p)
                if not (x0 <= (c.bounds[0] + c.bounds[2]) / 2 <= x1 and y0 <= (c.bounds[1] + c.bounds[3]) / 2 <= y1)]
        return la.union(keep)
    r = pathops.Path(); pen = r.getPen()
    pen.moveTo((x0, y0)); pen.lineTo((x1, y0)); pen.lineTo((x1, y1)); pen.lineTo((x0, y1)); pen.closePath()
    return pathops.op(p, r, pathops.PathOp.DIFFERENCE)


def eth_path(L, name, sx):
    t = L.t
    top = 712 - t / 2
    cut = 400
    base = remove_box(L, la.path_of(L.u, name), sx - 40, cut, sx + 40, 2000)
    y0 = cut - 30
    if L.dotted:     # empezar en el último punto que queda del asta
        y0 = max((c.bounds[1] + c.bounds[3]) / 2 for c in la.contours(base)
                 if abs((c.bounds[0] + c.bounds[2]) / 2 - sx) < 20)
    asta = curve_stroke(L, [((sx, y0), (sx, 560), (sx - 10, top), (sx - 95, top)),
                            ((sx - 95, top), (sx - 150, top), (sx - 185, top - 30), (sx - 195, top - 70))])
    barra = curve_stroke(L, [((sx - 85, 515), (sx + 75, 575))])
    if not L.dotted:
        return la.union([base, asta, barra])
    kept = []           # en la Dotted, sin puntos montados unos sobre otros
    for c in la.contours(base) + la.contours(asta) + la.contours(barra):
        cx, cy = (c.bounds[0] + c.bounds[2]) / 2, (c.bounds[1] + c.bounds[3]) / 2
        if all(math.dist((cx, cy), k) > la.DOT_GAP * 0.75 for k, _ in kept):
            kept.append(((cx, cy), c))
    return la.union([c for _, c in kept])


def thorn_path(L, name, hx):
    base = la.path_of(L.u, name)
    p = la.path_of(L.u, "p", dx=hx - P_STEM)
    if L.dotted:
        desc = la.union([c for c in la.contours(p) if (c.bounds[1] + c.bounds[3]) / 2 < -30
                         and abs((c.bounds[0] + c.bounds[2]) / 2 - hx) < 40])
    else:
        desc = la.clip(p, hx - 60, -1000, hx + 60, 10)
    return la.union([base, desc])


def stem_x(g, letter, parts):
    if len(parts) == 1:
        return next(a.x for a in g.anchors if a.name == "bottom")
    i = parts.index(letter) + 1
    return next(a.x for a in g.anchors if a.name == f"bottom_{i}")


def build(path):
    L = la.Lligada(path)
    u = L.u
    made, stems = {}, {}
    for letter, new, fn, off, cp in (("d", "eth", eth_path, 0, 0x00F0), ("h", "thorn", thorn_path, H_STEM, 0x00FE)):
        for g in list(u):
            parts = g.name.split(".")[0].split("_")
            if letter not in parts or "chainfix" in g.name:
                continue
            nn = "_".join(new if q == letter else q for q in parts) + g.name[len(g.name.split(".")[0]):]
            x = stem_x(g, letter, parts) + off
            L.put(nn, fn(L, g.name, x), g.width,
                  [(a.name, a.x, a.y) for a in g.anchors], [cp] if nn == new else [])
            made[g.name] = nn
            stems[nn] = (fn, x)
    # la Dotted junta b/v/w + o_d… en un glifo (dotjoin88…) para que no se monten puntos
    for line in u.features.text.split("\n"):
        m = re.match(r"\s*sub (\S+) (\S+) by (\S+);$", line)
        if m and m.group(2) in made and m.group(3) not in made and m.group(3) in u:
            a, b, x = m.groups()
            fn, sx = stems[made[b]]
            nn = x + "." + made[b].split(".")[0].split("_")[-1]
            L.put(nn, fn(L, x, u[a].width + sx), u[x].width,
                  [(an.name, an.x, an.y) for an in u[x].anchors])
            made[x] = nn
    cats = u.lib.setdefault("public.openTypeCategories", {})
    for old, new in made.items():
        if old in cats:
            cats[new] = cats[old]
    # reglas: mismas clases que la d / la h, y las ligaduras o+d, o+h
    out = []
    for line in u.features.text.split("\n"):
        if line.startswith("@") and "[" in line:
            toks = line[line.index("[") + 1:line.rindex("]")].split()
            extra = [made[t] for t in toks if t in made and made[t] not in toks]
            if extra:
                line = line[:line.rindex("]")] + " " + " ".join(extra) + "];"
        out.append(line)
        m = re.match(r"(\s*)sub (\S+) (\S+) by (\S+);$", line)
        if m and m.group(3) in made and m.group(4) in made:
            out.append(f"{m.group(1)}sub {m.group(2)} {made[m.group(3)]} by {made[m.group(4)]};")
    if "o_eth.high1" not in u.features.text:   # solo la primera vez después de lligada_acentos.py
        u.features.text = "\n".join(out)
    order = list(u.lib.get("public.glyphOrder", []))
    order += [n for n in u.keys() if n not in order]
    u.lib["public.glyphOrder"] = order
    u.save(overwrite=True)
    print(path, len(made), "glifos")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        build(p)
