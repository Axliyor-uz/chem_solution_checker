"""O'quvchi yozganini baholaydi va sababini aytadi.

Tekshirgich hech qachon shunchaki "noto'g'ri" demaydi. Har bir xulosa —
nima xato, u qayerda va nima qilish kerakligini aytadigan :class:`Issue`.
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
    """O'quvchi ishi haqidagi bitta xulosa."""

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
    """Tekshirgichning bitta javob bo'yicha barcha xulosalari."""

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
        """Tenglama o'qilsa, muvozanatlansa va zaryad saqlansa True."""
        return self.parsed and not self.errors

    @property
    def sorted_issues(self) -> list[Issue]:
        return sorted(self.issues, key=lambda issue: _LEVEL_RANK[issue.level])

    @property
    def headline(self) -> str:
        if not self.parsed:
            return "Tenglamani o'qib bo'lmadi"
        if self.errors:
            return self.errors[0].title
        if self.warnings:
            return "Muvozanatlangan, izohlar bilan"
        return "Muvozanatlangan va to'g'ri"


class FormulaValidator:
    """Bitta formulani alohida tekshiradi."""

    def validate(self, text: str) -> tuple[Formula | None, list[Issue]]:
        """Formulani o'qiydi va undagi shubhali joylarni bildiradi."""
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
                    fix=f"Shunday yozib ko'ring: {error.suggestion}" if error.suggestion else None,
                )
            )
            return None, issues

        if formula.charge:
            issues.append(
                Issue(
                    level="info",
                    code="charge",
                    title=f"Zaryadi {formula.charge:+d} bo'lgan ion sifatida o'qildi",
                    detail=f"{formula.display} deb tushunildi.",
                )
            )
        for symbol, count in formula.composition.items():
            if count > 200:
                issues.append(
                    Issue(
                        level="warning",
                        code="large-subscript",
                        title=f"{symbol} ning pastki indeksi g'ayrioddiy katta ({count})",
                        detail="Indeksni tekshiring — bu odatdagi formulalardan ancha chetda.",
                    )
                )
        if not issues:
            issues.append(
                Issue(
                    level="success",
                    code="formula-ok",
                    title=f"{formula.display} — to'g'ri formula",
                    detail=f"Molyar massasi {format_number(formula.molar_mass, 3)} g/mol.",
                )
            )
        return formula, issues


