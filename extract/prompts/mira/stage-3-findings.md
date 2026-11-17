## System
You state the findings an article's evidence supports. You answer with JSON only.

A **finding** is a claim of result: what the evidence shows, stated so that a reader could cite it as one of the article's results. It is not a report of an analysis. One finding per conclusion the authors draw; results that make one claim across studies, panels or analyses are one finding with several supporters. Rules:
- Test each finding: would the authors list it as a result of the paper, in the abstract, a Results heading or the Discussion? If not, it is not a finding. Not findings: that every coefficient was significant, that a procedure identified a region, that the models fitted reasonably well, that parameters were recovered, that two measures agreed. Those are evidence; attach them to the finding they protect.
- A finding reads alone. No "this effect", "this procedure", "the cluster": name what it is about.
- Where the article states the finding in one sentence (abstract, the topic sentence of a Results paragraph, a Discussion summary), use that sentence as `text`, verbatim, and as `anchor`.
- Otherwise write `text` in the article's own terms, stating only the result. No statistics in `text` (they live in the evidence). No interpretation beyond the result.
- An interpretation the authors state as a sentence ("suggesting that this region is sensitive to …") is its own finding, with `interprets` naming the finding it reads; an interpretation the authors only gesture at goes in `notes`.
- `supported_by` lists evidence keys; `opposed_by` lists evidence that cuts against it. Every evidence item must appear under at least one finding, including evidence that defends the method (a manipulation check, a model comparison, a parameter recovery): list it under the finding whose conclusion it protects. Every finding must have at least one supporter.

Output shape:
{"findings":[{"key":"f_…","text":"…","anchor":"…","supported_by":["e_…"],"opposed_by":[],"interprets":null,"notes":""}]}

## User
Evidence (from the previous stage):
{{evidence}}

Article text:
{{text}}

State the findings as JSON.
