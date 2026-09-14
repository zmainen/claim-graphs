"""The canon's concept entries: every concept the system has, declared once.

`vocab.py` holds the closed vocabularies as data — the relation names, the roles, the stance
and confidence sets. This module wraps each concept the design notes carried — claim, assertion,
result, question, module, finding cluster, scope, observation, loose, warrant, the checks, the
four kinds of decision, the adjudication procedure — with the fields the canon note names:

    definition     one paragraph, the thing itself
    signals        what a reader uses to recognise it in a paper
    distinct_from  pairs, with the sentence that tells them apart
    enforced_by    the rule/validator/layer/procedure that holds it, or `not enforced`
    operations     where it has them (fold/combine on a cluster, propagation on warrant)
    example        a pointer into the toy study, at the stage the concept first arises
    references     the design note that argued for it, and a corpus instance; rendered when present
    status         accepted or proposed, derived from the declaration that governs it
    glossary       the surface forms a term-scan resolves to this entry

Relation and role entries are generated from `vocab.py` so a relation added there becomes a
canon entry with no second edit; the hand-authored enrichment below supplies their toy example,
enforcement and glossary. `entries()` returns the merged registry, ordered.

`example.ref` resolves into `canon/toy-study/`: a claim slug, an edge `src -rel-> tgt`, or an
artifact path. `canon --check` holds every field present (or `not enforced`), every declared
vocabulary term owning an entry, and every ref resolving.
"""

from __future__ import annotations

from . import vocab

# Declarations the corpus records as accepted in runs/approvals.jsonl (the canon note's list).
# A concept's status is `accepted` when the declaration that governs it is here, else `proposed`.
ACCEPTED_DECLARATIONS = {
    "claim-format", "relation-vocab", "prediction-outcome", "parts", "questions", "procedure",
}

NOTE = {  # design notes, by short key
    "canon": "docs/design/2026-09-14-the-canon.md",
    "modules": "docs/design/2026-09-14-modules.md",
    "decision": "docs/design/2026-09-12-kinds-of-decision.md",
    "warrant": "docs/design/2026-09-13-warrant.md",
    "tension": "docs/design/2026-09-13-contrast-and-tension.md",
    "parts": "docs/design/2026-09-11-parts.md",
    "stance": "docs/design/2026-09-10-stance-and-alternative-claims.md",
    "verification-check": "docs/design/2026-09-13-verification-check.md",
    "scope": "docs/design/2026-09-14-scope-representation.md",
}


def ex(stage, ref):
    return {"stage": stage, "ref": ref}


# ── the singular concepts ──────────────────────────────────────────────────
# Each keyed by its concept id. Relation and role entries are added programmatically below.

