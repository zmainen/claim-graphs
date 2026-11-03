# MIRA de novo: the eight stages

**Status:** specification, 2026-11-01. Written from the Gädeke hand build (graph v1.1.0, tag
`gadeke-mira-v1.1.0` in elife-claim-trees) so that the same graph can be produced de novo on this
paper and others. Each stage is a contract: what it reads, the rule it applies, what it emits, what
the checker refuses, and which nodes of the Gädeke reference it is responsible for. Prompts are
written from these contracts, not the other way round.

**Why stages.** A single call over a paper yields the authors' assertions and nothing eliminative
(eleven baseline runs; see the error catalogue). The hand build succeeded because it was a sequence
of narrow judgements in the order the information appears in a paper, each under a hard constraint:
anchors verbatim, evidence tied to a panel, every panel covered, every claim reaching a question,
every edge legal in MIRA. Those constraints are already code (`gadeke_hand.py`'s build checks,
`mira_verify.py`). The pipeline inherits them unchanged. Each stage is an agent that *proposes*
nodes and a checker that *accepts* them; nothing enters the graph on the agent's say-so.

**Conventions that hold at every stage.**

- The text is the Reviewed Preprint as eLife Pathways serves it, flattened by `mira_page_text.py`.
  Every node has an `anchor`, verbatim in that text; optional `anchors` for further passages. An
  agent output without a verbatim anchor is discarded, not repaired.
- Node fields follow the delivered JSON: `id`, `type`, `text`, `description`, `anchor`, and the
  extras `subtype`, `panel`, `study`, `figure`, `notes`, `sourceDocument`. Ids are typed
  (Q H F A E K C R S P D) and assigned at assembly, so stages use provisional keys.
- A stage writes its output as its own file under `runs/<paper>/mira-denovo/<stage>.json`, so a
  human can adjudicate between stages and a later stage can be re-run alone.
- Each stage declares its *reference set*: the Gädeke nodes it must reproduce. Alignment is by
  meaning for claims and by shared statistics for evidence (`mira_align.py`, extended with a
  judged match for text). The target per stage is stated as recall of the reference set and
  precision of what is added; the overall target is a graph that passes the verifier and aligns on
  findings and alternatives, not identity with the hand graph.

---

## Stage 1 — Text and inventory

**Reads.** The paper's msid and version.

**Rule.** Fetch and flatten the page text; list every figure, panel, table and supplementary item
named in captions or cited in the text; list the studies (experiments with their own participants)
and the protocols (named procedures in Methods: task, manipulations, measures, analyses). A study
is a MIRA Study; a procedure is a Protocol followed by the studies that used it. This stage is
mostly deterministic; the agent's judgement is only in naming protocols at a useful grain (ten for
Gädeke: task, partner algorithm, icebreaker, happiness probe, risk estimation, happiness models,
mixed models, fMRI pipeline, PPI, signature comparison).

**Emits.** `text.txt`; `figures.json` (panel → IIIF image, thumbnail, page link); `inventory.json`
with `panels` (the completeness list), `studies` (S nodes with participant counts and setting,
anchored to Methods) and `protocols` (P nodes anchored to their Methods sentence, with
`follows` edges from studies).

**Checker refuses.** A study without an anchor naming participants; a protocol no study follows;
a panel list that omits any "Figure N[A-Z]" or "Table N" string that occurs in the text.

**Gädeke reference.** S1, S2; P1–P10; the 27-panel list (Figures 1–5 by panel, Table 1,
Supplementary Figure 2). Also D1, the paper itself, with its DOI.

**Known failures.** Protocol grain drifts (one node per Methods paragraph, or one per sentence).
Fix by the rule: a protocol is something a study *follows* and evidence can be *about*.

---

## Stage 2 — Evidence per panel

**Reads.** Text, inventory, one panel (or panel group) at a time.

