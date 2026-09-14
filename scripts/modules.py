#!/usr/bin/env python3
"""Modules: a claim graph in two grains, derived from the edges and nothing else.

A claim tree atomizes a paper into dozens of claims; a module is the unit a reader holds in
mind above them. A module is one question under test: the question, the hypothesis the paper
commits to, the alternatives it raises to reject, the predictions the hypothesis entails, the
findings that test them or bear on the hypothesis directly, and the interpretation drawn. That
is the argument grain. Below it, a finding and the analysis results that bear on it are one
cluster -- the finding is a claim on the paper, its results are atoms with spans and panels and
are never claims on the paper. Scope sits beside the argument as the module's domain (what the
claims apply to) and apparatus (what they rest on). An observation is a finding that answers no
declared question. What is left is loose, which is a lint naming a missing edge, not a category.

The derivation is mechanical -- see docs/design/2026-09-14-modules.md, the six steps:

  1. Seed        every question opens a module; the hypotheses and alternatives that `addresses`
                 it are its core (an alternative is a hypothesis with stance rejects/entertains).
  2. Argument    from the core, outward over argument edges breadth-first so the nearest core
                 wins: a prediction by `entails` from a hypothesis; a finding by `tests`,
                 `confirms`, `refutes`, `supports` or `extends` at a hypothesis or prediction, or
                 `rules-out` at an alternative; an interpretation by `interprets`/`supports` at a
                 member; a claim by `in-tension-with`/`dissociates-with` a member.
  3. Finding     a claim reaching a placed finding, prediction, hypothesis or interpretation by
                 `part-of`, `validates`, `supports`, `extends`, `qualifies` or `in-tension-with`
                 is a result of it. Repeat to a fixed point, so a result of a result is placed.
  4. Scope       for every member, what it `requires`/is `enables-method` by is apparatus; what
                 `scopes` it is domain. A claim hanging off a scope claim by a detail edge hangs
                 there.
  5. Observation an unplaced empirical or control claim that is the whole of something (no
                 outgoing detail edge) opens an observation module; step 3 runs again for it.
  6. Loose       whatever remains, each with the edge it would take to place it.

There is no model call. It writes runs/<paper>/modules.json (the full structure, with the
member list and the per-claim owner and grain) and views/<paper>.modules.json (the nested view
the site reads). Both are idempotent and byte-stable, so the layer runs on every tree without a
prompt.

Usage:
  python3 scripts/modules.py                    # every public paper, --write the outputs
  python3 scripts/modules.py <paper-slug>
  python3 scripts/modules.py --report           # per-module counts, no write
  python3 scripts/modules.py --write            # (default when a paper is named)
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_mira import (CLAIMS_DIR, first_assertion, load_index_questions,  # noqa: E402
                         load_paper, public_papers, relations)
from roots import GRAPH as ROOT  # noqa: E402

# Argument edges pulling a claim inward, read as in-edges to a member (u -rel-> member).
_ARG_TEST = {"tests", "confirms", "refutes"}
_ARG_SUPPORT = {"supports", "extends"}
# Detail edges: a result hangs under a finding by one of these, directed result -> finding.
DETAIL = {"part-of", "validates", "supports", "extends", "qualifies", "in-tension-with"}
# What a detail edge contributes to the cluster's `combine` record.
COMBINE_KEY = {"validates": "validated_by", "supports": "supported_by", "extends": "supported_by",
               "part-of": "parts", "qualifies": "qualified_by", "in-tension-with": "in_tension_with"}
COMBINE_FIELDS = ("validated_by", "supported_by", "parts", "qualified_by", "in_tension_with")
APPARATUS = {"requires", "enables-method"}
SYMMETRIC = {"in-tension-with", "dissociates-with"}
ALT_STANCES = {"rejects", "entertains"}
INTERP_ROLES = {"interpretation", "synthesis"}


# ── the paper's claims and edges ────────────────────────────────────────────

def _stance(claim: dict) -> str:
    for a in (claim.get("assertions") or []):
        if isinstance(a, dict) and a.get("stance"):
            return a["stance"]
    return claim.get("stance") or "asserts"


def _panel(claim: dict):
    return first_assertion(claim).get("panel")


def load_addresses(paper: str, by_slug: dict) -> tuple[list[dict], dict]:
    """Questions the paper states and which claim addresses which.

    `addresses` on a hypothesis is missing from some claim files (elife #157), so it is read
    from both places it can live: the claim files' own `addresses:` field, and the latest
    `runs/<paper>/questions.answer.v<N>.json`. Questions come from `index.md` where the tree
    carries them, else from the same answer file.
    """
    questions = load_index_questions(paper)
    addresses: dict[str, str] = {}
    answers = sorted(glob.glob(os.path.join(ROOT, "runs", paper, "questions.answer.v*.json")),
                     key=lambda p: int(re.search(r"\.v(\d+)\.json$", p).group(1)))
    if answers:
        data = json.load(open(answers[-1], encoding="utf-8"))
        if not questions:
            questions = [q for q in (data.get("questions") or [])
                         if q.get("id") and q.get("text")]
        for slug, qid in (data.get("addresses") or {}).items():
            if slug in by_slug:
                addresses[slug] = qid
    for slug, c in by_slug.items():                 # claim files are authoritative where present
        a = c.get("addresses")
        if isinstance(a, str):
            addresses[slug] = a
        elif isinstance(a, list) and a:
            addresses[slug] = a[0]
    return questions, addresses


def derive(paper: str) -> dict:
    """The six steps, on one paper. Returns owner, grain, parents, scope and loose."""
    claims = load_paper(paper)
    by_slug = {c["slug"]: c for c in claims}
    role = lambda s: by_slug[s].get("role")
    is_alt = lambda s: role(s) == "hypothesis" and _stance(by_slug[s]) in ALT_STANCES

    out_e: dict[str, list] = collections.defaultdict(list)
    in_e: dict[str, list] = collections.defaultdict(list)
    for s, c in by_slug.items():
        for rel, tgt in relations(c):
            if tgt in by_slug:
                out_e[s].append((rel, tgt))
                in_e[tgt].append((rel, s))

    questions, addresses = load_addresses(paper, by_slug)
    owner: dict[str, str] = {}
    grain: dict[str, str] = {}

    # 1. seed
    for qid in [q["id"] for q in questions]:
        for s in sorted(addresses):
            if addresses[s] == qid and s not in owner:
                owner[s] = qid
                grain[s] = "alternative" if is_alt(s) else "hypothesis"

    # 2. argument grain, breadth-first (nearest core wins)
    frontier = sorted(owner)
    while frontier:
        nxt = []
        for s in frontier:
            g, qid = grain[s], owner[s]
            for rel, t in sorted(out_e[s]):
                if t in owner:
                    continue
                if rel == "entails" and g == "hypothesis" and role(t) == "prediction":
                    owner[t], grain[t] = qid, "prediction"
                    nxt.append(t)
                elif rel in SYMMETRIC:
                    owner[t] = qid
                    grain[t] = "interpretation" if role(t) in INTERP_ROLES else "finding"
                    nxt.append(t)
            for rel, u in sorted(in_e[s]):
                if u in owner:
                    continue
                joined = False
                if rel in _ARG_TEST and g in ("hypothesis", "prediction"):
                    grain[u], joined = "finding", True
                elif rel in _ARG_SUPPORT and g in ("hypothesis", "prediction"):
                    grain[u] = "interpretation" if role(u) in INTERP_ROLES else "finding"
                    joined = True
                elif rel == "rules-out" and g == "alternative":
                    grain[u], joined = "finding", True
                elif rel == "interprets":
                    grain[u], joined = "interpretation", True
                elif rel in SYMMETRIC:
                    grain[u] = "interpretation" if role(u) in INTERP_ROLES else "finding"
                    joined = True
                if joined:
                    owner[u] = qid
                    nxt.append(u)
        frontier = sorted(set(nxt))

    # 3. finding grain: results hang under a placed node by a detail edge, to a fixed point
    parent: dict[str, str] = {}
    parent_rel: dict[str, str] = {}

    def attach(hosts: set[str]):
        changed = True
        while changed:
            changed = False
            for s in sorted(by_slug):
                if s in owner:
                    continue
                for rel, t in sorted(out_e[s]):
                    if rel in DETAIL and t in owner and grain.get(t) in hosts:
                        owner[s], grain[s] = owner[t], "detail"
                        parent[s], parent_rel[s] = t, rel
                        changed = True
                        break

    attach({"finding", "detail", "interpretation", "hypothesis", "prediction"})

    # 4. scope: apparatus (requires / enables-method) and domain (scopes), per module
    scope = {m: {"domain": set(), "apparatus": set()} for m in set(owner.values())}
    scope_parent: dict[str, str] = {}
    scope_parent_rel: dict[str, str] = {}

    def collect_scope():
        for s in [x for x in owner if grain.get(x) != "detail"]:
            for rel, t in out_e[s]:
                if rel in APPARATUS:
                    half = "domain" if role(t) == "scope" else "apparatus"
                    scope[owner[s]][half].add(t)
                    scope_parent.setdefault(t, s)
                    scope_parent_rel.setdefault(t, rel)
            for rel, u in in_e[s]:
                if rel == "scopes":
                    scope[owner[s]]["domain"].add(u)
                    scope_parent.setdefault(u, s)
                    scope_parent_rel.setdefault(u, "scopes")

    collect_scope()
    scope_slugs = lambda: {x for m in scope.values() for x in m["domain"] | m["apparatus"]}
    # a claim hanging off a scope claim by a detail edge hangs there
    scope_detail: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        anchors = scope_slugs() | set(scope_detail)
        for s in sorted(by_slug):
            if s in owner or s in scope_detail:
                continue
            for rel, t in sorted(out_e[s]):
                if rel in DETAIL and t in anchors:
                    scope_detail[s] = t
                    changed = True
                    break

    # 5. observations: an unplaced empirical/control whole (no outgoing detail edge)
    observations: list[str] = []
    placed = lambda: set(owner) | scope_slugs() | set(scope_detail)
    for s in sorted(by_slug):
        if s in placed():
            continue
        if role(s) in ("empirical", "control") and not any(
                rel in DETAIL for rel, _ in out_e[s]):
            oid = f"o{len(observations) + 1}"
            owner[s], grain[s] = oid, "finding"
            scope[oid] = {"domain": set(), "apparatus": set()}
            observations.append(oid)
    attach({"finding", "detail"})
    collect_scope()

    # 6. loose: whatever remains, with the edge it would take to place it
    def loose_reason(s: str) -> str:
        r = role(s)
        if r in INTERP_ROLES:
            return ("synthesis with no outgoing argument edge; wants a `supports` to a "
                    "hypothesis, `rules-out` to an alternative, or `interprets` a member")
        if r == "methodological":
            return "apparatus claim wanting a `requires` or `enables-method` edge from the finding that rests on it"
        if r in ("empirical", "control"):
            return "result reaching no placed finding; wants a `requires`, `supports`, `validates` or `tests` edge"
        if r == "scope":
            return "scope claim bounding no member; wants a `scopes` edge"
        return "no argument or detail edge connects it to a module"

    loose = {s: loose_reason(s) for s in sorted(by_slug) if s not in placed()}

    return dict(paper=paper, claims=claims, by_slug=by_slug, questions=questions,
                addresses=addresses, owner=owner, grain=grain, parent=parent,
                parent_rel=parent_rel, scope=scope, scope_detail=scope_detail,
                scope_parent=scope_parent, scope_parent_rel=scope_parent_rel,
                observations=observations, loose=loose, out_e=out_e, in_e=in_e,
                role=role, is_alt=is_alt)


# ── assembly ────────────────────────────────────────────────────────────────

def _children(d: dict) -> dict:
    kids = collections.defaultdict(list)
    for s, p in d["parent"].items():
        kids[p].append(s)
    return kids


def _cluster(d: dict, finding: str, kids: dict) -> dict:
    """The finding and every result beneath it, with the `combine` record its warrant used."""
    results, stack = [], list(kids.get(finding, []))
    while stack:
        r = stack.pop()
        results.append(r)
        stack.extend(kids.get(r, []))
    combine = {k: [] for k in COMBINE_FIELDS}
    for r in kids.get(finding, []):                 # direct results only feed `combine`
        combine[COMBINE_KEY[d["parent_rel"][r]]].append(r)
    for k in combine:
        combine[k].sort()
    panels = sorted({p for p in [_panel(d["by_slug"][finding])]
                     + [_panel(d["by_slug"][r]) for r in results] if p})
    c = d["by_slug"][finding]
    return dict(finding=finding, warrant=c.get("warrant"),
                results=sorted(results), combine=combine, panels=panels)


def _node(d: dict, slug: str) -> dict:
    c = d["by_slug"][slug]
    return dict(slug=slug, role=c.get("role"), sentence=" ".join((c.get("claim") or "").split()),
                warrant=c.get("warrant"), check=c.get("check_verification"), panel=_panel(c))


def _view_cluster(d: dict, finding: str, kids: dict) -> dict:
    base = _cluster(d, finding, kids)
    return {**_node(d, finding), "warrant": d["by_slug"][finding].get("warrant"),
            "results": [_node(d, r) for r in base["results"]],
            "combine": base["combine"], "panels": base["panels"]}


def assemble(d: dict) -> tuple[list, list]:
    """The module objects for runs/ (slug lists) and views/ (nested nodes)."""
    kids = _children(d)
    owner, grain, in_e, role = d["owner"], d["grain"], d["in_e"], d["role"]
    members = lambda m: sorted(s for s in owner if owner[s] == m)
    of_grain = lambda m, g: sorted(s for s in owner if owner[s] == m and grain[s] == g)

    def outcome(p: str) -> str:
        rels = {rel for rel, _ in in_e[p]}
        return "confirmed" if "confirms" in rels else "refuted" if "refutes" in rels else "untested"

    def tests(p: str, m: str) -> list:
        return sorted(u for rel, u in in_e[p]
                      if rel in _ARG_TEST and owner.get(u) == m and grain.get(u) == "finding")

    def eliminated_by(a: str, m: str) -> list:
        return sorted(u for rel, u in in_e[a] if rel == "rules-out" and owner.get(u) == m)

    runs_mods, view_mods = [], []
    q_ids = [q["id"] for q in d["questions"]]
    q_text = {q["id"]: q["text"] for q in d["questions"]}
    for m in q_ids + d["observations"]:
        if m not in set(owner.values()):
            continue
        sc = d["scope"][m]
        domain, apparatus = sorted(sc["domain"]), sorted(sc["apparatus"])
        if m in q_ids:
            hyps, alts = of_grain(m, "hypothesis"), of_grain(m, "alternative")
            preds, interp = of_grain(m, "prediction"), of_grain(m, "interpretation")
            under_pred = {f for p in preds for f in tests(p, m)}
            direct = [f for f in of_grain(m, "finding") if f not in under_pred]
            head = d["by_slug"][hyps[0]] if hyps else None
            warrant = head.get("warrant") if head else None
            summary = " ".join((head.get("claim") or "").split()) if head else q_text[m]
            runs_mods.append(dict(
                id=m, kind="question", question=q_text[m], warrant=warrant, summary=summary,
                hypotheses=hyps,
                alternatives=[dict(slug=a, eliminated_by=eliminated_by(a, m)) for a in alts],
                predictions=[dict(prediction=p, outcome=outcome(p),
                                  findings=[_cluster(d, f, kids) for f in tests(p, m)])
                             for p in preds],
                findings=[_cluster(d, f, kids) for f in direct],
                interpretations=interp, domain=domain, apparatus=apparatus, members=members(m)))
            view_mods.append(dict(
                id=m, kind="question", question=q_text[m], warrant=warrant, summary=summary,
                hypotheses=[_node(d, h) for h in hyps],
                alternatives=[{**_node(d, a), "eliminated_by": eliminated_by(a, m)} for a in alts],
                predictions=[dict(**_node(d, p), outcome=outcome(p),
                                  findings=[_view_cluster(d, f, kids) for f in tests(p, m)])
                             for p in preds],
                findings=[_view_cluster(d, f, kids) for f in direct],
                interpretations=[_node(d, i) for i in interp],
                domain=[_node(d, s) for s in domain], apparatus=[_node(d, s) for s in apparatus]))
        else:
            f = of_grain(m, "finding")[0]
            head = d["by_slug"][f]
            summary = " ".join((head.get("claim") or "").split())
            runs_mods.append(dict(id=m, kind="observation", question=None,
                                  warrant=head.get("warrant"), summary=summary,
                                  finding=_cluster(d, f, kids), domain=domain,
                                  apparatus=apparatus, members=members(m)))
            view_mods.append(dict(id=m, kind="observation", question=None,
                                  warrant=head.get("warrant"), summary=summary,
                                  finding=_view_cluster(d, f, kids),
                                  domain=[_node(d, s) for s in domain],
                                  apparatus=[_node(d, s) for s in apparatus]))
    return runs_mods, view_mods


def build(paper: str) -> tuple[dict, dict]:
    d = derive(paper)
    runs_mods, view_mods = assemble(d)
    loose = [dict(slug=s, reason=r) for s, r in d["loose"].items()]
    full = dict(layer="modules", paper=paper, modules=runs_mods, loose=loose,
                owner=dict(sorted(d["owner"].items())),
                grain=dict(sorted(d["grain"].items())))
    view = dict(paper=paper, modules=view_mods,
                loose=[dict(slug=s, sentence=" ".join((d["by_slug"][s].get("claim") or "").split()),
                            reason=r) for s, r in d["loose"].items()])
    return full, view


# ── I/O ─────────────────────────────────────────────────────────────────────

def _write(path: str, data: dict) -> bool:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    old = open(path, encoding="utf-8").read() if os.path.isfile(path) else None
    if old == new:
        return False
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new)
    return True


def report(paper: str, full: dict) -> None:
    """Per-module counts, in clusters and results -- never claims (the results are atoms)."""
    n_clusters = n_results = 0
    print(f"\n{paper}")
    for m in full["modules"]:
        clusters = ([m["finding"]] if m["kind"] == "observation"
                    else m["findings"] + [f for p in m["predictions"] for f in p["findings"]])
        n_clusters += len(clusters)
        rr = sum(len(c["results"]) for c in clusters)
        n_results += rr
        placed = len(m["members"])
        if m["kind"] == "question":
            print(f"  [{m['id']}] {placed} members · H{len(m['hypotheses'])} "
                  f"A{len(m['alternatives'])} P{len(m['predictions'])} "
                  f"clusters={len(clusters)} results={rr} I{len(m['interpretations'])} "
                  f"domain={len(m['domain'])} apparatus={len(m['apparatus'])}")
        else:
            print(f"  [{m['id']}] observation · {m['finding']['finding']} "
                  f"results={len(m['finding']['results'])}")
    n_q = sum(1 for m in full["modules"] if m["kind"] == "question")
    n_o = sum(1 for m in full["modules"] if m["kind"] == "observation")
    scope_n = len({s for m in full["modules"] for s in
                   [x for x in (m.get("domain", []) + m.get("apparatus", []))]})
    placed = len(full["owner"])
    print(f"  → {n_q} question modules, {n_o} observations; {n_clusters} findings (clusters), "
          f"{n_results} results; {placed} claims in modules, {len(full['loose'])} loose")
    for it in full["loose"]:
        print(f"    loose  {it['slug']}: {it['reason']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paper", nargs="?")
    ap.add_argument("--write", action="store_true", help="write the two output files")
    ap.add_argument("--report", action="store_true", help="print per-module counts, write nothing")
    a = ap.parse_args()

    slugs = [a.paper] if a.paper else (public_papers() or [])
    do_write = a.write or (a.paper and not a.report)
    for paper in slugs:
        if not os.path.isdir(os.path.join(CLAIMS_DIR, paper)):
            print(f"  {paper}: no claim directory", file=sys.stderr)
            continue
        full, view = build(paper)
        if do_write:
            f1 = _write(os.path.join(ROOT, "runs", paper, "modules.json"), full)
            f2 = _write(os.path.join(ROOT, "views", f"{paper}.modules.json"), view)
            print(f"{paper}: runs/{paper}/modules.json {'updated' if f1 else 'unchanged'}, "
                  f"views/{paper}.modules.json {'updated' if f2 else 'unchanged'}")
        if a.report:
            report(paper, full)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
