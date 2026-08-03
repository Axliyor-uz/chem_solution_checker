"""Yozilgan matnni kimyoviy obyektlarga aylantiradi.

Bu yerdagi grammatika o'quvchilar tenglamani amalda qanday yozsa, shunga
ataylab moslashuvchan — ``2H2O(l)``, ``SO4^2-``, ``SO42-``, ``Ca(OH)2``,
``CuSO4*5H2O`` — ammo chinakam ikkima'noli yozuvni baribir rad etadi. Har bir
xatolik o'quvchi tushunadigan xabar bilan :class:`ParseError` ni ko'taradi.
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
    """Kiritilgan matnni kimyo sifatida o'qib bo'lmaganda ko'tariladi.

    Args:
        message: Nima noto'g'ri ekani, sodda tilda.
        position: Xato tokendagi belgi o'rni, agar ma'lum bo'lsa.
        suggestion: O'quvchi qabul qilishi mumkin bo'lgan to'g'rilangan variant.
    """

    def __init__(self, message: str, position: int | None = None, suggestion: str | None = None):
        super().__init__(message)
        self.message = message
        self.position = position
        self.suggestion = suggestion


@dataclass(frozen=True, slots=True)
class Formula:
    """Bitta kimyoviy formula: tarkibi va umumiy zaryadi."""

    raw: str
    composition: dict[str, int]
    charge: int = 0

    @property
    def display(self) -> str:
        """Pastki va yuqori indekslar bilan terilgan formula."""
        return to_display(self.raw)

    @property
    def molar_mass(self) -> float:
        """Molyar massa, g/mol — standart atom massalari yig'indisi."""
        return sum(ELEMENTS[symbol].mass * count for symbol, count in self.composition.items())

    @property
    def atom_count(self) -> int:
        return sum(self.composition.values())

    @property
    def is_single_element(self) -> bool:
        """``Fe``, ``O2`` yoki ``S8`` kabi erkin elementlar uchun True."""
        return len(self.composition) == 1 and self.charge == 0

    def mass_contributions(self) -> list[tuple[str, int, float, float]]:
        """Har bir element uchun ``(belgi, soni, ulush, foiz)`` taqsimoti."""
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
    """Formula tenglamadagi ko'rinishida: koeffitsiyent, formula, holat."""

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
        """Koeffitsiyentga ko'paytirilgan tarkib."""
        return {s: c * self.coefficient for s, c in self.formula.composition.items()}

    @property
    def total_charge(self) -> int:
        return self.formula.charge * self.coefficient

    def with_coefficient(self, coefficient: int) -> "Species":
        return Species(coefficient, self.formula, self.state, self.raw)


@dataclass(slots=True)
class Equation:
    """To'liq reaksiya — ikkala tomoni ham tahlil qilingan."""

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
        """Ishtirok etayotgan barcha elementlar, tartib raqami bo'yicha."""
        found = {symbol for s in self.species for symbol in s.formula.composition}
        return sorted(found, key=lambda symbol: ELEMENTS[symbol].number)

    @property
    def has_charges(self) -> bool:
        return any(s.formula.charge for s in self.species)

    def with_coefficients(self, coefficients: list[int]) -> "Equation":
        """Yangi koeffitsiyentli nusxa qaytaradi: avval reagentlar, keyin mahsulotlar."""
        expected = len(self.species)
        if len(coefficients) != expected:
            raise ValueError(f"{expected} ta koeffitsiyent kutilgandi, {len(coefficients)} ta keldi.")
        split = len(self.reactants)
        return Equation(
            reactants=[s.with_coefficient(c) for s, c in zip(self.reactants, coefficients[:split])],
            products=[s.with_coefficient(c) for s, c in zip(self.products, coefficients[split:])],
            reversible=self.reversible,
            raw=self.raw,
            conditions=dict(self.conditions),
        )


