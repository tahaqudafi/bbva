"""Phonetic alphabet parser, email normalizer, and readback formatter."""

import re

_NATO: dict[str, str] = {
    "alpha": "a", "alfa": "a",
    "bravo": "b",
    "charlie": "c", "charli": "c",
    "delta": "d",
    "echo": "e",
    "foxtrot": "f", "fox trot": "f",
    "golf": "g",
    "hotel": "h",
    "india": "i",
    "juliet": "j", "juliett": "j",
    "kilo": "k",
    "lima": "l",
    "mike": "m",
    "november": "n",
    "oscar": "o",
    "papa": "p",
    "quebec": "q",
    "romeo": "r",
    "sierra": "s",
    "tango": "t",
    "uniform": "u",
    "victor": "v",
    "whiskey": "w", "whisky": "w",
    "x-ray": "x", "x ray": "x", "xray": "x",
    "yankee": "y",
    "zulu": "z",
}

_DIGITS: dict[str, str] = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}

_SPECIALS: dict[str, str] = {
    "at sign": "@", "at": "@",
    "dot": ".", "period": ".", "full stop": ".",
    "hyphen": "-", "dash": "-", "minus": "-",
    "underscore": "_", "under score": "_", "under": "_",
    "space": " ",
}

_DIGIT_WORDS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}

_SPECIAL_SPOKEN = {
    "@": "at",
    ".": "dot",
    "-": "hyphen",
    "_": "underscore",
}


def parse_spelled_text(text: str) -> str:
    """
    Convert spoken spelling to a normalized string.

    Handles NATO phonetic alphabet, single letters, digits, and
    special characters for email addresses.

    Examples:
      "Alpha Bravo Charlie"         -> "abc"
      "A for Alpha, B for Bravo"    -> "ab"
      "john at example dot com"     -> "john@example.com"
      "one two three"               -> "123"
    """
    text = text.lower().strip()
    text = re.sub(r"\b(as in|like)\b", " ", text)
    text = text.replace(",", " ")
    text = re.sub(r"\s+", " ", text).strip()

    tokens = text.split()
    result: list[str] = []
    i = 0

    while i < len(tokens):
        token = tokens[i]

        # "A for Alpha" means one letter. Skip "for" AND the phonetic word after it.
        if token == "for" and i > 0:
            i += 2  # skip "for" + the phonetic confirmation that follows
            continue

        matched = False
        # Try longest phrase first (3 words, then 2, then 1)
        for length in (3, 2, 1):
            phrase = " ".join(tokens[i : i + length])
            if phrase in _SPECIALS:
                result.append(_SPECIALS[phrase])
                i += length
                matched = True
                break
            if phrase in _NATO:
                result.append(_NATO[phrase])
                i += length
                matched = True
                break
            if phrase in _DIGITS:
                result.append(_DIGITS[phrase])
                i += length
                matched = True
                break

        if not matched:
            if len(token) == 1 and token.isalpha():
                result.append(token)
            elif token.isdigit():
                result.append(token)
            elif token.isalpha():
                # Non-phonetic word (e.g. "gmail", "com") — treat as literal
                result.append(token)
            # Unrecognized non-alpha tokens are discarded
            i += 1

    return "".join(result)


def normalize_email(spelled: str) -> str:
    """Parse a phonetically spelled email address."""
    return parse_spelled_text(spelled)


def validate_email_format(email: str) -> bool:
    """Return True if email matches a basic RFC-compliant pattern."""
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def spell_out_text(text: str) -> str:
    """
    Convert text to a spoken letter-by-letter readback string.

    Example:
      "jo@ex.com" -> "J, O, at, E, X, dot, C, O, M"
    """
    parts: list[str] = []
    for ch in text:
        if ch in _SPECIAL_SPOKEN:
            parts.append(_SPECIAL_SPOKEN[ch])
        elif ch.isdigit():
            parts.append(_DIGIT_WORDS[ch])
        elif ch.isalpha():
            parts.append(ch.upper())
        else:
            parts.append(ch)
    return ", ".join(parts)
