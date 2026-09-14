"""The canon's closed vocabularies, as data — the one place they are declared.

This module holds what `scripts/relations.py` and `extract/claim_graphs/vocabulary.py` used to
declare inline: the relation vocabulary (supports, opposes, gaps; descriptions, directions,
corpus examples, confusable pairs; the finer opposition cuts and the stance set) and the claim
vocabulary (questions, roles, claim types, confidence, the reconciler's three-way test). The two
modules are now thin views over this data (they re-export every name), so a concept is declared
once and the four scripts that read a relation and the prompts that render a role read the same
bytes. `canon/entries.py` wraps each of these with the definition, distinctions and enforcement
the design notes carried, and `canon --check` holds the two in step.

Pure data, no imports beyond `annotations`, so it can be loaded by path from a script module
(relations.py) and imported as a package (canon) without either pulling the other in.
"""

from __future__ import annotations

# A relation that asserts the target is strengthened by the source.
_SUPPORTS = {
    "supports": "the source provides evidence for the target",
    "tests": "an empirical result tests the target prediction, closing the loop",
    "validates": "a control whose specific result strengthens the target's warrant",
    "confirms": "an empirical result confirms the prediction it tested — the positive outcome of a test",
    "predicts": "the source predicts the target, typically model to experiment",
    "extends": "the source extends the target beyond its original conditions",
    "replicates": "an independent finding of the same result as the target",
}

# A relation that asserts the target is weakened, eliminated, or separated from something.
#
# `in-tension-with` sits here as the mild opposition the #125 ruling named when it split the
# old `dissociates-with`: two claims the paper asserts, both of which stand, that pull a shared
# implication in opposite directions. It exports under `mira:opposes`, but it is kept out of
# CONTRARY — a result may support a hypothesis and be in tension with another result — so the
# support-plus-oppose rule leaves it alone. The neutral contrast it was split from,
# `dissociates-with`, moved to GAPS: it opposes nothing and belongs under no MIRA predicate.
_OPPOSES = {
    "contradicts": "the source and target cannot both hold",
    "opposes": "the source stands against the target",
    "refutes": "an empirical result refutes the prediction it tested — the negative outcome of a test",
    "rules-out": "the source's evidence eliminates the target as an explanation",
    "in-tension-with": "two claims the paper asserts, both of which stand, that pull a shared "
                       "implication in opposite directions or cannot be jointly explained "
                       "without a further claim (symmetric)",
}

# A relation with no supporting or opposing sense, and — for the MIRA export — no predicate at
# all. These are what a conversion to a support/oppose vocabulary costs.
GAPS = {
    "entails": "a hypothesis entails its prediction — the deductive step",
    "derived-from": "a prediction derived from its hypothesis (inverse of entails)",
    "interprets": "one claim interprets another",
    "enables-method": "a result makes a downstream method possible",
    "scopes": "a scope constraint governs another claim's validity",
    "requires": "a claim depends on another holding",
    "qualifies": "a claim narrows another's applicability",
    "dissociates-with": "the source and target jointly establish a dissociation — two claims "
                        "whose difference across a condition, region, population or measure is "
                        "itself the finding, neither bearing on the other's truth (symmetric)",
    "part-of": "a component of another claim — one comparison, condition, measure or study "
               "of a proposition the target states whole; the target is weakened but not "
               "falsified by the source alone",
}

# SUPPORTS and OPPOSES are sets and GAPS is a description map, which is the shape the four
# call sites already used. The descriptions for all three live in DESCRIPTIONS, so nothing has
# to choose between knowing what a relation means and being able to test membership.
SUPPORTS = set(_SUPPORTS)
OPPOSES = set(_OPPOSES)
EDGE_KEYS = SUPPORTS | OPPOSES | set(GAPS)

DESCRIPTIONS = {**_SUPPORTS, **_OPPOSES, **GAPS}

