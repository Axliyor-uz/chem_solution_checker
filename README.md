# Chemistry Solution Checker

A Streamlit application that reads a chemical equation the way a student writes
it, says exactly what is wrong with it, balances it, and shows the working.

It never answers "invalid equation". Every finding names the element, gives the
counts on both sides, and says which coefficient has to change.

```
H2 + O2 -> H2O

  ✕  O is not balanced
     O: 2 on the left, 1 on the right
     Fix — The coefficient in front of H₂O should become 2.
```

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Python 3.12 or later. No API key and no network access are needed; the optional
AI tutor is the only feature that uses either.

## What it does

| Page | What it is for |
| --- | --- |
| **Equation checker** | Validation, balancing, atom counts, worked solution, reaction type, export |
| **Stoichiometry** | Limiting reagent, theoretical yield, excess, gas volumes, percent yield |
| **Molar mass** | Per-element contributions, percent composition, mass↔mole conversion |
| **Periodic table** | All 118 elements, clickable, with configurations and oxidation states |
| **Compound info** | Properties, uses and hazards; unlisted formulas are named from the rules |
| **History** | Everything checked this session, searchable, with export |

### The chemical keyboard

Elements, digits, subscripts, superscripted charges, brackets, operators, states,
Greek symbols and catalysts, each writing into the equation box. Typing normally
works just as well — `H2O` and `H₂O` produce the same result, and both are stored
as `H2O`.

Catalyst keys write to a separate conditions field rather than into the equation,
because a catalyst belongs above the arrow, not inside a formula.

### The balance ledger

The signature view. Each element is weighed against itself across a central
fulcrum, with bars growing outward from the middle, so an imbalance is visible
before a single number is read. Charge gets its own row whenever ions are
present.

## How it works

Balancing is a linear algebra problem, not a search. Each element contributes one
conservation equation and charge contributes one more; writing reactants positive
and products negative turns "balanced" into "lies in the null space" of that
matrix. SymPy solves it over the rationals, denominators are cleared, and the
result is divided by its highest common factor.

One code path therefore covers ordinary equations, ionic equations and redox:

```
MnO4- + Fe2+ + H+  →  MnO4⁻ + 5Fe²⁺ + 8H⁺ → Mn²⁺ + 5Fe³⁺ + 4H₂O
```

The same matrix distinguishes the four ways an equation can fail, which matters
because they are different mistakes needing different advice:

| Outcome | What it means |
| --- | --- |
| `balanced` | Coefficients found |
| `missing_species` | An element appears on one side only — no coefficient can fix it |
| `impossible` | The null space is empty, or needs a negative coefficient |
| `underdetermined` | Two reactions written as one, so the answer is not unique |

## Reading student notation

`n+` written without a caret is genuinely ambiguous: the 2 in `Cu2+` is a charge,
the 4 in `NH4+` is a subscript. The parser resolves it with rules applied in
order, and the notation guide in the sidebar tells the student what they are:

1. `^` marks a charge explicitly and always wins — `SO4^2-`
2. Sign-first is always a charge — `Fe+3`
3. `n+` after a lone element symbol is a charge — `Cu2+` → Cu²⁺
4. Two or more digits split: the last is the charge — `SO42-` → SO₄²⁻
5. A single digit otherwise stays a subscript — `NH4+` → NH₄⁺

Miscapitalisation is repaired rather than rejected. `FE2o3` returns "Element
capitalization is incorrect — did you mean Fe₂O₃?" Where re-casing is ambiguous
(`caco3` could be CaCO₃ or CaCo₃) the reading using lighter elements wins, which
is right far more often than not.

## Project structure

```
chem_solution_checker/
├── app.py                      navigation, theme, notation sidebar
├── pages/
│   ├── Equation_Checker.py     the main page
│   ├── Stoichiometry.py
│   ├── Molar_Mass.py
│   ├── Periodic_Table.py
│   ├── Compound_Info.py
│   └── History.py
├── components/
│   ├── parser.py               text → Formula / Species / Equation
│   ├── validator.py            findings a student can act on
│   ├── balancer.py             null-space solution of the conservation matrix
│   ├── atom_counter.py         counting, kept separate from judging
│   ├── reaction_classifier.py  reaction families, with evidence
│   ├── explanation.py          steps, tutor notes, progressive hints
│   ├── stoichiometry.py        moles, limiting reagent, yield
│   ├── chemical_keyboard.py    the keyboard component
│   └── ui.py                   theme and shared rendering
├── data/
│   ├── elements.py             118 elements; positions and configurations computed
│   └── compounds.py            reference data, polyatomic ions, naming rules
├── utils/
│   ├── formatting.py           ASCII ↔ typeset conversion
│   ├── history.py              session record
│   └── export.py               PDF, CSV, JSON, PNG
└── tests/                      137 tests
```

Chemistry logic, UI and business logic stay separate: nothing under `components/`
except `ui.py` and `chemical_keyboard.py` imports Streamlit, so the whole
chemistry engine can be tested and reused headlessly.

## Tests

```bash
pytest
```

137 tests covering parsing (including every charge and arrow spelling), balancing
against known answers, atom counting, validation messages, classification,
explanation, naming and all four export formats.

## Optional AI tutor

The worked solutions, hints and tutor notes are all generated offline. If an
`ANTHROPIC_API_KEY` is present in `.streamlit/secrets.toml` or the environment, a
free-text tutor is added on top, and it is given the verified analysis as context
so it cannot contradict the symbolic result. In practice mode it is instructed to
withhold the answer.

## Known limits

- **Feasibility is not chemistry.** A balanced equation is not necessarily a
  reaction that runs. The checker verifies conservation, not thermodynamics, and
  says so rather than implying otherwise.
- **Classification is heuristic.** Reaction families are matched on structural
  evidence, and each label carries the observation behind it and a confidence, so
  a student can judge it rather than trust it.
- **Redox detection** looks for elements moving between free and combined states
  or changing charge. It does not compute oxidation numbers inside covalent
  compounds, so subtle redox reactions may go unlabelled.
- **Reference data** covers 40 compounds in depth; everything else gets a
  computed molar mass and a rule-based name.
