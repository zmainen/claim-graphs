---
name: claim-structures
description: "Work with claim structures — typed propositions joined by typed logical relations (hypothesis entails prediction, empirical result tests it, control rules out an alternative, scope bounds it). Use when analyzing a paper into claims, speccing or outlining a paper around its argument, designing an experiment around what it has to rule out, auditing an argument for gaps, or authoring and editing claim files in a claim-graph corpus."
---

{{generated-note}}

A claim structure is a scientific argument written as data: one declarative proposition per
node, one typed logical relation per edge. It is the same object whether you are reading a
finished paper, planning one, or designing the experiment that will fill it — what changes is
which end you start from.

This skill and the `claim-graphs` machinery are one thing. The vocabulary below is rendered
from the same declarations the pipeline sends to a model, and the sequence in
[workflows/analyze-paper.md](workflows/analyze-paper.md) is rendered from the same layer graph
`pipeline.py run` walks. **Prefer running a layer to reproducing one.** Where a step has a
runner, the runner hands you the exact prompt the backend would have received; answering that
is how an agent and an API produce the same tree.

## What a claim is

A claim is an **entity**, not a result and not a figure. `dat-reuptake-dominates` is a
proposition about the world that several papers might assert, that a reproduction might test,
and that other claims might depend on. A *document* asserts a claim, in a particular panel,
with a particular analysis, on particular data — that pairing is an **assertion**, and it is a
property of the document, not of the claim. The same proposition can be asserted by one paper
and rejected by another; both assertions hang off the one claim, and the disagreement becomes
visible.

Relations between claims are **not citations**. `A requires B` says A would be invalid if B were
false. That is why the structure is worth building: invalidity propagates along the edges, so a
claim that fails is not an isolated correction but a traceable one.

## The minimal claim

```yaml
---
uuid: 26819b09-5b20-4c90-b9f3-8bdd29a2a57c   # uuid4, generated once, never changes
slug: distal-inhib-drops-firing-02hz          # 3-6 words, lowercase, verb phrase
claim: >
  Doubling the strength of distal dendritic inhibition reduces somatic firing rate from
  approximately 5.5 Hz to approximately 0.2 Hz, primarily by suppressing dendritic Ca²⁺ and
  NMDA spikes rather than by directly raising AP threshold.
claim-type: empirical        # what kind of proposition it is
role: empirical              # what work it does in the argument
epistemic: strong            # support strength — see references/vocabulary.md
concepts: [distal dendritic inhibition, somatic firing rate, dendritic spike suppression]

tests: [prediction-distal-dendritic-spike-mechanism]
requires: [l5-model-single-cell-scope]
in-tension-with: [perisomatic-inhib-drops-firing-07hz]

assertions:
  - paper-slug: headley-2026-inhibitory-rhythms
    doi: 10.7554/eLife.95562
    panel: fig4, fig5
    analysis: scripts/Fig4.ipynb
    dataset-doi: 10.5061/dryad.v6wwpzhb8
    method: compartmental modelling — inhibition magnitude sweep
    confidence: strong
    stance: asserts
---

Prose body: caveats, boundary conditions, why this edge and not that one.
```

Full vocabulary — every role, claim type and relation, with a real example of each:
[references/vocabulary.md](references/vocabulary.md). Relation directions and the pairs people
confuse: [references/relations.md](references/relations.md).

## The two axes

`claim-type` is the **epistemic character** of the proposition. `role` is the **rhetorical
function** it serves in this argument.

{{claim-types}}

{{roles}}

They are orthogonal, and the distinction is load-bearing. A `claim-type: empirical` proposition
is `role: empirical` when it is a finding, `role: control` when its job is to kill a rival, and
`role: scope` when its job is to bound what the others mean. The same measurement does
different work in different arguments.

### Stance

A document does not only assert. Stance is a property of the assertion, not of the claim:

{{stances}}

Stance says what the document concluded; the edges say why. Keep both — a paper can dismiss a
rival with no evidence at all, and conversely the `rules-out` edge names which control did the
work, which stance cannot.

### Epistemic

{{epistemic}}

## The spine

```
question
  ├── hypothesis  (the answer the work commits to)
  │     └─ entails → prediction ←─ tests ── empirical result
  │                                              ├─ requires → scope, methodological
  │                                              └─ supports → synthesis → interpretation
  └── alternative (a rival answer, stance: entertains)
        ←─ rules-out ── control
```

Every workflow below walks this spine. Analysis walks it upward from the panels; a paper spec
walks it downward from the question; an experimental design walks it sideways, from the rivals
that have to be eliminated to the measurements that eliminate them.

## Pick the workflow

