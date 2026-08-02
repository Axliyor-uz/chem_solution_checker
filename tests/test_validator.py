"""Tests for validation, classification, explanation and export."""

from __future__ import annotations

import json

import pytest

from components.balancer import balancer
from components.explanation import build_steps, error_report, hints, tutor_notes
from components.parser import parser
from components.reaction_classifier import classify, summarise
from components.validator import equation_validator, formula_validator
from data.compounds import name_from_formula
from utils import export


def check(text: str):
    return equation_validator.validate(text)


def codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


class TestEquationValidation:
    def test_balanced_equation_passes(self) -> None:
        report = check("2H2 + O2 -> 2H2O")
        assert report.ok
        assert report.headline == "Balanced and correct"
        assert "balanced" in codes(report)

    def test_unbalanced_equation_names_the_element(self) -> None:
        report = check("H2 + O2 -> H2O")
        assert not report.ok
        issue = next(i for i in report.issues if i.code == "unbalanced")
        assert "O" in issue.title
        assert "2 on the left" in issue.detail

    def test_fix_names_the_coefficient_to_change(self) -> None:
        report = check("H2 + O2 -> H2O")
        issue = next(i for i in report.issues if i.code == "unbalanced")
        assert issue.fix is not None
        assert "H₂O" in issue.fix and "2" in issue.fix

    def test_single_coefficient_fix_is_phrased_directly(self) -> None:
        report = check("2H2 + O2 -> H2O")
        issue = next(i for i in report.issues if i.code == "unbalanced")
        assert issue.fix == "The coefficient in front of H₂O should become 2."

    def test_lowest_terms_warning(self) -> None:
        report = check("4H2 + 2O2 -> 4H2O")
        assert "not-lowest-terms" in codes(report)
        assert report.headline == "Balanced, with notes"

    def test_charge_mismatch_is_an_error(self) -> None:
        report = check("Zn + Cu2+ -> Zn2+ + Cu2+")
        assert "charge-mismatch" in codes(report)

    def test_charge_conservation_is_confirmed(self) -> None:
        assert "charge-ok" in codes(check("Zn + Cu2+ -> Zn2+ + Cu"))

    def test_orphan_element_reported_as_missing_species(self) -> None:
        report = check("H2O -> H2 + O2 + N2")
        assert "orphan-element" in codes(report)

    def test_missing_plus_is_caught(self) -> None:
        assert "missing-plus" in codes(check("H2 O2 -> H2O"))

    def test_partial_states_warned(self) -> None:
        assert "state-mismatch" in codes(check("NaCl(aq) + AgNO3 -> AgCl(s) + NaNO3"))

    def test_spectator_ions_noted(self) -> None:
        report = check("Na+ + Cl- + Ag+ + NO3- -> AgCl(s) + Na+ + NO3-")
        assert "spectator" in codes(report)

    def test_parse_failure_is_reported_with_a_suggestion(self) -> None:
        report = check("FE2o3 -> Fe + O2")
        assert not report.parsed
        assert "Fe2O3" in report.errors[0].fix

    def test_issues_sorted_errors_first(self) -> None:
        levels = [issue.level for issue in check("H2 + O2 -> H2O").sorted_issues]
        assert levels[0] == "error"


class TestFormulaValidation:
    def test_valid_formula(self) -> None:
        formula, issues = formula_validator.validate("Ca(OH)2")
        assert formula is not None
        assert issues[0].level == "success"

    def test_invalid_formula(self) -> None:
        formula, issues = formula_validator.validate("Ca(OH2")
        assert formula is None
        assert issues[0].level == "error"

    def test_ion_is_noted(self) -> None:
        _, issues = formula_validator.validate("SO4^2-")
        assert any(issue.code == "charge" for issue in issues)


