# khatt-fonts

26 open Arabic fonts for [khatt](https://github.com/DrEssam97/khatt), grouped by
calligraphy style. They live in their own package so that khatt itself stays small.

```bash
pip install khatt-fonts
```

khatt finds the package on its own. Use a font by its name, or a style by its name for
that style's first font:

```python
import khatt

khatt.word_art("خط جميل", effect="gold", font="lalezar").save("gold.png")
khatt.draw_text(image, (40, 40), "مرحبا", font="ruqaa")
```

```bash
khatt "خط جميل" --effect neon --font rakkas -o neon.png
```

| Style | Fonts |
|---|---|
| `ruqaa` | `aref-ruqaa` |
| `kufi` | `reem-kufi`, `reem-kufi-fun`, `noto-kufi`, `kufam`, `qahiri` |
| `naskh` | `scheherazade`, `lateef`, `markazi`, `amiri-quran` |
| `nastaliq` | `gulzar` |
| `display` | `lalezar`, `rakkas`, `jomhuria`, `lemonada`, `marhey`, `blaka`, `blaka-hollow`, `katibeh`, `mirza`, `el-messiri`, `changa` |
| `handwriting` | `playpen` |
| `modern` | `tajawal`, `almarai`, `alexandria` |

`amiri-quran` is made for Quran text and has no Persian letters. `tajawal` is missing
some Persian letters too.

## Licences

All 26 fonts are under the SIL Open Font License 1.1 and are unmodified copies from
[google/fonts](https://github.com/google/fonts). Each font's licence and copyright
notice is in [`src/khatt_fonts/licenses/`](src/khatt_fonts/licenses/). The code in this
package is under the MIT licence.
