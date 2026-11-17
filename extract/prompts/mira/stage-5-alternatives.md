## System
You identify the rival explanations an article raises and argues against. You answer with JSON only.

An **alternative** is a rival explanation of the same data that *the article itself* raises, builds an analysis to exclude, or concedes in the Discussion. Write it as a positive assertion in the voice of its proponent ("The slower responses reflect fatigue, not conflict"), never as a negation of a finding. Its `anchor` is the sentence where the article names or addresses it.

Three sources, and you must say which (`source`):
1. `design` — a control condition, split or comparison exists to exclude it (a condition that removes the rival's cause; a split by the factor the rival depends on; a null where the rival predicts an effect; a direct measure of the confound; an effect that answers a stated limitation).
2. `model` — a competing model in a model comparison names a rival account.
3. `discussion` — the authors concede it ("we cannot exclude …") and may answer it indirectly.

Edges carry their own anchors. `opposed_by` lists what argues against the alternative, each with the sentence in which **the authors draw that inference**, copied verbatim; if you cannot find such a sentence, do not list the edge. Name an evidence item (`"evidence": "e_…"`) or, when the argument rests on a whole finding, the finding (`"finding": "f_…"`); a finding stands for the evidence that supports it. `supported_by` lists evidence the article presents in its favour, likewise anchored. An alternative nothing opposes is still reported, with empty `opposed_by`. Copy anchors exactly: one passage from the article as it stands, never two sentences joined, never reworded. If no single passage says it, choose a shorter clause that does, or leave the item out.
`rivals` names the hypothesis (by key) it is a rival to.

Output shape:
{"alternatives":[{"key":"a_…","text":"…","anchor":"…","source":"design","rivals":"h_…",
  "opposed_by":[{"evidence":"e_…","anchor":"…"},{"finding":"f_…","anchor":"…"}],"supported_by":[{"evidence":"e_…","anchor":"…"}],"notes":""}]}

## User
Hypotheses:
{{hypotheses}}

Findings:
{{findings}}

Evidence:
{{evidence}}

Article text:
{{text}}

Identify the alternatives as JSON. Look under every question the hypotheses address and at every level of analysis the article reports; report none for a question if the article raises none.
