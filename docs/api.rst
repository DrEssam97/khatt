API reference
=============

Everything here is importable from ``khatt`` itself (``import khatt``), except the
moviepy clips in :mod:`khatt.video` and the Pillow calls in :mod:`khatt.pillow`.

.. module:: khatt

Drawing on images
-----------------

.. autofunction:: draw_text
.. autofunction:: text_bbox
.. autofunction:: overlay
.. autofunction:: word_boxes
.. autoclass:: WordBox
   :members:
.. autoclass:: Span
   :members:
.. autofunction:: caption_image
.. autofunction:: put_text
.. autofunction:: tk_image
.. autofunction:: receipt_image

Numbers, poetry and justified text
----------------------------------

.. autofunction:: arabic_digits
.. autofunction:: poem

Word art, curves and shapes
---------------------------

.. autofunction:: word_art
.. autoclass:: Effect
   :members:
.. autoclass:: Gradient
.. autoclass:: Glow
.. autoclass:: Shadow
.. autoclass:: Extrude
.. autofunction:: get_effect
.. autofunction:: list_effects
.. autoclass:: Arc
.. autoclass:: Wave
.. autofunction:: list_curves
.. autofunction:: calligram
.. autofunction:: list_shapes
.. autofunction:: zakhrafa
.. autofunction:: list_zakhrafa
.. autofunction:: render_svg

OCR training data
-----------------

.. autofunction:: ocr_lines
.. autoclass:: OcrLine
   :members:
.. autoclass:: OcrWord
   :members:
.. autofunction:: write_ocr_dataset

Video captions
--------------

.. autoclass:: khatt.video.TextClip
.. autofunction:: khatt.video.word_captions
.. autofunction:: khatt.video.quran_captions
.. autofunction:: caption_steps
.. autoclass:: CaptionStep
   :members:
.. autoclass:: Word
   :members:
.. autofunction:: group_words
.. autofunction:: words_from_whisper
.. autofunction:: words_from_quran

Terminal art
------------

.. autofunction:: render
.. autofunction:: render_image
.. autofunction:: color_art
.. autofunction:: art_to_image
.. autofunction:: art_to_svg
.. autofunction:: art_to_html
.. autofunction:: animate
.. autoclass:: Animation
   :members:
.. autofunction:: frame_art
.. data:: CANVASES

   Image sizes by name for ``frame_art`` and ``khatt --canvas``: ``header``
   (1500x500), ``social`` (1280x640, GitHub's social preview), ``square``
   (1080x1080), ``story`` (1080x1920) and ``wallpaper`` (1920x1080).

.. autofunction:: fetch
.. autofunction:: fetch_image
.. autoclass:: Fact
   :members:
.. autofunction:: from_arabizi
.. autofunction:: is_arabizi
.. autofunction:: map_image
.. autofunction:: get_style
.. autofunction:: list_styles
.. autofunction:: list_palettes
.. autofunction:: list_frames

Fonts
-----

.. autofunction:: font_path
.. autofunction:: font_paths
.. autofunction:: list_fonts
.. autofunction:: missing_characters

Pillow code you already have
----------------------------

.. automodule:: khatt.pillow
   :members: text, textbbox, textlength, routing

Checking and repairing code
---------------------------

.. module:: khatt
   :no-index:

.. autofunction:: doctor
.. autofunction:: find_reshaping
.. autofunction:: unreshape
.. autofunction:: is_reshaped
.. autofunction:: base_direction
.. autofunction:: strip_tashkeel
.. autoexception:: ReshapedTextWarning
.. autoexception:: UnsupportedCharacterWarning
.. autoexception:: TextOverflowWarning
