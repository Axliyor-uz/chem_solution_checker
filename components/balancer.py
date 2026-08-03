"""Tenglamalarni saqlanish matritsasini yechish orqali muvozanatlaydi.

Har bir element bitta chiziqli tenglama beradi, zaryad esa yana bittasini.
Reagentlarni musbat, mahsulotlarni manfiy yozish "muvozanatlangan" degan
shartni "matritsaning nol fazosida yotadi" degan shartga aylantiradi — shu
sababli ionli va redoks tenglamalar ``H2 + O2 -> H2O`` bilan bir xil yo'ldan
o'tadi.
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

#: Ichki "left"/"right" qiymatlarining o'quvchi ko'radigan nomlari.
SIDE_NAMES: Final[dict[str, str]] = {"left": "chapda", "right": "o'ngda"}


@dataclass(slots=True)
class BalanceResult:
    """Bitta tenglamani muvozanatlashga urinish natijasi."""

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
        """O'zgargan har bir koeffitsiyent uchun ``(modda, oldin, keyin)``."""
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
    """Saqlanish matritsasining nol fazosi orqali tenglamalarni muvozanatlaydi."""

    def build_matrix(self, equation: Equation) -> tuple[Matrix, list[str]]:
        """Saqlanish matritsasini va har bir qator nomini quradi.

        Ustunlar ``equation.species`` tartibida; reagentlar musbat,
        mahsulotlar manfiy sanaladi, shuning uchun muvozanatlangan tenglamada
        koeffitsiyentlar vektori nolga aylanadi.
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
            labels.append("zaryad")
            rows.append(
                [
                    Rational(item.formula.charge * (1 if index < split else -1))
                    for index, item in enumerate(species)
                ]
            )
        return Matrix(rows), labels

    def balance(self, equation: Equation) -> BalanceResult:
        """Hamma narsani saqlaydigan eng kichik butun koeffitsiyentlarni topadi.

        Args:
            equation: O'qilgan tenglama — muvozanatlangan yoki yo'q.

        Returns:
            Nima bo'lganini tavsiflovchi :class:`BalanceResult`. Muvaffaqiyatsizlik
            xato sifatida ko'tarilmaydi, balki qaytariladi: muvozanatlanmaydigan
            tenglama o'quvchining birinchi urinishi uchun odatiy hol.
        """
        original = [item.coefficient for item in equation.species]
        orphans = orphan_elements(equation)
        if orphans:
            listed = ", ".join(
                f"{symbol} (faqat {SIDE_NAMES[side]})" for symbol, side in sorted(orphans.items())
            )
            return BalanceResult(
                status="missing_species",
                message=(
                    f"Bu elementlar faqat bir tomonda uchraydi: {listed}. "
                    "Buni hech qanday koeffitsiyent to'g'rilay olmaydi — modda tushib qolgan."
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
                    "Bu reaksiyani yozilgan holida hech qanday butun koeffitsiyent muvozanatlay olmaydi. "
                    "Formulalarni tekshiring — ulardan biri, ehtimol, siz nazarda tutgan birikma emas."
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
                    f"Bu tenglamada {len(basis)} ta mustaqil muvozanatlash bor va yagona "
                    "musbat javob yo'q. Uni alohida reaksiyalarga ajrating."
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
                    "Buni muvozanatlash uchun manfiy koeffitsiyent kerak, ya'ni reaksiya "
                    "yozilgan yo'nalishda bora olmaydi."
                ),
                original_coefficients=original,
                matrix_rows=matrix_rows,
                equation=equation,
            )
        if max(coefficients) > MAX_REASONABLE_COEFFICIENT:
            return BalanceResult(
                status="impossible",
                message=(
                    "Bu yerda kerak bo'ladigan koeffitsiyentlar haqiqatga to'g'ri kelmaydigan darajada "
                    "katta — odatda bu formulada xato yozilganini bildiradi."
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
            message = "Allaqachon muvozanatlangan va eng kichik holatda."
        elif status == "underdetermined":
            message = (
                f"Muvozanatlandi, lekin {len(basis)} ta mustaqil muvozanatlash mavjud — bu aslida "
                "bitta qatorga yozilgan bir nechta reaksiya."
            )
        else:
            message = "Muvozanatlandi."
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

    # ------------------------------------------------------------- yordamchilar

    @staticmethod
    def _to_smallest_integers(vector: Matrix) -> list[int] | None:
        """Maxrajlarni yo'qotadi, so'ng umumiy bo'luvchiga qisqartiradi."""
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
        """Bazis vektorlarning kichik kombinatsiyalari orasidan butunlay musbatini qidiradi.

        Aniqlanmagan sistemalarda (bitta qatorga yozilgan ikkita reaksiya)
        yechimlar cheksiz ko'p; kichik qidiruv yaroqli yechimni yetarlicha tez-tez
        topadi, topilmasa ``None`` qaytarish ham to'g'ri javob.
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
        """Javob haqiqatan ham hamma narsani saqlashini tasdiqlaydi."""
        candidate = equation.with_coefficients(coefficients)
        return is_balanced(candidate)


def _weight_grid(weights: tuple[int, ...], depth: int) -> list[tuple[int, ...]]:
    """``weights`` ning dekart ko'paytmasi, eng sodda kombinatsiyalar birinchi."""
    if depth <= 0:
        return [()]
    grid: list[tuple[int, ...]] = [()]
    for _ in range(min(depth, 4)):
        grid = [(*prefix, weight) for prefix in grid for weight in weights]
    return sorted(grid, key=lambda combo: sum(abs(value) for value in combo))


def imbalance_report(equation: Equation) -> list[str]:
    """Har bir element uchun nima xato ekanini o'quvchi tilida tushuntiruvchi jumlalar."""
    lines: list[str] = []
    for row in build_table(equation):
        if row.balanced:
            lines.append(f"{row.element}: to'g'ri (har ikki tomonda {row.left} ta).")
        else:
            lines.append(
                f"{row.element}: noto'g'ri — chapda {row.left}, o'ngda {row.right}."
            )
    left_charge = charge_of_side(equation.reactants)
    right_charge = charge_of_side(equation.products)
    if left_charge != right_charge:
        lines.append(
            f"Zaryad: noto'g'ri — chapda {left_charge:+d}, o'ngda {right_charge:+d}."
        )
    elif equation.has_charges:
        lines.append(f"Zaryad: to'g'ri (har ikki tomonda {left_charge:+d}).")
    return lines


#: Umumiy muvozanatlagich namunasi.
balancer: Final[EquationBalancer] = EquationBalancer()