**Rule.** For the panel, find every result sentence that reports it and emit one Evidence node per
reported result: `text` restates the result with its statistic in one sentence; `anchor` is the
sentence (or the statistic clause) verbatim; `panel` names the panel; `study` names the study the
result belongs to; `figure` is filled from `figures.json`. Two studies reporting the same effect are
two nodes (E23 and E24), because they are two measurements. A result reported in Methods or a
supplementary table without a figure is still evidence, with `panel` naming the section or table
(K3, K5, K6, E21, E22, E38, E39).

**Emits.** `evidence.json`: Evidence nodes with `grounds` edges from their study.

**Checker refuses.** An Evidence node whose anchor is not verbatim; one without `study`; one whose
`panel` is a figure but has no `figure` entry; a panel in the inventory that no node covers (this
is the stage's completeness criterion, and it is the reason to iterate per panel rather than per
paper).

**Gädeke reference.** E5–E39 and K1–K8 (the Check mark is applied in Stage 6; here they are plain
evidence). 43 nodes, 27 panels.

**Known failures.** Paraphrase that drops the statistic; merging two studies into one node; a
panel "covered" by a caption sentence rather than a result. The extractor's baseline runs show
all three.

`★ Insight` This is the stage where the hand build gained most over the extractor, and for a
mechanical reason: the unit of work is a panel, not a paper. Asked for "the evidence", a model
summarises; asked for "the results that cite Figure 3D", it transcribes. Completeness becomes
checkable because the inventory is a list.

---

## Stage 3 — Findings as groupings of evidence

**Reads.** Text, the evidence set.

**Rule.** A finding is the proposition a group of evidence supports: one Claim per figure-panel
group or per result the authors state as a conclusion. `text` states the result as a proposition.
Where the paper itself states the finding in one sentence (abstract, Results topic sentence,
Discussion summary), use that sentence verbatim; otherwise write it in the paper's own terms with
no interpretation beyond the result. Each Evidence node must `support` or `oppose` at least one
finding; each finding must be supported by at least one. Interpretations the authors offer
("suggesting that this part of prefrontal cortex is sensitive to guilt-related information") are
their own Claim, supported by the finding, only when the authors state them as a sentence (F10
from F9); otherwise they go in `notes`.

**Emits.** `findings.json`: Claim nodes (no subtype) with `supports`/`opposes` edges from evidence,
and `supports` edges from finding to interpretation.

**Checker refuses.** A finding no evidence supports; evidence that argues nothing; a finding whose
anchor is a Methods sentence; a finding text that contains a statistic (that belongs in evidence).

**Gädeke reference.** F1–F15 (F10 the one interpretation). Six of them (F1, F2, F7, F8, F9, F12)
match eLife's July prototype and keep its wording.

**Known failures.** One finding per evidence node (too fine); one finding per section (too
coarse); interpretation folded into the finding. The grain rule is the panel group: Figure 3D and
3H are one finding with two evidence nodes.

---

## Stage 4 — Hypotheses from intent

**Reads.** Text (Introduction, the opening of each Results subsection, Methods aims), the findings.

**Rule.** A Hypothesis is a claim the authors set out to test, stated before the result. Its anchor
is a sentence of intent: "we hypothesized", "may evoke", "given the documented association", "search
for networks sensitive to". `text` states the bet as a proposition in the authors' terms; it may
carry the interpretation the finding leaves out (H1 says "produces interpersonal guilt"; F1 says
what happened). Each hypothesis `addresses` a Question (Stage 7); each finding either `supports` a
hypothesis or, when it tests none, `addresses` the question directly. Findings that bear on no
hypothesis are "other findings" (F3, F4, F5, F7, F13, F14), not orphans.

**Emits.** `hypotheses.json`: Claim nodes with `subtype: Hypothesis`, `supports` edges from
findings.

