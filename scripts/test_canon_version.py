#!/usr/bin/env python3
"""Canon versioning and the page: the content digest, the ledger stamp, the concept approval.

Standalone — builds a throwaway graph root under a temp dir, needs no corpus and no model, and
writes nothing into the repository.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))      # REPO first, so `canon` is the package, not scripts/canon.py

import canon                       # noqa: E402
import pipeline                    # noqa: E402


def test_canon_version_is_a_stable_digest():
    a, b = canon.canon_version(), canon.canon_version()
    assert a == b and len(a) == 12, a
    print("ok  canon_version is a stable 12-char digest")


def test_entry_version_changes_with_the_entry():
    v1 = pipeline._canon_entry_version("warrant")
    assert v1 and len(v1) == 12
    assert pipeline._canon_entry_version("nonesuch") is None
    print("ok  per-entry version is defined for a concept, absent for a non-concept")


def test_run_record_carries_the_canon_version():
    # a minimal layer with nothing to read or produce still stamps the canon it ran under
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["CLAIM_GRAPHS_ROOT"] = tmp
        # record() reads the ledger under ROOT; ROOT is read at import, so patch the module global
        pipeline.ROOT = tmp
        layer = {"id": "toy-layer", "kind": "feature"}
        rec = pipeline.record("toy-paper", layer, {"toy-layer": layer}, note="", by="tester")
        assert rec.get("canon") == canon.canon_version(), rec
    print("ok  a run record stamps canon: <version>")


def test_approve_declaration_canon_and_status_overlay():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "runs").mkdir()
        env = dict(os.environ, CLAIM_GRAPHS_ROOT=tmp)
        out = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "pipeline.py"), "approve",
             "--declaration", "canon/warrant", "--by", "Tester", "--note", "fixture"],
            capture_output=True, text=True, env=env, cwd=str(REPO))
        assert out.returncode == 0, out.stderr
        rec = json.loads((Path(tmp) / "runs" / "approvals.jsonl").read_text().strip())
        assert rec["declaration"] == "canon/warrant"
        assert rec["version"] == pipeline._canon_entry_version("warrant")
        status = canon.corpus_status(root=tmp)
        assert status["warrant"] == "accepted", status["warrant"]
        assert status["result"] == "proposed"       # a concept nobody approved is unchanged
    print("ok  approve --declaration canon/warrant records the ruling and flips its status")


def test_page_renders_and_check_is_stable():
    from canon import page
    html = page.render()
    assert "<title>The Canon</title>" in html and "canon version</b>" in html
    assert page.check() == [], "committed docs/canon.html is not the rendered one"
    # corpus-free render is deterministic regardless of a stray corpus env
    os.environ.pop("CLAIM_GRAPHS_CORPUS_DIR", None)
    assert page.render() == html
    print("ok  the page renders in-register and the committed page equals it")


def _run():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nall canon versioning tests passed")


if __name__ == "__main__":
    _run()