# Which way an edge points, as a sentence about its two ends. A relation name says that two
# claims are related and not which is which, and the prompt that asks a model for edges gave it
# only the name — so `tests` came back from prediction to result as often as from result to
# prediction. The direction lives here, beside the definition, so the prompt contract and the
# checker read one rule.
DIRECTION = {
    "supports": "from the evidence to the claim it is evidence for",
    "tests": "from the empirical result to the prediction it tests",
    "validates": "from the control to the claim whose warrant it strengthens",
    "confirms": "from the result to the prediction it confirms — the positive outcome of a test, aimed at a prediction only",
    "predicts": "from the model or hypothesis to the observation it predicts",
    "extends": "from the later or broader result to the claim it extends",
    "replicates": "from the independent finding to the claim it reproduces",
    "contradicts": "from either claim to the other; they cannot both hold",
    "opposes": "from the claim that stands against to the one it stands against",
    "refutes": "from the result to the prediction it came out against — the negative outcome of a test, aimed at a prediction only",
    "rules-out": "from the control or evidence to the alternative explanation it eliminates — a claim "
                 "the paper entertains or rejects, never one it asserts",
    "dissociates-with": "symmetric: between the two empirical claims that together establish the contrast",
    "in-tension-with": "symmetric: between two claims the paper asserts whose implications pull against each other",
    "entails": "from the hypothesis to the prediction it deductively implies",
    "derived-from": "from the prediction back to its hypothesis; written mechanically as the reciprocal of entails",
    "interprets": "from the interpretation to the empirical claim it reframes",
    "enables-method": "from the methodological claim to the result whose interpretability it warrants",
    "scopes": "from the scope claim to the claims it bounds, or to `*` for every empirical claim in the paper",
    "requires": "from the dependent claim to its prerequisite: the source would be invalid if the target were false",
    "qualifies": "from the qualifying result to the claim whose applicability it narrows",
    "part-of": "from the component to the claim it is a part of: the source states one "
               "comparison, condition, measure or study of what the target states as a whole",
}

# One edge from the corpus per relation, as (paper, source slug, target slug). The prompt
# contract quotes both claims, so an example that names a slug the corpus no longer has fails
# generation rather than quietly describing an edge that does not exist. Relations with no use
# in the corpus have no example, and the contract says so.
EXAMPLE = {
    "supports": ("headley-2026-inhibitory-rhythms", "distal-inhib-drops-firing-02hz",
                 "hypothesis-distinct-compartmental-roles"),
    "requires": ("headley-2026-inhibitory-rhythms", "distal-inhib-drops-firing-02hz",
                 "l5-model-single-cell-scope"),
    "entails": ("headley-2026-inhibitory-rhythms", "hypothesis-distinct-compartmental-roles",
                "prediction-distal-dendritic-spike-mechanism"),
    "derived-from": ("headley-2026-inhibitory-rhythms", "prediction-distal-dendritic-spike-mechanism",
                     "hypothesis-distinct-compartmental-roles"),
    "tests": ("headley-2026-inhibitory-rhythms", "distal-inhib-drops-firing-02hz",
              "prediction-distal-dendritic-spike-mechanism"),
    "refutes": ("meijer-2025-serotonin-additive-r1", "5ht-stim-leaves-decision-behavior-intact",
                "prediction-5ht-shifts-psychometric"),
    # Gädeke's claim-tree v2 renamed the claim that carries this eliminative edge; the alt- node
    # is the one carried across from v1. `qualifies` left the corpus with the v1 tree — no claim
    # of any paper uses it now — so it has no example, which the contract renders as such.
    "rules-out": ("gadeke-2026-guilt-insula", "participant-happiness-lower-when-participant",
                  "alt-agency-aversion-not-guilt"),
    "dissociates-with": ("headley-2026-inhibitory-rhythms", "distal-inhib-drops-firing-02hz",
                         "perisomatic-inhib-drops-firing-07hz"),
    # The Gädeke tension (#125): the neural guilt response matches the published Yu/Koban
    # signature at the group level, yet individual signature scores do not track individual
    # behavioural guilt. Both stand; the replication is real and the null bounds what it means.
    "in-tension-with": ("gadeke-2026-guilt-insula", "dot-products-between-individual-neural",
                        "individual-grbs-dot-product-values-not"),
    "validates": ("meijer-2025-serotonin-orthogonal", "wt-controls-rule-out-light-artifact",
                  "5ht-stim-dilates-pupil"),
    "predicts": ("meijer-2025-serotonin-orthogonal", "hypothesis-state-switch-by-5ht",
                 "5ht-stim-dilates-pupil"),
    "confirms": ("meijer-2025-serotonin-orthogonal", "5ht-axis-orthogonal-to-choice-axis",
                 "prediction-5ht-axis-orthogonal-to-choice"),
    "interprets": ("headley-2026-inhibitory-rhythms", "pv-gamma-sst-beta-correspondence",
                   "beta-optimal-distal-dendritic-entrainment"),
    "enables-method": ("kammer-2026-foveal-feedback", "preregistered-design-validates-mvpa",
                       "foveal-v1-decodes-peripheral-saccade-target"),
    "scopes": ("headley-2026-inhibitory-rhythms", "l5-model-single-cell-scope", "*"),
    "extends": ("kammer-2026-foveal-feedback", "v2-v3-generalize-shape-not-category",
                "decoding-shape-sensitive-not-semantic"),
    # The low-minus-high difference is one measure of the insula ROI guilt result, which states
    # the same contrast "even after subtracting responses to high outcomes". Retrofitted onto
    # Gädeke's claim-tree v2 by the `parts` layer (#75).
    "part-of": ("gadeke-2026-guilt-insula", "difference-response-between-low-high",
                "insula-rois-responded-more-low"),
}

