"""Turn typed text into chemistry objects.

The grammar accepted here is deliberately forgiving of how students actually
write equations — ``2H2O(l)``, ``SO4^2-``, ``SO42-``, ``Ca(OH)2``,
``CuSO4*5H2O`` — while still refusing anything genuinely ambiguous. Every
failure raises :class:`ParseError` carrying a message a student can act on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final, Iterator

from data.elements import ELEMENTS, resolve_case
from utils.formatting import normalize_input, split_state, to_display

VALID_STATES: Final[frozenset[str]] = frozenset({"s", "l", "g", "aq"})
_OPEN_TO_CLOSE: Final[dict[str, str]] = {"(": ")", "[": "]", "{": "}"}
_CLOSE_TO_OPEN: Final[dict[str, str]] = {v: k for k, v in _OPEN_TO_CLOSE.items()}
_ELEMENT_TOKEN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z][a-z]?")
_TRAILING_STATE: Final[re.Pattern[str]] = re.compile(r"^\((s|l|g|aq)\)", re.IGNORECASE)


class ParseError(ValueError):
    """Raised when input cannot be read as chemistry.

    Args:
        message: What is wrong, in plain language.
        position: Character offset in the offending token, if known.
        suggestion: A corrected version the student can accept.
    """

    def __init__(self, message: str, position: int | None = None, suggestion: str | None = None):
        super().__init__(message)
        self.message = message
        self.position = position
        self.suggestion = suggestion


@dataclass(frozen=True, slots=True)
class Formula:
    """A single chemical formula: its composition and its net charge."""

    raw: str
    composition: dict[str, int]
    charge: int = 0

    @property
    def display(self) -> str:
        """The formula typeset with subscripts and superscripts."""
        return to_display(self.raw)

    @property
    def molar_mass(self) -> float:
        """Molar mass in g/mol, summed from standard atomic weights."""
        return sum(ELEMENTS[symbol].mass * count for symbol, count in self.composition.items())

    @property
    def atom_count(self) -> int:
        return sum(self.composition.values())

    @property
    def is_single_element(self) -> bool:
        """True for free elements such as ``Fe``, ``O2`` or ``S8``."""
        return len(self.composition) == 1 and self.charge == 0

    def mass_contributions(self) -> list[tuple[str, int, float, float]]:
        """Per-element ``(symbol, count, subtotal, percent)`` breakdown."""
        total = self.molar_mass
        rows: list[tuple[str, int, float, float]] = []
        for symbol, count in sorted(self.composition.items()):
            subtotal = ELEMENTS[symbol].mass * count
            percent = (subtotal / total * 100.0) if total else 0.0
            rows.append((symbol, count, subtotal, percent))
        return rows

    def __str__(self) -> str:
        return self.raw


@dataclass(frozen=True, slots=True)
class Species:
    """A formula as it appears in an equation: coefficient, formula, state."""

    coefficient: int
    formula: Formula
    state: str | None = None
    raw: str = ""

    @property
    def display(self) -> str:
        prefix = "" if self.coefficient == 1 else str(self.coefficient)
        suffix = f"({self.state})" if self.state else ""
        return f"{prefix}{self.formula.display}{suffix}"

    @property
    def ascii(self) -> str:
        prefix = "" if self.coefficient == 1 else str(self.coefficient)
        suffix = f"({self.state})" if self.state else ""
        return f"{prefix}{self.formula.raw}{suffix}"

    def atoms(self) -> dict[str, int]:
        """Composition scaled by the coefficient."""
        return {s: c * self.coefficient for s, c in self.formula.composition.items()}

    @property
    def total_charge(self) -> int:
        return self.formula.charge * self.coefficient

    def with_coefficient(self, coefficient: int) -> "Species":
        return Species(coefficient, self.formula, self.state, self.raw)


@dataclass(slots=True)
class Equation:
    """A complete reaction, both sides parsed."""

    reactants: list[Species]
    products: list[Species]
    reversible: bool = False
    raw: str = ""
    conditions: dict[str, str] = field(default_factory=dict)

    @property
    def arrow(self) -> str:
        return "⇌" if self.reversible else "→"

    @property
    def ascii_arrow(self) -> str:
        return "<->" if self.reversible else "->"

    @property
    def display(self) -> str:
        left = " + ".join(s.display for s in self.reactants)
        right = " + ".join(s.display for s in self.products)
        return f"{left} {self.arrow} {right}"

    @property
    def ascii(self) -> str:
        left = " + ".join(s.ascii for s in self.reactants)
        right = " + ".join(s.ascii for s in self.products)
        return f"{left} {self.ascii_arrow} {right}"

    @property
    def species(self) -> list[Species]:
        return [*self.reactants, *self.products]

    @property
    def elements(self) -> list[str]:
        """Every element present, ordered by atomic number."""
        found = {symbol for s in self.species for symbol in s.formula.composition}
        return sorted(found, key=lambda symbol: ELEMENTS[symbol].number)

    @property
    def has_charges(self) -> bool:
        return any(s.formula.charge for s in self.species)

    def with_coefficients(self, coefficients: list[int]) -> "Equation":
        """Return a copy carrying new coefficients, reactants then products."""
        expected = len(self.species)
        if len(coefficients) != expected:
            raise ValueError(f"Expected {expected} coefficients, got {len(coefficients)}.")
        split = len(self.reactants)
        return Equation(
            reactants=[s.with_coefficient(c) for s, c in zip(self.reactants, coefficients[:split])],
            products=[s.with_coefficient(c) for s, c in zip(self.products, coefficients[split:])],
            reversible=self.reversible,
            raw=self.raw,
            conditions=dict(self.conditions),
        )


class ChemicalParser:
    """Reads formulas, species and equations from text."""

    # ---------------------------------------------------------------- formulas

    def parse_formula(self, text: str) -> Formula:
        """Parse a bare formula, optionally with a charge or hydrate dot.

        Args:
            text: Something like ``Ca(OH)2``, ``SO4^2-`` or ``CuSO4*5H2O``.

        Returns:
            The parsed :class:`Formula`.

        Raises:
            ParseError: If the text is not a readable formula.
        """
        raw = normalize_input(text).replace(" ", "")
        if not raw:
            raise ParseError("Enter a formula first.")
        body, charge = self._split_charge(raw)
        if not body:
            raise ParseError("A charge needs a formula in front of it.")
        self._check_brackets(body)
        composition: dict[str, int] = {}
        try:
            for multiplier, part in self._split_hydrate(body):
                for symbol, count in self._parse_body(part, 0, len(part)).items():
                    composition[symbol] = composition.get(symbol, 0) + count * multiplier
        except ParseError as error:
            fixed = repair_capitalisation(body)
            if fixed:
                raise ParseError(
                    f"Element capitalization is incorrect in '{body}'. Did you mean '{fixed}'?",
                    error.position,
                    suggestion=fixed,
                ) from error
            raise
        return Formula(raw=body + charge_suffix(charge), composition=composition, charge=charge)

    def parse_species(self, text: str) -> Species:
        """Parse one term of an equation, e.g. ``2H2O(l)`` or ``3Fe^3+``."""
        raw = normalize_input(text).replace(" ", "")
        if not raw:
            raise ParseError("Empty term — check for a stray '+'.")
        body, state = split_state(raw)
        if state is None and (bad := re.search(r"\(([A-Za-z]{1,3})\)$", body)):
            raise ParseError(
                f"'{bad.group(1)}' is not a physical state. Use (s), (l), (g) or (aq).",
                suggestion=None,
            )
        match = re.match(r"^(\d+)(?=[A-Za-z(\[{])", body)
        coefficient = int(match.group(1)) if match else 1
        if coefficient == 0:
            raise ParseError("A coefficient of 0 removes the species — use 1 or more.")
        remainder = body[match.end():] if match else body
        formula = self.parse_formula(remainder)
        return Species(coefficient=coefficient, formula=formula, state=state, raw=raw)

    # --------------------------------------------------------------- equations

    def parse_equation(self, text: str) -> Equation:
        """Parse a full reaction.

        Raises:
            ParseError: If no arrow is present or either side is unreadable.
        """
        normalized = normalize_input(text)
        if not normalized:
            raise ParseError("Enter an equation, for example H2 + O2 -> H2O.")
        reversible = "<->" in normalized
        arrow = "<->" if reversible else "->"
        if arrow not in normalized:
            raise ParseError(
                "No reaction arrow found. Separate reactants and products with -> or ⇌."
            )
        if normalized.count(arrow) > 1:
            raise ParseError("An equation may only have one reaction arrow.")
        left_text, right_text = normalized.split(arrow)
        reactants = self._parse_side(left_text, "left")
        products = self._parse_side(right_text, "right")
        return Equation(
            reactants=reactants,
            products=products,
            reversible=reversible,
            raw=normalized,
        )

    def _parse_side(self, text: str, side: str) -> list[Species]:
        text = text.strip()
        if not text:
            raise ParseError(f"The {side} side of the arrow is empty.")
        return [self.parse_species(term) for term in self.split_terms(text)]

    @staticmethod
    def split_terms(side: str) -> list[str]:
        """Split one side on ``+``, without cutting a charge in half.

        ``Na+ + Cl-`` is two terms; ``Na+(aq)`` is one.
        """
        terms: list[str] = []
        current: list[str] = []
        for index, char in enumerate(side):
            if char != "+":
                current.append(char)
                continue
            rest = side[index + 1:]
            stripped = rest.lstrip()
            # A charge is always written against the formula ("Fe3+", never
            # "Fe3 +"), so a '+' with a space in front of it can only be a
            # separator — including when what follows is another '+'.
            spaced = index > 0 and side[index - 1].isspace()
            is_separator = spaced or (
                bool(stripped)
                and not _TRAILING_STATE.match(rest)
                and stripped[0] not in "+-"
                and (stripped[0].isupper() or stripped[0].isdigit() or stripped[0] in "([{")
            )
            if is_separator:
                terms.append("".join(current))
                current = []
            else:
                current.append(char)
        terms.append("".join(current))
        cleaned = [term.strip() for term in terms]
        if any(not term for term in cleaned):
            raise ParseError("Two '+' signs in a row, or a '+' with nothing after it.")
        return cleaned

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _split_charge(text: str) -> tuple[str, int]:
        """Separate a trailing charge from the formula body.

        ``n+`` written without a caret is ambiguous: in ``Cu2+`` the 2 is the
        charge, in ``NH4+`` it is a subscript. The rules applied here, in
        order, match how the notation is used in practice:

        1. ``^`` marks the charge explicitly and always wins.
        2. Sign-first (``Fe+3``, ``SO4-2``) is always a charge.
        3. ``n+`` after a lone element symbol is a charge (``Cu2+`` → Cu²⁺).
        4. ``mn+`` with two or more digits splits: the last digit is the
           charge, the rest a subscript (``SO42-`` → SO₄²⁻).
        5. A single digit otherwise stays a subscript (``NH4+`` → NH₄⁺).
        """
        if "^" in text:
            body, _, charge_text = text.rpartition("^")
            if not charge_text:
                raise ParseError("A '^' must be followed by a charge such as 2+ or -.")
            return body, ChemicalParser._read_charge(charge_text)

        sign_first = re.search(r"([+-])(\d+)$", text)
        if sign_first:
            sign = 1 if sign_first.group(1) == "+" else -1
            return text[: sign_first.start()], sign * int(sign_first.group(2))

        match = re.search(r"(\d*)([+-]+)$", text)
        if not match:
            return text, 0
        digits, signs = match.group(1), match.group(2)
        stem = text[: match.start()]
        if len(set(signs)) > 1:
            raise ParseError("Mixed '+' and '-' in one charge. Write 2+ or 2-, not both.")
        sign = 1 if signs[0] == "+" else -1
        if not digits:
            return stem, sign * len(signs)
        if len(signs) > 1:
            raise ParseError(
                f"Write this charge either as {digits}{signs[0]} or as {signs}, not both."
            )
        if re.fullmatch(r"[A-Z][a-z]?", stem) and stem in ELEMENTS:
            return stem, sign * int(digits)
        if len(digits) >= 2:
            return stem + digits[:-1], sign * int(digits[-1])
        return stem + digits, sign

    @staticmethod
    def _read_charge(text: str) -> int:
        """Read ``2+``, ``+2``, ``++`` or ``-`` as a signed integer."""
        text = text.strip()
        if not text:
            return 0
        if set(text) == {"+"}:
            return len(text)
        if set(text) == {"-"}:
            return -len(text)
        match = re.fullmatch(r"(\d+)([+-])|([+-])(\d+)", text)
        if not match:
            raise ParseError(
                f"'{text}' is not a valid charge. Write it as 2+, 3-, + or ^2-.",
            )
        magnitude = match.group(1) or match.group(4)
        sign = match.group(2) or match.group(3)
        value = int(magnitude)
        if value == 0:
            return 0
        return value if sign == "+" else -value

    @staticmethod
    def _check_brackets(text: str) -> None:
        stack: list[tuple[str, int]] = []
        for index, char in enumerate(text):
            if char in _OPEN_TO_CLOSE:
                stack.append((char, index))
            elif char in _CLOSE_TO_OPEN:
                if not stack:
                    raise ParseError(f"Closing '{char}' has no matching opening bracket.", index)
                opener, _ = stack.pop()
                if _OPEN_TO_CLOSE[opener] != char:
                    raise ParseError(f"'{opener}' is closed by '{char}'.", index)
        if stack:
            opener, index = stack[-1]
            raise ParseError(f"'{opener}' is never closed.", index)

    @staticmethod
    def _split_hydrate(text: str) -> Iterator[tuple[int, str]]:
        """Split ``CuSO4*5H2O`` into ``(1, 'CuSO4')`` and ``(5, 'H2O')``."""
        for part in text.split("*"):
            if not part:
                raise ParseError("A hydrate dot needs a formula on both sides.")
            match = re.match(r"^(\d+)", part)
            if match:
                yield int(match.group(1)), part[match.end():]
            else:
                yield 1, part

    def _parse_body(self, text: str, start: int, end: int) -> dict[str, int]:
        """Recursively read a bracket-free-or-nested formula segment."""
        composition: dict[str, int] = {}
        index = start
        while index < end:
            char = text[index]
            if char in _OPEN_TO_CLOSE:
                close = self._matching_bracket(text, index, end)
                inner = self._parse_body(text, index + 1, close)
                index, multiplier = self._read_count(text, close + 1, end)
                for symbol, count in inner.items():
                    composition[symbol] = composition.get(symbol, 0) + count * multiplier
                continue
            if char.isalpha():
                symbol, index = self._read_symbol(text, index, end)
                index, multiplier = self._read_count(text, index, end)
                composition[symbol] = composition.get(symbol, 0) + multiplier
                continue
            if char.isdigit():
                raise ParseError(
                    f"Unexpected number at position {index + 1}. "
                    "Numbers belong after an element symbol or bracket.",
                    index,
                )
            raise ParseError(f"'{char}' does not belong in a formula.", index)
        if not composition:
            raise ParseError("No elements found in this formula.")
        return composition

    @staticmethod
    def _matching_bracket(text: str, start: int, end: int) -> int:
        depth = 0
        for index in range(start, end):
            if text[index] in _OPEN_TO_CLOSE:
                depth += 1
            elif text[index] in _CLOSE_TO_OPEN:
                depth -= 1
                if depth == 0:
                    return index
        raise ParseError(f"'{text[start]}' is never closed.", start)

    @staticmethod
    def _read_symbol(text: str, index: int, end: int) -> tuple[str, int]:
        """Read one element symbol, longest match first."""
        two = text[index: index + 2]
        if len(two) == 2 and two in ELEMENTS and index + 2 <= end:
            return two, index + 2
        one = text[index]
        if one in ELEMENTS:
            return one, index + 1
        token_match = _ELEMENT_TOKEN.match(text, index)
        token = token_match.group(0) if token_match else one
        corrected = resolve_case(token) or resolve_case(token[0])
        if corrected:
            raise ParseError(
                f"'{token}' is not an element symbol. Element capitalization is incorrect — "
                f"did you mean '{corrected}'?",
                index,
                suggestion=repair_capitalisation(text),
            )
        raise ParseError(f"'{token}' is not a known element symbol.", index)

    @staticmethod
    def _read_count(text: str, index: int, end: int) -> tuple[int, int]:
        start = index
        while index < end and text[index].isdigit():
            index += 1
        if index == start:
            return index, 1
        value = int(text[start:index])
        if value == 0:
            raise ParseError("A subscript of 0 means the element is absent — remove it.", start)
        return index, value


def charge_suffix(charge: int) -> str:
    """Render a charge in canonical caret notation: ``^2-``, ``^+``, or ``""``."""
    if charge == 0:
        return ""
    sign = "+" if charge > 0 else "-"
    magnitude = abs(charge)
    return f"^{sign}" if magnitude == 1 else f"^{magnitude}{sign}"


def repair_capitalisation(text: str) -> str | None:
    """Re-case a formula whose letters are right but whose capitals are not.

    ``FE2o3`` becomes ``Fe2O3``. Returns ``None`` when no segmentation of the
    letters into real element symbols exists.
    """
    out: list[str] = []
    changed = False
    for chunk in re.findall(r"[A-Za-z]+|[^A-Za-z]+", text):
        if not chunk[0].isalpha():
            out.append(chunk)
            continue
        segmented = _segment_symbols(chunk)
        if segmented is None:
            return None
        joined = "".join(segmented)
        changed = changed or joined != chunk
        out.append(joined)
    return "".join(out) if changed else None


def _segment_symbols(letters: str) -> list[str] | None:
    """Split a letter run into element symbols, ignoring case.

    ``caco`` can be read as Ca+Co or Ca+C+O, and only one of those is a real
    compound. Ambiguity is settled by preferring the lighter elements, since
    the elements a student writes are overwhelmingly the common light ones.
    """
    candidates = _all_segmentations(letters)
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda parts: (sum(ELEMENTS[symbol].number for symbol in parts), len(parts)),
    )


def _all_segmentations(letters: str, depth: int = 0) -> list[list[str]]:
    """Every way to read a letter run as element symbols, case-insensitively."""
    if not letters:
        return [[]]
    if depth > 12:  # Long runs fall back to the greedy two-letter-first reading.
        greedy = resolve_case(letters[:2]) or resolve_case(letters[:1])
        if greedy is None:
            return []
        tails = _all_segmentations(letters[len(greedy):], depth + 1)
        return [[greedy, *tail] for tail in tails[:1]]
    found: list[list[str]] = []
    for size in (2, 1):
        if len(letters) < size:
            continue
        candidate = resolve_case(letters[:size])
        if candidate is None:
            continue
        for tail in _all_segmentations(letters[size:], depth + 1):
            found.append([candidate, *tail])
    return found


#: Shared, stateless parser instance.
parser: Final[ChemicalParser] = ChemicalParser()
