#!/usr/bin/env python3
"""Gädeke 2026 in the core vocabulary — the appendix of
docs/design/2026-10-07-mira-native-vocabulary.md as a MIRA JSON-LD graph.

This is a hand-built specification, not a pipeline output. The node list and every edge are
written here by hand from the appendix; the script only fetches each node's sentence, plain
title, panel and anchor quote from the claim files and the plain-claim layer so the texts are
the corpus's own rather than retyped. It exists so the appendix can be validated against
MIRA's shapes and compared, node for node, with what the pipeline later reproduces.

Usage:
  CLAIM_GRAPHS_ROOT=<elife-claim-trees checkout> python3 docs/design/2026-10-07-gadeke-core.py
  ... --validate     also run pyshacl against the vendored shapes under the same root
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required (use the conda python)")

ROOT = os.environ.get("CLAIM_GRAPHS_ROOT") or sys.exit("set CLAIM_GRAPHS_ROOT to the corpus checkout")
PAPER = "gadeke-2026-guilt-insula"
CLAIMS = os.path.join(ROOT, "claims", PAPER)
PLAIN = os.path.join(ROOT, "runs", PAPER, "plain-claim.answer.v5.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "2026-10-07-gadeke-core.jsonld")
DOI = "https://doi.org/10.7554/eLife.105391"
WHO = "urn:claim-graphs:hand-built-2026-10-07"
STAMP = "2026-10-07T00:00:00.000Z"
BASE = f"urn:claim-graphs:{PAPER}:core:"
MIRA_CONTEXT_URL = "https://purl.org/mira-science/mira.jsonld"

# ── the corpus's own words ────────────────────────────────────────────────────

def load_claims():
    out = {}
    for f in sorted(os.listdir(CLAIMS)):
        if not f.endswith(".md") or f == "index.md":
            continue
        text = open(os.path.join(CLAIMS, f), encoding="utf-8").read()
        fm = yaml.safe_load(text.split("---")[1])
        a = (fm.get("assertions") or [{}])[0]
        q = re.search(r"\*\*(?:results|caption|structure)-reader evidence:\*\*\s*\n> (.+)", text)
        out[fm["slug"]] = {
            "claim": " ".join(fm["claim"].split()),
            "panel": a.get("panel"),
            "anchor": q.group(1).strip() if q else None,
        }
    return out

C = load_claims()
PLAIN_TITLES = json.load(open(PLAIN, encoding="utf-8"))

def text(slug):
    return C[slug]["claim"]

def plain(slug, fallback=None):
    return PLAIN_TITLES.get(slug) or fallback or slug

# ── the specification ─────────────────────────────────────────────────────────
# Each entry: local id → (type, title, full statement, extras). Texts marked "from:<slug>"
# are the corpus's; the rest are written here, which is the Claim layer's job.

QUESTIONS = {
    "Q1": "Does responsibility for a social choice that leaves a partner worse off produce "
          "interpersonal guilt — a larger fall in the decision-maker's momentary happiness than "
          "when the partner made the same choice?",
    "Q2": "Is the anterior insula, with its condition- and choice-dependent connectivity to "
          "prefrontal cortex, the neural substrate of that guilt?",
    "Q3": "Does a neural substrate track the participant's responsibility for the partner's "
          "outcomes — representing the partner's reward prediction errors more strongly when "
          "they follow the participant's own choice?",
}

STUDIES = {
    "S1": ("Study 1 (behavioural, N = 40)",
           "Forty healthy adults performed the lottery choice task outside the scanner in three "
           "sessions, choosing for themselves (Solo), for themselves and a partner (Social), or "
           "watching the partner choose for both (Partner), and rated momentary happiness every "
           "few trials. The partner was another participant whose choices were simulated by an "
           "algorithm that always selected the option with the highest expected value."),
    "S2": ("Study 2 (fMRI, N = 44)",
           "Forty-four healthy adults performed the same task inside the fMRI scanner in two "
           "sessions, with identical parameters except longer inter-stimulus intervals (3–11 s) "
           "and partners who were experimenters positioned outside the scanner. All BOLD results "
           "derive from this study; behavioural results come from both."),
}

PROTOCOLS = {
    "P-task": ("Lottery choice task with Solo, Social and Partner conditions",
               text("each-trial-participants-chose-between") + " " + text("hold-partner-behaviour-constant-across")),
    "P-happiness": ("Computational modelling of momentary happiness",
                    text("momentary-happiness-modelled-five-computational") + " " + text("model-selection-among-happiness-models")),
    "P-LMM": ("Linear mixed models on happiness",
              "Happiness was analysed with linear mixed models containing the partner-outcome, "
              "decision-maker and participant-outcome factors and their two-way interactions "
              "(Model 5, Equation 10)."),
    "P-GLM2": ("Model-based GLM", text("model-based-glm-entered-best-fitting-computational")),
    "P-ROI": ("ROI definition by the lottery-versus-safe outcome contrast",
              "Regions of interest were defined as clusters more active during receipt of lottery "
              "than safe outcomes across all conditions. " + text("during-receipt-lottery-versus-safe")),
    "P-PPI": ("Seed-to-voxel psychophysiological interaction",
              "Two gPPI seed-to-voxel connectivity analyses used functionally defined seeds — the "
              "left insula cluster sensitive to risky versus safe outcomes and the left STS cluster "
              "responding more to social_pRPE than partner_pRPE — with identical seeds across participants."),
}

# Claims: id → (title, statement, source slugs for provenance)
CLAIMS_ = {
    # Q1
    "H1": (plain("responsibility-social-choice-yields-low"), text("responsibility-social-choice-yields-low"), ["responsibility-social-choice-yields-low"]),
    "P1a": ("Happiness fell more after a partner's low outcome when the participant had chosen",
            "When the partner received the low lottery outcome, participant happiness was lower when "
            "the participant rather than the partner had chosen the lottery — a partner-outcome × "
            "decision-maker interaction, in both studies.",
            ["responsibility-outcomes-generates-guilt-participant", "when-partner-received-low-lottery", "both-studies-participants-felt-worse"]),
    "P1b": ("A happiness model weighting the partner's prediction errors from the participant's own choices fits best",
            "A computational model that includes the partner's reward prediction errors arising from "
            "the participant's own choices (social_pRPE) explains the happiness data better than "
            "models omitting them, and the social_pRPE weights are reliably greater than zero.",
            ["responsibility-partner-outcomes-influences-participant"]),
    "F-rewards": ("Happiness tracked the participant's and the partner's rewards",
                  "Participant momentary happiness varied with the rewards the participant and the "
                  "partner received in the current trial.",
                  ["participant-momentary-happiness-varied-rewards", "participant-momentary-happiness-varied-rewards-2"]),
    "F-ownRPE": ("The participant's own prediction errors weighed more than the partner's",
                 text("participants-own-reward-prediction-errors").split(" (Study 1")[0] + ".",
                 ["participants-own-reward-prediction-errors"]),
    "F-agency": ("Being the decision-maker lowered happiness, whatever the outcome",
                 "Participant happiness was lower when the participant was the decision-maker "
                 "(Social and Solo versus Partner), independent of outcome.",
                 ["participant-happiness-lower-when-participant"]),
    "F-risk": (plain("participants-showed-very-similar-risk"), text("participants-showed-very-similar-risk"), ["participants-showed-very-similar-risk"]),
    "R-agency": (plain("alt-agency-aversion-not-guilt"), text("alt-agency-aversion-not-guilt"), ["alt-agency-aversion-not-guilt"]),
    "R-own": (plain("alt-guilt-effect-driven-by-own-outcome"), text("alt-guilt-effect-driven-by-own-outcome"), ["alt-guilt-effect-driven-by-own-outcome"]),
    "R-risk": (plain("alt-social-context-shifts-risk-attitude"), text("alt-social-context-shifts-risk-attitude"), ["alt-social-context-shifts-risk-attitude"]),
    "I-responsibility-aversion": (plain("lower-happiness-when-participant-decision-maker"), text("lower-happiness-when-participant-decision-maker"), ["lower-happiness-when-participant-decision-maker"]),
    "I-simple-guilt": (plain("behavioural-guilt-effect-larger-happiness"), text("behavioural-guilt-effect-larger-happiness"), ["behavioural-guilt-effect-larger-happiness"]),
    # Q2
    "H2": (plain("anterior-insula-neural-substrate-guilt"), text("anterior-insula-neural-substrate-guilt"), ["anterior-insula-neural-substrate-guilt"]),
    "P2": ("Insula BOLD was higher for the partner's low outcomes when the participant had chosen",
           "Insula BOLD responses to low lottery outcomes for the partner were higher in the Social "
           "than the Partner condition, with a Social × low-outcome interaction, even after "
           "subtracting responses to high outcomes.",
           ["anterior-insula-tracks-guilt-insula", "insula-rois-responded-more-low"]),
    "F-signature": ("The insula guilt response matched a published guilt signature",
                    "Individual neural guilt responses matched the Yu et al. (2020) guilt-related brain "
                    "signature, providing convergent validity.",
                    ["dot-products-between-individual-neural"]),
    "F-signature-individual": ("The signature match did not track individual guilt sensitivity",
                               "The match to the guilt-related brain signature did not correlate with "
                               "individual differences in the behavioural guilt effect.",
                               ["individual-grbs-dot-product-values-not"]),
    "H2b": (plain("functional-connectivity-between-guilt-responsibility-related"), text("functional-connectivity-between-guilt-responsibility-related"), ["functional-connectivity-between-guilt-responsibility-related"]),
    "P2b": ("Insula–right IFG connectivity varied with condition and choice",
            "Functional connectivity between the left anterior insula and the right inferior frontal "
            "gyrus varied with condition and choice, being highest when participants made risky "
            "choices for themselves and safe choices for both players.",
            ["connectivity-between-guilt-responsibility-related-outcome-ph", "functional-connectivity-between-left-anterior"]),
    "I-IFG": (plain("connectivity-between-left-anterior-insula"), text("connectivity-between-left-anterior-insula"), ["connectivity-between-left-anterior-insula"]),
    "F-social-network": ("Social versus Solo decisions engaged precuneus, TPJ and mPFC",
                         "Decisions in the Social compared with the Solo condition engaged the precuneus, "
                         "left temporo-parietal junction and medial prefrontal cortex, the first two most "
                         "active when participants chose the lottery in the Social condition.",
                         ["decisions-social-compared-solo-condition", "only-precuneus-tpj-showed-positive"]),
    # Q3
    "H3": (plain("neural-substrate-tracks-participant-responsibility"), text("neural-substrate-tracks-participant-responsibility"), ["neural-substrate-tracks-participant-responsibility"]),
    "P3": ("A left STS cluster tracked the partner's prediction errors from the participant's choices",
           "A left superior temporal sulcus cluster responded more to the partner's reward prediction "
           "errors resulting from the participant's than from the partner's choices.",
           ["neural-substrate-tracks-participant-responsibility-2", "one-cluster-left-sts-responded"]),
    "I-STS": (plain("authors-suggest-left-sts-region"), text("authors-suggest-left-sts-region"), ["authors-suggest-left-sts-region"]),
}

# Evidence: id → (slug, study, protocols)
EVIDENCE = {
    # Q1
    "E-guilt-S1": ("when-partner-received-low-lottery", "S1", ["P-task", "P-LMM"]),
    "E-guilt-S2": ("when-partner-received-low-lottery", "S2", ["P-task", "P-LMM"]),
    "E-LR": ("likelihood-ratio-test-showed-responsibility", "S1", ["P-happiness"]),
    "E-weights": ("partner-reward-prediction-errors-resulting", "S1", ["P-happiness"]),
    "E-R2": ("responsibility-model-yielded-higher-values", "S1", ["P-happiness"]),
    "E-AIC": ("among-computational-models-fitted-momentary", "S1", ["P-happiness"]),
    "E-redux-fit": ("responsibility-redux-model-incorporating-expected", "S1", ["P-happiness"]),
    "E-recovery": ("parameter-recovery-procedure-synthetic-data-generated", "S1", ["P-happiness"]),
    "E-rho-gainloss": ("risk-aversion-parameter-not-differ-between", "S1", ["P-happiness"]),
    "E-own-rewards": ("participant-momentary-happiness-varied-rewards", "S1", ["P-task"]),
    "E-partner-rewards": ("participant-momentary-happiness-varied-rewards-2", "S1", ["P-task"]),
    "E-sRPE": ("participants-own-reward-prediction-errors", "S1", ["P-happiness"]),
    "E-LMM-selection": ("linear-mixed-model-containing-all", "S1", ["P-LMM"]),
    "E-icebreaker": ("pre-task-icebreaker-succeeded-establishing-positive", "S1", ["P-task"]),
    "E-no-effect-high": ("responsibility-choices-not-influence-happiness", "S1", ["P-LMM"]),
    "E-own-outcome": ("guilt-effect-occurred-whether-participant", "S1", ["P-LMM"]),
    "E-agency": ("participant-happiness-lower-when-participant", "S1", ["P-LMM"]),
    "E-premiums": ("risk-premiums-not-differ-between", "S1", ["P-task"]),
    "E-rho-social": ("participants-slightly-more-risk-averse", "S1", ["P-task"]),
    "E-risky-choice": ("participants-chose-risky-option-lottery", "S1", ["P-task"]),
    "E-choice-regression": ("mixed-effects-regressions-choices-social-condition", "S1", ["P-task"]),
    "E-EV-interaction": ("no-significant-interaction-between-difference", "S1", ["P-task"]),
    "E-value-sensitive": ("participants-probability-choosing-risky-option", "S1", ["P-task"]),
    # Q2
    "E-insula-ROI": ("insula-rois-responded-more-low", "S2", ["P-ROI"]),
    "E-insula-voxel": ("mass-univariate-voxel-wise-analysis-found-small", "S2", ["P-task"]),
    "E-insula-diff": ("difference-response-between-low-high", "S2", ["P-ROI"]),
    "E-insula-outcome": ("during-outcome-phase-responses-low", "S2", ["P-ROI"]),
    "E-striatum-risky": ("bilateral-ventral-striatum-more-active", "S2", ["P-task"]),
    "E-signature": ("dot-products-between-individual-neural", "S2", ["P-ROI"]),
    "E-signature-individual": ("individual-grbs-dot-product-values-not", "S2", ["P-ROI"]),
    "E-PPI-insula": ("functional-connectivity-between-left-anterior", "S2", ["P-PPI"]),
    "E-PPI-STS": ("left-ifg-cluster-showed-opposite", "S2", ["P-PPI"]),
    "E-social-solo": ("decisions-social-compared-solo-condition", "S2", ["P-task"]),
    "E-precuneus-tpj": ("only-precuneus-tpj-showed-positive", "S2", ["P-task"]),
    "E-localizer": ("during-receipt-lottery-versus-safe", "S2", ["P-ROI"]),
    # Q3
    "E-STS-cluster": ("one-cluster-left-sts-responded", "S2", ["P-GLM2"]),
    "E-STS-sessions": ("left-superior-temporal-sulcus-cluster", "S2", ["P-GLM2"]),
    "E-manipulation": ("manipulation-check-bilateral-ventral-striatum", "S2", ["P-GLM2"]),
}

# Literature: id → (slug, target claim). Each becomes SourceDocument → Study → Evidence → supports.
LITERATURE = {
    "L-rutledge": ("rutledge-colleagues-established-changes-momentary", "F-rewards"),
    "L-insula-guilt": ("prior-literature-documents-association-between", "H2"),
    "L-connectivity": ("prior-functional-connectivity-work-shown", "H2b"),
}

# Edges beyond grounds / follows / sourceDocument, which are derived from the tables above.
EDGES = [
    # addresses
    ("H1", "addresses", "Q1"), ("R-agency", "addresses", "Q1"), ("R-own", "addresses", "Q1"), ("R-risk", "addresses", "Q1"),
    ("H2", "addresses", "Q2"), ("H2b", "addresses", "Q2"),
    ("H3", "addresses", "Q3"),
    # entails — the one addition
    ("H1", "entails", "P1a"), ("H1", "entails", "P1b"),
    ("H2", "entails", "P2"), ("H2b", "entails", "P2b"),
    ("H3", "entails", "P3"),
    # observationStatement — the claim an observation makes
    ("E-guilt-S1", "observationStatement", "P1a"), ("E-guilt-S2", "observationStatement", "P1a"),
    ("E-LR", "observationStatement", "P1b"), ("E-weights", "observationStatement", "P1b"),
    ("E-own-rewards", "observationStatement", "F-rewards"), ("E-partner-rewards", "observationStatement", "F-rewards"),
    ("E-sRPE", "observationStatement", "F-ownRPE"),
    ("E-agency", "observationStatement", "F-agency"),
    ("E-premiums", "observationStatement", "F-risk"), ("E-rho-social", "observationStatement", "F-risk"),
    ("E-risky-choice", "observationStatement", "F-risk"), ("E-choice-regression", "observationStatement", "F-risk"),
    ("E-EV-interaction", "observationStatement", "F-risk"),
    ("E-insula-ROI", "observationStatement", "P2"), ("E-insula-voxel", "observationStatement", "P2"),
    ("E-insula-diff", "observationStatement", "P2"), ("E-insula-outcome", "observationStatement", "P2"),
    ("E-signature", "observationStatement", "F-signature"),
    ("E-signature-individual", "observationStatement", "F-signature-individual"),
    ("E-PPI-insula", "observationStatement", "P2b"),
    ("E-social-solo", "observationStatement", "F-social-network"), ("E-precuneus-tpj", "observationStatement", "F-social-network"),
    ("E-STS-cluster", "observationStatement", "P3"),
    # supports — further evidence, checks (marked in the note as a view, not here), and claim→claim
    ("E-R2", "supports", "P1b"), ("E-AIC", "supports", "P1b"), ("E-redux-fit", "supports", "P1b"),
    ("E-recovery", "supports", "P1b"), ("E-rho-gainloss", "supports", "P1b"),
    ("E-LMM-selection", "supports", "P1a"), ("E-icebreaker", "supports", "P1a"),
    ("E-no-effect-high", "supports", "P1a"), ("E-own-outcome", "supports", "P1a"),
    ("E-value-sensitive", "supports", "P1a"), ("E-value-sensitive", "supports", "F-risk"),
    ("F-agency", "supports", "I-responsibility-aversion"),
    ("P1a", "supports", "I-simple-guilt"),
    ("E-striatum-risky", "supports", "P2"),
    ("F-signature", "supports", "H2"),
    ("E-PPI-STS", "supports", "P2b"),
    ("P2b", "supports", "I-IFG"),
    ("E-STS-sessions", "supports", "P3"), ("E-manipulation", "supports", "P3"),
    ("P3", "supports", "I-STS"),
    # opposes — rivals eliminated
    ("E-own-outcome", "opposes", "R-own"),
    ("P1a", "opposes", "R-agency"),
    ("F-risk", "opposes", "R-risk"),
]

RELATIONS = {
    "addresses": ("mira:addresses", "Claim", "Question", "a claim answers a research question"),
    "supports": ("mira:supports", "Argument", "Claim", "the source strengthens the claim"),
    "opposes": ("mira:opposes", "Argument", "Claim", "the source weakens the claim"),
    "observationStatement": ("mira:observationStatement", "Evidence", "Claim", "the claim an observation makes"),
    "grounds": ("mira:grounds", "Study", "Evidence", "a study produces a piece of evidence"),
    "follows": ("mira:follows", "Study", "Protocol", "a study follows a method"),
    "describesActivity": ("mira:describesActivity", "SourceDocument", "Study", "a document describes the study it reports"),
    "entails": (None, "Claim", "Claim", "a hypothesis entails a prediction it commits the paper to — "
                                      "the one relation here that MIRA does not define"),
}

# ── emit ──────────────────────────────────────────────────────────────────────

def item(content):
    return {"@type": "Item", "format": "text/plain", "content": content}

def stamped(n):
    n.update({"creator": WHO, "created": STAMP, "modified": STAMP})
    return n

def main():
    validate = "--validate" in sys.argv
    g = [{"@id": WHO, "@type": "UserAccount", "accountName": "claim-graphs, hand-built from the appendix"}]
    # Argument is MIRA's mixin for whatever may support or oppose — Evidence or Claim — and is
    # the domain of those two relations, so it needs a schema like the six concrete types.
    for t in ["Question", "Claim", "Evidence", "Study", "Protocol", "SourceDocument", "Argument"]:
        g.append(stamped({"@id": f"cg:type/{t}", "@type": "NodeSchema", "subClassOf": [f"mira:{t}"], "label": t}))
    for key, (sup, dom, rng, why) in RELATIONS.items():
        rid, did = f"cg:rel/{key}", f"cg:rel/{key}/def"
        sub = [{"@type": "owl:Restriction", "onProperty": "rdf:predicate", "hasValue": rid}]
        if sup:
            sub.insert(0, sup)
        g.append(stamped({"@id": rid, "@type": "AbstractRelationDef", "subClassOf": sub, "label": key}))
        g.append(stamped({"@id": did, "@type": "RelationDef", "domain": f"cg:type/{dom}", "range": f"cg:type/{rng}",
                          "subClassOf": [rid, "dgb:RelationInstance"], "label": key, "description": item(why)}))

    ids = {}
    def node(local, t, title, statement, **extra):
        iri = BASE + local
        ids[local] = iri
        n = {"@id": iri, "@type": [f"cg:type/{t}", t], "title": title, "description": item(statement)}
        n.update(extra)
        g.append(n)
        return iri

    g.append({"@id": DOI, "@type": ["cg:type/SourceDocument", "SourceDocument"],
              "title": "Contributions of insula and superior temporal sulcus to interpersonal guilt and "
                       "responsibility in social decisions (Gädeke et al., 2026, eLife 105391)"})
    ids["paper"] = DOI
    for q, t in QUESTIONS.items():
        node(q, "Question", t.split(" — ")[0].rstrip("?") + "?", t)
    for s, (title, desc) in STUDIES.items():
        node(s, "Study", title, desc)
    for p, (title, desc) in PROTOCOLS.items():
        node(p, "Protocol", title, desc)
    for c, (title, statement, sources) in CLAIMS_.items():
        node(c, "Claim", title, statement)
    for e, (slug, study, protos) in EVIDENCE.items():
        extra = {"sourceDocument": DOI}
        node(e, "Evidence", plain(slug), C[slug]["claim"], **extra)
    for l, (slug, target) in LITERATURE.items():
        d = node(l, "SourceDocument", plain(slug, "cited work"), "Cited work to be resolved to a DOI by reference-check. " + C[slug]["claim"])
        s = node(l + "-study", "Study", "The cited study", "The investigation the cited work reports.")
        e = node(l + "-evidence", "Evidence", plain(slug), C[slug]["claim"], sourceDocument=d)

    edges = list(EDGES)
    for e, (slug, study, protos) in EVIDENCE.items():
        edges.append((study, "grounds", e))
    for s in STUDIES:
        for p in PROTOCOLS:
            if any(s == st and p in pr for (_, st, pr) in EVIDENCE.values()):
                edges.append((s, "follows", p))
    edges += [(DOI, "describesActivity", s) for s in STUDIES]
    for l, (slug, target) in LITERATURE.items():
        edges += [(l, "describesActivity", l + "-study"), (l + "-study", "grounds", l + "-evidence"),
                  (l + "-evidence", "supports", target)]

    seen = set()
    for i, (src, rel, dst) in enumerate(edges, 1):
        if (src, rel, dst) in seen:
            continue
        seen.add((src, rel, dst))
        s, d = ids.get(src, src), ids.get(dst, dst)
        types = [f"cg:rel/{rel}"] + ([rel] if RELATIONS[rel][0] else [])
        g.append(stamped({"@id": f"{BASE}edge/{i}", "@type": types, "source": s, "destination": d,
                          "title": f"[[{src}]] -{rel}-> [[{dst}]]"}))

    doc = {"@context": [MIRA_CONTEXT_URL, {
        "cg": "https://w3id.org/claim-graphs/schema#",
        "dgb": "https://discoursegraphs.com/schema/dg_base#",
        "owl": "http://www.w3.org/2002/07/owl#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "onProperty": {"@id": "owl:onProperty", "@type": "@id"},
        "hasValue": {"@id": "owl:hasValue", "@type": "@id"},
    }], "@graph": g}
    json.dump(doc, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    from collections import Counter
    types = Counter(n["@type"][-1] if isinstance(n["@type"], list) else n["@type"] for n in g)
    rels = Counter(e[1] for e in seen)
    print(f"wrote {os.path.relpath(OUT)}")
    print("nodes:", dict(types))
    print("edges:", dict(rels), "total", len(seen))

    if validate:
        vendor = os.path.join(ROOT, "vendor")
        local = json.load(open(os.path.join(vendor, "mira.jsonld"), encoding="utf-8"))["@context"]
        doc["@context"] = [local if c == MIRA_CONTEXT_URL else c for c in doc["@context"]]
        with tempfile.NamedTemporaryFile("w", suffix=".jsonld", delete=False) as tmp:
            json.dump(doc, tmp)
        p = subprocess.run(["pyshacl", "-s", os.path.join(vendor, "mira.shacl"), "-sf", "turtle",
                            "-df", "json-ld", tmp.name], capture_output=True, text=True)
        print(p.stdout[-6000:] or p.stderr[-3000:])

if __name__ == "__main__":
    main()
