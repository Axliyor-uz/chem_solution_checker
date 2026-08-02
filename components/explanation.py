"""Turning a solved equation into a worked solution.

Three registers are produced here: the steps (what to do), the tutor notes
(why it works), and the hints (progressive nudges for practice mode, which
stop short of the answer until the last one).
"""

from __future__ import annotations

import json
import string
from dataclasses import dataclass, field
from typing import Final

from components.atom_counter import AtomRow, build_table, charge_of_side, count_side
from components.balancer import BalanceResult
from components.parser import Equation
from components.reaction_classifier import classify
from data.compounds import POLYATOMIC_IONS

_LETTERS: Final[str] = string.ascii_lowercase
_API_URL: Final[str] = "https://api.anthropic.com/v1/messages"
_TUTOR_MODEL: Final[str] = "claude-sonnet-4-6"


@dataclass(slots=True)
class Step:
    """One numbered step of a worked solution."""

    number: int
    title: str
    body: str
    rows: list[AtomRow] = field(default_factory=list)
    equation: str | None = None
    lines: list[str] = field(default_factory=list)


def build_steps(equation: Equation, result: BalanceResult) -> list[Step]:
    """Write the worked solution for one equation.

    Args:
        equation: The equation exactly as the student wrote it.
        result: The outcome from the balancer.

    Returns:
        Steps in order. If balancing failed, the steps stop at the point
        where the failure becomes visible.
    """
    steps: list[Step] = []
    original_rows = build_table(equation)
    unbalanced = [row for row in original_rows if not row.balanced]

    steps.append(
        Step(
            number=1,
            title="Har ikki tomondagi atomlarni sanang",
            body="Har bir indeksni uning formulasi oldidagi koeffitsiyentga ko'paytiring, "
            "so'ngra har bir element bo'yicha yig'indini hisoblang.",
            rows=original_rows,
            equation=equation.display,
            lines=[
                f"{side}: " + ", ".join(f"{symbol} × {count}" for symbol, count in sorted(totals.items()))
                for side, totals in (
                    ("Reaktivlar", count_side(equation.reactants)),
                    ("Mahsulotlar", count_side(equation.products)),
                )
            ],
        )
    )

    if not unbalanced and result.status == "already_balanced":
        steps.append(
            Step(
                number=2,
                title="Ikkala ustunni taqqoslang",
                body="Har bir element allaqachon ikkala tomonda bir xil yig'indiga ega va "
                "koeffitsiyentlar umumiy bo'luvchiga ega emas. Hech narsani o'zgartirish kerak emas.",
                lines=[f"{row.element}: {row.left} = {row.right}" for row in original_rows],
            )
        )
        steps.append(_charge_step(3, equation) if equation.has_charges else _final_step(3, equation))
        return steps

    steps.append(
        Step(
            number=2,
            title="Nimasi mos kelmasligini toping",
            body="Faqat yig'indisi farq qiladigan elementlarga e'tibor qaratish kerak. Qolgan hamma narsa "
            "allaqachon to'g'ri va xuddi shunday qolishi kerak.",
            lines=[
                f"{row.element}: chapda {row.left} ta, o'ngda {row.right} ta "
                f"→ {row.short_note}"
                for row in unbalanced
            ]
            or ["Barcha elementlar mos keladi; faqat umumiy ko'paytuvchi xato."],
        )
    )

    if not result.succeeded:
        steps.append(
            Step(
                number=3,
                title="Nima uchun buni yakunlab bo'lmaydi",
                body=result.message,
                lines=[],
            )
        )
        return steps

    symbols = [_LETTERS[index] for index in range(len(equation.species))]
    labelled = " + ".join(
        f"{symbol}·{item.formula.display}" for symbol, item in zip(symbols, equation.reactants)
    )
    labelled_right = " + ".join(
        f"{symbol}·{item.formula.display}"
        for symbol, item in zip(symbols[len(equation.reactants):], equation.products)
    )
    steps.append(
        Step(
            number=3,
            title="Har bir element uchun bittadan saqlanish tenglamasini yozing",
            body="Har bir koeffitsiyentni noma'lum bilan almashtiring. Har bir element bitta chiziqli "
            "tenglama beradi, chunki uning atomlari yo'qolib ketmaydi yoki o'z-o'zidan paydo bo'lmaydi.",
            equation=f"{labelled} → {labelled_right}",
            lines=_conservation_lines(equation, symbols),
        )
    )

    steps.append(
        Step(
            number=4,
            title="Eng kichik butun sonlarni toping",
            body="Tizim birgalikda yechiladi, so'ngra javob eng qisqargan ko'rinishda "
            "bo'lishi uchun eng katta umumiy bo'luvchiga bo'linadi.",
            lines=[
                f"{symbol} = {value}"
                for symbol, value in zip(symbols, result.coefficients)
            ],
            equation=result.equation.display if result.equation else None,
        )
    )

    if result.equation:
        steps.append(
            Step(
                number=5,
                title="Tenglashtirilgan tenglamani tekshiring",
                body="Yangi koeffitsiyentlar bilan qayta sanang. Ikkala ustun endi mos keladi, "
                "bu tenglashtirilganlikning ta'rifidir.",
                rows=build_table(result.equation),
                equation=result.equation.display,
            )
        )
        if result.equation.has_charges:
            steps.append(_charge_step(6, result.equation))
    return steps