# The pairs a reader most often confuses, each with what separates them. The contract renders
# these after the definitions, because a definition read alone is easy to agree with and hard
# to apply at the boundary.
CONFUSABLE = [
    ("requires", "supports",
     "`requires` is a dependency: if the target were false the source would be invalid. "
     "`supports` is evidence: the source makes the target more credible and would survive its "
     "falsity. One empirical claim commonly carries both — it *requires* the scope claim that "
     "bounds the model it was computed in, and *supports* the hypothesis it was run to test."),
    ("entails", "tests",
     "Both connect a hypothesis's arc, in opposite directions and from different roles. "
     "`entails` runs *down* from the hypothesis to a prediction and is deductive: the prediction "
     "follows if the hypothesis holds. `tests` runs *up* from an empirical result to the "
     "prediction it checks. A result never `entails` anything; a hypothesis never `tests`."),
    ("rules-out", "refutes",
     "`rules-out` eliminates an alternative explanation — a claim the paper raises in order to "
     "reject, which has a node of its own with stance `entertains` or `rejects`. `refutes` is "
     "the negative outcome of a test, aimed at one of the paper's own predictions that the "
     "evidence came out against; a paper refuting its own prediction is the hypothetico-deductive "
     "loop closing. When a result bears against a hypothesis, do not aim `refutes` at the "
     "hypothesis — write the prediction the hypothesis entails and refute that. Never aim "
     "`rules-out` at a claim the same paper asserts."),
    ("confirms", "supports",
     "`confirms` is the outcome of a stated prediction: an empirical result came out the way the "
     "prediction said it would, and the edge runs from the result to that prediction — its "
     "negative counterpart is `refutes`. `supports` is evidence for a hypothesis or higher-order "
     "claim, making it more credible without being the settling of a prediction. A result that "
     "tests a prediction carries `tests` and then `confirms` or `refutes` it; the same result may "
     "`supports` the hypothesis that prediction was derived from. Aim `confirms` and `refutes` at "
     "predictions only — a result that bears on a hypothesis directly takes `supports`."),
    ("dissociates-with", "contradicts",
     "`dissociates-with` joins two results that are both true and *differ*: the contrast between "
     "them is the finding, and neither undermines the other. `contradicts` says two claims cannot "
     "both hold. Two conditions producing different effects is a dissociation, not a "
     "contradiction. A dissociation is also not a tension: a contrast is marked by “whereas”, "
     "“in contrast”, “selectively”, and the two results simply differ; a tension (`in-tension-with`) "
     "is marked by “although”, “however”, “despite”, “no correlation with”, “at the cost of”, and "
     "the two results pull a shared implication in opposite directions."),
    ("in-tension-with", "contradicts",
     "`contradicts` says two claims cannot both hold. A tension says both do: the paper asserts "
     "each, and they stand together while pulling a shared implication in opposite directions."),
    ("in-tension-with", "qualifies",
     "`qualifies` is directional — one result narrows the applicability of another. A tension has "
     "no narrower side: neither claim bounds the other, they simply pull against each other. The "
     "wengert case (a general impairment, and a layer that mostly escapes it) is arguably a "
     "qualification, and the reading is left to the reader rather than fixed by rule."),
    ("in-tension-with", "rules-out",
     "`rules-out` eliminates an alternative the paper raised in order to reject — a claim with "
     "stance `entertains` or `rejects`. A tension is between two claims the paper *asserts*, both "
     "of which stand; nothing is being eliminated."),
    ("scopes", "requires",
     "A scope claim bounds what a result can mean and is written from the scope claim *to* the "
     "results it bounds (or to `*`). `requires` is written from the result *to* what it depends "
     "on. The same pair of claims can carry both, in opposite directions: the result requires "
     "the scope; the scope scopes the result."),
    ("validates", "supports",
     "`validates` is a control's edge: a check whose specific outcome (a null where a confound "
     "would have produced an effect, a sign-flip, a manipulation check) strengthens the warrant "
     "for a target. `supports` is ordinary evidence for a proposition. A control `validates`; a "
     "main result `supports`."),
    ("part-of", "supports",
     "`part-of` is composition: the source is one comparison, condition, measure or study *of* "
     "the proposition the target states whole, and dropping it weakens the target without "
     "falsifying it. `supports` is evidence: an independent finding that makes the target more "
     "credible and would survive being removed. The insula-ROI result stated beside the "
     "voxel-wise result is a *part of* the claim that the insula tracks the guilt effect; a "
     "distinct finding that happens to bear on that claim merely *supports* it. A filter on "
     "`supports` cannot tell a component from an independent finding, which is why composition "
     "needs its own relation."),
]

