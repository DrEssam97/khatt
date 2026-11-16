"""Arabizi to Arabic letters: ``7abibi`` becomes ``حبيبي``.

Arabizi (also called Franco-Arabic or Arabish) writes Arabic in Latin letters, with
digits for the sounds Latin lacks: 2 for hamza, 3 for ain, 5 for khaa, 6 for taa, 7 for
haa, 8 for qaf and 9 for sad. It has no fixed spelling, so no converter is always right.
This one is small and predictable:

* a list of common words in several dialects, converted as a whole;
* the digit letters (``3'`` for ghain), letter pairs (``sh``, ``kh``, ``gh``, ``th``,
  ``dh``, ``ch``) and single letters;
* vowels by a few rules: a vowel that starts a word takes an alef (``أ`` or ``إ``), a
  doubled vowel, a diphthong (``ai``, ``ou``) or a vowel in the last syllable is long
  (``ا``, ``و``, ``ي``), a vowel at the end of a word is written (``ة`` for the ``-a``
  of a word of three or more consonants), and the other short vowels are left out, as
  Arabic usually writes them;
* ``el`` or ``al`` at the start of a word, with or without a hyphen, is the article
  ``ال``.

The rules can't know everything Arabizi leaves out: whether ``t`` is ``ت`` or ``ط``,
or which syllable has the long vowel (``fahem`` comes out ``فهيم``, not ``فاهم``).

Your own words go in ``words``, which wins over everything else. Conversion is always
something you ask for (``--arabizi``): khatt never converts Latin text on its own.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

WORDS: dict[str, str] = {
    "2ana": "أنا",
    "2enta": "إنت",
    "2enti": "إنتي",
    "2nta": "إنت",
    "2ahlan": "أهلا",
    "3ala": "على",
    "3an": "عن",
    "3shan": "عشان",
    "ezayak": "إزيك",
    "ezayek": "إزيك",
    "esmak": "اسمك",
    "esmi": "اسمي",
    "fi": "في",
    "fe": "في",
    "kifak": "كيفك",
    "keefak": "كيفك",
    "kifik": "كيفك",
    "khalas": "خلاص",
    "5alas": "خلاص",
    "la": "لا",
    "ma": "ما",
    "men": "من",
    "min": "من",
    "wa7ed": "واحد",
    "wahed": "واحد",
    "etnein": "اتنين",
    "itnein": "اتنين",
    "tlata": "تلاتة",
    "talata": "ثلاثة",
    "shou": "شو",
    "mabrouk": "مبروك",
    "mabrook": "مبروك",
    "ahlan": "أهلا",
    "ahla": "أهلا",
    "alhamdulillah": "الحمد لله",
    "allah": "الله",
    "ana": "أنا",
    "aywa": "أيوه",
    "bas": "بس",
    "bss": "بس",
    "el7amdulillah": "الحمد لله",
    "enta": "إنت",
    "enti": "إنتي",
    "habibi": "حبيبي",
    "habibti": "حبيبتي",
    "inshallah": "إن شاء الله",
    "insha2allah": "إن شاء الله",
    "inta": "إنت",
    "inti": "إنتي",
    "ma3a": "مع",
    "ma3": "مع",
    "masha2allah": "ما شاء الله",
    "mashallah": "ما شاء الله",
    "mar7aba": "مرحبا",
    "marhaba": "مرحبا",
    "masr": "مصر",
    "ma9r": "مصر",
    "msh": "مش",
    "mish": "مش",
    "mesh": "مش",
    "salam": "سلام",
    "salamu": "سلام",
    "shokran": "شكرا",
    "shukran": "شكرا",
    "sho": "شو",
    "shu": "شو",
    "sabah": "صباح",
    "saba7": "صباح",
    "sa7": "صح",
    "tamam": "تمام",
    "wallah": "والله",
    "wallahi": "والله",
    "walla": "والله",
    "ya": "يا",
    "yalla": "يلا",
    "yallah": "يلا",
    "zay": "زي",
    "zei": "زي",
    "3arabi": "عربي",
    "3arab": "عرب",
    "3alaykom": "عليكم",
    "3alaikum": "عليكم",
    "3likom": "عليكم",
    "7abibi": "حبيبي",
    "7abibti": "حبيبتي",
    "7elw": "حلو",
    "7elwa": "حلوة",
    "7ilwa": "حلوة",
    "7ob": "حب",
    "7ub": "حب",
    "kheir": "خير",
    "5eir": "خير",
    "5er": "خير",
    "khair": "خير",
}
"""Common Arabizi words and their Arabic spelling, in lowercase."""

# Longest first: three letters, then two, then one.
_LETTERS: tuple[tuple[str, str], ...] = (
    ("3'", "غ"),
    ("9'", "ض"),
    ("6'", "ظ"),
    ("7'", "خ"),
    ("sh", "ش"),
    ("ch", "ش"),
    ("kh", "خ"),
    ("gh", "غ"),
    ("th", "ث"),
    ("dh", "ذ"),
    ("2", "ء"),
    ("3", "ع"),
    ("5", "خ"),
    ("6", "ط"),
    ("7", "ح"),
    ("8", "ق"),
    ("9", "ص"),
    ("b", "ب"),
    ("p", "ب"),
    ("t", "ت"),
    ("g", "ج"),
    ("j", "ج"),
    ("d", "د"),
    ("r", "ر"),
    ("z", "ز"),
    ("s", "س"),
    ("c", "ك"),
    ("f", "ف"),
    ("v", "ف"),
    ("q", "ق"),
    ("k", "ك"),
    ("l", "ل"),
    ("m", "م"),
    ("n", "ن"),
    ("h", "ه"),
    ("w", "و"),
    ("y", "ي"),
    ("x", "كس"),
)
_VOWELS = "aeiou"
_LONG = {"a": "ا", "e": "ي", "i": "ي", "o": "و", "u": "و"}
_PUNCTUATION = str.maketrans({"?": "؟", ",": "،", ";": "؛"})
_DIGIT_LETTERS = re.compile(r"[a-z]['’]?[235679]|[235679]['’]?[a-z]", re.IGNORECASE)
_TOKEN = re.compile(r"[A-Za-z0-9'’]+|[^A-Za-z0-9'’]+")
_HYPHENATED_ARTICLE = re.compile(r"\b([ae]l|il)-(?=[A-Za-z0-9])", re.IGNORECASE)
_PRONOUN_ENDINGS = ("ak", "ek", "ik", "ok", "kom", "kum", "hom", "hum")
"""Word endings (your, their...) whose vowel stays short: kifak is كيفك, not كيفاك."""


def is_arabizi(text: str) -> bool:
    """Whether ``text`` looks like Arabizi: Latin words with digit letters, or common words.

    Only a hint (khatt suggests ``--arabizi`` when it sees it); it never converts
    anything by itself.
    """
    if any("؀" <= char <= "ۿ" for char in text):
        return False
    words = re.findall(r"[A-Za-z0-9']+", text.lower())
    return bool(_DIGIT_LETTERS.search(text)) or any(word in WORDS for word in words)


def _units(word: str) -> list[str]:
    """``word`` split into letters, letter pairs and vowels."""
    units = []
    index = 0
    while index < len(word):
        for latin, _ in _LETTERS:
            if word.startswith(latin, index):
                units.append(latin)
                index += len(latin)
                break
        else:
            units.append(word[index])
            index += 1
    return units


def _convert_word(word: str) -> str:
    """One Arabizi word in Arabic letters, by the rules of the module docstring."""
    letters = dict(_LETTERS)
    lowered = word.lower().replace("’", "'")
    if lowered.isdigit():
        return word
    article = ""
    for prefix in ("el-", "al-", "il-", "el", "al"):
        rest = lowered[len(prefix) :]
        if lowered.startswith(prefix) and len(rest) >= 2 and rest[0] not in _VOWELS:
            article, lowered = "ال", rest
            break
    units = _units(lowered)
    consonants = [n for n, unit in enumerate(units) if unit not in _VOWELS]
    last_consonant = consonants[-1] if consonants else -1
    if lowered.endswith(_PRONOUN_ENDINGS):
        last_consonant = -1  # the vowel before the ending is short
    # A word of three or more consonants ending in -a or -ah is feminine: ة.
    feminine = len(consonants) - lowered.endswith("ah") >= 3 and (
        lowered.endswith("a") or lowered.endswith("ah")
    )
    if lowered.endswith("ah") and feminine:
        units = units[:-1]
    out: list[str] = []
    for n, unit in enumerate(units):
        if unit in _VOWELS:
            previous = units[n - 1] if n else ""
            following = units[n + 1] if n + 1 < len(units) else ""
            if n == 0 and not article:
                out.append("أ" if unit in "aou" else "إ")
                if unit in "ou" and following == unit:
                    out.append("و")
            elif previous == unit:
                continue  # the second of a doubled vowel was written with the first
            elif previous in _VOWELS and unit != "a":
                out.append(_LONG[unit])  # a diphthong (ai, ei, au, ou): ي or و
            elif following == unit:
                out.append(_LONG[unit])  # a doubled vowel is long
            elif n == len(units) - 1:
                # a vowel ending the word is written; -a ends a feminine word with ة
                out.append("ة" if unit == "a" and feminine else _LONG[unit])
            elif n == last_consonant - 1 and n > 0:
                out.append(_LONG[unit])  # the vowel of the last syllable
            continue
        arabic = letters.get(unit, unit)
        if out and out[-1] == arabic and n and units[n - 1] == unit:
            continue  # a doubled consonant is one letter (with a shadda, left out)
        if unit == "2" and n == 0 and not article:
            arabic = "أ"
        out.append(arabic)
    return article + "".join(out)


def from_arabizi(text: str, words: Mapping[str, str] | None = None) -> str:
    """Arabizi in Arabic letters.

    Args:
        text: Arabizi, such as ``"ana 7abibi, yalla!"``. Arabic letters in it are left
            as they are, and so are numbers.
        words: Your own spellings, ``{"arabizi": "عربي"}``, matched without regard to
            case; they win over the built-in list and the rules.

    Returns:
        The text with every Latin word in Arabic letters, and ``?``, ``,`` and ``;`` as
        ``؟``, ``،`` and ``؛``.
    """
    own = {key.lower(): value for key, value in (words or {}).items()}
    out = []
    for token in _TOKEN.findall(_HYPHENATED_ARTICLE.sub(r"\1", text)):
        if not re.match(r"[A-Za-z0-9'’]", token):
            out.append(token.translate(_PUNCTUATION))
            continue
        key = token.lower().replace("’", "'")
        if key in own:
            out.append(own[key])
        elif key in WORDS:
            out.append(WORDS[key])
        else:
            out.append(_convert_word(token))
    return "".join(out)
