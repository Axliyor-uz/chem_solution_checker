"""Text helpers that move between what a student types and what they read.

Internally every formula is stored in plain ASCII (``H2O``, ``SO4^2-``).
Only at render time is it turned into typeset chemistry (``H₂O``, ``SO₄²⁻``).
Keeping the two representations apart means the parser never has to worry
about Unicode and the display never has to worry about grammar.
"""

from __future__ import annotations

import re
from typing import Final

SUBSCRIPTS: Final[dict[str, str]] = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
}
SUPERSCRIPTS: Final[dict[str, str]] = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻",
}
_SUB_TO_ASCII: Final[dict[int, str]] = {ord(v): k for k, v in SUBSCRIPTS.items()}
#: Keyed by character, not ordinal, because it is used for ``in`` tests.
_SUP_TO_ASCII: Final[dict[str, str]] = {v: k for k, v in SUPERSCRIPTS.items()}

#: Everything a student might type for "reacts to give".
FORWARD_ARROWS: Final[tuple[str, ...]] = ("-->", "->", "=>", "→", "⟶", "⇒")
#: Everything a student might type for "equilibrium".
REVERSIBLE_ARROWS: Final[tuple[str, ...]] = ("<->", "<=>", "⇌", "⇄", "↔", "<-->")

CANONICAL_FORWARD: Final[str] = "->"
CANONICAL_REVERSIBLE: Final[str] = "<->"

_STATE_PATTERN: Final[re.Pattern[str]] = re.compile(r"\((s|l|g|aq)\)\s*$", re.IGNORECASE)


def strip_unicode_digits(text: str) -> str:
    """Turn typeset digits back into ASCII so the parser can read them.

    ``H₂SO₄`` becomes ``H2SO4`` and ``Fe³⁺`` becomes ``Fe^3+``.
    """
    text = text.translate(_SUB_TO_ASCII)
    out: list[str] = []
    in_super = False
    for char in text:
        if char in _SUP_TO_ASCII:
            if not in_super:
                out.append("^")
                in_super = True
            out.append(_SUP_TO_ASCII[char])
        else:
            in_super = False
            out.append(char)
    return "".join(out)


def normalize_arrows(text: str) -> str:
    """Collapse every accepted arrow spelling onto two canonical forms."""
    # Reversible arrows are parked on a placeholder first: the canonical form
    # "<->" contains "->", so replacing forward arrows would otherwise split it.
    placeholder = "\x00"
    for arrow in sorted(REVERSIBLE_ARROWS, key=len, reverse=True):
        text = text.replace(arrow, placeholder)
    for arrow in sorted(FORWARD_ARROWS, key=len, reverse=True):
        text = text.replace(arrow, f" {CANONICAL_FORWARD} ")
    # A bare "=" is an arrow too, once the "<=>" spellings are already parked.
    text = re.sub(r"(?<![<\->=])=(?![>=])", f" {CANONICAL_FORWARD} ", text)
    text = text.replace(placeholder, f" {CANONICAL_REVERSIBLE} ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_input(text: str) -> str:
    """Full clean-up of raw keyboard input into canonical ASCII notation."""
    text = strip_unicode_digits(text)
    text = text.replace("∙", "*").replace("·", "*").replace("•", "*")
    text = text.replace("↑", "(g)").replace("↓", "(s)")
    text = normalize_arrows(text)
    return re.sub(r"\s+", " ", text).strip()


def _superscript(text: str) -> str:
    return "".join(SUPERSCRIPTS.get(char, char) for char in text)


def _subscript(text: str) -> str:
    return "".join(SUBSCRIPTS.get(char, char) for char in text)


def to_display(text: str) -> str:
    """Typeset an ASCII formula or whole equation for reading.

    Digits are subscripted only when they follow an element symbol or a
    closing bracket, so the ``2`` in ``2H2O`` stays full size as a
    coefficient while both other digits drop down.
    """
    text = strip_unicode_digits(text)
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "^":
            index += 1
            start = index
            while index < length and text[index] in "0123456789+-":
                index += 1
            out.append(_superscript(text[start:index]))
            continue
        if char.isdigit():
            start = index
            while index < length and text[index].isdigit():
                index += 1
            previous = out[-1] if out else ""
            if previous and (previous[-1].isalpha() or previous[-1] in ")]}"):
                out.append(_subscript(text[start:index]))
            else:
                out.append(text[start:index])
            continue
        if char == "*":
            out.append("·")
            index += 1
            continue
        out.append(char)
        index += 1
    rendered = "".join(out)
    rendered = rendered.replace(CANONICAL_REVERSIBLE, "⇌").replace(CANONICAL_FORWARD, "→")
    return rendered


def split_state(token: str) -> tuple[str, str | None]:
    """Peel a trailing physical state off a species token."""
    match = _STATE_PATTERN.search(token)
    if not match:
        return token, None
    return token[: match.start()].strip(), match.group(1).lower()


def format_number(value: float, digits: int = 4) -> str:
    """Format a quantity for a results table without trailing noise."""
    if value == 0:
        return "0"
    if abs(value) >= 1e5 or abs(value) < 1e-4:
        return f"{value:.{digits}e}"
    return f"{round(value, digits):g}"