# A finer cut of OPPOSES, for the one check that needs it: which relations may not be aimed at
# a claim the same paper asserts.
#
# `rules-out`, `contradicts` and `opposes` assert the target is false, so aiming one at a claim
# the paper holds is an error under any reading — the thing actually being eliminated has no
# node, and the edge found the nearest claim that does.
#
# `refutes` is not in that group, and the distinction is the substance rather than a detail.
# Under the #28 ruling `refutes` is an outcome aimed at a prediction only: a paper refuting its
# own prediction is the hypothetico-deductive loop closing, not opposing a claim it asserts, so
# it stays out of CONTRARY. A `refutes` (or `confirms`) that lands on a hypothesis is the
# shortcut the ruling retires — the fix is to write the prediction the hypothesis entails and
# aim the outcome there — and `check_relations.py` flags it as "outcome aimed at a hypothesis"
# rather than this set doing so. Grouping `refutes` with `rules-out` reported the loop-closing
# cases as errors.
#
# `in-tension-with` and `dissociates-with` are both excluded, which the #125 ruling settles:
# a tension holds between two claims the paper *asserts*, so it could never target a claim it
# does not; and a dissociation is a neutral contrast that eliminates nothing. Neither is a move
# that says the target is false, so neither belongs here.
CONTRARY = {"contradicts", "opposes", "rules-out"}
REFUTES_OWN = {"refutes"}

# The outcome relations: how a test came out, aimed at a prediction only (issue #28). `confirms`
# is the positive outcome, `refutes` the negative; `tests` is the neutral edge whose verdict
# they record. Declared here so the checker and the prediction-outcome layer read one set.
OUTCOME = {"confirms", "refutes"}
NEUTRAL_TEST = {"tests"}

# What a paper may do with a proposition, per docs/claim-format.md § 2.
STANCES = {"asserts", "entertains", "rejects", "attributes"}

# ── The claim vocabulary (roles, types, confidence) ──────────────────────

# ── Questions ────────────────────────────────────────────────────────────
# A question is not a claim — a claim is a declarative sentence — so it lives on the paper, not
# in the claim graph. It is what the paper set out to answer, and the paper states it, in the
# abstract or in the Introduction. Each hypothesis and each rejected alternative addresses one:
# the hypothesis is the answer the paper commits to, the alternatives are the answers it turns
# down. A question is never a hypothesis with a question mark: do not manufacture one by
# hollowing a hypothesis into "X involves neural mechanisms" — return the question the paper
# actually asked, or none.

