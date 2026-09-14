# Converge the two perspective readings

Two readers have read the same whole document from opposite ends. The **evidence reader**
worked upward from what the document shows — its figures, panels, reported values, and the
findings it inherits from citations. The **argument reader** worked downward from what the
document claims — its question, the answer it commits to, the rivals it names, what it says it
does not establish.

Your job is to produce one claim table from the two, and — this is the part that carries the
information — to record **which side each proposition came from**.

## Why the sides matter more than the count

Do not grade a claim by how many readers found it. The two readers read the same text, so
convergence is cheap and a tally of it says almost nothing. What says something is where a
proposition appears on one side only, because each kind of one-sidedness names a specific
defect in the document's argument:

| where it appeared | what it means | `origin` |
|:--|:--|:--|
| both readers | the argument and the evidence meet here — the document both claims it and shows it | `both` |
| argument only | the document asserts this and nothing in it shows it. An unbacked assertion, or evidence that lives only in a citation the evidence reader did not surface | `argument-only` |
| evidence only | the document shows this and no part of its argument uses it. An orphan result, or a premise the argument leans on silently | `evidence-only` |

Neither one-sided category is automatically a fault. A review is *expected* to be dense with
`argument-only` claims resting on citations, and a methods-heavy paper with `evidence-only`
ones. The point is that the shape is visible and can be read against what the document is
trying to be, instead of being averaged into a grade.

## What to do

1. Take every proposition from both readers. Two claims are the same proposition when they
   would be true or false together — not when they share words. Readers phrase the same claim
   very differently, and a claim and its negation are never the same proposition.
2. Where both found it, write it once, in the wording that states it most precisely, and set
   `origin: both`. Keep the evidence quote from the evidence reader and the panel anchor from
   whichever reader anchored it to a real part.
3. Where one found it, keep it as written and set `origin` accordingly.
4. Merge nothing that states two different propositions, and split nothing that states one.
   Where a claim states a whole that two others each partly establish, keep the whole and mark
   the parts `part-of` rather than emitting three near-duplicates.
5. Never introduce a number, a panel id or a wording that neither reader recorded.

## What not to do

- Do not drop a claim for being one-sided. That is the measurement, not noise.
- Do not manufacture symmetry by inventing a counterpart on the missing side.
- Do not re-grade confidence by counting readers. `origin` replaces that; a `confidence` you
  cannot justify from the readers' own labels should stay as the reader left it.

Return the converged table in the schema below, each claim carrying `origin`, and nothing else.
