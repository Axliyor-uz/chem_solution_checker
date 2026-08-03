"""Dasturning ko'rinishi — bitta joyda.

Rang tanlovi olov sinovidan olingan — natriy sarig'i, mis yashili, stronsiy
qizili, kaliy siyohrangi — quyuq siyoh fonida, shuning uchun interfeys ranglari
o'zi xizmat qilayotgan fanda ma'no kasb etadi. Yashil — muvozanat, qizil —
muvozanatsizlik, sariq — ogohlantirish.
"""

from __future__ import annotations

import html
from typing import Iterable, Sequence

import streamlit as st

from components.atom_counter import AtomRow
from components.explanation import Step
from components.validator import Issue

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root {
  --ink: #0B1017;
  --slab: #131B26;
  --slab-2: #18222F;
  --line: #243040;
  --paper: #E6EDF5;
  --muted: #8496AD;
  --sodium: #F0A028;
  --copper: #37C4A6;
  --strontium: #E7515F;
  --potassium: #9A86F0;
  --display: 'Space Grotesk', system-ui, sans-serif;
  --body: 'Inter', system-ui, sans-serif;
  --mono: 'IBM Plex Mono', ui-monospace, monospace;
}

.stApp { background: var(--ink); color: var(--paper); font-family: var(--body); }
section[data-testid="stSidebar"] { background: #090D13; border-right: 1px solid var(--line); }
h1, h2, h3, h4 { font-family: var(--display); letter-spacing: -0.01em; color: var(--paper); }

/* Sarlavha ------------------------------------------------------------- */
.masthead { border-bottom: 1px solid var(--line); padding: 0.2rem 0 1.1rem; margin-bottom: 1.4rem; }
.masthead .eyebrow {
  font-family: var(--mono); font-size: 0.7rem; letter-spacing: 0.18em;
  text-transform: uppercase; color: var(--copper); margin-bottom: 0.45rem;
}
.masthead h1 { font-size: 2rem; margin: 0 0 0.3rem; line-height: 1.1; }
.masthead p { color: var(--muted); margin: 0; font-size: 0.94rem; max-width: 60ch; }

/* Tenglama ko'rsatkichi ------------------------------------------------ */
.equation-card {
  background: var(--slab); border: 1px solid var(--line); border-left: 3px solid var(--copper);
  border-radius: 4px; padding: 1.1rem 1.25rem; margin: 0.5rem 0 1rem;
}
.equation-card .label {
  font-family: var(--mono); font-size: 0.68rem; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--muted); margin-bottom: 0.5rem;
}
.equation-card .formula {
  font-family: var(--mono); font-size: 1.45rem; font-weight: 500;
  color: var(--paper); word-break: break-word; line-height: 1.45;
}
.equation-card.is-error { border-left-color: var(--strontium); }
.equation-card.is-muted { border-left-color: var(--line); }
.equation-card.is-muted .formula { color: var(--muted); font-size: 1.15rem; }

/* Muvozanat tarozisi — asosiy element ----------------------------------- */
.ledger { border: 1px solid var(--line); border-radius: 4px; overflow: hidden; margin: 0.4rem 0 0.9rem; }
.ledger-head {
  display: grid; grid-template-columns: 3.2rem 1fr 3.6rem 1fr 3.2rem;
  font-family: var(--mono); font-size: 0.66rem; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--muted); background: var(--slab-2); padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--line);
}
.ledger-head span:nth-child(2) { text-align: right; }
.ledger-head span:nth-child(3), .ledger-head span:nth-child(5) { text-align: center; }
.ledger-row {
  display: grid; grid-template-columns: 3.2rem 1fr 3.6rem 1fr 3.2rem; align-items: center;
  padding: 0.42rem 0.75rem; border-bottom: 1px solid rgba(36,48,64,0.55); background: var(--slab);
}
.ledger-row:last-child { border-bottom: none; }
.ledger-row .sym {
  font-family: var(--mono); font-weight: 600; font-size: 0.95rem; color: var(--paper);
}
.ledger-row .count {
  font-family: var(--mono); font-size: 0.9rem; color: var(--paper); text-align: center;
}
.ledger-row .count.dim { color: var(--muted); }
.pan { height: 9px; border-radius: 2px; display: flex; }
.pan.left { justify-content: flex-end; }
.pan .fill { height: 100%; border-radius: 2px; }
.pan .fill.ok { background: var(--copper); }
.pan .fill.off { background: var(--strontium); }
.pan .fill.short { background: rgba(231,81,95,0.28); border: 1px dashed rgba(231,81,95,0.75); }
.fulcrum {
  font-family: var(--mono); font-size: 0.72rem; text-align: center; color: var(--muted);
}
.fulcrum.off { color: var(--strontium); font-weight: 600; }
.fulcrum.ok { color: var(--copper); }