QUESTIONS = (
    "A **question** is what the paper set out to answer. It is not a claim — a claim is a "
    "declarative sentence — so it is recorded on the paper rather than as a node in the graph. "
    "The paper states it, in the abstract or in the opening of the Introduction. Each "
    "`hypothesis` and each rejected alternative addresses one: the hypothesis is the answer the "
    "paper commits to, and the alternatives it rules out are the other answers to the same "
    "question. Never turn a question into a hollow hypothesis such as \"X involves neural "
    "mechanisms\" — return the question the paper actually asked, or return none."
)

# ── Roles ────────────────────────────────────────────────────────────────
# The rhetorical function a claim serves in the paper's argument. Nine values; the corpus uses
# all nine. `example` is (paper, slug). `signals` are phrases in the prose that mark the role.

ROLES = [
    {
        "role": "hypothesis",
        "definition": "An answer the paper commits to, to a question it states: the proposition "
                      "it bets on, phrased as a claim about the world rather than as the "
                      "question. It carries no empirical content of its own; it is what the "
                      "predictions are deduced from and what the results are gathered for, and "
                      "the alternatives the paper rules out are the other answers to the same "
                      "question. Each hypothesis carries `addresses`, the question it answers. "
                      "Most papers have one to three.",
        "typical_claim_type": "hypothesis",
        "signals": ["we hypothesize", "we propose that", "we asked whether", "we sought to test",
                    "the central question is whether"],
        "carries": "`entails` to each of its predictions; usually `panel: null`",
        "example": ("headley-2026-inhibitory-rhythms", "hypothesis-distinct-compartmental-roles"),
    },
    {
        "role": "prediction",
        "definition": "What should be observed if the hypothesis holds, under stated conditions. "
                      "A prediction is deduced, not measured: it is anchored in the model or in "
                      "principled reasoning, and an empirical claim then tests it. Write it as a "
                      "conditional when the paper does not.",
        "typical_claim_type": "prediction",
        "signals": ["if X, then we should observe Y", "this predicts that", "the model predicts",
                    "should be maximally effective at", "is predicted to"],
        "carries": "`derived-from` back to its hypothesis (written mechanically); is the target of `tests`",
        "example": ("headley-2026-inhibitory-rhythms", "prediction-beta-optimal-distal"),
    },
    {
        "role": "empirical",
        "definition": "A measured or computed result, anchored to the panel that shows it, "
                      "carrying the paper's own numbers and the paper's own epistemic verb. The "
                      "largest role.",
        "typical_claim_type": "empirical",
        "signals": ["we found that", "we observed", "we measured", "increased", "did not differ"],
        "carries": "`tests` to the prediction it checks; `supports` and `requires` as the argument needs",
        "example": ("headley-2026-inhibitory-rhythms", "distal-inhib-drops-firing-02hz"),
    },
    {
        "role": "control",
        "definition": "An empirical result whose work in the argument is to eliminate an "
                      "alternative explanation or to show a manipulation did what it should. "
                      "Its content is a measurement; what makes it a control is what it rules "
                      "out. A null result is usually a control.",
        "typical_claim_type": "empirical",
        "signals": ["rules out", "excludes", "is not due to", "no significant effect of",
                    "control condition", "manipulation check", "regardless of"],
        "carries": "`rules-out` to the alternative it eliminates; `validates` to the claim it defends",
        "example": ("gadeke-2026-guilt-insula", "risk-premiums-not-differ-between"),
    },
    {
        "role": "scope",
        "definition": "A boundary condition on what the results can mean: the model class, the "
                      "preparation, the population, the design. Often global. It asserts nothing "
                      "about the world; it says where the paper's assertions apply.",
        "typical_claim_type": "assessment",
        "signals": ["all results come from", "restricted to", "in this preparation",
                    "was not a physiological pattern", "N = "],
        "carries": "`scopes` to the claims it bounds, or `scopes: [\"*\"]`",
        "example": ("headley-2026-inhibitory-rhythms", "l5-model-single-cell-scope"),
    },
    {
        "role": "methodological",
        "definition": "A capability or analytical commitment that a downstream result depends on "
                      "for its interpretation: the sorting pipeline, the null distribution, the "
                      "model fit that licenses a model-based analysis. Not procedure for its own "
                      "sake — which software ran the task is not a claim unless a result turns on "
                      "it. A localizer — a contrast run only to define a region or a set "
                      "of trials for a later analysis — is `methodological`, not "
                      "`empirical`, because the paper does not argue from it.",
        "typical_claim_type": "assessment",
        "signals": ["analysis is on", "nulls are", "fit better than", "validated against"],
        "carries": "`enables-method` to the results it warrants",
        "example": ("kammer-2026-foveal-feedback", "preregistered-design-validates-mvpa"),
    },
    {
        "role": "synthesis",
        "definition": "A higher-order proposition that integrates several of the paper's own "
                      "results into one claim, staying inside the paper's evidence: the "
                      "dissociation, the reconciliation, the summary that several panels jointly "
                      "establish.",
        "typical_claim_type": "synthesis",
        "signals": ["taken together", "these results show", "this dissociation establishes",
                    "in summary"],
        "carries": "is the target of `supports` from the results it integrates",
        "example": ("meijer-2025-serotonin-additive-r1", "orthogonality-derived-from-additivity"),
    },
    {
        "role": "interpretation",
        "definition": "A reading of the results through a theoretical lens from outside the "
                      "paper's own evidence: a mapping onto a framework, a proposed mechanism, a "
                      "functional meaning. It is an act of mapping, not a derivation.",
        "typical_claim_type": "interpretive",
        "signals": ["may provide a functional interpretation", "suggests a role for",
                    "points to a mechanism whereby", "is consistent with the view that"],
        "carries": "`interprets` to the empirical claims it reframes",
        "example": ("headley-2026-inhibitory-rhythms", "pv-gamma-sst-beta-correspondence"),
    },
    {
        "role": "literature-context",
        "definition": "A finding from cited prior work that the paper's argument inherits as a "
                      "premise, recorded as a claim of its own so the inheritance is auditable. "
                      "The citation may be implicit: prose that paraphrases a prior empirical "
                      "pattern as background is literature-context whether or not it names the "
                      "paper.",
        "typical_claim_type": "interpretive",
        "signals": ["as shown by", "previous work has established", "the reported association of",
                    "(Author, Year) found"],
        "carries": "is the target of `requires` or `interprets` from the claims that lean on it",
        "example": ("headley-2026-inhibitory-rhythms", "interprets-pv-gamma-sst-beta-associations"),
    },
]

