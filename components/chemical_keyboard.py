"""The chemical keyboard.

Typing chemistry on a normal keyboard is the first obstacle a student hits:
subscripts, superscripted charges and arrows are all awkward. These keys write
straight into the equation box, so the notation is available without knowing
any shortcuts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Final, Sequence

import streamlit as st

from utils.formatting import to_display


@dataclass(frozen=True, slots=True)
class KeyGroup:
    """One labelled tab of the keyboard."""

    name: str
    keys: tuple[str, ...]
    columns: int = 10
    hint: str = ""
    labels: dict[str, str] | None = None

    def label_for(self, key: str) -> str:
        return (self.labels or {}).get(key, key)


COMMON_ELEMENTS: Final[tuple[str, ...]] = (
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
    "Ti", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Br", "I",
    "Ag", "Sn", "Ba", "Pt", "Au", "Hg", "Pb", "Sr", "Li", "Rb",
)

GROUPS: Final[tuple[KeyGroup, ...]] = (
    KeyGroup(
        "Elements",
        COMMON_ELEMENTS,
        columns=10,
        hint="The elements a syllabus uses most. Every other symbol can be typed directly.",
    ),
    KeyGroup(
        "Numbers",
        ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"),
        columns=10,
        hint="A number typed before a formula is a coefficient; after a symbol it is a subscript.",
    ),
    KeyGroup(
        "Subscripts",
        ("₂", "₃", "₄", "₅", "₆", "₇", "₈", "₉", "₁", "₀"),
        columns=10,
        hint="Optional — typing H2O gives the same result as H₂O. Both are stored as H2O.",
    ),
    KeyGroup(
        "Charges",
        ("⁺", "⁻", "²⁺", "³⁺", "²⁻", "³⁻", "^", "^2+", "^2-", "^3+"),
        columns=10,
        hint="Charges go after the formula: Fe³⁺, SO₄²⁻, NH₄⁺.",
    ),
    KeyGroup(
        "Brackets",
        ("(", ")", "[", "]", "{", "}"),
        columns=6,
        hint="Brackets group a repeated unit: Ca(OH)₂, Al₂(SO₄)₃.",
    ),
    KeyGroup(
        "Operators",
        (" + ", " -> ", " <-> ", "=", "*", "↑", "↓"),
        columns=7,
        hint="↑ and ↓ are read as (g) and (s).",
        labels={" + ": "+", " -> ": "→", " <-> ": "⇌", "*": "· (hydrate)", "=": "="},
    ),
    KeyGroup(
        "States",
        ("(s)", "(l)", "(g)", "(aq)"),
        columns=4,
        hint="Physical state goes last: NaCl(aq), H₂O(l), CO₂(g).",
    ),
    KeyGroup(
        "Greek",
        ("Δ", "λ", "α", "β", "γ", "°"),
        columns=6,
        hint="Δ marks heating, λ a wavelength, α and β radiation types.",
    ),
)

CONDITION_KEYS: Final[tuple[str, ...]] = (
    "Pt", "MnO2", "Ni", "V2O5", "Fe", "Δ (heat)", "hv (light)", "high pressure", "electrolysis",
)

EXAMPLES: Final[tuple[tuple[str, str], ...]] = (
    ("Water from its elements", "H2 + O2 -> H2O"),
    ("Rusting iron", "Fe + O2 -> Fe2O3"),
    ("Thermal decomposition", "CaCO3 -> CaO + CO2"),
    ("Neutralisation", "NaOH + HCl -> NaCl + H2O"),
    ("Burning propane", "C3H8 + O2 -> CO2 + H2O"),
    ("Contact process", "SO2(g) + O2(g) <=> SO3(g)"),
    ("Precipitation", "NaCl(aq) + AgNO3(aq) -> AgCl(s) + NaNO3(aq)"),
    ("Ionic redox", "MnO4- + Fe2+ + H+ -> Mn2+ + Fe3+ + H2O"),
)


def _append(target_key: str, token: str) -> None:
    current = st.session_state.get(target_key, "")
    st.session_state[target_key] = f"{current}{token}"


def _backspace(target_key: str) -> None:
    st.session_state[target_key] = st.session_state.get(target_key, "")[:-1]


def _clear(target_key: str) -> None:
    st.session_state[target_key] = ""


def keyboard(target_key: str, conditions_key: str | None = None) -> None:
    """Draw the keyboard, writing into the widget bound to ``target_key``.

    Args:
        target_key: Session-state key of the equation input.
        conditions_key: Optional session-state key for reaction conditions,
            which is where catalyst keys write. Catalysts belong above the
            arrow, not inside a formula, so they never touch the equation.
    """
    st.session_state.setdefault(target_key, "")
    tab_names = [group.name for group in GROUPS] + (["Catalysts"] if conditions_key else [])
    tabs = st.tabs(tab_names)

    for tab, group in zip(tabs, GROUPS):
        with tab:
            if group.hint:
                st.caption(group.hint)
            _key_grid(
                group.keys,
                group.columns,
                lambda token: _append(target_key, token),
                prefix=f"kb-{group.name}",
                label=group.label_for,
            )

    if conditions_key:
        with tabs[-1]:
            st.caption("Conditions are recorded beside the equation, not inside a formula.")
            st.session_state.setdefault(conditions_key, "")
            _key_grid(
                CONDITION_KEYS,
                5,
                lambda token: _append_condition(conditions_key, token),
                prefix="kb-cond",
            )

    edit_columns = st.columns(3)
    with edit_columns[0]:
        st.button("⌫ Backspace", key="kb-back", on_click=_backspace, args=(target_key,))
    with edit_columns[1]:
        st.button("Space", key="kb-space", on_click=_append, args=(target_key, " "))
    with edit_columns[2]:
        st.button("Clear", key="kb-clear", on_click=_clear, args=(target_key,))


def _append_condition(conditions_key: str, token: str) -> None:
    current = st.session_state.get(conditions_key, "").strip()
    st.session_state[conditions_key] = f"{current}, {token}" if current else token


def _key_grid(
    keys: Sequence[str],
    columns: int,
    on_press: Callable[[str], None],
    prefix: str,
    label: Callable[[str], str] | None = None,
) -> None:
    """Lay keys out in a grid of buttons."""
    for start in range(0, len(keys), columns):
        row = keys[start: start + columns]
        slots = st.columns(columns)
        for index, key in enumerate(row):
            with slots[index]:
                st.button(
                    label(key) if label else key,
                    key=f"{prefix}-{start + index}-{key}",
                    on_click=on_press,
                    args=(key,),
                    width="stretch",
                )


def live_preview(text: str) -> None:
    """Show the typeset version of what is currently typed."""
    if not text.strip():
        st.caption("Nothing typed yet. Use the keys above, or type directly.")
        return
    st.markdown(
        f'<div class="equation-card is-muted"><div class="label">Reads as</div>'
        f'<div class="formula">{to_display(text)}</div></div>',
        unsafe_allow_html=True,
    )


def example_picker(target_key: str, columns: int = 4) -> None:
    """Buttons that load worked examples into the equation box."""
    st.caption("Or start from an example:")
    for start in range(0, len(EXAMPLES), columns):
        row = EXAMPLES[start: start + columns]
        slots = st.columns(columns)
        for index, (name, equation) in enumerate(row):
            with slots[index]:
                st.button(
                    name,
                    key=f"example-{start + index}",
                    on_click=_set_value,
                    args=(target_key, equation),
                    width="stretch",
                )


def _set_value(target_key: str, value: str) -> None:
    st.session_state[target_key] = value
