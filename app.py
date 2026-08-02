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
    page_title="Chemistry Solution Checker",
    page_icon="⚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = [
    st.Page("pages/Equation_Checker.py", title="Equation checker", icon="⚖️", default=True),
    st.Page("pages/Stoichiometry.py", title="Stoichiometry", icon="🧮"),
    st.Page("pages/Molar_Mass.py", title="Molar mass", icon="⚗️"),
    st.Page("pages/Periodic_Table.py", title="Periodic table", icon="🔬"),
    st.Page("pages/Compound_Info.py", title="Compound info", icon="🧪"),
    st.Page("pages/History.py", title="History", icon="🕘"),
]


def sidebar_reference() -> None:
    """Notation reminder, always within reach."""
    with st.sidebar:
        st.markdown("### How to type it")
        st.markdown(
            """
| You mean | Type |
| --- | --- |
| H₂O | `H2O` |
| Ca(OH)₂ | `Ca(OH)2` |
| SO₄²⁻ | `SO4^2-` or `SO42-` |
| Fe³⁺ | `Fe3+` |
| NH₄⁺ | `NH4+` |
| CuSO₄·5H₂O | `CuSO4*5H2O` |
| → | `->` or `=` |
| ⇌ | `<=>` |
| state | `(s) (l) (g) (aq)` |
            """
        )
        st.caption(
            "Subscripts and superscripts from the keyboard work too — they are "
            "converted for you."
        )


inject_theme()
sidebar_reference()
st.navigation(PAGES).run()
