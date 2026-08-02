"""Periodic table — click any element for its data."""

from __future__ import annotations

import html

import streamlit as st

from components.ui import CATEGORY_COLORS, category_legend, page_header, stats
from data.elements import BY_NUMBER, ELEMENTS, Element, search
from utils.formatting import format_number

page_header(
    "Davriy jadval",
    "Har bir element elektronlar joylashishiga ko'ra tartiblangan. "
    "Ma'lumotlarini ko'rish uchun katakchani bosing.",
    eyebrow="118 ta element",
)

selected_symbol = st.query_params.get("element", "H")
if selected_symbol not in ELEMENTS:
    selected_symbol = "H"


def _cell(element: Element, selected: str) -> str:
    color = CATEGORY_COLORS.get(element.category, "#5A8FD8")
    classes = "cell selected" if element.symbol == selected else "cell"
    return (
        f'<a class="{classes}" href="?element={element.symbol}" target="_self" '
        f'style="background:{color}1F;border-color:{color}66;color:{color};'
        f'text-decoration:none;" title="{html.escape(element.name)}">'
        f'<span class="z">{element.number}</span>'
        f'<span class="s">{element.symbol}</span></a>'
    )


def render_table(selected: str) -> str:
    """Build the 18-column grid, f-block on its own two rows."""
    positions = {(element.row, element.column): element for element in ELEMENTS.values()}
    cells: list[str] = []
    for row in range(1, 10):
        if row == 8:
            cells.append('<div class="cell gap" style="grid-column: span 18"></div>')
        for column in range(1, 19):
            element = positions.get((row, column))
            cells.append(_cell(element, selected) if element else '<div class="cell gap"></div>')
    return f'<div class="ptable">{"".join(cells)}</div>'


st.markdown(render_table(selected_symbol), unsafe_allow_html=True)
category_legend()

st.divider()

detail_columns = st.columns([2, 3], gap="large")
element = ELEMENTS[selected_symbol]

with detail_columns[0]:
    color = CATEGORY_COLORS.get(element.category, "#5A8FD8")
    st.markdown(
        f"""<div class="equation-card" style="border-left-color:{color}">
        <div class="label">{html.escape(element.category)}</div>
        <div class="formula" style="font-size:2.4rem;line-height:1.1">{element.symbol}</div>
        <div style="font-family:var(--display);font-size:1.15rem;margin-top:0.2rem">
        {html.escape(element.name)}</div>
        <div style="color:var(--muted);font-family:var(--mono);font-size:0.8rem;margin-top:0.3rem">
        Z = {element.number} · {element.period}-davr ·
        {element.group + "-guruh" if element.group else "f-blok"} ·
        {element.block}-blok</div></div>""",
        unsafe_allow_html=True,
    )
    finder = st.text_input("Element izlash", placeholder="temir, Fe yoki 26")
    if finder:
        matches = search(finder)[:12]
        if not matches:
            st.caption("Hech narsa topilmadi.")
        for match in matches:
            st.markdown(
                f'<a href="?element={match.symbol}" target="_self" '
                f'style="color:var(--copper);text-decoration:none;font-family:var(--mono);'
                f'font-size:0.85rem">{match.number} · {match.symbol} — {html.escape(match.name)}</a>',
                unsafe_allow_html=True,
            )

with detail_columns[1]:
    stats(
        [
            ("Atom raqami", str(element.number)),
            ("Atom massasi", f"{format_number(element.mass, 4)}"),
            ("Valent elektronlari", str(element.valence_electrons) if element.valence_electrons else "—"),
            ("Asosiy holati", f"{element.common_oxidation_state:+d}" if element.common_oxidation_state else "—"),
        ]
    )
    st.markdown("**Elektron konfiguratsiya**")
    st.code(element.electron_configuration, language=None)
    st.markdown("**Oksidlanish darajalari**")
    if element.oxidation_states:
        st.caption(
            ", ".join(f"{state:+d}" for state in element.oxidation_states)
            + "  — birinchisi siz eng ko'p uchratadigani."
        )
    else:
        st.caption("Asosiy oksidlanish darajalari yo'q — bu element odatda birikmalar hosil qilmaydi.")
    if element.uses:
        st.markdown("**Qayerda ishlatiladi/uchraydi**")
        st.caption(element.uses)

    neighbours = [
        BY_NUMBER.get(element.number - 1),
        BY_NUMBER.get(element.number + 1),
    ]
    links = " · ".join(
        f'<a href="?element={item.symbol}" target="_self" style="color:var(--muted);'
        f'text-decoration:none">{item.symbol} {html.escape(item.name)}</a>'
        for item in neighbours
        if item
    )
    if links:
        st.markdown(
            f'<div style="margin-top:0.8rem;font-family:var(--mono);font-size:0.78rem">'
            f"Yaqinida: {links}</div>",
            unsafe_allow_html=True,
        )
