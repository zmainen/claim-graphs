"""`not_evidence`: a file the paper was bootstrapped with is not proof a layer ran.

`claim-tree` declares it produces `claims/{paper}/*.md`, and it does — including the paper's
`index.md`. But `index.md` is also what a new paper must be given *before* anything can run,
because it carries the `doi:` that `prepare` resolves. So the bootstrap file matched the
layer's own output glob, `state()` read the tree as an artifact that merely predates the
ledger, the agent walker treats that state as satisfied, and every layer between `prepare` and
the requested target was skipped without a word. Following the setup instructions put you in
it, and the run reported success.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pipeline  # noqa: E402

CORPUS = "corpora:\n  t:\n    public: true\n    papers:\n      - p\n"


def _graph(tmp: Path, claim_files: list[str]) -> Path:
    """A graph root holding one paper, with the named files under claims/p/."""
    (tmp / "claims" / "p").mkdir(parents=True, exist_ok=True)
    (tmp / "runs" / "p").mkdir(parents=True, exist_ok=True)
    (tmp / "corpus.yaml").write_text(CORPUS, encoding="utf-8")
    for name in claim_files:
        (tmp / "claims" / "p" / name).write_text("---\nslug: x\n---\n", encoding="utf-8")
    return tmp


def _claim_tree_state(tmp: Path) -> str:
    saved = pipeline.ROOT
    try:
        pipeline.ROOT = str(tmp)
        return pipeline.state(pipeline.load(), ["p"])["p"]["claim-tree"]["state"]
    finally:
        pipeline.ROOT = saved


def test_an_index_alone_is_not_a_claim_tree():
    """The bootstrap file every new paper needs must not read as the layer's output."""
    with tempfile.TemporaryDirectory() as d:
        state = _claim_tree_state(_graph(Path(d), ["index.md"]))
        assert state == pipeline.ABSENT, (
            f"claim-tree is {state!r} for a paper that has only its bootstrap index; "
            "the agent walker treats anything but `absent` as satisfied and skips the chain")


def test_a_claim_file_beside_it_still_counts():
    """A real tree predating the ledger keeps reporting `unrecorded`, as the corpus relies on."""
    with tempfile.TemporaryDirectory() as d:
        state = _claim_tree_state(_graph(Path(d), ["index.md", "some-claim.md"]))
        assert state == "unrecorded", f"expected unrecorded for a real tree, got {state!r}"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} passed")
