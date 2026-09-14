"""No runner may derive a corpus path from its own location.

The machinery and the graph were one directory before the split, so `os.path.dirname(
os.path.dirname(os.path.abspath(__file__)))` meant both and every script said it. They are two
repositories now, that expression means the machinery, and most of what these scripts touch —
runs/, claims/, review/, verification/, site/ — belongs to the graph.

The failure is quiet, which is why it needs a test rather than care. A corpus build wrote
review/prediction-outcome.json into the machinery checkout; someone saw an untracked file in
their working tree and committed it; a public repository acquired 47 rows of claim text from
twelve named papers (#50, cleaned up in #43). Reading the wrong root is the same defect
mirrored (#42).

No network, no corpus. Runs standalone or under pytest.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

# The exact header that caused #50.
FROM_FILE = re.compile(
    r"^ROOT\s*=\s*os\.path\.dirname\(os\.path\.dirname\(os\.path\.abspath\(__file__\)\)\)",
    re.M)

# Modules whose ROOT must follow the graph. Every one of these reads or writes corpus paths.
GRAPH_ROOTED = ["agents_report", "apply_review", "audit_verifications", "evaluation_report",
                "prediction_outcome", "review_queue", "warrant", "trace",
                "export_mira", "formats_report", "validate_mira", "check_reproductions",
                "pipeline"]


def test_no_script_roots_itself_at_its_own_file():
    """`MACHINERY = ...__file__...` is correct and stays; `ROOT = ...__file__...` is the bug."""
    offenders = [p.name for p in sorted(SCRIPTS.glob("*.py"))
                 if FROM_FILE.search(p.read_text(encoding="utf-8"))]
    assert not offenders, (
        "these derive ROOT from their own location, so corpus paths resolve into the machinery "
        f"checkout (#50): {offenders}. Use `from roots import GRAPH as ROOT`."
    )


def test_the_graph_root_is_what_the_environment_names():
    """The property that matters, checked by running it rather than by reading it."""
    import importlib

    with tempfile.TemporaryDirectory() as d:
        elsewhere = str(Path(d).resolve())
        before = os.environ.get("CLAIM_GRAPHS_ROOT")
        os.environ["CLAIM_GRAPHS_ROOT"] = elsewhere
        try:
            import roots
            importlib.reload(roots)
            assert roots.GRAPH == elsewhere
            assert roots.MACHINERY != elsewhere, "the machinery is where the code is"

            for name in GRAPH_ROOTED:
                mod = importlib.import_module(name)
                importlib.reload(mod)
                root = getattr(mod, "ROOT", None)
                if root is None:
                    continue
                assert os.path.abspath(root) == elsewhere, (
                    f"{name}.ROOT is {root}, not the graph the environment names — "
                    "a corpus path built from it lands in the wrong checkout"
                )
        finally:
            if before is None:
                os.environ.pop("CLAIM_GRAPHS_ROOT", None)
            else:
                os.environ["CLAIM_GRAPHS_ROOT"] = before
            importlib.reload(importlib.import_module("roots"))


def test_the_machinery_is_still_reachable():
    """Splitting the roots must not strand the prompts and declarations that live here."""
    import roots
    assert Path(roots.machinery("pipeline", "layers.yaml")).is_file()
    assert Path(roots.machinery("extract", "prompts")).is_dir()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} passed")
