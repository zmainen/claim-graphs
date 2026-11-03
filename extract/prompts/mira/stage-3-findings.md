## System
You state the findings an article's evidence supports. You answer with JSON only.

A **finding** is the proposition a group of evidence items supports: one per figure-panel group, or per result the authors state as a conclusion. Rules:
- Where the article states the finding in one sentence (abstract, the topic sentence of a Results paragraph, a Discussion summary), use that sentence as `text`, verbatim, and as `anchor`.
- Otherwise write `text` in the article's own terms, stating only the result. No statistics in `text` (they live in the evidence). No interpretation beyond the result.
- An interpretation the authors state as a sentence ("suggesting that this region is sensitive to …") is its own finding, with `interprets` naming the finding it reads; an interpretation the authors only gesture at goes in `notes`.
- `supported_by` lists evidence keys; `opposed_by` lists evidence that cuts against it. Every evidence item must appear under at least one finding; every finding must have at least one supporter.

Output shape:
{"findings":[{"key":"f_…","text":"…","anchor":"…","supported_by":["e_…"],"opposed_by":[],"interprets":null,"notes":""}]}

## User
Evidence (from the previous stage):
{{evidence}}

Article text:
{{text}}

State the findings as JSON.
