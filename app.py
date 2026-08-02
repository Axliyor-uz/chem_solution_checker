"""Chemistry Solution Checker — application entry point.

Run with:  ``streamlit run app.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from components.ui import inject_theme  # noqa: E402  (path set up above)

st.set_page_config(
    page_title="Kimyoviy Tenglamalar Tekshiruvi",
    page_icon="⚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = [
    st.Page("pages/Equation_Checker.py", title="Tenglamalar tekshiruvi", icon="⚖️", default=True),
    st.Page("pages/Stoichiometry.py", title="Stexiometriya", icon="🧮"),
    st.Page("pages/Molar_Mass.py", title="Molyar massa", icon="⚗️"),
    st.Page("pages/Periodic_Table.py", title="Davriy jadval", icon="🔬"),
    st.Page("pages/Compound_Info.py", title="Birikma ma'lumoti", icon="🧪"),
    st.Page("pages/History.py", title="Tarix", icon="🕘"),
]


def sidebar_reference() -> None:
    """Notation reminder, always within reach."""
    with st.sidebar:
        st.markdown("### Qanday yoziladi")
        st.markdown(
            """
| Nazarda tutilgan | Yozish |
| --- | --- |
| H₂O | `H2O` |
| Ca(OH)₂ | `Ca(OH)2` |
| SO₄²⁻ | `SO4^2-` yoki `SO42-` |
| Fe³⁺ | `Fe3+` |
| NH₄⁺ | `NH4+` |
| CuSO₄·5H₂O | `CuSO4*5H2O` |
| → | `->` yoki `=` |
| ⇌ | `<=>` |
| holat | `(s) (l) (g) (aq)` |
            """
        )
        st.caption(
            "Klaviatura orqali yozilgan pastki va yuqori indekslar ham ishlaydi — "
            "ular avtomatik aylantiriladi."
        )


inject_theme()
sidebar_reference()
st.navigation(PAGES).run()
