"""Equation checker — validate, balance and explain a chemical equation."""

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


def _api_key() -> str:
    """Read the tutor's API key from secrets or the environment.

    Reading ``st.secrets`` raises when no secrets file has been created, which
    is the normal state for a local checkout, so absence is treated as "the
    optional feature is off" rather than an error.
    """
    try:
        secret = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:  # noqa: BLE001 - no secrets file is a normal condition
        secret = ""
    return str(secret or os.environ.get("ANTHROPIC_API_KEY", ""))

page_header(
    "Equation checker",
    "Type a reaction, and every element gets weighed against itself. "
    "Where it does not balance, the coefficient that has to change is named.",
    eyebrow="Check · Balance · Explain",
)

st.session_state.setdefault(INPUT_KEY, "H2 + O2 -> H2O")
st.session_state.setdefault(CONDITIONS_KEY, "")

left, right = st.columns([3, 2], gap="large")

with left:
    st.text_area(
        "Equation",
        key=INPUT_KEY,
        height=88,
        label_visibility="collapsed",
        placeholder="H2 + O2 -> H2O",
    )
    keys.live_preview(st.session_state[INPUT_KEY])
    practice_mode = st.toggle(
        "Practice mode",
        value=False,
        help="Hold back the answer and give one hint at a time.",
    )

with right:
    keys.keyboard(INPUT_KEY, CONDITIONS_KEY)

keys.example_picker(INPUT_KEY)

with st.expander("Reaction conditions (optional)"):
    condition_columns = st.columns(3)
    with condition_columns[0]:
        st.text_input("Catalyst and conditions", key=CONDITIONS_KEY, placeholder="V2O5, Δ")
    with condition_columns[1]:
        temperature = st.text_input("Temperature", placeholder="450 °C")
    with condition_columns[2]:
        pressure = st.text_input("Pressure", placeholder="2 atm")

st.divider()

source = st.session_state[INPUT_KEY].strip()
if not source:
    st.info("Type an equation above, or pick one of the examples.")
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
        equation_card(source, label="Could not read this", variant="is-error")
    else:
        equation_card(equation.display, label="As you wrote it")
        if balance and balance.succeeded and balance.equation:
            if practice_mode and balance.status != "already_balanced":
                st.caption("Practice mode is on, so the balanced equation is hidden.")
            else:
                equation_card(
                    balance.equation.display,
                    label="Balanced" if balance.status != "already_balanced" else "Already balanced",
                )

with verdict_columns[1]:
    if equation:
        left_mass, right_mass = mass_balance(equation)
        rows = report.rows
        stats(
            [
                ("Species", str(len(equation.species))),
                ("Elements", str(len(equation.elements))),
                ("Balanced", "yes" if all(row.balanced for row in rows) else "no"),
                ("Mass in", f"{format_number(left_mass, 2)}"),
                ("Mass out", f"{format_number(right_mass, 2)}"),
            ]
        )

if equation:
    st.markdown("#### The balance")
    charges = (
        (charge_of_side(equation.reactants), charge_of_side(equation.products))
        if equation.has_charges
        else None
    )
    balance_ledger(report.rows, charges)

st.markdown("#### What the checker found")
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
    ["Worked solution", "Reaction type", "Tutor", "Export"]
)

with tab_steps:
    if practice_mode:
        st.caption("One hint at a time. Reveal only as many as you need.")
        hint_list = hints(equation, balance)
        for index, hint in enumerate(hint_list, start=1):
            last = index == len(hint_list) and len(hint_list) > 1
            with st.expander("Show the answer" if last else f"Hint {index}"):
                st.write(hint)
    elif steps:
        steps_view(steps)
    else:
        st.info("No steps to show for this input.")

with tab_type:
    types = classify(equation)
    if not types:
        st.info("This does not match a standard reaction family.")
    for item in types:
        st.markdown(f"**{item.name}** · {item.confidence_label}")
        st.caption(item.evidence)
    if equation.conditions:
        st.markdown("**Conditions recorded**")
        for name, value in equation.conditions.items():
            st.caption(f"{name.capitalize()}: {value}")

with tab_tutor:
    if balance:
        for heading, text in tutor_notes(equation, balance):
            st.markdown(f"**{heading}**")
            st.caption(text)
        st.markdown("**Where this one usually goes wrong**")
        for mistake in common_mistakes(equation):
            st.caption(f"· {mistake}")

    st.divider()
    api_key = _api_key()
    question = st.text_input(
        "Ask about this equation",
        placeholder="Why does oxygen get balanced last?",
    )
    if question:
        if not api_key:
            st.info(
                "Add an ANTHROPIC_API_KEY to Streamlit secrets to enable the AI tutor. "
                "Everything else on this page works without it."
            )
        elif balance:
            with st.spinner("Thinking…"):
                st.write(
                    ask_ai_tutor(
                        question,
                        tutor_context(equation, balance),
                        api_key,
                        practice_mode=practice_mode,
                    )
                )

with tab_export:
    st.caption("Take this result with you.")
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
