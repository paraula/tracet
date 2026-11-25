"""
Tracet Lligada: completa el juego GF Latin Core sin romper las uniones.

  python scripts/lligada_acentos.py sources/TracetLligada-Regular.ufo [...]
  python scripts/puntos_componentes.py sources/TracetLligadaDotted-Regular.ufo

La Lligada tiene ~2.150 glifos de unión (o_a.high1, b_o_a.obvwfix…). En lugar
de redibujar cada variante con cada acento:
  1. ccmp: cada minúscula acentuada nueva (č) se descompone en letra base +
     acento combinable (c + ◌̌). Las reglas de unión ven la letra base.
  2. Las reglas de unión ignoran los acentos (lookupflag IgnoreMarks).
  3. Cada glifo de unión lleva anclas sobre cada letra que contiene
     (top_1, top_2… en las ligaduras). Se calculan buscando la letra suelta
     dentro del glifo; en las vocales se usa la posición exacta del agudo
     de la variante acentuada que ya existe.
  4. La i y la j pierden el punto cuando llevan un acento encima (ı ȷ ī…).
Mayúsculas: las de la Lligada son las de la Pal. Las acentuadas se montan
con la mayúscula de la Lligada y el acento de la Pal; Æ Œ Ð Þ Ø Ł Đ Ħ ẞ se
copian de la Pal. Para que las reglas de unión las traten como su letra base,
se añaden a las mismas clases (Č donde está C, Æ donde está A…).
Se puede volver a ejecutar: parte siempre de las reglas originales.
"""
import copy, math, os, re, sys, unicodedata
import numpy as np
import ufoLib2
import pathops
from PIL import Image, ImageDraw, ImageFilter
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.agl import UV2AGL

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from componer_acentos import CubicPen  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCALE = 0.25                          # raster para buscar letras (1 px = 4 unidades)
DOT_D, DOT_GAP = 34.0, 60.0           # punto y separación de la Dotted
ACCENTED = ["circumflex", "dieresis", "cedilla", "acute", "grave", "tilde"]

# fuente -> (UFO de la Pal, desplazamiento x, y, cambio de anchura de las mayúsculas)
PAL = {"TracetLligada-Regular": ("TracetPal-Regular", 0, 0, 0),
       "TracetLligada-Bold": ("TracetPal-Bold", -10, -10, -21),
       "TracetLligadaDotted-Regular": ("TracetPalDotted-Regular", 0, 0, 0)}

COMBINING = {0x0300: "gravecomb", 0x0301: "acutecomb", 0x0302: "uni0302", 0x0303: "tildecomb",
             0x0304: "uni0304", 0x0306: "uni0306", 0x0307: "uni0307", 0x0308: "uni0308",
             0x030A: "uni030A", 0x030B: "uni030B", 0x030C: "uni030C", 0x0326: "uni0326",
             0x0327: "uni0327", 0x0328: "uni0328"}
EXTRA_MARKS = ["commaturned.mark", "caronvert.mark", "bar.mark", "slash.mark",
               "slashlong.mark", "dotless.mark"]
TOP = ["gravecomb", "acutecomb", "uni0302", "tildecomb", "uni0304", "uni0306", "uni0307",
       "uni0308", "uni030A", "uni030B", "uni030C", "commaturned.mark", "dotless.mark"]
# minúsculas que no salen de la descomposición Unicode
LOWER_SPECIAL = {0x0137: ("k", "uni0326"), 0x013C: ("l", "uni0326"), 0x0146: ("n", "uni0326"),
                 0x0123: ("g", "commaturned.mark"), 0x010F: ("d", "caronvert.mark"),
                 0x013E: ("l", "caronvert.mark"), 0x0165: ("t", "caronvert.mark"),
                 0x0142: ("l", "slash.mark"), 0x0111: ("d", "bar.mark"), 0x0127: ("h", "bar.mark"),
                 0x00F8: ("o", "slashlong.mark"), 0x0131: ("i", "dotless.mark"),
                 0x0237: ("j", "dotless.mark")}
