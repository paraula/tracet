"""
Repaso de calidad de la Tracet Lligada. Se ejecuta el último:

  python scripts/lligada_acentos.py   sources/TracetLligada*.ufo
  python scripts/lligada_eth_thorn.py sources/TracetLligada*.ufo
  python scripts/puntos_componentes.py sources/TracetLligadaDotted-Regular.ufo
  python scripts/lligada_calidad.py   sources/TracetLligada*.ufo

1. Limpia los contornos, igual que calidad.py en la Pal (y quita las
   «espinas» que deja a veces la unión de letra y acento): contornos vacíos o
   degenerados, segmentos casi nulos, puntos que sobran en una recta y rectas
   casi verticales u horizontales.
2. Los signos matemáticos (+ − × ÷ = < > ±) tienen todos la misma anchura.
3. .notdef: una caja simple.
4. Quita los glifos a los que no llega ninguna regla (restos de Fontself:
   b_o.liga, …chainfix…). Se compila la fuente en memoria y se calcula qué
   glifos se pueden alcanzar desde los caracteres con todas las reglas.
   Se quitan también de las reglas (y de las reglas originales que usa
   lligada_acentos.py).
5. Los nombres de más de 31 caracteres se acortan en la fuente compilada
   (public.postscriptNames); en los UFO se quedan los nombres descriptivos.
Se puede volver a ejecutar.
"""
import collections, math, os, re, sys
import pathops
import ufoLib2
import ufo2ft
from fontTools import subset

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calidad import clean_glyph  # noqa: E402
from componer_acentos import CubicPen  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
MATH = ["plus", "minus", "multiply", "divide", "equal", "less", "greater", "plusminus"]
MAX_NAME = 31
TOKEN = re.compile(r"(?<![\w.@\\])([A-Za-z_.][\w.]*)(?![\w.])")


def math_widths(u):
    names = [n for n in MATH if n in u]
    w = collections.Counter(u[n].width for n in names).most_common(1)[0][0]
    n_fixed = 0
    for n in names:
        g = u[n]
        if g.width != w:
            g.move(((w - g.width) / 2, 0))
            g.width = w
            n_fixed += 1
    return n_fixed


def notdef(u):
    g = u[".notdef"]
    hy = u["hyphen"].getBounds(u)
    t = round(hy.yMax - hy.yMin)
    if "Dotted" in u.info.familyName:
        t = 40
    w, h, m = 500, 700, 50
    g.clearContours(); g.clearComponents()
    pen = g.getPen()
    for x0, y0, x1, y1, hole in ((m, 0, w - m, h, False), (m + t, t, w - m - t, h - t, True)):
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]       # exterior: antihorario
        if hole:
            pts.reverse()
        pen.moveTo(pts[0])
        for p in pts[1:]:
            pen.lineTo(p)
        pen.closePath()
    g.width = w


def reachable(u):
    tt = ufo2ft.compileTTF(u, removeOverlaps=False, useProductionNames=False,
                           convertCubics=True, reverseDirection=True)
    opts = subset.Options()
    opts.layout_features = ["*"]
    opts.notdef_outline = True
    opts.glyph_names = True
    s = subset.Subsetter(opts)
    s.populate(unicodes=tt.getBestCmap().keys())
    s._closure_glyphs(tt)
    return set(s.glyphs_retained) | {".notdef"}


def strip_features(text, dead):
    """Quita los glifos muertos de clases y reglas. Una regla que necesita
    un glifo (o una clase) muerto no se puede aplicar nunca: se quita."""
    dead_classes = set()
    for _ in range(5):                         # las clases vacías arrastran a otras
        out, before = [], len(dead_classes)
        for line in text.split("\n"):
            m = re.match(r"(\s*)(@[\w.]+)\s*=\s*\[(.*)\];\s*$", line)
            if m:
                toks = [t for t in m.group(3).split() if t not in dead and t not in dead_classes]
                if not toks:
                    dead_classes.add(m.group(2))
                    continue
                out.append(f"{m.group(1)}{m.group(2)} = [{' '.join(toks)}];")
                continue
            s = line.strip()
            if s.startswith(("sub ", "pos ", "ignore ", "enum ")):
                def brackets(mm):
                    toks = [t for t in mm.group(1).split() if t not in dead and t not in dead_classes]
                    return "[" + " ".join(toks) + "]"
                line2 = re.sub(r"\[([^\]]*)\]", brackets, line)
                plain = re.sub(r"\[[^\]]*\]", " ", line2)
                body = plain.split(" by ")[0] if " by " in plain else plain
                if "[]" in line2 or any(t.strip("';") in dead for t in plain.split()) \
                        or any(t.strip("';") in dead_classes for t in body.split()):
                    continue
                line = line2
            out.append(line)
        text = "\n".join(out)
        if len(dead_classes) == before:
            break
    return text


def prune(u):
    keep = reachable(u)
    dead = {n for n in u.keys() if n not in keep}
    if not dead:
        return 0
    for n in dead:
        del u[n]
    u.features.text = strip_features(u.features.text, dead)
    if "tracet.originalFeatures" in u.lib:
        u.lib["tracet.originalFeatures"] = strip_features(u.lib["tracet.originalFeatures"], dead)
    for key in ("public.openTypeCategories", "public.postscriptNames"):
        if key in u.lib:
            u.lib[key] = {k: v for k, v in u.lib[key].items() if k not in dead}
    u.lib["public.glyphOrder"] = [n for n in u.lib.get("public.glyphOrder", []) if n not in dead]
    u.glyphOrder = u.lib["public.glyphOrder"]
    return len(dead)


def short_names(u):
    long_ = sorted(n for n in u.keys() if len(n) > MAX_NAME)
    names = {n: f"lig{i:04d}" for i, n in enumerate(long_, 1)}
    if names:
        u.lib["public.postscriptNames"] = names
    else:
        u.lib.pop("public.postscriptNames", None)
    return len(names)


def spikes(u):
    """Contornos con una «espina» (A→B→A, ida y vuelta sin superficie), que
    a veces deja la unión de letra y acento: se rehacen con pathops.simplify."""
    def spiky(g):
        for c in g.contours:
            on = [(p.x, p.y) for p in c.points if p.type]
            if any(math.dist(on[i - 2], on[i]) < 1.5 and math.dist(on[i - 1], on[i]) > 20
                   for i in range(len(on))):
                return True
        return False
    fixed = 0
    for g in u:
        if g.contours and spiky(g):
            p = pathops.Path()
            for c in g.contours:
                c.draw(p.getPen())
            q = pathops.simplify(p, fix_winding=True, clockwise=False)
            g.clearContours()
            q.draw(CubicPen(g.getPen()))
            fixed += 1
    return fixed


def main(path):
    u = ufoLib2.Font.open(path)
    fixes = spikes(u) + sum(clean_glyph(g) for g in u)
    m = math_widths(u)
    notdef(u)
    gone = prune(u)
    s = short_names(u)
    u.save(overwrite=True)
    print(f"{os.path.basename(path)}: {fixes} arreglos de contorno, {m} signos matemáticos, "
          f"{gone} glifos inalcanzables quitados, {s} nombres acortados")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
