"""The skill and the machinery say the same thing.

What these pin is that the agent-facing skill cannot drift from what the CLI does. It already
had: the committed skill omitted `in-tension-with` after #125 added it, still called
`dissociates-with` an opposition after the same ruling moved it out, and offered an `epistemic`
value no claim file uses. Every one of those was a hand-copied enumeration.

So the enumerations are rendered, and these tests check three things: that the committed files
are what the sources generate, that every relation and rule reaches the agent, and that the
runbook names the layers the declaration actually has.

No LLM and no network. Runs under pytest or standalone.
"""

from __future__ import annotations

import functools
import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml

from claim_graphs import skill

REPO = Path(__file__).resolve().parents[2]

CORPUS = Path(os.environ.get("CLAIM_GRAPHS_CORPUS_DIR")
              or (Path(os.environ.get("CLAIM_GRAPHS_ROOT") or REPO) / "claims"))
HAVE_CORPUS = CORPUS.is_dir()
WHY_SKIPPED = (f"no corpus at {CORPUS}: the skill quotes real claim files, as the prompt "
               f"contract does. Set CLAIM_GRAPHS_CORPUS_DIR to a corpus checkout.")


def needs_corpus(fn):
    """Skip under pytest, and report rather than fail when run standalone."""
    @functools.wraps(fn)
    def wrapper(*a, **k):
        if not HAVE_CORPUS:
            print(f"SKIP  {fn.__name__}: {WHY_SKIPPED}")
            return
        return fn(*a, **k)
    try:
        import pytest
        return pytest.mark.skipif(not HAVE_CORPUS, reason=WHY_SKIPPED)(wrapper)
    except ImportError:
        return wrapper


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _committed(name: str) -> str:
    return (REPO / skill.SKILL_DIR / name).read_text(encoding="utf-8")


@needs_corpus
def test_committed_skill_is_what_its_sources_generate():
    stale = skill.check(REPO)
    assert not stale, (
        f"{', '.join(stale)} differ from what docs/skill/ and the declarations generate. "
        f"Run: cd extract && python3 -m claim_graphs.cli skill --write")


def test_every_file_is_committed():
    for name in skill.FILES:
        assert (REPO / skill.SKILL_DIR / name).is_file(), f"{name} is not committed"


def test_every_relation_reaches_the_agent():
    """The defect that started this: a relation in the vocabulary and not in the skill."""
    rel = _script("relations")
    text = _committed("references/relations.md")
    missing = [r for r in rel.EDGE_KEYS if f"`{r}`" not in text]
    assert not missing, f"relations the skill never names: {missing}"


def test_no_relation_the_vocabulary_does_not_have():
    import re
    rel = _script("relations")
    table = _committed("references/relations.md").split("## The six moves")[0]
    named = set(re.findall(r"^\| `([a-z-]+)`", table, re.M))
    assert named <= rel.EDGE_KEYS, f"skill names relations that do not exist: {named - rel.EDGE_KEYS}"


def test_every_enforced_rule_reaches_the_agent():
    chk = _script("check_relations")
    text = _committed("references/checks.md")
    missing = [rid for rid, _, _ in chk.RULES + chk.WARNS if rid not in text]
    assert not missing, f"rules the gate enforces and the skill never states: {missing}"


def test_runbook_names_the_declared_chain():
    """The sequence is the declaration's, not a remembered one."""
    declared = [ly["id"] for ly in skill._chain(REPO, "claim-tree")]
    text = _committed("workflows/analyze-paper.md")
    for lid in declared:
        assert f"`{lid}`" in text, f"{lid} is in the claim-tree chain and not in the runbook"
    layers = yaml.safe_load((REPO / "pipeline" / "layers.yaml").read_text(encoding="utf-8"))
    ids = {ly["id"] for ly in layers["layers"]}
    import re
    named = set(re.findall(r"^\| \d+ \| `([a-z-]+)`", text, re.M))
    assert named <= ids, f"runbook names layers that do not exist: {named - ids}"


def test_closed_value_sets_agree_with_the_converter():
    """`epistemic` in the skill is the set the interchange converter accepts."""
    spec = importlib.util.spec_from_file_location(
        "to_claim_set", REPO / "schema" / "to_claim_set.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = _committed("SKILL.md")
    for v in mod.STRENGTH:
        assert f"`{v}`" in text, f"epistemic value {v} is accepted and not named in the skill"


def test_sources_declare_themselves_generated():
    for name in skill.FILES:
        src = (REPO / skill.SOURCE_DIR / name).read_text(encoding="utf-8")
        assert "{{generated-note}}" in src, f"docs/skill/{name} does not say it is rendered"


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