def _conservation_lines(equation: Equation, symbols: list[str]) -> list[str]:
    """Render ``H: 2a = 2c`` style lines, one per element plus charge."""
    split = len(equation.reactants)
    lines: list[str] = []
    for element in equation.elements:
        left_terms: list[str] = []
        right_terms: list[str] = []
        for index, item in enumerate(equation.species):
            count = item.formula.composition.get(element, 0)
            if not count:
                continue
            term = symbols[index] if count == 1 else f"{count}{symbols[index]}"
            (left_terms if index < split else right_terms).append(term)
        lines.append(f"{element}:  {' + '.join(left_terms)}  =  {' + '.join(right_terms)}")
    if equation.has_charges:
        left_terms = [
            f"{item.formula.charge:+d}{symbols[index]}"
            for index, item in enumerate(equation.species)
            if index < split and item.formula.charge
        ]
        right_terms = [
            f"{item.formula.charge:+d}{symbols[index]}"
            for index, item in enumerate(equation.species)
            if index >= split and item.formula.charge
        ]
        lines.append(f"zaryad:  {' + '.join(left_terms)}  =  {' + '.join(right_terms)}")
    return lines


def _charge_step(number: int, equation: Equation) -> Step:
    left = charge_of_side(equation.reactants)
    right = charge_of_side(equation.products)
    verdict = "mos keladi" if left == right else "mos kelmaydi"
    return Step(
        number=number,
        title="Zaryadni tekshiring",
        body=f"Umumiy zaryad {verdict}: chapda {left:+d}, o'ngda {right:+d}. "
        "Ionli tenglamada zaryad atomlar bilan birga saqlanib qoladi.",
    )


def _final_step(number: int, equation: Equation) -> Step:
    return Step(
        number=number,
        title="Qiladigan boshqa ish qolmadi",
        body="Tenglama yozilganidek tenglashtirilgan.",
        equation=equation.display,
    )


# --------------------------------------------------------------- tutor voice


def tutor_notes(equation: Equation, result: BalanceResult) -> list[tuple[str, str]]:
    """``(heading, explanation)`` pairs about this particular equation."""
    notes: list[tuple[str, str]] = [
        (
            "Nima uchun indekslar emas, doim koeffitsiyentlar",
            "Indeksni o'zgartirish moddani o'zgartiradi: H₂O suv, H₂O₂ vodorod peroksidi. "
            "Koeffitsiyentlar faqat nechta molekula borligini o'zgartiradi, bu esa siz erkin tanlay oladigan yagona narsadir.",
        ),
        (
            "Tenglashtirish aslida nimani anglatadi",
            "Atomlar qayta taqsimlanadi, yangidan yaratilmaydi. Aynan shu bitta fakt nima uchun yig'indilar "
            "mos kelishi kerakligini va nima uchun har ikki tomondagi massa bir xil chiqishini tushuntiradi.",
        ),
    ]

    shared_ions = _intact_ions(equation)
    if shared_ions:
        listed = ", ".join(shared_ions)
        notes.append(
            (
                "Bu guruhlarni bir butun sifatida tenglashtiring",
                f"{listed} reaksiyadan o'zgarmasdan o'tadi. Uni alohida atomlar sifatida emas, "
                "balki yaxlit bir blok sifatida hisoblash bir necha qadamni tejaydi.",
            )
        )

    types = classify(equation)
    if types:
        primary = types[0].name
        strategy = _STRATEGY_BY_TYPE.get(primary)
        if strategy:
            notes.append((f"{primary.lower()} reaksiyasi uchun strategiya".capitalize(), strategy))

    oxygen_odd = any(
        item.formula.composition.get("O", 0) % 2 == 1
        for item in equation.products
        if "O" in item.formula.composition
    )
    if oxygen_odd and any(item.formula.composition == {"O": 2} for item in equation.reactants):
        notes.append(
            (
                "Toq kislorod usuli",
                "O'ng tomondagi toq sondagi kislorod faqat O₂ dan kelib chiqa olmaydi. O'zingizga "
                "3/2 O₂ kabi kasr sonni ishlatishga ruxsat bering, tenglashtirishni tugating va "
                "uni yo'qotish uchun har bir koeffitsiyentni ikkiga ko'paytiring.",
            )
        )

    if result.status == "underdetermined":
        notes.append(
            (
                "Nima uchun bittadan ko'p javob bor",
                "Ikkita mustaqil reaksiya bitta qator qilib yozilgan, shuning uchun koeffitsiyentlarda "
                "erkin parametr bor. Ularni ajrating, shunda har biri yagona javobga ega bo'ladi.",
            )
        )
    return notes