class ChemicalParser:
    """Matndan formula, modda va tenglamalarni o'qiydi."""

    # ---------------------------------------------------------------- formulas

    def parse_formula(self, text: str) -> Formula:
        """Formulani o'qiydi; zaryad yoki gidrat nuqtasi ham bo'lishi mumkin.

        Args:
            text: ``Ca(OH)2``, ``SO4^2-`` yoki ``CuSO4*5H2O`` kabi matn.

        Returns:
            O'qilgan :class:`Formula`.

        Raises:
            ParseError: Matn o'qib bo'ladigan formula bo'lmasa.
        """
        raw = normalize_input(text).replace(" ", "")
        if not raw:
            raise ParseError("Avval formula kiriting.")
        body, charge = self._split_charge(raw)
        if not body:
            raise ParseError("Zaryaddan oldin formula turishi kerak.")
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
                    f"'{body}' da element belgilari katta-kichik harfda noto'g'ri yozilgan. "
                    f"'{fixed}' ni nazarda tutdingizmi?",
                    error.position,
                    suggestion=fixed,
                ) from error
            raise
        return Formula(raw=body + charge_suffix(charge), composition=composition, charge=charge)

    def parse_species(self, text: str) -> Species:
        """Tenglamaning bitta hadini o'qiydi, masalan ``2H2O(l)`` yoki ``3Fe^3+``."""
        raw = normalize_input(text).replace(" ", "")
        if not raw:
            raise ParseError("Bo'sh had — ortiqcha '+' bor-yo'qligini tekshiring.")
        body, state = split_state(raw)
        if state is None and (bad := re.search(r"\(([A-Za-z]{1,3})\)$", body)):
            raise ParseError(
                f"'{bad.group(1)}' fizik holat emas. (s), (l), (g) yoki (aq) dan foydalaning.",
                suggestion=None,
            )
        match = re.match(r"^(\d+)(?=[A-Za-z(\[{])", body)
        coefficient = int(match.group(1)) if match else 1
        if coefficient == 0:
            raise ParseError("0 koeffitsiyenti moddani yo'q qiladi — 1 yoki undan katta son yozing.")
        remainder = body[match.end():] if match else body
        formula = self.parse_formula(remainder)
        return Species(coefficient=coefficient, formula=formula, state=state, raw=raw)

    # --------------------------------------------------------------- equations

    def parse_equation(self, text: str) -> Equation:
        """To'liq reaksiyani o'qiydi.

        Raises:
            ParseError: Strelka bo'lmasa yoki biror tomonini o'qib bo'lmasa.
        """
        normalized = normalize_input(text)
        if not normalized:
            raise ParseError("Tenglama kiriting, masalan H2 + O2 -> H2O.")
        reversible = "<->" in normalized
        arrow = "<->" if reversible else "->"
        if arrow not in normalized:
            raise ParseError(
                "Reaksiya strelkasi topilmadi. Reagentlar va mahsulotlarni -> yoki ⇌ bilan ajrating."
            )
        if normalized.count(arrow) > 1:
            raise ParseError("Tenglamada faqat bitta reaksiya strelkasi bo'lishi mumkin.")
        left_text, right_text = normalized.split(arrow)
        reactants = self._parse_side(left_text, "chap")
        products = self._parse_side(right_text, "o'ng")
        return Equation(
            reactants=reactants,
            products=products,
            reversible=reversible,
            raw=normalized,
        )

    def _parse_side(self, text: str, side: str) -> list[Species]:
        text = text.strip()
        if not text:
            raise ParseError(f"Strelkaning {side} tomoni bo'sh.")
        return [self.parse_species(term) for term in self.split_terms(text)]

    @staticmethod
    def split_terms(side: str) -> list[str]:
        """Bir tomonni ``+`` bo'yicha ajratadi, zaryadni ikkiga bo'lib yubormay.

        ``Na+ + Cl-`` ikkita had; ``Na+(aq)`` esa bitta.
        """
        terms: list[str] = []
        current: list[str] = []
        for index, char in enumerate(side):
            if char != "+":
                current.append(char)
                continue
            rest = side[index + 1:]
            stripped = rest.lstrip()
            # Zaryad doim formulaga yopishib yoziladi ("Fe3+", hech qachon
            # "Fe3 +" emas), shuning uchun oldida bo'sh joy turgan '+' faqat
            # ajratgich bo'la oladi — undan keyin yana '+' kelsa ham.
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
            raise ParseError("Ketma-ket ikkita '+' belgisi yoki oxirida yolg'iz qolgan '+'.")
        return cleaned

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _split_charge(text: str) -> tuple[str, int]:
        """Oxiridagi zaryadni formula tanasidan ajratadi.

        Ustki belgisiz yozilgan ``n+`` ikkima'noli: ``Cu2+`` da 2 — zaryad,
        ``NH4+`` da esa pastki indeks. Quyidagi qoidalar shu tartibda
        qo'llanadi va yozuvning amaldagi ishlatilishiga mos keladi:

        1. ``^`` zaryadni aniq belgilaydi va doim ustun turadi.
        2. Avval ishora kelsa (``Fe+3``, ``SO4-2``) — bu doim zaryad.
        3. Yolg'iz element belgisidan keyingi ``n+`` — zaryad (``Cu2+`` → Cu²⁺).
        4. Ikki va undan ortiq raqamli ``mn+`` bo'linadi: oxirgi raqam zaryad,
           qolgani pastki indeks (``SO42-`` → SO₄²⁻).
        5. Aks holda bitta raqam pastki indeks bo'lib qoladi (``NH4+`` → NH₄⁺).
        """
        if "^" in text:
            body, _, charge_text = text.rpartition("^")
            if not charge_text:
                raise ParseError("'^' dan keyin zaryad kelishi kerak, masalan 2+ yoki -.")
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
            raise ParseError("Bitta zaryadda '+' va '-' aralashgan. 2+ yoki 2- deb yozing, ikkalasini emas.")
        sign = 1 if signs[0] == "+" else -1
        if not digits:
            return stem, sign * len(signs)
        if len(signs) > 1:
            raise ParseError(
                f"Bu zaryadni yo {digits}{signs[0]} deb, yo {signs} deb yozing — ikkalasini birga emas."
            )
        if re.fullmatch(r"[A-Z][a-z]?", stem) and stem in ELEMENTS:
            return stem, sign * int(digits)
        if len(digits) >= 2:
            return stem + digits[:-1], sign * int(digits[-1])
        return stem + digits, sign

    @staticmethod
    def _read_charge(text: str) -> int:
        """``2+``, ``+2``, ``++`` yoki ``-`` ni ishorali butun son sifatida o'qiydi."""
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
                f"'{text}' to'g'ri zaryad emas. Uni 2+, 3-, + yoki ^2- ko'rinishida yozing.",
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
                    raise ParseError(f"Yopuvchi '{char}' uchun ochuvchi qavs yo'q.", index)
                opener, _ = stack.pop()
                if _OPEN_TO_CLOSE[opener] != char:
                    raise ParseError(f"'{opener}' qavsi '{char}' bilan yopilgan.", index)
        if stack:
            opener, index = stack[-1]
            raise ParseError(f"'{opener}' qavsi yopilmagan.", index)

    @staticmethod
    def _split_hydrate(text: str) -> Iterator[tuple[int, str]]:
        """``CuSO4*5H2O`` ni ``(1, 'CuSO4')`` va ``(5, 'H2O')`` ga ajratadi."""
        for part in text.split("*"):
            if not part:
                raise ParseError("Gidrat nuqtasining ikkala tomonida ham formula bo'lishi kerak.")
            match = re.match(r"^(\d+)", part)
            if match:
                yield int(match.group(1)), part[match.end():]
            else:
                yield 1, part

    def _parse_body(self, text: str, start: int, end: int) -> dict[str, int]:
        """Qavssiz yoki ichma-ich qavsli formula bo'lagini rekursiv o'qiydi."""
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
                    f"{index + 1}-o'rinda kutilmagan raqam. "
                    "Raqamlar element belgisidan yoki qavsdan keyin keladi.",
                    index,
                )
            raise ParseError(f"'{char}' formulada ishlatilmaydi.", index)
        if not composition:
            raise ParseError("Bu formulada element topilmadi.")
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
        raise ParseError(f"'{text[start]}' qavsi yopilmagan.", start)

    @staticmethod
    def _read_symbol(text: str, index: int, end: int) -> tuple[str, int]:
        """Bitta element belgisini o'qiydi, avval eng uzun moslikni sinaydi."""
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
                f"'{token}' element belgisi emas. Katta-kichik harf noto'g'ri — "
                f"'{corrected}' ni nazarda tutdingizmi?",
                index,
                suggestion=repair_capitalisation(text),
            )
        raise ParseError(f"'{token}' tanish element belgisi emas.", index)

    @staticmethod
    def _read_count(text: str, index: int, end: int) -> tuple[int, int]:
        start = index
        while index < end and text[index].isdigit():
            index += 1
        if index == start:
            return index, 1
        value = int(text[start:index])
        if value == 0:
            raise ParseError("0 pastki indeksi element yo'q degani — uni olib tashlang.", start)
        return index, value


