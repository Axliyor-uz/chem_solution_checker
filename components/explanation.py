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
            title="Count the atoms on each side",
            body="Multiply every subscript by the coefficient in front of its formula, "
            "then total each element.",
            rows=original_rows,
            equation=equation.display,
            lines=[
                f"{side}: " + ", ".join(f"{symbol} × {count}" for symbol, count in sorted(totals.items()))
                for side, totals in (
                    ("Reactants", count_side(equation.reactants)),
                    ("Products", count_side(equation.products)),
                )
            ],
        )
    )

    if not unbalanced and result.status == "already_balanced":
        steps.append(
            Step(
                number=2,
                title="Compare the two columns",
                body="Every element already has the same total on both sides, and the "
                "coefficients share no common factor. Nothing needs changing.",
                lines=[f"{row.element}: {row.left} = {row.right}" for row in original_rows],
            )
        )
        steps.append(_charge_step(3, equation) if equation.has_charges else _final_step(3, equation))
        return steps

    steps.append(
        Step(
            number=2,
            title="Find what does not match",
            body="Only the elements whose totals differ need attention. Everything else "
            "is already satisfied and must stay that way.",
            lines=[
                f"{row.element}: {row.left} on the left, {row.right} on the right "
                f"→ {row.short_note}"
                for row in unbalanced
            ]
            or ["Every element matches; only the overall factor is wrong."],
        )
    )

    if not result.succeeded:
        steps.append(
            Step(
                number=3,
                title="Why this cannot be finished",
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
            title="Write one conservation equation per element",
            body="Replace each coefficient with an unknown. Every element gives a linear "
            "equation, because its atoms cannot be created or destroyed.",
            equation=f"{labelled} → {labelled_right}",
            lines=_conservation_lines(equation, symbols),
        )
    )

    steps.append(
        Step(
            number=4,
            title="Solve for the smallest whole numbers",
            body="The system is solved together, then divided by the highest common "
            "factor so the answer is in lowest terms.",
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
                title="Check the balanced equation",
                body="Recount with the new coefficients. Both columns now agree, "
                "which is the definition of balanced.",
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
        lines.append(f"charge:  {' + '.join(left_terms)}  =  {' + '.join(right_terms)}")
    return lines


def _charge_step(number: int, equation: Equation) -> Step:
    left = charge_of_side(equation.reactants)
    right = charge_of_side(equation.products)
    verdict = "matches" if left == right else "does not match"
    return Step(
        number=number,
        title="Check the charge",
        body=f"Net charge {verdict}: {left:+d} on the left, {right:+d} on the right. "
        "In an ionic equation charge is conserved alongside atoms.",
    )


def _final_step(number: int, equation: Equation) -> Step:
    return Step(
        number=number,
        title="Nothing left to do",
        body="The equation is balanced as written.",
        equation=equation.display,
    )


# --------------------------------------------------------------- tutor voice


def tutor_notes(equation: Equation, result: BalanceResult) -> list[tuple[str, str]]:
    """``(heading, explanation)`` pairs about this particular equation."""
    notes: list[tuple[str, str]] = [
        (
            "Why coefficients and never subscripts",
            "Changing a subscript changes the substance: H₂O is water, H₂O₂ is hydrogen "
            "peroxide. Coefficients only change how many molecules you have, which is the "
            "one thing you are free to choose.",
        ),
        (
            "What balancing actually claims",
            "Atoms are rearranged, not created. That single fact is why the totals must "
            "agree, and why the mass on each side comes out the same.",
        ),
    ]

    shared_ions = _intact_ions(equation)
    if shared_ions:
        listed = ", ".join(shared_ions)
        notes.append(
            (
                "Balance these groups as one unit",
                f"{listed} passes through the reaction unchanged. Counting it as a single "
                "block instead of separate atoms saves several steps.",
            )
        )

    types = classify(equation)
    if types:
        primary = types[0].name
        strategy = _STRATEGY_BY_TYPE.get(primary)
        if strategy:
            notes.append((f"Strategy for a {primary.lower()} reaction", strategy))

    oxygen_odd = any(
        item.formula.composition.get("O", 0) % 2 == 1
        for item in equation.products
        if "O" in item.formula.composition
    )
    if oxygen_odd and any(item.formula.composition == {"O": 2} for item in equation.reactants):
        notes.append(
            (
                "The odd-oxygen trick",
                "An odd number of oxygens on the right cannot come from O₂ alone. Allow "
                "yourself a fraction such as 3/2 O₂, finish the balance, then double every "
                "coefficient to clear it.",
            )
        )

    if result.status == "underdetermined":
        notes.append(
            (
                "Why there is more than one answer",
                "Two independent reactions have been written as one line, so the coefficients "
                "have a free parameter. Separate them and each becomes unique.",
            )
        )
    return notes


_STRATEGY_BY_TYPE: Final[dict[str, str]] = {
    "Combustion": "Balance carbon first, then hydrogen, and leave oxygen for last — "
    "oxygen appears in two products, so fixing it first only undoes itself.",
    "Neutralisation (acid–base)": "Balance the metal, then the acid's anion as a unit, "
    "and let water absorb the leftover hydrogen and oxygen.",
    "Double displacement": "Treat each polyatomic ion as a block that swaps partners "
    "intact; only the two cations really move.",
    "Single displacement": "Balance the element that moves first, then the spectator anion.",
    "Decomposition": "Start from the single reactant: whatever it contains has to reappear, "
    "distributed among the products.",
    "Synthesis": "Work backwards from the single product, since it fixes every ratio.",
    "Redox": "If coefficients resist, split the equation into oxidation and reduction "
    "half-reactions, balance electrons, then recombine.",
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
        "Editing a subscript to force the numbers to work — that writes a different compound.",
        "Stopping at the first element that balances instead of rechecking the others.",
    ]
    if any(item.formula.composition.get("O", 0) for item in equation.products):
        mistakes.append("Balancing oxygen early, then breaking it again while fixing hydrogen.")
    if _intact_ions(equation):
        mistakes.append("Splitting a polyatomic ion into separate atoms and losing track of it.")
    if equation.has_charges:
        mistakes.append("Balancing the atoms but forgetting that charge also has to match.")
    if len(equation.species) > 4:
        mistakes.append("Leaving the answer with a common factor still in it, such as 2:4:2.")
    return mistakes


def hints(equation: Equation, result: BalanceResult) -> list[str]:
    """Progressive hints, weakest first. Only the last one gives the answer."""
    rows = build_table(equation)
    unbalanced = [row for row in rows if not row.balanced]
    if not unbalanced:
        return ["Every element already matches — check whether the coefficients share a factor."]

    first = unbalanced[0]
    steps = [
        f"Start with {first.element}. Count it carefully on both sides before touching anything.",
        f"{first.element}: {first.left} on the left, {first.right} on the right — "
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
            steps.append(f"Try changing the coefficient in front of {display}.")
            steps.append(f"{display} needs a coefficient of {value}.")
        steps.append(f"The balanced equation is {result.equation.display}.")
    return steps


def error_report(equation: Equation, result: BalanceResult) -> list[str]:
    """Plain sentences explaining what is wrong, in the order to fix it."""
    lines: list[str] = []
    for row in build_table(equation):
        if row.balanced:
            continue
        lines.append(
            f"{row.element} atoms are not balanced. Left side {row.left}, "
            f"right side {row.right}."
        )
    if result.succeeded and result.equation:
        for display, before, after in result.changes:
            lines.append(f"The coefficient before {display} should become {after} (currently {before}).")
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
        "Give one hint that moves the student forward by a single step. "
        "Do not state the balanced equation or the final coefficients."
        if practice_mode
        else "Explain clearly and completely, showing the reasoning."
    )
    system = (
        "You are a chemistry tutor for high school and first-year university students. "
        "The verified analysis below comes from a symbolic checker and is correct — "
        "never contradict it. Be concise, concrete, and use the student's own equation. "
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
                        "content": f"Verified analysis:\n{context}\n\nStudent asks: {question}",
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
        return f"The AI tutor is unavailable right now ({error.__class__.__name__}). " \
               "The worked steps and notes on this page do not need it."
