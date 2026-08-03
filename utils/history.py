"""O'quvchi allaqachon tekshirgan ishlar yozuvi.

Tarix Streamlit sessiya holatida saqlanadi, ya'ni o'quvchi eksport qilishni
tanlamaguncha diskka hech narsa yozilmaydi.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Final

import streamlit as st

STATE_KEY: Final[str] = "history"
MAX_ENTRIES: Final[int] = 200

#: Oy nomlari — ``strftime`` mahalliylashtirishga tayanmasligi uchun qo'lda berilgan.
MONTHS_SHORT: Final[tuple[str, ...]] = (
    "yan", "fev", "mar", "apr", "may", "iyn",
    "iyl", "avg", "sen", "okt", "noy", "dek",
)


@dataclass(slots=True)
class HistoryEntry:
    """Tekshirilgan bitta tenglama."""

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
        moment = self.moment
        return f"{moment.day} {MONTHS_SHORT[moment.month - 1]} {moment:%H:%M}"

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
    """Yozuv qo'shadi; oxirgi yozuvning aynan takrori bo'lsa, uni almashtiradi."""
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
    """Barcha yozuvlar, eng yangisi birinchi."""
    return list(_store())


def search(term: str) -> list[HistoryEntry]:
    """Barcha maydonlar bo'yicha qidiruv so'roviga mos yozuvlar."""
    return [entry for entry in _store() if entry.matches(term)]


def delete(index: int) -> None:
    """Bitta yozuvni o'rni bo'yicha o'chiradi."""
    entries = _store()
    if 0 <= index < len(entries):
        entries.pop(index)


def clear() -> None:
    """Barcha yozuvlarni o'chiradi."""
    st.session_state[STATE_KEY] = []


def to_json() -> str:
    """Butun tarix JSON ko'rinishida."""
    return json.dumps([entry.to_dict() for entry in _store()], indent=2)


def to_rows() -> list[dict[str, Any]]:
    """Jadval yoki CSV eksporti uchun yassi qatorlar."""
    return [
        {
            "Tekshirilgan vaqt": entry.when,
            "Yozilgani": entry.source,
            "O'qilgani": entry.equation,
            "Muvozanatlangani": entry.balanced,
            "Natija": entry.status,
            "Reaksiya turlari": ", ".join(entry.reaction_types),
        }
        for entry in _store()
    ]
