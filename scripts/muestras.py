"""
Genera las imágenes de muestra de documentation/img/ a partir de fonts/ttf/.

  python scripts/muestras.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTF = os.path.join(ROOT, "fonts", "ttf")
OUT = os.path.join(ROOT, "documentation", "img")
INK, PAPER, SOFT, LINE = (28, 28, 27), (250, 248, 243), (120, 118, 112), (205, 200, 190)


def font(name, size):
    return ImageFont.truetype(os.path.join(TTF, name + ".ttf"), size, layout_engine=ImageFont.Layout.RAQM
                              if ImageFont.core.HAVE_RAQM else ImageFont.Layout.BASIC)


def specimen():
    W, H = 2048, 1024
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.text((120, 70), "Tracet", font=font("TracetPal-Regular", 300), fill=INK)
    d.text((126, 420), "Handwriting-model type for learning to read and write", font=font("TracetPal-Regular", 52), fill=SOFT)
    y = 540
    for style, label in (("Thin", "Thin"), ("Regular", "Regular"), ("Bold", "Bold"), ("ExtraBold", "ExtraBold")):
        d.text((126, y), f"{label}  Aa Bb Cc Ññ Çç Łł Őő 0123", font=font("TracetPal-" + style, 76), fill=INK)
        y += 110
    im.save(os.path.join(OUT, "image1.png"))


def dotted():
    W, H = 2048, 1024
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.text((120, 60), "Tracet Pal Dotted", font=font("TracetPal-Regular", 64), fill=SOFT)
    size = 190
    rows = [("TracetPal-Regular", "La lluna"), ("TracetPalDotted-Regular", "La lluna"),
            ("TracetPalDotted-Regular", "La lluna")]
    y = 158
    for f, txt in rows:
        fo = font(f, size)
        # PIL dibuja desde la línea de ascendentes (hhea ascent = 1050)
        base = y + round(size * 1050 / 1000)
        xh = base - round(size * 348 / 1000)
        cap = base - round(size * 721 / 1000)
        for yy, w in ((cap, 2), (xh, 2), (base, 4)):
            d.line((120, yy, W - 120, yy), fill=LINE, width=w)
        d.text((140, y), txt, font=fo, fill=INK)
        y += 270
    im.save(os.path.join(OUT, "image2.png"))


def charset():
    W, H = 2048, 1024
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    f = font("TracetPal-Regular", 74)
    rows = ["ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "abcdefghijklmnopqrstuvwxyz",
            "ÀÁÂÄÅĂĄÆÇĆČĎĐÉÈĘĚËĞĢĦÍĮİĶĹĽŁÑŃŇŅ",
            "ÓÖŐØŒŔŘŚŠŞȘŤȚÞÚÜŮŰŲÝŸŹŻŽẞ",
            "àáâäåăąæçćčďđðéèęěëğģħíįıķĺľłñńňņ",
            "óöőøœŕřśšşșßťțþúüůűųýÿźżž",
            "0123456789 .,:;¡!¿?«»“”‘’()[]{}&@#%€$£+−×÷="]
    y = 70
    for r in rows:
        d.text((110, y), r, font=f, fill=INK)
        y += 128
    im.save(os.path.join(OUT, "image3.png"))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    specimen()
    dotted()
    charset()
    print("OK", sorted(os.listdir(OUT)))
