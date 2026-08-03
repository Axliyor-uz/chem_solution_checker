"""Yechilgan tenglamani bosqichma-bosqich yechimga aylantiradi.

Bu yerda uch xil matn tayyorlanadi: qadamlar (nima qilish kerak), ustoz
izohlari (nega shunday) va maslahatlar (mashq rejimi uchun bosqichma-bosqich
yo'l-yo'riq — oxirgisigacha javobni ochib qo'ymaydi).
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
    """Yechimning raqamlangan bitta qadami."""

    number: int
    title: str
    body: str
    rows: list[AtomRow] = field(default_factory=list)
    equation: str | None = None
    lines: list[str] = field(default_factory=list)


def build_steps(equation: Equation, result: BalanceResult) -> list[Step]:
    """Bitta tenglama uchun to'liq yechimni yozadi.

    Args:
        equation: O'quvchi yozgan tenglama, aynan o'sha holida.
        result: Muvozanatlagichdan chiqqan natija.

    Returns:
        Tartibdagi qadamlar. Muvozanatlash bo'lmasa, qadamlar xato ko'rinadigan
        joyda to'xtaydi.
    """
    steps: list[Step] = []
    original_rows = build_table(equation)
    unbalanced = [row for row in original_rows if not row.balanced]

    steps.append(
        Step(
            number=1,
            title="Har ikki tomondagi atomlarni sanang",
            body="Har bir pastki indeksni formulasi oldidagi koeffitsiyentga ko'paytiring, "
            "so'ng har bir elementni jamlang.",
            rows=original_rows,
            equation=equation.display,
            lines=[
                f"{side}: " + ", ".join(f"{symbol} × {count}" for symbol, count in sorted(totals.items()))
                for side, totals in (
                    ("Reagentlar", count_side(equation.reactants)),
                    ("Mahsulotlar", count_side(equation.products)),
                )
            ],
        )
    )

    if not unbalanced and result.status == "already_balanced":
        steps.append(
            Step(
                number=2,
                title="Ikkala ustunni solishtiring",
                body="Har bir elementning yig'indisi ikkala tomonda allaqachon bir xil va "
                "koeffitsiyentlarning umumiy bo'luvchisi yo'q. Hech narsani o'zgartirish shart emas.",
                lines=[f"{row.element}: {row.left} = {row.right}" for row in original_rows],
            )
        )
        steps.append(_charge_step(3, equation) if equation.has_charges else _final_step(3, equation))
        return steps

    steps.append(
        Step(
            number=2,
            title="Mos kelmayotganini toping",
            body="Faqat yig'indilari farq qiladigan elementlarga e'tibor kerak. Qolganlari "
            "allaqachon joyida va shundayligicha qolishi kerak.",
            lines=[
                f"{row.element}: chapda {row.left}, o'ngda {row.right} "
                f"→ {row.short_note}"
                for row in unbalanced
            ]
            or ["Har bir element mos keladi; faqat umumiy ko'paytuvchi noto'g'ri."],
        )
    )

    if not result.succeeded:
        steps.append(
            Step(
                number=3,
                title="Nega buni oxiriga yetkazib bo'lmaydi",
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
            title="Har bir element uchun bitta saqlanish tenglamasini yozing",
            body="Har bir koeffitsiyentni noma'lum bilan almashtiring. Har bir element chiziqli "
            "tenglama beradi, chunki uning atomlari yo'qdan bor bo'lmaydi va yo'qolmaydi.",
            equation=f"{labelled} → {labelled_right}",
            lines=_conservation_lines(equation, symbols),
        )
    )

    steps.append(
        Step(
            number=4,
            title="Eng kichik butun sonlarni toping",
            body="Sistema birgalikda yechiladi, so'ng javob eng kichik holatga kelishi uchun "
            "eng katta umumiy bo'luvchiga bo'linadi.",
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
                title="Muvozanatlangan tenglamani tekshiring",
                body="Yangi koeffitsiyentlar bilan qaytadan sanang. Endi ikkala ustun mos keladi — "
                "muvozanatlangan degani aynan shu.",
                rows=build_table(result.equation),
                equation=result.equation.display,
            )
        )
        if result.equation.has_charges:
            steps.append(_charge_step(6, result.equation))
    return steps


def _conservation_lines(equation: Equation, symbols: list[str]) -> list[str]:
    """``H: 2a = 2c`` ko'rinishidagi qatorlar — har bir element uchun bittadan, ustiga zaryad."""
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
        "Ionli tenglamada zaryad ham atomlar qatori saqlanadi.",
    )


def _final_step(number: int, equation: Equation) -> Step:
    return Step(
        number=number,
        title="Qiladigan ish qolmadi",
        body="Tenglama yozilgan holida muvozanatlangan.",
        equation=equation.display,
    )


