"""Stoichiometry — mole calculations on a balanced equation."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.balancer import balancer
from components.parser import ParseError, parser
from components.stoichiometry import (
    MOLAR_VOLUME_RTP,
    MOLAR_VOLUME_STP,
    UNIT_LABELS,
    Amount,
    StoichiometryCalculator,
    StoichiometryError,
)
from components.ui import equation_card, page_header, stats
from utils.formatting import format_number

INPUT_KEY = "equation_input"

page_header(
    "Stoichiometry",
    "Give the amounts you start with. The coefficients do the rest: what runs out "
    "first, what is left over, and how much product you can expect.",
    eyebrow="Moles · Limiting reagent · Yield",
)

st.session_state.setdefault(INPUT_KEY, "H2 + O2 -> H2O")
source = st.text_input("Equation", key=INPUT_KEY)

if not source.strip():
    st.info("Enter an equation to begin.")
    st.stop()

try:
    equation = parser.parse_equation(source)
except ParseError as error:
    st.error(error.message)
    if error.suggestion:
        st.caption(f"Try: {error.suggestion}")
    st.stop()

result = balancer.balance(equation)
if not result.succeeded or not result.equation:
    st.error(result.message)
    st.stop()

balanced = result.equation
if result.status != "already_balanced":
    st.caption("Balanced first — mole ratios only mean something once it is.")
equation_card(balanced.display, label="Working from")

st.markdown("#### Conditions for gases")
condition_columns = st.columns([1, 1, 1])
with condition_columns[0]:
    basis = st.radio(
        "Molar volume",
        ["STP (0 °C, 1 atm)", "RTP (25 °C, 1 atm)", "Custom"],
        label_visibility="collapsed",
    )
if basis == "Custom":
    with condition_columns[1]:
        temperature = st.number_input("Temperature (°C)", value=25.0, step=5.0)
    with condition_columns[2]:
        pressure = st.number_input("Pressure (atm)", value=1.0, min_value=0.01, step=0.1)
    molar_volume = StoichiometryCalculator.molar_volume_at(temperature, pressure)
else:
    molar_volume = MOLAR_VOLUME_STP if basis.startswith("STP") else MOLAR_VOLUME_RTP
st.caption(f"1 mol of any gas occupies {format_number(molar_volume, 3)} L under these conditions.")

st.markdown("#### What you start with")
st.caption("Give an amount for every reactant to find the limiting one, or just one to scale from it.")

species_labels = [
    f"{item.formula.display} — {'reactant' if index < len(balanced.reactants) else 'product'}"
    for index, item in enumerate(balanced.species)
]

amounts: list[Amount] = []
count = st.number_input("How many amounts do you know?", min_value=1, max_value=6, value=1, step=1)
for slot in range(int(count)):
    row = st.columns([3, 2, 2, 2])
    with row[0]:
        choice = st.selectbox(
            "Species", species_labels, key=f"species-{slot}",
            index=min(slot, len(species_labels) - 1),
        )
    index = species_labels.index(choice)
    with row[1]:
        value = st.number_input("Amount", key=f"value-{slot}", value=10.0, min_value=0.0, step=1.0)
    with row[2]:
        unit = st.selectbox(
            "Unit", list(UNIT_LABELS), key=f"unit-{slot}",
            format_func=lambda key: UNIT_LABELS[key],
        )
    concentration = None
    with row[3]:
        if unit in {"L_solution", "mL_solution"}:
            concentration = st.number_input(
                "Concentration (mol/L)", key=f"conc-{slot}", value=1.0, min_value=0.0, step=0.1
            )
        else:
            st.caption(f"M = {format_number(balanced.species[index].formula.molar_mass, 3)} g/mol")
    amounts.append(Amount(index, value, unit, concentration))

yield_columns = st.columns([1, 3])
with yield_columns[0]:
    apply_yield = st.checkbox("Apply a percent yield")
percent = None
if apply_yield:
    with yield_columns[1]:
        percent = st.slider("Percent yield", 1.0, 100.0, 100.0, 0.5)

calculator = StoichiometryCalculator(molar_volume)
try:
    outcome = calculator.calculate(balanced, amounts, percent)
except StoichiometryError as error:
    st.error(str(error))
    st.stop()

st.divider()
st.markdown("#### Results")

if outcome.limiting:
    stats(
        [
            ("Limiting reagent", outcome.limiting.name),
            ("Reaction runs", f"{format_number(outcome.extent, 4)} ×"),
            ("Products formed", str(len(outcome.products))),
        ],
        accent="var(--copper)",
    )

table = pd.DataFrame(
    [
        {
            "Species": item.name,
            "Role": item.role,
            "Moles": round(item.moles, 5),
            "Mass (g)": round(item.mass, 4),
            "Gas volume (L)": round(item.gas_volume, 4) if item.gas_volume is not None else None,
            "Supplied (mol)": round(item.supplied_moles, 5) if item.supplied_moles is not None else None,
            "Left over (mol)": round(item.excess_moles, 5) if item.excess_moles is not None else None,
            "Limiting": "yes" if item.limiting else "",
        }
        for item in outcome.results
    ]
)
st.dataframe(table, width="stretch", hide_index=True)

excess = outcome.excess_reagents
if excess:
    st.markdown("**Left over when the reaction stops**")
    for item in excess:
        st.caption(
            f"{item.name}: {format_number(item.excess_moles or 0, 4)} mol "
            f"({format_number(item.excess_mass or 0, 4)} g) unreacted."
        )

for note in outcome.notes:
    st.caption(f"· {note}")

with st.expander("How this was worked out"):
    st.markdown(
        f"""
1. Each amount was converted to moles — mass ÷ molar mass, or volume ÷ {format_number(molar_volume, 3)} L/mol for a gas.
2. Each reactant's moles were divided by its coefficient. The smallest answer is how many times the reaction as written can run: **{format_number(outcome.extent, 5)}**.
3. That reactant is the limiting one; everything else is in excess by the difference.
4. Every other species was scaled from the same number, then converted back into grams or litres.
        """
    )
    st.caption(
        "Percent yield, when applied, scales the products only — it does not change "
        "how much reactant was consumed."
    )