**Checker refuses.** A hypothesis anchored to a result sentence; a hypothesis no finding supports
(a hypothesis the paper raised and did not test is a Request, not a Hypothesis); a finding that
reaches neither a hypothesis nor a question.

**Gädeke reference.** H1–H4, with F1, F2, F6 → H1; F8, F15 → H2; F9, F11, F10 → H3; F12 → H4.

**Known failures.** Restating the finding as its own hypothesis (the question/hypothesis
redundancy caught in review); treating every Introduction sentence about prior work as a
hypothesis. The test: would the authors have called it a prediction before seeing the data?

---

## Stage 5 — Alternatives from controls

**Reads.** Text, findings, hypotheses, evidence.

**Rule.** An Alternative is a rival explanation of the same data that the paper itself raises,
builds an analysis to exclude, or concedes in the Discussion. It is written as a positive
assertion, in the voice of its proponent. It `addresses` the same question as the hypothesis it
rivals. Evidence `opposes` it only where the authors draw that inference; the `opposes` edge is
anchored to the sentence that does so (A1 ← "The 'guilt effect' occurred whether the participant
received the high lottery outcome…"). Evidence may also `support` an alternative, and must be
drawn that way when the paper says so (E10 supports A3). An alternative nothing opposes is kept and
marked open, not dropped. Two construction cases, as separate sub-prompts:

- *Rivals read off a design.* A control condition or split exists to exclude something: the
  own-outcome split (A1), the good-outcome null (A2), the Solo/Social risk measures (A3), the
  partner-reward effect against the algorithm limitation (A6).
- *Rivals read off a model comparison.* A competing model names a rival account: the Inequality
  and Guilt-envy models (A4). The likelihood-ratio evidence opposes it.

A third source, the Discussion's "we cannot exclude", yields alternatives the authors leave open or
argue against indirectly (A5, opposed only by the signature match, which the authors call
indirect).

**Emits.** `alternatives.json`: Claim nodes with `subtype: Alternative`, `addresses` edges,
`opposes`/`supports` edges from evidence with their own anchors.

**Checker refuses.** An `opposes` edge without an anchored inference sentence (the precision guard
the alternatives pass lacked); an alternative that merely negates a finding ("the effect is not
guilt") rather than asserting a rival; an alternative anchored to nothing the authors wrote.

**Gädeke reference.** A1–A6 with their opposing evidence: A1 ← E25, E26; A2 ← E27; A3 ← E6, E7, E8,
E9, E11 (E5, E10 for it); A4 ← E14, E15; A5 ← E38; A6 ← E12, E13.

**Known failures.** The third alternatives pass over the baseline found A5 but invented the
inference; the first found rivals the paper never names. Both are what the anchored-edge rule
excludes. Also: alternatives under the brain question (Q2) were not found by hand either; the
specification should ask for them and accept none.

`★ Insight` Stages 4 and 5 are the only ones with no counterpart in MIRA's extractor, and they
are the reason the graph can show elimination. They are also the stages where "the paper itself
draws the inference" does all the work: it is what separates a claim the authors argued against
from a claim we think they should have.

---

## Stage 6 — Checks, cited work, requests

**Reads.** Text, evidence, findings; the reference list from the page.

**Rule.** Three small passes with crisp definitions.

- *Check.* Mark as `subtype: Check` any Evidence whose job is to defend the method rather than
  decide a finding: manipulation checks (K1, K2, K8), positive controls (K7), assumption tests
  (K3), model selection and parameter recovery (K5, K6), convergence of measures (K4). A check
  still `supports` the finding it underwrites.
- *Cited.* For each finding the paper takes from another publication and leans on in its
  argument, emit a SourceDocument for the work (C nodes, with reference-list entry, DOI as `url`,
  and bibliography fields `authors year title journal volume pages`) and one Evidence with
  `subtype: Cited`, `sourceDocument` = that C node, `text` as this paper states the finding, and
  a `supports`/`opposes` edge to the claim it bears on. No placeholder Study. Lean-on means the
  argument uses it: the modelling method adopted (C1→E1→F4), the comparison the agency effect is
  read against (C2→E2→F5), the paradigm behind the insula hypothesis (C3→E3→H2), the external
  yardstick (C4→E4→F15). Background citations are not cited work.
- *Request.* One Request per future-work item in the Discussion, anchored, with `request_target`
  edges to the findings or alternatives it is about (R1–R6).

**Emits.** `checks.json` (ids to mark), `cited.json` (C and Cited-E nodes with edges),
`requests.json`.

**Checker refuses.** A Check that supports nothing; a Cited evidence without a resolvable DOI; a
Request with no target.

**Gädeke reference.** K1–K8; C1–C4 and E1–E4; R1–R6.

---

## Stage 7 — Questions and summaries

**Reads.** The assembled structure (Stages 1–6).

**Rule.** *Questions:* one per line of inquiry the hypotheses divide into, stated a level above
any hypothesis so that hypotheses and alternatives can both address it (Q1 behavioural, Q2
neural). Anchored to the sentence that poses the gap. Two for Gädeke; the prototype's third
(risk preferences) is a finding, not a question. *Summaries:* for every Question, Claim and
Request, one or two plain sentences a non-specialist can read alone, no numbers, no editorial
register (that goes in `notes`); for Evidence, one plain sentence without the statistic. Summaries
are written last so they describe fixed nodes, and in a separate pass so the structural stages are
not asked to write prose.

**Emits.** `questions.json`; `summaries.json` keyed by provisional id.

**Checker refuses.** A summary over two sentences, or matching the editorial pattern
(`mira_verify.py`'s `EDITORIAL`); a question no hypothesis or finding addresses; a claim that reaches
no question.

**Gädeke reference.** Q1, Q2; every `description` in the hand graph.

**Known failures.** Summaries that restate the text with the numbers removed; summaries that
editorialise ("rival to…", "weak result"); a question per hypothesis.

---

## Stage 8 — Assemble, verify, align, view

**Reads.** All stage files.

**Rule.** Assemble into the working-graph JSON: assign typed ids in creation order, attach
`figure` entries, emit `stats`, `fields`, `version`, `date`. Run the build checks (anchor
verbatim, edge grammar, panel coverage), then `mira_verify.py`; exit on any problem. Emit the
JSON-LD with the four `NodeSchema` subclasses. Align against the reference graph with
`mira_align.py`. Build the review page and, when adjudicated, the delivery page.

**Emits.** `<paper>-denovo.graph.json`, `.mira.jsonld`, `.verification.json`, `alignment.json`,
the two pages.

**Checker refuses.** Anything the verifier refuses. Alignment is reported, not gated: recall of the
reference set per stage, precision of additions, and the list of unmatched nodes on each side for
adjudication.

**Gädeke reference.** The whole graph: 97 nodes, 162 edges; verification 97/97.

---

## Running order and adjudication points

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. Stages 2 and 3 are iterated per panel group until coverage is
complete. A human adjudicates after Stage 3 (are these the findings?) and after Stage 5 (are these
the rivals, and did the paper really argue against them?); the other stages are checked by code.
On Gädeke the run is blind: the hand graph is withheld from every prompt and used only in Stage 8.

## What is paper-specific here

The two alternative-construction cases and the panel-driven evidence rule assume an experimental
paper with figures. A modelling paper (Headley) will test whether "panel" generalises to "figure or
equation" and whether rivals come from model comparison alone. That is the second run.

## Where it lives

`extract/prompts/mira/stage-N-*.md` (one specification and one prompt per stage), a runner
`scripts/mira_denovo.py <paper> [--from N]` that executes stages in order and writes each output,
and a `mira-denovo` layer in `pipeline/layers.yaml`. The existing `mira_verify.py`, `mira_align.py`
and `mira_viewer.py` close the run.