class EquationValidator:
    """Yozilgan tenglamani to'liq tekshiradi."""

    def __init__(self) -> None:
        self._formula_validator = FormulaValidator()

    def validate(self, text: str) -> ValidationReport:
        """Tenglamani o'qiydi, muvozanatlaydi va tahlil qiladi.

        Args:
            text: Xom kiritma — parser qabul qiladigan istalgan yozuvda.

        Returns:
            :class:`ValidationReport`. Unda doim kamida bitta xulosa bo'ladi.
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
                    fix=f"Shunday yozib ko'ring: {error.suggestion}" if error.suggestion else None,
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

    # ------------------------------------------------------- qismiy tekshiruvlar

    def _structure_issues(self, text: str, equation: Equation) -> list[Issue]:
        issues: list[Issue] = []
        normalized = normalize_input(text)

        for side_name, side in (("chapda", equation.reactants), ("o'ngda", equation.products)):
            seen: dict[str, int] = {}
            for item in side:
                seen[item.formula.raw] = seen.get(item.formula.raw, 0) + 1
            for raw, count in seen.items():
                if count > 1:
                    issues.append(
                        Issue(
                            level="info",
                            code="repeated-species",
                            title=f"{raw} {side_name} {count} marta uchraydi",
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
                            title="Ikkita formula bo'sh joy bilan qo'shilib ketganga o'xshaydi",
                            detail=f"'{piece.strip()}' bitta modda deb o'qildi.",
                            fix="Reagent va mahsulotlarni '+' bilan ajrating.",
                        )
                    )

        states = [item.state for item in equation.species]
        if any(states) and not all(states):
            missing = [item.formula.display for item in equation.species if not item.state]
            issues.append(
                Issue(
                    level="warning",
                    code="state-mismatch",
                    title="Fizik holat faqat ayrim moddalarda ko'rsatilgan",
                    detail=f"Holati yo'q: {', '.join(missing)}.",
                    fix="Yo har bir moddaga (s), (l), (g) yoki (aq) qo'ying, yo hech biriga qo'ymang.",
                )
            )

        spectators = self._spectators(equation)
        if spectators:
            issues.append(
                Issue(
                    level="info",
                    code="spectator",
                    title=f"Ikkala tomonda o'zgarmagan: {', '.join(spectators)}",
                    detail="Ikkala tomonda bir xil turgan moddalar reaksiyada qatnashmaydi.",
                    fix="Ularni qisqartirsangiz, qisqa ionli tenglama chiqadi.",
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
                other = "mahsulotlar" if side == "left" else "reagentlar"
                where = "chapda" if side == "left" else "o'ngda"
                issues.append(
                    Issue(
                        level="error",
                        code="orphan-element",
                        title=f"{symbol} faqat {where} uchraydi",
                        detail=f"Atomlar yo'qolib qolmaydi, demak {other} orasida tarkibida "
                        f"{symbol} bo'lgan modda tushib qolgan.",
                        fix=f"{symbol} ni olib yuruvchi tushib qolgan moddani {other}ga qo'shing.",
                    )
                )
            return issues

        if result.status == "impossible":
            issues.append(
                Issue(
                    level="error",
                    code="impossible",
                    title="Bu reaksiyani yozilganidek muvozanatlab bo'lmaydi",
                    detail=result.message,
                    fix="Har bir formulani nazarda tutgan birikmangiz bilan solishtiring.",
                )
            )
            return issues

        if balanced_now:
            lowest = result.coefficients == result.original_coefficients
            issues.append(
                Issue(
                    level="success",
                    code="balanced",
                    title="Har bir element muvozanatda",
                    detail="; ".join(f"{row.element}: {row.left} = {row.right}" for row in rows),
                )
            )
            if not lowest and result.coefficients:
                factor = result.original_coefficients[0] // result.coefficients[0]
                issues.append(
                    Issue(
                        level="warning",
                        code="not-lowest-terms",
                        title="Koeffitsiyentlar eng kichik holatda emas",
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
                    title=f"{self._name_elements(wrong)} muvozanatlanmagan",
                    detail=detail,
                    fix=self._coefficient_fix(equation, result),
                )
            )

        if result.status == "underdetermined":
            issues.append(
                Issue(
                    level="warning",
                    code="underdetermined",
                    title="Bir nechta muvozanatlash varianti mavjud",
                    detail=result.message,
                    fix="Yagona javob olish uchun har bir reaksiyani alohida yozing.",
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
                    title=f"Zaryad muvozanatda: ikkala tomonda ham {left:+d}",
                )
            ]
        return [
            Issue(
                level="error",
                code="charge-mismatch",
                title="Zaryad saqlanmagan",
                detail=f"Chapda umumiy {left:+d}, o'ngda esa {right:+d}.",
                fix="Muhitga qarab elektron, H⁺ yoki OH⁻ qo'shing va qaytadan muvozanatlang.",
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
                    title=f"Massa saqlangan: har ikki tomonda {format_number(left, 3)} g/mol",
                )
            ]
        return [
            Issue(
                level="info",
                code="mass-gap",
                title="Massa hali mos kelmayapti",
                detail=f"Kirishda {format_number(left, 3)} g/mol, chiqishda {format_number(right, 3)} g/mol — "
                f"farqi {format_number(abs(left - right), 3)} g/mol.",
                fix="Atomlar joyiga tushishi bilan massa ham to'g'ri chiqadi.",
            )
        ]

    # ------------------------------------------------------------ yordamchilar

    @staticmethod
    def _name_elements(rows: list[AtomRow]) -> str:
        names = [row.element for row in rows]
        if len(names) == 1:
            return names[0]
        return f"{', '.join(names[:-1])} va {names[-1]}"

    @staticmethod
    def _coefficient_fix(equation: Equation, result: BalanceResult) -> str | None:
        """Qaysi koeffitsiyentni o'zgartirish kerakligini aytadi, shunchaki "xato" demaydi."""
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
            return f"{display} oldidagi koeffitsiyent {after} bo'lishi kerak."
        listed = ", ".join(f"{display} → {after}" for display, _, after in changes)
        return f"Bu koeffitsiyentlarni to'g'rilang: {listed}."

    @staticmethod
    def _spectators(equation: Equation) -> list[str]:
        def key(item: Species) -> tuple[str, str | None]:
            return item.formula.raw, item.state

        left = {key(item) for item in equation.reactants}
        right = {key(item) for item in equation.products}
        shared = left & right
        return [parser.parse_formula(raw).display for raw, _ in sorted(shared)]


#: Umumiy tekshirgich namunalari.
formula_validator: Final[FormulaValidator] = FormulaValidator()
equation_validator: Final[EquationValidator] = EquationValidator()