UPPER_COPY = {0x00C6: "A", 0x0152: "O", 0x00D0: "D", 0x0110: "D", 0x00DE: "P", 0x00D8: "O",
              0x1E9E: "B", 0x0126: "H", 0x0141: "L"}    # copiadas de la Pal -> letra base para las uniones
SYMBOLS = ["dollar", "cent", "yen", "copyright", "registered", "trademark", "asciicircum", "asciitilde"]
SPACING = {0x0060: "gravecomb", 0x00B4: "acutecomb", 0x02C6: "uni0302", 0x02C7: "uni030C",
           0x00A8: "uni0308", 0x02DC: "tildecomb", 0x00AF: "uni0304", 0x02D8: "uni0306",
           0x02D9: "uni0307", 0x02DA: "uni030A", 0x02DD: "uni030B", 0x00B8: "uni0327",
           0x02DB: "uni0328"}
MARKER = "# --- lligada_acentos.py ---"


def gname(u):
    return UV2AGL.get(u, f"uni{u:04X}")


def letters_of(name):
    """Letras base de un glifo por su nombre: 'o_aacute.high1' -> ['o', 'a']."""
    out = []
    for p in name.split(".")[0].split("_"):
        for suf in ACCENTED:
            if p.endswith(suf) and len(p) > len(suf):
                p = p[: -len(suf)]
                break
        out.append(p)
    return out


# ------------------------------------------------------------------ geometría
def path_of(font, name, dx=0, dy=0, sx=1, sy=1):
    rec = DecomposingRecordingPen(font)
    font[name].draw(rec)
    p = pathops.Path()
    rec.replay(TransformPen(p.getPen(), (sx, 0, 0, sy, dx, dy)))
    return p


def moved(p, dx, dy, sx=1, sy=1):
    q = pathops.Path()
    p.draw(TransformPen(q.getPen(), (sx, 0, 0, sy, dx, dy)))
    return q


def union(paths):
    acc = pathops.Path()
    for p in paths:
        acc = pathops.op(acc, p, pathops.PathOp.UNION)
    return acc


def clip(p, x0, y0, x1, y1):
    r = pathops.Path()
    pen = r.getPen()
    pen.moveTo((x0, y0)); pen.lineTo((x1, y0)); pen.lineTo((x1, y1)); pen.lineTo((x0, y1)); pen.closePath()
    return pathops.op(p, r, pathops.PathOp.INTERSECTION)


def empty(p):
    return p.bounds == (0, 0, 0, 0)


def contours(p):
    """Contornos sueltos de un path (para trabajar punto a punto)."""
    out, cur = [], None
    for verb, pts in p.segments:
        if verb == "moveTo":
            cur = pathops.Path(); pen = cur.getPen(); pen.moveTo(pts[0])
        elif verb == "lineTo":
            pen.lineTo(pts[0])
        elif verb == "qCurveTo":
            pen.qCurveTo(*pts)
        elif verb == "curveTo":
            pen.curveTo(*pts)
        elif verb in ("closePath", "endPath"):
            pen.closePath(); out.append(cur)
    return out


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


def bounds(font, name):
    b = BoundsPen(font)
    font[name].draw(b)
    return b.bounds


class Poly(BasePen):
    def __init__(s, gs=None):
        super().__init__(gs); s.polys = []; s.cur = []
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


def raster(font, name, x0, y0, w, h, blur):
    rec = DecomposingRecordingPen(font)
    font[name].draw(rec)
    pp = Poly()
    rec.replay(pp)
    size = (max(1, int(w * SCALE)), max(1, int(h * SCALE)))
    polys = [[((x - x0) * SCALE, (y0 + h - y) * SCALE) for x, y in poly] for poly in pp.polys if len(poly) >= 3]
    if len(polys) > 40:                       # Dotted: puntos sueltos, sin huecos
        img = Image.new("L", size, 0)
        d = ImageDraw.Draw(img)
        for poly in polys:
            d.polygon(poly, fill=255)
    else:                                     # par-impar, para los huecos
        acc = np.zeros((size[1], size[0]), dtype=bool)
        for poly in polys:
            m = Image.new("1", size, 0)
            ImageDraw.Draw(m).polygon(poly, fill=1)
            acc ^= np.array(m, dtype=bool)
        img = Image.fromarray((acc * 255).astype(np.uint8))
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(img, dtype=np.float32) / 255


