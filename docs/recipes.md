# Arabic in other Python libraries

Many Python libraries draw text without shaping Arabic: the letters come out
unjoined, or left to right, or as empty boxes. These recipes draw the text with
khatt and hand the finished pixels to the library, so it never has to shape
anything. If your library already shapes Arabic (a browser, Kivy 3, Pillow with
Raqm), you don't need them.

## OpenCV

`cv2.putText` draws Arabic as `???` before OpenCV 5.0 and as separate letters in
reverse order in 5.0. OpenCV 5.1 joins Arabic letters, but still reverses Arabic-Indic
digits (١٥٠ comes out ٠٥١), misplaces a bracket or quote that starts a line, and draws
text pre-shaped with arabic_reshaper as `?`. `khatt.put_text` draws the same correct
text on every OpenCV version. It takes the same order of arguments, BGR colours, and the
baseline origin OpenCV uses, and draws into the frame in place (NumPy needed):

```python
import cv2
import khatt

frame = cv2.imread("frame.png")
khatt.put_text(frame, "مرحبا بالعالم", (40, 80), size_px=48, color=(0, 255, 255),
               stroke_width=3, stroke_color=(0, 0, 0))
cv2.imwrite("labelled.png", frame)
```

It works on grayscale and BGRA frames too, and `channels="rgb"` takes RGB arrays
(from Pillow, Matplotlib or most other libraries). Only the part of the frame under
the text is touched, so it is cheap to call on every frame of a video.

## pygame

Make the text once as an image, then turn it into a surface:

```python
import pygame
import khatt

image = khatt.caption_image("مرحبا بالعالم", font_size=48, color="white")
label = pygame.image.frombytes(image.tobytes(), image.size, "RGBA")
screen.blit(label, (40, 40))
```

## Dear PyGui

Textures take RGBA floats from 0 to 1:

```python
import numpy as np
import dearpygui.dearpygui as dpg
import khatt

image = khatt.caption_image("مرحبا بالعالم", font_size=40, color="black")
data = (np.asarray(image, dtype=np.float32) / 255).ravel()
with dpg.texture_registry():
    dpg.add_static_texture(image.width, image.height, data, tag="arabic")
dpg.add_image("arabic", parent=window)
```

## Tkinter

Tk on Linux draws Arabic as separate letters, left to right. `khatt.tk_image` gives Tk
a picture of the text instead, which looks the same on every system:

```python
import khatt

photo = khatt.tk_image("مرحبا بالعالم", size_px=32)
tk.Label(root, image=photo).pack()
```

For CustomTkinter, use `customtkinter.CTkImage(light_image=khatt.caption_image(...))`.

## Streamlit and other web apps

Browsers shape Arabic themselves, so plain text needs nothing. For text drawn into an
image (a chart, a certificate, a thumbnail), draw it with khatt and show the image:

```python
import streamlit as st
import khatt

st.image(khatt.caption_image("مرحبا بالعالم", font_size=48))
```

## Thermal receipt printers

ESC/POS printers have no Arabic fonts, so receipts print as images.
`khatt.receipt_image` lays them out at the printer's width:

```python
from escpos.printer import Usb
import khatt

receipt = khatt.receipt_image(
    [("قهوة عربية", "15.00"), ("كعكة", "12.50"), "---", ("المجموع", "27.50")],
    title="مقهى الخط",
    footer="شكرا لزيارتكم",
    width="80mm",  # or "58mm", or a number of dots
)
Usb(0x04B8, 0x0202).image(receipt)
```
