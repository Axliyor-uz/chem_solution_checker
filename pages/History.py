"""History — everything checked in this session."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.ui import page_header, stats
from utils import history

INPUT_KEY = "equation_input"

page_header(
    "History",
    "Every equation checked in this session, newest first. Nothing leaves the "
    "browser unless you export it.",
    eyebrow="This session",
)

entries = history.all_entries()
if not entries:
    st.info("Nothing checked yet. Head to the equation checker and try one.")
    st.stop()

balanced_count = sum(1 for entry in entries if entry.status.startswith("Balanced"))
stats(
    [
        ("Checked", str(len(entries))),
        ("Came out balanced", str(balanced_count)),
        ("Needed work", str(len(entries) - balanced_count)),
    ]
)

search_columns = st.columns([3, 1])
with search_columns[0]:
    term = st.text_input("Search", placeholder="Fe, combustion, unbalanced…", label_visibility="collapsed")
with search_columns[1]:
    if st.button("Clear history", width="stretch"):
        history.clear()
        st.rerun()

results = history.search(term)
if not results:
    st.caption("No entries match that search.")

for entry in results:
    index = entries.index(entry)
    with st.container(border=True):
        columns = st.columns([5, 2, 1])
        with columns[0]:
            st.markdown(f"**{entry.equation}**")
            if entry.balanced and entry.balanced != "—" and entry.balanced != entry.equation:
                st.caption(f"Balanced: {entry.balanced}")
            if entry.reaction_types:
                st.caption(" · ".join(entry.reaction_types))
        with columns[1]:
            st.caption(entry.when)
            st.caption(entry.status)
        with columns[2]:
            st.button(
                "Reload",
                key=f"reload-{index}",
                on_click=lambda value=entry.source: st.session_state.update({INPUT_KEY: value}),
                width="stretch",
            )
            if st.button("Delete", key=f"delete-{index}", width="stretch"):
                history.delete(index)
                st.rerun()

st.divider()
st.markdown("#### Export")
export_columns = st.columns(3)
rows = history.to_rows()
with export_columns[0]:
    st.download_button(
        "CSV",
        data=pd.DataFrame(rows).to_csv(index=False),
        file_name="chemistry-history.csv",
        mime="text/csv",
        width="stretch",
    )
with export_columns[1]:
    st.download_button(
        "JSON",
        data=history.to_json(),
        file_name="chemistry-history.json",
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
        file_name="chemistry-history.md",
        mime="text/markdown",
        width="stretch",
    )

with st.expander("As a table"):
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