_STRATEGY_BY_TYPE: Final[dict[str, str]] = {
    "Yonish": "Avval uglerodni, so'ngra vodorodni tenglashtiring va kislorodni oxiriga qoldiring — "
    "kislorod ikkita mahsulotda uchraydi, shuning uchun uni birinchi bo'lib to'g'rilash faqat qilingan ishni yo'qqa chiqaradi.",
    "Neytrallanish (kislota-asos)": "Metalni, so'ngra kislota anionini bir butun sifatida tenglashtiring, "
    "suv esa qolgan vodorod va kislorodni o'zlashtiradi.",
    "Ikki tomonlama o'rin olish": "Har bir ko'patomli ionni hamkorini o'zgartiruvchi butun bir blok sifatida qarating; "
    "faqat ikkita kation o'rin almashadi.",
    "O'rin olish": "Avval o'rnini o'zgartirgan elementni, keyin esa tomoshabin anionni tenglashtiring.",
    "Parchalanish": "Yagona reaktivdan boshlang: u nimadan iborat bo'lsa, mahsulotlar orasida taqsimlanishi kerak.",
    "Birlashish": "Yagona mahsulotdan orqaga qarab ishlang, chunki u barcha nisbatlarni belgilab beradi.",
    "Oksidlanish-qaytarilish": "Agar koeffitsiyentlarni topish qiyin bo'lsa, tenglamani oksidlanish va qaytarilish "
    "yarim reaksiyalariga ajrating, elektronlarni tenglashtiring, keyin qayta birlashtiring.",
}


def _intact_ions(equation: Equation) -> list[str]:
    """Polyatomic ions that appear inside compounds on both sides."""
    left_text = " ".join(item.formula.raw for item in equation.reactants)
    right_text = " ".join(item.formula.raw for item in equation.products)
    found: list[str] = []
    for ion in sorted(POLYATOMIC_IONS, key=len, reverse=True):
        if len(ion) < 2:
            continue
        if ion in left_text and ion in right_text and not any(ion in seen for seen in found):
            found.append(ion)
    return found


def common_mistakes(equation: Equation) -> list[str]:
    """Mistakes a student is likely to make on this specific equation."""
    mistakes: list[str] = [
        "Raqamlarni moslashtirish uchun indeksni o'zgartirish — bu butunlay boshqa birikmani anglatadi.",
        "Boshqalarini qayta tekshirish o'rniga, tenglashgan birinchi elementda to'xtab qolish.",
    ]
    if any(item.formula.composition.get("O", 0) for item in equation.products):
        mistakes.append("Kislorodni erta tenglashtirib qo'yish, keyin vodorodni to'g'rilash jarayonida uni yana buzish.")
    if _intact_ions(equation):
        mistakes.append("Ko'patomli ionni alohida atomlarga ajratib yuborish va uni yo'qotib qo'yish.")
    if equation.has_charges:
        mistakes.append("Atomlarni tenglashtirish, ammo zaryad ham mos kelishi kerakligini unutish.")
    if len(equation.species) > 4:
        mistakes.append("Javobda hali ham umumiy bo'luvchi qolib ketishi, masalan 2:4:2.")
    return mistakes


