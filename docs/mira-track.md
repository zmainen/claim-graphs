# The MIRA track — runbook

How to pick up this work without the conversation that produced it. Read this, then the
design note, then the error catalogue; everything else is a command below.

**What it is.** A programme agreed on [#77](https://github.com/zmainen/claim-graphs/issues/77)
(the reviewer's critique is the first comment there): start from MIRA's own vocabulary and the
MIRA community extractor, measure what a single call recovers of a paper, and add a stage only
where it demonstrates a benefit against that baseline. The target is a graph eLife Pathways can
show on a paper's page and a real scientist has checked. The paper so far is Gädeke et al. 2026
(eLife 105391), chosen by eLife as the easiest of their ten.

**Where things are.**

| What | Where |
|:--|:--|
| Design note (the vocabulary argument; MIRA types, roles as views) | `docs/design/2026-10-07-mira-native-vocabulary.md` (on `main`) |
| The ruling, and the reviewer's critique | claim-graphs #77 |
| Layer declaration (`mira` group, `mira-baseline`) | `pipeline/layers.yaml` |
| The extractor's prompt, verbatim, with provenance | `extract/prompts/external/mira-extraction/system_message.txt`, `user_preamble.txt`, `SOURCE.md` |
| Our prompt variant and its diff | `…/system_message.variant-1.txt`, `…/VARIANTS.md` |
| The alternatives pass prompt | `…/alternatives_pass.txt` |
| Runner (run / answer / pass / summarize) | `scripts/mira_baseline.py` |
| Scorer against the paper's eliminative structure | `scripts/mira_score.py` |
| Page-text flattener (anchors against what eLife serves) | `scripts/mira_page_text.py` |
| Report builder (the artifact, one page per run) | `scripts/mira_report.py` |
| Run outputs and the **error catalogue** | corpus `runs/<paper>/mira-baseline/` (`README.md`) |
| The hand-built graph, spec + builder, both output formats | corpus `runs/<paper>/mira-hand/` (`README.md`, `gadeke_hand.py`) |
| The Fable full-pipeline run (another session) | corpus `experiments/2026-10-16-mira-extractor-gadeke/` (#178) |
| The forked extractor with `--dump-prompt`/`--answer` | `~/Projects/mainenlab/MIRA-extraction`, branch `feat/claude-subagent-runner` |
| The readable record | private artifact https://claude.ai/artifact/PzYJYiQtBPxx5nkgK6MMen |

The corpus is `zmainen/elife-claim-trees`; the machinery (this repo) is pinned there by
`.claim-graphs-sha`. The track's machinery is on branch `design/mira-track` (PR #79), **ahead of
the pin**. Until the pin moves, run the track from a checkout of that branch and point the
corpus at it with `CLAIM_GRAPHS_ROOT`; never regenerate the corpus's committed site data
against it (CI regenerates against the pin and diffs).

## Setup

```bash
# corpus checkout (any branch), machinery checkout on design/mira-track
export CLAIM_GRAPHS_ROOT=/path/to/elife-claim-trees
cd /path/to/claim-graphs            # on design/mira-track
python3 -c "import pyshacl, yaml"   # use the conda python if the system one lacks them
secrets get OPENROUTER_API_KEY >/dev/null   # the runner reads the key from the Keychain at run time
```

## The steps, as commands

**0. The paper text.** The runner assembles the text the API runs see from
`runs/<paper>/prepared.json` (title · authors · DOI · abstract · intro · results · discussion ·
methods · captions · appendix). That is the v1 JATS. The text eLife Pathways *serves* is a
different version; anchors meant for their page must come from it:

```bash
python3 scripts/mira_page_text.py 105391 --out $CLAIM_GRAPHS_ROOT/runs/gadeke-2026-guilt-insula/mira-hand
# → <msid>v<N>-page.txt and figures.json (figure ids, IIIF image URLs, page anchors)
```

**1. Baseline: the extractor's call, as it is.**

```bash
python3 scripts/mira_baseline.py run gadeke-2026-guilt-insula --runs 3                      # pinned free model (expect timeouts)
python3 scripts/mira_baseline.py run gadeke-2026-guilt-insula --model anthropic/claude-sonnet-4.5 --tag sonnet-4.5
```
Each run writes `<tag>.run<i>.{graph.json,raw.txt,meta.json}` and refreshes `summary.json`.
The call is reproduced from the extractor's source (see the runner's docstring); the
extractor's own fold/consolidation/projection are not run. Run-to-run variance is large (49 vs
33 nodes on identical input); never compare single runs across conditions without repeats.

**2. A prompt variant.** Add a file beside the vendored prompt, describe the diff in
`VARIANTS.md`, run both arms the same way:

```bash
python3 scripts/mira_baseline.py run <paper> --model anthropic/claude-sonnet-4.5 --tag sonnet-4.5-variant1 --prompt system_message.variant-1.txt
```
A subagent can answer the dumped prompt instead (the extractor's `--answer` mode): give it the
system message and the user message as files, have it write only the JSON, then
`mira_baseline.py answer <paper> <reply.json> --tag … --model … --prompt …`. Note the route
halves the graph size: compare subagent runs only with subagent runs.

**3. A second stage over a graph.**

```bash
python3 scripts/mira_baseline.py pass <paper> <base-run-name> --prompt alternatives_pass.txt --tag sonnet-4.5-alternatives
```
The reply is a patch (new nodes `a…`/`ae…`, new edges), grammar-checked and merged onto the base;
`<tag>.run<i>.patch.json` is the diff.

**4. Score.** `python3 scripts/mira_score.py <paper>` — every graph against the alternatives the
paper raises (listed per paper in the script, from reading the paper), questions, hypothesis/
finding split, per-study evidence, straw rivals. Keyword-based; confirm by eye.

**5. The hand-built reference.** `runs/<paper>/mira-hand/<paper>_hand.py` is both the
specification (every node with statement, plain summary, study, panel, anchor; every edge) and
the builder, which refuses to emit if an anchor is not verbatim in the page text, an edge breaks
the grammar, or a panel is unaccounted for. It emits the extractor's working-graph shape (what
eLife's prototype ingests, with `subtypes`, `coverage` and `figures`) and MIRA JSON-LD with the
four `NodeSchema` subclasses (Hypothesis, Alternative, Check, Cited). Validate the JSON-LD with `scripts/validate_mira.py` (expect only
the upstream `sh:in` violations and the closed `prov:Activity` refusal of title/description on
Study nodes).

**5b. Verify and view the deliverable.** What eLife asked for (Paul Shannon, 6 Oct) is one graph
with summaries and anchors they can load into their prototype. The checklist and the review
surface:

```bash
cd $CLAIM_GRAPHS_ROOT/runs/<paper>/mira-hand
python3 <paper>_hand.py                                   # rebuild; refuses on a non-verbatim anchor
python3 <cg>/scripts/mira_verify.py <paper>-hand.graph.json <page-text>.txt     # the checklist → .verification.json; exit 1 on any problem
python3 <cg>/scripts/mira_align.py <paper>-hand.graph.json <other>.graph.json <hand-map>.json --out alignment.json   # counterpart table vs another graph of the same paper
python3 <cg>/scripts/mira_viewer.py <paper>-hand.graph.json <page-text>.txt --compare <other>.graph.json alignment.json --compare-label "July prototype" --embed-figures   # → <paper>-hand.viewer.html; --embed-figures inlines panel thumbnails (the artifact sandbox blocks eLife's image host), cached in .figcache/
```
The viewer is one self-contained page in the language of eLife Pathways' prototype
(https://elifepathways.github.io/ux-prototypes/OXA-MIRA-UX/#/article/105391): a masthead with
title, authors and DOI; a sticky list of the major sections on the left, with the view buttons
and the chip key beneath it; the article in the middle with every anchored passage underlined
and tagged by its id chip, figures inline at their placeholders; the claims on the right, side by
side with the text. Nothing switches tabs: clicking a passage opens its node on the right, and
opening a row highlights and scrolls to its passage on the left. The claims column is a tree per
question (hypotheses with their findings, other findings, alternatives), then the requests, the
studies with their protocols, and the cited works with reference entries. One row per node, the
plain summary only; a row opens in place to the full record (statement with statistic, quote,
figure thumbnail and link, edges) and to its children — evidence grouped as supported by / argued
against by / checks / from cited work, interpretations under "read as". One open node per level;
"collapse all" closes everything. Ids are typed (Q H F A E K C R S P) and each row shows its
counterpart in the compared graph (`= g3`) or `new`. Verification, Compared and JSON are folded
under "internal" in the left margin so a shared page reads as a reader's tool. Publish it as its
own artifact for review (Gädeke: https://claude.ai/artifact/2hV3hPEa8P1tgkVuzCrsHJ); the artifact
sandbox blocks eLife's image host and page-started downloads, hence `--embed-figures` and no
export link. Rules for the deliverable, agreed 26–27 Oct: summaries are one or two plain
sentences with no editorial remarks (those go in `notes`); findings keep eLife's wording where the
prototype has them; cited works are SourceDocuments with bibliography fields (`authors`, `year`,
`title`, `journal`, `volume`, `pages`, `doi`, `url`) and their findings are `Cited` evidence;
nodes may carry extra `anchors`; the extractor-shaped `.graph.json` is what goes to eLife's
prototype, the JSON-LD alongside it for Paul.

The handoff itself is the page: `mira_viewer.py ... --embed-figures --deliver --out <paper>-hand.deliver.html`
builds the one eLife receives (Gädeke: https://claude.ai/artifact/5AFpgCyeGQXKbCZzAUe1M6). It
drops the comparison and the verification table, and its Data item opens About this graph
(facts only, in four parts: what it is and who built and reviewed it; what is in it; what is new,
the four subclasses one line each; the checks; the two files), the cleaned working-graph JSON
(written beside it as `.deliver.graph.json`, no `key`, with a `fields` block naming the extra
fields) and the MIRA JSON-LD, read from `<paper>-hand.mira.jsonld`. One self-contained file, no
server, no outside requests: `--embed-figures` inlines every figure in the graph's `figures`
table (not only those on evidence nodes; the artifact frame blocks eLife's image host) and
copies them to `fig/` beside the page as a fallback. Do not publish `fig/` with the artifact:
sidecar files make the export a zip instead of one HTML file, and the embedded images suffice.
Version the graph: the builder sets `version` and `date` on the JSON (and the JSON-LD stamps);
the page shows them in the masthead and the About page. Every change that reaches the delivered
page is its own version (major.minor.patch: schema or subclasses / nodes or edges / wording,
summaries, anchors or the page), committed on its own, recorded in the run's `CHANGELOG.md`, and
tagged `<paper>-mira-v<version>` on the corpus (`gadeke-mira-v1.0.0`, 2026-10-28, is what eLife
received). Bump, rebuild, verify, republish, commit, tag: in that order. Keep the JSON: it is the
form the Pathways prototype loads; the JSON-LD is for MIRA. Every chip shows its node's full
statement on hover; edge lines in a drawer are chip triples only.

**6. The record.** `python3 scripts/mira_report.py <paper>` writes
`runs/<paper>/mira-report/site/` (not committed); publish `index.html` as the artifact page and
the other files as its files. Every count and quote on the pages comes from the run files.

**7. The local site.** The `mira-baseline` layer page renders the baseline README. To see it,
regenerate the site data against this branch and **do not commit the result**:
`PYTHONPATH=<cg>/extract:<cg>/scripts CLAIM_GRAPHS=<cg> python3 scripts/corpus_facts.py` in the
corpus, then `cd site && CLAIM_GRAPHS=<cg> npm run dev`.

## What the runs established (details in the error catalogue)

No single-call extraction — pinned free model (never completed), Sonnet, Fable through the full
pipeline, or Sonnet with variant-1 — produced a rival the paper eliminates or an `opposes` edge
aimed at one. The prompt's definition of a Claim as "an assertion the authors make" excludes
them. Variant-1's structural rules took (Study per analysis, Evidence per study, one Question
per hypothesis); its argument rules did not. The alternatives pass raises `opposes` to 1–5 and
finds the Discussion's open alternative reliably, a Results-based elimination occasionally, and
the design- and model-comparison-based alternatives never. One early judgement was reversed: the
guilt-signature match *is* used by the paper against the emotion-labelling alternatives.

## Decisions taken (eLife call, 16 Oct 2026; Zach, 16 Oct)

Pure MIRA output; our old format deprecated. Every node carries `text` (statement),
`description` (plain summary) and a verbatim `anchor`; Evidence is per study and per figure
panel, with the figure's image and page anchor; Studies are the two experiments (not the
analyses); `Hypothesis` and `Alternative` are subclasses of Claim and `Check` of Evidence,
declared as `NodeSchema`; cited works the argument leans on are included with their own study
and finding; anchors are against the version eLife Pathways serves (v2), not the v1 JATS.
Discourse Graphs already names Hypothesis ("untested claim"), InterpretedAs (= MIRA's
`observationStatement`) and Issue (= Request); our `stance` is what it calls a belief predicate,
deliberately left out of its base spec. Alternative has no name upstream; that is the proposal.

## What is left

1. Zach's adjudication of the hand-built graph (open judgement calls are listed in its README).
2. Hand-off to eLife: share the delivery page (one file carrying the reading surface, the
   cleaned JSON for Lina's prototype and the JSON-LD for Paul); ask whether their loader can
   take JSON-LD directly, in which case the JSON can go.
3. The alternatives pass: a precision guard (an `opposes` edge requires that the paper itself
   draws the inference, anchored) and sub-steps for the two construction cases (rivals read
   off a design; rivals read off a model comparison).
4. Scoring every run against the adjudicated reference, by meaning (not keywords).
5. A second, unlike paper (Headley, a modelling paper) through the same steps.
6. The local site: a page for the hand-built graph; later, the site consuming MIRA directly.
7. This paper's public reviews attached to the graph (eLife: Daniel Ecer, Hazal Ciplak).
8. The #77 ruling: an attributed belief predicate, with Hypothesis and Alternative resolved from
   it, as the proposal to MIRA; then move the pin.
