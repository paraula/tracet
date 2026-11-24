"""
Compila los UFO de sources/ en TTF (fonts/ttf/) con fontmake y añade lo que
Google Fonts pide a fuentes sin hinting: tablas gasp/prep y STAT.

  python scripts/build.py
"""
import glob, os, subprocess, sys
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import ttProgram
from fontTools.otlLib.builder import buildStatTable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "fonts", "ttf")
os.makedirs(OUT, exist_ok=True)

WEIGHTS = [(100, "Thin"), (400, "Regular"), (700, "Bold"), (800, "ExtraBold")]


def fix_nonhinting(f):
    """Equivale a `gftools fix-nonhinting`."""
    gasp = newTable("gasp")
    gasp.gaspRange = {0xFFFF: 0x000F}
    f["gasp"] = gasp
    prep = newTable("prep")
    prep.program = ttProgram.Program()
    prep.program.fromAssembly(["PUSHW[]", "511", "SCANCTRL[]", "PUSHB[]", "4", "SCANTYPE[]"])
    f["prep"] = prep
    f["head"].flags |= 1 << 3


def add_stat(f):
    # en fuentes estáticas, una sola entrada: la de su propio peso
    wght = f["OS/2"].usWeightClass
    name = dict(WEIGHTS).get(wght, "Regular")
    value = dict(value=wght, name=name)
    if wght == 400:
        value.update(flags=0x2, linkedValue=700)
    buildStatTable(f, [dict(tag="wght", name="Weight", values=[value])])


for ufo in sorted(glob.glob(os.path.join(ROOT, "sources", "*.ufo"))):
    subprocess.run([sys.executable, "-m", "fontmake", "-u", ufo, "-o", "ttf",
                    "--output-dir", OUT, "--overlaps-backend", "pathops"], check=True)
    ttf = os.path.join(OUT, os.path.basename(ufo)[:-4] + ".ttf")
    f = TTFont(ttf)
    fix_nonhinting(f)
    add_stat(f)
    f.save(ttf)
    print("OK", os.path.basename(ttf))