| You are… | Read | Has a runner |
|:---------|:-----|:-------------|
| turning a published or drafted paper into claims | [workflows/analyze-paper.md](workflows/analyze-paper.md) | yes — the layers below |
| speccing or restructuring a paper you are writing | [workflows/spec-paper.md](workflows/spec-paper.md) | not yet |
| designing an experiment or study before data exists | [workflows/design-experiment.md](workflows/design-experiment.md) | not yet |
| checking a structure someone else built | [references/checks.md](references/checks.md) | yes — `make check` |
| handing a structure to a person to read | [references/presentation.md](references/presentation.md) | no |

## Invariants

These hold in all three workflows, and are the defects found most often in real claim graphs.
The ones a gate already rejects are in [references/checks.md](references/checks.md); do not
carry those in your head, run the checker.

1. **One sentence, one claim.** A proposition needing two sentences is two claims. Two results
   joined by "and" are two claims — or one whole with two `part-of` components, if neither
   states the proposition on its own.
2. **Quantitative where the result is.** Put the numbers in the claim sentence, taken verbatim
   from the source. Never compute, round, or infer a value that the source does not state —
   a plausible fabricated number is the failure mode a reader cannot catch.
3. **The alternative needs a node.** A control exists to eliminate a rival, so the rival must
   exist as a claim for `rules-out` to reach. A control whose edges name only the claim it
   defends has not recorded the point of the control.
4. **Direction is part of the relation.** `entails` runs down from hypothesis to prediction;
   `tests` runs up from result to prediction. They are neither interchangeable nor reciprocal.
5. **Scope before results.** Write what the work does *not* establish — the model's boundary,
   the population, the stimulation regime — as scope claims, and point them at what they bound.
   Written afterwards, they become a discussion paragraph nobody traverses.
6. **The graph is the argument.** Read the edges alone, with the claim sentences, and see
   whether the argument reconstructs. If it does not, the edges are wrong — not the reader.
7. **The structure is not the artifact.** When the deliverable is for a person, overlay the
   claims onto their document — anchored to the spans they came from, in plain wording, with the
   gaps shown — rather than pasting claim files into it.
8. **Do not fabricate identifiers.** Generate UUIDs (`python3 -c "import uuid; print(uuid.uuid4())"`).
   Take panel ids from the source's own figure elements. Leave `doi: ~` unless the DOI is real.

## Using the machinery

```bash
python3 scripts/pipeline.py run <paper> claim-tree --dry-run   # what producing a graph would do
python3 scripts/check_relations.py --rules                     # what the gate enforces
make check                                                     # the gate CI enforces
```

`docs/claim-format.md` is the normative authoring format, `pipeline/layers.yaml` the processing
graph, `docs/method.md` the method including verification, `docs/extending.md` how to add a
layer when a workflow here has no runner.

A corpus is a separate checkout: point `CLAIM_GRAPHS_CORPUS_DIR` at one. No human has verified
any claim in the seed corpus — treat existing files as a draft annotation layer to imitate
structurally, not as adjudicated content.

### Starting a graph for a paper of your own

The machinery holds no papers. A graph is a directory you make, and three things are needed
before any layer will run — the second is the one that is easy to miss, because without it
every command answers `no paper '<slug>'`, which is true and unhelpful:

1. `claims/<slug>/index.md` with front matter carrying `doi:` — a DOI, or any reference a
   source resolves, a local path included.
2. `corpus.yaml` at the graph root, listing the slug under `corpora.<name>.papers`.
3. `CLAIM_GRAPHS_ROOT` at the graph, `CLAIM_GRAPHS_CORPUS_DIR` at its `claims/`, and the
   machinery's `extract/` and `scripts/` on `PYTHONPATH`.

### What a `doi:` may point at

| reference | path taken |
|:--|:--|
| an eLife DOI | JATS from the publisher's CDN |
| a local `.xml` / `.nxml` | JATS, read as structure |
| `.md`, `.docx`, `.tex`, `.html`, `.odt`, `.rst` | converted to JATS by pandoc, then read as structure |
| a local `.pdf` | flat text, sliced by pattern |

The distinction that matters is not the file extension but which of two branches the document
reaches. JATS is read as structure: sections by their titles, captions bound to figure ids,
tables with their rows. Everything else is flat text sliced by regex, which finds results and
methods and loses the rest. Anything pandoc reads therefore arrives structured; only PDF does
not, because pandoc cannot read PDF.

**Markdown with YAML front matter is the best non-JATS input**, because it is the one where
the title and abstract survive. Give it `title:` and `abstract:` in the front matter — an
`# Abstract` heading becomes an ordinary section, and the abstract slice then comes back empty
with no error to tell you. Word keeps the title and loses the abstract; HTML and LaTeX arrive
with neither. Body sections come through from all of them.

Converting needs `pandoc` installed. If it is missing, the refusal says so by name.
