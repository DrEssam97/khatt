"""The rescue kit: undo arabic_reshaper, warn about it, and find it in a project."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
from cli_runner import invoke
from PIL import Image

import khatt
from khatt.cli import main
from khatt.shaping import strip_tashkeel

# Made with arabic-reshaper 3.1.0 and python-bidi 0.6.12, which are not test
# dependencies: (typed, reshape(typed), get_display(reshape(typed))).
CASES = [
    ("مرحبا بالعالم", "ﻣﺮﺣﺒﺎ ﺑﺎﻟﻌﺎﻟﻢ", "ﻢﻟﺎﻌﻟﺎﺑ ﺎﺒﺣﺮﻣ"),
    ("السلام عليكم ورحمة الله", "ﺍﻟﺴﻼﻡ ﻋﻠﻴﻜﻢ ﻭﺭﺣﻤﺔ ﷲ", "ﷲ ﺔﻤﺣﺭﻭ ﻢﻜﻴﻠﻋ ﻡﻼﺴﻟﺍ"),
    ("لا إله إلا الله", "ﻻ ﺇﻟﻪ ﺇﻻ ﷲ", "ﷲ ﻻﺇ ﻪﻟﺇ ﻻ"),
    ("العدد 2026 كبير", "ﺍﻟﻌﺪﺩ 2026 ﻛﺒﻴﺮ", "ﺮﻴﺒﻛ 2026 ﺩﺪﻌﻟﺍ"),
    ("قال (مرحبا) ثم ذهب.", "ﻗﺎﻝ (ﻣﺮﺣﺒﺎ) ﺛﻢ ﺫﻫﺐ.", ".ﺐﻫﺫ ﻢﺛ )ﺎﺒﺣﺮﻣ( ﻝﺎﻗ"),
    ("محمد ﷺ", "ﻣﺤﻤﺪ ﷺ", "ﷺ ﺪﻤﺤﻣ"),
    ("تعلم Python اليوم", "ﺗﻌﻠﻢ Python ﺍﻟﻴﻮﻡ", "ﻡﻮﻴﻟﺍ Python ﻢﻠﻌﺗ"),
]


class TestUnreshape:
    @pytest.mark.parametrize(("typed", "reshaped", "shown"), CASES)
    def test_display_order(self, typed: str, reshaped: str, shown: str) -> None:
        assert khatt.unreshape(shown) == typed

    @pytest.mark.parametrize(("typed", "reshaped", "shown"), CASES)
    def test_typed_order(self, typed: str, reshaped: str, shown: str) -> None:
        assert khatt.unreshape(reshaped, display_order=False) == typed

    def test_typed_order_told_by_the_shapes(self) -> None:
        # Long joined words read initial-medial-final: no need to say so.
        assert khatt.unreshape("ﻣﺮﺣﺒﺎ ﺑﺎﻟﻌﺎﻟﻢ") == "مرحبا بالعالم"

    def test_tashkeel_arabic_reshaper_deleted(self) -> None:
        # arabic_reshaper drops harakat by default; they can't come back.
        typed = "مَرْحَبًا بِكُمْ"
        assert khatt.unreshape("ﻢﻜﺑ ﺎﺒﺣﺮﻣ") == strip_tashkeel(typed)

    def test_a_line_starting_with_a_latin_word(self) -> None:
        typed = "Google لأن المعلم من ذلك"
        shown = "Google ﻚﻟﺫ ﻦﻣ ﻢﻠﻌﻤﻟﺍ ﻥﻷ"
        assert khatt.unreshape(shown) != typed  # looks like a line ending with it
        assert khatt.unreshape(shown, direction="ltr") == typed

    def test_lines_shown_one_by_one(self) -> None:
        shown = "ﻝﻭﺃ ﺮﻄﺳ\nﻥﺎﺛ ﺮﻄﺳ"
        assert khatt.unreshape(shown) == "سطر أول\nسطر ثان"

    @pytest.mark.parametrize("text", ["", "hello", "مرحبا", "﴿مرحبا﴾", "محمد ﷺ", "2026"])
    def test_typed_text_unchanged(self, text: str) -> None:
        assert not khatt.is_reshaped(text)
        assert khatt.unreshape(text) == text

    def test_is_reshaped(self) -> None:
        assert khatt.is_reshaped("ﻣﺮﺣﺒﺎ")
        assert khatt.is_reshaped("ﷲ")  # arabic_reshaper's ligature for الله

    def test_bad_direction(self) -> None:
        with pytest.raises(ValueError, match="direction"):
            khatt.unreshape("ﻣﺮﺣﺒﺎ", direction="up")

    def test_draws_like_the_typed_text(self) -> None:
        typed, _, shown = CASES[0]
        a, b = Image.new("RGB", (500, 90), "white"), Image.new("RGB", (500, 90), "white")
        khatt.draw_text(a, (10, 10), typed)
        khatt.draw_text(b, (10, 10), khatt.unreshape(shown))
        assert a.tobytes() == b.tobytes()


class TestWarning:
    def test_reshaped_text_warns(self) -> None:
        with pytest.warns(khatt.ReshapedTextWarning, match=r"khatt\.unreshape"):
            khatt.draw_text(Image.new("RGB", (300, 80)), (0, 0), CASES[0][2])

    def test_typed_text_does_not(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            khatt.draw_text(Image.new("RGB", (300, 80)), (0, 0), "محمد ﷺ ﴿مرحبا﴾")


class TestFindReshaping:
    @staticmethod
    def _project(root: Path) -> Path:
        (root / "app").mkdir()
        (root / "app" / "render.py").write_text(
            "import arabic_reshaper\n"
            "from bidi.algorithm import get_display\n"
            "\n"
            "def label(text):\n"
            "    return get_display(arabic_reshaper.reshape(text))\n",
            encoding="utf-8",
        )
        (root / "app" / "short.py").write_text(
            "from arabic_reshaper import reshape\nfrom bidi import get_display\n"
            "x = reshape('a')  # fix later\ny = get_display(x)\n",
            encoding="utf-8",
        )
        (root / "app" / "clean.py").write_text(
            "import numpy as np\nnp.reshape([1], (1,))\n# arabic_reshaper used to be here\n",
            encoding="utf-8",
        )
        (root / ".venv" / "lib").mkdir(parents=True)
        (root / ".venv" / "lib" / "pkg.py").write_text(
            "import arabic_reshaper\narabic_reshaper.reshape('a')\n", encoding="utf-8"
        )
        return root

    def test_finds_the_calls(self, tmp_path: Path) -> None:
        places = khatt.find_reshaping(self._project(tmp_path))
        assert places == [
            "app/render.py:5: return get_display(arabic_reshaper.reshape(text))",
            "app/short.py:3: x = reshape('a')  # fix later",
            "app/short.py:4: y = get_display(x)",
        ]

    def test_one_file_and_a_limit(self, tmp_path: Path) -> None:
        project = self._project(tmp_path)
        assert khatt.find_reshaping(project / "app" / "short.py") == [
            "short.py:3: x = reshape('a')  # fix later",
            "short.py:4: y = get_display(x)",
        ]
        assert len(khatt.find_reshaping(project, limit=1)) == 1

    def test_missing_path(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            khatt.find_reshaping(tmp_path / "nope")

    def test_doctor_reports_them(self, tmp_path: Path) -> None:
        report = khatt.doctor(self._project(tmp_path))
        assert len(report["reshaping"]) == 3
        assert any("3 place(s)" in warning for warning in report["warnings"])
        assert khatt.doctor()["reshaping"] == []

    def test_cli(self, tmp_path: Path) -> None:
        result = invoke(main, ["--doctor", str(self._project(tmp_path))])
        assert result.exit_code == 0
        assert "pre-shaping Arabic:" in result.output
        assert "app/render.py:5:" in result.output
        missing = invoke(main, ["--doctor", str(tmp_path / "nope")])
        assert missing.exit_code == 2
        assert "no such file or folder" in missing.output