# Pairs a reader most often confuses, with what separates them and two claims that sit either
# side of the line. Each example is (paper, slug).
ROLE_CONFUSABLE = [
    ("hypothesis", "prediction",
     "A hypothesis says what is the case; a prediction says what will be observed if it is. "
     "\"Compartments serve distinct roles\" is the bet; \"if so, doubling distal inhibition "
     "should suppress dendritic spikes more than doubling perisomatic inhibition\" is what it "
     "commits the paper to seeing. Surface both, and keep them apart: adding predictions never "
     "reduces the number of hypotheses.",
     ("headley-2026-inhibitory-rhythms", "hypothesis-distinct-compartmental-roles"),
     ("headley-2026-inhibitory-rhythms", "prediction-distal-dendritic-spike-mechanism")),
    ("control", "empirical",
     "Both are measurements. Ask what the result is *for*: if it demonstrates the effect the "
     "paper is about, it is empirical; if it shows that something else does not explain that "
     "effect, or that the manipulation worked, it is a control.",
     ("gadeke-2026-guilt-insula", "risk-premiums-not-differ-between"),
     ("gadeke-2026-guilt-insula", "when-partner-received-low-lottery")),
    ("synthesis", "interpretation",
     "Synthesis stays inside the paper's own evidence and says what several results jointly "
     "establish. Interpretation reaches outside it, to a framework, a mechanism or a literature, "
     "and says what the results mean there.",
     ("meijer-2025-serotonin-additive-r1", "orthogonality-derived-from-additivity"),
     ("headley-2026-inhibitory-rhythms", "pv-gamma-sst-beta-correspondence")),
    ("scope", "methodological",
     "Scope bounds where the results apply and usually qualifies every empirical claim at once. "
     "A methodological claim is a specific capability that specific results depend on for their "
     "meaning. \"All results come from a single-cell model\" is scope; \"the preregistered plan "
     "fixed the decoding pipeline, the ROIs and the tests in advance\" is methodological, "
     "because the decoding results count as confirmatory only if it did.",
     ("headley-2026-inhibitory-rhythms", "l5-model-single-cell-scope"),
     ("kammer-2026-foveal-feedback", "preregistered-design-validates-mvpa")),
    ("literature-context", "interpretation",
     "Literature-context restates what a cited paper found; it is someone else's result, "
     "inherited. Interpretation is this paper's reading of its own results, even when that "
     "reading leans on the literature. The inherited premise and the reading that uses it are "
     "two claims.",
     ("headley-2026-inhibitory-rhythms", "interprets-pv-gamma-sst-beta-associations"),
     ("headley-2026-inhibitory-rhythms", "pv-gamma-sst-beta-correspondence")),
]

