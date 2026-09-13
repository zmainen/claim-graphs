"""Agent mode: one command, repeated, drives the chain.

`run` assumes a backend answers a model call. An agent answering the layers itself had to
perform a three-step loop per layer — dump, answer, record — described in prose and carried
out by hand: eighteen steps for one paper, each a chance to use the wrong path, skip a layer,
or answer two independent readers in one context.

What these pin is the protocol that replaces the prose: the caller repeats one command and
reads an exit code. 10 means a prompt is waiting, 11 means the answer was refused and should
be rewritten, 0 means the target is current. The layer list never reaches the caller.

`cmd_run` is stubbed here — it has its own tests, and what is under test is the loop around
it. Runs under pytest or standalone.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pipeline

DECL = """
version: 1
layers:
  - id: prepare
    kind: step
    scope: paper
    title: Prepared paper
    question: What text did the readers read?
    produces: ["runs/{paper}/prepared.json"]
    command: "true"
  - id: results-reader
    kind: candidate
    scope: paper
    title: Results reader
    question: What does the Results section assert?
    needs: [prepare]
    produces: ["runs/{paper}/results-reader.output.json"]
    command: "claim_graphs.cli results-reader"
    by_from: model
  - id: claim-tree
    kind: step
    scope: paper
    title: Claim tree
    question: What does this paper assert?
    needs: [results-reader]
    produces: ["claims/{paper}/*.md"]
    command: "true"
"""


class _Harness:
    """A graph root with a declaration, and a cmd_run that behaves like the real one."""

    def __init__(self, tmp: str):
        self.root = Path(tmp)
        (self.root / "pipeline").mkdir(parents=True, exist_ok=True)
        (self.root / "pipeline" / "layers.yaml").write_text(DECL, encoding="utf-8")
        (self.root / "corpus.yaml").write_text(
            "corpora:\n  t:\n    public: true\n    papers:\n      - p\n", encoding="utf-8")
        (self.root / "runs" / "p").mkdir(parents=True, exist_ok=True)
        (self.root / "runs" / "p" / "prepared.json").write_text("{}", encoding="utf-8")
        self.calls: list[tuple] = []
        self.refuse = False

    def cmd_run(self, args) -> int:
        if args.dump_prompt:
            Path(args.dump_prompt).parent.mkdir(parents=True, exist_ok=True)
            Path(args.dump_prompt).write_text("system\n\n---\n\nuser", encoding="utf-8")
            self.calls.append(("dump", args.layer))
            return 0
        if args.answer:
            self.calls.append(("record", args.layer, args.by, args.tokens))
            if self.refuse:
                return 1
            out = self.root / "runs" / "p" / f"{args.layer}.output.json"
            out.write_text("{}", encoding="utf-8")
            return 0
        self.calls.append(("run", args.layer))
        if args.layer == "claim-tree":
            d = self.root / "claims" / "p"
            d.mkdir(parents=True, exist_ok=True)
            (d / "c.md").write_text("---\n---\n", encoding="utf-8")
        return 0


def _agent(paper="p", layer="claim-tree", **kw) -> int:
    base = dict(paper=paper, layer=layer, by=None, tokens=None, note=None,
                profile=None, json=False)
    base.update(kw)
    return pipeline.cmd_agent(argparse.Namespace(**base))


def _with_harness(fn):
    """Run `fn(h)` with pipeline pointed at a temp graph and cmd_run stubbed."""
    saved = (pipeline.ROOT, pipeline.MACHINERY, pipeline.DECL, pipeline.cmd_run, pipeline.load)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            h = _Harness(tmp)
            pipeline.ROOT = pipeline.MACHINERY = str(h.root)
            stub = str(h.root / "pipeline" / "layers.yaml")
            pipeline.DECL = stub
            # `load()` binds DECL as a default argument at definition time, so reassigning the
            # module global does not reach it. Pin the path instead — the first version of this
            # test silently ran against the real declaration and reported failures that were
            # the harness's own.
            real_load = saved[4]
            pipeline.load = lambda path=None, _s=stub, _l=real_load: _l(_s)
            pipeline.cmd_run = h.cmd_run
            return fn(h)
    finally:
        (pipeline.ROOT, pipeline.MACHINERY, pipeline.DECL,
         pipeline.cmd_run, pipeline.load) = saved


def test_it_stops_at_the_first_layer_a_model_must_answer():
    def check(h):
        rc = _agent()
        assert rc == pipeline.AGENT_WAITING, rc
        prompt, answer, _ = pipeline._agent_paths("p", "results-reader")
        assert os.path.isfile(prompt), "the prompt is left on disk for whoever answers it"
        assert not os.path.exists(answer), "the answer is what the caller is being asked for"
        # It ran what needed no model first, and did not run what comes after.
        assert ("dump", "results-reader") in h.calls
        assert ("run", "claim-tree") not in h.calls
    _with_harness(check)


def test_an_answer_on_disk_is_recorded_and_the_chain_continues():
    def check(h):
        assert _agent() == pipeline.AGENT_WAITING
        _, answer, recorded = pipeline._agent_paths("p", "results-reader")
        Path(answer).write_text("[]", encoding="utf-8")

        assert _agent(by="a subagent", tokens=4200) == 0, "the target is reached"
        assert ("record", "results-reader", "a subagent", 4200) in h.calls, \
            "who answered and what it cost reach the ledger"
        assert ("run", "claim-tree") in h.calls
        assert not os.path.exists(answer) and os.path.isfile(recorded), \
            "a recorded answer is moved aside, or the next call records it twice"
    _with_harness(check)


def test_a_refused_answer_is_left_in_place_to_be_rewritten():
    def check(h):
        assert _agent() == pipeline.AGENT_WAITING
        _, answer, recorded = pipeline._agent_paths("p", "results-reader")
        Path(answer).write_text("not what the schema says", encoding="utf-8")
        h.refuse = True

        assert _agent() == pipeline.AGENT_REFUSED
        assert os.path.isfile(answer), "the caller rewrites this file; do not move it"
        assert not os.path.exists(recorded)
    _with_harness(check)


def test_json_mode_puts_only_json_on_stdout(capsys=None):
    """The machine contract: stdout parses, whatever the layers underneath print."""
    def check(h):
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _agent(json=True)
        assert rc == pipeline.AGENT_WAITING
        d = json.loads(buf.getvalue())
        assert d["status"] == "waiting"
        assert d["layer"] == "results-reader"
        assert d["question"] == "What does the Results section assert?"
        assert d["remaining"] == ["results-reader"]
        assert "independently" in d["independent"], "a reader says it must be read alone"
    _with_harness(check)


def test_the_readers_it_warns_about_are_the_ones_reconcile_reads():
    """`READER_LAYERS` is a claim about the real declaration, so check it against it."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(pipeline.__file__)))
    decl = pipeline.load(os.path.join(here, "pipeline", "layers.yaml"))
    needs = decl["by_id"]["reconcile"].get("needs") or []
    assert set(pipeline.READER_LAYERS) == set(needs), (
        f"reconcile reads {needs}; the independence warning names "
        f"{list(pipeline.READER_LAYERS)}")


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"ok   {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")
    raise SystemExit(0 if passed == len(tests) else 1)
