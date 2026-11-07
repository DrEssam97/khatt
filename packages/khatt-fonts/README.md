# khatt-fonts

22 more open Arabic fonts for [khatt](https://github.com/DrEssam97/khatt), grouped by
calligraphy style, on top of the 8 khatt bundles. They live in their own package so that
khatt itself stays small.

```bash
pip install khatt-fonts
```

khatt finds the package on its own. Use a font by its name:

```python
import khatt

khatt.word_art("خط جميل", effect="gold", font="jomhuria").save("gold.png")
khatt.draw_text(image, (40, 40), "مرحبا", font="gulzar")
```

```bash
khatt "خط جميل" --effect neon --font marhey -o neon.png
```

| Style | Fonts |
|---|---|
| `kufi` | `reem-kufi-fun`, `noto-kufi`, `kufam`, `qahiri` |
| `naskh` | `scheherazade`, `lateef`, `markazi`, `amiri-quran` |
| `nastaliq` | `gulzar` |
| `display` | `jomhuria`, `lemonada`, `marhey`, `blaka`, `blaka-hollow`, `katibeh`, `mirza`, `el-messiri`, `changa` |
| `handwriting` | `playpen` |
| `modern` | `tajawal`, `almarai`, `alexandria` |

`amiri-quran` is made for Quran text and has no Persian letters. `tajawal` is missing
some Persian letters too.

## Licences

All 22 fonts are under the SIL Open Font License 1.1 and are unmodified copies from
[google/fonts](https://github.com/google/fonts). Each font's licence and copyright
notice is in [`src/khatt_fonts/licenses/`](src/khatt_fonts/licenses/). The code in this
package is under the MIT licence.
