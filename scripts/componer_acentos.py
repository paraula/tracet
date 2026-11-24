"""
Compone en los UFO de sources/ las letras acentuadas que se pueden hacer con
acentos que la fuente ya tiene (agudo, grave, circunflejo, diéresis, anillo,
caron, macron, punto, cedilla), además de ȷ, los acentos combinables
(U+0300…) y los acentos sueltos ˙ ¸.

  python scripts/componer_acentos.py

Cada acento se copia de una letra de referencia ya dibujada (á, Á, š, Š, ç…)
y se coloca sobre la letra nueva con la misma separación y el mismo
desplazamiento horizontal. Solo crea o reescribe los glifos de la lista;
el resto de los UFO no se toca.

También añade anclas top/bottom a las letras base y a los acentos
combinables, para que fontmake genere la colocación de acentos (mark).
"""
import glob, os, sys
import ufoLib2
from fontTools.agl import UV2AGL
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
import pathops
from fontTools.pens.basePen import BasePen

sys.stdout.reconfigure(encoding="utf-8")


class CubicPen(BasePen):
    """Pasa las curvas cuadráticas de pathops a cúbicas, como el resto del
    UFO (gftools no acepta curvas cuadráticas al quitar solapamientos)."""
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
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# acento -> (referencia minúscula, base), (referencia mayúscula, base), letras nuevas
ACCENTS = {
    "acute":      (("aacute", "a"), ("Aacute", "A"),
                   [0x0106, 0x0107, 0x0139, 0x013A, 0x0143, 0x0144, 0x0154, 0x0155,
                    0x015A, 0x015B, 0x0179, 0x017A, 0x1E82, 0x1E83]),
    "grave":      (("agrave", "a"), ("Agrave", "A"), [0x1E80, 0x1E81, 0x1EF2, 0x1EF3]),
    "circumflex": (("acircumflex", "a"), ("Acircumflex", "A"), [0x0174, 0x0175, 0x0176, 0x0177]),
    "dieresis":   (("adieresis", "a"), ("Adieresis", "A"), [0x1E84, 0x1E85]),
    "ring":       (("aring", "a"), ("Aring", "A"), [0x016E, 0x016F]),
    "caron":      (("scaron", "s"), ("Scaron", "S"),
                   [0x010C, 0x010D, 0x010E, 0x011A, 0x011B, 0x0147, 0x0148, 0x0158,
                    0x0159, 0x0164]),
    "tilde":      (("ntilde", "n"), ("Ntilde", "N"), []),
    "macron":     (None, None, [0x0100, 0x0101, 0x0112, 0x0113, 0x012A, 0x012B, 0x014C, 0x014D,
                                0x016A, 0x016B]),
    "dot":        (None, None, [0x010A, 0x010B, 0x0116, 0x0117, 0x0120, 0x0121, 0x0130,
                                0x017B, 0x017C]),
    "cedilla":    (("ccedilla", "c"), ("Ccedilla", "C"), [0x015E, 0x015F]),
}
COMBINING = {0x0300: "grave", 0x0301: "acute", 0x0302: "circumflex", 0x0303: "tilde",
             0x0304: "macron", 0x0307: "dot", 0x0308: "dieresis", 0x030A: "ring",
             0x030C: "caron", 0x0327: "cedilla"}
SPACING = {0x02D9: "dot", 0x00B8: "cedilla"}
BASE_OVERRIDE = {0x012B: "dotlessi", 0x0130: "I"}   # ī sobre ı


def gname(u):
    return UV2AGL.get(u, f"uni{u:04X}")


def base_of(u):
    import unicodedata
    if u in BASE_OVERRIDE:
        return BASE_OVERRIDE[u]
    return unicodedata.normalize("NFD", chr(u))[0]


def cbounds(contours):
    b = BoundsPen(None)
    for c in contours:
        c.draw(b)
    return b.bounds


def center(b):
    return (b[0] + b[2]) / 2


