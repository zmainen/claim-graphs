#!/usr/bin/env python3
"""The modules derivation, on a synthetic paper that exercises every one of the six steps.

A twelve-claim paper is written to a temporary corpus and run through `modules.build`: a
question module with a hypothesis, an alternative and a prediction; a finding cluster whose
results include a detail of a detail; a scope claim (domain) and an apparatus claim; an
observation; and a loose synthesis that carries its reason. Byte-stability is pinned (two builds
agree, a second write is a no-op), and the two `check_relations` warnings the layer's rules add
are pinned against the same paper.

No network, no model. The corpus is built here, so it runs with no checkout. Env is set before
`modules` is imported because the graph root and claims dir are read at import.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

_ROOT = tempfile.mkdtemp(prefix="modules-test-")
os.environ["CLAIM_GRAPHS_ROOT"] = _ROOT
os.environ["CLAIM_GRAPHS_CORPUS_DIR"] = os.path.join(_ROOT, "claims")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PAPER = "synth-modules"
CLAIMS = os.path.join(_ROOT, "claims", PAPER)
RUNS = os.path.join(_ROOT, "runs", PAPER)

# slug -> (role, frontmatter-body). Edges are top-level keys except supports/requires, which the
# format stores under `belongings:` (see extract/claim_graphs/edges.py).
_CLAIMS = {
    "hyp-main": ("hypothesis", {"entails": ["pred-1"]}),
    "alt-rival": ("hypothesis", {"_stance": "rejects"}),
    "pred-1": ("prediction", {}),
    "finding-a": ("empirical", {"tests": ["pred-1"], "confirms": ["pred-1"],
                                "warrant": "moderate",
                                "belongings": [{"relation": "requires", "target": "apparatus-model"}]}),
    "result-detail": ("empirical", {"part-of": ["finding-a"]}),
    "detail-of-detail": ("empirical", {"validates": ["result-detail"]}),
    "control-elim": ("control", {"rules-out": ["alt-rival"], "warrant": "strong"}),
    "scope-sample": ("scope", {"scopes": ["finding-a"]}),
    "apparatus-model": ("methodological", {}),
    "obs-standalone": ("empirical", {"warrant": "moderate"}),
    "obs-detail": ("empirical", {"part-of": ["obs-standalone"]}),
    "loose-synth": ("synthesis", {}),
}


def _frontmatter(slug: str, role: str, body: dict) -> str:
    lines = [f"uuid: 0000-{slug}", f"slug: {slug}", f"claim: sentence for {slug}",
             "claim-type: empirical", f"role: {role}"]
    stance = body.get("_stance")
    for key, val in body.items():
        if key.startswith("_"):
            continue
        if key == "belongings":
            lines.append("belongings:")
            for b in val:
                lines.append(f"  - relation: {b['relation']}")
                lines.append(f"    target: {b['target']}")
        elif isinstance(val, list):
            lines.append(f"{key}:")
            lines += [f"  - {t}" for t in val]
        else:
            lines.append(f"{key}: {val}")
    lines.append("assertions:")
    lines.append(f"  - paper-slug: {PAPER}")
    if stance:
        lines.append(f"    stance: {stance}")
    lines.append("reproductions: []")
    return "---\n" + "\n".join(lines) + "\n---\n"


def _build_corpus():
    os.makedirs(CLAIMS, exist_ok=True)
    os.makedirs(RUNS, exist_ok=True)
    for slug, (role, body) in _CLAIMS.items():
        with open(os.path.join(CLAIMS, f"{slug}.md"), "w", encoding="utf-8") as fh:
            fh.write(_frontmatter(slug, role, body))
    with open(os.path.join(CLAIMS, "index.md"), "w", encoding="utf-8") as fh:
        fh.write(f"---\npaper-slug: {PAPER}\n---\n")
    # addresses live in the answer file (elife #157), which `modules` reads alongside claim files
    with open(os.path.join(RUNS, "questions.answer.v1.json"), "w", encoding="utf-8") as fh:
        json.dump({"questions": [{"id": "q1", "text": "the question under test?"}],
                   "addresses": {"hyp-main": "q1", "alt-rival": "q1"}}, fh)


_build_corpus()

import modules  # noqa: E402
import check_relations  # noqa: E402


def _q1(full):
    return next(m for m in full["modules"] if m["id"] == "q1")


def test_question_module():
    full, _ = modules.build(PAPER)
    q1 = _q1(full)
    assert q1["kind"] == "question"
    assert q1["hypotheses"] == ["hyp-main"]
    assert [a["slug"] for a in q1["alternatives"]] == ["alt-rival"]
    # the control that rules out the rival is what eliminated it
    assert q1["alternatives"][0]["eliminated_by"] == ["control-elim"]
    assert [p["prediction"] for p in q1["predictions"]] == ["pred-1"]
    assert q1["predictions"][0]["outcome"] == "confirmed"
    print("ok  question module: hypothesis, alternative eliminated, prediction confirmed")


def test_finding_cluster_and_detail_of_detail():
    full, _ = modules.build(PAPER)
    q1 = _q1(full)
    clusters = q1["findings"] + [f for p in q1["predictions"] for f in p["findings"]]
    fa = next(c for c in clusters if c["finding"] == "finding-a")
    # a result and the detail of that result are both placed in the cluster
    assert set(fa["results"]) == {"result-detail", "detail-of-detail"}, fa["results"]
    # combine records only the DIRECT result the warrant was computed from
    assert fa["combine"]["parts"] == ["result-detail"]
    assert fa["warrant"] == "moderate"
    print("ok  finding cluster: result and detail-of-detail placed, combine is direct only")


def test_scope_split():
    full, _ = modules.build(PAPER)
    q1 = _q1(full)
    assert q1["domain"] == ["scope-sample"]
    assert q1["apparatus"] == ["apparatus-model"]
    print("ok  scope: domain from scopes, apparatus from requires")


def test_observation():
    full, _ = modules.build(PAPER)
    obs = [m for m in full["modules"] if m["kind"] == "observation"]
    assert len(obs) == 1, [m["id"] for m in full["modules"]]
    o = obs[0]
    assert o["finding"]["finding"] == "obs-standalone"
    assert o["finding"]["results"] == ["obs-detail"]
    print("ok  observation: a whole with no argument edge, its result beneath it")


def test_loose_has_reason():
    full, _ = modules.build(PAPER)
    loose = {it["slug"]: it["reason"] for it in full["loose"]}
    assert "loose-synth" in loose, loose
    assert "synthesis" in loose["loose-synth"]
    print("ok  loose: the synthesis is loose and its reason names the missing edge")


def test_byte_stable():
    a, _ = modules.build(PAPER)
    b, _ = modules.build(PAPER)
    assert json.dumps(a) == json.dumps(b)
    path = os.path.join(RUNS, "modules.json")
    assert modules._write(path, a) in (True, False)
    assert modules._write(path, a) is False        # a second write of the same content is a no-op
    print("ok  byte-stable: two builds agree, a re-write is a no-op")


def test_check_relations_warnings():
    modules.build(PAPER)
    modules._write(os.path.join(RUNS, "modules.json"), modules.build(PAPER)[0])
    _errors, warnings = check_relations.check(PAPER)
    assert any("loose-synth" in w and "no outgoing argument edge" in w for w in warnings), warnings
    assert any("loose after `modules`" in w for w in warnings), warnings
    print("ok  check_relations: synthesis-outward warning and per-loose-claim warning fire")


def _run():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nall modules tests passed")


if __name__ == "__main__":
    _run()
