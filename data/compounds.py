"""Compound reference data and a fallback namer.

The lookup table covers the compounds a syllabus actually uses. Anything
outside it falls through to :func:`name_from_formula`, which applies the
ordinary naming rules rather than returning nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from data.elements import ELEMENTS

_METALS: Final[frozenset[str]] = frozenset(
    symbol
    for symbol, element in ELEMENTS.items()
    if element.category
    in {"alkali metal", "alkaline earth metal", "transition metal",
        "post-transition metal", "lanthanide", "actinide"}
)

#: Ions that survive a reaction intact and are best balanced as one unit.
POLYATOMIC_IONS: Final[dict[str, tuple[str, int]]] = {
    "OH": ("hydroxide", -1), "NO3": ("nitrate", -1), "NO2": ("nitrite", -1),
    "SO4": ("sulfate", -2), "SO3": ("sulfite", -2), "CO3": ("carbonate", -2),
    "HCO3": ("hydrogencarbonate", -1), "PO4": ("phosphate", -3),
    "NH4": ("ammonium", 1), "ClO3": ("chlorate", -1), "ClO4": ("perchlorate", -1),
    "ClO": ("hypochlorite", -1), "MnO4": ("permanganate", -1),
    "Cr2O7": ("dichromate", -2), "CrO4": ("chromate", -2), "CN": ("cyanide", -1),
    "SCN": ("thiocyanate", -1), "C2H3O2": ("acetate", -1), "HSO4": ("hydrogensulfate", -1),
}

_ANION_STEMS: Final[dict[str, str]] = {
    "O": "ox", "S": "sulf", "N": "nitr", "P": "phosph", "C": "carb", "H": "hydr",
    "F": "fluor", "Cl": "chlor", "Br": "brom", "I": "iod", "Se": "selen",
    "Te": "tellur", "As": "arsen", "Si": "silic", "B": "bor",
}
_PREFIXES: Final[tuple[str, ...]] = (
    "", "mono", "di", "tri", "tetra", "penta", "hexa", "hepta", "octa", "nona", "deca",
)
_ROMAN: Final[dict[int, str]] = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII",
}


@dataclass(frozen=True, slots=True)
class Compound:
    """Reference entry for one compound."""

    formula: str
    name: str
    common_name: str = ""
    state: str = ""
    density: str = ""
    melting_point: str = ""
    uses: str = ""
    hazards: str = ""


#: Curated reference data. Densities are at room temperature unless noted.
COMPOUNDS: Final[dict[str, Compound]] = {
    c.formula: c
    for c in (
        Compound("H2O", "Water", "", "liquid", "1.00 g/cm³", "0 °C",
                 "Solvent, coolant, reaction medium.", "None under normal use."),
        Compound("H2SO4", "Sulfuric acid", "oil of vitriol", "liquid", "1.84 g/cm³", "10 °C",
                 "Fertiliser, batteries, refining.",
                 "Severe burns; dehydrates skin. Always add acid to water."),
        Compound("HCl", "Hydrogen chloride", "muriatic acid in solution", "gas", "1.49 g/L", "-114 °C",
                 "Pickling steel, pH control, digestion.",
                 "Corrosive; the vapour attacks the airway."),
        Compound("HNO3", "Nitric acid", "aqua fortis", "liquid", "1.51 g/cm³", "-42 °C",
                 "Fertiliser, explosives, etching.", "Strong oxidiser; stains skin yellow."),
        Compound("NaOH", "Sodium hydroxide", "caustic soda", "solid", "2.13 g/cm³", "318 °C",
                 "Soap, paper, drain cleaner.", "Severe burns; dissolving releases heat."),
        Compound("KOH", "Potassium hydroxide", "caustic potash", "solid", "2.04 g/cm³", "406 °C",
                 "Soft soap, batteries, biodiesel.", "Severe burns."),
        Compound("NaCl", "Sodium chloride", "osh tuzi", "solid", "2.17 g/cm³", "801 °C",
                 "Food, chlor-alkali feedstock, de-icing.", "None under normal use."),
        Compound("CaCO3", "Calcium carbonate", "limestone, chalk", "solid", "2.71 g/cm³", "decomposes 825 °C",
                 "Cement, antacids, filler.", "Dust irritates the lungs."),
        Compound("CaO", "Calcium oxide", "quicklime", "solid", "3.34 g/cm³", "2613 °C",
                 "Cement, steelmaking, soil treatment.", "Reacts with water, releasing heat."),
        Compound("Ca(OH)2", "Calcium hydroxide", "slaked lime", "solid", "2.21 g/cm³", "decomposes 580 °C",
                 "Mortar, water treatment, limewater test.", "Irritant to skin and eyes."),
        Compound("CO2", "Carbon dioxide", "", "gas", "1.98 g/L", "sublimes -78 °C",
                 "Carbonation, fire extinguishers, photosynthesis.",
                 "Asphyxiant in enclosed spaces."),
        Compound("CO", "Carbon monoxide", "", "gas", "1.14 g/L", "-205 °C",
                 "Reducing agent in smelting, syngas.",
                 "Odourless and fatal; binds haemoglobin."),
        Compound("NH3", "Ammonia", "", "gas", "0.73 g/L", "-78 °C",
                 "Fertiliser, refrigerant, cleaning.", "Pungent, corrosive to airways."),
        Compound("CH4", "Methane", "natural gas", "gas", "0.66 g/L", "-182 °C",
                 "Fuel, hydrogen production.", "Flammable; potent greenhouse gas."),
        Compound("C2H5OH", "Ethanol", "alcohol", "liquid", "0.789 g/cm³", "-114 °C",
                 "Solvent, fuel, disinfectant.", "Flammable; toxic in quantity."),
        Compound("C6H12O6", "Glucose", "dextrose", "solid", "1.54 g/cm³", "146 °C",
                 "Cellular fuel, fermentation feedstock.", "None under normal use."),
        Compound("H2O2", "Hydrogen peroxide", "", "liquid", "1.45 g/cm³", "-0.4 °C",
                 "Bleaching, disinfection, propellant.",
                 "Strong oxidiser; concentrated solutions burn."),
        Compound("O2", "Oxygen", "", "gas", "1.43 g/L", "-219 °C",
                 "Respiration, steelmaking, welding.", "Accelerates fire violently."),
        Compound("H2", "Hydrogen", "", "gas", "0.09 g/L", "-259 °C",
                 "Ammonia synthesis, fuel cells.", "Explosive over a wide range in air."),
        Compound("N2", "Nitrogen", "", "gas", "1.25 g/L", "-210 °C",
                 "Inert atmospheres, cryogenics.", "Asphyxiant in enclosed spaces."),
        Compound("Fe2O3", "Iron(III) oxide", "rust, haematite", "solid", "5.24 g/cm³", "1565 °C",
                 "Iron ore, pigment, thermite.", "Dust irritates the lungs."),
        Compound("FeO", "Iron(II) oxide", "wüstite", "solid", "5.75 g/cm³", "1377 °C",
                 "Pigment, ceramic glaze.", "Dust irritant."),
        Compound("Fe3O4", "Iron(II,III) oxide", "magnetite", "solid", "5.17 g/cm³", "1597 °C",
                 "Iron ore, magnetic recording, pigment.", "Dust irritant."),
        Compound("CuSO4", "Copper(II) sulfate", "blue vitriol (pentahydrate)", "solid",
                 "3.60 g/cm³", "decomposes 650 °C",
                 "Fungicide, electroplating, Fehling's test.", "Harmful if swallowed; toxic to fish."),
        Compound("AgNO3", "Silver nitrate", "lunar caustic", "solid", "4.35 g/cm³", "212 °C",
                 "Halide tests, photography, cauterisation.", "Corrosive; stains skin black."),
        Compound("AgCl", "Silver chloride", "", "solid", "5.56 g/cm³", "455 °C",
                 "Photographic emulsions, reference electrodes.",
                 "Darkens in light; low toxicity."),
        Compound("KMnO4", "Potassium permanganate", "", "solid", "2.70 g/cm³", "decomposes 240 °C",
                 "Titrations, water treatment, disinfectant.",
                 "Strong oxidiser; stains everything purple-brown."),
        Compound("K2Cr2O7", "Potassium dichromate", "", "solid", "2.68 g/cm³", "398 °C",
                 "Oxidising titrations, leather tanning.", "Carcinogenic; handle with care."),
        Compound("NaHCO3", "Sodium hydrogencarbonate", "osh sodasi", "solid", "2.20 g/cm³",
                 "decomposes 50 °C", "Baking, antacid, fire suppression.", "None under normal use."),
        Compound("Na2CO3", "Sodium carbonate", "washing soda, soda ash", "solid", "2.54 g/cm³",
                 "851 °C", "Glass, detergents, water softening.", "Irritant to eyes and skin."),
        Compound("SO2", "Sulfur dioxide", "", "gas", "2.63 g/L", "-72 °C",
                 "Sulfuric acid feedstock, preservative.",
                 "Chokes; triggers asthma; forms acid rain."),
        Compound("SO3", "Sulfur trioxide", "", "liquid", "1.92 g/cm³", "17 °C",
                 "Sulfuric acid manufacture.", "Violently hygroscopic; severe burns."),
        Compound("NO2", "Nitrogen dioxide", "", "gas", "1.88 g/L", "-11 °C",
                 "Nitric acid intermediate.", "Brown, toxic; damages lung tissue."),
        Compound("ZnCl2", "Zinc chloride", "", "solid", "2.91 g/cm³", "290 °C",
                 "Soldering flux, wood preservative.", "Corrosive."),
        Compound("MgO", "Magnesium oxide", "magnesia", "solid", "3.58 g/cm³", "2852 °C",
                 "Refractory bricks, antacids.", "Dust irritant."),
        Compound("Al2O3", "Aluminium oxide", "alumina, corundum", "solid", "3.99 g/cm³", "2072 °C",
                 "Aluminium smelting, abrasives, ceramics.", "Dust irritant."),
        Compound("CH3COOH", "Ethanoic acid", "acetic acid, vinegar", "liquid", "1.05 g/cm³", "17 °C",
                 "Vinegar, solvent, plastics.", "Corrosive when concentrated."),
        Compound("NH4Cl", "Ammonium chloride", "sal ammoniac", "solid", "1.53 g/cm³",
                 "sublimes 338 °C", "Dry cells, flux, fertiliser.", "Irritant."),
        Compound("BaSO4", "Barium sulfate", "", "solid", "4.49 g/cm³", "1580 °C",
                 "X-ray contrast, drilling mud, pigment.",
                 "Insoluble, so non-toxic — soluble barium salts are not."),
        Compound("PbI2", "Lead(II) iodide", "", "solid", "6.16 g/cm³", "402 °C",
                 "Golden-rain demonstration, detectors.", "Toxic; cumulative lead poison."),
    )
}


def normalise_key(formula: str) -> str:
    """Strip charge and hydrate notation to match the lookup table."""
    return re.sub(r"\^.*$", "", formula.strip())


def lookup(formula: str) -> Compound | None:
    """Find curated data for a formula, if it is in the table."""
    return COMPOUNDS.get(normalise_key(formula))


def search(term: str) -> list[Compound]:
    """Find compounds by formula, systematic name or common name."""
    term = term.strip().lower()
    if not term:
        return sorted(COMPOUNDS.values(), key=lambda c: c.name)
    return sorted(
        (
            compound
            for compound in COMPOUNDS.values()
            if term in compound.formula.lower()
            or term in compound.name.lower()
            or term in compound.common_name.lower()
        ),
        key=lambda c: c.name,
    )


def polyatomic_ions_in(formula: str) -> list[str]:
    """Polyatomic ions written intact inside a formula, longest first."""
    found: list[str] = []
    for ion in sorted(POLYATOMIC_IONS, key=len, reverse=True):
        if ion in formula and not any(ion in seen for seen in found):
            found.append(ion)
    return found


def name_from_formula(formula: str, composition: dict[str, int], charge: int = 0) -> str | None:
    """Apply the ordinary naming rules to a formula not in the table.

    Handles binary ionic compounds (with a Roman numeral where the metal has
    more than one common oxidation state) and binary covalent compounds
    (with Greek prefixes). Returns ``None`` when no rule applies.
    """
    known = lookup(formula)
    if known:
        return known.name
    if charge:
        ion = POLYATOMIC_IONS.get(normalise_key(formula))
        return ion[0].capitalize() if ion else None
    if len(composition) == 1:
        symbol = next(iter(composition))
        return ELEMENTS[symbol].name if symbol in ELEMENTS else None
    if len(composition) != 2:
        return _name_with_polyatomic(formula, composition)

    (first, first_count), (second, second_count) = _ordered_pair(composition)
    stem = _ANION_STEMS.get(second)
    if stem is None:
        return None
    anion = f"{stem}ide"
    if first in _METALS:
        cation = ELEMENTS[first].name
        states = ELEMENTS[first].oxidation_states
        if len(states) > 1:
            anion_charge = _anion_charge(second)
            if anion_charge:
                oxidation = abs(anion_charge) * second_count / first_count
                if oxidation == int(oxidation) and int(oxidation) in _ROMAN:
                    return f"{cation}({_ROMAN[int(oxidation)]}) {anion}"
        return f"{cation} {anion}"
    first_prefix = _PREFIXES[first_count] if first_count < len(_PREFIXES) else ""
    second_prefix = _PREFIXES[second_count] if second_count < len(_PREFIXES) else ""
    if first_prefix == "mono":
        first_prefix = ""
    head = f"{first_prefix}{ELEMENTS[first].name.lower()}"
    tail = f"{second_prefix}{anion}".replace("aox", "ox").replace("oox", "ox")
    return f"{head} {tail}".capitalize()


def _name_with_polyatomic(formula: str, composition: dict[str, int]) -> str | None:
    """Name a salt built from a metal and a recognised polyatomic ion."""
    match = re.match(r"^([A-Z][a-z]?)\d*", formula)
    if not match or match.group(1) not in _METALS:
        return None
    metal = match.group(1)
    remainder = formula[match.end():].strip("()")
    for ion, (ion_name, _) in POLYATOMIC_IONS.items():
        if remainder.startswith(ion) or remainder.strip("()0123456789") == ion:
            return f"{ELEMENTS[metal].name} {ion_name}"
    return None


def _ordered_pair(composition: dict[str, int]) -> list[tuple[str, int]]:
    """Cation-like element first, matching how formulas are written."""
    items = list(composition.items())
    if items[0][0] in _METALS or items[1][0] not in _METALS:
        return items
    return [items[1], items[0]]


def _anion_charge(symbol: str) -> int | None:
    element = ELEMENTS.get(symbol)
    if not element:
        return None
    negatives = [state for state in element.oxidation_states if state < 0]
    return negatives[0] if negatives else None
