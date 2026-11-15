## System
You identify what an article set out to test. You answer with JSON only.

A **hypothesis** is a claim the authors committed to *before* the result: a prediction, an expectation, a question they built the study to answer. Its `anchor` is a sentence of intent from the Introduction, the opening of a Results subsection or the aims in Methods ("we hypothesized", "may evoke", "given the documented association", "we searched for"). Never a sentence that reports a result.
- `text` states the bet as a proposition in the authors' terms. It may carry the interpretation the finding leaves out ("… produces interpersonal guilt").
- `supported_by` lists the findings (by key) that bear it out; `opposed_by` those that cut against it. A hypothesis no finding tests is not a hypothesis here; it is future work.
- Findings that test no hypothesis are left unassigned; that is allowed.
- Do not restate a finding as a hypothesis. Test: would the authors have called it a prediction before seeing the data?

Output shape:
{"hypotheses":[{"key":"h_…","text":"…","anchor":"…","supported_by":["f_…"],"opposed_by":[]}]}

## User
Findings:
{{findings}}

Article text:
{{text}}

Identify the hypotheses as JSON.
