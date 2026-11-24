# Tracet

![Tracet Pal glyphs](documentation/img/proof-glyphs.png)

Tracet is a family of handwriting-model typefaces for learning to read and write, designed by David Martínez at [Paraula](https://paraula.com).

- **Tracet Pal**: an upright, print-script model ("lletra de pal") in four weights: Thin, Regular, Bold and ExtraBold.
- **Tracet Pal Dotted**: the same letters drawn as dotted lines, for tracing practice.

The letters are built from a single stroke skeleton, the same line a child follows with a pencil. Each weight is the same skeleton with a different stroke width, and the dotted style places evenly spaced dots along it.

*Tracet* is Catalan for "trace, stroke".

## Character set

Google Fonts Latin Core (GF_Latin_Core), which covers the languages of Western, Central and Eastern Europe written in the Latin script.

## Building

The UFO files in `sources/` are the masters. To build the fonts:

```
pip install -r requirements.txt
cd sources
gftools builder config.yaml
gftools builder config-dotted.yaml
```

The fonts are written to `fonts/ttf/`.

### Helper scripts

`scripts/` contains the tools used to edit the UFO masters. They are not needed to build the fonts.

- `componer_acentos.py`: composes accented letters from the accents already drawn, adds the combining marks and the mark anchors.
- `trazos_svg.py`: imports the letters and accents drawn as centre-line strokes in `sources/dibujos/*.svg`. It strokes them at the width of each weight and dots them for the Dotted style.
- `build.py`: a local build with fontmake that does not require gftools.

## License

This Font Software is licensed under the SIL Open Font License, Version 1.1. The license is in [OFL.txt](OFL.txt) and is also available with a FAQ at https://openfontlicense.org

## Authors

See [AUTHORS.txt](AUTHORS.txt).
