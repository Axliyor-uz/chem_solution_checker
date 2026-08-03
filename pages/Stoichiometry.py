"""Stexiometriya — muvozanatlangan tenglama bo'yicha mol hisoblari."""

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

#: Ichki rol nomlarining o'zbekcha ko'rinishi.
ROLE_NAMES = {"reactant": "reagent", "product": "mahsulot"}

page_header(
    "Stexiometriya",
    "Boshlang'ich miqdorlarni kiriting. Qolganini koeffitsiyentlar hal qiladi: nima "
    "birinchi tugaydi, nima ortib qoladi va qancha mahsulot kutish mumkin.",
    eyebrow="Mol · Cheklovchi reagent · Unum",
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
        st.caption(f"Shunday yozib ko'ring: {error.suggestion}")
    st.stop()

result = balancer.balance(equation)
if not result.succeeded or not result.equation:
    st.error(result.message)
    st.stop()

balanced = result.equation
if result.status != "already_balanced":
    st.caption("Avval muvozanatlandi — mol nisbatlari faqat shundan keyin ma'noga ega bo'ladi.")
equation_card(balanced.display, label="Hisob shu tenglama bo'yicha")

st.markdown("#### Gazlar uchun sharoit")
condition_columns = st.columns([1, 1, 1])
with condition_columns[0]:
    basis = st.radio(
        "Molyar hajm",
        ["STP (0 °C, 1 atm)", "RTP (25 °C, 1 atm)", "Boshqa sharoit"],
        label_visibility="collapsed",
    )
if basis == "Boshqa sharoit":
    with condition_columns[1]:
        temperature = st.number_input("Harorat (°C)", value=25.0, step=5.0)
    with condition_columns[2]:
        pressure = st.number_input("Bosim (atm)", value=1.0, min_value=0.01, step=0.1)
    molar_volume = StoichiometryCalculator.molar_volume_at(temperature, pressure)
else:
    molar_volume = MOLAR_VOLUME_STP if basis.startswith("STP") else MOLAR_VOLUME_RTP
st.caption(f"Bu sharoitda istalgan gazning 1 moli {format_number(molar_volume, 3)} L hajmni egallaydi.")

st.markdown("#### Boshlang'ich miqdorlar")
st.caption("Cheklovchi reagentni topish uchun har bir reagent miqdorini kiriting yoki bittasini kiritib, shundan hisoblang.")

species_labels = [
    f"{item.formula.display} — {'reagent' if index < len(balanced.reactants) else 'mahsulot'}"
    for index, item in enumerate(balanced.species)
]

amounts: list[Amount] = []
count = st.number_input("Nechta miqdor ma'lum?", min_value=1, max_value=6, value=1, step=1)
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
    apply_yield = st.checkbox("Foizli unumni qo'llash")
percent = None
if apply_yield:
    with yield_columns[1]:
        percent = st.slider("Unum, %", 1.0, 100.0, 100.0, 0.5)

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
            ("Reaksiya bordi", f"{format_number(outcome.extent, 4)} ×"),
            ("Hosil bo'lgan mahsulotlar", str(len(outcome.products))),
        ],
        accent="var(--copper)",
    )

table = pd.DataFrame(
    [
        {
            "Modda": item.name,
            "Roli": ROLE_NAMES[item.role],
            "Mol": round(item.moles, 5),
            "Massa (g)": round(item.mass, 4),
            "Gaz hajmi (L)": round(item.gas_volume, 4) if item.gas_volume is not None else None,
            "Berilgan (mol)": round(item.supplied_moles, 5) if item.supplied_moles is not None else None,
            "Ortib qolgan (mol)": round(item.excess_moles, 5) if item.excess_moles is not None else None,
            "Cheklovchi": "ha" if item.limiting else "",
        }
        for item in outcome.results
    ]
)
st.dataframe(table, width="stretch", hide_index=True)

excess = outcome.excess_reagents
if excess:
    st.markdown("**Reaksiya to'xtaganda ortib qoladi**")
    for item in excess:
        st.caption(
            f"{item.name}: {format_number(item.excess_moles or 0, 4)} mol "
            f"({format_number(item.excess_mass or 0, 4)} g) reaksiyaga kirishmaydi."
        )

for note in outcome.notes:
    st.caption(f"· {note}")

with st.expander("Bu qanday hisoblandi"):
    st.markdown(
        f"""
1. Har bir miqdor molga o'girildi — massa ÷ molyar massa, gaz uchun esa hajm ÷ {format_number(molar_volume, 3)} L/mol.
2. Har bir reagentning moli o'z koeffitsiyentiga bo'lindi. Eng kichik natija reaksiya yozilgan holida necha marta bora olishini bildiradi: **{format_number(outcome.extent, 5)}**.
3. O'sha reagent cheklovchi hisoblanadi; qolganlari farq miqdoricha ortiqcha.
4. Boshqa barcha moddalar shu son bo'yicha hisoblandi va yana gramm yoki litrga qaytarildi.
        """
    )
    st.caption(
        "Foizli unum qo'llanilganda faqat mahsulotlarga ta'sir qiladi — sarflangan "
        "reagent miqdorini o'zgartirmaydi."
    )
