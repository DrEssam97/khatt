# Moving off arabic_reshaper

For years, the way to get Arabic into Pillow and matplotlib was:

```python
import arabic_reshaper
from bidi.algorithm import get_display

draw.text((x, y), get_display(arabic_reshaper.reshape(text)), font=font)
```

`arabic_reshaper.reshape` swaps each letter for its joined shape (Arabic "presentation
forms", such as `ﻣ` for an initial meem), and `get_display` reverses the line into the
order it is shown in. Both steps were needed because Pillow and matplotlib couldn't
shape Arabic themselves.

They can now, which breaks that recipe:

- **Pillow** shapes Arabic when it has Raqm. Many Linux images already have it, and
  Pillow is working on Raqm in all its wheels.
- **matplotlib 3.11 and later** shape Arabic in their own wheels.
- **OpenCV 5.1 and later** shape Arabic in `cv2.putText`. Pre-shaped text comes out as
  `?` with its built-in font, or backwards with a font of your own.

Given pre-shaped text, they shape it a second time. The letters come out unjoined or in
the wrong order, often only on some machines, so it can look fine on yours and broken in
production.

## Find it

`khatt --doctor` shows which shapers your environment has. Give it your project, and it
also lists every place that pre-shapes Arabic:

```text
$ khatt --doctor src/
...
pre-shaping Arabic:
  src/render.py:44: return get_display(arabic_reshaper.reshape(text))
warning: 1 place(s) in src/ pre-shape Arabic (listed above). ...
```

It exits with status 1 when it finds any, so it can guard a project in CI. As a
[pre-commit](https://pre-commit.com) hook:

```yaml
repos:
  - repo: https://github.com/DrEssam97/khatt
    rev: v0.14.0
    hooks:
      - id: khatt-doctor
        args: ["src/"]  # the folder to scan; the default is the whole project
```

From Python: `khatt.find_reshaping("src/")`, or `khatt.doctor("src/")`.

## Fix it

Pass the text as typed to something that shapes it once.

With khatt, the output is the same whether or not Pillow has Raqm:

```python
import khatt

khatt.draw_text(image, (x, y), text, font="amiri", size_px=48)
```

Or keep your `ImageDraw` code and change only the call: `khatt.pillow.text(draw, xy,
text, ...)` takes `draw.text`'s arguments, and turns already-reshaped strings back
before drawing them. For a library you can't edit, wrap its calls in
`with khatt.pillow.routing():`.

Or, where you know the library shapes Arabic (Pillow with Raqm, matplotlib 3.11+,
OpenCV 5.1+), drop both calls and give it `text` itself.

## When Pillow shapes Arabic everywhere

Pillow is working on Raqm in all its wheels, Windows and macOS included. On the day that
ships, every `get_display(arabic_reshaper.reshape(text))` passed to `ImageDraw.text`
starts drawing backwards, on every machine at once, after a routine `pip install -U`.
Three steps get you ready now:

1. Run `khatt --doctor .` (or add the hook above) to list every place that pre-shapes.
2. Replace those calls with `khatt.draw_text`, which shapes the text once whatever
   Pillow has, or give Pillow the plain text where you know it has Raqm.
3. Run `khatt.unreshape()` over any reshaped strings you have stored.

## Text that was already reshaped

Strings saved after `arabic_reshaper` (in a database, a JSON file, subtitles) can be
turned back:

```python
plain = khatt.unreshape(saved)
```

- Presentation forms go back to letters: a lam-alef ligature to lam and alef, `ﷲ` to
  `الله`. Symbols typed on purpose, such as `ﷺ` and the ornate brackets `﴿ ﴾`, stay.
- Lines that went through `get_display` are put back in typed order. Whether a line
  did is told from its letter shapes; where they can't tell (short words, lam-alef),
  it counts as having gone through `get_display`, the usual recipe. Pass
  `display_order=False` if you only reshaped.
- A mostly Arabic line that starts with a Latin word looks the same, once shown, as
  one that ends with it. Those come back right to left; pass `direction="ltr"` if
  yours start with the Latin word.
- `arabic_reshaper` drops harakat by default, so they can't come back.
- Multi-line text that went through `get_display` in one piece can't be put back:
  python-bidi moves its line breaks. Text shown one line at a time is fine.
- `khatt.is_reshaped(text)` says whether a string has presentation forms. khatt warns
  (`khatt.ReshapedTextWarning`) when it is asked to draw one.
