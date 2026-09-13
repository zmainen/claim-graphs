# Scope: one envelope or many bounds, and why the corpus writes both

**Status:** proposed
**Issue:** [#37](https://github.com/zmainen/claim-graphs/issues/37)
**Frames:** [#17](https://github.com/zmainen/claim-graphs/issues/17)
**Depends on:** `scripts/relations.py`, `extract/claim_graphs/evaluate.py`, `scripts/check_relations.py`, `docs/claim-format.md`, five papers' scope claims

A scope claim says where a result stops: the preparation, the population, the model class, the
stimulation regime. The relation that carries it, `scopes`, runs from the bounding claim to what
it bounds, and the vocabulary offers two forms — name the targets, or write `["*"]` for every
empirical claim in the paper. This note argues that the corpus uses one of those forms to say
both things, that the two things are different, and that no consumer can currently tell them
apart.

It was found by measuring rather than by reading. Edge recovery on `wengert-2026-kcnc1` scored
`scopes` at **0 of 17** — the worst of any relation, and the only one at zero with a substantial
denominator — on a tree whose scope claims are perfectly reasonable.

## What the corpus does

Across thirteen papers, `scopes` carries **168 edges to named targets and 3 to `["*"]`**. Two
papers use `"*"` at all. This is not a vocabulary nobody knows about: `"*"` is the documented
form in `relations.py`, and the worked example rendered into every prompt contract is
`headley-2026-inhibitory-rhythms / l5-model-single-cell-scope → *`.

Where a paper has a dominant scope claim, what it covers — as a fraction of the claims a scope
can bound, meaning roles `empirical`, `control`, `synthesis` and `interpretation`:

| paper | hub scope claim | targets | eligible | coverage |
|:--|:--|--:|--:|--:|
| kolb-2026-igabasnfr2 | `scope-sensor-engineering-paper` | 14 | 11 | **127%** |
| rozak-2026-neurovascular-dl | `scope-pipeline-and-application-paper` | 14 | 13 | **108%** |
| scheller-2026-self-prioritization | `scope-toj-tva-paradigm` | 14 | 13 | **108%** |
| artiushin-2026-spider-atlas | `atlas-observational-scope` | 15 | 14 | **107%** |
| wengert-2026-kcnc1 | `scope-a421v-knockin-mouse` | 18 | 17 | **106%** |
| meijer-2025-serotonin-orthogonal | `seven-target-trajectories-13-regions` | 5 | 13 | 38% |
| bouyeure-2026-fear-rsa | `lss-unreinforced-trials-only` | 6 | 19 | 32% |
| meijer-2025-serotonin-additive-r1 | `seven-target-trajectories-13-regions` | 7 | 23 | 30% |

Coverage exceeds 100% where the hub also bounds the methodological and scope claims rather than
only the results.

The distribution is bimodal, and nothing in between. Five papers scope ~everything; three scope
under 40%. That is not a spectrum of judgement calls, it is two different propositions.

## The two propositions

**A global envelope.** "Everything this paper establishes holds only for the heterozygous
knock-in on this background, at these ages." It bounds the work. Five papers assert it by
enumerating every eligible claim, which is `["*"]` written out by hand.

**A selective bound.** "These particular results come from unreinforced trials only." It bounds
part of the work, and the claims it does not name are deliberately outside it. Three papers
assert this, and naming targets is the right and only way to say it.

Rendered as YAML they are indistinguishable: a list of slugs. The difference is recoverable only
by counting the list against the paper, which no consumer does.

## What that costs

**It makes the scope metric meaningless.** On `wengert-2026-kcnc1` the curated tree bounds the
paper from one claim with 18 outgoing edges; the induced tree bounds each result locally from
four narrower claims with 15 edges between them. Both say the work is bounded, and the recovery
score is zero, because the test is pairwise and the shapes differ. The reference's top three
sources carry 33% of all its edges; the chain's carry 9%. A pairwise metric punishes a hub
against a mesh even when they assert the same thing.

**It rots.** An enumeration is a snapshot of the claims that existed when it was written. Add a
claim and the envelope silently stops covering the paper — no check fires, because a shorter
list is legal. `kolb-2026-igabasnfr2` already carries 27 scope edges against 21 claims.

**It hides the interesting case.** A paper where the envelope genuinely does *not* cover
everything — where some result escapes the stated limitation — is exactly what a reader wants to
find, and today it is indistinguishable from an envelope whose author stopped typing.

## Proposal

1. A scope claim that bounds the whole paper carries `scopes: ["*"]`.
2. A scope claim that bounds a subset names its targets.
3. `["*"]` and a complete enumeration are **the same assertion**. Every consumer — the exporters,
   `evaluate`'s edge scorer, the site — expands `"*"` to the eligible set rather than treating it
   as one edge to a literal. This is what makes a `"*"` tree and an enumerated tree compare equal,
   and it is the half that fixes the 0/17.
4. `check_relations.py` warns when an enumeration covers every eligible claim: it is almost
   certainly `"*"`, and it will rot.

## What it does not settle

Whether a tree should carry *both* an envelope and local bounds — the knock-in line bounding
everything, and the two-photon preparation bounding only the imaging results — is left open. The
proposal permits it: `"*"` from one claim, named targets from another. Nothing yet says whether
a local bound under a global envelope is redundant or informative, and the corpus has no example
to reason from, because no paper currently carries both.

## Cost of the change

Rewriting five papers' hub claims to `["*"]` changes roughly 75 edges. Every tree downstream goes
stale, every export regenerates, and the five papers' `scopes` counts drop by an order of
magnitude — which will look like a regression on any figure that counts edges, and is not one.
The alternative is to keep two encodings of one proposition, and a scope measurement that cannot
mean anything.
