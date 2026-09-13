"""One parser for a claim file's frontmatter, and a test that keeps it at one.

`claim_graphs.claimfile` exists because the same regex — `key:` with `[]` or `{}` at column 0
on the next line, which strict YAML rejects — had been written out by hand in eleven modules.
They did not stay identical. Three of them (`evaluate`, `verdicts`, `verify_refs`) carried a
variant that matched only `[]`, so a claim file with an empty *mapping* at column zero parsed
under eight readers and failed under three — and a claim that fails to parse is not reported,
it is skipped. That had already cost the project once: five of Gädeke's 27 claims were absent
from its OXA export, and they were the five carrying verification records.

Consolidating is only worth doing if it holds, so this asserts the property rather than the
count: no module outside `claimfile` may define its own frontmatter normaliser. A reader that
needs different behaviour should say so in `claimfile`, where the choice is visible.

No LLM and no network. Runs under pytest or standalone.
"""

from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CANONICAL = REPO / "extract" / "claim_graphs" / "claimfile.py"

# The defect, in every spelling it has been written in: a substitution over a key followed by
# a newline and a bare empty collection.
NORMALISER = re.compile(r"""re\.(?:sub|compile)\(\s*r?["'][^"']*\\n\s*\(?\\?\[""")

SKIP = {".git", "node_modules", "__pycache__", ".claude", "vendor", "site"}


def _sources():
    for p in REPO.rglob("*.py"):
        if SKIP & set(p.relative_to(REPO).parts):
            continue
        yield p


def test_only_claimfile_defines_the_normaliser():
    offenders = []
    for p in _sources():
        if p == CANONICAL:
            continue
        if NORMALISER.search(p.read_text(encoding="utf-8")):
            offenders.append(str(p.relative_to(REPO)))
    assert not offenders, (
        "these define their own frontmatter normaliser instead of using "
        "claim_graphs.claimfile: " + ", ".join(sorted(offenders)))


def test_the_canonical_one_handles_both_empty_collections():
    """The variant that diverged dropped `{}`. Both forms must survive a round trip."""
    sys.path.insert(0, str(REPO / "extract"))
    from claim_graphs import claimfile

    import yaml
    for empty, expected in (("[]", []), ("{}", {})):
        body = f"slug: a\nbelongings:\n{empty}\nrole: empirical"
        loaded = yaml.safe_load(claimfile.loadable(body))
        assert loaded["belongings"] == expected, f"{empty} did not survive: {loaded!r}"
        assert loaded["role"] == "empirical", "the rest of the block was lost"


def test_a_file_that_will_not_parse_is_None_not_an_exception():
    """`frontmatter` skips, `load` raises. Both contracts were deliberate; keep both."""
    import tempfile
    sys.path.insert(0, str(REPO / "extract"))
    from claim_graphs import claimfile

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.md"
        p.write_text("---\nslug: a\n  bad: [indent\n---\nbody\n", encoding="utf-8")
        assert claimfile.frontmatter(p) is None
        try:
            claimfile.load(p)
        except Exception:
            pass
        else:
            raise AssertionError("load() should raise on a file it cannot parse")


if __name__ == "__main__":
    tests = [test_only_claimfile_defines_the_normaliser,
             test_the_canonical_one_handles_both_empty_collections,
             test_a_file_that_will_not_parse_is_None_not_an_exception]
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
