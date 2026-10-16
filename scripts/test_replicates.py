"""Replicates are peers, not versions — and the report must not pool two models.

A version supersedes: v2 is the better answer and v1 is history. Replicates are N draws from
one distribution, none superseding another, so they are kept apart from the version counter
and from the ledger. Pooling samples from two models would report their disagreement with each
other as one model's disagreement with itself, which is the only number this measures.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _run(root: Path, *argv: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAIM_GRAPHS_ROOT": str(root)}
    return subprocess.run([sys.executable, str(HERE / "replicates.py"), *argv],
                          capture_output=True, text=True, env=env)


def _answer(tmp: Path, name: str, claims: list[str]) -> Path:
    p = tmp / name
    p.write_text(json.dumps([{"claim": c, "role": "empirical"} for c in claims]),
                 encoding="utf-8")
    return p


def test_samples_are_numbered_and_kept_apart_from_versions():
    with tempfile.TemporaryDirectory() as d:
        root, tmp = Path(d) / "graph", Path(d)
        a = _answer(tmp, "a.json", ["tuning width narrowed", "bursts sharpened tuning"])
        assert _run(root, "record", "p", "results-reader", str(a), "--by", "m").returncode == 0
        assert _run(root, "record", "p", "results-reader", str(a), "--by", "m").returncode == 0
        d2 = root / "runs" / "p" / "replicates" / "results-reader"
        assert (d2 / "r1.output.json").is_file() and (d2 / "r2.output.json").is_file()
        # the canonical output and the ledger are untouched: nothing downstream sees these
        assert not (root / "runs" / "p" / "results-reader.output.json").exists()
        assert not (root / "runs" / "p" / "ledger.jsonl").exists()


def test_a_model_is_not_compared_against_a_different_model():
    with tempfile.TemporaryDirectory() as d:
        root, tmp = Path(d) / "graph", Path(d)
        same = ["alpha rose", "beta fell"]
        other = ["gamma drifted", "delta held"]
        for _ in range(2):
            _run(root, "record", "p", "results-reader", str(_answer(tmp, "x.json", same)),
                 "--by", "model-one")
        for _ in range(2):
            _run(root, "record", "p", "results-reader", str(_answer(tmp, "y.json", other)),
                 "--by", "model-two")
        out = _run(root, "report", "p", "results-reader").stdout
        assert "2 answering model(s)" in out
        # each model agrees perfectly with itself; pooled, they would agree not at all
        assert out.count("self-agreement: mean 1.00") == 2, out


def test_reporting_nothing_is_an_error_not_an_empty_success():
    with tempfile.TemporaryDirectory() as d:
        r = _run(Path(d) / "graph", "report", "p", "results-reader")
        assert r.returncode == 2 and "no replicates" in r.stderr


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} passed")