# ── What is not a claim ──────────────────────────────────────────────────
# The `methodological` definition drew the line — procedure is a claim only when a result turns
# on it — but the recorded Opus structure reader returned procedure anyway, because the line had
# no examples (docs/design/2026-09-11-parts.md). `WARRANTS` are the positive side: procedure a
# result does turn on, quoted through `_quote` so each resolves to a real methodological claim.
# `NOT_CLAIMS` are the negative side: sentences the reader returned (the six from Gädeke's v3
# structure output, plus one from the earlier DeepSeek run) that no result turns on, each with
# the one thing it merely records.
WARRANTS = [
    ("kammer-2026-foveal-feedback", "preregistered-design-validates-mvpa"),
    ("gadeke-2026-guilt-insula", "model-based-glm-entered-best-fitting-computational"),
    ("gadeke-2026-guilt-insula", "momentary-happiness-modelled-five-computational"),
    ("gadeke-2026-guilt-insula", "parameter-recovery-procedure-synthetic-data-generated"),
]

NOT_CLAIMS = [
    ("Happiness ratings were Z-scored per participant to remove the influence of differing "
     "rating variability across participants.",
     "a normalisation — no result reads differently for it"),
    ("Risk attitude was quantified as a risk premium — the EVdiff value yielding 50% risky "
     "choices from a fitted logistic regression — and compared between Solo and Social "
     "conditions with paired t-tests in both studies.",
     "a definition of a measure — the finding is that the premium did not differ, not that it "
     "was defined this way"),
    ("Two gPPI seed-to-voxel connectivity analyses used functionally defined seeds: the left "
     "insula cluster more sensitive to Risky versus Safe outcomes (GLM3) and the left STS "
     "cluster responding more to social_pRPE than partner_pRPE (GLM4), with identical seeds "
     "across participants.",
     "a seed choice — the connectivity result is the claim, not which seeds produced it"),
    ("All reported clusters survive a whole-brain family-wise-error-corrected threshold of "
     "p < 0.05 with a cluster-forming voxel-wise threshold of p < 0.001 (or a smaller volume "
     "where explicitly mentioned).",
     "a threshold applied to every result alike — a scope condition folded into the paper's "
     "scope claim, not a finding"),
    ("The fMRI data of four Study 2 participants were excluded from the fMRI analysis for "
     "excessive head motion (>3 mm or >3°).",
     "an exclusion count — a component of the paper's scope claim, not a claim of its own"),
    ("The Study 2 sample size of 44 was fixed a priori by a G*Power analysis based on Study 1's "
     "effect size (Cohen's d = 0.56), with alpha = 0.05 and power = 0.95.",
     "a power analysis fixing the sample — a component of the paper's scope claim"),
    ("The experiment was implemented in MATLAB using Psychtoolbox.",
     "a software choice — no result would mean anything different in another toolbox"),
]

# ── Claim types ──────────────────────────────────────────────────────────
# The epistemic character of the proposition, independent of the role it plays. Seven values:
# the five in docs/claim-format.md and the two the corpus uses for its deductive layer, which
# method.md § 4.2 names as the typical type of those roles and 77 claim files carry.

CLAIM_TYPES = [
    ("empirical", "a directly observed or computed result"),
    ("interpretive", "an inference drawn from one or more empirical claims"),
    ("existence", "an assertion that a phenomenon, entity or resource exists"),
    ("synthesis", "a claim integrating results across several analyses or papers"),
    ("assessment", "a methodological, scope or quality claim about how the work was done"),
    ("hypothesis", "a proposition bet on, not yet evidenced by this paper's results"),
    ("prediction", "a deduced expectation, to be tested by an empirical claim"),
]

