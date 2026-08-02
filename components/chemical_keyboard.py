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
        "Elementlar",
        COMMON_ELEMENTS,
        columns=10,
        hint="O'quv dasturlarida eng ko'p qo'llaniladigan elementlar. Boshqa barcha belgilarni bevosita kiritish mumkin.",
    ),
    KeyGroup(
        "Raqamlar",
        ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"),
        columns=10,
        hint="Formuladan oldin yozilgan raqam - koeffitsiyent; belgidan keyin yozilgani - indeks.",
    ),
    KeyGroup(
        "Indekslar",
        ("₂", "₃", "₄", "₅", "₆", "₇", "₈", "₉", "₁", "₀"),
        columns=10,
        hint="Ixtiyoriy — H2O deb yozish H₂O kabi natija beradi. Ikkalasi ham H2O sifatida saqlanadi.",
    ),
    KeyGroup(
        "Zaryadlar",
        ("⁺", "⁻", "²⁺", "³⁺", "²⁻", "³⁻", "^", "^2+", "^2-", "^3+"),
        columns=10,
        hint="Zaryadlar formuladan keyin qo'yiladi: Fe³⁺, SO₄²⁻, NH₄⁺.",
    ),
    KeyGroup(
        "Qavslar",
        ("(", ")", "[", "]", "{", "}"),
        columns=6,
        hint="Qavslar takrorlanuvchi birlikni guruhlaydi: Ca(OH)₂, Al₂(SO₄)₃.",
    ),
    KeyGroup(
        "Operatorlar",
        (" + ", " -> ", " <-> ", "=", "*", "↑", "↓"),
        columns=7,
        hint="↑ va ↓ mos ravishda (g) va (s) deb o'qiladi.",
        labels={" + ": "+", " -> ": "→", " <-> ": "⇌", "*": "· (kristallgidrat)", "=": "="},
    ),
    KeyGroup(
        "Holatlar",
        ("(s)", "(l)", "(g)", "(aq)"),
        columns=4,
        hint="Fizik holat oxirida yoziladi: NaCl(aq), H₂O(l), CO₂(g).",
    ),
    KeyGroup(
        "Yunoncha",
        ("Δ", "λ", "α", "β", "γ", "°"),
        columns=6,
        hint="Δ - qizdirish, λ - to'lqin uzunligi, α va β - nurlanish turlari.",
    ),
)

CONDITION_KEYS: Final[tuple[str, ...]] = (
    "Pt", "MnO2", "Ni", "V2O5", "Fe", "Δ (heat)", "hv (light)", "high pressure", "electrolysis",
)

EXAMPLES: Final[tuple[tuple[str, str], ...]] = (
    ("Suvning elementlaridan hosil bo'lishi", "H2 + O2 -> H2O"),
    ("Temirning zanglashi", "Fe + O2 -> Fe2O3"),
    ("Termik parchalanish", "CaCO3 -> CaO + CO2"),
    ("Neytrallanish", "NaOH + HCl -> NaCl + H2O"),
    ("Propan yonishi", "C3H8 + O2 -> CO2 + H2O"),
    ("Kontakt jarayoni", "SO2(g) + O2(g) <=> SO3(g)"),
    ("Cho'kma tushishi", "NaCl(aq) + AgNO3(aq) -> AgCl(s) + NaNO3(aq)"),
    ("Ionli oksidlanish-qaytarilish", "MnO4- + Fe2+ + H+ -> Mn2+ + Fe3+ + H2O"),
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
    tab_names = [group.name for group in GROUPS] + (["Katalizatorlar"] if conditions_key else [])
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
            st.caption("Sharoitlar formula ichida emas, balki tenglama yonida yoziladi.")
            st.session_state.setdefault(conditions_key, "")
            _key_grid(
                CONDITION_KEYS,
                5,
                lambda token: _append_condition(conditions_key, token),
                prefix="kb-cond",
            )

    edit_columns = st.columns(3)
    with edit_columns[0]:
        st.button("⌫ O'chirish", key="kb-back", on_click=_backspace, args=(target_key,))
    with edit_columns[1]:
        st.button("Bo'sh joy", key="kb-space", on_click=_append, args=(target_key, " "))
    with edit_columns[2]:
        st.button("Tozalash", key="kb-clear", on_click=_clear, args=(target_key,))


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
        st.caption("Hali hech narsa yozilmadi. Yuqoridagi tugmalardan foydalaning yoki bevosita kiriting.")
        return
    st.markdown(
        f'<div class="equation-card is-muted"><div class="label">Shunday o\'qiladi</div>'
        f'<div class="formula">{to_display(text)}</div></div>',
        unsafe_allow_html=True,
    )


def example_picker(target_key: str, columns: int = 4) -> None:
    """Buttons that load worked examples into the equation box."""
    st.caption("Yoki misollardan boshlang:")
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
