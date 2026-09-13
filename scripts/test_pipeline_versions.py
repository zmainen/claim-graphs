"""A run keeps a versioned copy of each single file it produced under runs/.

The site's two-version comparison reads an earlier version's bytes from `<name>.v<N>.<ext>`
beside the current output. `pipeline.keep_versions` is what writes those copies, and this pins
its contract: single files under `runs/` are copied to the version the run recorded, and
nothing else is — a path outside `runs/`, a glob, or a directory is left alone, and no version
is backfilled.

Runs under pytest (``pytest scripts/test_pipeline_versions.py``) or standalone
(``python3 scripts/test_pipeline_versions.py``).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pipeline


def _touch(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_keep_versions_copies_runs_single_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _touch(root, "runs/p/reconciler.output.json", '{"v": 2}')
        _touch(root, "runs/p/edge-inference.output.json", "[]")
        rec = {
            "v": 2,
            "out": [
                {"path": "runs/p/reconciler.output.json"},
                {"path": "runs/p/edge-inference.output.json"},
            ],
        }
        made = pipeline.keep_versions(rec, root=str(root))

        assert set(made) == {
            "runs/p/reconciler.output.v2.json",
            "runs/p/edge-inference.output.v2.json",
        }
        # The copy is beside the current output, carries the run's version, and is byte-equal.
        kept = root / "runs/p/reconciler.output.v2.json"
        assert kept.is_file()
        assert kept.read_text(encoding="utf-8") == '{"v": 2}'
        # The layer's own output path is untouched — everything downstream reads it.
        assert (root / "runs/p/reconciler.output.json").is_file()


def test_the_two_roots_resolve_separately():
    """A declared path goes to the checkout that owns it — #6.

    Before the split this was one root and the question did not arise. After it, a layer's
    `reads:` (prompts, scripts) is in the machinery checkout and its `produces:` (runs, claims)
    is in the graph's, and resolving both against one root is how the runner became unable to
    touch a graph anywhere else.
    """
    old, old_m = pipeline.ROOT, pipeline.MACHINERY
    try:
        with tempfile.TemporaryDirectory() as mach, tempfile.TemporaryDirectory() as graph:
            pipeline.MACHINERY, pipeline.ROOT = mach, graph

            assert pipeline.where("scripts/relations.py").startswith(mach)
            assert pipeline.where("extract/prompts/contract/vocabulary.md").startswith(mach)
            assert pipeline.where("runs/p/ledger.jsonl").startswith(graph)
            assert pipeline.where("claims/p/index.md").startswith(graph)
            assert pipeline.where("coverage/p.json").startswith(graph)

            # And each is hashed where it lives, not where the other one is.
            _touch(Path(mach), "scripts/relations.py", "EDGE_KEYS = ['supports']\n")
            _touch(Path(graph), "runs/p/out.json", "{}")
            assert pipeline.digest("scripts/relations.py") is not None
            assert pipeline.digest("runs/p/out.json") is not None
            # A decoy at the same relative path under the graph root does not shadow it.
            before = pipeline.digest("scripts/relations.py")
            _touch(Path(graph), "scripts/relations.py", "decoy\n")
            assert pipeline.digest("scripts/relations.py") == before

            # A machinery checkout with no graph beside it has no papers, and does not raise.
            assert pipeline.papers() == []
    finally:
        pipeline.ROOT, pipeline.MACHINERY = old, old_m


def _decl(root: Path):
    """A tiny two-layer declaration under `root`, with its reads on disk, loaded with
    pipeline pointed at `root` so digests and the corpus ledger resolve there."""
    _touch(root, "scripts/relations.py", "EDGE_KEYS = ['supports']\n")
    (root / "pipeline").mkdir(parents=True, exist_ok=True)
    (root / "pipeline" / "layers.yaml").write_text(
        "version: 1\n"
        "layers:\n"
        "  - id: claim-format\n"
        "    kind: feature\n"
        "    scope: corpus\n"
        "    reads: []\n"
        "  - id: relation-vocab\n"
        "    kind: question\n"
        "    scope: corpus\n"
        "    needs: [claim-format]\n"
        "    reads: [scripts/relations.py]\n"
        "  - id: claim-tree\n"
        "    kind: step\n"
        "    scope: paper\n"
        "    needs: [relation-vocab]\n"
        "    produces: ['claims/{paper}/*.md']\n",
        encoding="utf-8")
    # Both roots: this fixture is the single-repository layout, where the machinery and the
    # graph are one directory. `scripts/relations.py` is a machinery read and `claims/` a graph
    # produce, so pointing only one of them at the temp tree would resolve the pair in two
    # different places.
    pipeline.ROOT = pipeline.MACHINERY = str(root)
    return pipeline.load(str(root / "pipeline" / "layers.yaml"))


def test_declaration_version_is_a_function_of_entry_and_reads():
    old, old_m = pipeline.ROOT, pipeline.MACHINERY
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            decl = _decl(root)
            rv = decl["by_id"]["relation-vocab"]
            v1 = pipeline.declaration_version(rv)
            assert v1 == pipeline.declaration_version(rv)          # deterministic
            # A read file it names moves the version — the same machinery staleness uses.
            _touch(root, "scripts/relations.py", "EDGE_KEYS = ['supports', 'tests']\n")
            assert pipeline.declaration_version(rv) != v1
    finally:
        pipeline.ROOT, pipeline.MACHINERY = old, old_m


def test_declaration_state_open_accepted_superseded():
    old, old_m = pipeline.ROOT, pipeline.MACHINERY
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            decl = _decl(root)
            rv = decl["by_id"]["relation-vocab"]

            # Never approved → open, and claim-tree is provisional on the corpus decisions.
            ds = pipeline.declaration_state(decl)
            assert ds["relation-vocab"]["scheme"] == "open"
            assert ds["claim-tree"].get("provisional_on") == ["claim-format", "relation-vocab"]

            # Approve claim-format and the current relation-vocab version → accepted.
            pipeline.approve_declaration("claim-format",
                                         pipeline.declaration_version(decl["by_id"]["claim-format"]),
                                         by="curator")
            ver = pipeline.declaration_version(rv)
            pipeline.approve_declaration("relation-vocab", ver, by="curator", note="ruled")
            ds = pipeline.declaration_state(decl)
            assert ds["relation-vocab"]["scheme"] == "accepted"
            assert ds["relation-vocab"]["approved"]["by"] == "curator"
            # claim-tree now waits on nothing — both corpus deps are accepted.
            assert "provisional_on" not in ds["claim-tree"]

            # Move the declaration past what was accepted → proposed, marked superseded.
            _touch(root, "scripts/relations.py", "EDGE_KEYS = ['supports', 'opposes']\n")
            ds = pipeline.declaration_state(decl)
            assert ds["relation-vocab"]["scheme"] == "proposed"
            assert ds["relation-vocab"]["approved"]["superseded"] is True
            # And claim-tree is provisional again, on relation-vocab alone.
            assert ds["claim-tree"].get("provisional_on") == ["relation-vocab"]

            # The ruling is one line in the corpus-level ledger, in the approval shape.
            recs = pipeline.read_corpus_approvals()
            assert [r["declaration"] for r in recs] == ["claim-format", "relation-vocab"]
            assert recs[1]["version"] == ver and recs[1]["note"] == "ruled"
    finally:
        pipeline.ROOT, pipeline.MACHINERY = old, old_m


def test_status_proposed_reads_as_proposed_until_accepted():
    old, old_m = pipeline.ROOT, pipeline.MACHINERY
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            decl = _decl(root)
            decl["by_id"]["relation-vocab"]["status"] = "proposed"
            ds = pipeline.declaration_state(decl)
            assert ds["relation-vocab"]["scheme"] == "proposed"
            pipeline.approve_declaration("relation-vocab",
                                         pipeline.declaration_version(decl["by_id"]["relation-vocab"]),
                                         by="curator")
            assert pipeline.declaration_state(decl)["relation-vocab"]["scheme"] == "accepted"
    finally:
        pipeline.ROOT, pipeline.MACHINERY = old, old_m


def test_keep_versions_ignores_non_runs_globs_and_missing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _touch(root, "claims/p/a-claim.md", "---\n---\n")          # not under runs/
        _touch(root, "runs/p/questions.output.json", "{}")          # a real runs/ file
        rec = {
            "v": 1,
            "out": [
                {"path": "claims/p/a-claim.md"},                    # outside runs/: skip
                {"path": "runs/p/claim-tree.v1/*.md"},              # a glob: skip
                {"path": "runs/p/never-written.output.json"},       # absent: skip
                {"path": "runs/p/questions.output.json"},           # kept
            ],
        }
        made = pipeline.keep_versions(rec, root=str(root))

        assert made == ["runs/p/questions.output.v1.json"]
        assert not (root / "claims/p/a-claim.v1.md").exists()
        assert not (root / "runs/p/never-written.output.v1.json").exists()



# ── which machinery ran (issue #2) ────────────────────────────────────────────


def test_a_record_names_the_machinery_that_ran_it():
    """Without this a dependency upgrade leaves every cell reporting `current` when the code
    that produced it has been replaced — the one thing the ledger exists to prevent."""
    stamp = pipeline.machinery_stamp()
    assert stamp.get("version"), "a record should name the package version"
    assert stamp.get("contract"), "and the rendered prompt contract it was run with"
    assert len(stamp["contract"]) == 12


def test_the_contract_hash_follows_the_words_the_model_is_sent():
    """The version is what a reader cites; the contract hash is what changes what a model was
    told. A contract edit under an unchanged version has happened, and must not read as current.
    """
    import pathlib
    before = pipeline.machinery_stamp()["contract"]
    target = pathlib.Path(pipeline.CONTRACT_DIR) / "vocabulary.md"
    original = target.read_text(encoding="utf-8")
    try:
        target.write_text(original + "\n<!-- a word the model would now be sent -->\n",
                          encoding="utf-8")
        assert pipeline.machinery_stamp()["contract"] != before
    finally:
        target.write_text(original, encoding="utf-8")
    assert pipeline.machinery_stamp()["contract"] == before


def test_drift_is_silent_for_a_record_that_cannot_say():
    """A record written before the field existed says nothing about its machinery. Silence is
    not agreement, but it is not disagreement either — calling every historical record stale
    would be a worse answer than admitting the record cannot say. Those surface through the
    absent-input path instead, which is honest: the file they named is genuinely not there."""
    assert pipeline.machinery_drift({"layer": "x", "in": []}) == []
    assert pipeline.machinery_drift({"machinery": pipeline.machinery_stamp()}) == []
    drift = pipeline.machinery_drift({"machinery": {"version": "0.0.9", "contract": "0" * 12}})
    assert len(drift) == 2 and any("0.0.9" in d for d in drift)


def test_a_machinery_path_and_a_graph_path_are_told_apart():
    """The three causes call for different actions, so they are not one list. A machinery file
    that changed means re-run and the answer may be identical; a changed claim file does not."""
    assert pipeline.base_of("claims/p/x.md") == pipeline.ROOT
    assert pipeline.base_of("runs/p/prepared.json") == pipeline.ROOT
    assert pipeline.base_of("scripts/export_mira.py") == pipeline.MACHINERY
    assert pipeline.base_of("extract/prompts/results-reader.md") == pipeline.MACHINERY


def _run():
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as e:                              # noqa: PERF203
                fails += 1
                print(f"FAIL {name}: {e}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(_run())
