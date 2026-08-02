"""A record of what the student has already checked.

History lives in Streamlit's session state, so nothing is written to disk
without the student choosing to export it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Final

import streamlit as st

STATE_KEY: Final[str] = "history"
MAX_ENTRIES: Final[int] = 200


@dataclass(slots=True)
class HistoryEntry:
    """One checked equation."""

    timestamp: str
    source: str
    equation: str
    balanced: str
    status: str
    reaction_types: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def moment(self) -> datetime:
        return datetime.fromisoformat(self.timestamp)

    @property
    def when(self) -> str:
        return self.moment.strftime("%d %b %H:%M")

    def matches(self, term: str) -> bool:
        term = term.strip().lower()
        if not term:
            return True
        haystack = " ".join(
            [self.source, self.equation, self.balanced, self.status, *self.reaction_types]
        ).lower()
        return term in haystack

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _store() -> list[HistoryEntry]:
    if STATE_KEY not in st.session_state:
        st.session_state[STATE_KEY] = []
    return st.session_state[STATE_KEY]


def record(
    source: str,
    equation: str,
    balanced: str,
    status: str,
    reaction_types: list[str] | None = None,
    notes: str = "",
) -> HistoryEntry:
    """Add an entry, skipping an immediate duplicate of the last one."""
    entries = _store()
    entry = HistoryEntry(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        source=source.strip(),
        equation=equation,
        balanced=balanced,
        status=status,
        reaction_types=reaction_types or [],
        notes=notes,
    )
    if entries and entries[0].source == entry.source and entries[0].status == entry.status:
        entries[0] = entry
        return entry
    entries.insert(0, entry)
    del entries[MAX_ENTRIES:]
    return entry


def all_entries() -> list[HistoryEntry]:
    """Every entry, newest first."""
    return list(_store())


def search(term: str) -> list[HistoryEntry]:
    """Entries matching a search term across every field."""
    return [entry for entry in _store() if entry.matches(term)]


def delete(index: int) -> None:
    """Remove one entry by position."""
    entries = _store()
    if 0 <= index < len(entries):
        entries.pop(index)


def clear() -> None:
    """Remove every entry."""
    st.session_state[STATE_KEY] = []


def to_json() -> str:
    """The whole history as JSON."""
    return json.dumps([entry.to_dict() for entry in _store()], indent=2)


def to_rows() -> list[dict[str, Any]]:
    """Flat rows for a table or CSV export."""
    return [
        {
            "Tekshirilgan vaqti": entry.when,
            "Kiritilgan": entry.source,
            "Tenglama": entry.equation,
            "Tenglashtirilgan": entry.balanced,
            "Holati": entry.status,
            "Reaksiya turlari": ", ".join(entry.reaction_types),
        }
        for entry in _store()
    ]
