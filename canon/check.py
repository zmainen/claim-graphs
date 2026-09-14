"""`canon --check`: the entries are complete, the vocabulary resolves, the surfaces render.

The checks the note names, minus the ones that are their own standalone test (the per-layer toy
derivations are `scripts/test_canon.py`):

  1. every entry has every required field, or `enforced_by` says `not enforced`;
  2. every entry's toy example resolves into `canon/toy-study/`;
  3. every declared vocabulary term (relation, role, stance, verdict, warrant level, decision
     kind …) owns a canon entry, and every vocabulary token backticked in the method and the
     skill resolves to one — this is how a concept stops living in three places at once;
  4. the composed graph and the induced graph of the toy study agree at the argument grain;
  5. the existing contract and skill checks, folded in as cases (run only with a corpus).

Returns a list of problem strings; empty means clean.
"""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import yaml

from . import ROOT as CANON_ROOT, TOY_STUDY, TOY_PAPER
from .entries import entries as _registry, vocab as _vocab, ACCEPTED, PROPOSED

REPO = CANON_ROOT.parent

REQUIRED = ("definition", "signals", "distinct_from", "enforced_by", "example", "status",
            "governed_by", "glossary")

# Backticked tokens in prose that are not concepts: CLI verbs, file/format names, field keys.
NON_CONCEPT = {
    "status", "accepted", "proposed", "open", "issue", "needs", "reads", "produces", "views",
    "addresses", "belongings", "panel", "role", "claim-type", "claim_type", "source", "citation",
    "notes", "evidence", "sources", "uuid", "slug", "claim", "confidence", "readers", "epistemic",
    "check", "run", "state", "approve", "agent", "skeleton", "high", "tentative", "single-source",
    "make", "null", "true", "false", "views", "scope", "domain", "apparatus",
}


def _toy_claims() -> set[str]:
    d = TOY_STUDY / "claims" / TOY_PAPER
    return {p.stem for p in d.glob("*.md") if p.name != "index.md"}


def _example_ok(ref: str, slugs: set[str]) -> bool:
    ref = (ref or "").strip()
    if not ref:
        return False
    m = re.fullmatch(r"(\S+)\s+-\S+->\s+(\S+)", ref)      # an edge: src -rel-> tgt
    if m:
        return m.group(1) in slugs and m.group(2) in slugs
    if ref in slugs:                                       # a claim slug
        return True
    if ref.startswith("toy-study/"):                       # an artifact path
        return (REPO / "canon" / ref).exists()
    return False


def _vocab_terms() -> set[str]:
    v = _vocab
    terms = set(v.EDGE_KEYS) | {r["role"] for r in v.ROLES} | set(v.STANCES)
    terms |= {n for n, _ in v.CLAIM_TYPES}
    return terms


def _backticked(text: str) -> set[str]:
    return set(re.findall(r"`([a-z][a-z0-9-]+)`", text))


def _fold_surface_checks(problems: list[str]) -> None:
    """The contract and skill checks, as cases of the canon check (need a corpus)."""
    if not os.environ.get("CLAIM_GRAPHS_CORPUS_DIR"):
        return
    import sys
    sys.path.insert(0, str(REPO / "extract"))
    from claim_graphs import contract, skill
    for name in contract.check(REPO / "extract" / "prompts"):
        problems.append(f"contract surface stale: {name} (run `contract --write`)")
    for name in skill.check(REPO):
        problems.append(f"skill surface stale: {name} (run `skill --write`)")


def _schema_closed_sets(problems: list[str]) -> None:
    """The interchange schema's closed value sets are the canon's.

    `schema/to_claim_set.py` already reads the relation set from the canon (via `relations.py`);
    this holds the JSON schema's own enums to it too — the relation enum is exactly the canon's
    `EDGE_KEYS`, and the claim-type enum is the canon's claim types plus the one alias the
    exporter adds (`scope`, from the scope role's type). A drift here means a consumer validates
    against a vocabulary the machinery no longer speaks.
    """
    import json
    schema = json.loads((REPO / "schema" / "claim-set-v0.schema.json").read_text(encoding="utf-8"))
    rel_enum = set(schema["$defs"]["relation"].get("enum", []))
    if rel_enum != set(_vocab.EDGE_KEYS):
        problems.append(f"schema relation enum != canon EDGE_KEYS "
                        f"(only in schema: {sorted(rel_enum - set(_vocab.EDGE_KEYS))}; "
                        f"only in canon: {sorted(set(_vocab.EDGE_KEYS) - rel_enum)})")
    type_enum = set(schema["$defs"]["claim"]["properties"]["type"].get("enum", []))
    canon_types = {n for n, _ in _vocab.CLAIM_TYPES} | {"scope"}   # scope is to_claim_set's alias
    if type_enum != canon_types:
        problems.append(f"schema type enum != canon claim types + scope alias "
                        f"(only in schema: {sorted(type_enum - canon_types)}; "
                        f"only in canon: {sorted(canon_types - type_enum)})")