def hints(equation: Equation, result: BalanceResult) -> list[str]:
    """Progressive hints, weakest first. Only the last one gives the answer."""
    rows = build_table(equation)
    unbalanced = [row for row in rows if not row.balanced]
    if not unbalanced:
        return ["Barcha elementlar allaqachon mos keladi — koeffitsiyentlarda umumiy bo'luvchi bor-yo'qligini tekshiring."]

    first = unbalanced[0]
    steps = [
        f"{first.element} dan boshlang. Biror narsani o'zgartirishdan oldin uni ikkala tomonda ehtiyotkorlik bilan sanab chiqing.",
        f"{first.element}: chapda {first.left} ta, o'ngda {first.right} ta — "
        f"{first.short_note}.",
    ]
    if result.succeeded and result.equation:
        changes = [
            (species.formula.display, after)
            for species, before, after in zip(
                equation.species, result.original_coefficients, result.coefficients
            )
            if before != after
        ]
        relevant = [
            (species.formula.display, after)
            for species, before, after in zip(
                equation.species, result.original_coefficients, result.coefficients
            )
            if before != after and first.element in species.formula.composition
        ]
        if relevant or changes:
            display, value = (relevant or changes)[0]
            steps.append(f"{display} oldidagi koeffitsiyentni o'zgartirib ko'ring.")
            steps.append(f"{display} ga {value} koeffitsiyent kerak.")
        steps.append(f"Tenglashtirilgan tenglama: {result.equation.display}.")
    return steps


def error_report(equation: Equation, result: BalanceResult) -> list[str]:
    """Plain sentences explaining what is wrong, in the order to fix it."""
    lines: list[str] = []
    for row in build_table(equation):
        if row.balanced:
            continue
        lines.append(
            f"{row.element} atomlari tenglashmagan. Chap tomonda {row.left}, "
            f"o'ng tomonda {row.right}."
        )
    if result.succeeded and result.equation:
        for display, before, after in result.changes:
            lines.append(f"{display} oldidagi koeffitsiyent {after} bo'lishi kerak (hozir {before}).")
    elif result.message:
        lines.append(result.message)
    return lines


# ----------------------------------------------------------- optional AI hook


def tutor_context(equation: Equation, result: BalanceResult) -> str:
    """Compact JSON description of the current problem, for the AI tutor."""
    return json.dumps(
        {
            "equation": equation.ascii,
            "balanced": result.equation.ascii if result.equation else None,
            "status": result.status,
            "atom_counts": [
                {"element": row.element, "left": row.left, "right": row.right}
                for row in build_table(equation)
            ],
            "reaction_types": [item.name for item in classify(equation)],
        },
        indent=None,
    )


def ask_ai_tutor(
    question: str,
    context: str,
    api_key: str,
    practice_mode: bool = False,
    timeout: int = 30,
) -> str:
    """Ask Claude to explain, using the checker's own results as context.

    The offline explanations above are the default; this is an optional extra
    that needs an API key. In practice mode the model is told to withhold the
    final answer and give a hint instead.

    Args:
        question: The student's question.
        context: Output of :func:`tutor_context`.
        api_key: Anthropic API key.
        practice_mode: Whether to withhold the answer.
        timeout: Seconds to wait for a response.

    Returns:
        The tutor's reply, or an explanatory message if the call failed.
    """
    import requests  # Imported lazily so the app runs without network libraries.

    style = (
        "O'quvchini bir qadam oldinga siljitadigan bitta ishora bering. "
        "Tenglashtirilgan tenglamani yoki yakuniy koeffitsiyentlarni aytmang."
        if practice_mode
        else "Fikrlash jarayonini ko'rsatgan holda, aniq va to'liq tushuntiring."
    )
    system = (
        "Siz o'rta maktab va universitetning birinchi bosqich talabalari uchun kimyo o'qituvchisisiz. "
        "Quyidagi tasdiqlangan tahlil simvolik tekshiruvchidan olingan va u to'g'ri — "
        "hech qachon unga qarshi chiqmang. Qisqa, aniq bo'ling va o'quvchining o'z tenglamasidan foydalaning. "
        f"{style}"
    )
    try:
        response = requests.post(
            _API_URL,
            headers={
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": _TUTOR_MODEL,
                "max_tokens": 700,
                "system": system,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Tasdiqlangan tahlil:\n{context}\n\nO'quvchining savoli: {question}",
                    }
                ],
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return "".join(
            block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text"
        ).strip()
    except Exception as error:  # noqa: BLE001 - surfaced to the student, not swallowed
        return f"Ayni paytda AI o'qituvchi mavjud emas ({error.__class__.__name__}). " \
               "Ushbu sahifadagi batafsil yechim va eslatmalar usiz ham ishlaydi."
