"""
Genera las imágenes de muestra a partir de fonts/ttf/:
  documentation/img/          Tracet Pal y Tracet Pal Dotted
  documentation/lligada/img/  Tracet Lligada y Tracet Lligada Dotted

  python scripts/muestras.py

La Lligada se compone con HarfBuzz (las uniones son reglas OpenType) y se
dibuja con FreeType.
"""
import os
import numpy as np
import freetype
import uharfbuzz as hb
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTF = os.path.join(ROOT, "fonts", "ttf")
OUT = os.path.join(ROOT, "documentation", "img")
OUT_L = os.path.join(ROOT, "documentation", "lligada", "img")
INK, PAPER, SOFT, LINE = (28, 28, 27), (250, 248, 243), (120, 118, 112), (205, 200, 190)


def font(name, size):
    return ImageFont.truetype(os.path.join(TTF, name + ".ttf"), size, layout_engine=ImageFont.Layout.RAQM
                              if ImageFont.core.HAVE_RAQM else ImageFont.Layout.BASIC)


def hb_text(im, x, base, text, name, size, fill=None):
    """Escribe text con la fuente name; (x, base) es el inicio de la línea base."""
    fill = fill or INK
    path = os.path.join(TTF, name + ".ttf")
    hbf = hb.Font(hb.Face(hb.Blob.from_file_path(path)))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hbf, buf, {})
    face = freetype.Face(path)
    face.set_char_size(size * 64)
    k = size / face.units_per_EM
    cover = np.zeros((im.height, im.width), np.uint8)
    pen = x
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        face.load_glyph(info.codepoint, freetype.FT_LOAD_NO_HINTING | freetype.FT_LOAD_RENDER)
        g = face.glyph
        bm = g.bitmap
        if bm.width and bm.rows:
            a = np.array(bm.buffer, np.uint8).reshape(bm.rows, bm.pitch)[:, :bm.width]
            gx = round(pen + pos.x_offset * k) + g.bitmap_left
            gy = round(base - pos.y_offset * k) - g.bitmap_top
            x0, y0 = max(gx, 0), max(gy, 0)
            x1, y1 = min(gx + bm.width, im.width), min(gy + bm.rows, im.height)
            if x1 > x0 and y1 > y0:
                sub = a[y0 - gy:y1 - gy, x0 - gx:x1 - gx]
                cover[y0:y1, x0:x1] = np.maximum(cover[y0:y1, x0:x1], sub)
        pen += pos.x_advance * k
    base_im = np.array(im, np.float32)
    al = (cover.astype(np.float32) / 255)[..., None]
    out = base_im * (1 - al) + np.array(fill, np.float32) * al
    im.paste(Image.fromarray(out.astype(np.uint8)))
    return pen


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


# ------------------------------------------------------------------ Lligada
def lligada_specimen():
    W, H = 2048, 1024
    im = Image.new("RGB", (W, H), PAPER)
    hb_text(im, 120, 330, "Tracet Lligada", "TracetLligada-Regular", 250)
    hb_text(im, 126, 470, "Joined handwriting model for learning to write", "TracetPal-Regular", 52, SOFT)
    hb_text(im, 126, 680, "La lluna, la pruna, vestida de dol.", "TracetLligada-Regular", 110)
    hb_text(im, 126, 880, "La lluna, la pruna, vestida de dol.", "TracetLligada-Bold", 110)
    im.save(os.path.join(OUT_L, "image1.png"))


def lligada_dotted():
    W, H = 2048, 1024
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    hb_text(im, 120, 110, "Tracet Lligada Dotted", "TracetPal-Regular", 64, SOFT)
    size = 190
    rows = [("TracetLligada-Regular", "bona nit"), ("TracetLligadaDotted-Regular", "bona nit"),
            ("TracetLligadaDotted-Regular", "bona nit")]
    base = 400
    for f, txt in rows:
        xh = base - round(size * 347 / 1000)
        asc = base - round(size * 721 / 1000)
        for yy, w in ((asc, 2), (xh, 2), (base, 4)):
            d.line((120, yy, W - 120, yy), fill=LINE, width=w)
        hb_text(im, 140, base, txt, f, size)
        base += 270
    im.save(os.path.join(OUT_L, "image2.png"))


def lligada_charset():
    W, H = 2048, 1024
    im = Image.new("RGB", (W, H), PAPER)
    rows = [("abcdefghijklmnopqrstuvwxyz", "TracetLligada-Regular"),
            ("àáâäãåāăąæçćčďđðéèêëėęěēğģħíìîïįīıķĺľłñńňņ", "TracetLligada-Regular"),
            ("óòôöõőøœŕřśšşșßťțþúùûüůűųūýÿźżž", "TracetLligada-Regular"),
            ("ABCDEFGHIJKLMNOPQRSTUVWXYZ ÇĞŁŐŠŽÐÞ", "TracetLligada-Regular"),
            ("0123456789 .,:;¡!¿?«»“”()&@#%€$£+−×÷=", "TracetLligada-Regular"),
            ("Paraula escriu amb lletra lligada.", "TracetLligada-Bold")]
    base = 150
    for txt, f in rows:
        hb_text(im, 110, base, txt, f, 78)
        base += 150
    im.save(os.path.join(OUT_L, "image3.png"))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    specimen()
    dotted()
    charset()
    print("OK", sorted(os.listdir(OUT)))
    if os.path.exists(os.path.join(TTF, "TracetLligada-Regular.ttf")):
        os.makedirs(OUT_L, exist_ok=True)
        lligada_specimen()
        lligada_dotted()
        lligada_charset()
        print("OK", sorted(os.listdir(OUT_L)))