/* Xulosalar ------------------------------------------------------------- */
.finding {
  display: grid; grid-template-columns: 1.6rem 1fr; gap: 0.55rem;
  border: 1px solid var(--line); border-radius: 4px; padding: 0.75rem 0.9rem;
  margin-bottom: 0.55rem; background: var(--slab);
}
.finding .mark {
  font-family: var(--mono); font-weight: 700; font-size: 0.95rem; line-height: 1.35;
}
.finding .title { font-weight: 600; font-size: 0.95rem; line-height: 1.35; }
.finding .detail { color: var(--muted); font-size: 0.86rem; margin-top: 0.22rem; line-height: 1.5; }
.finding .fix {
  font-size: 0.86rem; margin-top: 0.45rem; padding-top: 0.45rem;
  border-top: 1px dashed var(--line); color: var(--paper);
}
.finding .fix b { font-family: var(--mono); font-weight: 600; color: var(--sodium); }
.finding.error { border-left: 3px solid var(--strontium); }
.finding.error .mark { color: var(--strontium); }
.finding.warning { border-left: 3px solid var(--sodium); }
.finding.warning .mark { color: var(--sodium); }
.finding.success { border-left: 3px solid var(--copper); }
.finding.success .mark { color: var(--copper); }
.finding.info { border-left: 3px solid var(--potassium); }
.finding.info .mark { color: var(--potassium); }

/* Qadamlar ---------------------------------------------------------------- */
.step { border-left: 1px solid var(--line); padding: 0 0 1.3rem 1.3rem; margin-left: 0.85rem; position: relative; }
.step:last-child { padding-bottom: 0.3rem; }
.step .no {
  position: absolute; left: -0.86rem; top: 0; width: 1.7rem; height: 1.7rem;
  border-radius: 50%; background: var(--slab-2); border: 1px solid var(--line);
  font-family: var(--mono); font-size: 0.78rem; color: var(--copper);
  display: flex; align-items: center; justify-content: center;
}
.step h4 { margin: 0.15rem 0 0.35rem; font-size: 1rem; }
.step p { color: var(--muted); font-size: 0.9rem; line-height: 1.6; margin: 0 0 0.5rem; }
.step .work {
  font-family: var(--mono); font-size: 0.87rem; background: var(--slab);
  border: 1px solid var(--line); border-radius: 4px; padding: 0.6rem 0.8rem;
  color: var(--paper); line-height: 1.75; white-space: pre-wrap;
}

/* Ko'rsatkichlar ---------------------------------------------------------- */
.stat-grid { display: flex; flex-wrap: wrap; gap: 0.6rem; margin: 0.3rem 0 1rem; }
.stat {
  flex: 1 1 8.5rem; background: var(--slab); border: 1px solid var(--line);
  border-radius: 4px; padding: 0.65rem 0.8rem;
}
.stat .k {
  font-family: var(--mono); font-size: 0.64rem; letter-spacing: 0.13em;
  text-transform: uppercase; color: var(--muted);
}
.stat .v { font-family: var(--mono); font-size: 1.15rem; font-weight: 600; margin-top: 0.2rem; }

/* Davriy jadval ----------------------------------------------------------- */
.ptable { display: grid; grid-template-columns: repeat(18, minmax(0, 1fr)); gap: 2px; }
.ptable .cell {
  aspect-ratio: 1; border-radius: 2px; padding: 2px; display: flex;
  flex-direction: column; justify-content: center; align-items: center;
  border: 1px solid transparent; min-height: 27px;
}
.ptable .cell .z { font-family: var(--mono); font-size: 0.44rem; opacity: 0.65; line-height: 1; }
.ptable .cell .s { font-family: var(--mono); font-size: 0.72rem; font-weight: 600; line-height: 1.15; }
.ptable .gap { visibility: hidden; }
.ptable .cell.selected { outline: 2px solid var(--paper); outline-offset: -2px; }
.legend { display: flex; flex-wrap: wrap; gap: 0.4rem 0.9rem; margin-top: 0.7rem; }
.legend span { font-size: 0.72rem; color: var(--muted); display: flex; align-items: center; gap: 0.3rem; }
.legend i { width: 9px; height: 9px; border-radius: 2px; display: inline-block; }