# ------------------------------------------------------------- ustoz izohlari


def tutor_notes(equation: Equation, result: BalanceResult) -> list[tuple[str, str]]:
    """Aynan shu tenglama haqida ``(sarlavha, izoh)`` juftliklari."""
    notes: list[tuple[str, str]] = [
        (
            "Nega faqat koeffitsiyent, hech qachon pastki indeks emas",
            "Pastki indeksni o'zgartirsangiz, modda o'zgaradi: H₂O — suv, H₂O₂ — vodorod "
            "peroksid. Koeffitsiyent esa faqat molekulalar sonini o'zgartiradi va aynan "
            "shuni tanlash sizning ixtiyoringizda.",
        ),
        (
            "Muvozanatlash aslida nimani anglatadi",
            "Atomlar qaytadan joylashadi, yangidan yaratilmaydi. Yig'indilar mos kelishi "
            "va har ikki tomondagi massa teng chiqishi shundan.",
        ),
    ]

    shared_ions = _intact_ions(equation)
    if shared_ions:
        listed = ", ".join(shared_ions)
        notes.append(
            (
                "Bu guruhlarni bitta birlik sifatida tenglashtiring",
                f"{listed} reaksiyadan o'zgarmay o'tadi. Uni alohida atomlar emas, yaxlit "
                "blok sifatida sanash bir necha qadamni tejaydi.",
            )
        )

    types = classify(equation)
    if types:
        primary = types[0].name
        strategy = _STRATEGY_BY_TYPE.get(primary)
        if strategy:
            notes.append((f"{primary} reaksiyasi uchun strategiya", strategy))

    oxygen_odd = any(
        item.formula.composition.get("O", 0) % 2 == 1
        for item in equation.products
        if "O" in item.formula.composition
    )
    if oxygen_odd and any(item.formula.composition == {"O": 2} for item in equation.reactants):
        notes.append(
            (
                "Toq kisloroddagi hiyla",
                "O'ngdagi toq sondagi kislorod faqat O₂ dan kela olmaydi. Avval 3/2 O₂ kabi "
                "kasr koeffitsiyentga ruxsat bering, muvozanatni tugating, so'ng kasrdan "
                "qutulish uchun barcha koeffitsiyentlarni ikkilantiring.",
            )
        )

    if result.status == "underdetermined":
        notes.append(
            (
                "Nega javob bittadan ko'p",
                "Ikkita mustaqil reaksiya bitta qatorga yozilgan, shuning uchun koeffitsiyentlarda "
                "erkin parametr bor. Ularni ajratsangiz, har biri yagona javobga ega bo'ladi.",
            )
        )
    return notes


_STRATEGY_BY_TYPE: Final[dict[str, str]] = {
    "Yonish": "Avval uglerodni, keyin vodorodni tenglashtiring, kislorodni esa oxiriga "
    "qoldiring — kislorod ikkita mahsulotda uchraydi, shuning uchun uni birinchi "
    "tenglashtirish keyin baribir buziladi.",
    "Neytrallanish (kislota–asos)": "Avval metallni, so'ng kislota anionini yaxlit birlik "
    "sifatida tenglashtiring, ortib qolgan vodorod va kislorodni suv o'ziga oladi.",
    "Almashinish": "Har bir murakkab ionni butun holda o'rin almashadigan blok deb qarang; "
    "aslida faqat ikkita kation joyini o'zgartiradi.",
    "O'rin almashinish": "Avval o'rin almashayotgan elementni, keyin o'zgarmaydigan anionni "
    "tenglashtiring.",
    "Parchalanish": "Yagona reagentdan boshlang: uning tarkibidagi hamma narsa mahsulotlar "
    "orasida qaytadan paydo bo'lishi shart.",
    "Birikish": "Yagona mahsulotdan teskari yo'nalishda boring — u barcha nisbatlarni belgilaydi.",
    "Oksidlanish-qaytarilish": "Koeffitsiyentlar chiqmasa, tenglamani oksidlanish va qaytarilish "
    "yarim reaksiyalariga bo'ling, elektronlarni tenglashtiring va qayta birlashtiring.",
}


