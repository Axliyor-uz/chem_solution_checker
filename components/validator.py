"""Judging what a student wrote, and saying why.

The validator never answers "invalid". Every finding is an :class:`Issue`
that names the thing that is wrong, where it is, and what to do about it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final, Literal

from components.atom_counter import (
    AtomRow,
    build_table,
    charge_of_side,
    is_balanced,
    mass_balance,
    orphan_elements,
)
from components.balancer import BalanceResult, balancer
from components.parser import Equation, Formula, ParseError, Species, parser
from utils.formatting import format_number, normalize_input

Level = Literal["error", "warning", "info", "success"]

_LEVEL_RANK: Final[dict[Level, int]] = {"error": 0, "warning": 1, "success": 2, "info": 3}
_ACID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^H\d*[A-Z]")


@dataclass(frozen=True, slots=True)
class Issue:
    """One finding about the student's work."""

    level: Level
    code: str
    title: str
    detail: str = ""
    fix: str | None = None

    @property
    def icon(self) -> str:
        return {"error": "✕", "warning": "!", "info": "·", "success": "✓"}[self.level]


@dataclass(slots=True)
class ValidationReport:
    """Everything the checker concluded about one submission."""

    source: str
    equation: Equation | None = None
    issues: list[Issue] = field(default_factory=list)
    balance: BalanceResult | None = None
    rows: list[AtomRow] = field(default_factory=list)

    @property
    def parsed(self) -> bool:
        return self.equation is not None

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.level == "warning"]

    @property
    def ok(self) -> bool:
        """True when the equation parses, balances and conserves charge."""
        return self.parsed and not self.errors

    @property
    def sorted_issues(self) -> list[Issue]:
        return sorted(self.issues, key=lambda issue: _LEVEL_RANK[issue.level])

    @property
    def headline(self) -> str:
        if not self.parsed:
            return "Could not read the equation"
        if self.errors:
            return self.errors[0].title
        if self.warnings:
            return "Balanced, with notes"
        return "Balanced and correct"


class FormulaValidator:
    """Checks a single formula in isolation."""

    def validate(self, text: str) -> tuple[Formula | None, list[Issue]]:
        """Parse one formula and report anything questionable about it."""
        issues: list[Issue] = []
        try:
            formula = parser.parse_formula(text)
        except ParseError as error:
            issues.append(
                Issue(
                    level="error",
                    code="parse",
                    title="Bu formulani o'qib bo'lmadi",
                    detail=error.message,
                    fix=f"Ushbu variantni sinab ko'ring: {error.suggestion}" if error.suggestion else None,
                )
            )
            return None, issues

        if formula.charge:
            issues.append(
                Issue(
                    level="info",
                    code="charge",
                    title=f"{formula.charge:+d} zaryadli ion sifatida o'qildi",
                    detail=f"{formula.display} deb talqin qilindi.",
                )
            )
        for symbol, count in formula.composition.items():
            if count > 200:
                issues.append(
                    Issue(
                        level="warning",
                        code="large-subscript",
                        title=f"{symbol} g'ayritabiiy katta indeksga ega ({count})",
                        detail="Indeksni tekshiring — bu oddiy formulalar uchun juda katta.",
                    )
                )
        if not issues:
            issues.append(
                Issue(
                    level="success",
                    code="formula-ok",
                    title=f"{formula.display} - to'g'ri formula",
                    detail=f"Molyar massasi {format_number(formula.molar_mass, 3)} g/mol.",
                )
            )
        return formula, issues


