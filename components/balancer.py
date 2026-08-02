"""Balancing equations by solving the conservation matrix.

Each element contributes one linear equation, and charge contributes one
more. Writing reactants positive and products negative turns "balanced" into
"lies in the null space", which handles ionic and redox equations with the
same code path as ``H2 + O2 -> H2O``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import gcd
from typing import Final, Literal

from sympy import Matrix, Rational, lcm

from components.atom_counter import build_table, charge_of_side, is_balanced, orphan_elements
from components.parser import Equation

Status = Literal["already_balanced", "balanced", "impossible", "underdetermined", "missing_species"]

MAX_REASONABLE_COEFFICIENT: Final[int] = 10_000


@dataclass(slots=True)
class BalanceResult:
    """The outcome of trying to balance one equation."""

    status: Status
    message: str
    equation: Equation | None = None
    coefficients: list[int] = field(default_factory=list)
    original_coefficients: list[int] = field(default_factory=list)
    matrix_rows: list[tuple[str, list[int]]] = field(default_factory=list)
    solution_count: int = 0
    cross_checked: bool = False

    @property
    def succeeded(self) -> bool:
        return self.status in {"already_balanced", "balanced", "underdetermined"}

    @property
    def changes(self) -> list[tuple[str, int, int]]:
        """``(species, before, after)`` for every coefficient that moved."""
        if not self.equation:
            return []
        rows: list[tuple[str, int, int]] = []
        for species, before, after in zip(
            self.equation.species, self.original_coefficients, self.coefficients
        ):
            if before != after:
                rows.append((species.formula.display, before, after))
        return rows


class EquationBalancer:
    """Balances equations by null-space solution of the conservation matrix."""

    def build_matrix(self, equation: Equation) -> tuple[Matrix, list[str]]:
        """Build the conservation matrix and the label for each row.

        Columns follow ``equation.species`` order; reactants count positive
        and products negative, so a balanced equation sends the coefficient
        vector to zero.
        """
        species = equation.species
        split = len(equation.reactants)
        labels: list[str] = []
        rows: list[list[Rational]] = []
        for symbol in equation.elements:
            row = [
                Rational(item.formula.composition.get(symbol, 0) * (1 if index < split else -1))
                for index, item in enumerate(species)
            ]
            labels.append(symbol)
            rows.append(row)
        if equation.has_charges:
            labels.append("charge")
            rows.append(
                [
                    Rational(item.formula.charge * (1 if index < split else -1))
                    for index, item in enumerate(species)
                ]
            )
        return Matrix(rows), labels

    def balance(self, equation: Equation) -> BalanceResult:
        """Find the smallest whole-number coefficients that conserve everything.

        Args:
            equation: A parsed equation, balanced or not.

        Returns:
            A :class:`BalanceResult` describing what happened. Failure is
            reported, never raised: an unbalanceable equation is a normal
            outcome for a student's first attempt.
        """
        original = [item.coefficient for item in equation.species]
        orphans = orphan_elements(equation)
        if orphans:
            listed = ", ".join(
                f"{symbol} (only on the {side})" for symbol, side in sorted(orphans.items())
            )
            return BalanceResult(
                status="missing_species",
                message=(
                    f"These elements appear on one side only: {listed}. "
                    "No set of coefficients can fix that — a species is missing."
                ),
                original_coefficients=original,
                equation=equation,
            )

        matrix, labels = self.build_matrix(equation)
        matrix_rows = [
            (label, [int(value) for value in matrix.row(index)])
            for index, label in enumerate(labels)
        ]
        basis = matrix.nullspace()

        if not basis:
            return BalanceResult(
                status="impossible",
                message=(
                    "No whole-number coefficients can balance this reaction as written. "
                    "Check the formulas — one of them is probably not the intended compound."
                ),
                original_coefficients=original,
                matrix_rows=matrix_rows,
                equation=equation,
            )

        vector = basis[0] if len(basis) == 1 else self._pick_positive(basis)
        if vector is None:
            return BalanceResult(
                status="underdetermined",
                message=(
                    f"This equation has {len(basis)} independent balancings and no single "
                    "positive answer. Split it into separate reactions."
                ),
                original_coefficients=original,
                matrix_rows=matrix_rows,
                solution_count=len(basis),
                equation=equation,
            )

        coefficients = self._to_smallest_integers(vector)
        if coefficients is None:
            return BalanceResult(
                status="impossible",
                message=(
                    "Balancing this needs a negative coefficient, which means the reaction "
                    "cannot run in the direction written."
                ),
                original_coefficients=original,
                matrix_rows=matrix_rows,
                equation=equation,
            )
        if max(coefficients) > MAX_REASONABLE_COEFFICIENT:
            return BalanceResult(
                status="impossible",
                message=(
                    "The coefficients needed here are implausibly large, which usually means "
                    "a formula was mistyped."
                ),
                original_coefficients=original,
                matrix_rows=matrix_rows,
                equation=equation,
            )

        balanced = equation.with_coefficients(coefficients)
        status: Status = "underdetermined" if len(basis) > 1 else (
            "already_balanced" if coefficients == original else "balanced"
        )
        if status == "already_balanced":
            message = "Already balanced, and in lowest terms."
        elif status == "underdetermined":
            message = (
                f"Balanced, but {len(basis)} independent balancings exist — this is really "
                "more than one reaction written as one."
            )
        else:
            message = "Balanced."
        return BalanceResult(
            status=status,
            message=message,
            equation=balanced,
            coefficients=coefficients,
            original_coefficients=original,
            matrix_rows=matrix_rows,
            solution_count=len(basis),
            cross_checked=self._cross_check(equation, coefficients),
        )

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _to_smallest_integers(vector: Matrix) -> list[int] | None:
        """Clear denominators, then divide out the common factor."""
        values = [Rational(value) for value in vector]
        if all(value == 0 for value in values):
            return None
        multiplier = lcm([value.q for value in values])
        integers = [int(value * multiplier) for value in values]
        if all(value <= 0 for value in integers):
            integers = [-value for value in integers]
        if any(value <= 0 for value in integers):
            return None
        divisor = 0
        for value in integers:
            divisor = gcd(divisor, value)
        return [value // divisor for value in integers] if divisor > 1 else integers

    @staticmethod
    def _pick_positive(basis: list[Matrix]) -> Matrix | None:
        """Search small combinations of basis vectors for an all-positive one.

        Under-determined systems (two reactions written as one) have infinitely
        many solutions; a small search finds a usable one often enough to be
        worth doing, and returning ``None`` is a fine answer when it does not.
        """
        weights = (-2, -1, 0, 1, 2, 3)
        for combination in _weight_grid(weights, len(basis)):
            if not any(combination):
                continue
            candidate = sum(
                (weight * vector for weight, vector in zip(combination, basis)),
                Matrix([0] * basis[0].rows),
            )
            values = list(candidate)
            if all(value > 0 for value in values) or all(value < 0 for value in values):
                return candidate
        return None

    @staticmethod
    def _cross_check(equation: Equation, coefficients: list[int]) -> bool:
        """Confirm the answer really does conserve everything."""
        candidate = equation.with_coefficients(coefficients)
        return is_balanced(candidate)


def _weight_grid(weights: tuple[int, ...], depth: int) -> list[tuple[int, ...]]:
    """Cartesian product of ``weights``, shallowest combinations first."""
    if depth <= 0:
        return [()]
    grid: list[tuple[int, ...]] = [()]
    for _ in range(min(depth, 4)):
        grid = [(*prefix, weight) for prefix in grid for weight in weights]
    return sorted(grid, key=lambda combo: sum(abs(value) for value in combo))


def imbalance_report(equation: Equation) -> list[str]:
    """Per-element sentences describing what is wrong, in student language."""
    lines: list[str] = []
    for row in build_table(equation):
        if row.balanced:
            lines.append(f"{row.element}: correct ({row.left} on each side).")
        else:
            lines.append(
                f"{row.element}: incorrect — {row.left} on the left, {row.right} on the right."
            )
    left_charge = charge_of_side(equation.reactants)
    right_charge = charge_of_side(equation.products)
    if left_charge != right_charge:
        lines.append(
            f"Charge: incorrect — {left_charge:+d} on the left, {right_charge:+d} on the right."
        )
    elif equation.has_charges:
        lines.append(f"Charge: correct ({left_charge:+d} on each side).")
    return lines


#: Shared balancer instance.
balancer: Final[EquationBalancer] = EquationBalancer()
