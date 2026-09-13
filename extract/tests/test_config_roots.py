"""Where a run writes, when the machinery and the graph are different checkouts.

`claims/` is what `claim-tree` declares it produces, and `produces:` resolves against the
graph root. If the writer resolves it somewhere else, the files and their provenance come
apart — which is not hypothetical twice over. The first time, `--root` lost to an exported
`CLAIM_GRAPHS_CORPUS_DIR` and a writer test's `claims/p/` was committed into the corpus. The
second time, the same hole in the environment form let a subagent run write 140 claim files
over a corpus and delete 31 committed ones, while the ledger recorded `out: []`.

No LLM and no network. Runs under pytest or standalone.
"""

from __future__ import annotations

import os
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claim_graphs.config import Config


def _args(**kw) -> Namespace:
    base = dict(root=None, corpus_dir=None, backend=None, profile=None)
    base.update(kw)
    return Namespace(**base)


def _clear(env: dict) -> None:
    for k in ("CLAIM_GRAPHS_ROOT", "CLAIM_GRAPHS_CORPUS_DIR"):
        env.pop(k, None)


def test_a_root_in_the_environment_beats_a_corpus_in_the_environment():
    """The bug: the root named in the environment, the corpus pointed elsewhere."""
    saved = dict(os.environ)
    try:
        with tempfile.TemporaryDirectory() as graph, tempfile.TemporaryDirectory() as other:
            _clear(os.environ)
            os.environ["CLAIM_GRAPHS_ROOT"] = graph
            os.environ["CLAIM_GRAPHS_CORPUS_DIR"] = other      # examples live elsewhere
            cfg = Config.from_args(_args())
            assert cfg.corpus_dir == Path(graph).resolve() / "claims", (
                "a named graph root must own claims/, or the writer and the ledger disagree")
    finally:
        os.environ.clear()
        os.environ.update(saved)


def test_a_root_flag_still_beats_a_corpus_in_the_environment():
    saved = dict(os.environ)
    try:
        with tempfile.TemporaryDirectory() as graph, tempfile.TemporaryDirectory() as other:
            _clear(os.environ)
            os.environ["CLAIM_GRAPHS_CORPUS_DIR"] = other
            cfg = Config.from_args(_args(root=graph))
            assert cfg.corpus_dir == Path(graph).resolve() / "claims"
    finally:
        os.environ.clear()
        os.environ.update(saved)


def test_an_explicit_corpus_dir_still_wins():
    """The one way to say it deliberately — reading someone else's corpus on purpose."""
    saved = dict(os.environ)
    try:
        with tempfile.TemporaryDirectory() as graph, tempfile.TemporaryDirectory() as other:
            _clear(os.environ)
            os.environ["CLAIM_GRAPHS_ROOT"] = graph
            cfg = Config.from_args(_args(corpus_dir=other))
            assert cfg.corpus_dir == Path(other).resolve()
    finally:
        os.environ.clear()
        os.environ.update(saved)


def test_the_environment_corpus_applies_when_no_root_is_named():
    """What the variable is for: worked examples, when nothing says where the graph is."""
    saved = dict(os.environ)
    try:
        with tempfile.TemporaryDirectory() as other:
            _clear(os.environ)
            os.environ["CLAIM_GRAPHS_CORPUS_DIR"] = other
            cfg = Config.from_args(_args())
            assert cfg.corpus_dir == Path(other).resolve()
    finally:
        os.environ.clear()
        os.environ.update(saved)


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL  {t.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")
    raise SystemExit(0 if passed == len(tests) else 1)
