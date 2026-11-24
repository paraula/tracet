"""
Importa a los UFO de sources/ los caracteres dibujados en Illustrator
(sources/dibujos/trazos_pal_v2.svg) y monta con ellos las letras que
faltaban del juego GF Latin Core.

  python scripts/componer_acentos.py   (antes)
  python scripts/trazos_svg.py

El SVG tiene los trazos (línea central) de la Regular. Para cada estilo:
  - el trazo se escala con la H (mayúsculas) o la l (minúsculas) de ese estilo,
  - se le da el grosor del estilo (en la Dotted se convierte en puntos),
  - los acentos se colocan respecto a la letra base del propio dibujo.

Las minúsculas que no están dibujadas (ă ą ģ ő ș…) usan el acento de la
mayúscula, colocado como los acentos que ya tiene la fuente.
Solo crea o reescribe los glifos de este script.
"""
import glob, math, os, re, sys
import xml.etree.ElementTree as ET
import ufoLib2
import pathops
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from componer_acentos import Composer, cbounds, center, gname  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_FILE = os.path.join(ROOT, "sources", "dibujos", "trazos_pal_v2.svg")
NS = "{http://www.w3.org/2000/svg}"
DOT_GAP = 60.0          # separación entre puntos de la Dotted
DOT_T = 35.0            # diámetro del punto de la Dotted
LSB = 50

# Letras = base de la fuente + acento dibujado.  id de la base en el SVG,
# glifo base, cómo se alinea en vertical (con la parte de arriba o de abajo).
ACCENTED = {
    0x0104: ("A", "A", "bottom"), 0x0118: ("E", "E", "bottom"),
    0x012E: ("I", "I", "bottom"), 0x0172: ("U", "U", "bottom"),       # ogonek
    0x0102: ("A1", "A", "top"), 0x011E: ("G", "G", "top"),            # breve
    0x0150: ("O", "O", "top"), 0x0170: ("U1", "U", "top"),            # doble agudo
    0x0122: ("G1", "G", "bottom"), 0x0136: ("K", "K", "bottom"),      # coma inferior
    0x013B: ("L", "L", "bottom"), 0x0145: ("N", "N", "bottom"),
    0x0218: ("S", "S", "bottom"), 0x021A: ("T", "T", "bottom"),
    0x010F: ("d", "d", "top"), 0x013E: ("l", "l", "top"),             # caron vertical
    0x0165: ("t", "t", "top"),
    0x0126: ("H", "H", "bottom"), 0x0141: ("L2", "L", "bottom"),      # barras
    0x0110: ("D3", "D", "bottom"), 0x0111: ("d2", "d", "bottom"),
    0x0127: ("h", "h", "bottom"),
}
# Acentos guardados para montar el resto: nombre -> letra de la que salen
ACC_FROM = {"breve": 0x0102, "hungarumlaut": 0x0150, "commabelow": 0x0218,
            "ogonek_A": 0x0104, "ogonek_E": 0x0118, "ogonek_I": 0x012E,
            "caronvert": 0x013E}

# Letras dibujadas enteras: id de un elemento del dibujo, minúscula/mayúscula
WHOLE = {0x00C6: ("A2", "upper"), 0x0152: ("E2", "upper"), 0x00DE: ("P", "upper"),
         0x1E9E: ("D1", "upper"), 0x00F0: ("d1", "lower"), 0x00FE: ("p", "lower"),
         0x0142: ("t1", "lower")}

# Kerning de las letras nuevas: (lado izquierdo como, lado derecho como)
KERN_SRC = {"AE": ("A", "E"), "OE": ("O", "E"), "Thorn": ("P", "P"),
            "uni1E9E": ("H", "S"), "eth": ("o", "o"), "thorn": ("p", "p"),
            "lslash": ("l", "t"), "Eth": ("D", "D")}

# Minúsculas montadas con los acentos de las mayúsculas
LOWER_ABOVE = {0x0103: ("a", "breve"), 0x011F: ("g", "breve"),
               0x0151: ("o", "hungarumlaut"), 0x0171: ("u", "hungarumlaut")}
LOWER_OGONEK = {0x0105: ("a", "ogonek_A"), 0x0119: ("e", "ogonek_E"),
                0x012F: ("i", "ogonek_I"), 0x0173: ("u", "ogonek_A")}
LOWER_COMMA = {0x0219: "s", 0x021B: "t", 0x0137: "k", 0x013C: "l", 0x0146: "n"}


