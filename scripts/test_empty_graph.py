"""A bare graph — one paper directory, an index, no claim files — reports empty, never crashes.

The smallest thing a graph can be is `claims/<slug>/index.md` and nothing else: no `corpus.yaml`,
no claim files, no runs. A fresh user's first state. Every mechanical runner has to survive it,
and one did not — `check_relations.py` with no paper argument iterated `public_papers()`, which is
`None` when there is no manifest, and died with `TypeError: 'NoneType' object is not iterable`
(#70). The fix is the same one `export_mira` already made: no manifest means scan the claim
directories on disk.

The graph here carries no `corpus.yaml` on purpose — that is the case that broke — so `state`,
which lists the manifest's papers, is out of scope; it is tested where the manifest is.

No network, no corpus. Runs standalone or under pytest.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SLUG = "demo-2026-empty"
INDEX = """---
paper-slug: demo-2026-empty
title: "An empty demonstration paper"
doi: 10.1234/demo.2026.0001
---

## Abstract

A fresh graph with no claim files yet.
"""


def _bare_graph(d: str) -> str:
    paper = Path(d) / "claims" / SLUG
    paper.mkdir(parents=True)
    (paper / "index.md").write_text(INDEX, encoding="utf-8")
    return d


def _run(root: str, *args: str) -> tuple[int, str]:
    env = {**os.environ, "CLAIM_GRAPHS_ROOT": root}
    env.pop("CLAIM_GRAPHS_CORPUS_DIR", None)
    p = subprocess.run([sys.executable, str(SCRIPTS / args[0]), *args[1:]],
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stdout + p.stderr


def test_no_mechanical_script_crashes_on_a_bare_graph():
    """Each reports empty and exits clean; none raises. `check_relations` with no argument is #70."""
    with tempfile.TemporaryDirectory() as d:
        root = _bare_graph(d)
        cases = [
            (("check_relations.py",), "0 error(s) across 1 paper(s)"),
            (("check_relations.py", SLUG), "0 error(s) across 1 paper(s)"),
            (("prediction_outcome.py",), "0 abstention"),
            (("prediction_outcome.py", "--write"), "0 abstention"),
            (("formats_report.py", SLUG), "0 relations"),
            (("warrant.py", SLUG), "0 claims"),
            (("audit_verifications.py",), "0 error(s)"),
        ]
        for args, needle in cases:
            rc, out = _run(root, *args)
            label = " ".join(args)
            assert "Traceback" not in out, f"{label} crashed:\n{out}"
            assert rc == 0, f"{label} exited {rc}:\n{out}"
            assert needle in out, f"{label} did not report empty ({needle!r} absent):\n{out}"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} passed")