SINGLETONS: dict[str, dict] = {
    "claim": dict(
        governed_by="claim-format",
        definition="A proposition that exists independently of any paper — one declarative "
                   "sentence in active voice, quantitative where the result is, carrying the "
                   "paper's own epistemic verb. It has a claim type (what kind of proposition it "
                   "is), a role (the work it does in an argument), and typed relations to other "
                   "claims. Papers do not contain claims; they make assertions about them.",
        signals=["a declarative sentence a reader could agree or disagree with",
                 "states one thing, not a procedure or a question"],
        distinct_from=[
            ("assertion", "A claim is the proposition; an assertion is one paper committing to "
                          "it, with a stance, a panel and a confidence. Two papers asserting the "
                          "same proposition share one claim and carry two assertions."),
            ("question", "A question is what a paper set out to answer and is not a declarative "
                         "sentence, so it is recorded on the paper, not as a claim."),
        ],
        enforced_by="extract/claim_graphs/schema.py (the shape a reader returns); the frontmatter "
                    "parser and check_relations' unparseable-frontmatter rule",
        operations=None,
        example=ex("induced: the written-up study read into claim files",
                   "hyp-polish-raises-shine"),
        references={"note": NOTE["stance"], "corpus": "gadeke-2026-guilt-insula"},
        glossary=["claim", "claims"],
    ),
    "assertion": dict(
        governed_by="claim-format",
        definition="One paper's commitment to a claim, at a moment in time: a block carrying the "
                   "paper slug, the stance the paper takes, the panel or locator that grounds it, "
                   "and the paper's own confidence. Stance and confidence are facts about the "
                   "assertion, not about the claim, which is why the same claim can carry opposing "
                   "assertions from two papers.",
        signals=["\"the authors report\"", "\"we found\"", "a claim tied to one paper's panel"],
        distinct_from=[
            ("claim", "The claim is paper-independent; the assertion is the situation of one paper "
                      "relating to it. `confidence` lives on the assertion; the proposition does "
                      "not."),
            ("readers", "An assertion's `confidence` is the paper's own posture; `readers` is "
                        "agreement between extraction readers, a fact about extraction."),
        ],
        enforced_by="schema/to_claim_set.py (assertions_of); check_relations (attributes needs a "
                    "source)",
        operations=None,
        example=ex("induced: every toy claim carries a `toy-widgets` assertion with a panel",
                   "finding-polished-shinier"),
        references={"note": NOTE["stance"]},
        glossary=["assertion", "assertions"],
    ),
    "result": dict(
        governed_by="modules",
        definition="An analysis result that bears on a finding: a claim file in the format, with "
                   "its own span and panel, that hangs beneath the finding it belongs to rather "
                   "than standing on the paper. Coverage and verification need results as atoms; "
                   "nothing that shows or exports a module may call them claims on the paper.",
        signals=["a number, comparison or sub-analysis that the finding above it reports as one "
                 "thing", "carries a panel and often a reproduction record"],
        distinct_from=[
            ("finding cluster", "A result is a member beneath the finding; the cluster is the "
                                "finding together with its results, and the cluster is the unit "
                                "reported and folded."),
            ("claim", "Every result is a claim file, but within a module it is a detail of its "
                      "finding, not a claim on the paper's argument."),
        ],
        enforced_by="scripts/modules.py (finding grain: results attach to a finding by a detail "
                    "edge)",
        operations=None,
        example=ex("derived: the analysis produces results that fold under the finding",
                   "result-shine-delta -part-of-> finding-polished-shinier"),
        references={"note": NOTE["modules"]},
        glossary=["result", "results"],
    ),
    "claim-type": dict(
        governed_by="claim-format",
        definition="The epistemic character of a proposition, independent of the role it plays: "
                   "`empirical` (a directly observed or computed result), `interpretive` (an "
                   "inference drawn from empirical claims), `existence` (a phenomenon, entity or "
                   "resource exists), `synthesis` (integrating results across analyses or "
                   "papers), `assessment` (a methodological, scope or quality claim), and the two "
                   "the deductive layer uses, `hypothesis` and `prediction`. Type and role are "
                   "independent axes: a measurement can play the role of a result, a control or a "
                   "scope condition.",
        signals=["what kind of proposition it is, asked apart from its function"],
        distinct_from=[
            ("role", "Type is what kind of proposition a claim is; role is the work it does in an "
                     "argument. The same empirical type can be a result, a control or a scope "
                     "claim."),
        ],
        enforced_by="extract/claim_graphs/vocabulary.py (CLAIM_TYPES); schema/to_claim_set.py "
                    "and the JSON schema's closed `type` set",
        operations=None,
        example=ex("induced: every toy claim carries a claim type", "finding-polished-shinier"),
        references={"note": NOTE["canon"]},
        glossary=["claim-type", "empirical", "interpretive", "existence", "synthesis",
                  "assessment", "hypothesis", "prediction"],
    ),
    "question": dict(
        governed_by="questions",
        definition="What a paper set out to answer. It is not a claim — a claim is a declarative "
                   "sentence — so it is recorded on the paper, in the abstract or the opening of "
                   "the Introduction. Each hypothesis and each rejected alternative addresses one: "
                   "the hypothesis is the answer the paper commits to, the alternatives the "
                   "answers it turns down.",
        signals=["\"we asked whether\"", "\"the central question is whether\"",
                 "an interrogative in the abstract"],
        distinct_from=[
            ("role:hypothesis", "A question is interrogative and lives on the paper; a hypothesis "
                                "is the declarative answer to it and is a claim. Never hollow a "
                                "hypothesis into a question with a question mark."),
            ("module", "A module is one question under test together with the claims that answer "
                       "it; the question is what seeds the module."),
        ],
        enforced_by="the `questions` layer; scripts/modules.py seeds a module per question",
        operations=None,
        example=ex("composed: the study opens with the question the design commits to",
                   "toy-study/design.yaml"),
        references={"note": NOTE["modules"], "corpus": "gadeke-2026-guilt-insula"},
        glossary=["question", "questions"],
    ),
    "stance": dict(
        governed_by="stance",
        definition="What a paper does with a proposition, recorded on the assertion: `asserts` "
                   "(claims it true, the default), `entertains` (raises it as a candidate, does "
                   "not assert it), `rejects` (argues it false), `attributes` (someone else "
                   "asserts it and this paper reports that; requires a source). A ruled-out "
                   "alternative is a claim with stance `entertains` or `rejects` and an incoming "
                   "`rules-out` edge.",
        signals=["\"we can rule out that\"", "\"one possibility is\"", "\"contrary to X\"",
                 "\"as (Author) showed\""],
        distinct_from=[
            ("relation:rules-out", "Stance is the paper's conclusion about a proposition; the "
                                   "`rules-out` edge is the warrant — which evidence did the "
                                   "rejecting. A paper can reject by dismissal, with stance and "
                                   "no edge."),
            ("warrant", "Stance is a posture the paper takes; warrant is how well the argument "
                        "supports the claim, read from the tree."),
        ],
        enforced_by="check_relations (unknown-stance; attributes-without-source; an opposing edge "
                    "may not target an asserted claim)",
        operations=None,
        example=ex("induced: the rival is a claim with stance `rejects`",
                   "alt-handling-raises-shine"),
        references={"note": NOTE["stance"], "corpus": "gadeke-2026-guilt-insula"},
        glossary=["stance", "asserts", "entertains", "rejects", "attributes"],
    ),
    "confidence": dict(
        governed_by="claim-format",
        definition="A paper's own confidence in a proposition, recorded on the assertion as "
                   "analyst judgement and left absent rather than invented. After reconciliation "
                   "a separate `readers` grade records agreement between extraction readers "
                   "(`high`, `contested`, `single-source`). The two are constantly confused and "
                   "are different fields: one is about the world's paper, the other about the "
                   "reading.",
        signals=["the paper's hedging verbs (\"suggests\", \"demonstrates\")"],
        distinct_from=[
            ("readers", "`confidence` is the paper's posture toward the proposition; `readers` is "
                        "how many extraction readers surfaced it and whether they agreed."),
            ("warrant", "Confidence is what the paper says; warrant is what its argument earns. A "
                        "confident sentence earns no warrant its argument does not."),
        ],
        enforced_by="extract/claim_graphs/vocabulary.py (the vocabularies contract.py renders)",
        operations=None,
        example=ex("induced: toy assertions carry a `readers` grade, not an invented confidence",
                   "result-shine-delta"),
        references={"note": NOTE["warrant"]},
        glossary=["confidence"],
    ),
    "readers": dict(
        governed_by="claim-format",
        definition="Agreement between extraction readers, recorded after reconciliation: `high` "
                   "(more than one reader surfaced it and they agree on panel and direction), "
                   "`contested` (they disagree), `single-source` (one reader surfaced it, "
                   "expected for panel numerics, scope and synthesis). It is a fact about the "
                   "reading, not about the world, and is not the paper's `confidence`.",
        signals=["set at reconciliation, not read from the prose"],
        distinct_from=[
            ("confidence", "`readers` is agreement between readers; `confidence` is the paper's "
                           "own posture. `single-source` is not a mark against a claim."),
        ],
        enforced_by="the `reconcile` layer; extract/claim_graphs/vocabulary.py (CONFIDENCE)",
        operations=None,
        example=ex("induced: toy assertions carry `readers: high`", "finding-polished-shinier"),
        references={"note": NOTE["canon"]},
        glossary=["readers"],
    ),
    "module": dict(
        governed_by="modules",
        definition="One question under test: the question, the hypothesis the paper commits to, "
                   "the alternatives it raises to reject, the predictions the hypothesis entails, "
                   "the findings that test them or bear on the hypothesis, and the interpretation "
                   "drawn. That is the argument grain — a handful of nodes a reader holds in mind. "
                   "A module carries a warrant (its hypothesis's) and a summary. It is derived "
                   "mechanically from the edges.",
        signals=["the paragraph a reader would give as \"what this paper argues\"",
                 "one question and its answer, above the atoms"],
        distinct_from=[
            ("finding cluster", "A module is the argument grain (question, hypothesis, findings); "
                                "a finding cluster is one finding with its results, the finding "
                                "grain beneath. The cluster is what a paper lists; the module is "
                                "not."),
            ("observation", "A question module answers a declared question; an observation module "
                            "is a finding that answers none."),
        ],
        enforced_by="scripts/modules.py (the six-step derivation); scripts/test_modules.py",
        operations="derived from the edges: seed from questions, argument grain breadth-first, "
                   "finding grain to a fixed point, scope, observations, loose",
        example=ex("induced: the derivation groups the atoms into one question module",
                   "toy-study/composed.yaml"),
        references={"note": NOTE["modules"], "corpus": "gadeke-2026-guilt-insula"},
        glossary=["module", "modules"],
    ),
    "finding-cluster": dict(
        governed_by="modules",
        definition="A finding together with the results that bear on it — the unit of a paper's "
                   "reporting and the finding grain of a module. Across versions the cluster is "
                   "the unit of identity (a result that appears or vanishes is a change inside "
                   "the finding, not a new claim on the paper); for strength it is the unit of "
                   "warrant (the finding's level is a function of its results).",
        signals=["a finding a paper reports as one thing, with its numbers beneath it"],
        distinct_from=[
            ("result", "The cluster is the finding plus its results; a result is one member "
                       "beneath it."),
            ("module", "A finding cluster is one node of a module's finding grain; a module holds "
                       "many at its argument grain."),
        ],
        enforced_by="scripts/modules.py (the cluster and its `combine` record)",
        operations="fold — align findings and compare results beneath them across versions; "
                   "combine — compute the finding's warrant from its results (validated_by, "
                   "supported_by, parts, qualified_by, in_tension_with)",
        example=ex("derived: the finding and its two results are one cluster with a combine record",
                   "finding-polished-shinier"),
        references={"note": NOTE["modules"]},
        glossary=["finding", "findings", "finding cluster", "fold", "combine", "cluster"],
    ),
    "scope-domain": dict(
        governed_by="modules",
        definition="One half of a module's scope: what the claims apply to — the sample, the "
                   "task, the design — drawn from the scope claims the members are scoped by. It "
                   "is the ground of the argument, not a member of it, and the module shows it as "
                   "one line that opens. A scope claim stays a claim, adjudicable and cited to a "
                   "span.",
        signals=["\"all results come from\"", "\"restricted to\"", "\"N =\""],
        distinct_from=[
            ("scope-apparatus", "The domain is what the claims apply to (population, task); the "
                                "apparatus is what they rest on (models, localizers, the GLM)."),
            ("role:scope", "The role `scope` is a claim's function; a module's domain is the set "
                           "of scope claims that bound its members — the two meanings #37 found "
                           "written identically."),
        ],
        enforced_by="scripts/modules.py (step 4: `scopes` edges set the module's domain)",
        operations=None,
        example=ex("induced: the brass-only scope claim is the module's domain",
                   "scope-brass-widgets"),
        references={"note": NOTE["modules"], "corpus": "headley-2026-inhibitory-rhythms"},
        glossary=["domain", "scope"],
    ),
    "scope-apparatus": dict(
        governed_by="modules",
        definition="The other half of a module's scope: what the claims rest on — the models, the "
                   "model selection, the GLM, the localizer — drawn from what the members require "
                   "or are enabled-method by. Like the domain it is the ground of the argument, "
                   "shown as one line that opens, not a member of it.",
        signals=["a calibration, a fitted model, a localizer a result depends on"],
        distinct_from=[
            ("scope-domain", "The apparatus is what the claims rest on; the domain is what they "
                             "apply to."),
            ("role:methodological", "A methodological claim is the apparatus claim's role; the "
                                    "apparatus is the set of such claims a module's members "
                                    "require."),
        ],
        enforced_by="scripts/modules.py (step 4: `requires`/`enables-method` set the apparatus)",
        operations=None,
        example=ex("induced: the calibrated shine meter is the module's apparatus",
                   "apparatus-shine-meter"),
        references={"note": NOTE["modules"]},
        glossary=["apparatus"],
    ),
    "observation": dict(
        governed_by="modules",
        definition="A finding that answers no declared question — a result no hypothesis "
                   "predicted, a model that fitted best. It is a module of the second kind, with "
                   "its own details, and it is what a later paper makes a hypothesis of. A paper "
                   "that is mostly observations is telling you something true about it.",
        signals=["\"we also observed\"", "an incidental result outside the paper's questions"],
        distinct_from=[
            ("module", "An observation module answers no declared question; a question module "
                       "answers one. There is no third kind: apparatus is scope, and anything "
                       "else is a missing edge."),
            ("loose", "An observation is a whole finding placed as its own module; a loose claim "
                      "is one the derivation could not place at all."),
        ],
        enforced_by="scripts/modules.py (step 5: a whole with no argument edge opens an "
                    "observation)",
        operations=None,
        example=ex("induced: heavier widgets being duller answers no question, so opens an "
                   "observation module", "obs-heavier-widgets-duller"),
        references={"note": NOTE["modules"]},
        glossary=["observation", "observations"],
    ),
    "loose": dict(
        governed_by="modules",
        definition="A claim the derivation could not place in any module. Loose is a lint, not a "
                   "category: it names a missing edge, and the layer lists each loose claim with "
                   "what it would take to place it. A paper with nothing loose is one whose "
                   "argument the graph fully holds.",
        signals=["a claim with no argument edge into any placed node"],
        distinct_from=[
            ("observation", "A loose claim is unplaced; an observation is a whole finding placed "
                            "as its own module."),
        ],
        enforced_by="scripts/modules.py (step 6); check_relations echoes the loose list as "
                    "warnings",
        operations=None,
        example=ex("asserted-about: the review flags the dangling synthesis as loose with its "
                   "reason", "loose-synth-widgets-improvable"),
        references={"note": NOTE["modules"]},
        glossary=["loose"],
    ),
    "warrant": dict(
        governed_by="warrant",
        definition="What the tree's argument gives a reader grounds to believe, read from the "
                   "structure the paper reports — predictions and their outcomes, controls, "
                   "rivals ruled out or standing, support and interpretation — as distinct from "
                   "what the paper says (`confidence`) and how many readers agreed (`readers`). "
                   "Four graded levels — `strong`, `moderate`, `weak`, `contested` — plus the "
                   "prediction and alternative vocabularies. It reads the argument alone; checking "
                   "is a separate layer.",
        signals=["computed, not read from the prose", "cites the argument edges that fired"],
        distinct_from=[
            ("confidence", "Warrant is what the argument earns; confidence is what the paper "
                           "asserts. A hedged sentence loses no warrant its argument gives it."),
            ("verification-check", "Warrant states what the paper's argument implies; a check "
                                   "states whether that argument survives a re-run, and writes "
                                   "beside the warrant rather than into it."),
        ],
        enforced_by="scripts/warrant.py (the rule, kept for scoring); scripts/test_warrant.py",
        operations="propagation — a claim's warrant is bounded above by the weakest same-role-"
                   "group claim it requires",
        example=ex("asserted-about: the review reads the finding's warrant as strong",
                   "finding-polished-shinier"),
        references={"note": NOTE["warrant"], "corpus": "gadeke-2026-guilt-insula"},
        glossary=["warrant", "strong", "moderate", "weak", "contested", "ruled-out", "open",
                  "confirmed", "refuted", "untested"],
    ),
    "verification-check": dict(
        governed_by="verification-check",
        definition="The first checking layer: does a re-run stand behind each claim, read beside "
                   "its warrant. For each claim it reads the reproduction records and the "
                   "verification provenance and returns one of six verdicts — `reproduced`, "
                   "`partial`, `mismatch`, `blocked`, `unattempted`, `unrecorded` — by precedence "
                   "over that evidence. It writes its own field and never touches `warrant`.",
        signals=["a reproduction record on a claim", "a provenance run that measured a value"],
        distinct_from=[
            ("warrant", "The check reads what happened when someone re-ran the result; warrant "
                        "reads the paper's own argument. `contested` from a failed reproduction is "
                        "the check's word, not warrant's."),
        ],
        enforced_by="extract/claim_graphs/verification_check.py (verdict precedence)",
        operations=None,
        example=ex("derived: the shine-delta result carries a reproduction record the check reads",
                   "result-shine-delta"),
        references={"note": NOTE["verification-check"]},
        glossary=["verification-check", "reproduced", "mismatch", "blocked", "unattempted",
                  "unrecorded", "partial"],
    ),
    "decision:code": dict(
        governed_by="procedure",
        definition="One of the four kinds of decision: does the mechanism do what its declaration "
                   "says? Decided by tests and gates and a reviewer of the diff; recorded as a PR; "
                   "mechanical, changing no meaning. The ledger marks runs stale where inputs "
                   "moved.",
        signals=["a pull request", "a failing or passing gate"],
        distinct_from=[
            ("decision:scheme", "Code asks whether the mechanism matches its declaration; scheme "
                                "asks what the declaration should mean."),
            ("decision:run", "Code is a decision; a run is not."),
        ],
        enforced_by="tests and `make check`; the ledger's staleness computation",
        operations=None,
        example=ex("this PR is itself a code decision — the fixture tests and canon --check gate "
                   "it", "toy-study/review/verdict.json"),
        references={"note": NOTE["decision"]},
        glossary=["kind:code"],
    ),
    "decision:scheme": dict(
        governed_by="procedure",
        definition="One of the four kinds of decision: what does this mean, for every paper? "
                   "Decided by a person, once; recorded as a design note, the declaration with "
                   "`status: accepted`, and an entry in `runs/approvals.jsonl` naming the "
                   "declaration's version. Its effect is propagation — every run under the old "
                   "scheme is stale. A canon entry is ruled on this way.",
        signals=["a scheme issue phrased as a question (\"Is X an opposition?\")",
                 "a declaration's `status` and version"],
        distinct_from=[
            ("decision:adjudication", "A scheme ruling settles a meaning for every paper; an "
                                      "adjudication settles one version of one layer's output for "
                                      "one paper."),
            ("decision:code", "Scheme decides meaning; code decides whether the mechanism matches "
                              "the meaning."),
        ],
        enforced_by="scripts/pipeline.py (approve --declaration; declaration_version); the canon "
                    "version on the ledger",
        operations=None,
        example=ex("asserted-about: accepting a canon entry is a scheme ruling recorded in "
                   "approvals", "toy-study/review/verdict.json"),
        references={"note": NOTE["decision"]},
        glossary=["kind:scheme", "scheme"],
    ),
    "decision:adjudication": dict(
        governed_by="procedure",
        definition="One of the four kinds of decision: is this version of this layer's output "
                   "right, for this paper? Decided by a person, per version, in four steps "
                   "(prepare a verdict skeleton, read a verdict per claim and edge, approve the "
                   "version, apply the verdicts to the next). Recorded as a verdict file and an "
                   "entry in `runs/<paper>/approvals.jsonl`. A partial reading is a legitimate "
                   "state.",
        signals=["a verdict file beside a layer's output", "a badge \"approved v3 by <person>\""],
        distinct_from=[
            ("decision:scheme", "An adjudication is per paper, per version; a scheme ruling is for "
                                "every paper, once. Per-paper adjudications accumulate into a "
                                "layer acceptance."),
            ("verdict", "An adjudication is the act of reading; a verdict is one decision it "
                        "records about one claim or edge."),
        ],
        enforced_by="scripts/pipeline.py approve; scripts/verdicts.py (the skeleton and vocabulary)",
        operations=None,
        example=ex("asserted-about: the review adjudicates the toy modules, leaving verdicts",
                   "toy-study/review/verdict.json"),
        references={"note": NOTE["decision"]},
        glossary=["kind:adjudication", "adjudication"],
    ),
    "decision:run": dict(
        governed_by="procedure",
        definition="One of the four kinds of decision that is not a decision: produce the next "
                   "version under the current scheme. Nobody decides it; the runner does it. "
                   "Recorded as a ledger entry; its effect is a new, unread version. It needs an "
                   "issue only when it needs money.",
        signals=["a ledger entry naming inputs by hash", "\"run the chain on the nine papers\""],
        distinct_from=[
            ("decision:code", "A run produces a version under an accepted scheme; a code decision "
                              "is a change to the mechanism. Calling a run a decision is how "
                              "\"carry the papers through the layers\" became an issue rather than "
                              "a command."),
        ],
        enforced_by="not enforced",
        operations=None,
        example=ex("derived: producing the toy analysis manifest is a run under the current scheme",
                   "toy-study/analysis/manifest.json"),
        references={"note": NOTE["decision"]},
        glossary=["kind:run"],
    ),
    "adjudication-procedure": dict(
        governed_by="procedure",
        definition="The four steps of an adjudication, the verdict vocabulary, and the rule that a "
                   "partial reading is a state — themselves a scheme, ruled on once and versioned. "
                   "A verdict file names the procedure version it was read under, so a reading "
                   "made under an earlier procedure stays a valid record. It is evaluable because "
                   "its output is structured: agreement, yield, persistence and effect.",
        signals=["a verdict file naming its `procedure_version`"],
        distinct_from=[
            ("decision:adjudication", "The procedure is the scheme (the steps and vocabulary); an "
                                      "adjudication is one application of it to a paper."),
        ],
        enforced_by="scripts/pipeline.py (procedure is a DOC_DECLARATION, versioned by digest); "
                    "accepted as procedure v1",
        operations=None,
        example=ex("asserted-about: the toy review names the procedure version it read under",
                   "toy-study/review/verdict.json"),
        references={"note": NOTE["decision"]},
        glossary=["procedure", "adjudication-procedure"],
    ),
    "verdict": dict(
        governed_by="procedure",
        definition="One decision an adjudication records about one claim or edge, from a closed "
                   "vocabulary. On a claim: `keep`, `strike`, `merge-into`, `part-of`, or a "
                   "corrected role or panel. On an edge: `ok`, `wrong-direction`, "
                   "`wrong-relation`, `strike`, `missing`. The verdicts become the next version "
                   "through the writer's carry machinery.",
        signals=["one word per claim and per edge in a verdict file"],
        distinct_from=[
            ("decision:adjudication", "A verdict is one recorded decision; the adjudication is the "
                                      "whole reading that produces them."),
            ("relation", "An edge verdict (`missing`, `wrong-relation`) is a judgement about a "
                         "relation, not a relation itself."),
        ],
        enforced_by="scripts/verdicts.py (the skeleton and the closed verdict sets)",
        operations=None,
        example=ex("asserted-about: the review keeps the finding and marks the rules-out edge ok",
                   "toy-study/review/verdict.json"),
        references={"note": NOTE["decision"]},
        glossary=["verdict", "keep", "strike", "merge-into", "wrong-direction", "wrong-relation",
                  "missing", "ok"],
    ),
}