class EquationValidator:
    """Runs the full check on a typed equation."""

    def __init__(self) -> None:
        self._formula_validator = FormulaValidator()

    def validate(self, text: str) -> ValidationReport:
        """Parse, balance and critique one equation.

        Args:
            text: Raw input, in any notation the parser accepts.

        Returns:
            A :class:`ValidationReport`. It always has at least one issue.
        """
        report = ValidationReport(source=text)
        try:
            equation = parser.parse_equation(text)
        except ParseError as error:
            report.issues.append(
                Issue(
                    level="error",
                    code="parse",
                    title="Tenglamani o'qib bo'lmadi",
                    detail=error.message,
                    fix=f"Ushbu variantni sinab ko'ring: {error.suggestion}" if error.suggestion else None,
                )
            )
            return report

        report.equation = equation
        report.rows = build_table(equation)
        report.issues.extend(self._structure_issues(text, equation))

        result = balancer.balance(equation)
        report.balance = result
        report.issues.extend(self._balance_issues(equation, result))
        report.issues.extend(self._charge_issues(equation))
        report.issues.extend(self._mass_issue(equation))
        return report

    # ------------------------------------------------------------- sub-checks

    def _structure_issues(self, text: str, equation: Equation) -> list[Issue]:
        issues: list[Issue] = []
        normalized = normalize_input(text)

        for side_name, side in (("left", equation.reactants), ("right", equation.products)):
            seen: dict[str, int] = {}
            for item in side:
                seen[item.formula.raw] = seen.get(item.formula.raw, 0) + 1
            for raw, count in seen.items():
                if count > 1:
                    issues.append(
                        Issue(
                            level="info",
                            code="repeated-species",
                            title=f"{raw} {side_name} tomonida {count} marta paydo bo'ldi",
                            detail="O'xshash hadlarni bitta koeffitsiyentga birlashtirish mumkin.",
                        )
                    )

        for term in normalized.replace("<->", "->").split("->"):
            for piece in parser.split_terms(term.strip()):
                if re.search(r"[A-Za-z0-9)\]}]\s+[A-Z(\[{]", piece.strip()):
                    issues.append(
                        Issue(
                            level="warning",
                            code="missing-plus",
                            title="Ikki formula bo'sh joy bilan bog'langanga o'xshaydi",
                            detail=f"'{piece.strip()}' bitta modda sifatida o'qildi.",
                            fix="Reaktivlar va mahsulotlarni '+' bilan ajrating.",
                        )
                    )

        states = [item.state for item in equation.species]
        if any(states) and not all(states):
            missing = [item.formula.display for item in equation.species if not item.state]
            issues.append(
                Issue(
                    level="warning",
                    code="state-mismatch",
                    title="Fizik holatlar faqat ba'zi moddalar uchun berilgan",
                    detail=f"Holati ko'rsatilmaganlar: {', '.join(missing)}.",
                    fix="Har bir moddani (s), (l), (g) yoki (aq) bilan belgilang yoki hech birini belgilamang.",
                )
            )

        spectators = self._spectators(equation)
        if spectators:
            issues.append(
                Issue(
                    level="info",
                    code="spectator",
                    title=f"Ikkala tomonda ham o'zgarmasdan qolganlar: {', '.join(spectators)}",
                    detail="Ikkala tomonda ham bir xil ko'rinishda bo'lgan moddalar reaksiyada qatnashmaydi.",
                    fix="Sof ionli tenglamani olish uchun ularni qisqartiring.",
                )
            )
        return issues

    def _balance_issues(self, equation: Equation, result: BalanceResult) -> list[Issue]:
        issues: list[Issue] = []
        rows = build_table(equation)
        balanced_now = is_balanced(equation)

        if result.status == "missing_species":
            orphans = orphan_elements(equation)
            for symbol, side in sorted(orphans.items()):
                other = "mahsulotlarda" if side == "left" else "reaktivlarda"
                issues.append(
                    Issue(
                        level="error",
                        code="orphan-element",
                        title=f"{symbol} faqat {side} tomonida mavjud",
                        detail=f"Atomlar yo'qolib qolmaydi, shuning uchun tarkibida {symbol} bo'lgan "
                        f"modda {other} yetishmayapti.",
                        fix=f"{symbol} tutgan yetishmayotgan {other[:-1]}ni qo'shing.",
                    )
                )
            return issues

        if result.status == "impossible":
            issues.append(
                Issue(
                    level="error",
                    code="impossible",
                    title="Bu reaksiya yozilganidek tenglashtirilishi mumkin emas",
                    detail=result.message,
                    fix="Har bir formulani o'zingiz nazarda tutgan birikma bilan solishtiring.",
                )
            )
            return issues

        if balanced_now:
            lowest = result.coefficients == result.original_coefficients
            issues.append(
                Issue(
                    level="success",
                    code="balanced",
                    title="Har bir element tenglashgan",
                    detail="; ".join(f"{row.element}: {row.left} = {row.right}" for row in rows),
                )
            )
            if not lowest and result.coefficients:
                factor = result.original_coefficients[0] // result.coefficients[0]
                issues.append(
                    Issue(
                        level="warning",
                        code="not-lowest-terms",
                        title="Koeffitsiyentlar eng kichik hadlarda emas",
                        detail=f"Har bir koeffitsiyentni {factor} ga bo'lish mumkin.",
                        fix=f"Uni {result.equation.display} ko'rinishida yozing."
                        if result.equation
                        else None,
                    )
                )
        else:
            wrong = [row for row in rows if not row.balanced]
            detail = "; ".join(
                f"{row.element}: chapda {row.left}, o'ngda {row.right}" for row in wrong
            )
            issues.append(
                Issue(
                    level="error",
                    code="unbalanced",
                    title=f"{self._name_elements(wrong)} tenglashmagan",
                    detail=detail,
                    fix=self._coefficient_fix(equation, result),
                )
            )

        if result.status == "underdetermined":
            issues.append(
                Issue(
                    level="warning",
                    code="underdetermined",
                    title="Bir nechta tenglashtirish usuli mavjud",
                    detail=result.message,
                    fix="Noyob javobni olish uchun har bir reaksiyani alohida yozing.",
                )
            )
        return issues

    def _charge_issues(self, equation: Equation) -> list[Issue]:
        if not equation.has_charges:
            return []
        left = charge_of_side(equation.reactants)
        right = charge_of_side(equation.products)
        if left == right:
            return [
                Issue(
                    level="success",
                    code="charge-ok",
                    title=f"Charge balances at {left:+d} on both sides",
                )
            ]
        return [
            Issue(
                level="error",
                code="charge-mismatch",
                title="Charge is not conserved",
                detail=f"Net {left:+d} on the left but {right:+d} on the right.",
                fix="Add electrons, H⁺ or OH⁻ as the medium requires, then rebalance.",
            )
        ]

    @staticmethod
    def _mass_issue(equation: Equation) -> list[Issue]:
        left, right = mass_balance(equation)
        if abs(left - right) < 1e-6:
            return [
                Issue(
                    level="info",
                    code="mass-ok",
                    title=f"Mass conserved: {format_number(left, 3)} g/mol on each side",
                )
            ]
        return [
            Issue(
                level="info",
                code="mass-gap",
                title="Mass does not yet match",
                detail=f"{format_number(left, 3)} g/mol in, {format_number(right, 3)} g/mol out — "
                f"a gap of {format_number(abs(left - right), 3)} g/mol.",
                fix="Mass falls into place once the atoms do.",
            )
        ]

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _name_elements(rows: list[AtomRow]) -> str:
        names = [row.element for row in rows]
        if len(names) == 1:
            return f"{names[0]} is"
        return f"{', '.join(names[:-1])} and {names[-1]} are"

    @staticmethod
    def _coefficient_fix(equation: Equation, result: BalanceResult) -> str | None:
        """Say which coefficient to change, not just that something is wrong."""
        if not result.succeeded or not result.equation:
            return None
        changes = [
            (species.formula.display, before, after)
            for species, before, after in zip(
                equation.species, result.original_coefficients, result.coefficients
            )
            if before != after
        ]
        if not changes:
            return None
        if len(changes) == 1:
            display, _, after = changes[0]
            return f"The coefficient in front of {display} should become {after}."
        listed = ", ".join(f"{display} → {after}" for display, _, after in changes)
        return f"Adjust these coefficients: {listed}."

    @staticmethod
    def _spectators(equation: Equation) -> list[str]:
        def key(item: Species) -> tuple[str, str | None]:
            return item.formula.raw, item.state

        left = {key(item) for item in equation.reactants}
        right = {key(item) for item in equation.products}
        shared = left & right
        return [parser.parse_formula(raw).display for raw, _ in sorted(shared)]


#: Shared validator instances.
formula_validator: Final[FormulaValidator] = FormulaValidator()
equation_validator: Final[EquationValidator] = EquationValidator()
