#!/usr/bin/env python3
"""The canon's toy study, run through every layer that needs no model.

The study in `canon/toy-study/` is copied to a temporary root (so the repo stays clean and the
run is byte-stable), then driven through the mechanical layers the canon note names — modules,
prediction-outcome, warrant's rule, the verification check and the linter — and each is asserted
to derive the structure the fixture declares. The composed graph (`composed.yaml`) and the
induced graph (the claim files) are asserted to agree at the argument grain.

No network, no model, no corpus checkout. Env is set before the layer modules are imported,
because each binds its graph root at import.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_SRC = REPO / "canon" / "toy-study"
_ROOT = Path(tempfile.mkdtemp(prefix="canon-toy-"))
shutil.copytree(_SRC, _ROOT / "study")
STUDY = _ROOT / "study"
PAPER = "toy-widgets"

os.environ["CLAIM_GRAPHS_ROOT"] = str(STUDY)
os.environ["CLAIM_GRAPHS_CORPUS_DIR"] = str(STUDY / "claims")

sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "extract"))
sys.path.insert(0, str(REPO))

import yaml  # noqa: E402
import modules  # noqa: E402
import warrant  # noqa: E402
import prediction_outcome  # noqa: E402
import check_relations  # noqa: E402
from export_mira import load_paper  # noqa: E402
from claim_graphs import verification_check as vc  # noqa: E402


def _question(full):
    return next(m for m in full["modules"] if m["kind"] == "question")


def test_modules_derives_the_declared_structure():
    full, _ = modules.build(PAPER)
    q = _question(full)
    assert q["hypotheses"] == ["hyp-polish-raises-shine"], q["hypotheses"]
    assert [a["slug"] for a in q["alternatives"]] == ["alt-handling-raises-shine"]
    assert q["alternatives"][0]["eliminated_by"] == ["control-handled-no-rise"]
    assert [p["prediction"] for p in q["predictions"]] == ["pred-polished-shinier"]
    assert q["predictions"][0]["outcome"] == "confirmed"
    assert q["domain"] == ["scope-brass-widgets"]
    assert q["apparatus"] == ["apparatus-shine-meter"]
    clusters = q["findings"] + [f for p in q["predictions"] for f in p["findings"]]
    fa = next(c for c in clusters if c["finding"] == "finding-polished-shinier")
    assert set(fa["combine"]["parts"]) == {"result-shine-delta", "result-per-batch-shine"}
    obs = [m for m in full["modules"] if m["kind"] == "observation"]
    assert [o["finding"]["finding"] for o in obs] == ["obs-heavier-widgets-duller"]
    loose = {it["slug"] for it in full["loose"]}
    assert "loose-synth-widgets-improvable" in loose, loose
    print("ok  modules: question module, observation and loose claim derived as declared")


def test_composed_and_induced_agree():
    composed = yaml.safe_load((STUDY / "composed.yaml").read_text(encoding="utf-8"))
    full, _ = modules.build(PAPER)
    q = _question(full)
    assert q["id"] == composed["module"]
    assert sorted(q["hypotheses"]) == sorted(composed["hypotheses"])
    assert {a["slug"]: sorted(a["eliminated_by"]) for a in q["alternatives"]} == \
        {a["slug"]: sorted(a["eliminated_by"]) for a in composed["alternatives"]}
    assert {p["prediction"]: p["outcome"] for p in q["predictions"]} == \
        {p["prediction"]: p["outcome"] for p in composed["predictions"]}
    assert sorted(q["domain"]) == sorted(composed["domain"])
    assert sorted(q["apparatus"]) == sorted(composed["apparatus"])
    print("ok  composed and induced graphs agree at the argument grain")


def test_prediction_outcome():
    d = prediction_outcome.build([PAPER])
    item = next(i for i in d["items"] if i["prediction"] == "pred-polished-shinier")
    assert item["bucket"] == "recorded", item
    assert item["confirms"] == ["finding-polished-shinier"]
    print("ok  prediction-outcome: the prediction is recorded, confirmed by the finding")


def test_warrant_rule():
    res = warrant.resolve(PAPER)
    assert res["hyp-polish-raises-shine"]["level"] == "strong"
    assert res["finding-polished-shinier"]["level"] == "strong"
    assert res["control-handled-no-rise"]["level"] == "moderate"
    assert res["interp-polish-removes-oxide"]["level"] == "moderate"
    assert res["alt-handling-raises-shine"]["level"] == "ruled-out"
    assert res["pred-polished-shinier"]["level"] == "confirmed"
    print("ok  warrant rule: strong finding, moderate control, ruled-out rival, confirmed prediction")


def test_verification_check():
    by = {c["slug"]: c for c in load_paper(PAPER)}
    v, _ = vc.verdict(by["result-shine-delta"].get("reproductions") or [], {})
    assert v == "partial", v          # a verified record, not observed running
    v2, _ = vc.verdict(by["finding-polished-shinier"].get("reproductions") or [], {})
    assert v2 == "unrecorded", v2      # no reproduction record
    assert set(vc.VERDICTS) >= {v, v2}
    print("ok  verification-check: a recorded result reads partial, an unrecorded one unrecorded")


def test_linter_is_clean_and_flags_the_loose_synthesis():
    errors, _ = check_relations.check(PAPER)
    assert errors == [], errors
    # once modules has written its output, the loose list is echoed as warnings
    full, _ = modules.build(PAPER)
    modules._write(os.path.join(STUDY, "runs", PAPER, "modules.json"), full)
    _errs, warnings = check_relations.check(PAPER)
    assert any("loose-synth-widgets-improvable" in w and "no outgoing argument edge" in w
               for w in warnings), warnings
    assert any("loose after `modules`" in w for w in warnings), warnings
    print("ok  linter: zero errors, the loose synthesis warned before and after modules runs")


def _run():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nall canon toy-study tests passed")


if __name__ == "__main__":
    _run()