# ------------------------------------------------------------------ SVG
def circle_line(cx, cy, rx, ry):
    k = 0.5523
    return [("M", (cx + rx, cy)),
            ("C", (cx + rx, cy + k * ry), (cx + k * rx, cy + ry), (cx, cy + ry)),
            ("C", (cx - k * rx, cy + ry), (cx - rx, cy + k * ry), (cx - rx, cy)),
            ("C", (cx - rx, cy - k * ry), (cx - k * rx, cy - ry), (cx, cy - ry)),
            ("C", (cx + k * rx, cy - ry), (cx + rx, cy - k * ry), (cx + rx, cy)),
            ("Z",)]


def element_subs(el):
    """Líneas centrales de un elemento del SVG (coordenadas del SVG)."""
    tag = el.tag.replace(NS, "")
    subs = []
    if tag == "path":
        r = RecordingPen()
        parse_path(el.get("d"), r)
        cur = None
        for op, a in r.value:
            if op == "moveTo":
                cur = [("M", a[0])]
                subs.append(cur)
            elif op == "lineTo":
                cur.append(("L", a[0]))
            elif op == "curveTo":
                cur.append(("C",) + tuple(a))
            elif op == "qCurveTo":
                p0, q, p = cur[-1][-1], a[0], a[-1]
                cur.append(("C", (p0[0] + 2 / 3 * (q[0] - p0[0]), p0[1] + 2 / 3 * (q[1] - p0[1])),
                            (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1])), p))
            elif op == "closePath":
                cur.append(("Z",))
    elif tag == "line":
        subs.append([("M", (float(el.get("x1")), float(el.get("y1")))),
                     ("L", (float(el.get("x2")), float(el.get("y2"))))])
    elif tag == "polyline":
        n = [float(v) for v in re.findall(r"[-\d.]+", el.get("points"))]
        pts = list(zip(n[0::2], n[1::2]))
        subs.append([("M", pts[0])] + [("L", p) for p in pts[1:]])
    elif tag in ("circle", "ellipse"):
        rx = float(el.get("r") or el.get("rx"))
        ry = float(el.get("r") or el.get("ry"))
        subs.append(circle_line(float(el.get("cx")), float(el.get("cy")), rx, ry))
    for ch in el:
        subs += element_subs(ch)
    return subs


def flatten(sub, steps=24):
    pts, cur = [], None
    for s in sub:
        if s[0] in ("M", "L"):
            cur = s[1]
            pts.append(cur)
        elif s[0] == "C":
            (x0, y0), (x1, y1), (x2, y2), (x3, y3) = cur, s[1], s[2], s[3]
            for i in range(1, steps + 1):
                t = i / steps
                m = 1 - t
                pts.append((m**3*x0 + 3*m*m*t*x1 + 3*m*t*t*x2 + t**3*x3,
                            m**3*y0 + 3*m*m*t*y1 + 3*m*t*t*y2 + t**3*y3))
            cur = s[3]
    return pts


def subs_bounds(subs):
    pts = [p for sub in subs for p in flatten(sub)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def map_subs(subs, f):
    return [[(s[0],) + tuple(f(*p) for p in s[1:]) for s in sub] for sub in subs]


class Drawing:
    def __init__(self, path):
        root = ET.parse(path).getroot()
        self.byid = {}
        self.parent = {}
        for p in root.iter():
            for c in p:
                self.parent[c] = p
            if p.get("id"):
                self.byid[p.get("id")] = p
        self.top_groups = {self.byid["Mayuscula"], self.byid["Minuscula"]}

    def base_and_accent(self, base_id):
        """Trazos de la letra base y del resto del grupo (el acento)."""
        el = self.byid[base_id]
        p = self.parent[el]
        while len(list(p)) == 1:
            el, p = p, self.parent[p]
        acc = [s for c in p if c is not el for s in element_subs(c)]
        return element_subs(el), acc

    def whole(self, any_id):
        el = self.byid[any_id]
        while self.parent[el] not in self.top_groups:
            el = self.parent[el]
        return element_subs(el)


# ------------------------------------------------------------------ contornos
class CubicPen(BasePen):
    """Pasa las curvas cuadráticas de pathops a cúbicas (como el resto del UFO)."""
    def __init__(self, other):
        super().__init__(None)
        self.o = other

    def _moveTo(self, p): self.o.moveTo(p)
    def _lineTo(self, p): self.o.lineTo(p)
    def _curveToOne(self, a, b, c): self.o.curveTo(a, b, c)

    def _qCurveToOne(self, q, p):
        p0 = self._getCurrentPoint()
        self.o.curveTo((p0[0] + 2 / 3 * (q[0] - p0[0]), p0[1] + 2 / 3 * (q[1] - p0[1])),
                       (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1])), p)

    def _closePath(self): self.o.closePath()
    def _endPath(self): self.o.endPath()