def induced_argument_grain() -> dict:
    """The toy study's derived question module, in a subprocess with the toy root.

    `modules.py` binds its graph root at import, so the derivation runs isolated from whatever
    corpus the surrounding `make check` has pointed the environment at.
    """
    import json
    import subprocess
    import sys
    code = (
        "import json,sys; sys.path.insert(0,'scripts'); import modules;"
        "full,_=modules.build('%s');"
        "print(json.dumps(next(m for m in full['modules'] if m['kind']=='question')))" % TOY_PAPER)
    env = dict(os.environ, CLAIM_GRAPHS_ROOT=str(TOY_STUDY),
               CLAIM_GRAPHS_CORPUS_DIR=str(TOY_STUDY / "claims"))
    out = subprocess.run([sys.executable, "-c", code], cwd=str(REPO), env=env,
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "modules build failed")
    return json.loads(out.stdout)


def _method_tracks_canon(problems: list[str]) -> None:
    """The method's relation and role tables name exactly the canon's vocabulary.

    `docs/method.md` is the definitions a person reads; a relation the canon has and the method
    omits is a definition the method silently lacks. The tables are token-filled from the same
    corpus facts, so this holds their *membership* to the canon rather than regenerating the prose.
    """
    method = REPO / "docs" / "method.md"
    if not method.is_file():
        return
    text = method.read_text(encoding="utf-8")
    rel_table = re.search(r"### 4\.3.*?### 4\.4", text, re.S)
    if rel_table:
        named = set(re.findall(r"^\| `([a-z-]+)` \|", rel_table.group(0), re.M))
        missing = set(_vocab.EDGE_KEYS) - named
        extra = named - set(_vocab.EDGE_KEYS)
        if missing:
            problems.append(f"method.md relation table omits canon relations: {sorted(missing)}")
        if extra:
            problems.append(f"method.md relation table names non-canon relations: {sorted(extra)}")


def _composed_induced_agree(problems: list[str]) -> None:
    """The toy study's composed argument grain equals the induced derivation (no corpus needed)."""
    composed = yaml.safe_load((TOY_STUDY / "composed.yaml").read_text(encoding="utf-8"))
    try:
        q = induced_argument_grain()
    except RuntimeError as e:
        problems.append(f"composed==induced: could not derive the toy modules — {e}")
        return
    if q.get("id") != composed["module"]:
        problems.append(f"composed==induced: derived module {q.get('id')} != {composed['module']}")
    if q is None:
        problems.append(f"composed==induced: module {composed['module']} not derived")
        return
    if sorted(q["hypotheses"]) != sorted(composed["hypotheses"]):
        problems.append(f"composed==induced: hypotheses {q['hypotheses']} != "
                        f"{composed['hypotheses']}")
    got_alts = {a["slug"]: sorted(a["eliminated_by"]) for a in q["alternatives"]}
    want_alts = {a["slug"]: sorted(a["eliminated_by"]) for a in composed["alternatives"]}
    if got_alts != want_alts:
        problems.append(f"composed==induced: alternatives {got_alts} != {want_alts}")
    got_preds = {p["prediction"]: p["outcome"] for p in q["predictions"]}
    want_preds = {p["prediction"]: p["outcome"] for p in composed["predictions"]}
    if got_preds != want_preds:
        problems.append(f"composed==induced: predictions {got_preds} != {want_preds}")
    for half in ("domain", "apparatus"):
        if sorted(q[half]) != sorted(composed[half]):
            problems.append(f"composed==induced: {half} {q[half]} != {composed[half]}")


def check() -> list[str]:
    problems: list[str] = []
    reg = _registry()
    slugs = _toy_claims()

    # 1. completeness
    for eid, e in reg.items():
        for f in REQUIRED:
            if f not in e or e[f] in (None, "", [], {}):
                problems.append(f"{eid}: missing field `{f}`")
        if e.get("status") not in (ACCEPTED, PROPOSED):
            problems.append(f"{eid}: status {e.get('status')!r} not accepted/proposed")
        # 2. example resolves
        exj = e.get("example") or {}
        if not _example_ok(exj.get("ref", ""), slugs):
            problems.append(f"{eid}: example ref {exj.get('ref')!r} does not resolve into the toy "
                            f"study")

    # 3. every declared vocabulary term owns an entry
    glossary = {g for e in reg.values() for g in e.get("glossary", [])}
    for term in _vocab_terms():
        if term not in glossary:
            problems.append(f"vocabulary term `{term}` resolves to no canon entry")

    # 3b. vocabulary tokens backticked in the method and the skill resolve to an entry
    for rel in (REPO / "docs" / "method.md", REPO / "skills" / "claim-structures" / "SKILL.md"):
        if not rel.is_file():
            continue
        for tok in _backticked(rel.read_text(encoding="utf-8")):
            if tok in NON_CONCEPT or tok in slugs:
                continue
            if tok in _vocab_terms() and tok not in glossary:
                problems.append(f"{rel.name}: `{tok}` is a vocabulary term with no canon entry")

    # 4. composed == induced
    _composed_induced_agree(problems)

    # 5. the contract and skill surfaces, folded in
    _fold_surface_checks(problems)

    # 5b. the interchange schema's closed value sets are the canon's
    _schema_closed_sets(problems)

    # 5c. the method's definition tables name exactly the canon's vocabulary
    _method_tracks_canon(problems)

    # 6. the committed page is the rendered one
    from . import page as _page
    problems += _page.check()

    return problems