def ink_x(font, name, y0, y1, side=None):
    """Extensión horizontal de la tinta entre dos alturas."""
    b = clip(path_of(font, name), -3000, y0, 5000, y1)
    if empty(b):
        return None
    x0, _, x1, _ = b.bounds
    return x0, x1


# ------------------------------------------------------------------ fuente
class Lligada:
    def __init__(self, path):
        self.path = path
        self.u = ufoLib2.Font.open(path)
        key = os.path.basename(path)[:-4]
        pal, self.pdx, self.pdy, self.pdw = PAL[key]
        self.pal = ufoLib2.Font.open(os.path.join(ROOT, "sources", pal + ".ufo"))
        self.dotted = "Dotted" in self.u.info.familyName
        self.xh = self.u.info.xHeight
        self.blur = 3 if self.dotted else 1.5
        hy = bounds(self.u, "hyphen")
        self.t = DOT_D if self.dotted else hy[3] - hy[1]
        self._tpl = {}
        self.made = []
        # caracteres que ya tenía la fuente (para poder volver a ejecutar el script)
        self.orig = set(self.u.lib.setdefault(
            "tracet.originalUnicodes", sorted({cp for g in self.u for cp in g.unicodes})))
        self.alias = {}                       # glifo nuevo -> letra base en las reglas

    # ---------------------------------------------------------- trazos
    def stroke(self, pts, closed=False):
        """Línea central -> trazo (o puntos en la Dotted)."""
        if self.dotted:
            seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
            L = sum(seg)
            n = max(1, round(L / DOT_GAP))
            out = []
            for k in range(n if closed else n + 1):
                d, acc = L * k / n, 0
                for i, s in enumerate(seg):
                    if acc + s >= d - 1e-6 or i == len(seg) - 1:
                        u = 0 if s == 0 else min(1, (d - acc) / s)
                        out.append(circle(pts[i][0] + u * (pts[i + 1][0] - pts[i][0]),
                                          pts[i][1] + u * (pts[i + 1][1] - pts[i][1]), DOT_D / 2))
                        break
                    acc += s
            return union(out)
        p = pathops.Path()
        pen = p.getPen()
        pen.moveTo(pts[0])
        for q in pts[1:]:
            pen.lineTo(q)
        pen.closePath() if closed else pen.endPath()
        p.stroke(self.t, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
        p.convertConicsToQuads()
        return p

    def arc(self, cx, cy, rx, ry, a0, a1, n=24, closed=False):
        return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                 cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]

    def scaled(self, p, sx, sy):
        """Escala un acento. En la Dotted se escalan las posiciones, no los puntos."""
        if not self.dotted:
            return moved(p, 0, 0, sx, sy)
        out = []
        for c in contours(p):
            b = c.bounds
            out.append(circle((b[0] + b[2]) / 2 * sx, (b[1] + b[3]) / 2 * sy, DOT_D / 2))
        return union(out)

    def put(self, name, path=None, width=0, anchors=(), unicodes=(), components=()):
        u = self.u
        g = u.newGlyph(name) if name not in u else u[name]
        g.clearContours(); g.clearComponents(); g.clearAnchors()
        if path is not None and not empty(path):
            path.draw(CubicPen(g.getPen()))
        for base, dx, dy in components:
            g.components.append(ufoLib2.objects.Component(base, transformation=(1, 0, 0, 1, round(dx), round(dy))))
        g.width = round(width)
        g.unicodes = list(unicodes)
        for a in anchors:
            g.appendAnchor({"name": a[0], "x": round(a[1]), "y": round(a[2])})
        self.made.append(name)
        return g

    # ---------------------------------------------------------- anclas
    def find(self, gname_, letter, expect_x, min_x):
        from scipy.signal import fftconvolve
        u = self.u
        gb, lb = bounds(u, gname_), bounds(u, letter)
        if gb is None or lb is None:
            return None
        Y0, H = -450, 1450
        X0 = min(gb[0], lb[0]) - 400
        W = (gb[2] - X0) + 400
        G = raster(u, gname_, X0, Y0, W, H, self.blur)
        if letter not in self._tpl:
            self._tpl[letter] = raster(u, letter, lb[0], Y0, lb[2] - lb[0], H, self.blur)
        T = self._tpl[letter]
        tn = (T * T).sum() or 1
        score = fftconvolve(G, T[::-1, ::-1], mode="valid")[0] / tn
        dx = X0 + np.arange(len(score)) / SCALE - lb[0]
        score = score - 0.0006 * np.abs(dx - expect_x)
        score[dx < min_x] = -1e9
        k = int(np.argmax(score))
        return float(dx[k]), float(score[k])

    def standalone_anchors(self):
        """Anclas de cada minúscula suelta."""
        u, xh = self.u, self.xh
        st = {}
        for L in "abcdefghijklmnopqrstuvwxyz":
            b = bounds(u, L)
            top = b[3]
            if top > xh * 1.3:                       # letras con ascendente
                band = ink_x(u, L, top - 60, top + 1)
            else:
                band = ink_x(u, L, xh * 0.6, xh * 1.05)
            tx = (band[0] + band[1]) / 2 if band else (b[0] + b[2]) / 2
            for acc in ("acute", "circumflex", "tilde"):
                n = L + acc
                if n in u:
                    a = clip(path_of(u, n), -3000, max(xh, top) * 1.05, 5000, 2000)
                    if not empty(a):
                        tx = (a.bounds[0] + a.bounds[2]) / 2
                        break
            body = ink_x(u, L, xh * 0.25, xh * 0.75) or (b[0], b[2])
            bx = tx if top > xh * 1.3 else (body[0] + body[1]) / 2
            if L in "ij":                             # sin contar el punto
                top = clip(path_of(u, L), -3000, -2000, 5000, xh * 1.1).bounds[3]
            anc = {"top": (tx, top), "bottom": (bx, 0)}
            if L in "aeiu":
                anc["ogonek"] = (b[2] - (b[2] - b[0]) * 0.22, 0)
            if L == "o":
                anc["center"] = ((body[0] + body[1]) / 2, xh / 2)
            if L in "dh":
                y = xh + (top - xh) * 0.55
                band = ink_x(u, L, y - 15, y + 15)
                anc["bar"] = ((band[0] + band[1]) / 2 if band else tx, y)
            if L == "l":
                y = xh + (top - xh) * 0.25
                band = ink_x(u, L, y - 15, y + 15)
                anc["slash"] = ((band[0] + band[1]) / 2 if band else tx, y)
            if L in "dlt":
                band = ink_x(u, L, top - (top - xh) * 0.3, top + 1)
                anc["caronvert"] = ((band[1] if band else b[2]) + 30, top)
            st[L] = anc
        return st

    def sibling_x(self, g, i):
        """x exacta del agudo de la variante acentuada (o_a.x -> o_aacute.x)."""
        base = g.name.split(".")[0]
        parts = base.split("_")
        p = parts[i]
        if len(p) != 1:
            return None
        sib = "_".join(parts[:i] + [p + "acute"] + parts[i + 1:]) + g.name[len(base):]
        if sib not in self.u or sib == g.name:
            return None
        cb = lambda c: tuple(round(v) for v in BoundsPen_bounds(c))
        own = {cb(c) for c in g.contours}
        new = [BoundsPen_bounds(c) for c in self.u[sib].contours
               if BoundsPen_bounds(c)[1] > self.xh * 1.05 and cb(c) not in own]
        if not new:
            return None
        return (min(b[0] for b in new) + max(b[2] for b in new)) / 2

    def anchors(self):
        u = self.u
        st = self.standalone_anchors()
        self.st = st
        cats = dict(u.lib.get("public.openTypeCategories", {}))
        n = 0
        for g in list(u):
            if g.name.startswith((".", "_")) or g.name in self.made:
                continue
            letters = letters_of(g.name)
            if not all(L in st for L in letters):
                continue
            exp, min_x, pos = 0, -1e9, []
            for L in letters:
                if g.name == L:
                    dx = 0
                else:
                    r = self.find(g.name, L, exp, min_x)
                    if r is None:
                        break
                    dx = r[0]
                pos.append((L, dx))
                exp, min_x = dx + u[L].width, dx + u[L].width * 0.35
            if len(pos) != len(letters):
                continue
            g.clearAnchors()
            for i, (L, dx) in enumerate(pos):
                suf = f"_{i + 1}" if len(pos) > 1 else ""
                for name, (x, y) in st[L].items():
                    if name == "top":
                        sx = self.sibling_x(g, i)
                        x = sx - dx if sx is not None else x
                    g.appendAnchor({"name": name + suf, "x": round(x + dx), "y": round(y)})
            cats[g.name] = "ligature" if len(pos) > 1 else "base"
            n += 1
        # mayúsculas: centro arriba y abajo (para acentos combinables)
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            g = u[c]
            b = bounds(u, c)
            g.clearAnchors()
            g.appendAnchor({"name": "top", "x": round((b[0] + b[2]) / 2), "y": round(b[3])})
            g.appendAnchor({"name": "bottom", "x": round((b[0] + b[2]) / 2), "y": 0})
            cats[c] = "base"
        u.lib["public.openTypeCategories"] = cats
        return n

    # ---------------------------------------------------------- acentos
    def above(self, name, base_top):
        return clip(path_of(self.u, name), -3000, base_top + 15, 5000, 2000)

    def marks(self):
        u, xh, st = self.u, self.xh, self.st
        a_top = st["a"]["top"][1]
        ax = st["a"]["top"][0]
        top_anchor = [("_top", 0, a_top)]

        def from_comp(comp, L):                      # acento de una letra acentuada existente
            tx, ty = st[L]["top"]
            p = self.above(comp, bounds(u, L)[3])
            return moved(p, -tx, a_top - ty)

        acute = from_comp("aacute", "a")
        circ = from_comp("acircumflex", "a")
        bottom = circ.bounds[1]
        cw = circ.bounds[2] - circ.bounds[0]
        marks = {"acutecomb": acute, "gravecomb": from_comp("agrave", "a"), "uni0302": circ,
                 "uni0308": from_comp("adieresis", "a"), "tildecomb": from_comp("ntilde", "n")}
        # caron: circunflejo invertido
        car = moved(circ, 0, 0, 1, -1)
        marks["uni030C"] = moved(car, 0, bottom - car.bounds[1])
        # macron, breve, anillo, punto
        y = bottom + self.t / 2 + 20
        marks["uni0304"] = self.stroke([(-cw * 0.36, y), (cw * 0.36, y)])
        rx = cw * 0.32
        marks["uni0306"] = self.stroke(self.arc(0, bottom + self.t / 2 + rx * 0.8, rx, rx * 0.8, 180, 360))
        die = marks["uni0308"]
        dots = contours(die)
        if self.dotted:
            dot = circle(0, (die.bounds[1] + die.bounds[3]) / 2, DOT_D / 2)
        else:
            d0 = min(dots, key=lambda c: c.bounds[0])
            b = d0.bounds
            dot = moved(d0, -(b[0] + b[2]) / 2, 0)
        marks["uni0307"] = dot
        r = max(cw * 0.17, self.t * 1.3)
        marks["uni030A"] = self.stroke(self.arc(0, bottom + self.t / 2 + r, r, r, 0, 360, 32), closed=True)
        # doble agudo
        small = self.scaled(moved(acute, 0, -acute.bounds[1]), 0.62, 0.8)
        sw = small.bounds[2] - small.bounds[0]
        marks["uni030B"] = union([moved(small, -sw * 0.55, bottom), moved(small, sw * 0.55, bottom)])
        # coma girada (ģ)
        comma = path_of(u, "comma")
        c = comma.bounds
        cm = moved(comma, -(c[0] + c[2]) / 2, -(c[1] + c[3]) / 2)
        turned = moved(cm, 0, 0, -1, -1)
        marks["commaturned.mark"] = moved(turned, 0, bottom - turned.bounds[1])
        marks["dotless.mark"] = None
        for name, p in marks.items():
            uni = [k for k, v in COMBINING.items() if v == name]
            self.put(name, p, 0, top_anchor, uni)
        # debajo: coma, cedilla, ogonek
        self.put("uni0326", moved(cm, 0, -60 - cm.bounds[3]), 0, [("_bottom", 0, 0)], [0x0326])
        ced = clip(path_of(u, "ccedilla"), -3000, -2000, 5000, -12)
        if self.dotted:
            ced = union([c for c in contours(path_of(u, "ccedilla")) if (c.bounds[1] + c.bounds[3]) / 2 < -15])
        cb = ced.bounds
        self.put("uni0327", moved(ced, -(cb[0] + cb[2]) / 2, 0), 0, [("_bottom", 0, 0)], [0x0327])
        og = path_of(self.pal, "ogonek")
        o = og.bounds
        self.put("uni0328", moved(og, -o[2] + self.t / 2, -o[3] + self.t / 2), 0, [("_ogonek", 0, 0)], [0x0328])
        # caron vertical, barras
        q = path_of(u, "quoteright")
        qb = q.bounds
        cv = self.scaled(moved(q, -qb[0], -qb[3]), 0.85, 0.85)
        self.put("caronvert.mark", cv, 0, [("_caronvert", 0, 0)])
        self.put("bar.mark", self.stroke([(-85, 0), (85, 0)]), 0, [("_bar", 0, 0)])
        ang = math.radians(35)
        L = 95
        self.put("slash.mark", self.stroke([(-L * math.cos(ang), -L * math.sin(ang)), (L * math.cos(ang), L * math.sin(ang))]),
                 0, [("_slash", 0, 0)])
        ob = bounds(u, "o")
        h = xh * 0.62
        w = (ob[2] - ob[0]) * 0.42
        self.put("slashlong.mark", self.stroke([(-w, -h), (w, h)]), 0, [("_center", 0, 0)])
        cats = self.u.lib["public.openTypeCategories"]
        for m in list(COMBINING.values()) + EXTRA_MARKS:
            cats[m] = "mark"
        return a_top

    # ---------------------------------------------------------- letras
    def lower_targets(self):
        import glyphsets
        core = set(glyphsets.unicodes_per_glyphset("GF_Latin_Core"))
        have = self.orig
        out = {}
        for cp in sorted(core - have):
            ch = chr(cp)
            if not ch.isalpha() or not ch.islower():
                continue
            if cp in LOWER_SPECIAL:
                out[cp] = LOWER_SPECIAL[cp]
                continue
            nfd = unicodedata.normalize("NFD", ch)
            if len(nfd) == 2 and ord(nfd[1]) in COMBINING and nfd[0] in self.st:
                out[cp] = (nfd[0], COMBINING[ord(nfd[1])])
        return out

    def lower(self):
        u = self.u
        rules = []
        missing = []
        for cp, (base, mark) in self.lower_targets().items():
            name = gname(cp)
            ba = {a.name: a for a in u[base].anchors}
            ma = {a.name: a for a in u[mark].anchors}
            key = next(k for k in ma if k.startswith("_"))[1:]
            if key not in ba:
                missing.append(chr(cp)); continue
            dx, dy = ba[key].x - ma["_" + key].x, ba[key].y - ma["_" + key].y
            if mark == "dotless.mark":         # ı ȷ: la letra sin el punto
                self.put(name, self.dotless_path(base), u[base].width, [], [cp])
            else:
                self.put(name, None, u[base].width, [], [cp], [(base, 0, 0), (mark, dx, dy)])
            rules.append(f"    sub {name} by {base} {mark};")
        return rules, missing

    def dotless_path(self, name):
        """El glifo sin el punto de la i/j (la última letra)."""
        u = self.u
        g = u[name]
        tops = sorted([a for a in g.anchors if a.name.startswith("top")], key=lambda a: a.name)
        tx = tops[-1].x if tops else (bounds(u, name)[0] + bounds(u, name)[2]) / 2
        keep = []
        p = path_of(u, name)
        for c in contours(p):
            b = c.bounds
            is_dot = b[1] > self.xh * 1.1 and abs((b[0] + b[2]) / 2 - tx) < 110 and b[3] < self.xh * 1.6
            if not is_dot:
                keep.append(c)
        # todos los contornos juntos, para conservar los huecos (no unirlos uno a uno)
        out = pathops.Path()
        pen = out.getPen()
        for c in keep:
            c.draw(pen)
        return out

    def dotless_variants(self):
        u = self.u
        pairs = []
        for g in list(u):
            if g.name in self.made or g.name.startswith((".", "_")):
                continue
            parts = g.name.split(".")[0].split("_")
            if parts[-1] not in ("i", "j") or not g.anchors:
                continue
            d = g.name + ".dotless"
            self.put(d, self.dotless_path(g.name), g.width,
                     [(a.name, a.x, a.y) for a in g.anchors])
            self.u.lib["public.openTypeCategories"][d] = self.u.lib["public.openTypeCategories"].get(g.name, "base")
            pairs.append((g.name, d))
        return pairs

    def pal_glyph(self, name):
        """Glifo de la Pal con el desplazamiento de esta fuente."""
        return path_of(self.pal, name, self.pdx, self.pdy), self.pal[name].width + self.pdw

    def upper(self):
        import glyphsets
        core = set(glyphsets.unicodes_per_glyphset("GF_Latin_Core"))
        have = self.orig
        u, pal = self.u, self.pal
        pal_cmap = {cp: g.name for g in pal for cp in g.unicodes}
        for cp in sorted(core - have):
            ch = chr(cp)
            if not (ch.isalpha() and ch.isupper()) or cp not in pal_cmap:
                continue
            pname = pal_cmap[cp]
            name = gname(cp)
            nfd = unicodedata.normalize("NFD", ch)
            base = nfd[0] if len(nfd) == 2 and nfd[0] in u else None
            if base:
                # mayúscula de la Lligada + acento de la Pal en la misma posición
                acc = pathops.op(path_of(pal, pname), path_of(pal, base), pathops.PathOp.DIFFERENCE)
                if self.dotted:
                    keep = [c for c in contours(acc) if c.bounds[2] - c.bounds[0] > 20 and c.bounds[3] - c.bounds[1] > 20]
                    acc = union(keep)
                pb, lb = bounds(pal, base), bounds(u, base)
                below = acc.bounds[3] <= pb[1] + 40
                dx = (lb[0] + lb[2]) / 2 - (pb[0] + pb[2]) / 2
                dy = (lb[1] - pb[1]) if below else (lb[3] - pb[3])
                path = union([path_of(u, base), moved(acc, dx, dy)])
                self.put(name, path, u[base].width, [], [cp])
                self.alias[name] = base
            else:
                path, w = self.pal_glyph(pname)
                self.put(name, path, w, [], [cp])
                self.alias[name] = UPPER_COPY.get(cp, "O")

    def symbols(self, a_top):
        u = self.u
        for n in SYMBOLS:
            if n in self.pal and not (set(self.pal[n].unicodes) & self.orig):
                path, w = self.pal_glyph(n)
                cp = self.pal[n].unicodes
                self.put(n, path, w, [], cp)
        names = {0x0060: "grave", 0x00B4: "acute", 0x02C6: "circumflex", 0x02C7: "caron",
                 0x00A8: "dieresis", 0x02DC: "tilde", 0x00AF: "macron", 0x02D8: "breve",
                 0x02D9: "dotaccent", 0x02DA: "ring", 0x02DD: "hungarumlaut", 0x00B8: "cedilla",
                 0x02DB: "ogonek"}
        have = self.orig
        for cp, mark in SPACING.items():
            if cp in have:
                continue
            p = path_of(u, mark)
            b = p.bounds
            w = max(260, (b[2] - b[0]) + 120)
            dy = 0
            if mark == "uni0328":
                dy = 0
            self.put(names[cp], moved(p, w / 2 - (b[0] + b[2]) / 2, dy), w, [], [cp])

    # ---------------------------------------------------------- reglas
    def features(self, rules, dotless):
        u = self.u
        orig = u.lib.setdefault("tracet.originalFeatures", u.features.text.split(MARKER)[0])
        fea = orig
        # las reglas de unión ignoran los acentos combinables
        fea = re.sub(r"(lookup L\d+ \{\n)(?!    lookupflag)", r"\1    lookupflag IgnoreMarks;\n", fea)
        # mayúsculas nuevas: mismas clases y contextos que su letra base
        by_base = {}
        for new, base in self.alias.items():
            by_base.setdefault(base, []).append(new)
        out = []
        for line in fea.split("\n"):
            if line.startswith("@c") and "[" in line:
                names = line[line.index("[") + 1:line.rindex("]")].split()
                extra = [n for b in names for n in by_base.get(b, [])]
                if extra:
                    line = line[:line.rindex("]")] + " " + " ".join(extra) + "];"
            elif ("'" in line or line.strip().startswith("ignore")) and line.strip().startswith(("sub", "ignore")):
                def rep(m):
                    tok, q = m.group(1), m.group(2)
                    if tok in by_base:
                        return "[" + " ".join([tok] + by_base[tok]) + "]" + q
                    return m.group(0)
                line = re.sub(r"(?<![@\w.\[])([A-Za-z][\w.]*)(')?(?=[\s;])", rep, line)
            out.append(line)
        lines = out
        dec = [MARKER, "lookup Descompon {"] + rules + ["} Descompon;",
               "feature ccmp {", "    lookup Descompon;", "} ccmp;", ""]
        k = next(i for i, l in enumerate(lines) if l.startswith("lookup "))
        lines = lines[:k] + dec + lines[k:]
        top = [m for m in TOP if m in u]
        tail = [MARKER + " (i/j sin punto)",
                f"@TopMarks = [{' '.join(top)}];",
                "lookup SinPunto {"] + [f"    sub {a} by {b};" for a, b in dotless] + ["} SinPunto;",
                "lookup SoftDotted {",
                f"    sub [{' '.join(a for a, _ in dotless)}]' lookup SinPunto @TopMarks;",
                "} SoftDotted;",
                "feature calt {", "    lookup SoftDotted;", "} calt;", ""]
        u.features.text = "\n".join(lines + tail)


def BoundsPen_bounds(c):
    b = BoundsPen(None)
    c.draw(b)
    return b.bounds


def main(path):
    L = Lligada(path)
    for name in list(L.u.keys()):                  # empezar limpio si se vuelve a ejecutar
        if name.endswith(".dotless") or name in EXTRA_MARKS:
            del L.u[name]
    n = L.anchors()
    a_top = L.marks()
    rules, missing = L.lower()
    dotless = L.dotless_variants()
    L.upper()
    L.symbols(a_top)
    L.features(rules, dotless)
    order = list(L.u.lib.get("public.glyphOrder", []))
    order += [g for g in L.u.keys() if g not in order]
    L.u.lib["public.glyphOrder"] = order
    L.u.glyphOrder = order
    L.u.save(overwrite=True)
    print(f"{os.path.basename(path)}: {n} glifos con anclas, {len(rules)} minúsculas por descomposición, "
          f"{len(dotless)} variantes sin punto, {len(L.alias)} mayúsculas. Sin ancla: {''.join(missing) or '-'}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
