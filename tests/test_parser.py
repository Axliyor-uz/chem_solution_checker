"""Tests for formula and equation parsing."""

from __future__ import annotations

import pytest

from components.parser import ParseError, parser, repair_capitalisation
from utils.formatting import normalize_input, to_display


class TestFormulas:
    @pytest.mark.parametrize(
        ("text", "composition"),
        [
            ("H2O", {"H": 2, "O": 1}),
            ("Ca(OH)2", {"Ca": 1, "O": 2, "H": 2}),
            ("Al2(SO4)3", {"Al": 2, "S": 3, "O": 12}),
            ("C6H12O6", {"C": 6, "H": 12, "O": 6}),
            ("CuSO4*5H2O", {"Cu": 1, "S": 1, "O": 9, "H": 10}),
            ("K4[Fe(CN)6]", {"K": 4, "Fe": 1, "C": 6, "N": 6}),
        ],
    )
    def test_composition(self, text: str, composition: dict[str, int]) -> None:
        assert parser.parse_formula(text).composition == composition

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("H2O", 18.015),
            ("H2SO4", 98.07),
            ("Ca(OH)2", 74.09),
            ("CuSO4*5H2O", 249.68),
        ],
    )
    def test_molar_mass(self, text: str, expected: float) -> None:
        assert parser.parse_formula(text).molar_mass == pytest.approx(expected, abs=0.01)

    @pytest.mark.parametrize(
        ("text", "charge", "composition"),
        [
            ("Na+", 1, {"Na": 1}),
            ("Cl-", -1, {"Cl": 1}),
            ("Ca++", 2, {"Ca": 1}),
            ("Fe3+", 3, {"Fe": 1}),      # lone symbol: the digit is the charge
            ("Fe+3", 3, {"Fe": 1}),
            ("Cu2+", 2, {"Cu": 1}),
            ("NH4+", 1, {"N": 1, "H": 4}),   # polyatomic: the digit is a subscript
            ("SO42-", -2, {"S": 1, "O": 4}),
            ("SO4^2-", -2, {"S": 1, "O": 4}),
            ("CO32-", -2, {"C": 1, "O": 3}),
            ("PO43-", -3, {"P": 1, "O": 4}),
            ("Cr2O72-", -2, {"Cr": 2, "O": 7}),
        ],
    )
    def test_charges(self, text: str, charge: int, composition: dict[str, int]) -> None:
        formula = parser.parse_formula(text)
        assert formula.charge == charge
        assert formula.composition == composition

    def test_charge_is_stored_canonically(self) -> None:
        assert parser.parse_formula("SO42-").raw == "SO4^2-"
        assert parser.parse_formula("Na+").raw == "Na^+"

    @pytest.mark.parametrize(
        "text", ["H2Q", "Ca(OH2", "Ca(OH]2", "O0", "2", "H2^", "H2+-"]
    )
    def test_rejects_nonsense(self, text: str) -> None:
        with pytest.raises(ParseError):
            parser.parse_formula(text)


class TestEquations:
    def test_reads_both_sides(self) -> None:
        equation = parser.parse_equation("2H2 + O2 -> 2H2O")
        assert [s.coefficient for s in equation.reactants] == [2, 1]
        assert equation.products[0].coefficient == 2
        assert equation.products[0].formula.composition == {"H": 2, "O": 1}

    @pytest.mark.parametrize("arrow", ["->", "-->", "=>", "=", "→"])
    def test_forward_arrow_spellings(self, arrow: str) -> None:
        equation = parser.parse_equation(f"H2 + O2 {arrow} H2O")
        assert not equation.reversible
        assert len(equation.reactants) == 2

    @pytest.mark.parametrize("arrow", ["<->", "<=>", "⇌"])
    def test_reversible_arrow_spellings(self, arrow: str) -> None:
        assert parser.parse_equation(f"2SO2 + O2 {arrow} 2SO3").reversible

    def test_states(self) -> None:
        equation = parser.parse_equation("NaCl(aq) + AgNO3(aq) -> AgCl(s) + NaNO3(aq)")
        assert [s.state for s in equation.species] == ["aq", "aq", "s", "aq"]

    def test_plus_in_a_charge_is_not_a_separator(self) -> None:
        equation = parser.parse_equation("Na+ + Cl- -> NaCl")
        assert len(equation.reactants) == 2
        assert equation.reactants[0].formula.charge == 1

    def test_state_after_a_charge(self) -> None:
        equation = parser.parse_equation("Na+(aq) + Cl-(aq) -> NaCl(s)")
        assert len(equation.reactants) == 2
        assert equation.reactants[0].state == "aq"

    def test_unicode_input(self) -> None:
        assert parser.parse_equation("H₂ + O₂ → H₂O").ascii == "H2 + O2 -> H2O"

    def test_superscript_charges(self) -> None:
        formula = parser.parse_equation("Fe³⁺ + OH⁻ -> Fe(OH)3").reactants[0].formula
        assert formula.charge == 3

    def test_elements_ordered_by_atomic_number(self) -> None:
        assert parser.parse_equation("C3H8 + O2 -> CO2 + H2O").elements == ["H", "C", "O"]

    @pytest.mark.parametrize(
        "text", ["H2 + O2", "-> H2O", "H2 + O2 -> ", "H2 -> H2 -> H2", "H2 + + O2 -> H2O"]
    )
    def test_rejects_malformed_equations(self, text: str) -> None:
        with pytest.raises(ParseError):
            parser.parse_equation(text)

    def test_rejects_invalid_state(self) -> None:
        with pytest.raises(ParseError, match="physical state"):
            parser.parse_equation("H2 + O2 -> H2O(x)")


class TestCapitalisationRepair:
    @pytest.mark.parametrize(
        ("wrong", "right"),
        [("FE2o3", "Fe2O3"), ("h2o", "H2O"), ("NAcl", "NaCl"), ("caco3", "CaCO3")],
    )
    def test_repairs(self, wrong: str, right: str) -> None:
        assert repair_capitalisation(wrong) == right

    def test_leaves_correct_formulas_alone(self) -> None:
        assert repair_capitalisation("Fe2O3") is None

    def test_gives_up_on_impossible_letters(self) -> None:
        assert repair_capitalisation("Qz9") is None

    def test_error_carries_the_suggestion(self) -> None:
        with pytest.raises(ParseError) as caught:
            parser.parse_formula("FE2o3")
        assert caught.value.suggestion == "Fe2O3"


class TestFormatting:
    @pytest.mark.parametrize(
        ("ascii_text", "display"),
        [
            ("H2O", "H₂O"),
            ("2H2O", "2H₂O"),          # coefficient stays full size
            ("Ca(OH)2", "Ca(OH)₂"),
            ("SO4^2-", "SO₄²⁻"),
            ("CuSO4*5H2O", "CuSO₄·5H₂O"),
            ("H2 + O2 -> H2O", "H₂ + O₂ → H₂O"),
        ],
    )
    def test_display(self, ascii_text: str, display: str) -> None:
        assert to_display(ascii_text) == display

    def test_normalisation_is_idempotent(self) -> None:
        once = normalize_input("H₂ + O₂ → H₂O")
        assert normalize_input(once) == once
