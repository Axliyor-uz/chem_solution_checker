"""Natijani dasturdan tashqariga chiqarish.

To'rtta format, har biri o'z maqsadi uchun: JSON — boshqa dastur uchun,
CSV — jadval uchun, PDF — topshirish uchun, PNG — daftarga qo'yish uchun.
"""

from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Any, Final, Sequence

from components.atom_counter import AtomRow, build_table, mass_balance
from components.explanation import Step
from components.reaction_classifier import classify
from components.validator import ValidationReport
from utils.formatting import format_number

#: Oy nomlari — ``strftime`` mahalliylashtirishga tayanmasligi uchun qo'lda berilgan.
_MONTHS: Final[tuple[str, ...]] = (
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
)


def _stamp() -> str:
    """Joriy sana va vaqt, o'zbekcha oy nomi bilan."""
    now = datetime.now()
    return f"{now.day} {_MONTHS[now.month - 1]} {now.year}, {now:%H:%M}"


def to_dict(report: ValidationReport, steps: Sequence[Step] = ()) -> dict[str, Any]:
    """Bitta tekshiruvning to'liq, mashina o'qiy oladigan yozuvi."""
    payload: dict[str, Any] = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "typed": report.source,
        "verdict": report.headline,
        "valid": report.ok,
        "findings": [
            {
                "level": issue.level,
                "code": issue.code,
                "title": issue.title,
                "detail": issue.detail,
                "fix": issue.fix,
            }
            for issue in report.sorted_issues
        ],
    }
    if report.equation:
        left_mass, right_mass = mass_balance(report.equation)
        payload["equation"] = {
            "read_as": report.equation.ascii,
            "display": report.equation.display,
            "reversible": report.equation.reversible,
            "reactants": [item.ascii for item in report.equation.reactants],
            "products": [item.ascii for item in report.equation.products],
            "reaction_types": [item.name for item in classify(report.equation)],
            "mass_reactants_g_per_mol": round(left_mass, 4),
            "mass_products_g_per_mol": round(right_mass, 4),
        }
        payload["atom_counts"] = [
            {"element": row.element, "left": row.left, "right": row.right,
             "balanced": row.balanced}
            for row in report.rows
        ]
    if report.balance:
        payload["balancing"] = {
            "status": report.balance.status,
            "message": report.balance.message,
            "balanced_equation": report.balance.equation.ascii if report.balance.equation else None,
            "coefficients": report.balance.coefficients,
            "original_coefficients": report.balance.original_coefficients,
        }
    if steps:
        payload["steps"] = [
            {"number": step.number, "title": step.title, "body": step.body,
             "working": step.lines, "equation": step.equation}
            for step in steps
        ]
    return payload


def to_json(report: ValidationReport, steps: Sequence[Step] = ()) -> str:
    """Yozuvning formatlangan JSON ko'rinishi."""
    return json.dumps(to_dict(report, steps), indent=2)


def to_csv(report: ValidationReport) -> str:
    """Atomlar hisobi CSV ko'rinishida — jadvalga tushadigan qism."""
    lines = ["element,reagent_atomlari,mahsulot_atomlari,farq,muvozanat"]
    for row in report.rows:
        lines.append(
            f"{row.element},{row.left},{row.right},{row.difference},{str(row.balanced).lower()}"
        )
    return "\n".join(lines)


def to_pdf(report: ValidationReport, steps: Sequence[Step] = ()) -> bytes:
    """Bir betlik yechim PDF ko'rinishida.

    Returns:
        PDF fayl tarkibi. ReportLab o'rnatilmagan bo'lsa, oddiy matnli
        baytlar qatoriga qaytadi.
    """
    try:
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
        from reportlab.lib import colors
    except ImportError:  # pragma: no cover - depends on deployment
        return _plain_text(report, steps).encode("utf-8")

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title="Kimyoviy yechim tekshiruvi",
    )
    sheet = getSampleStyleSheet()
    heading = ParagraphStyle(
        "heading", parent=sheet["Heading1"], fontSize=16, spaceAfter=2, textColor=colors.HexColor("#0B1017")
    )
    label = ParagraphStyle(
        "label", parent=sheet["Normal"], fontSize=8, textColor=colors.HexColor("#6B7A90"),
        spaceAfter=8, alignment=TA_LEFT,
    )
    body = ParagraphStyle("body", parent=sheet["Normal"], fontSize=9.5, leading=14)
    formula = ParagraphStyle(
        "formula", parent=sheet["Normal"], fontName="Helvetica-Bold", fontSize=13, leading=18,
        spaceBefore=4, spaceAfter=8,
    )
    step_title = ParagraphStyle(
        "stepTitle", parent=sheet["Heading3"], fontSize=10.5, spaceBefore=10, spaceAfter=2
    )

    flow: list[Any] = [
        Paragraph("Kimyoviy yechim tekshiruvi", heading),
        Paragraph(_stamp(), label),
        Paragraph(f"<b>Yozilgani:</b> {_escape(report.source)}", body),
    ]
    if report.equation:
        flow.append(Paragraph(_escape(report.equation.display), formula))
    if report.balance and report.balance.equation and report.balance.succeeded:
        flow.append(Paragraph("<b>Muvozanatlangan:</b>", body))
        flow.append(Paragraph(_escape(report.balance.equation.display), formula))
    flow.append(Paragraph(f"<b>Xulosa:</b> {_escape(report.headline)}", body))
    flow.append(Spacer(1, 6))

    if report.rows:
        flow.append(Paragraph("Atomlar hisobi", step_title))
        flow.append(_atom_table(report.rows))

    for issue in report.sorted_issues:
        text = f"<b>{_escape(issue.title)}</b>"
        if issue.detail:
            text += f"<br/>{_escape(issue.detail)}"
        if issue.fix:
            text += f"<br/><i>Yechim: {_escape(issue.fix)}</i>"
        flow.append(Spacer(1, 4))
        flow.append(Paragraph(text, body))

    if steps:
        flow.append(Paragraph("Yechim qadamlari", step_title))
        for step in steps:
            flow.append(Paragraph(f"{step.number}-qadam — {_escape(step.title)}", step_title))
            flow.append(Paragraph(_escape(step.body), body))
            if step.equation:
                flow.append(Paragraph(f"<font face='Courier'>{_escape(step.equation)}</font>", body))
            for line in step.lines:
                flow.append(Paragraph(f"<font face='Courier'>{_escape(line)}</font>", body))

    document.build(flow)
    return buffer.getvalue()