# ── relation entries, generated from vocab.py ────────────────────────────────
# Each relation is a canon entry: its definition and direction are the declared data; the
# enrichment below supplies enforcement notes, a toy example and glossary where the default does
# not fit. A relation the toy graph exercises points at that edge; one it does not points at the
# stage where the concept nonetheless arises, with a corpus instance in references.

# toy edges present in canon/toy-study, by relation
_TOY_EDGES = {
    "entails": ("hyp-polish-raises-shine", "pred-polished-shinier"),
    "tests": ("finding-polished-shinier", "pred-polished-shinier"),
    "confirms": ("finding-polished-shinier", "pred-polished-shinier"),
    "supports": ("finding-polished-shinier", "hyp-polish-raises-shine"),
    "requires": ("finding-polished-shinier", "apparatus-shine-meter"),
    "validates": ("control-handled-no-rise", "finding-polished-shinier"),
    "rules-out": ("control-handled-no-rise", "alt-handling-raises-shine"),
    "scopes": ("scope-brass-widgets", "finding-polished-shinier"),
    "enables-method": ("apparatus-shine-meter", "finding-polished-shinier"),
    "interprets": ("interp-polish-removes-oxide", "finding-polished-shinier"),
    "qualifies": ("caveat-large-widgets-less", "finding-polished-shinier"),
    "part-of": ("result-shine-delta", "finding-polished-shinier"),
    "in-tension-with": ("result-gloss-aggregate-agrees", "result-gloss-individual-null"),
}

