"""Tests for balancing, atom counting and mole arithmetic."""

from __future__ import annotations

import pytest

from components.atom_counter import build_table, is_balanced, mass_balance, orphan_elements
from components.balancer import balancer
from components.parser import parser
from components.stoichiometry import (
    Amount,
    StoichiometryCalculator,
    StoichiometryError,
    calculator,
    percent_yield,
)


def balance(text: str):
    return balancer.balance(parser.parse_equation(text))


class TestBalancing:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("H2 + O2 -> H2O", [2, 1, 2]),
            ("Fe + O2 -> Fe2O3", [4, 3, 2]),
            ("C3H8 + O2 -> CO2 + H2O", [1, 5, 3, 4]),
            ("C6H12O6 + O2 -> CO2 + H2O", [1, 6, 6, 6]),
            ("Al + HCl -> AlCl3 + H2", [2, 6, 2, 3]),
            ("NaCl -> Na + Cl2", [2, 2, 1]),
            ("Cu + HNO3 -> Cu(NO3)2 + NO + H2O", [3, 8, 3, 2, 4]),
            ("KMnO4 + HCl -> KCl + MnCl2 + H2O + Cl2", [2, 16, 2, 2, 8, 5]),
        ],
    )
    def test_coefficients(self, text: str, expected: list[int]) -> None:
        result = balance(text)
        assert result.succeeded
        assert result.coefficients == expected
        assert result.cross_checked

    def test_ionic_redox_balances_charge_too(self) -> None:
        result = balance("MnO4- + Fe2+ + H+ -> Mn2+ + Fe3+ + H2O")
        assert result.coefficients == [1, 5, 8, 1, 5, 4]
        assert is_balanced(result.equation)

    def test_already_balanced_is_recognised(self) -> None:
        assert balance("CaCO3 -> CaO + CO2").status == "already_balanced"

    def test_reduces_to_lowest_terms(self) -> None:
        result = balance("4H2 + 2O2 -> 4H2O")
        assert result.status == "balanced"
        assert result.coefficients == [2, 1, 2]

    def test_missing_species_is_named_as_such(self) -> None:
        result = balance("H2O -> H2 + O2 + N2")
        assert result.status == "missing_species"
        assert "N" in result.message

    def test_impossible_reaction(self) -> None:
        result = balance("Zn + Cu2+ -> Zn2+ + Cu2+")
        assert not result.succeeded

    def test_underdetermined_is_flagged(self) -> None:
        result = balance("Fe + O2 -> FeO + Fe2O3")
        assert result.status == "underdetermined"
        assert result.solution_count > 1
        assert is_balanced(result.equation)

    def test_matrix_has_a_row_per_element_plus_charge(self) -> None:
        equation = parser.parse_equation("Zn + Cu2+ -> Zn2+ + Cu")
        matrix, labels = balancer.build_matrix(equation)
        assert labels == ["Cu", "Zn", "charge"]
        assert matrix.shape == (3, 4)

    def test_changes_report_only_what_moved(self) -> None:
        result = balance("H2 + O2 -> H2O")
        assert [(before, after) for _, before, after in result.changes] == [(1, 2), (1, 2)]


class TestAtomCounter:
    def test_counts_both_sides(self) -> None:
        rows = build_table(parser.parse_equation("H2 + O2 -> H2O"))
        counts = {row.element: (row.left, row.right) for row in rows}
        assert counts == {"H": (2, 2), "O": (2, 1)}

    def test_difference_and_verdict(self) -> None:
        row = next(r for r in build_table(parser.parse_equation("H2 + O2 -> H2O")) if r.element == "O")
        assert row.difference == -1
        assert row.verdict == "incorrect"
        assert "left" in row.short_note

    def test_mass_conservation_follows_atom_balance(self) -> None:
        left, right = mass_balance(parser.parse_equation("2H2 + O2 -> 2H2O"))
        assert left == pytest.approx(right)

    def test_orphans(self) -> None:
        assert orphan_elements(parser.parse_equation("H2O -> H2 + O2 + N2")) == {"N": "right"}


class TestStoichiometry:
    def test_limiting_reagent_and_yield(self) -> None:
        equation = parser.parse_equation("2H2(g) + O2(g) -> 2H2O(l)")
        outcome = calculator.calculate(equation, [Amount(0, 4.0, "g"), Amount(1, 50.0, "g")])
        assert outcome.limiting.name.startswith("H")
        water = outcome.products[0]
        assert water.moles == pytest.approx(1.9841, abs=1e-3)
        assert water.mass == pytest.approx(35.744, abs=1e-2)

    def test_mass_is_conserved_across_the_calculation(self) -> None:
        equation = parser.parse_equation("2H2 + O2 -> 2H2O")
        outcome = calculator.calculate(equation, [Amount(0, 4.0, "g")])
        consumed = sum(item.mass for item in outcome.reactants)
        produced = sum(item.mass for item in outcome.products)
        assert consumed == pytest.approx(produced, rel=1e-9)

    def test_excess_reagent(self) -> None:
        equation = parser.parse_equation("2H2 + O2 -> 2H2O")
        outcome = calculator.calculate(equation, [Amount(0, 4.0, "g"), Amount(1, 50.0, "g")])
        excess = outcome.excess_reagents
        assert len(excess) == 1
        assert excess[0].excess_moles == pytest.approx(0.5705, abs=1e-3)

    def test_percent_yield_scales_products_only(self) -> None:
        equation = parser.parse_equation("N2 + 3H2 -> 2NH3")
        outcome = calculator.calculate(equation, [Amount(0, 28.0, "g")], percent_yield=50.0)
        assert outcome.products[0].moles == pytest.approx(0.9995, abs=1e-3)
        assert outcome.reactants[0].moles == pytest.approx(0.9995, abs=1e-3)

    def test_gas_volume_conversion(self) -> None:
        equation = parser.parse_equation("2H2(g) + O2(g) -> 2H2O(l)")
        outcome = calculator.calculate(equation, [Amount(0, 22.414, "L_gas")])
        assert outcome.reactants[0].moles == pytest.approx(1.0, abs=1e-4)

    def test_solution_volume_needs_a_concentration(self) -> None:
        equation = parser.parse_equation("NaOH + HCl -> NaCl + H2O")
        with pytest.raises(StoichiometryError, match="concentration"):
            calculator.calculate(equation, [Amount(0, 0.25, "L_solution")])

    def test_refuses_an_unbalanced_equation(self) -> None:
        equation = parser.parse_equation("H2 + O2 -> H2O")
        with pytest.raises(StoichiometryError, match="Balance"):
            calculator.calculate(equation, [Amount(0, 1.0, "mol")])

    def test_molar_volume_at_conditions(self) -> None:
        assert StoichiometryCalculator.molar_volume_at(0.0) == pytest.approx(22.41, abs=0.05)
        assert StoichiometryCalculator.molar_volume_at(25.0) == pytest.approx(24.47, abs=0.05)

    def test_percent_yield_helper(self) -> None:
        assert percent_yield(8.0, 10.0) == pytest.approx(80.0)