def _intact_ions(equation: Equation) -> list[str]:
    """Ikkala tomondagi birikmalar ichida uchraydigan murakkab ionlar."""
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
    """Aynan shu tenglamada o'quvchi ko'proq yo'l qo'yadigan xatolar."""
    mistakes: list[str] = [
        "Sonlar to'g'ri chiqsin deb pastki indeksni o'zgartirish — bu butunlay boshqa birikma bo'lib qoladi.",
        "Birinchi element muvozanatga kelishi bilan to'xtab, qolganlarini qayta tekshirmaslik.",
    ]
    if any(item.formula.composition.get("O", 0) for item in equation.products):
        mistakes.append("Kislorodni erta tenglashtirib, keyin vodorodni to'g'rilashda uni yana buzib qo'yish.")
    if _intact_ions(equation):
        mistakes.append("Murakkab ionni alohida atomlarga bo'lib yuborib, uni ko'zdan qochirish.")
    if equation.has_charges:
        mistakes.append("Atomlarni tenglashtirib, zaryad ham mos kelishi kerakligini unutish.")
    if len(equation.species) > 4:
        mistakes.append("Javobda umumiy bo'luvchini qoldirib yuborish, masalan 2:4:2.")
    return mistakes


def hints(equation: Equation, result: BalanceResult) -> list[str]:
    """Bosqichma-bosqich maslahatlar. Javobni faqat oxirgisi beradi."""
    rows = build_table(equation)
    unbalanced = [row for row in rows if not row.balanced]
    if not unbalanced:
        return ["Har bir element allaqachon mos keladi — koeffitsiyentlarning umumiy bo'luvchisi bor-yo'qligini tekshiring."]

    first = unbalanced[0]
    steps = [
        f"{first.element} dan boshlang. Hech narsaga tegmasdan avval uni ikkala tomonda diqqat bilan sanang.",
        f"{first.element}: chapda {first.left}, o'ngda {first.right} — "
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
            steps.append(f"{display} uchun koeffitsiyent {value} bo'lishi kerak.")
        steps.append(f"Muvozanatlangan tenglama: {result.equation.display}.")
    return steps


def error_report(equation: Equation, result: BalanceResult) -> list[str]:
    """Nima xato ekanini tuzatish tartibida tushuntiruvchi oddiy jumlalar."""
    lines: list[str] = []
    for row in build_table(equation):
        if row.balanced:
            continue
        lines.append(
            f"{row.element} atomlari muvozanatlanmagan. Chap tomonda {row.left}, "
            f"o'ng tomonda {row.right}."
        )
    if result.succeeded and result.equation:
        for display, before, after in result.changes:
            lines.append(f"{display} oldidagi koeffitsiyent {after} bo'lishi kerak (hozir {before}).")
    elif result.message:
        lines.append(result.message)
    return lines


# ------------------------------------------------- ixtiyoriy sun'iy intellekt


def tutor_context(equation: Equation, result: BalanceResult) -> str:
    """Joriy masalaning ixcham JSON tavsifi — sun'iy intellekt ustozi uchun."""
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
    """Claude'dan tushuntirishni so'raydi, kontekst sifatida tekshirgich natijasini beradi.

    Yuqoridagi oflayn tushuntirishlar asosiy hisoblanadi; bu esa API kalitini
    talab qiladigan ixtiyoriy qo'shimcha. Mashq rejimida modelga yakuniy javobni
    bermay, faqat maslahat berish topshiriladi.

    Args:
        question: O'quvchining savoli.
        context: :func:`tutor_context` natijasi.
        api_key: Anthropic API kaliti.
        practice_mode: Javobni yashirib turish kerakmi.
        timeout: Javobni necha soniya kutish.

    Returns:
        Ustozning javobi yoki so'rov muvaffaqiyatsiz bo'lsa, tushuntiruvchi xabar.
    """
    import requests  # Tarmoq kutubxonalarisiz ham ishlashi uchun kech import qilinadi.

    style = (
        "O'quvchini bir qadam oldinga siljitadigan bitta maslahat bering. "
        "Muvozanatlangan tenglamani ham, yakuniy koeffitsiyentlarni ham aytmang."
        if practice_mode
        else "Fikr yuritish yo'lini ko'rsatib, aniq va to'liq tushuntiring."
    )
    system = (
        "Siz maktab o'quvchilari va birinchi kurs talabalari uchun kimyo o'qituvchisisiz. "
        "Quyidagi tekshirilgan tahlil ramziy tekshirgichdan olingan va to'g'ri — unga "
        "hech qachon zid gapirmang. Qisqa va aniq javob bering, o'quvchining o'z "
        "tenglamasidan foydalaning. Javobni o'zbek tilida yozing. "
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
                        "content": f"Tekshirilgan tahlil:\n{context}\n\nO'quvchining savoli: {question}",
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
    except Exception as error:  # noqa: BLE001 - o'quvchiga ko'rsatiladi, yashirilmaydi
        return f"Sun'iy intellekt ustozi hozir mavjud emas ({error.__class__.__name__}). " \
               "Bu sahifadagi qadamlar va izohlar unsiz ham ishlaydi."
