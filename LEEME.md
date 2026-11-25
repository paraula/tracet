# Tracet — versión para Google Fonts

**Esta carpeta (Escritorio\tracet) es el original del proyecto y será el repositorio de GitHub.** La carpeta de Google Drive `Google Fonts\Tracet - versión Google Fonts` es una copia del 24-11-2026 y no se edita.

No es la fuente interna de Paraula. La interna (Paraula Pal v1.200) se genera a partir de estos UFO con `Paraula Pal\scripts\build_paraula_pal_v1200.py`, en Drive.

| Google Fonts | Origen interno |
|---|---|
| Tracet Pal (Thin, Regular, Bold, ExtraBold) | Paraula Pal |
| Tracet Pal Dotted (Regular) | Paraula Pal Punteada |
| Tracet Lligada (Regular, Bold) — en preparación | Paraula Lligada 26 |
| Tracet Lligada Dotted (Regular) — en preparación | Paraula Lligada 26 Puntejada R31 |

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
python scripts/calidad.py
```

`calidad.py` limpia los contornos, pone el kerning detrás de ď ľ ť Ľ y quita el punto de la i/j cuando llevan un acento combinable. `muestras.py` regenera las imágenes de `documentation/img/` después de compilar.

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

## Estado

Tracet Pal y Tracet Pal Dotted: juego GF Latin Core completo (319/319). Enviadas a Google Fonts: https://github.com/google/fonts/issues/11470

## Tracet Lligada (en preparación)

- `sources/TracetLligada-*.ufo` y `TracetLligadaDotted-Regular.ufo` salen de Paraula Lligada 26 v1.100 con `lligada_otf_a_ufo.py` (en Drive, como `otf_a_ufo.py`). Las reglas de unión de Fontself están en el `features.fea` de cada UFO.
- `lligada_verificar.py` (en Drive) compara la Tracet Lligada compilada con la interna en 57.065 textos. El 24-11-2026 dio 0 diferencias en los 3 estilos: las uniones son idénticas.
- En la Dotted, cada punto es un componente del glifo `_dot` (`scripts/puntos_componentes.py`). Así el TTF pasa de 10,8 a 5,2 MB.
- Se compila sin hinting (`autohintTTF: false`) para no multiplicar el tamaño.
- Los scripts de la Pal (`componer_acentos.py`, `trazos_svg.py`, `calidad.py`, `build.py`) solo actúan sobre `TracetPal*.ufo`.
- Los TTF de la Lligada no se suben al repositorio hasta que esté completa (`.gitignore`).
- `scripts/lligada_acentos.py` completa el juego salvo ð y þ: las minúsculas acentuadas nuevas se descomponen en letra + acento combinable (ccmp), las reglas de unión ignoran los acentos y cada glifo de unión lleva anclas sobre cada letra. La i/j pierden el punto con acento. Las mayúsculas y los símbolos salen de la Pal. Después hay que pasar `puntos_componentes.py` a la Dotted.
- Comprobado el 25-11-2026: las uniones de siempre, 0 diferencias en 57.065 textos; las 118 letras nuevas se unen igual que su letra base (26.550 combinaciones por estilo).
- `scripts/lligada_eth_thorn.py` añade ð y þ con los trazos de la propia Lligada: la ð es la d con el asta curvada hacia la izquierda y una barra inclinada; la þ es la h con la bajada de la p. Se unen igual que la d y la h (también en las ligaduras con la o). Va después de `lligada_acentos.py` y antes de `puntos_componentes.py`. Con esto, el juego GF Latin Core está completo (319/319).

```
cd sources
gftools builder config-lligada.yaml
gftools builder config-lligada-dotted.yaml
```
