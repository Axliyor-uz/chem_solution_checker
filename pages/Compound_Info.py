"""Compound info — what a formula is, and what it is for."""

from __future__ import annotations

import html

import streamlit as st

from components.parser import ParseError, parser
from components.ui import equation_card, page_header, stats
from data.compounds import (
    COMPOUNDS,
    POLYATOMIC_IONS,
    lookup,
    name_from_formula,
    polyatomic_ions_in,
    search,
)
from data.elements import ELEMENTS
from utils.formatting import format_number

QUERY_KEY = "compound_query"

page_header(
    "Compound info",
    "Search by formula or by name. Curated entries carry properties and hazards; "
    "anything else is named from the ordinary rules.",
    eyebrow="Reference",
)

st.session_state.setdefault(QUERY_KEY, "H2SO4")
term = st.text_input("Formula or name", key=QUERY_KEY, placeholder="H2SO4, sulfuric acid, baking soda")

if not term.strip():
    st.info("Type a formula or a name.")
    st.stop()

matches = search(term)
compound = lookup(term) or (matches[0] if matches else None)

parsed = None
try:
    parsed = parser.parse_formula(compound.formula if compound else term)
except ParseError as error:
    if not compound:
        st.error(error.message)
        st.stop()

if parsed:
    derived_name = name_from_formula(parsed.raw, parsed.composition, parsed.charge)
    equation_card(parsed.display, label=(compound.name if compound else derived_name) or "Formula")
    entries = [
        ("Molar mass", f"{format_number(parsed.molar_mass, 3)} g/mol"),
        ("Atoms per unit", str(parsed.atom_count)),
    ]
    if compound:
        entries.extend(
            [("State", compound.state or "—"), ("Density", compound.density or "—")]
        )
    stats(entries, accent="var(--copper)")

if compound:
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**Systematic name**")
        st.caption(compound.name)
        if compound.common_name:
            st.markdown("**Also called**")
            st.caption(compound.common_name)
        if compound.melting_point:
            st.markdown("**Melting point**")
            st.caption(compound.melting_point)
    with right:
        if compound.uses:
            st.markdown("**What it is used for**")
            st.caption(compound.uses)
        if compound.hazards:
            st.markdown("**Handling and hazards**")
            st.warning(compound.hazards, icon="⚠")
else:
    st.caption(
        "Not in the reference table. The name above comes from the standard naming "
        "rules, and the molar mass is computed from the formula."
    )

if parsed:
    st.divider()
    st.markdown("#### What it is made of")
    composition_columns = st.columns(min(len(parsed.composition), 6) or 1)
    for column, (symbol, count) in zip(composition_columns, sorted(parsed.composition.items())):
        element = ELEMENTS[symbol]
        share = element.mass * count / parsed.molar_mass * 100
        with column:
            st.markdown(
                f'<div class="stat"><div class="k">{symbol} × {count}</div>'
                f'<div class="v">{share:.1f}%</div>'
                f'<div class="k" style="margin-top:0.2rem">{html.escape(element.name)}</div></div>',
                unsafe_allow_html=True,
            )

    ions = [ion for ion in polyatomic_ions_in(parsed.raw) if ion in POLYATOMIC_IONS]
    if ions and len(parsed.composition) > 2:
        st.markdown("#### Ions inside it")
        for ion in ions:
            name, charge = POLYATOMIC_IONS[ion]
            st.caption(f"{ion} — {name}, charge {charge:+d}. Balance it as one unit.")

if len(matches) > 1:
    st.divider()
    st.markdown("#### Other matches")
    for other in matches[1:9]:
        st.markdown(
            f"`{other.formula}` — {other.name}"
            + (f" ({other.common_name})" if other.common_name else "")
        )

with st.expander(f"Browse all {len(COMPOUNDS)} reference compounds"):
    for entry in sorted(COMPOUNDS.values(), key=lambda item: item.name):
        st.markdown(f"`{entry.formula}` — {entry.name}")