/* Streamlit vidjetlarini moslash ------------------------------------------- */
.stTextArea textarea, .stTextInput input {
  font-family: var(--mono) !important; background: var(--slab) !important;
  color: var(--paper) !important; border: 1px solid var(--line) !important;
  border-radius: 4px !important; font-size: 1.02rem !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
  border-color: var(--copper) !important; box-shadow: 0 0 0 1px var(--copper) !important;
}
div.stButton > button {
  font-family: var(--mono); background: var(--slab-2); color: var(--paper);
  border: 1px solid var(--line); border-radius: 3px; padding: 0.3rem 0.1rem;
  font-size: 0.85rem; width: 100%; transition: border-color 90ms ease, color 90ms ease;
}
div.stButton > button:hover { border-color: var(--copper); color: var(--copper); }
div.stButton > button:focus-visible { outline: 2px solid var(--paper); outline-offset: 1px; }
div.stButton > button[kind="primary"] {
  background: var(--copper); color: #06231C; border-color: var(--copper); font-weight: 600;
}
div.stButton > button[kind="primary"]:hover { background: #45D8B8; color: #06231C; }
/* Tugmalar to'ri — klaviatura va misollar ----------------------------------
   Streamlit 640px dan tor ekranda ustunlarni bitta qatorga bittadan tizadi, bu
   esa qirq element tugmasini qirqta yaxlit qatorga aylantiradi. Bu to'rlar
   har qanday kenglikda gorizontal qoladi. */
.st-key-example-grid [data-testid="stHorizontalBlock"],
[class*="st-key-keygrid"] [data-testid="stHorizontalBlock"] {
  flex-wrap: nowrap !important; gap: 0.25rem !important;
}
.st-key-example-grid [data-testid="stColumn"],
[class*="st-key-keygrid"] [data-testid="stColumn"] {
  min-width: 0 !important; flex: 1 1 0 !important;
}
[class*="st-key-keygrid"] > [data-testid="stVerticalBlock"] { gap: 0.25rem !important; }
.st-key-example-grid div.stButton > button,
[class*="st-key-keygrid"] div.stButton > button {
  padding: 0.2rem 0.1rem; font-size: 0.76rem; min-height: 0; line-height: 1.35;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.st-key-example-grid div.stButton > button { font-size: 0.72rem; }
.st-key-keygrid-edit div.stButton > button { font-size: 0.72rem; }
.stTabs [data-baseweb="tab"] { font-family: var(--mono); font-size: 0.82rem; }
.stTabs [aria-selected="true"] { color: var(--copper) !important; }
div[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 4px; }
.stAlert { border-radius: 4px; }
hr { border-color: var(--line); }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
@media (max-width: 640px) {
  .masthead h1 { font-size: 1.5rem; }
  .equation-card .formula { font-size: 1.15rem; }
  .ledger-head, .ledger-row { grid-template-columns: 2.4rem 1fr 3rem 1fr 2.4rem; }
}
</style>
"""

CATEGORY_COLORS: dict[str, str] = {
    "ishqoriy metall": "#F0A028",
    "ishqoriy-yer metall": "#D98A3A",
    "o'tish metali": "#37C4A6",
    "o'tishdan keyingi metall": "#2E9C89",
    "metalloid": "#9A86F0",
    "metallmas": "#5A8FD8",
    "galogen": "#7BB3E8",
    "inert gaz": "#B07BD8",
    "lantanoid": "#E7515F",
    "aktinoid": "#C4444F",
}


def inject_theme() -> None:
    """Har bir sahifa chizilganda uslublar jadvalini qo'llaydi."""
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str, eyebrow: str = "") -> None:
    """Sahifa sarlavhasini chizadi."""
    st.markdown(
        f"""<div class="masthead">
        {f'<div class="eyebrow">{html.escape(eyebrow)}</div>' if eyebrow else ''}
        <h1>{html.escape(title)}</h1>
        <p>{html.escape(subtitle)}</p></div>""",
        unsafe_allow_html=True,
    )


def equation_card(text: str, label: str = "Tenglama", variant: str = "") -> None:
    """Formula yoki tenglamani monoshrift kartochkasida ko'rsatadi."""
    css_class = f"equation-card {variant}".strip()
    st.markdown(
        f"""<div class="{css_class}">
        <div class="label">{html.escape(label)}</div>
        <div class="formula">{html.escape(text)}</div></div>""",
        unsafe_allow_html=True,
    )


def balance_ledger(rows: Sequence[AtomRow], charges: tuple[int, int] | None = None) -> None:
    """Asosiy ko'rinish: har bir element tayanch nuqtasi atrofida o'zi bilan taroziga qo'yiladi.

    Ustunlar markazdan tashqariga qarab o'sadi, shuning uchun muvozanatsizlik
    birorta raqamni o'qishdan oldin notekis juftlik sifatida ko'rinadi.
    """
    if not rows:
        st.caption("Hozircha tortiladigan atom yo'q.")
        return
    peak = max(max(row.left, row.right) for row in rows) or 1
    body = [
        '<div class="ledger"><div class="ledger-head">'
        "<span>Element</span><span>Reagentlar</span><span>Muvozanat</span>"
        "<span>Mahsulotlar</span><span>Δ</span></div>"
    ]
    for row in rows:
        left_pct = row.left / peak * 100
        right_pct = row.right / peak * 100
        if row.balanced:
            left_class = right_class = "ok"
            mark, mark_class = "=", "ok"
        else:
            left_class = "off" if row.left > row.right else "short"
            right_class = "off" if row.right > row.left else "short"
            mark, mark_class = ("≠", "off")
        delta = "0" if row.balanced else f"{row.difference:+d}"
        body.append(
            f'<div class="ledger-row">'
            f'<span class="sym">{html.escape(row.element)}</span>'
            f'<span class="pan left"><span class="fill {left_class}" style="width:{left_pct:.1f}%"></span></span>'
            f'<span class="count">{row.left}<span class="fulcrum {mark_class}"> {mark} </span>{row.right}</span>'
            f'<span class="pan right"><span class="fill {right_class}" style="width:{right_pct:.1f}%"></span></span>'
            f'<span class="count {"dim" if row.balanced else ""}">{delta}</span>'
            f"</div>"
        )
    if charges is not None:
        left_charge, right_charge = charges
        ok = left_charge == right_charge
        body.append(
            f'<div class="ledger-row"><span class="sym">q</span>'
            f'<span class="pan left"></span>'
            f'<span class="count">{left_charge:+d}'
            f'<span class="fulcrum {"ok" if ok else "off"}"> {"=" if ok else "≠"} </span>'
            f"{right_charge:+d}</span>"
            f'<span class="pan right"></span>'
            f'<span class="count {"dim" if ok else ""}">{right_charge - left_charge:+d}</span></div>'
        )
    body.append("</div>")
    st.markdown("".join(body), unsafe_allow_html=True)


def findings(issues: Iterable[Issue]) -> None:
    """Tekshirgich xulosalarini kartochkalar ko'rinishida chizadi."""
    for issue in issues:
        detail = f'<div class="detail">{html.escape(issue.detail)}</div>' if issue.detail else ""
        fix = f'<div class="fix"><b>Yechim</b> — {html.escape(issue.fix)}</div>' if issue.fix else ""
        st.markdown(
            f'<div class="finding {issue.level}"><div class="mark">{issue.icon}</div>'
            f'<div><div class="title">{html.escape(issue.title)}</div>{detail}{fix}</div></div>',
            unsafe_allow_html=True,
        )


def steps_view(steps: Sequence[Step]) -> None:
    """Bosqichma-bosqich yechimni chizadi."""
    for step in steps:
        work = ""
        if step.equation:
            work += html.escape(step.equation)
        if step.lines:
            work += ("\n" if work else "") + "\n".join(html.escape(line) for line in step.lines)
        block = f'<div class="work">{work}</div>' if work else ""
        st.markdown(
            f'<div class="step"><div class="no">{step.number}</div>'
            f"<h4>{html.escape(step.title)}</h4>"
            f"<p>{html.escape(step.body)}</p>{block}</div>",
            unsafe_allow_html=True,
        )
        if step.rows:
            balance_ledger(step.rows)


def stats(items: Sequence[tuple[str, str]], accent: str = "var(--paper)") -> None:
    """Nomlangan qiymatlar qatori."""
    cards = "".join(
        f'<div class="stat"><div class="k">{html.escape(key)}</div>'
        f'<div class="v" style="color:{accent}">{html.escape(value)}</div></div>'
        for key, value in items
    )
    st.markdown(f'<div class="stat-grid">{cards}</div>', unsafe_allow_html=True)


def category_legend() -> None:
    """Davriy jadval uchun rang izohi."""
    entries = "".join(
        f'<span><i style="background:{color}"></i>{html.escape(name)}</span>'
        for name, color in CATEGORY_COLORS.items()
    )
    st.markdown(f'<div class="legend">{entries}</div>', unsafe_allow_html=True)
