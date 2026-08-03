"""Kimyoviy klaviatura.

Oddiy klaviaturada kimyo yozish — o'quvchi duch keladigan birinchi to'siq:
pastki indeks, yuqori indeksdagi zaryad va strelkalarni terish noqulay. Bu
tugmalar to'g'ridan-to'g'ri tenglama maydoniga yozadi, shuning uchun hech
qanday tezkor tugmani bilish shart emas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Final, Sequence

import streamlit as st

from utils.formatting import to_display


@dataclass(frozen=True, slots=True)
class KeyGroup:
    """Klaviaturaning nomlangan bitta bo'limi."""

    name: str
    keys: tuple[str, ...]
    columns: int = 8
    hint: str = ""
    labels: dict[str, str] | None = None
    tips: dict[str, str] | None = None

    def label_for(self, key: str) -> str:
        return (self.labels or {}).get(key, key)

    def tip_for(self, key: str) -> str | None:
        """Sig'dirish uchun qisqartirilgan tugma yozuvining to'liq izohi."""
        return (self.tips or {}).get(key)


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
        hint="O'quv dasturida eng ko'p uchraydigan elementlar. Qolgan barcha belgilarni to'g'ridan-to'g'ri yozish mumkin.",
    ),
    KeyGroup(
        "Raqamlar",
        ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"),
        columns=10,
        hint="Formula oldiga yozilgan raqam — koeffitsiyent; element belgisidan keyin esa pastki indeks.",
    ),
    KeyGroup(
        "Indekslar",
        ("₂", "₃", "₄", "₅", "₆", "₇", "₈", "₉", "₁", "₀"),
        columns=10,
        hint="Majburiy emas — H2O deb yozsangiz ham, H₂O deb yozsangiz ham natija bir xil. Ikkalasi H2O bo'lib saqlanadi.",
    ),
    KeyGroup(
        "Zaryadlar",
        ("⁺", "⁻", "²⁺", "³⁺", "²⁻", "³⁻", "^", "^2+", "^2-", "^3+"),
        columns=10,
        hint="Zaryad formuladan keyin yoziladi: Fe³⁺, SO₄²⁻, NH₄⁺.",
    ),
    KeyGroup(
        "Qavslar",
        ("(", ")", "[", "]", "{", "}"),
        columns=6,
        hint="Qavs takrorlanuvchi guruhni birlashtiradi: Ca(OH)₂, Al₂(SO₄)₃.",
    ),
    KeyGroup(
        "Amallar",
        (" + ", " -> ", " <-> ", "=", "*", "↑", "↓"),
        columns=7,
        hint="↑ va ↓ (g) va (s) deb o'qiladi. · gidratdagi suvni birlashtiradi.",
        labels={" + ": "+", " -> ": "→", " <-> ": "⇌", "*": "·", "=": "="},
        tips={"*": "Gidrat nuqtasi — CuSO4*5H2O CuSO₄·5H₂O deb o'qiladi"},
    ),
    KeyGroup(
        "Holatlar",
        ("(s)", "(l)", "(g)", "(aq)"),
        columns=4,
        hint="Fizik holat oxirida yoziladi: NaCl(aq), H₂O(l), CO₂(g).",
    ),
    KeyGroup(
        "Grek",
        ("Δ", "λ", "α", "β", "γ", "°"),
        columns=6,
        hint="Δ — qizdirish, λ — to'lqin uzunligi, α va β — nurlanish turlari.",
    ),
)

CONDITION_KEYS: Final[tuple[str, ...]] = (
    "Pt", "MnO2", "Ni", "V2O5", "Fe", "Δ (qizdirish)", "hv (yorug'lik)", "yuqori bosim", "elektroliz",
)

CONDITION_LABELS: Final[dict[str, str]] = {
    "Δ (qizdirish)": "Δ", "hv (yorug'lik)": "hv",
    "yuqori bosim": "bosim", "elektroliz": "el-liz",
}

EXAMPLES: Final[tuple[tuple[str, str, str], ...]] = (
    ("Suv", "Elementlaridan suv", "H2 + O2 -> H2O"),
    ("Zang", "Temirning zanglashi", "Fe + O2 -> Fe2O3"),
    ("Issiq", "Termik parchalanish", "CaCO3 -> CaO + CO2"),
    ("Kislota", "Neytrallanish", "NaOH + HCl -> NaCl + H2O"),
    ("Yonish", "Propanning yonishi", "C3H8 + O2 -> CO2 + H2O"),
    ("Kontakt", "Kontakt usuli", "SO2(g) + O2(g) <=> SO3(g)"),
    ("Cho'kma", "Cho'kma hosil bo'lishi", "NaCl(aq) + AgNO3(aq) -> AgCl(s) + NaNO3(aq)"),
    ("Redoks", "Ionli oksidlanish-qaytarilish", "MnO4- + Fe2+ + H+ -> Mn2+ + Fe3+ + H2O"),
)


def _append(target_key: str, token: str) -> None:
    current = st.session_state.get(target_key, "")
    st.session_state[target_key] = f"{current}{token}"


def _backspace(target_key: str) -> None:
    st.session_state[target_key] = st.session_state.get(target_key, "")[:-1]


def _clear(target_key: str) -> None:
    st.session_state[target_key] = ""


def keyboard(target_key: str, conditions_key: str | None = None) -> None:
    """Klaviaturani chizadi va ``target_key`` ga bog'langan maydonga yozadi.

    Args:
        target_key: Tenglama kiritish maydonining sessiya kaliti.
        conditions_key: Reaksiya sharoitlari uchun ixtiyoriy sessiya kaliti —
            katalizator tugmalari shu yerga yozadi. Katalizator strelka ustida
            turadi, formula ichida emas, shuning uchun tenglamaga tegmaydi.
    """
    st.session_state.setdefault(target_key, "")
    tab_names = [group.name for group in GROUPS] + (["Katalizatorlar"] if conditions_key else [])

    with st.expander("Kimyoviy klaviatura", expanded=False):
        st.caption("Klaviaturani ochish uchun bosing. Oddiy yozish ham ishlayveradi.")
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
                st.caption("Sharoitlar tenglama yonida qayd etiladi, formula ichida emas.")
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
    tip: Callable[[str], str | None] | None = None,
) -> None:
    """Tugmalarni kichik tugmalar to'ridagi kabi joylashtiradi.

    To'r ``keygrid-`` konteyneri ichida turadi va uslublar faylida har qanday
    ekran kengligida bir qator bo'lib qolishi ta'minlanadi — aks holda telefonda
    qirq element tugmasi qirqta yaxlit qatorga cho'zilib ketadi.
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
    """Hozir yozilgan matnning terilgan ko'rinishini ko'rsatadi."""
    if not text.strip():
        st.caption("Hali hech narsa yozilmagan. Yuqoridagi tugmalardan foydalaning yoki to'g'ridan-to'g'ri yozing.")
        return
    st.markdown(
        f'<div class="equation-card is-muted"><div class="label">Shunday o\'qiladi</div>'
        f'<div class="formula">{to_display(text)}</div></div>',
        unsafe_allow_html=True,
    )


def example_picker(target_key: str, columns: int = 6) -> None:
    """Tayyor misollarni tenglama maydoniga yuklaydigan tugmalar.

    Tugmada bir so'zli yozuv turadi, shunda butun qator telefon ekraniga sig'adi;
    to'liq nom va tenglamaning o'zi izohda ko'rinadi. ``example-grid`` konteyneri
    qatorni har qanday kenglikda gorizontal saqlaydi.
    """
    st.caption("Yoki misoldan boshlang:")
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
