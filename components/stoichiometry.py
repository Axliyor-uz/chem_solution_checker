"""Mole arithmetic on a balanced equation.

Everything here starts from moles. Grams, litres of gas and solution volumes
are converted to moles first, the coefficients do the work, and the answer is
converted back — which is exactly the route a student is taught to follow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

from components.atom_counter import is_balanced
from components.parser import Equation, Species

Unit = Literal["mol", "g", "kg", "mg", "L_gas", "mL_gas", "L_solution", "mL_solution"]

#: Molar volume of an ideal gas, litres per mole.
MOLAR_VOLUME_STP: Final[float] = 22.414   # 0 °C, 1 atm
MOLAR_VOLUME_RTP: Final[float] = 24.055   # 25 °C, 1 atm
GAS_CONSTANT: Final[float] = 0.082057     # L·atm / (mol·K)

UNIT_LABELS: Final[dict[Unit, str]] = {
    "mol": "moles",
    "g": "grams",
    "kg": "kilograms",
    "mg": "milligrams",
    "L_gas": "litres of gas",
    "mL_gas": "millilitres of gas",
    "L_solution": "litres of solution",
    "mL_solution": "millilitres of solution",
}


class StoichiometryError(ValueError):
    """Raised when a calculation cannot be set up from the given inputs."""


@dataclass(frozen=True, slots=True)
class Amount:
    """A quantity of one species, in whatever unit the student has."""

    species_index: int
    value: float
    unit: Unit = "g"
    concentration: float | None = None  # mol/L, for solution volumes

    def to_moles(self, species: Species, molar_volume: float) -> float:
        """Convert to moles.

        Raises:
            StoichiometryError: If a solution volume is given without a
                concentration, or the amount is negative.
        """
        if self.value < 0:
            raise StoichiometryError("Amounts cannot be negative.")
        mass = species.formula.molar_mass
        if self.unit == "mol":
            return self.value
        if self.unit == "g":
            return self.value / mass
        if self.unit == "kg":
            return self.value * 1000.0 / mass
        if self.unit == "mg":
            return self.value / 1000.0 / mass
        if self.unit == "L_gas":
            return self.value / molar_volume
        if self.unit == "mL_gas":
            return self.value / 1000.0 / molar_volume
        if self.unit in {"L_solution", "mL_solution"}:
            if not self.concentration:
                raise StoichiometryError(
                    "A solution volume needs a concentration in mol/L to become moles."
                )
            litres = self.value if self.unit == "L_solution" else self.value / 1000.0
            return litres * self.concentration
        raise StoichiometryError(f"Unknown unit '{self.unit}'.")


@dataclass(slots=True)
class SpeciesResult:
    """What the calculation says about one species."""

    species: Species
    role: Literal["reactant", "product"]
    moles: float
    mass: float
    gas_volume: float | None = None
    supplied_moles: float | None = None
    excess_moles: float | None = None
    limiting: bool = False

    @property
    def name(self) -> str:
        return self.species.formula.display

    @property
    def excess_mass(self) -> float | None:
        if self.excess_moles is None:
            return None
        return self.excess_moles * self.species.formula.molar_mass


@dataclass(slots=True)
class StoichiometryResult:
    """The full picture for one set of starting amounts."""

    equation: Equation
    results: list[SpeciesResult]
    limiting: SpeciesResult | None
    extent: float
    molar_volume: float
    notes: list[str] = field(default_factory=list)

    @property
    def reactants(self) -> list[SpeciesResult]:
        return [item for item in self.results if item.role == "reactant"]

    @property
    def products(self) -> list[SpeciesResult]:
        return [item for item in self.results if item.role == "product"]

    @property
    def excess_reagents(self) -> list[SpeciesResult]:
        return [
            item
            for item in self.reactants
            if item.excess_moles is not None and item.excess_moles > 1e-9
        ]


class StoichiometryCalculator:
    """Runs mole calculations on a balanced equation."""

    def __init__(self, molar_volume: float = MOLAR_VOLUME_STP) -> None:
        self.molar_volume = molar_volume

    @staticmethod
    def molar_volume_at(temperature_c: float, pressure_atm: float = 1.0) -> float:
        """Ideal-gas molar volume in L/mol at a given temperature and pressure."""
        if pressure_atm <= 0:
            raise StoichiometryError("Pressure must be greater than zero.")
        kelvin = temperature_c + 273.15
        if kelvin <= 0:
            raise StoichiometryError("Temperature is below absolute zero.")
        return GAS_CONSTANT * kelvin / pressure_atm

    def calculate(
        self,
        equation: Equation,
        amounts: list[Amount],
        percent_yield: float | None = None,
    ) -> StoichiometryResult:
        """Work out every quantity implied by the given starting amounts.

        Args:
            equation: A balanced equation.
            amounts: One or more known amounts of reactants (or of a single
                product, to work backwards).
            percent_yield: Optional actual yield as a percentage, applied to
                the products.

        Returns:
            A :class:`StoichiometryResult`.

        Raises:
            StoichiometryError: If the equation is not balanced or no amount
                was supplied.
        """
        if not is_balanced(equation):
            raise StoichiometryError(
                "Balance the equation first — mole ratios come from the coefficients."
            )
        if not amounts:
            raise StoichiometryError("Give at least one known amount.")

        species = equation.species
        supplied: dict[int, float] = {}
        for amount in amounts:
            if not 0 <= amount.species_index < len(species):
                raise StoichiometryError("An amount refers to a species that is not in the equation.")
            moles = amount.to_moles(species[amount.species_index], self.molar_volume)
            supplied[amount.species_index] = supplied.get(amount.species_index, 0.0) + moles

        split = len(equation.reactants)
        notes: list[str] = []

        # The extent of reaction: how many times the equation as written can run.
        reactant_extents = {
            index: moles / species[index].coefficient
            for index, moles in supplied.items()
            if index < split
        }
        if reactant_extents:
            extent = min(reactant_extents.values())
            limiting_index = min(reactant_extents, key=lambda i: reactant_extents[i])
            if len(reactant_extents) == 1:
                notes.append(
                    "Only one starting amount was given, so it is assumed to be fully consumed."
                )
        else:
            product_extents = {
                index: moles / species[index].coefficient
                for index, moles in supplied.items()
                if index >= split
            }
            extent = min(product_extents.values())
            limiting_index = None
            notes.append("Working backwards from a product to the reactants it requires.")

        results: list[SpeciesResult] = []
        for index, item in enumerate(species):
            role: Literal["reactant", "product"] = "reactant" if index < split else "product"
            required = item.coefficient * extent
            given = supplied.get(index)
            excess = None
            if role == "reactant" and given is not None:
                excess = given - required
            moles_out = required
            if role == "product" and percent_yield is not None:
                moles_out = required * percent_yield / 100.0
            results.append(
                SpeciesResult(
                    species=item,
                    role=role,
                    moles=moles_out,
                    mass=moles_out * item.formula.molar_mass,
                    gas_volume=moles_out * self.molar_volume if item.state == "g" else None,
                    supplied_moles=given,
                    excess_moles=excess,
                    limiting=index == limiting_index,
                )
            )

        if percent_yield is not None:
            notes.append(
                f"Product amounts include the {percent_yield:g}% yield; "
                "the theoretical values are higher."
            )
        limiting = results[limiting_index] if limiting_index is not None else None
        if limiting and len(reactant_extents) > 1:
            notes.append(
                f"{limiting.name} runs out first, so it fixes how far the reaction goes."
            )
        return StoichiometryResult(
            equation=equation,
            results=results,
            limiting=limiting,
            extent=extent,
            molar_volume=self.molar_volume,
            notes=notes,
        )


def mole_ratio(equation: Equation, from_index: int, to_index: int) -> str:
    """The ratio between two species, written the way it is used."""
    species = equation.species
    first, second = species[from_index], species[to_index]
    return (
        f"{first.coefficient} mol {first.formula.display} : "
        f"{second.coefficient} mol {second.formula.display}"
    )


def percent_yield(actual: float, theoretical: float) -> float:
    """Percent yield from actual and theoretical amounts in the same unit."""
    if theoretical <= 0:
        raise StoichiometryError("Theoretical yield must be greater than zero.")
    return actual / theoretical * 100.0


#: Default calculator at STP.
calculator: Final[StoichiometryCalculator] = StoichiometryCalculator()