# A relation's governing declaration. `part-of` was ruled under #75 (parts); everything else is
# the relation vocabulary itself.
_REL_GOVERNED = {"part-of": "parts"}

# Where a relation not exercised by the toy graph nonetheless first arises, and its glossary.
_REL_STAGE = {
    "refutes": ("asserted-about: the outcome a tested prediction can take; the toy prediction is "
                "confirmed, not refuted", "toy-study/review/verdict.json"),
    "predicts": ("composed: a model-to-observation prediction; the toy hypothesis entails its "
                 "prediction", "toy-study/design.yaml"),
    "replicates": ("derived: an independent finding of the same result; the toy per-batch result "
                   "stands in", "toy-study/analysis/manifest.json"),
    "extends": ("induced: extending a claim beyond its conditions; not exercised in the toy study",
                "toy-study/paper.md"),
    "contradicts": ("asserted-about: two claims that cannot both hold; the toy study has none",
                    "toy-study/review/verdict.json"),
    "opposes": ("asserted-about: a claim standing against another; the toy study has none",
                "toy-study/review/verdict.json"),
    "dissociates-with": ("induced: a neutral contrast between two results; the toy study's tension "
                         "is the nearer case", "toy-study/paper.md"),
    "derived-from": ("induced: written mechanically as the reciprocal of entails",
                     "toy-study/paper.md"),
}


