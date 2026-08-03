"""Tenglamaning har ikki tomonidagi atom va zaryadni sanaydi.

Tekshirgichning muvozanat haqidagi barcha xulosasi shu moduldan kelib
chiqadi, shuning uchun sanash baho berishdan alohida saqlangan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from components.parser import Equation, Species
from data.elements import ELEMENTS


@dataclass(frozen=True, slots=True)
class AtomRow:
    """Bitta elementning strelka bo'ylab hisobi."""

    element: str
    left: int
    right: int

    @property
    def difference(self) -> int:
        """O'ng minus chap: musbat bo'lsa, mahsulotlar tomonida ortiqcha bor."""
        return self.right - self.left

    @property
    def balanced(self) -> bool:
        return self.left == self.right

    @property
    def verdict(self) -> str:
        return "to'g'ri" if self.balanced else "noto'g'ri"

    @property
    def short_note(self) -> str:
        if self.balanced:
            return "muvozanatda"
        surplus_side = "o'ngda" if self.difference > 0 else "chapda"
        return f"{surplus_side} {abs(self.difference)} ta ortiq"


def count_side(species: Iterable[Species]) -> dict[str, int]:
    """Bir tomondagi har bir element atomlari yig'indisi, koeffitsiyentlar bilan."""
    totals: dict[str, int] = {}
    for item in species:
        for symbol, count in item.atoms().items():
            totals[symbol] = totals.get(symbol, 0) + count
    return totals


def charge_of_side(species: Iterable[Species]) -> int:
    """Bir tomondagi umumiy zaryad, koeffitsiyentlar bilan."""
    return sum(item.total_charge for item in species)


def build_table(equation: Equation) -> list[AtomRow]:
    """Har bir element uchun bitta :class:`AtomRow`, tartib raqami bo'yicha."""
    left = count_side(equation.reactants)
    right = count_side(equation.products)
    return [
        AtomRow(element=symbol, left=left.get(symbol, 0), right=right.get(symbol, 0))
        for symbol in sorted(set(left) | set(right), key=lambda s: ELEMENTS[s].number)
    ]


def unbalanced_rows(equation: Equation) -> list[AtomRow]:
    """Faqat o'quvchi hali to'g'rilashi kerak bo'lgan qatorlar."""
    return [row for row in build_table(equation) if not row.balanced]


def is_balanced(equation: Equation) -> bool:
    """Har bir element va umumiy zaryad ikkala tomonda mos kelsa True."""
    if any(not row.balanced for row in build_table(equation)):
        return False
    return charge_of_side(equation.reactants) == charge_of_side(equation.products)


def side_mass(species: Iterable[Species]) -> float:
    """Bir tomondagi umumiy massa, g/mol — massa saqlanishini tekshirish."""
    return sum(item.formula.molar_mass * item.coefficient for item in species)


def mass_balance(equation: Equation) -> tuple[float, float]:
    """``(reagentlar massasi, mahsulotlar massasi)``, g/mol."""
    return side_mass(equation.reactants), side_mass(equation.products)


def orphan_elements(equation: Equation) -> dict[str, str]:
    """Faqat bir tomonda uchraydigan elementlar va ular turgan tomon.

    Bunday elementni faqat koeffitsiyent bilan tenglashtirib bo'lmaydi — bu
    modda tushib qolganini bildiradi, ya'ni noto'g'ri koeffitsiyentdan boshqa xato.
    """
    left = count_side(equation.reactants)
    right = count_side(equation.products)
    orphans: dict[str, str] = {}
    for symbol in set(left) | set(right):
        if symbol not in right:
            orphans[symbol] = "left"
        elif symbol not in left:
            orphans[symbol] = "right"
    return orphans
