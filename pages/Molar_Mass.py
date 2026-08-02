"""Molar mass — element-by-element breakdown of any formula."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.ui import equation_card, findings, page_header, stats
from components.validator import formula_validator
from data.compounds import name_from_formula
from data.elements import ELEMENTS
from utils.formatting import format_number

FORMULA_KEY = "molar_mass_formula"

page_header(
    "Molar mass",
    "One formula in, the full arithmetic out: what each element contributes, "
    "and what fraction of the mass it accounts for.",
    eyebrow="g/mol",
)

st.session_state.setdefault(FORMULA_KEY, "Ca(OH)2")
column_input, column_examples = st.columns([2, 3], gap="large")

with column_input:
    formula_text = st.text_input("Formula", key=FORMULA_KEY, placeholder="Ca(OH)2")
with column_examples:
    st.caption("Quick picks")
    picks = ("H2SO4", "Ca(OH)2", "C6H12O6", "Al2(SO4)3", "CuSO4*5H2O", "KMnO4")
    pick_columns = st.columns(len(picks))
    for column, pick in zip(pick_columns, picks):
        with column:
            st.button(
                pick,
                key=f"pick-{pick}",
                on_click=lambda value=pick: st.session_state.update({FORMULA_KEY: value}),
                width="stretch",
            )

if not formula_text.strip():
    st.info("Enter a formula.")
    st.stop()

formula, issues = formula_validator.validate(formula_text)
if formula is None:
    findings(issues)
    st.stop()

name = name_from_formula(formula.raw, formula.composition, formula.charge)
equation_card(formula.display, label=name or "Formula")

stats(
    [
        ("Molar mass", f"{format_number(formula.molar_mass, 4)} g/mol"),
        ("Atoms per unit", str(formula.atom_count)),
        ("Distinct elements", str(len(formula.composition))),
        ("Charge", f"{formula.charge:+d}" if formula.charge else "neutral"),
    ],
    accent="var(--copper)",
)

rows = formula.mass_contributions()
table = pd.DataFrame(
    [
        {
            "Element": f"{symbol} — {ELEMENTS[symbol].name}",
            "Atoms": count,
            "Atomic mass": round(ELEMENTS[symbol].mass, 4),
            "Contribution (g/mol)": round(subtotal, 4),
            "Percent by mass": f"{percent:.2f}%",
        }
        for symbol, count, subtotal, percent in rows
    ]
)
st.dataframe(table, width="stretch", hide_index=True)

st.markdown("#### The arithmetic")
lines = [
    f"{symbol}:  {count} × {format_number(ELEMENTS[symbol].mass, 4)}  =  {format_number(subtotal, 4)}"
    for symbol, count, subtotal, _ in rows
]
lines.append("─" * 34)
lines.append(f"Total:  {format_number(formula.molar_mass, 4)} g/mol")
st.code("\n".join(lines), language=None)

st.markdown("#### Mass and moles")
convert_columns = st.columns(3)
with convert_columns[0]:
    grams = st.number_input("Mass (g)", value=10.0, min_value=0.0, step=1.0)
    st.caption(f"= {format_number(grams / formula.molar_mass, 5)} mol")
with convert_columns[1]:
    moles = st.number_input("Amount (mol)", value=1.0, min_value=0.0, step=0.1)
    st.caption(f"= {format_number(moles * formula.molar_mass, 4)} g")
with convert_columns[2]:
    st.number_input("Particles (×10²³)", value=6.022, min_value=0.0, step=0.1, key="particles")
    particles = st.session_state["particles"]
    st.caption(f"= {format_number(particles / 6.02214076, 5)} mol")

findings([issue for issue in issues if issue.level != "success"])
