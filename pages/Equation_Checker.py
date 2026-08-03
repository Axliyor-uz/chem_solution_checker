"""Tenglama tekshirgich — kimyoviy tenglamani tekshiradi, muvozanatlaydi va tushuntiradi."""

from __future__ import annotations

import os

import streamlit as st

from components import chemical_keyboard as keys
from components.atom_counter import charge_of_side, mass_balance
from components.explanation import (
    ask_ai_tutor,
    build_steps,
    common_mistakes,
    hints,
    tutor_context,
    tutor_notes,
)
from components.reaction_classifier import classify
from components.ui import balance_ledger, equation_card, findings, page_header, stats, steps_view
from components.validator import equation_validator
from utils import export, history
from utils.formatting import format_number

INPUT_KEY = "equation_input"
CONDITIONS_KEY = "equation_conditions"

#: Tenglama ichida saqlanadigan sharoit kalitlarining o'zbekcha nomlari.
CONDITION_NAMES = {"catalyst": "Katalizator", "temperature": "Harorat", "pressure": "Bosim"}


def _api_key() -> str:
    """Ustoz uchun API kalitini secrets faylidan yoki muhit o'zgaruvchisidan o'qiydi.

    ``st.secrets`` ni o'qish secrets fayli yaratilmagan bo'lsa xato beradi, bu esa
    lokal nusxa uchun odatiy hol; shuning uchun kalit yo'qligi xato emas, "ixtiyoriy
    imkoniyat o'chirilgan" deb qaraladi.
    """
    try:
        secret = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:  # noqa: BLE001 - secrets faylining yo'qligi odatiy hol
        secret = ""
    return str(secret or os.environ.get("ANTHROPIC_API_KEY", ""))

page_header(
    "Tenglama tekshirgich",
    "Reaksiyani yozing — har bir element o'zi bilan taroziga qo'yiladi. "
    "Muvozanat bo'lmasa, qaysi koeffitsiyentni o'zgartirish kerakligi aytiladi.",
    eyebrow="Tekshirish · Muvozanatlash · Tushuntirish",
)

st.session_state.setdefault(INPUT_KEY, "H2 + O2 -> H2O")
st.session_state.setdefault(CONDITIONS_KEY, "")

left, right = st.columns([3, 2], gap="large")

with left:
    st.text_area(
        "Tenglama",
        key=INPUT_KEY,
        height=88,
        label_visibility="collapsed",
        placeholder="H2 + O2 -> H2O",
    )
    keys.live_preview(st.session_state[INPUT_KEY])
    solve_clicked = st.button("Yechish", type="primary")
    st.caption("Tenglamani tekshirish uchun «Yechish» tugmasini bosing.")
    practice_mode = st.toggle(
        "Mashq rejimi",
        value=False,
        help="Javobni yashirib turadi va bir vaqtda bittadan maslahat beradi.",
    )

with right:
    keys.keyboard(INPUT_KEY, CONDITIONS_KEY)

keys.example_picker(INPUT_KEY)

with st.expander("Reaksiya sharoitlari (ixtiyoriy)"):
    condition_columns = st.columns(3)
    with condition_columns[0]:
        st.text_input("Katalizator va sharoitlar", key=CONDITIONS_KEY, placeholder="V2O5, Δ")
    with condition_columns[1]:
        temperature = st.text_input("Harorat", placeholder="450 °C")
    with condition_columns[2]:
        pressure = st.text_input("Bosim", placeholder="2 atm")

st.divider()

source = st.session_state[INPUT_KEY].strip()
if not source:
    st.info("Yuqoriga tenglama yozing yoki misollardan birini tanlang.")
    st.stop()

report = equation_validator.validate(source)
equation = report.equation
balance = report.balance

if equation:
    equation.conditions = {
        key: value
        for key, value in (
            ("catalyst", st.session_state[CONDITIONS_KEY]),
            ("temperature", temperature),
            ("pressure", pressure),
        )
        if value
    }

verdict_columns = st.columns([3, 2], gap="large")

with verdict_columns[0]:
    if not equation:
        equation_card(source, label="Buni o'qib bo'lmadi", variant="is-error")
    else:
        equation_card(equation.display, label="Siz yozganingizdek")
        if balance and balance.succeeded and balance.equation:
            if practice_mode and balance.status != "already_balanced":
                st.caption("Mashq rejimi yoqilgan, shuning uchun muvozanatlangan tenglama yashirilgan.")
            else:
                equation_card(
                    balance.equation.display,
                    label="Muvozanatlangan" if balance.status != "already_balanced" else "Allaqachon muvozanatlangan",
                )