def _relation_entries() -> dict[str, dict]:
    out: dict[str, dict] = {}
    confus_by: dict[str, list] = {}
    for a, b, why in vocab.CONFUSABLE:
        confus_by.setdefault(a, []).append((f"relation:{b}", why))
        confus_by.setdefault(b, []).append((f"relation:{a}", why))
    for name in sorted(vocab.EDGE_KEYS):
        gov = _REL_GOVERNED.get(name, "relation-vocab")
        if name in _TOY_EDGES:
            s, t = _TOY_EDGES[name]
            example = ex("induced: the edge in the toy claim graph", f"{s} -{name}-> {t}")
        else:
            stage, ref = _REL_STAGE[name]
            example = ex(stage, ref)
        refs = {"note": NOTE["canon"]}
        if name in ("in-tension-with", "dissociates-with"):
            refs["note"] = NOTE["tension"]
        if name == "part-of":
            refs["note"] = NOTE["parts"]
        corpus_ex = vocab.EXAMPLE.get(name)
        if corpus_ex:
            refs["corpus"] = corpus_ex[0]
        enforced = ("scripts/check_relations.py (the vocabulary is closed; direction and the "
                    "opposition rules); extract/claim_graphs/edges.py")
        out[f"relation:{name}"] = dict(
            governed_by=gov,
            definition=vocab.DESCRIPTIONS[name],
            signals=[vocab.DIRECTION.get(name, "")],
            distinct_from=confus_by.get(name, []) or
            [("relation", "A relation is a typed logical edge, not a citation.")],
            enforced_by=enforced,
            operations=None,
            example=example,
            references=refs,
            glossary=[name],
        )
    return out


