"""Tarix — shu sessiyada tekshirilgan hamma narsa."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.ui import page_header, stats
from utils import history

INPUT_KEY = "equation_input"

page_header(
    "Tarix",
    "Shu sessiyada tekshirilgan har bir tenglama, eng yangisi birinchi. Siz eksport "
    "qilmaguningizcha hech narsa brauzerdan chiqmaydi.",
    eyebrow="Shu sessiya",
)

entries = history.all_entries()
if not entries:
    st.info("Hali hech narsa tekshirilmagan. Tenglama tekshirgichga o'tib, bittasini sinab ko'ring.")
    st.stop()

balanced_count = sum(1 for entry in entries if entry.status.startswith("Muvozanatlangan"))
stats(
    [
        ("Tekshirilgan", str(len(entries))),
        ("Muvozanatlangan", str(balanced_count)),
        ("Ishlash kerak", str(len(entries) - balanced_count)),
    ]
)

search_columns = st.columns([3, 1])
with search_columns[0]:
    term = st.text_input("Qidirish", placeholder="Fe, yonish, muvozanatlanmagan…", label_visibility="collapsed")
with search_columns[1]:
    if st.button("Tarixni tozalash", width="stretch"):
        history.clear()
        st.rerun()

results = history.search(term)
if not results:
    st.caption("Bu so'rovga mos yozuv topilmadi.")

for entry in results:
    index = entries.index(entry)
    with st.container(border=True):
        columns = st.columns([5, 2, 1])
        with columns[0]:
            st.markdown(f"**{entry.equation}**")
            if entry.balanced and entry.balanced != "—" and entry.balanced != entry.equation:
                st.caption(f"Muvozanatlangan: {entry.balanced}")
            if entry.reaction_types:
                st.caption(" · ".join(entry.reaction_types))
        with columns[1]:
            st.caption(entry.when)
            st.caption(entry.status)
        with columns[2]:
            st.button(
                "Qayta yuklash",
                key=f"reload-{index}",
                on_click=lambda value=entry.source: st.session_state.update({INPUT_KEY: value}),
                width="stretch",
            )
            if st.button("O'chirish", key=f"delete-{index}", width="stretch"):
                history.delete(index)
                st.rerun()

st.divider()
st.markdown("#### Eksport")
export_columns = st.columns(3)
rows = history.to_rows()
with export_columns[0]:
    st.download_button(
        "CSV",
        data=pd.DataFrame(rows).to_csv(index=False),
        file_name="kimyo-tarixi.csv",
        mime="text/csv",
        width="stretch",
    )
with export_columns[1]:
    st.download_button(
        "JSON",
        data=history.to_json(),
        file_name="kimyo-tarixi.json",
        mime="application/json",
        width="stretch",
    )
with export_columns[2]:
    st.download_button(
        "Markdown",
        data="\n".join(
            f"- **{entry.equation}** → {entry.balanced} ({entry.status}, {entry.when})"
            for entry in entries
        ),
        file_name="kimyo-tarixi.md",
        mime="text/markdown",
        width="stretch",
    )

with st.expander("Jadval ko'rinishida"):
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
