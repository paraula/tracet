"""
Tracet Lligada: letras con acentos nuevos que funcionan con las uniones.

  python scripts/lligada_acentos.py sources/TracetLligada-Regular.ufo [...]

La Lligada tiene ~2.150 glifos de unión (o_a.high1, b_o_a.obvwfix…). En lugar
de redibujar cada variante con cada acento:
  1. ccmp: la letra acentuada (č) se descompone en letra base + acento
     combinable (c + ◌̌). Las reglas de unión ven la letra base.
  2. Las reglas de unión ignoran los acentos (lookupflag IgnoreMarks).
  3. Cada glifo de unión lleva anclas sobre cada letra que contiene
     (top_1, top_2… en las ligaduras), calculadas buscando la letra suelta
     dentro del glifo. GPOS coloca el acento en su ancla.
Las mayúsculas nuevas se copian de Tracet Pal (las mayúsculas de la Lligada
son las de la Pal).
"""
import math, os, re, sys
import numpy as np
import ufoLib2
import pathops
from PIL import Image, ImageDraw, ImageFilter
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen, DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.agl import UV2AGL

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCALE = 0.25                      # raster para buscar letras (1 px = 4 unidades)

# letra acentuada -> (base, acento combinable)
LOWER = {0x0101: ("a", "uni0304"), 0x010D: ("c", "uni030C"), 0x0119: ("e", "uni0328"),
         0x0151: ("o", "uni030B"), 0x0219: ("s", "uni0326")}
UPPER_FROM_PAL = {0x010C: "Ccaron", 0x0218: "uni0218", 0x0100: "Amacron", 0x0118: "Eogonek",
                  0x0150: "Ohungarumlaut"}
TOP_MARKS = ["uni0304", "uni030C", "uni030B"]
BOTTOM_MARKS = ["uni0326", "uni0328"]
ACCENTED = {"acute", "grave", "circumflex", "dieresis", "tilde", "cedilla"}


def gname(u):
    return UV2AGL.get(u, f"uni{u:04X}")


def letters_of(name):
    """Letras base que contiene un glifo, por su nombre: 'o_aacute.high1' -> ['o', 'a']."""
    base = name.split(".")[0]
    out = []
    for p in base.split("_"):
        for suf in sorted(ACCENTED, key=len, reverse=True):
            if p.endswith(suf) and len(p) > len(suf):
                p = p[: -len(suf)]
                break
        out.append(p)
    return out


# ------------------------------------------------------------------ dibujo
def path_of(font, name, dx=0, dy=0):
    rec = DecomposingRecordingPen(font)
    font[name].draw(rec)
    p = pathops.Path()
    rec.replay(TransformPen(p.getPen(), (1, 0, 0, 1, dx, dy)))
    return p


def raster(font, name, x0, y0, w, h, blur):
    rec = DecomposingRecordingPen(font)
    font[name].draw(rec)
    img = Image.new("L", (max(1, int(w * SCALE)), max(1, int(h * SCALE))), 0)
    d = ImageDraw.Draw(img)
    from fontTools.pens.basePen import BasePen

    class Poly(BasePen):
        def __init__(s):
            super().__init__(None); s.polys = []; s.cur = []
        def _moveTo(s, p): s.cur = [p]
        def _lineTo(s, p): s.cur.append(p)
        def _curveToOne(s, a, b, c):
            p0 = s.cur[-1]
            for i in range(1, 7):
                t = i / 6; m = 1 - t
                s.cur.append((m**3*p0[0]+3*m*m*t*a[0]+3*m*t*t*b[0]+t**3*c[0],
                              m**3*p0[1]+3*m*m*t*a[1]+3*m*t*t*b[1]+t**3*c[1]))
        def _qCurveToOne(s, a, b):
            p0 = s.cur[-1]
            for i in range(1, 7):
                t = i / 6; m = 1 - t
                s.cur.append((m*m*p0[0]+2*m*t*a[0]+t*t*b[0], m*m*p0[1]+2*m*t*a[1]+t*t*b[1]))
        def _closePath(s): s.polys.append(s.cur); s.cur = []
        def _endPath(s): s.polys.append(s.cur); s.cur = []

    pp = Poly()
    rec.replay(pp)
    polys = [[((x - x0) * SCALE, (y0 + h - y) * SCALE) for x, y in poly] for poly in pp.polys if len(poly) >= 3]
    if len(polys) > 40:            # Dotted: puntos sueltos, sin huecos
        d.rectangle((0, 0) + img.size, fill=0)
        for poly in polys:
            d.polygon(poly, fill=255)
        im = img
    else:                          # par-impar para los huecos (o, a, e…)
        acc = np.zeros((img.size[1], img.size[0]), dtype=bool)
        for poly in polys:
            m = Image.new("1", img.size, 0)
            ImageDraw.Draw(m).polygon(poly, fill=1)
            acc ^= np.array(m, dtype=bool)
        im = Image.fromarray((acc * 255).astype(np.uint8))
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(im, dtype=np.float32) / 255


