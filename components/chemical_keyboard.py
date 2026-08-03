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
    columns: int = 8
    hint: str = ""
    labels: dict[str, str] | None = None
    tips: dict[str, str] | None = None

    def label_for(self, key: str) -> str:
        return (self.labels or {}).get(key, key)

    def tip_for(self, key: str) -> str | None:
        """Tooltip for a key whose label had to be abbreviated to fit."""
        return (self.tips or {}).get(key)


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
        hint="↑ and ↓ are read as (g) and (s). · joins the water in a hydrate.",
        labels={" + ": "+", " -> ": "→", " <-> ": "⇌", "*": "·", "=": "="},
        tips={"*": "Hydrate dot — CuSO4*5H2O reads as CuSO₄·5H₂O"},
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

CONDITION_LABELS: Final[dict[str, str]] = {
    "Δ (heat)": "Δ", "hv (light)": "hv", "high pressure": "press", "electrolysis": "electro",
}

EXAMPLES: Final[tuple[tuple[str, str, str], ...]] = (
    ("Water", "Water from its elements", "H2 + O2 -> H2O"),
    ("Rust", "Rusting iron", "Fe + O2 -> Fe2O3"),
    ("Heat", "Thermal decomposition", "CaCO3 -> CaO + CO2"),
    ("Acid", "Neutralisation", "NaOH + HCl -> NaCl + H2O"),
    ("Burn", "Burning propane", "C3H8 + O2 -> CO2 + H2O"),
    ("Contact", "Contact process", "SO2(g) + O2(g) <=> SO3(g)"),
    ("Ppt", "Precipitation", "NaCl(aq) + AgNO3(aq) -> AgCl(s) + NaNO3(aq)"),
    ("Redox", "Ionic redox", "MnO4- + Fe2+ + H+ -> Mn2+ + Fe3+ + H2O"),
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

    with st.expander("Chemistry keyboard", expanded=False):
        st.caption("Tap to open the keyboard. Typing normally still works too.")
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
                    tip=group.tip_for,
                )

        if conditions_key:
            with tabs[-1]:
                st.caption("Conditions are recorded beside the equation, not inside a formula.")
                st.session_state.setdefault(conditions_key, "")
                _key_grid(
                    CONDITION_KEYS,
                    9,
                    lambda token: _append_condition(conditions_key, token),
                    prefix="kb-cond",
                    label=lambda key: CONDITION_LABELS.get(key, key),
                    tip=lambda key: key if key in CONDITION_LABELS else None,
                )

        with st.container(key="keygrid-edit"):
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
    tip: Callable[[str], str | None] | None = None,
) -> None:
    """Lay keys out in a grid of small buttons.

    The grid sits in a ``keygrid-`` container, which the stylesheet holds to
    one row per line at any width — otherwise a phone stacks forty element
    keys into forty full-width rows.
    """
    with st.container(key=f"keygrid-{prefix}"):
        for start in range(0, len(keys), columns):
            row = keys[start: start + columns]
            slots = st.columns(columns)
            for index, key in enumerate(row):
                with slots[index]:
                    st.button(
                        label(key) if label else key,
                        key=f"{prefix}-{start + index}-{key}",
                        help=tip(key) if tip else None,
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


def example_picker(target_key: str, columns: int = 6) -> None:
    """Buttons that load worked examples into the equation box.

    The buttons carry a one-word label so a whole row fits on a phone; the
    full name and the equation itself are in the tooltip. The ``example-grid``
    container is styled to keep the row horizontal at any width.
    """
    st.caption("Or start from an example:")
    with st.container(key="example-grid"):
        for start in range(0, len(EXAMPLES), columns):
            row = EXAMPLES[start: start + columns]
            slots = st.columns(columns)
            for index, (short, name, equation) in enumerate(row):
                with slots[index]:
                    st.button(
                        short,
                        key=f"example-{start + index}",
                        help=f"{name} — {to_display(equation)}",
                        on_click=_set_value,
                        args=(target_key, equation),
                        width="stretch",
                    )


def _set_value(target_key: str, value: str) -> None:
    st.session_state[target_key] = value
