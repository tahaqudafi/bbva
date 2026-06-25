"""
Unit tests for phonetic alphabet parsing and email utilities.
No external dependencies.
"""

import pytest
from phonetic import (
    parse_spelled_text,
    normalize_email,
    validate_email_format,
    spell_out_text,
)


class TestParseSpelledText:
    # NATO phonetic words -----------------------------------------------

    def test_nato_full_words(self):
        assert parse_spelled_text("Alpha Bravo Charlie Delta") == "abcd"

    def test_nato_case_insensitive(self):
        assert parse_spelled_text("ALPHA BRAVO") == "ab"

    def test_nato_with_for_filler(self):
        assert parse_spelled_text("A for Alpha, B for Bravo") == "ab"

    def test_single_letters(self):
        assert parse_spelled_text("A B C D") == "abcd"

    def test_mixed_nato_and_letters(self):
        assert parse_spelled_text("Alpha B Charlie") == "abc"

    # Digits ------------------------------------------------------------

    def test_spoken_digits(self):
        assert parse_spelled_text("one two three") == "123"

    def test_digit_zero(self):
        assert parse_spelled_text("zero") == "0"

    # Special email characters ------------------------------------------

    def test_at_sign(self):
        assert parse_spelled_text("at") == "@"

    def test_dot(self):
        assert parse_spelled_text("dot") == "."

    def test_hyphen(self):
        assert parse_spelled_text("hyphen") == "-"

    def test_underscore(self):
        assert parse_spelled_text("underscore") == "_"

    def test_dash_alias(self):
        assert parse_spelled_text("dash") == "-"

    def test_period_alias(self):
        assert parse_spelled_text("period") == "."

    # Full email composition --------------------------------------------

    def test_email_nato_spelling(self):
        # "alpha at bravo dot com" → "a@b.com"  ("com" is literal)
        assert parse_spelled_text("alpha at bravo dot com") == "a@b.com"

    def test_email_literal_words(self):
        assert parse_spelled_text("john at example dot com") == "john@example.com"

    def test_email_with_underscore(self):
        assert parse_spelled_text("alpha underscore bravo at example dot com") == "a_b@example.com"

    def test_email_with_digit(self):
        assert parse_spelled_text("alpha one two at example dot com") == "a12@example.com"

    # Edge cases --------------------------------------------------------

    def test_empty_string(self):
        assert parse_spelled_text("") == ""

    def test_whitespace_only(self):
        assert parse_spelled_text("   ") == ""

    def test_commas_stripped(self):
        assert parse_spelled_text("Alpha, Bravo, Charlie") == "abc"


class TestValidateEmailFormat:
    def test_simple_valid(self):
        assert validate_email_format("user@example.com") is True

    def test_valid_with_plus(self):
        assert validate_email_format("user+tag@example.com") is True

    def test_valid_with_dots(self):
        assert validate_email_format("first.last@company.co.uk") is True

    def test_valid_with_digits(self):
        assert validate_email_format("user123@example.org") is True

    def test_invalid_no_at(self):
        assert validate_email_format("userexample.com") is False

    def test_invalid_no_domain(self):
        assert validate_email_format("user@") is False

    def test_invalid_no_tld(self):
        assert validate_email_format("user@example") is False

    def test_invalid_empty(self):
        assert validate_email_format("") is False

    def test_invalid_double_at(self):
        assert validate_email_format("user@@example.com") is False


class TestSpellOutText:
    def test_letters(self):
        result = spell_out_text("AB")
        assert result == "A, B"

    def test_email_contains_at(self):
        result = spell_out_text("a@b.com")
        assert "at" in result

    def test_email_contains_dot(self):
        result = spell_out_text("a@b.com")
        assert "dot" in result

    def test_digit_spoken(self):
        result = spell_out_text("1")
        assert result == "one"

    def test_underscore_spoken(self):
        result = spell_out_text("_")
        assert result == "underscore"

    def test_hyphen_spoken(self):
        result = spell_out_text("-")
        assert result == "hyphen"


class TestNormalizeEmail:
    def test_phonetic_email(self):
        result = normalize_email("john at example dot com")
        assert result == "john@example.com"