"""The periodic table, as data.

Only the facts that cannot be derived are stored (symbol, name, standard
atomic weight, common oxidation states). Period, group, block, category and
ground-state electron configuration are all computed, which keeps the table
short enough to audit by eye.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Final

# (atomic number, symbol, name, standard atomic weight)
_RAW: Final[tuple[tuple[int, str, str, float], ...]] = (
    (1, "H", "Hydrogen", 1.008), (2, "He", "Helium", 4.0026),
    (3, "Li", "Lithium", 6.94), (4, "Be", "Beryllium", 9.0122),
    (5, "B", "Boron", 10.81), (6, "C", "Carbon", 12.011),
    (7, "N", "Nitrogen", 14.007), (8, "O", "Oxygen", 15.999),
    (9, "F", "Fluorine", 18.998), (10, "Ne", "Neon", 20.180),
    (11, "Na", "Sodium", 22.990), (12, "Mg", "Magnesium", 24.305),
    (13, "Al", "Aluminium", 26.982), (14, "Si", "Silicon", 28.085),
    (15, "P", "Phosphorus", 30.974), (16, "S", "Sulfur", 32.06),
    (17, "Cl", "Chlorine", 35.45), (18, "Ar", "Argon", 39.95),
    (19, "K", "Potassium", 39.098), (20, "Ca", "Calcium", 40.078),
    (21, "Sc", "Scandium", 44.956), (22, "Ti", "Titanium", 47.867),
    (23, "V", "Vanadium", 50.942), (24, "Cr", "Chromium", 51.996),
    (25, "Mn", "Manganese", 54.938), (26, "Fe", "Iron", 55.845),
    (27, "Co", "Cobalt", 58.933), (28, "Ni", "Nickel", 58.693),
    (29, "Cu", "Copper", 63.546), (30, "Zn", "Zinc", 65.38),
    (31, "Ga", "Gallium", 69.723), (32, "Ge", "Germanium", 72.630),
    (33, "As", "Arsenic", 74.922), (34, "Se", "Selenium", 78.971),
    (35, "Br", "Bromine", 79.904), (36, "Kr", "Krypton", 83.798),
    (37, "Rb", "Rubidium", 85.468), (38, "Sr", "Strontium", 87.62),
    (39, "Y", "Yttrium", 88.906), (40, "Zr", "Zirconium", 91.224),
    (41, "Nb", "Niobium", 92.906), (42, "Mo", "Molybdenum", 95.95),
    (43, "Tc", "Technetium", 98.0), (44, "Ru", "Ruthenium", 101.07),
    (45, "Rh", "Rhodium", 102.91), (46, "Pd", "Palladium", 106.42),
    (47, "Ag", "Silver", 107.87), (48, "Cd", "Cadmium", 112.41),
    (49, "In", "Indium", 114.82), (50, "Sn", "Tin", 118.71),
    (51, "Sb", "Antimony", 121.76), (52, "Te", "Tellurium", 127.60),
    (53, "I", "Iodine", 126.90), (54, "Xe", "Xenon", 131.29),
    (55, "Cs", "Caesium", 132.91), (56, "Ba", "Barium", 137.33),
    (57, "La", "Lanthanum", 138.91), (58, "Ce", "Cerium", 140.12),
    (59, "Pr", "Praseodymium", 140.91), (60, "Nd", "Neodymium", 144.24),
    (61, "Pm", "Promethium", 145.0), (62, "Sm", "Samarium", 150.36),
    (63, "Eu", "Europium", 151.96), (64, "Gd", "Gadolinium", 157.25),
    (65, "Tb", "Terbium", 158.93), (66, "Dy", "Dysprosium", 162.50),
    (67, "Ho", "Holmium", 164.93), (68, "Er", "Erbium", 167.26),
    (69, "Tm", "Thulium", 168.93), (70, "Yb", "Ytterbium", 173.05),
    (71, "Lu", "Lutetium", 174.97), (72, "Hf", "Hafnium", 178.49),
    (73, "Ta", "Tantalum", 180.95), (74, "W", "Tungsten", 183.84),
    (75, "Re", "Rhenium", 186.21), (76, "Os", "Osmium", 190.23),
    (77, "Ir", "Iridium", 192.22), (78, "Pt", "Platinum", 195.08),
    (79, "Au", "Gold", 196.97), (80, "Hg", "Mercury", 200.59),
    (81, "Tl", "Thallium", 204.38), (82, "Pb", "Lead", 207.2),
    (83, "Bi", "Bismuth", 208.98), (84, "Po", "Polonium", 209.0),
    (85, "At", "Astatine", 210.0), (86, "Rn", "Radon", 222.0),
    (87, "Fr", "Francium", 223.0), (88, "Ra", "Radium", 226.0),
    (89, "Ac", "Actinium", 227.0), (90, "Th", "Thorium", 232.04),
    (91, "Pa", "Protactinium", 231.04), (92, "U", "Uranium", 238.03),
    (93, "Np", "Neptunium", 237.0), (94, "Pu", "Plutonium", 244.0),
    (95, "Am", "Americium", 243.0), (96, "Cm", "Curium", 247.0),
    (97, "Bk", "Berkelium", 247.0), (98, "Cf", "Californium", 251.0),
    (99, "Es", "Einsteinium", 252.0), (100, "Fm", "Fermium", 257.0),
    (101, "Md", "Mendelevium", 258.0), (102, "No", "Nobelium", 259.0),
    (103, "Lr", "Lawrencium", 266.0), (104, "Rf", "Rutherfordium", 267.0),
    (105, "Db", "Dubnium", 268.0), (106, "Sg", "Seaborgium", 269.0),
    (107, "Bh", "Bohrium", 270.0), (108, "Hs", "Hassium", 269.0),
    (109, "Mt", "Meitnerium", 278.0), (110, "Ds", "Darmstadtium", 281.0),
    (111, "Rg", "Roentgenium", 282.0), (112, "Cn", "Copernicium", 285.0),
    (113, "Nh", "Nihonium", 286.0), (114, "Fl", "Flerovium", 289.0),
    (115, "Mc", "Moscovium", 290.0), (116, "Lv", "Livermorium", 293.0),
    (117, "Ts", "Tennessine", 294.0), (118, "Og", "Oganesson", 294.0),
)

#: Oxidation states seen in ordinary chemistry; the most common one first.
_OXIDATION_STATES: Final[dict[str, tuple[int, ...]]] = {
    "H": (1, -1), "He": (), "Li": (1,), "Be": (2,), "B": (3,),
    "C": (4, 2, -4), "N": (-3, 5, 4, 3, 2, -2), "O": (-2, -1),
    "F": (-1,), "Ne": (), "Na": (1,), "Mg": (2,), "Al": (3,),
    "Si": (4, -4), "P": (5, 3, -3), "S": (-2, 4, 6), "Cl": (-1, 1, 3, 5, 7),
    "Ar": (), "K": (1,), "Ca": (2,), "Sc": (3,), "Ti": (4, 3),
    "V": (5, 4, 3, 2), "Cr": (3, 6, 2), "Mn": (2, 4, 7, 6, 3),
    "Fe": (3, 2), "Co": (2, 3), "Ni": (2, 3), "Cu": (2, 1), "Zn": (2,),
    "Ga": (3,), "Ge": (4, 2), "As": (3, 5, -3), "Se": (-2, 4, 6),
    "Br": (-1, 1, 5), "Kr": (2,), "Rb": (1,), "Sr": (2,), "Y": (3,),
    "Zr": (4,), "Nb": (5,), "Mo": (6, 4), "Tc": (7,), "Ru": (3, 4),
    "Rh": (3,), "Pd": (2, 4), "Ag": (1,), "Cd": (2,), "In": (3,),
    "Sn": (2, 4), "Sb": (3, 5), "Te": (-2, 4, 6), "I": (-1, 1, 5, 7),
    "Xe": (2, 4, 6), "Cs": (1,), "Ba": (2,), "La": (3,), "Ce": (3, 4),
    "W": (6, 4), "Pt": (2, 4), "Au": (3, 1), "Hg": (2, 1), "Tl": (1, 3),
    "Pb": (2, 4), "Bi": (3, 5), "Ra": (2,), "Th": (4,), "U": (6, 4),
}

#: Everyday context, kept to one line each.
_USES: Final[dict[str, str]] = {
    "H": "Ammonia synthesis, refining, fuel cells.",
    "He": "Cryogenics, MRI magnets, lifting gas.",
    "Li": "Rechargeable batteries, ceramics, mood stabilisers.",
    "C": "Steel, plastics, every organic molecule.",
    "N": "Fertiliser, inert atmospheres, liquid coolant.",
    "O": "Steelmaking, medicine, combustion.",
    "F": "Toothpaste additives, refrigerants, PTFE.",
    "Na": "Table salt, street lighting, sodium-vapour lamps.",
    "Mg": "Lightweight alloys, flares, chlorophyll.",
    "Al": "Aircraft, packaging, power cables.",
    "Si": "Semiconductors, glass, silicones.",
    "P": "Fertiliser, matches, DNA backbone.",
    "S": "Sulfuric acid, vulcanised rubber, fungicides.",
    "Cl": "Water treatment, PVC, bleach.",
    "K": "Fertiliser, glass, nerve signalling.",
    "Ca": "Cement, bone, steel deoxidation.",
    "Ti": "Implants, aerospace alloys, white pigment.",
    "Cr": "Stainless steel, plating, pigments.",
    "Mn": "Steel hardening, dry cells, permanganate.",
    "Fe": "Steel, haemoglobin, catalysts.",
    "Ni": "Stainless steel, plating, hydrogenation catalyst.",
    "Cu": "Wiring, plumbing, brass and bronze.",
    "Zn": "Galvanising, brass, dietary enzyme cofactor.",
    "Br": "Flame retardants, photographic film, sedatives.",
    "Ag": "Electronics, photography, antimicrobials.",
    "I": "Antiseptics, thyroid hormones, contrast media.",
    "Pt": "Catalytic converters, jewellery, electrodes.",
    "Au": "Electronics contacts, jewellery, dentistry.",
    "Hg": "Fluorescent lamps, older thermometers, amalgams.",
    "Pb": "Car batteries, radiation shielding, older solders.",
    "U": "Nuclear fuel, radiography sources.",
}

_CONFIG_EXCEPTIONS: Final[dict[int, str]] = {
    24: "[Ar] 3d5 4s1", 29: "[Ar] 3d10 4s1", 41: "[Kr] 4d4 5s1",
    42: "[Kr] 4d5 5s1", 44: "[Kr] 4d7 5s1", 45: "[Kr] 4d8 5s1",
    46: "[Kr] 4d10", 47: "[Kr] 4d10 5s1", 57: "[Xe] 5d1 6s2",
    58: "[Xe] 4f1 5d1 6s2", 64: "[Xe] 4f7 5d1 6s2", 78: "[Xe] 4f14 5d9 6s1",
    79: "[Xe] 4f14 5d10 6s1", 89: "[Rn] 6d1 7s2", 90: "[Rn] 6d2 7s2",
    91: "[Rn] 5f2 6d1 7s2", 92: "[Rn] 5f3 6d1 7s2", 93: "[Rn] 5f4 6d1 7s2",
    96: "[Rn] 5f7 6d1 7s2", 103: "[Rn] 5f14 7s2 7p1",
}

_NOBLE_GASES: Final[tuple[tuple[int, str], ...]] = (
    (86, "Rn"), (54, "Xe"), (36, "Kr"), (18, "Ar"), (10, "Ne"), (2, "He"),
)

# Madelung (n + l) filling order.
_ORBITAL_ORDER: Final[tuple[tuple[int, str, int], ...]] = (
    (1, "s", 2), (2, "s", 2), (2, "p", 6), (3, "s", 2), (3, "p", 6),
    (4, "s", 2), (3, "d", 10), (4, "p", 6), (5, "s", 2), (4, "d", 10),
    (5, "p", 6), (6, "s", 2), (4, "f", 14), (5, "d", 10), (6, "p", 6),
    (7, "s", 2), (5, "f", 14), (6, "d", 10), (7, "p", 6),
)

_METALLOIDS: Final[frozenset[str]] = frozenset({"B", "Si", "Ge", "As", "Sb", "Te", "Po", "At"})
_NONMETALS: Final[frozenset[str]] = frozenset({"H", "C", "N", "O", "P", "S", "Se"})
_POST_TRANSITION: Final[frozenset[str]] = frozenset(
    {"Al", "Ga", "In", "Sn", "Tl", "Pb", "Bi", "Nh", "Fl", "Mc", "Lv"}
)


@dataclass(frozen=True, slots=True)
class Element:
    """One entry of the periodic table."""

    number: int
    symbol: str
    name: str
    mass: float
    period: int
    group: int | None
    block: str
    category: str
    row: int
    column: int
    oxidation_states: tuple[int, ...] = ()
    uses: str = ""
    _config: str = field(default="", repr=False)

    @property
    def electron_configuration(self) -> str:
        """Ground-state configuration in noble-gas shorthand."""
        return self._config

    @property
    def valence_electrons(self) -> int | None:
        """Outer-shell electron count, for main-group elements only."""
        if self.group is None or 3 <= self.group <= 12:
            return None
        return self.group if self.group <= 2 else self.group - 10

    @property
    def common_oxidation_state(self) -> int | None:
        return self.oxidation_states[0] if self.oxidation_states else None


def _full_configuration(number: int) -> list[tuple[int, str, int]]:
    remaining = number
    shells: list[tuple[int, str, int]] = []
    for shell, orbital, capacity in _ORBITAL_ORDER:
        if remaining <= 0:
            break
        filled = min(capacity, remaining)
        shells.append((shell, orbital, filled))
        remaining -= filled
    return shells


def _configuration(number: int) -> str:
    if number in _CONFIG_EXCEPTIONS:
        return _CONFIG_EXCEPTIONS[number]
    core_symbol = ""
    core_number = 0
    for noble_number, noble_symbol in _NOBLE_GASES:
        if number > noble_number:
            core_symbol, core_number = noble_symbol, noble_number
            break
    shells = _full_configuration(number)
    consumed = 0
    kept: list[tuple[int, str, int]] = []
    for shell, orbital, filled in shells:
        consumed += filled
        if consumed <= core_number:
            continue
        kept.append((shell, orbital, filled))
    # Written by shell rather than by filling order: [Ar] 3d6 4s2, not 4s2 3d6.
    kept.sort(key=lambda item: (item[0], "spdf".index(item[1])))
    prefix = f"[{core_symbol}] " if core_symbol else ""
    return prefix + " ".join(f"{shell}{orbital}{filled}" for shell, orbital, filled in kept)


def _position(number: int) -> tuple[int, int, int, int | None]:
    """Return ``(period, row, column, group)`` on an 18-column layout.

    Lanthanides and actinides are given their own rows (8 and 9) so the
    main body of the table stays 18 columns wide.
    """
    if 57 <= number <= 71:
        return 6, 8, number - 57 + 3, None
    if 89 <= number <= 103:
        return 7, 9, number - 89 + 3, None
    if number <= 2:
        return 1, 1, 1 if number == 1 else 18, 1 if number == 1 else 18
    if number <= 10:
        column = number - 2 if number <= 4 else number + 8
        return 2, 2, column, column
    if number <= 18:
        column = number - 10 if number <= 12 else number
        return 3, 3, column, column
    if number <= 36:
        return 4, 4, number - 18, number - 18
    if number <= 54:
        return 5, 5, number - 36, number - 36
    if number <= 86:
        column = number - 54 if number <= 56 else number - 68
        return 6, 6, column, column
    column = number - 86 if number <= 88 else number - 100
    return 7, 7, column, column


def _block(number: int, group: int | None) -> str:
    if group is None:
        return "f"
    if group <= 2 and number != 2:
        return "s"
    if 3 <= group <= 12:
        return "d"
    return "s" if number == 2 else "p"


def _category(symbol: str, number: int, group: int | None, block: str) -> str:
    if block == "f":
        return "lantanoid" if number <= 71 else "aktinoid"
    if group == 18:
        return "asil gaz"
    if group == 17:
        return "galogen"
    if group == 1 and symbol != "H":
        return "ishqoriy metall"
    if group == 2:
        return "ishqoriy-yer metall"
    if symbol in _METALLOIDS:
        return "metalloid"
    if symbol in _NONMETALS:
        return "metallmas"
    if symbol in _POST_TRANSITION:
        return "o'tish metallidan keyingi metall"
    if block == "d":
        return "o'tish metalli"
    return "metallmas"


def _build() -> dict[str, Element]:
    table: dict[str, Element] = {}
    for number, symbol, name, mass in _RAW:
        period, row, column, group = _position(number)
        block = _block(number, group)
        table[symbol] = Element(
            number=number,
            symbol=symbol,
            name=name,
            mass=mass,
            period=period,
            group=group,
            block=block,
            category=_category(symbol, number, group, block),
            row=row,
            column=column,
            oxidation_states=_OXIDATION_STATES.get(symbol, ()),
            uses=_USES.get(symbol, ""),
            _config=_configuration(number),
        )
    return table


ELEMENTS: Final[dict[str, Element]] = _build()
SYMBOLS: Final[frozenset[str]] = frozenset(ELEMENTS)
BY_NUMBER: Final[dict[int, Element]] = {e.number: e for e in ELEMENTS.values()}
CATEGORY_ORDER: Final[tuple[str, ...]] = (
    "ishqoriy metall", "ishqoriy-yer metall", "o'tish metalli",
    "o'tish metallidan keyingi metall", "metalloid", "metallmas", "galogen",
    "asil gaz", "lantanoid", "aktinoid",
)


def get(symbol: str) -> Element | None:
    """Look up an element by its exact symbol."""
    return ELEMENTS.get(symbol)


@lru_cache(maxsize=512)
def resolve_case(token: str) -> str | None:
    """Find the correctly cased symbol for a miscased token (``fe`` → ``Fe``)."""
    lowered = token.lower()
    for symbol in ELEMENTS:
        if symbol.lower() == lowered:
            return symbol
    return None


def search(term: str) -> list[Element]:
    """Find elements by symbol, name or atomic number."""
    term = term.strip().lower()
    if not term:
        return sorted(ELEMENTS.values(), key=lambda e: e.number)
    if term.isdigit():
        element = BY_NUMBER.get(int(term))
        return [element] if element else []
    return sorted(
        (e for e in ELEMENTS.values() if term in e.symbol.lower() or term in e.name.lower()),
        key=lambda e: e.number,
    )
