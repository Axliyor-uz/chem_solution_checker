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
    "Stexiometriya",
    "Boshlang'ich miqdorlarni kiriting. Koeffitsiyentlar qolganini bajaradi: "
    "nima birinchi tugaydi, nima ortib qoladi va qancha mahsulot hosil bo'ladi.",
    eyebrow="Mollar · Cheklovchi reagent · Unumdorlik",
)

st.session_state.setdefault(INPUT_KEY, "H2 + O2 -> H2O")
source = st.text_input("Tenglama", key=INPUT_KEY)

if not source.strip():
    st.info("Boshlash uchun tenglama kiriting.")
    st.stop()

try:
    equation = parser.parse_equation(source)
except ParseError as error:
    st.error(error.message)
    if error.suggestion:
        st.caption(f"Sinab ko'ring: {error.suggestion}")
    st.stop()

result = balancer.balance(equation)
if not result.succeeded or not result.equation:
    st.error(result.message)
    st.stop()

balanced = result.equation
if result.status != "already_balanced":
    st.caption("Avval tenglashtirildi — mol nisbatlari faqat shundagina hisoblanadi.")
equation_card(balanced.display, label="Shundan kelib chiqib")

st.markdown("#### Gazlar uchun sharoitlar")
condition_columns = st.columns([1, 1, 1])
with condition_columns[0]:
    basis = st.radio(
        "Molyar hajm",
        ["STP (0 °C, 1 atm)", "RTP (25 °C, 1 atm)", "Boshqa"],
        label_visibility="collapsed",
    )
if basis == "Boshqa":
    with condition_columns[1]:
        temperature = st.number_input("Harorat (°C)", value=25.0, step=5.0)
    with condition_columns[2]:
        pressure = st.number_input("Bosim (atm)", value=1.0, min_value=0.01, step=0.1)
    molar_volume = StoichiometryCalculator.molar_volume_at(temperature, pressure)
else:
    molar_volume = MOLAR_VOLUME_STP if basis.startswith("STP") else MOLAR_VOLUME_RTP
st.caption(f"Bu sharoitda har qanday gazning 1 moli {format_number(molar_volume, 3)} L hajmni egallaydi.")

st.markdown("#### Boshlang'ich miqdorlar")
st.caption("Cheklovchi reagentni topish uchun har bir reaktivning miqdorini bering yoki faqat bittasini kiritib hisoblang.")

species_labels = [
    f"{item.formula.display} — {'reaktiv' if index < len(balanced.reactants) else 'mahsulot'}"
    for index, item in enumerate(balanced.species)
]

amounts: list[Amount] = []
count = st.number_input("Nechta miqdorni bilasiz?", min_value=1, max_value=6, value=1, step=1)
for slot in range(int(count)):
    row = st.columns([3, 2, 2, 2])
    with row[0]:
        choice = st.selectbox(
            "Modda", species_labels, key=f"species-{slot}",
            index=min(slot, len(species_labels) - 1),
        )
    index = species_labels.index(choice)
    with row[1]:
        value = st.number_input("Miqdor", key=f"value-{slot}", value=10.0, min_value=0.0, step=1.0)
    with row[2]:
        unit = st.selectbox(
            "Birlik", list(UNIT_LABELS), key=f"unit-{slot}",
            format_func=lambda key: UNIT_LABELS[key],
        )
    concentration = None
    with row[3]:
        if unit in {"L_solution", "mL_solution"}:
            concentration = st.number_input(
                "Konsentratsiya (mol/L)", key=f"conc-{slot}", value=1.0, min_value=0.0, step=0.1
            )
        else:
            st.caption(f"M = {format_number(balanced.species[index].formula.molar_mass, 3)} g/mol")
    amounts.append(Amount(index, value, unit, concentration))

yield_columns = st.columns([1, 3])
with yield_columns[0]:
    apply_yield = st.checkbox("Foiz unumdorlikni qo'llash")
percent = None
if apply_yield:
    with yield_columns[1]:
        percent = st.slider("Foiz unumdorlik", 1.0, 100.0, 100.0, 0.5)

calculator = StoichiometryCalculator(molar_volume)
try:
    outcome = calculator.calculate(balanced, amounts, percent)
except StoichiometryError as error:
    st.error(str(error))
    st.stop()

st.divider()
st.markdown("#### Natijalar")

if outcome.limiting:
    stats(
        [
            ("Cheklovchi reagent", outcome.limiting.name),
            ("Reaksiya yurishi", f"{format_number(outcome.extent, 4)} ×"),
            ("Hosil bo'lgan mahsulotlar", str(len(outcome.products))),
        ],
        accent="var(--copper)",
    )

table = pd.DataFrame(
    [
        {
            "Modda": item.name,
            "Rol": item.role,
            "Mollar": round(item.moles, 5),
            "Massa (g)": round(item.mass, 4),
            "Gaz hajmi (L)": round(item.gas_volume, 4) if item.gas_volume is not None else None,
            "Kiritilgan (mol)": round(item.supplied_moles, 5) if item.supplied_moles is not None else None,
            "Ortib qolgan (mol)": round(item.excess_moles, 5) if item.excess_moles is not None else None,
            "Cheklovchi": "ha" if item.limiting else "",
        }
        for item in outcome.results
    ]
)
st.dataframe(table, width="stretch", hide_index=True)

excess = outcome.excess_reagents
if excess:
    st.markdown("**Reaksiya to'xtaganda ortib qolgan miqdor**")
    for item in excess:
        st.caption(
            f"{item.name}: {format_number(item.excess_moles or 0, 4)} mol "
            f"({format_number(item.excess_mass or 0, 4)} g) reaksiyaga kirmagan."
        )

for note in outcome.notes:
    st.caption(f"· {note}")

with st.expander("Bu qanday hisoblandi"):
    st.markdown(
        f"""
1. Har bir miqdor mollarga aylantirildi — massa ÷ molyar massa, yoki gaz uchun hajm ÷ {format_number(molar_volume, 3)} L/mol.
2. Har bir reaktivning mollari uning koeffitsiyentiga bo'lindi. Eng kichik javob, yozilganidek reaksiya necha marta yurishini bildiradi: **{format_number(outcome.extent, 5)}**.
3. Bu reaktiv cheklovchi hisoblanadi; qolgan hamma narsa shu farqqa ko'ra ortiqcha olingan.
4. Boshqa har bir modda xuddi shu songa ko'paytirildi va keyin gramm yoki litrga qayta aylantirildi.
        """
    )
    st.caption(
        "Foiz unumdorlik faqat mahsulotlarga ta'sir qiladi — u reaktivlarning qanchasi sarflanganligini "
        "o'zgartirmaydi."
    )