def union(paths):
    acc = pathops.Path()
    for p in paths:
        acc = pathops.op(acc, p, pathops.PathOp.UNION, clockwise=False)
    return acc


def glyph_path(g):
    p = pathops.Path()
    g.draw(p.getPen())
    return p


def pbounds(p):
    return p.bounds if len(list(p.segments)) else None


def moved(p, dx, dy, sx=1, sy=1):
    q = pathops.Path()
    p.draw(TransformPen(q.getPen(), (sx, 0, 0, sy, dx, dy)))
    return q


def circle(cx, cy, r):
    k = 0.5523 * r
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo((cx + r, cy))
    pen.curveTo((cx + r, cy + k), (cx + k, cy + r), (cx, cy + r))
    pen.curveTo((cx - k, cy + r), (cx - r, cy + k), (cx - r, cy))
    pen.curveTo((cx - r, cy - k), (cx - k, cy - r), (cx, cy - r))
    pen.curveTo((cx + k, cy - r), (cx + r, cy - k), (cx + r, cy))
    pen.closePath()
    return p


# ------------------------------------------------------------------ por fuente
class Tracer:
    def __init__(self, ufo, drawing):
        self.u = ufo
        self.d = drawing
        self.dotted = "Dotted" in ufo.info.familyName
        hy = cbounds(ufo["hyphen"].contours)
        self.t = DOT_T if self.dotted else hy[3] - hy[1]
        self.comp = Composer(ufo)
        self.made = []
        self.acc = {}       # acentos ya colocados (contornos en la fuente)
        # escala de los dibujos enteros: H para mayúsculas, l para minúsculas
        self.ref = {"upper": self.calib("H", "H"), "lower": self.calib("l", "l")}

    # -- calibración SVG -> fuente
    def cl_bounds(self, name):
        """Caja de la línea central de un glifo de la fuente."""
        b = cbounds(self.u[name].contours)
        h = self.t / 2
        return b[0] + h, b[1] + h, b[2] - h, b[3] - h

    def calib(self, svg_id, glyph):
        sb = subs_bounds(element_subs(self.d.byid[svg_id]))
        fb = self.cl_bounds(glyph)
        return (fb[3] - fb[1]) / (sb[3] - sb[1]), sb, fb

    # -- trazo
    def stroke(self, subs, avoid=()):
        if self.dotted:
            return self.dots(subs, avoid)
        out = []
        for sub in subs:
            closed = sub[-1] == ("Z",)
            p = pathops.Path()
            pen = p.getPen()
            for s in sub:
                if s[0] == "M":
                    pen.moveTo(s[1])
                elif s[0] == "L":
                    pen.lineTo(s[1])
                elif s[0] == "C":
                    pen.curveTo(s[1], s[2], s[3])
            pen.closePath() if closed else pen.endPath()
            p.stroke(self.t, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
            p.convertConicsToQuads()
            out.append(p)
        return union(out)

    def dots(self, subs, avoid=()):
        """Línea central -> puntos cada DOT_GAP. No pone puntos encima de
        los que ya hay (avoid) ni duplicados donde se cruzan los trazos."""
        centers = []
        for sub in subs:
            closed = sub[-1] == ("Z",)
            pts = flatten([s for s in sub if s != ("Z",)])
            if closed and pts[0] != pts[-1]:
                pts.append(pts[0])
            seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
            L = sum(seg)
            n = max(1, round(L / DOT_GAP))
            for k in range(n if closed else n + 1):
                d, acc = L * k / n, 0
                for i, s in enumerate(seg):
                    if acc + s >= d or i == len(seg) - 1:
                        u = 0 if s == 0 else (d - acc) / s
                        centers.append((pts[i][0] + u * (pts[i + 1][0] - pts[i][0]),
                                        pts[i][1] + u * (pts[i + 1][1] - pts[i][1])))
                        break
                    acc += s
        keep = []
        for c in centers:
            if all(math.dist(c, o) > DOT_GAP * 0.6 for o in list(avoid) + keep):
                keep.append(c)
        return union([circle(x, y, self.t / 2) for x, y in keep])

    def dot_centers(self, name):
        if not self.dotted:
            return []
        bs = [cbounds([c]) for c in self.u[name].contours]
        return [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in bs]

    # -- escritura
    def write(self, name, cp, path, width, base_lsb=None, base_rsb=None):
        """Escribe el glifo. Si el contorno sale de los márgenes de la base
        (barras de Ħ Ł), lo desplaza y ensancha el glifo."""
        b = pbounds(path)
        dx = 0
        if base_lsb is not None:
            if b[0] < base_lsb:
                dx = base_lsb - b[0]
            width = max(width + dx, b[2] + dx + base_rsb)
        g = self.u.newGlyph(name) if name not in self.u else self.u[name]
        g.clearContours(); g.clearComponents(); g.clearAnchors()
        moved(path, round(dx), 0).draw(CubicPen(g.getPen()))
        g.unicodes = [cp] if cp else []
        g.width = round(width)
        self.made.append(name)
        return g

    def spaced(self, name, cp, path, lsb=LSB, rsb=LSB):
        b = pbounds(path)
        path = moved(path, lsb - b[0], 0)
        return self.write(name, cp, path, b[2] - b[0] + lsb + rsb)

    def kern(self, new, left, right):
        k = self.u.kerning
        for (a, b), v in list(k.items()):
            if a == right:
                k[(new, b)] = v
            if b == left:
                k[(a, new)] = v

    # -- pasos
    def accented(self):
        for cp, (sid, base, align) in ACCENTED.items():
            bsubs, asubs = self.d.base_and_accent(sid)
            sb = subs_bounds(bsubs)
            fb = self.cl_bounds(base)
            k = self.ref["upper" if base.isupper() else "lower"][0]

            def f(x, y):
                fx = center(fb) + (x - (sb[0] + sb[2]) / 2) * k
                fy = fb[1] + (sb[3] - y) * k if align == "bottom" else fb[3] - (y - sb[1]) * k
                return fx, fy
            acc = self.stroke(map_subs(asubs, f), self.dot_centers(base))
            for key, src in ACC_FROM.items():
                if src == cp:
                    self.acc[key] = (acc, base)
            g = self.u[base]
            lsb = cbounds(g.contours)[0]
            rsb = g.width - cbounds(g.contours)[2]
            self.write(gname(cp), cp, union([glyph_path(g), acc]), g.width, lsb, rsb)
            self.kern(gname(cp), base, base)
        # Ð = Đ
        src = self.u["Dcroat"]
        self.write("Eth", 0x00D0, glyph_path(src), src.width)
        self.kern("Eth", "D", "D")

    def whole(self):
        for cp, (sid, case) in WHOLE.items():
            k, sb, fb = self.ref[case]
            f = lambda x, y: (x * k, fb[1] + (sb[3] - y) * k)
            path = self.stroke(map_subs(self.d.whole(sid), f))
            name = gname(cp)
            self.spaced(name, cp, path)
            self.kern(name, *KERN_SRC[name])

    def contours_of(self, path):
        g = ufoLib2.objects.Glyph()
        path.draw(CubicPen(g.getPen()))
        return list(g.contours)

    def lower(self):
        c = self.comp
        # breve y doble agudo: como el circunflejo de â (desplazamiento y separación)
        _, rx, gap = c.ref("acircumflex", "a")
        for cp, (base, key) in LOWER_ABOVE.items():
            c.put(gname(cp), [cp], base, self.contours_of(self.acc[key][0]), rx, gap)
            self.kern(gname(cp), base, base)
        # ogonek: pegado al extremo inferior derecho de la letra
        for cp, (base, key) in LOWER_OGONEK.items():
            acc, ubase = self.acc[key]
            ab = pbounds(acc)
            dx = self.foot_right(base) - self.foot_right(ubase)
            g = self.u[base]
            self.write(gname(cp), cp, union([glyph_path(g), moved(acc, dx, 0)]), g.width)
            self.kern(gname(cp), base, base)
        # coma inferior: centrada bajo la letra (bajo el asta en la t)
        comma, ubase = self.acc["commabelow"]
        cb = pbounds(comma)
        for cp, base in LOWER_COMMA.items():
            g = self.u[base]
            x = self.stem_center(base) if base == "t" else center(cbounds(g.contours))
            acc = moved(comma, x - (cb[0] + cb[2]) / 2, 0)
            self.write(gname(cp), cp, union([glyph_path(g), acc]), g.width)
            self.kern(gname(cp), base, base)
        # ģ: coma girada encima, como el agudo de á
        _, rx, gap = c.ref("aacute", "a")
        turned = moved(comma, 0, 0, -1, -1)
        c.put("uni0123", [0x0123], "g", self.contours_of(turned), rx, gap)
        self.kern("uni0123", "g", "g")
        # Ľ: el apóstrofo de ľ, a la misma distancia del asta
        apos, _ = self.acc["caronvert"]
        ab = pbounds(apos)
        dx = ab[0] - self.stem_right("l")
        dy = ab[3] - cbounds(self.u["l"].contours)[3]
        Lb = cbounds(self.u["L"].contours)
        acc = moved(apos, self.stem_right("L") + dx - ab[0], Lb[3] + dy - ab[3])
        g = self.u["L"]
        self.write("Lcaron", 0x013D, union([glyph_path(g), acc]), g.width)
        self.kern("Lcaron", "L", "L")

    def slice_x(self, name, y0, y1):
        r = pathops.Path()
        p = r.getPen()
        p.moveTo((-2000, y0)); p.lineTo((3000, y0)); p.lineTo((3000, y1)); p.lineTo((-2000, y1)); p.closePath()
        return pbounds(pathops.op(glyph_path(self.u[name]), r, pathops.PathOp.INTERSECTION))

    def foot_right(self, name):
        return self.slice_x(name, -5, self.t * 1.5)[2]

    def stem_right(self, name):
        top = cbounds(self.u[name].contours)[3]
        return self.slice_x(name, top * 0.55, top * 0.65)[2]

    def stem_center(self, name):
        xh = cbounds(self.u["x"].contours)[3]
        b = self.slice_x(name, xh * 0.45, xh * 0.55)
        return (b[0] + b[2]) / 2

    def loose(self):
        """˘ ˛ ˝ sueltos y los combinables U+0306 030B 0326 0328."""
        c = self.comp
        w = self.u["acute"].width
        wo = self.u["o"].width
        xh = cbounds(self.u["x"].contours)[3]
        _, _, gap = c.ref("acircumflex", "a")
        cats = dict(self.u.lib.get("public.openTypeCategories", {}))
        items = [(0x02D8, 0x0306, "breve", "top"), (0x02DD, 0x030B, "hungarumlaut", "top"),
                 (0x02DB, 0x0328, "ogonek_A", "bottom"), (None, 0x0326, "commabelow", "bottom")]
        for spacing, comb, key, where in items:
            acc = self.acc[key][0]
            ab = pbounds(acc)
            dy = (xh + gap - ab[1]) if where == "top" else 0
            if spacing:
                self.write(gname(spacing), spacing,
                           moved(acc, w / 2 - (ab[0] + ab[2]) / 2, dy), w)
            g = self.write(gname(comb), comb, moved(acc, -wo / 2 - (ab[0] + ab[2]) / 2, dy), 0)
            if where == "top":
                g.appendAnchor({"name": "_top", "x": round(-wo / 2), "y": round(xh)})
            else:
                g.appendAnchor({"name": "_bottom", "x": round(-wo / 2), "y": 0})
            cats[g.name] = "mark"
        self.u.lib["public.openTypeCategories"] = cats

    def run(self):
        self.accented()
        self.whole()
        self.lower()
        self.loose()
        # anclas en las letras nuevas sin acento, para los combinables
        cats = self.u.lib["public.openTypeCategories"]
        for n in ["AE", "OE", "Thorn", "Eth", "Dcroat", "Hbar", "Lslash", "uni1E9E",
                  "eth", "thorn", "dcroat", "hbar", "lslash"]:
            g = self.u[n]
            b = cbounds(g.contours)
            g.appendAnchor({"name": "top", "x": round(center(b)), "y": round(b[3])})
            g.appendAnchor({"name": "bottom", "x": round(center(b)), "y": 0})
            cats[n] = "base"
        order = list(self.u.lib.get("public.glyphOrder", []))
        order += [n for n in self.made + self.comp.made if n not in order]
        self.u.lib["public.glyphOrder"] = order
        self.u.glyphOrder = order


def main():
    drawing = Drawing(SVG_FILE)
    for path in sorted(glob.glob(os.path.join(ROOT, "sources", "*.ufo"))):
        u = ufoLib2.Font.open(path)
        t = Tracer(u, drawing)
        t.run()
        u.save(overwrite=True)
        print(f"{os.path.basename(path):32} +{len(set(t.made))} glifos (total {len(u)})")


if __name__ == "__main__":
    main()