with verdict_columns[1]:
    if equation:
        left_mass, right_mass = mass_balance(equation)
        rows = report.rows
        stats(
            [
                ("Moddalar", str(len(equation.species))),
                ("Elementlar", str(len(equation.elements))),
                ("Muvozanat", "bor" if all(row.balanced for row in rows) else "yo'q"),
                ("Kiruvchi massa", f"{format_number(left_mass, 2)}"),
                ("Chiquvchi massa", f"{format_number(right_mass, 2)}"),
            ]
        )

if equation:
    st.markdown("#### Muvozanat")
    charges = (
        (charge_of_side(equation.reactants), charge_of_side(equation.products))
        if equation.has_charges
        else None
    )
    balance_ledger(report.rows, charges)

st.markdown("#### Tekshirgich nimalarni aniqladi")
findings(report.sorted_issues)

if not equation:
    st.stop()

steps = build_steps(equation, balance) if balance else []
history.record(
    source=source,
    equation=equation.display,
    balanced=balance.equation.display if balance and balance.equation else "—",
    status=report.headline,
    reaction_types=[item.name for item in classify(equation)],
)

tab_steps, tab_type, tab_tutor, tab_export = st.tabs(
    ["Yechim qadamlari", "Reaksiya turi", "Ustoz", "Eksport"]
)

with tab_steps:
    if practice_mode:
        st.caption("Bir vaqtda bitta maslahat. Faqat kerak bo'lganicha oching.")
        hint_list = hints(equation, balance)
        for index, hint in enumerate(hint_list, start=1):
            last = index == len(hint_list) and len(hint_list) > 1
            with st.expander("Javobni ko'rsatish" if last else f"{index}-maslahat"):
                st.write(hint)
    elif steps:
        steps_view(steps)
    else:
        st.info("Bu kiritma uchun ko'rsatiladigan qadam yo'q.")

with tab_type:
    types = classify(equation)
    if not types:
        st.info("Bu standart reaksiya turkumlariga to'g'ri kelmadi.")
    for item in types:
        st.markdown(f"**{item.name}** · {item.confidence_label}")
        st.caption(item.evidence)
    if equation.conditions:
        st.markdown("**Qayd etilgan sharoitlar**")
        for name, value in equation.conditions.items():
            st.caption(f"{CONDITION_NAMES.get(name, name.capitalize())}: {value}")

with tab_tutor:
    if balance:
        for heading, text in tutor_notes(equation, balance):
            st.markdown(f"**{heading}**")
            st.caption(text)
        st.markdown("**Bu misolda odatda qayerda xato qilinadi**")
        for mistake in common_mistakes(equation):
            st.caption(f"· {mistake}")

    st.divider()
    api_key = _api_key()
    question = st.text_input(
        "Shu tenglama haqida so'rang",
        placeholder="Nega kislorod oxirida tenglashtiriladi?",
    )
    if question:
        if not api_key:
            st.info(
                "Sun'iy intellekt ustozini yoqish uchun Streamlit secrets fayliga ANTHROPIC_API_KEY qo'shing. "
                "Bu sahifadagi qolgan hamma narsa usiz ham ishlaydi."
            )
        elif balance:
            with st.spinner("O'ylanmoqda…"):
                st.write(
                    ask_ai_tutor(
                        question,
                        tutor_context(equation, balance),
                        api_key,
                        practice_mode=practice_mode,
                    )
                )

with tab_export:
    st.caption("Bu natijani o'zingiz bilan olib keting.")
    export_columns = st.columns(4)
    with export_columns[0]:
        st.download_button(
            "PDF",
            data=export.to_pdf(report, steps),
            file_name=export.summary_filename(report, "pdf"),
            mime="application/pdf",
            width="stretch",
        )
    with export_columns[1]:
        st.download_button(
            "CSV",
            data=export.to_csv(report),
            file_name=export.summary_filename(report, "csv"),
            mime="text/csv",
            width="stretch",
        )
    with export_columns[2]:
        st.download_button(
            "JSON",
            data=export.to_json(report, steps),
            file_name=export.summary_filename(report, "json"),
            mime="application/json",
            width="stretch",
        )
    with export_columns[3]:
        st.download_button(
            "PNG",
            data=export.to_png(report),
            file_name=export.summary_filename(report, "png"),
            mime="image/png",
            width="stretch",
        )
