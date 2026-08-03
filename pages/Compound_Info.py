"""Birikma haqida — formula nima ekani va nimaga ishlatilishi."""

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
    "Birikma haqida",
    "Formula yoki nomi bo'yicha qidiring. Ma'lumotnomadagi yozuvlarda xossalar va "
    "xavflar bor; qolganlari oddiy qoidalar asosida nomlanadi.",
    eyebrow="Ma'lumotnoma",
)

st.session_state.setdefault(QUERY_KEY, "H2SO4")
term = st.text_input("Formula yoki nomi", key=QUERY_KEY, placeholder="H2SO4, sulfat kislota, ichimlik sodasi")

if not term.strip():
    st.info("Formula yoki nom yozing.")
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
        ("Molyar massa", f"{format_number(parsed.molar_mass, 3)} g/mol"),
        ("Birlikdagi atomlar", str(parsed.atom_count)),
    ]
    if compound:
        entries.extend(
            [("Holati", compound.state or "—"), ("Zichligi", compound.density or "—")]
        )
    stats(entries, accent="var(--copper)")

if compound:
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**Sistematik nomi**")
        st.caption(compound.name)
        if compound.common_name:
            st.markdown("**Yana shunday ataladi**")
            st.caption(compound.common_name)
        if compound.melting_point:
            st.markdown("**Suyuqlanish harorati**")
            st.caption(compound.melting_point)
    with right:
        if compound.uses:
            st.markdown("**Nimaga ishlatiladi**")
            st.caption(compound.uses)
        if compound.hazards:
            st.markdown("**Ehtiyot choralari va xavflari**")
            st.warning(compound.hazards, icon="⚠")
else:
    st.caption(
        "Ma'lumotnoma jadvalida yo'q. Yuqoridagi nom standart nomlash qoidalari asosida "
        "olingan, molyar massa esa formuladan hisoblangan."
    )

if parsed:
    st.divider()
    st.markdown("#### Tarkibi")
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
        st.markdown("#### Ichidagi ionlar")
        for ion in ions:
            name, charge = POLYATOMIC_IONS[ion]
            st.caption(f"{ion} — {name}, zaryadi {charge:+d}. Uni bitta birlik sifatida tenglashtiring.")

if len(matches) > 1:
    st.divider()
    st.markdown("#### Boshqa mos kelganlari")
    for other in matches[1:9]:
        st.markdown(
            f"`{other.formula}` — {other.name}"
            + (f" ({other.common_name})" if other.common_name else "")
        )

with st.expander(f"Ma'lumotnomadagi {len(COMPOUNDS)} ta birikmani ko'rish"):
    for entry in sorted(COMPOUNDS.values(), key=lambda item: item.name):
        st.markdown(f"`{entry.formula}` — {entry.name}")