# `confidence` on an assertion and `readers` are different fields and are constantly read as
# one. `confidence` is this paper's own confidence in the proposition — analyst judgement, and
# the writer leaves it absent rather than guessing. `readers` is agreement at extraction, which
# is a fact about the readers and not about the world; that is the vocabulary below.

ASSERTION_CONFIDENCE_NOTE = (
    "`confidence` on an assertion is this paper's own confidence in the proposition — analyst "
    "judgement, which the writer leaves absent rather than inventing. It is not `readers`, the "
    "agreement between extraction readers recorded beside it."
)

# ── Confidence, after reconciliation ─────────────────────────────────────
# A fact about agreement between the readers, not about the world. The partition means most
# claims are visible to at most two readers, so "all three" is not the bar for `high`.

CONFIDENCE = [
    ("high", "more than one reader surfaced the same proposition and they agree on its panel "
             "and its direction"),
    ("contested", "more than one reader surfaced it and they disagree — about the panel, the "
                  "direction, or whether it is a hypothesis, a prediction or a result. Record "
                  "what each said in `notes`"),
    ("single-source", "one reader surfaced it. Expected for panel-level numerics (caption reader "
                      "only), scope and methodological claims (structure reader only) and "
                      "synthesis (results reader only); not a mark against the claim"),
]

# What a reader may say about its own claim, before reconciliation.
READER_CONFIDENCE = [
    ("high", "asserted directly in the text the reader was given, with a quotable sentence"),
    ("tentative", "read between the lines, summarised across sentences, or ambiguous in the "
                  "source; say why in `notes`"),
]

# ── Same, part, or different ─────────────────────────────────────────────
# The reconciler's three-way test, shown on real pairs. Each triple is two candidate sentences
# and the verdict, with one line of why. All are drawn from the Gädeke pairs the recorded Opus
# run wrongly kept apart (docs/design/2026-09-11-parts.md); the sentences are quoted literally
# from the claim files, so a triple is an example of what the reconciler actually receives.
# `contract.py` renders these; they are strings, not slugs, because the reconciler compares
# sentences, not files.
SAME_CLAIM = [
    ("same",
     "In both studies, participants felt worse after low lottery outcomes for the partner when "
     "those outcomes followed their own choice rather than the partner's, which the authors "
     "interpret as interpersonal guilt.",
     "When the partner received the low lottery outcome, participant happiness was lower when "
     "the participant rather than the partner had chosen the lottery — a significant "
     "partner-outcome × decision-maker interaction (Study 1: t(1180) = 3.52, p = 0.0004, "
     "β = 0.37; Study 2: t(937) = 2.85, p = 0.0045, β = 0.33) — operationalizing interpersonal "
     "guilt.",
     "The same partner-outcome × decision-maker interaction on the same happiness data, cited "
     "once as a cross-study synthesis and once as the result that computes it: merge, keep the "
     "wording with the coefficients."),
    ("part",
     "One cluster in the left STS responded more to partner reward prediction errors resulting "
     "from participant rather than partner choices (pFWE = 0.022, T = 4.70, d = 0.53, "
     "100 voxels, peak MNI [−52 –32 0]).",
     "The left superior temporal sulcus cluster responded to model-based regressors coding "
     "participant reward prediction resulting from participant and partner choices across both "
     "sessions of the experiment.",
     "The first states one directional contrast — participant-caused above partner-caused — of "
     "the broader responsiveness the second states as a whole: keep both, the first `part_of` "
     "the second."),
    ("different",
     "During receipt of lottery versus safe outcomes (across all conditions), clusters were "
     "more active in the bilateral anterior insula, dmPFC, right STS, bilateral ventral "
     "striatum, right dorsolateral prefrontal cortex, and bilateral inferior parietal lobe.",
     "The bilateral ventral striatum was more active when participants chose the risky rather "
     "than the safe option (Cohen's d = 0.72 left, 0.85 right), irrespective of Social or Solo "
     "condition, replicating previous findings.",
     "Both light up the ventral striatum, but by different computations — one the "
     "lottery-versus-safe outcome-receipt contrast, the other the risky-versus-safe choice "
     "contrast: keep both, no relation between them here."),
]