class TestClassification:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("CH4 + 2O2 -> CO2 + 2H2O", "Combustion"),
            ("CaCO3 -> CaO + CO2", "Decomposition"),
            ("2Na + Cl2 -> 2NaCl", "Synthesis"),
            ("NaOH + HCl -> NaCl + H2O", "Neutralisation (acid–base)"),
            ("Fe + CuSO4 -> FeSO4 + Cu", "Single displacement"),
            ("NaCl(aq) + AgNO3(aq) -> AgCl(s) + NaNO3(aq)", "Precipitation"),
        ],
    )
    def test_primary_type(self, text: str, expected: str) -> None:
        assert classify(parser.parse_equation(text))[0].name == expected

    def test_redox_detected_alongside(self) -> None:
        names = [item.name for item in classify(parser.parse_equation("Zn + 2HCl -> ZnCl2 + H2"))]
        assert "Redox" in names

    def test_equilibrium_from_the_arrow(self) -> None:
        names = [item.name for item in classify(parser.parse_equation("2SO2 + O2 <=> 2SO3"))]
        assert "Equilibrium" in names

    def test_summary_sentence(self) -> None:
        assert summarise(parser.parse_equation("CH4 + 2O2 -> CO2 + 2H2O")).startswith("Combustion")


class TestExplanation:
    def test_steps_end_with_a_verified_check(self) -> None:
        equation = parser.parse_equation("C3H8 + O2 -> CO2 + H2O")
        steps = build_steps(equation, balancer.balance(equation))
        assert steps[0].number == 1
        assert steps[-1].rows
        assert all(row.balanced for row in steps[-1].rows)

    def test_conservation_lines_use_unknowns(self) -> None:
        equation = parser.parse_equation("H2 + O2 -> H2O")
        steps = build_steps(equation, balancer.balance(equation))
        setup = next(step for step in steps if "conservation" in step.title)
        assert any(line.startswith("H:") for line in setup.lines)

    def test_hints_reveal_gradually(self) -> None:
        equation = parser.parse_equation("Fe + O2 -> Fe2O3")
        given = hints(equation, balancer.balance(equation))
        assert len(given) >= 3
        assert "4Fe" not in given[0]
        assert "4Fe" in given[-1]

    def test_error_report_is_plain_language(self) -> None:
        equation = parser.parse_equation("H2 + O2 -> H2O")
        lines = error_report(equation, balancer.balance(equation))
        assert any("Oxygen" in line or line.startswith("O atoms") for line in lines)
        assert any("should become 2" in line for line in lines)

    def test_tutor_notes_adapt_to_the_reaction(self) -> None:
        equation = parser.parse_equation("CH4 + O2 -> CO2 + H2O")
        headings = [heading for heading, _ in tutor_notes(equation, balancer.balance(equation))]
        assert any("combustion" in heading.lower() for heading in headings)

    def test_polyatomic_units_are_pointed_out(self) -> None:
        equation = parser.parse_equation("NaOH + H2SO4 -> Na2SO4 + H2O")
        headings = [heading for heading, _ in tutor_notes(equation, balancer.balance(equation))]
        assert any("one unit" in heading for heading in headings)


class TestNaming:
    @pytest.mark.parametrize(
        ("formula", "name"),
        [
            ("FeCl3", "Iron(III) chloride"),
            ("FeCl2", "Iron(II) chloride"),
            ("Cu2O", "Copper(I) oxide"),
            ("MgCl2", "Magnesium chloride"),
            ("N2O4", "Dinitrogen tetroxide"),
            ("KNO3", "Potassium nitrate"),
            ("H2O", "Water"),
        ],
    )
    def test_names(self, formula: str, name: str) -> None:
        parsed = parser.parse_formula(formula)
        assert name_from_formula(parsed.raw, parsed.composition, parsed.charge) == name


class TestExport:
    def test_json_round_trips(self) -> None:
        report = check("H2 + O2 -> H2O")
        payload = json.loads(export.to_json(report))
        assert payload["equation"]["read_as"] == "H2 + O2 -> H2O"
        assert payload["balancing"]["coefficients"] == [2, 1, 2]
        assert payload["valid"] is False

    def test_csv_has_a_row_per_element(self) -> None:
        rows = export.to_csv(check("H2 + O2 -> H2O")).splitlines()
        assert rows[0].startswith("element")
        assert len(rows) == 3

    def test_pdf_is_a_pdf(self) -> None:
        report = check("2H2 + O2 -> 2H2O")
        assert export.to_pdf(report).startswith(b"%PDF")

    def test_png_is_a_png(self) -> None:
        assert export.to_png(check("2H2 + O2 -> 2H2O")).startswith(b"\x89PNG")

    def test_filename_is_safe(self) -> None:
        name = export.summary_filename(check("2H2 + O2 -> 2H2O"), "pdf")
        assert name.endswith(".pdf")
        assert " " not in name and "/" not in name