# ── role entries, generated from vocab.py ────────────────────────────────────

_ROLE_TOY = {  # a toy claim that plays each role
    "hypothesis": "hyp-polish-raises-shine",
    "prediction": "pred-polished-shinier",
    "empirical": "finding-polished-shinier",
    "control": "control-handled-no-rise",
    "scope": "scope-brass-widgets",
    "methodological": "apparatus-shine-meter",
    "synthesis": "loose-synth-widgets-improvable",
    "interpretation": "interp-polish-removes-oxide",
    "literature-context": None,   # the toy study inherits no cited premise
}


def _role_entries() -> dict[str, dict]:
    out: dict[str, dict] = {}
    confus_by: dict[str, list] = {}
    for a, b, why, _ea, _eb in vocab.ROLE_CONFUSABLE:
        confus_by.setdefault(a, []).append((f"role:{b}", why))
        confus_by.setdefault(b, []).append((f"role:{a}", why))
    for r in vocab.ROLES:
        name = r["role"]
        toy = _ROLE_TOY.get(name)
        if toy:
            example = ex(f"induced: a toy claim with role `{name}`", toy)
        else:
            example = ex("induced: a cited premise; the toy study inherits none",
                         "toy-study/paper.md")
        refs = {"note": NOTE["canon"], "corpus": r["example"][0]}
        out[f"role:{name}"] = dict(
            governed_by="claim-format",
            definition=" ".join(str(r["definition"]).split()),
            signals=list(r["signals"]),
            distinct_from=confus_by.get(name, []) or
            [("role", "A role is the work a claim does in an argument, not what kind of "
                      "proposition it is.")],
            enforced_by="extract/claim_graphs/vocabulary.py (ROLES, rendered into the contract "
                        "by contract.py); the `warrant` rule is by role",
            operations=None,
            example=example,
            references=refs,
            glossary=[name],
        )
    return out


def entries() -> dict[str, dict]:
    """The whole registry, ordered: singular concepts, then relations, then roles."""
    out: dict[str, dict] = {}
    out.update(SINGLETONS)
    out.update(_relation_entries())
    out.update(_role_entries())
    for eid, e in out.items():
        e.setdefault("status", ACCEPTED if e["governed_by"] in ACCEPTED_DECLARATIONS else PROPOSED)
    return out


ACCEPTED, PROPOSED = "accepted", "proposed"
FIELDS = ("definition", "signals", "distinct_from", "enforced_by", "operations", "example",
          "references", "status", "governed_by", "glossary")