class Composer:
    def __init__(self, ufo):
        self.u = ufo
        self.dotted = "Dotted" in ufo.info.familyName
        self.made = []

    def lim(self, top):
        return top + 1 if self.dotted else top * 0.75

    def split(self, comp, base):
        """Contornos del acento (encima de la base) y del resto."""
        top = cbounds(self.u[base].contours)[3]
        acc, rest = [], []
        for c in self.u[comp].contours:
            (acc if cbounds([c])[1] > self.lim(top) else rest).append(c)
        return acc, rest

    def ref(self, comp, base):
        """acento, desplazamiento x respecto al centro de la base, separación vertical."""
        acc, rest = self.split(comp, base)
        ab, rb = cbounds(acc), cbounds(rest)
        return acc, center(ab) - center(rb), ab[1] - rb[3]

    def cedilla(self, comp, base):
        g = self.u[comp]
        if self.dotted:
            acc = [c for c in g.contours if (cbounds([c])[1] + cbounds([c])[3]) / 2 < -20]
        else:
            path = pathops.Path()
            g.draw(path.getPen())
            def clip(x0, y0, x1, y1):
                r = pathops.Path()
                p = r.getPen()
                p.moveTo((x0, y0)); p.lineTo((x1, y0)); p.lineTo((x1, y1)); p.lineTo((x0, y1)); p.closePath()
                return pathops.op(path, r, pathops.PathOp.INTERSECTION)
            hook = clip(-2000, -1000, 3000, -10)
            stem = clip(-2000, -40, 3000, -10).bounds          # anchura del pie
            top = clip(stem[0], -10, stem[2], 30)               # unión con la letra
            acc_path = pathops.op(hook, top, pathops.PathOp.UNION)
            tmp = ufoLib2.objects.Glyph()
            acc_path.draw(CubicPen(tmp.getPen()))
            acc = list(tmp.contours)
        rb = cbounds(self.u[base].contours)
        ab = cbounds(acc)
        return acc, center(ab) - center(rb), None

    def accent(self, kind, upper):
        refs = ACCENTS[kind]
        if kind == "macron":
            acc = list(self.u["macron"].contours)
            a, rx, gap = self.ref(*ACCENTS["acute"][1 if upper else 0])
            ha, hm = cbounds(a), cbounds(acc)
            return acc, 0, gap + ((ha[3] - ha[1]) - (hm[3] - hm[1])) / 2
        if kind == "dot":
            acc, _ = self.split("i", "dotlessi")
            _, _, gap = self.ref(*ACCENTS["dieresis"][1 if upper else 0])
            return acc, 0, gap
        if kind == "cedilla":
            return self.cedilla(*refs[1 if upper else 0])
        return self.ref(*refs[1 if upper else 0])

    def put(self, name, unicodes, base, acc, rx, gap, width=None):
        tb = cbounds(self.u[base].contours) if base else None
        ab = cbounds(acc)
        if gap is None:       # cedilla: misma altura que en la referencia
            dx, dy = (center(tb) if tb else 0) + rx - center(ab), 0
        else:
            dx = (center(tb) + rx if tb else 0) - center(ab)
            dy = (tb[3] if tb else 0) + gap - ab[1]
        g = self.u.newGlyph(name) if name not in self.u else self.u[name]
        g.clearContours(); g.clearComponents(); g.clearAnchors()
        pen = g.getPen()
        if base:
            for c in self.u[base].contours:
                c.draw(pen)
        tp = TransformPen(pen, (1, 0, 0, 1, round(dx), round(dy)))
        for c in acc:
            c.draw(tp)
        g.unicodes = unicodes
        g.width = self.u[base].width if base else (width or 0)
        self.made.append(name)
        return g

    def copy_kerning(self, new, base):
        k = self.u.kerning
        for (a, b), v in list(k.items()):
            if a == base:
                k[(new, b)] = v
            if b == base:
                k[(a, new)] = v
        for (a, b), v in list(k.items()):
            if a == base and b == base:
                k[(new, new)] = v

    def run(self):
        u = self.u
        # letras acentuadas
        for kind, (_, _, letters) in ACCENTS.items():
            for cp in letters:
                base = base_of(cp)
                upper = len(base) == 1 and base.isupper()
                acc, rx, gap = self.accent(kind, upper)
                self.put(gname(cp), [cp], base, acc, rx, gap)
                self.copy_kerning(gname(cp), base)
        # ȷ (j sin punto)
        jtop = cbounds(u["dotlessi"].contours)[3]
        j = u.newGlyph("uni0237") if "uni0237" not in u else u["uni0237"]
        j.clearContours()
        pen = j.getPen()
        for c in u["j"].contours:
            if cbounds([c])[1] <= self.lim(jtop):
                c.draw(pen)
        j.unicodes, j.width = [0x0237], u["j"].width
        self.copy_kerning("uni0237", "j")
        self.made.append("uni0237")
        # acentos sueltos con avance (˙ ¸): mismo ancho que el agudo suelto
        w = u["acute"].width
        for cp, kind in SPACING.items():
            acc, rx, gap = self.accent(kind, False)
            g = self.put(gname(cp), [cp], None, acc, 0, gap, width=w)
            self.center_in(g, w, kind, gap)
        # combinables: ancho 0, dibujados sobre la letra anterior
        cats = dict(u.lib.get("public.openTypeCategories", {}))
        wo = u["o"].width
        xh = cbounds(u["x"].contours)[3]
        for cp, kind in COMBINING.items():
            acc, rx, gap = self.accent(kind, False)
            g = self.put(gname(cp), [cp], None, acc, 0, gap, width=0)
            ab = cbounds(g.contours)
            g.move((round(-wo / 2 - center(ab)), 0 if kind == "cedilla" else round(xh)))
            ab = cbounds(g.contours)
            if kind == "cedilla":
                g.appendAnchor({"name": "_bottom", "x": round(-wo / 2), "y": 0})
            else:
                g.appendAnchor({"name": "_top", "x": round(-wo / 2), "y": round(xh)})
            cats[g.name] = "mark"
        # anclas en las letras base
        bases = [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"] + ["dotlessi", "uni0237"]
        for n in bases:
            g = u[n]
            b = cbounds(g.contours)
            g.clearAnchors()
            g.appendAnchor({"name": "top", "x": round(center(b)), "y": round(b[3])})
            g.appendAnchor({"name": "bottom", "x": round(center(b)), "y": 0})
            cats[n] = "base"
        u.lib["public.openTypeCategories"] = cats
        # sin esto, fontmake solo activa 'mark' para el script por defecto, no para latn
        if "languagesystem" not in u.features.text:
            u.features.text = "languagesystem DFLT dflt;\nlanguagesystem latn dflt;\n" + u.features.text
        # orden de glifos
        order = list(u.lib.get("public.glyphOrder", []))
        order += [n for n in self.made if n not in order]
        u.lib["public.glyphOrder"] = order
        u.glyphOrder = order

    def center_in(self, g, w, kind, gap):
        ab = cbounds(g.contours)
        xh = cbounds(self.u["x"].contours)[3]
        g.move((round(w / 2 - center(ab)), 0 if kind == "cedilla" else round(xh)))


def main():
    for path in sorted(glob.glob(os.path.join(ROOT, "sources", "*.ufo"))):
        u = ufoLib2.Font.open(path)
        c = Composer(u)
        c.run()
        u.save(overwrite=True)
        print(f"{os.path.basename(path):32} +{len(c.made)} glifos (total {len(u)})")


if __name__ == "__main__":
    main()