def charge_suffix(charge: int) -> str:
    """Zaryadni kanonik ``^`` yozuvida qaytaradi: ``^2-``, ``^+`` yoki ``""``."""
    if charge == 0:
        return ""
    sign = "+" if charge > 0 else "-"
    magnitude = abs(charge)
    return f"^{sign}" if magnitude == 1 else f"^{magnitude}{sign}"


def repair_capitalisation(text: str) -> str | None:
    """Harflari to'g'ri, lekin katta-kichikligi noto'g'ri formulani to'g'rilaydi.

    ``FE2o3`` → ``Fe2O3``. Harflarni haqiqiy element belgilariga bo'lishning
    imkoni bo'lmasa ``None`` qaytaradi.
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
    """Harflar ketma-ketligini element belgilariga ajratadi, harf kattaligiga qaramay.

    ``caco`` ni Ca+Co yoki Ca+C+O deb o'qish mumkin, ammo faqat bittasi haqiqiy
    birikma. Ikkima'nolik yengilroq elementlar foydasiga hal qilinadi, chunki
    o'quvchi yozadigan elementlar deyarli har doim keng tarqalgan yengil elementlar.
    """
    candidates = _all_segmentations(letters)
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda parts: (sum(ELEMENTS[symbol].number for symbol in parts), len(parts)),
    )


def _all_segmentations(letters: str, depth: int = 0) -> list[list[str]]:
    """Harflar ketma-ketligini element belgilari sifatida o'qishning barcha variantlari."""
    if not letters:
        return [[]]
    if depth > 12:  # Uzun ketma-ketliklar uchun avval ikki harfli ochko'z o'qishga o'tiladi.
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


#: Umumiy, holatsiz parser namunasi.
parser: Final[ChemicalParser] = ChemicalParser()
