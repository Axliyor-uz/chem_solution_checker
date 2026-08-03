"""Muvozanatlangan tenglama bo'yicha mol hisob-kitobi.

Bu yerda hamma narsa moldan boshlanadi. Gramm, gaz litri va eritma hajmi avval
molga o'giriladi, keyin koeffitsiyentlar ish beradi va javob yana qaytariladi —
aynan o'quvchiga o'rgatiladigan yo'l.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

from components.atom_counter import is_balanced
from components.parser import Equation, Species

Unit = Literal["mol", "g", "kg", "mg", "L_gas", "mL_gas", "L_solution", "mL_solution"]

#: Ideal gazning molyar hajmi, litr/mol.
MOLAR_VOLUME_STP: Final[float] = 22.414   # 0 °C, 1 atm
MOLAR_VOLUME_RTP: Final[float] = 24.055   # 25 °C, 1 atm
GAS_CONSTANT: Final[float] = 0.082057     # L·atm / (mol·K)

UNIT_LABELS: Final[dict[Unit, str]] = {
    "mol": "mol",
    "g": "gramm",
    "kg": "kilogramm",
    "mg": "milligramm",
    "L_gas": "litr gaz",
    "mL_gas": "millilitr gaz",
    "L_solution": "litr eritma",
    "mL_solution": "millilitr eritma",
}


class StoichiometryError(ValueError):
    """Berilgan ma'lumotlardan hisob tuzib bo'lmaganda ko'tariladi."""


@dataclass(frozen=True, slots=True)
class Amount:
    """Bitta moddaning miqdori — o'quvchida qanday birlikda bo'lsa, shunday."""

    species_index: int
    value: float
    unit: Unit = "g"
    concentration: float | None = None  # mol/L, eritma hajmlari uchun

    def to_moles(self, species: Species, molar_volume: float) -> float:
        """Molga o'giradi.

        Raises:
            StoichiometryError: Eritma hajmi konsentratsiyasiz berilgan bo'lsa
                yoki miqdor manfiy bo'lsa.
        """
        if self.value < 0:
            raise StoichiometryError("Miqdor manfiy bo'lishi mumkin emas.")
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
                    "Eritma hajmini molga o'girish uchun mol/L dagi konsentratsiya kerak."
                )
            litres = self.value if self.unit == "L_solution" else self.value / 1000.0
            return litres * self.concentration
        raise StoichiometryError(f"Noma'lum birlik: '{self.unit}'.")


@dataclass(slots=True)
class SpeciesResult:
    """Hisob bitta modda haqida nima deydi."""

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
    """Bitta boshlang'ich miqdorlar to'plami uchun to'liq manzara."""

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
    """Muvozanatlangan tenglama bo'yicha mol hisoblarini bajaradi."""

    def __init__(self, molar_volume: float = MOLAR_VOLUME_STP) -> None:
        self.molar_volume = molar_volume

    @staticmethod
    def molar_volume_at(temperature_c: float, pressure_atm: float = 1.0) -> float:
        """Berilgan harorat va bosimdagi ideal gaz molyar hajmi, L/mol."""
        if pressure_atm <= 0:
            raise StoichiometryError("Bosim noldan katta bo'lishi kerak.")
        kelvin = temperature_c + 273.15
        if kelvin <= 0:
            raise StoichiometryError("Harorat mutlaq noldan past.")
        return GAS_CONSTANT * kelvin / pressure_atm

    def calculate(
        self,
        equation: Equation,
        amounts: list[Amount],
        percent_yield: float | None = None,
    ) -> StoichiometryResult:
        """Berilgan boshlang'ich miqdorlardan kelib chiqadigan barcha qiymatlarni hisoblaydi.

        Args:
            equation: Muvozanatlangan tenglama.
            amounts: Reagentlarning bir yoki bir nechta ma'lum miqdori (yoki
                teskari hisoblash uchun bitta mahsulot miqdori).
            percent_yield: Ixtiyoriy amaliy unum, foizda — mahsulotlarga qo'llanadi.

        Returns:
            :class:`StoichiometryResult`.

        Raises:
            StoichiometryError: Tenglama muvozanatlanmagan bo'lsa yoki hech qanday
                miqdor berilmagan bo'lsa.
        """
        if not is_balanced(equation):
            raise StoichiometryError(
                "Avval tenglamani muvozanatlang — mol nisbatlari koeffitsiyentlardan olinadi."
            )
        if not amounts:
            raise StoichiometryError("Kamida bitta ma'lum miqdorni kiriting.")

        species = equation.species
        supplied: dict[int, float] = {}
        for amount in amounts:
            if not 0 <= amount.species_index < len(species):
                raise StoichiometryError("Miqdor tenglamada yo'q moddaga tegishli.")
            moles = amount.to_moles(species[amount.species_index], self.molar_volume)
            supplied[amount.species_index] = supplied.get(amount.species_index, 0.0) + moles

        split = len(equation.reactants)
        notes: list[str] = []

        # Reaksiya darajasi: tenglama yozilgan holida necha marta bora oladi.
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
                    "Faqat bitta boshlang'ich miqdor berilgan, shuning uchun u to'liq sarflanadi deb olindi."
                )
        else:
            product_extents = {
                index: moles / species[index].coefficient
                for index, moles in supplied.items()
                if index >= split
            }
            extent = min(product_extents.values())
            limiting_index = None
            notes.append("Mahsulotdan teskari yo'nalishda unga kerak bo'lgan reagentlar hisoblanmoqda.")

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
                f"Mahsulot miqdorlari {percent_yield:g}% unum bilan berilgan; "
                "nazariy qiymatlar bundan yuqori."
            )
        limiting = results[limiting_index] if limiting_index is not None else None
        if limiting and len(reactant_extents) > 1:
            notes.append(
                f"{limiting.name} birinchi bo'lib tugaydi, ya'ni reaksiya qay darajada borishini u belgilaydi."
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
    """Ikki modda orasidagi nisbat — ishlatiladigan ko'rinishda."""
    species = equation.species
    first, second = species[from_index], species[to_index]
    return (
        f"{first.coefficient} mol {first.formula.display} : "
        f"{second.coefficient} mol {second.formula.display}"
    )


def percent_yield(actual: float, theoretical: float) -> float:
    """Bir xil birlikdagi amaliy va nazariy miqdorlardan foizli unum."""
    if theoretical <= 0:
        raise StoichiometryError("Nazariy unum noldan katta bo'lishi kerak.")
    return actual / theoretical * 100.0


#: Standart sharoitdagi (STP) asosiy kalkulyator.
calculator: Final[StoichiometryCalculator] = StoichiometryCalculator()
