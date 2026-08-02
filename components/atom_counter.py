"""Counting atoms and charge on each side of an equation.

Everything the checker says about balance ultimately comes from this module,
so the counting is kept separate from the judging.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from components.parser import Equation, Species
from data.elements import ELEMENTS



@dataclass(frozen=True, slots=True)
class AtomRow:
    """One element's tally across the arrow."""

    element: str
    left: int
    right: int

    @property
    def difference(self) -> int:
        """Right minus left: positive means the product side has a surplus."""
        return self.right - self.left

    @property
    def balanced(self) -> bool:
        return self.left == self.right

    @property
    def verdict(self) -> str:
        return "correct" if self.balanced else "incorrect"

    @property
    def short_note(self) -> str:
        """A three-word verdict for the explanation column."""
        if self.balanced:
            return "mos keladi"
        if self.left > self.right:
            return f"chapda {self.left - self.right} ta ortiqcha"
        return f"o'ngda {self.right - self.left} ta ortiqcha"


def count_side(species: Iterable[Species]) -> dict[str, int]:
    """Total atoms of each element on one side, coefficients included."""
    totals: dict[str, int] = {}
    for item in species:
        for symbol, count in item.atoms().items():
            totals[symbol] = totals.get(symbol, 0) + count
    return totals


def charge_of_side(species: Iterable[Species]) -> int:
    """Net charge on one side, coefficients included."""
    return sum(item.total_charge for item in species)


def build_table(equation: Equation) -> list[AtomRow]:
    """One :class:`AtomRow` per element, ordered by atomic number."""
    left = count_side(equation.reactants)
    right = count_side(equation.products)
    return [
        AtomRow(element=symbol, left=left.get(symbol, 0), right=right.get(symbol, 0))
        for symbol in sorted(set(left) | set(right), key=lambda s: ELEMENTS[s].number)
    ]


def unbalanced_rows(equation: Equation) -> list[AtomRow]:
    """Only the rows a student still has to fix."""
    return [row for row in build_table(equation) if not row.balanced]


def is_balanced(equation: Equation) -> bool:
    """True when every element and the net charge match on both sides."""
    if any(not row.balanced for row in build_table(equation)):
        return False
    return charge_of_side(equation.reactants) == charge_of_side(equation.products)


def side_mass(species: Iterable[Species]) -> float:
    """Total mass in g/mol on one side — the mass-conservation check."""
    return sum(item.formula.molar_mass * item.coefficient for item in species)


def mass_balance(equation: Equation) -> tuple[float, float]:
    """``(reactant mass, product mass)`` in g/mol."""
    return side_mass(equation.reactants), side_mass(equation.products)


def orphan_elements(equation: Equation) -> dict[str, str]:
    """Elements appearing on only one side, mapped to the side they are on.

    An orphan can never be balanced by coefficients alone — it means a
    species is missing, which is a different mistake from a wrong coefficient.
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
