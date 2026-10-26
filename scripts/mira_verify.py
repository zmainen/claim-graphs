#!/usr/bin/env python3
"""mira_verify — the checklist a MIRA working graph must pass before it goes to eLife.

Checks, per graph (the extractor's working-graph shape: nodes with id/type/text/description/anchor,
edges with relation/subject/object):
  shape        parses; every node has id, type, text; ids unique; types are MIRA's seven
  summaries    every Question, Claim and Request has a description of one or two sentences, with no
               editorial register ("Rival to…", "Argued against…", "Check." belong in `notes`)
  anchors      every node has an anchor found character-for-character in the given text
  evidence     every Evidence names a study (grounds edge) and a panel/section, and has a figure
               where its panel is a figure or table
  edges        every edge is one of MIRA's relations with legal endpoint types; no dangling ids
  structure    every Claim addresses a Question or is reached from one through supports/opposes;
               every Evidence supports or opposes something or is the observationStatement of a Claim
Writes <graph>.verification.json beside the graph: per-node and per-edge verdicts the viewer shows.

Usage: mira_verify.py <graph.json> <anchor-text.txt>
"""
import json, os, re, sys
from collections import Counter

TYPES = {"Question", "Claim", "Evidence", "Study", "Protocol", "SourceDocument", "Request"}
LEGAL = {"addresses": ({"Claim"}, {"Question"}), "supports": ({"Evidence", "Claim"}, {"Claim"}), "opposes": ({"Evidence", "Claim"}, {"Claim"}),
         "grounds": ({"Study"}, {"Evidence"}), "follows": ({"Study"}, {"Protocol"}), "describesActivity": ({"SourceDocument"}, {"Study"}),
         "request_target": ({"Request"}, {"Claim"}), "request_for": ({"Request"}, {"Study"}), "observationStatement": ({"Evidence"}, {"Claim"})}
EDITORIAL = re.compile(r"^(Rival|Check\b|Argued against|Alternative to|Raised by the authors|A limitation|Future work the Discussion|Cited finding|Manipulation check|Positive control|Assumption check|Model selection|Parameter recovery|Convergence)", re.I)

def sentences(s):
    return [x for x in re.split(r"(?<=[.!?])\s+", s.strip()) if x]

def main():
    gpath, tpath = sys.argv[1], sys.argv[2]
    g = json.load(open(gpath, encoding="utf-8")); text = open(tpath, encoding="utf-8").read()
    nodes, edges = g["nodes"], g["edges"]
    N = {n["id"]: n for n in nodes}
    verdict = {"nodes": {}, "edges": [], "summary": {}}
    problems = Counter()
    def flag(nid, check, ok, note=""):
        verdict["nodes"].setdefault(nid, {})[check] = {"ok": ok, "note": note}
        if not ok: problems[check] += 1
    dup = [k for k, c in Counter(n["id"] for n in nodes).items() if c > 1]
    grounds = {e["object"] for e in edges if e["relation"] == "grounds"}
    argued = {e["subject"] for e in edges if e["relation"] in ("supports", "opposes", "observationStatement")}
    addressed = {e["subject"] for e in edges if e["relation"] == "addresses"}
    reached = set(addressed)
    changed = True
    while changed:
        changed = False
        for e in edges:
            if e["relation"] in ("supports", "opposes") and e["object"] in reached and e["subject"] not in reached and N.get(e["subject"], {}).get("type") == "Claim":
                reached.add(e["subject"]); changed = True
    for n in nodes:
        nid = n["id"]
        flag(nid, "shape", bool(n.get("type") in TYPES and n.get("text")) and nid not in dup, "" if n.get("type") in TYPES else f"type {n.get('type')}")
        if n["type"] in ("Question", "Claim", "Request"):
            d = n.get("description", "")
            ns = len(sentences(d))
            ok = 1 <= ns <= 2 and not EDITORIAL.match(d)
            flag(nid, "summary", ok, "" if ok else ("missing" if not d else f"{ns} sentences" if ns > 2 else "editorial register"))
        a = n.get("anchor")
        flag(nid, "anchor", bool(a) and a in text, "" if a and a in text else ("missing" if not a else "not verbatim"))
        if n["type"] == "Evidence":
            ok = nid in grounds and bool(n.get("panel") or n.get("study"))
            flag(nid, "evidence", ok, "" if ok else ("no study" if nid not in grounds else "no panel"))
            if n.get("panel") and re.match(r"(Figure|Table) \d", n["panel"]):
                flag(nid, "figure", bool(n.get("figure")), "" if n.get("figure") else "panel named, no figure link")
        if n["type"] == "Claim":
            flag(nid, "structure", nid in reached, "" if nid in reached else "reaches no Question")
        if n["type"] == "Evidence":
            flag(nid, "structure", nid in argued, "" if nid in argued else "argues nothing")
    for e in edges:
        ok = e["relation"] in LEGAL and e["subject"] in N and e["object"] in N
        if ok:
            s, o = LEGAL[e["relation"]]
            ok = N[e["subject"]]["type"] in s and N[e["object"]]["type"] in o
        verdict["edges"].append({**e, "ok": ok})
        if not ok: problems["edges"] += 1
    verdict["summary"] = {"nodes": len(nodes), "edges": len(edges), "problems": dict(problems),
                          "passed": sum(1 for v in verdict["nodes"].values() if all(c["ok"] for c in v.values())),
                          "text_chars": len(text)}
    out = gpath.replace(".graph.json", ".verification.json")
    json.dump(verdict, open(out, "w"), indent=1)
    print(json.dumps(verdict["summary"]))
    for nid, v in verdict["nodes"].items():
        bad = [f"{c}: {r['note']}" for c, r in v.items() if not r["ok"]]
        if bad: print(f"  {nid:24} {'; '.join(bad)}")
    sys.exit(1 if problems else 0)

if __name__ == "__main__":
    main()