def _atom_table(rows: Sequence[AtomRow]) -> Any:
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    data = [["Element", "Reagentlar", "Mahsulotlar", "Muvozanat"]]
    for row in rows:
        data.append([row.element, str(row.left), str(row.right), "bor" if row.balanced else "yo'q"])
    table = Table(data, colWidths=[70, 90, 90, 90])
    style = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0B1017")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EDF5")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C3CDDB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for index, row in enumerate(rows, start=1):
        if not row.balanced:
            style.append(("TEXTCOLOR", (0, index), (-1, index), colors.HexColor("#B3202C")))
    table.setStyle(TableStyle(style))
    return table


def to_png(report: ValidationReport) -> bytes:
    """Tenglama va uning atomlar hisobidan iborat, ulashsa bo'ladigan rasm."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = report.rows
    height = 2.4 + 0.34 * max(len(rows), 1)
    figure, axes = plt.subplots(figsize=(7.4, height), dpi=200)
    figure.patch.set_facecolor("#0B1017")
    axes.set_facecolor("#0B1017")
    axes.axis("off")

    equation = report.equation.display if report.equation else report.source
    axes.text(0.0, 1.0, "Yechim tekshiruvi", color="#37C4A6", fontsize=8,
              family="monospace", transform=axes.transAxes, va="top")
    axes.text(0.0, 0.93, equation, color="#E6EDF5", fontsize=13, family="monospace",
              transform=axes.transAxes, va="top", wrap=True)
    balanced = report.balance.equation if report.balance else None
    if balanced and report.balance and report.balance.succeeded:
        axes.text(0.0, 0.80, f"Muvozanatlangan:  {balanced.display}", color="#37C4A6", fontsize=11,
                  family="monospace", transform=axes.transAxes, va="top")
    axes.text(0.0, 0.70, report.headline, color="#8496AD", fontsize=9,
              transform=axes.transAxes, va="top")

    top = 0.60
    axes.text(0.0, top, "ELEMENT      REAGENTLAR   MAHSULOTLAR", color="#8496AD", fontsize=8,
              family="monospace", transform=axes.transAxes, va="top")
    for index, row in enumerate(rows):
        colour = "#37C4A6" if row.balanced else "#E7515F"
        axes.text(
            0.0, top - 0.06 * (index + 1),
            f"{row.element:<12} {row.left:<11} {row.right}",
            color=colour, fontsize=9, family="monospace",
            transform=axes.transAxes, va="top",
        )
    axes.text(0.0, 0.02, _stamp(), color="#57657C", fontsize=7,
              transform=axes.transAxes, va="bottom")

    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", facecolor=figure.get_facecolor(), bbox_inches="tight")
    plt.close(figure)
    return buffer.getvalue()


def _plain_text(report: ValidationReport, steps: Sequence[Step]) -> str:
    lines = [
        "Kimyoviy yechim tekshiruvi",
        _stamp(),
        "",
        f"Yozilgani: {report.source}",
    ]
    if report.equation:
        lines.append(f"O'qilgani: {report.equation.display}")
    if report.balance and report.balance.equation:
        lines.append(f"Muvozanatlangan: {report.balance.equation.display}")
    lines.extend(["", f"Xulosa: {report.headline}", ""])
    for row in report.rows:
        lines.append(f"  {row.element}: {row.left} / {row.right} — {row.short_note}")
    for step in steps:
        lines.extend(["", f"{step.number}-qadam: {step.title}", step.body, *step.lines])
    return "\n".join(lines)


def summary_filename(report: ValidationReport, extension: str) -> str:
    """Ichida nima borligini bildiruvchi fayl nomi."""
    stem = "equation"
    if report.equation:
        stem = report.equation.ascii.replace(" ", "").replace("->", "-to-").replace("<->", "-eq-")
    safe = "".join(char for char in stem if char.isalnum() or char in "-_")[:60] or "equation"
    return f"{safe}.{extension}"


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
