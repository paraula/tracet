# Tracet — versión para Google Fonts

**Esta carpeta (Escritorio\tracet) es el original del proyecto y será el repositorio de GitHub.** La carpeta de Google Drive `Google Fonts\Tracet - versión Google Fonts` es una copia del 24-11-2026 y no se edita.

No es la fuente interna de Paraula. La interna (Paraula Pal v1.200) se genera a partir de estos UFO con `Paraula Pal\scripts\build_paraula_pal_v1200.py`, en Drive.

| Google Fonts | Origen interno |
|---|---|
| Tracet Pal (Thin, Regular, Bold, ExtraBold) | Paraula Pal |
| Tracet Pal Dotted (Regular) | Paraula Pal Punteada |
| Tracet Lligada (pendiente) | Paraula Lligada 26 |

## Carpetas

- `sources/`: los UFO editables. **Son el original**: los cambios se hacen aquí.
- `fonts/ttf/`: los TTF compilados. No se editan a mano.
- `sources/config.yaml` y `sources/config-dotted.yaml`: configuración de `gftools builder`, la compilación oficial de Google Fonts.
- `documentation/`: descripción de la familia e imágenes para Google Fonts.
- El script que creó los UFO a partir de los OTF internos (`otf_a_ufo.py`) se queda solo en Drive: depende de las fuentes internas y no va al repositorio.
- `scripts/componer_acentos.py`: monta sobre los UFO las letras con acentos ya existentes (Ć Č Ā Ė Ş Ů…), los acentos combinables, ˙ ¸ y ȷ, y añade anclas para colocar los acentos. Se puede volver a ejecutar: solo reescribe sus propios glifos.
- `sources/dibujos/trazos_pal_v2.svg`: copia del dibujo de Illustrator (`Paraula Pal/Illustrator/Font Pal Paraula Regular_v2.svg`) con los caracteres nuevos.
- `scripts/trazos_svg.py`: convierte ese dibujo en glifos para los 4 pesos y la Dotted: Æ Œ Ð Þ Đ Ħ Ł ẞ, ð þ đ ħ ł, los acentos breve, ogonek, doble agudo, coma inferior y caron vertical, y todas las letras que los llevan. Se ejecuta después de `componer_acentos.py`.
- `scripts/build.py`: compila los UFO en TTF.

## Compilar

Si se han cambiado los dibujos o los acentos, primero se regeneran esos glifos:

```
python scripts/componer_acentos.py
python scripts/trazos_svg.py
```

Compilación oficial de Google Fonts (con hinting automático):

```
cd sources
gftools builder config.yaml
gftools builder config-dotted.yaml
```

`python scripts/build.py` hace una compilación rápida, sin gftools, para pruebas.

Git está configurado con la dirección oculta de GitHub (`…@users.noreply.github.com`), no con el correo de Paraula. El repositorio será `github.com/paraula/tracet`.

## Cambios respecto a la versión interna

- Nombres de familia y de archivo nuevos. Licencia OFL. Diseñador: David Martínez.
- La ExtraBold está escalada x0,905 y tiene la misma altura de mayúsculas que la Regular.
- Métricas verticales según Google: lineGap 0, typo = hhea. El interlineado es el mismo que el de la versión interna.
- Glifos con nombres estándar. Se han quitado los caracteres de control (LF), el guion blando y los contornos vacíos.
- Los signos matemáticos tienen todos la misma anchura. Se han añadido los separadores U+2028 y U+2029.
- Se han añadido las tablas gasp/prep, STAT y meta.

## Pendiente

1. Dirección del repositorio de GitHub en el copyright.
2. Revisar el kerning de las letras nuevas (ahora copiado de su letra base). En ď ľ ť el apóstrofo queda muy cerca de la letra siguiente.
3. Limpieza de los avisos de contornos.
4. Tracet Lligada.

El juego de caracteres GF Latin Core está completo: 319 de 319 en los 5 estilos.