def bounds(font, name):
    b = BoundsPen(font)
    font[name].draw(b)
    return b.bounds


# ------------------------------------------------------------------ fuente
class Lligada:
    def __init__(self, path):
        self.path = path
        self.u = ufoLib2.Font.open(path)
        self.dotted = "Dotted" in self.u.info.familyName
        self.xh = self.u.info.xHeight
        self.blur = 3 if self.dotted else 1.5
        hy = bounds(self.u, "hyphen")
        self.t = 34 if self.dotted else hy[3] - hy[1]
        self.Y0, self.H = -450, 1450
        self._tpl = {}

    def find(self, gname_, letter, expect_x, min_x=-1e9):
        """Desplazamiento horizontal de la letra suelta dentro del glifo."""
        u = self.u
        gb = bounds(u, gname_)
        lb = bounds(u, letter)
        if gb is None or lb is None:
            return None
        from scipy.signal import fftconvolve
        X0 = min(gb[0], lb[0]) - 400
        W = (gb[2] - X0) + 400
        G = raster(u, gname_, X0, self.Y0, W, self.H, self.blur)
        if letter not in self._tpl:
            self._tpl[letter] = raster(u, letter, lb[0], self.Y0, lb[2] - lb[0], self.H, self.blur)
        T = self._tpl[letter]
        tn = (T * T).sum() or 1
        score = fftconvolve(G, T[::-1, ::-1], mode="valid")[0] / tn
        dx = X0 + np.arange(len(score)) / SCALE - lb[0]
        score = score - 0.0006 * np.abs(dx - expect_x)    # preferir la posición esperada
        score[dx < min_x] = -1e9                            # cada letra, a la derecha de la anterior
        k = int(np.argmax(score))
        return float(dx[k]), float(score[k])

    def anchors(self):
        """Anclas top/bottom (o top_1, top_2…) en todas las letras y variantes."""
        u = self.u
        cats = dict(u.lib.get("public.openTypeCategories", {}))
        stand = {}                     # anclas de cada letra suelta
        for L in "abcdefghijklmnopqrstuvwxyz":
            b = bounds(u, L)
            core = [b[0], b[2]]
            top = b[3]
            stand[L] = ((b[0] + b[2]) / 2, top, (b[0] + b[2]) / 2)
            # el acento agudo de la letra acentuada da la x buena (letras con acento)
            for acc in ("acute", "circumflex"):
                n = L + acc
                if n in u:
                    abs_ = [c for c in u[n].contours if self._cb(c)[1] > self.xh * 1.05]
                    if abs_:
                        x0 = min(self._cb(c)[0] for c in abs_); x1 = max(self._cb(c)[2] for c in abs_)
                        stand[L] = ((x0 + x1) / 2, top, stand[L][2])
                        break
        report = []
        for g in u:
            if g.name.startswith(".") or g.name == "_dot":
                continue
            letters = letters_of(g.name)
            if g.unicodes and len(letters) == 1 and letters[0] not in stand:
                continue
            if not all(L in stand for L in letters):
                continue
            g.clearAnchors()
            exp, min_x = 0, -1e9
            pos = []
            for i, L in enumerate(letters):
                if g.name == L:
                    dx, sc = 0, 1
                else:
                    r = self.find(g.name, L, exp, min_x)
                    if r is None:
                        break
                    dx, sc = r
                pos.append((L, dx, sc))
                exp = dx + u[L].width
                min_x = dx + u[L].width * 0.35
            if len(pos) != len(letters):
                continue
            for i, (L, dx, sc) in enumerate(pos):
                tx, top, bx = stand[L]
                suf = f"_{i + 1}" if len(pos) > 1 else ""
                ax = self.sibling_x(g, i, len(pos)) or (tx + dx)
                g.appendAnchor({"name": "top" + suf, "x": round(ax), "y": round(top)})
                g.appendAnchor({"name": "bottom" + suf, "x": round(bx + dx), "y": 0})
                report.append((g.name, L, round(dx), round(sc, 2)))
            cats[g.name] = "ligature" if len(pos) > 1 else "base"
        u.lib["public.openTypeCategories"] = cats
        return report

    def sibling_x(self, g, i, n):
        """Si existe la misma variante con agudo en la letra i (o_a.x -> o_aacute.x),
        la x exacta de ese agudo."""
        base = g.name.split(".")[0]
        parts = base.split("_")
        p = parts[i]
        if len(p) != 1:
            return None
        sib = "_".join(parts[:i] + [p + "acute"] + parts[i + 1:]) + g.name[len(base):]
        if sib not in self.u or sib == g.name:
            return None
        own = {tuple(round(v) for v in self._cb(c)) for c in g.contours}
        new = [self._cb(c) for c in self.u[sib].contours
               if self._cb(c)[1] > self.xh * 1.05 and tuple(round(v) for v in self._cb(c)) not in own]
        if not new:
            return None
        return (min(b[0] for b in new) + max(b[2] for b in new)) / 2

    @staticmethod
    def _cb(c):
        b = BoundsPen(None)
        c.draw(b)
        return b.bounds


    # -------------------------------------------------------------- acentos
    def contours_above(self, name, lim):
        return [c for c in self.u[name].contours if self._cb(c)[1] > lim]

    def put_glyph(self, name, path, width=0, anchors=(), unicodes=()):
        u = self.u
        g = u.newGlyph(name) if name not in u else u[name]
        g.clearContours(); g.clearComponents(); g.clearAnchors()
        from componer_acentos import CubicPen
        path.draw(CubicPen(g.getPen()))
        g.width = width
        g.unicodes = list(unicodes)
        for a in anchors:
            g.appendAnchor(a)
        return g

    def stroke(self, pts, closed=False):
        p = pathops.Path()
        pen = p.getPen()
        pen.moveTo(pts[0])
        for q in pts[1:]:
            pen.lineTo(q)
        pen.closePath() if closed else pen.endPath()
        p.stroke(self.t, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
        p.convertConicsToQuads()
        return p

    def marks(self):
        """Acentos combinables nuevos, con el estilo de los de la Lligada."""
        u, xh = self.u, self.xh
        lim = xh * 1.05
        a_top = bounds(u, "a")[3]
        circ = union_c(self.contours_above("acircumflex", lim))
        acute = union_c(self.contours_above("aacute", lim))
        cb, ab = circ.bounds, acute.bounds
        bottom = cb[1]                         # altura del acento sobre la a
        ccx = (cb[0] + cb[2]) / 2
        top_anchor = {"name": "_top", "x": 0, "y": round(a_top)}
        made = {}
        # caron: circunflejo invertido
        car = moved(circ, -ccx, 0, 1, -1)
        car = moved(car, 0, bottom - car.bounds[1])
        made["uni030C"] = car
        # macron: trazo horizontal
        w = (cb[2] - cb[0]) * 0.72
        yc = bottom + self.t / 2 + 25
        made["uni0304"] = self.stroke([(-w / 2, yc), (w / 2, yc)])
        # doble agudo: dos agudos más pequeños
        acx = (ab[0] + ab[2]) / 2
        small = moved(moved(acute, -acx, -ab[1]), 0, 0, 0.62, 0.8)
        sw = small.bounds[2] - small.bounds[0]
        made["uni030B"] = union_p([moved(small, -sw * 0.55, bottom), moved(small, sw * 0.55, bottom)])
        for name, path in made.items():
            self.put_glyph(name, path, 0, [top_anchor])
        # coma inferior: la coma de la fuente, debajo de la línea base
        comma = path_of(u, "comma")
        c = comma.bounds
        com = moved(comma, -(c[0] + c[2]) / 2, -60 - c[3])
        self.put_glyph("uni0326", com, 0, [{"name": "_bottom", "x": 0, "y": 0}])
        # ogonek: el de la Pal, a escala de los acentos de la Lligada
        pal = ufoLib2.Font.open(os.path.join(ROOT, "sources", "TracetPal-Regular.ufo"))
        og = path_of(pal, "ogonek")
        o = og.bounds
        og = moved(og, -o[2] + self.t / 2, -o[3] + self.t / 2)      # punta de arriba en (0, 0)
        self.put_glyph("uni0328", og, 0, [{"name": "_ogonek", "x": 0, "y": 0}])
        return a_top

    def ogonek_anchors(self):
        """Ancla del ogonek: al pie derecho de cada vocal (a e i u) del glifo."""
        u = self.u
        for g in u:
            tops = {a.name: a for a in g.anchors if a.name.startswith("bottom")}
            if not tops:
                continue
            letters = letters_of(g.name)
            for name, a in list(tops.items()):
                i = int(name.split("_")[1]) - 1 if "_" in name else 0
                if i >= len(letters) or letters[i] not in "aeiu":
                    continue
                L = letters[i]
                lb = bounds(u, L)
                foot = (lb[2] - (lb[2] - lb[0]) * 0.22) - (lb[0] + lb[2]) / 2
                suf = name[len("bottom"):]
                g.appendAnchor({"name": "ogonek" + suf, "x": round(a.x + foot), "y": 0})

    def precomposed(self, a_top):
        """La letra acentuada (cmap) dibujada con componentes, y su descomposición."""
        u = self.u
        rules = []
        for cp, (base, mark) in LOWER.items():
            name = gname(cp)
            g = u.newGlyph(name) if name not in u else u[name]
            g.clearContours(); g.clearComponents(); g.clearAnchors()
            ba = {a.name: a for a in u[base].anchors}
            ma = {a.name: a for a in u[mark].anchors}
            key = next(k for k in ma if k.startswith("_"))[1:]
            dx, dy = ba[key].x - ma["_" + key].x, ba[key].y - ma["_" + key].y
            g.components.append(ufoLib2.objects.Component(base))
            g.components.append(ufoLib2.objects.Component(mark, transformation=(1, 0, 0, 1, dx, dy)))
            g.width = u[base].width
            g.unicodes = [cp]
            rules.append(f"    sub {name} by {base} {mark};")
        return rules

    def upper_from_pal(self):
        pal = ufoLib2.Font.open(os.path.join(ROOT, "sources", "TracetPal-Regular.ufo"))
        for cp, name in UPPER_FROM_PAL.items():
            src = pal[name]
            g = self.u.newGlyph(name) if name not in self.u else self.u[name]
            g.clearContours(); g.clearComponents(); g.clearAnchors()
            import copy
            for c in src.contours:
                g.contours.append(copy.deepcopy(c))
            g.width = src.width
            g.unicodes = [cp]

    def features(self, rules):
        u = self.u
        fea = u.features.text
        marker = "# --- lligada_acentos.py ---"
        fea = fea.split(marker)[0]
        # las reglas de unión ignoran los acentos combinables
        fea = re.sub(r"(lookup L\d+ \{\n)(?!    lookupflag)", r"\1    lookupflag IgnoreMarks;\n", fea)
        head, rest = fea.split("\n\n", 1) if fea.startswith("languagesystem") else ("", fea)
        dec = "\n".join([marker, "lookup Descompon {"] + rules + ["} Descompon;",
                        "feature ccmp {", "    lookup Descompon;", "} ccmp;", marker + " fin", ""])
        # la descomposición tiene que ir antes que las uniones (orden de lookups)
        lines = fea.split("\n")
        k = next(i for i, l in enumerate(lines) if l.startswith("lookup "))
        lines = lines[:k] + [dec] + lines[k:]
        u.features.text = "\n".join(lines)
        cats = u.lib.setdefault("public.openTypeCategories", {})
        for m in TOP_MARKS + BOTTOM_MARKS:
            cats[m] = "mark"


def union_c(contours):
    p = pathops.Path()
    for c in contours:
        c.draw(p.getPen())
    return pathops.op(p, pathops.Path(), pathops.PathOp.UNION)


def union_p(paths):
    acc = pathops.Path()
    for p in paths:
        acc = pathops.op(acc, p, pathops.PathOp.UNION)
    return acc


def moved(p, dx, dy, sx=1, sy=1):
    q = pathops.Path()
    p.draw(TransformPen(q.getPen(), (sx, 0, 0, sy, dx, dy)))
    return q


def main(path):
    L = Lligada(path)
    rep = L.anchors()
    a_top = L.marks()
    L.ogonek_anchors()
    rules = L.precomposed(a_top)
    L.upper_from_pal()
    L.features(rules)
    order = L.u.lib.get("public.glyphOrder", [])
    for g in L.u:
        if g.name not in order:
            order.append(g.name)
    L.u.lib["public.glyphOrder"] = order
    L.u.save(overwrite=True)
    print(path, len(rep), "anclas")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    for p in sys.argv[1:]:
        main(p)
