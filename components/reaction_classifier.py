"""Naming the reaction type, and saying what the evidence was.

A reaction can honestly belong to several families at once — a neutralisation
is also a double displacement — so this returns a ranked list rather than one
label, and each entry carries the observation that produced it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from components.parser import Equation, Species
from data.elements import ELEMENTS

_METAL_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "alkali metal", "alkaline earth metal", "transition metal",
        "post-transition metal", "lanthanide", "actinide",
    }
)
#: Acids students meet before they meet organic chemistry.
_KNOWN_ACIDS: Final[frozenset[str]] = frozenset(
    {"HCl", "HBr", "HI", "HF", "H2SO4", "HNO3", "H3PO4", "H2CO3", "CH3COOH", "HClO4", "H2SO3"}
)
_KNOWN_BASES: Final[frozenset[str]] = frozenset(
    {"NaOH", "KOH", "LiOH", "Ca(OH)2", "Ba(OH)2", "Mg(OH)2", "NH3", "NH4OH", "Al(OH)3"}
)
_COMMON_GASES: Final[frozenset[str]] = frozenset({"H2", "O2", "N2", "CO2", "SO2", "NH3", "Cl2", "H2S", "NO2"})


@dataclass(frozen=True, slots=True)
class ReactionType:
    """One classification, with the reason it was assigned."""

    name: str
    evidence: str
    confidence: float

    @property
    def confidence_label(self) -> str:
        if self.confidence > 0.8:
            return "Katta ehtimol bilan"
        if self.confidence > 0.5:
            return "Ehtimoli bor"
        return "Mumkin"


def is_metal(symbol: str) -> bool:
    element = ELEMENTS.get(symbol)
    return bool(element and element.category in _METAL_CATEGORIES)


def is_acid(species: Species) -> bool:
    """Recognise an acid from its formula, Arrhenius style."""
    raw = species.formula.raw
    if raw in _KNOWN_ACIDS:
        return True
    composition = species.formula.composition
    starts_with_hydrogen = bool(re.match(r"^H\d*[A-Z(]", raw))
    return starts_with_hydrogen and "H" in composition and not any(
        is_metal(symbol) for symbol in composition
    )


def is_base(species: Species) -> bool:
    """Recognise a hydroxide base or ammonia."""
    raw = species.formula.raw
    if raw in _KNOWN_BASES:
        return True
    composition = species.formula.composition
    has_hydroxide = "OH" in raw and composition.get("O", 0) >= 1 and composition.get("H", 0) >= 1
    return has_hydroxide and any(is_metal(symbol) for symbol in composition)


def is_hydrocarbon_like(species: Species) -> bool:
    """Carbon and hydrogen, optionally oxygen — the things that burn."""
    composition = species.formula.composition
    return set(composition) <= {"C", "H", "O"} and "C" in composition and "H" in composition


def is_water(species: Species) -> bool:
    return species.formula.composition == {"H": 2, "O": 1}


def classify(equation: Equation) -> list[ReactionType]:
    """Rank the reaction families this equation belongs to.

    Args:
        equation: A parsed equation; balancing is not required.

    Returns:
        Classifications ordered by confidence, most confident first. An
        empty list means nothing recognisable matched.
    """
    found: list[ReactionType] = []
    reactants, products = equation.reactants, equation.products
    free_left = [s for s in reactants if s.formula.is_single_element]
    free_right = [s for s in products if s.formula.is_single_element]

    if len(products) == 1 and len(reactants) >= 2:
        found.append(
            ReactionType(
                name="Birlashish",
                evidence=f"{len(reactants)} ta reaktiv birlashib, bitta {products[0].formula.display} mahsulotini hosil qiladi.",
                confidence=0.95,
            )
        )
    if len(reactants) == 1 and len(products) >= 2:
        found.append(
            ReactionType(
                name="Parchalanish",
                evidence=f"{reactants[0].formula.display} parchalanib, {len(products)} ta mahsulot hosil qiladi.",
                confidence=0.95,
            )
        )

    oxygen_reactant = any(s.formula.composition == {"O": 2} for s in reactants)
    fuel = [s for s in reactants if is_hydrocarbon_like(s)]
    makes_co2 = any(s.formula.composition == {"C": 1, "O": 2} for s in products)
    makes_water = any(is_water(s) for s in products)
    if oxygen_reactant and fuel and (makes_co2 or makes_water):
        found.append(
            ReactionType(
                "Yonish",
                f"{fuel[0].formula.display} O₂ da yonib "
                f"{'CO₂ va H₂O' if makes_co2 and makes_water else 'oksidlar'} hosil qiladi.",
                0.95,
            )
        )
    elif oxygen_reactant and len(products) == 1:
        found.append(
            ReactionType("Yonish", "Element O₂ da yonib, o'z oksidini hosil qiladi.", 0.7)
        )

    acids = [s for s in reactants if is_acid(s)]
    bases = [s for s in reactants if is_base(s)]
    if acids and bases:
        confidence = 0.95 if makes_water else 0.7
        found.append(
            ReactionType(
                "Neytrallanish (kislota-asos)",
                f"{acids[0].formula.display} {bases[0].formula.display} bilan reaksiyaga kirishib"
                + (" tuz va suv hosil qiladi." if makes_water else "."),
                confidence,
            )
        )
    elif acids and any(is_metal(sym) for s in reactants for sym in s.formula.composition
                       if s.formula.is_single_element):
        found.append(
            ReactionType(
                "Kislota-metall reaksiyasi",
                f"{acids[0].formula.display} erkin metall bilan reaksiyaga kirishib, H₂ ajratib chiqaradi.",
                0.8,
            )
        )

    if len(free_left) == 1 and len(free_right) == 1 and len(reactants) == 2 == len(products):
        found.append(
            ReactionType(
                "O'rin olish",
                f"Birikmada {free_left[0].formula.display} ning o'rnini "
                f"{free_right[0].formula.display} egallaydi.",
                0.9,
            )
        )
    elif (
        len(reactants) == 2 == len(products)
        and not free_left
        and not free_right
        and _partners_swap(equation)
    ):
        found.append(
            ReactionType(
                "Ikki tomonlama o'rin olish",
                "Ikkita birikma hamkorlarini o'zaro almashadi.",
                0.85 if not (acids and bases) else 0.6,
            )
        )

    precipitate = [s for s in products if s.state == "s"]
    if precipitate and any(s.state == "aq" for s in reactants):
        found.append(
            ReactionType(
                "Cho'kma tushishi",
                f"{precipitate[0].formula.display} eritmadan qattiq modda sifatida ajralib chiqadi.",
                0.9,
            )
        )
    gases = [s for s in products if s.state == "g" or s.formula.raw in _COMMON_GASES]
    if gases and not (oxygen_reactant and fuel):
        found.append(
            ReactionType(
                "Gaz ajralishi",
                f"{gases[0].formula.display} gaz sifatida ajralib chiqadi.",
                0.75 if gases[0].state == "g" else 0.5,
            )
        )

    redox = _redox_evidence(equation, free_left, free_right)
    if redox:
        found.append(redox)

    if equation.reversible:
        found.append(
            ReactionType(
                "Muvozanat",
                "⇌ bilan yozilgan, shuning uchun reaksiya ikkala yo'nalishda bir vaqtda boradi.",
                0.99,
            )
        )

    found.sort(key=lambda item: item.confidence, reverse=True)
    return _deduplicate(found)


def _partners_swap(equation: Equation) -> bool:
    """True when AB + CD gives AD + CB rather than something unrelated."""
    def leading(species: Species) -> str | None:
        match = re.match(r"^([A-Z][a-z]?)", species.formula.raw)
        return match.group(1) if match else None

    left_leads = {leading(s) for s in equation.reactants}
    right_leads = {leading(s) for s in equation.products}
    return bool(left_leads and left_leads == right_leads)


def _redox_evidence(
    equation: Equation, free_left: list[Species], free_right: list[Species]
) -> ReactionType | None:
    """Spot the two everyday signatures of electron transfer."""
    combined_left = {s for item in equation.reactants for s in item.formula.composition
                     if not item.formula.is_single_element}
    combined_right = {s for item in equation.products for s in item.formula.composition
                      if not item.formula.is_single_element}
    for species in free_left:
        symbol = next(iter(species.formula.composition))
        if symbol in combined_right:
            return ReactionType(
                "Oksidlanish-qaytarilish",
                f"{symbol} erkin element (oksidlanish darajasi 0) sifatida boshlanadi va oxirida birikmaga kiradi, "
                "demak elektronlar ko'chgan.",
                0.9,
            )
    for species in free_right:
        symbol = next(iter(species.formula.composition))
        if symbol in combined_left:
            return ReactionType(
                "Oksidlanish-qaytarilish",
                f"{symbol} birikmadan erkin element sifatida ajralib chiqdi, demak elektronlar ko'chgan.",
                0.9,
            )
    charges = {
        symbol: item.formula.charge
        for item in equation.species
        if len(item.formula.composition) == 1
        for symbol in item.formula.composition
    }
    for item in equation.reactants:
        if len(item.formula.composition) != 1:
            continue
        symbol = next(iter(item.formula.composition))
        for other in equation.products:
            if other.formula.composition == item.formula.composition and (
                other.formula.charge != item.formula.charge
            ):
                return ReactionType(
                    "Oksidlanish-qaytarilish",
                    f"{symbol} ning zaryadi {item.formula.charge:+d} dan "
                    f"{other.formula.charge:+d} ga o'zgaradi.",
                    0.95,
                )
    return None if not charges else None


def _deduplicate(items: list[ReactionType]) -> list[ReactionType]:
    seen: set[str] = set()
    unique: list[ReactionType] = []
    for item in items:
        if item.name in seen:
            continue
        seen.add(item.name)
        unique.append(item)
    return unique


def summarise(equation: Equation) -> str:
    """One-line answer for the "what kind of reaction is this" question."""
    types = classify(equation)
    if not types:
        return "Standart reaksiya turi aniqlanmadi."
    primary = types[0]
    if len(types) == 1:
        return f"{primary.name} reaksiyasi."
    others = ", ".join(item.name for item in types[1:])
    return f"{primary.name} reaksiyasi (shuningdek: {others})."
