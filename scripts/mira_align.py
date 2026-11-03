#!/usr/bin/env python3
"""mira_align — align two MIRA working graphs of the same paper, for the viewer's compare tab.

Claims, questions, requests and protocols are aligned by a hand-written map (they are judgements
of meaning). Evidence is aligned automatically by the statistics the two items quote: two nodes
that share two or more numbers (t, p, d, β, voxel counts…) report the same result. The output is
one file the viewer embeds: for every node on either side, its counterpart on the other, if any.

Usage: mira_align.py <ours.graph.json> <theirs.graph.json> <hand-map.json> [--out alignment.json]
hand-map.json: {"claims": {"theirId": "ourId", ...}, "questions": {...}, "requests": {...}, "protocols": {...}}
"""
import json, re, sys

def nums(s):
    return set(re.findall(r"\d+\.\d+|\d{2,}", s))

def main():
    a = sys.argv[1:]
    ours, theirs, hand = (json.load(open(p, encoding="utf-8")) for p in a[:3])
    out = a[a.index("--out") + 1] if "--out" in a else "alignment.json"
    O = {n["id"]: n for n in ours["nodes"]}; T = {n["id"]: n for n in theirs["nodes"]}
    KEY = {n.get("key", n["id"]): n["id"] for n in ours["nodes"]}   # the hand map may use a node's `key` (its mnemonic)
    pairs = {}   # theirId -> ourId
    for section in ("claims", "questions", "requests", "protocols", "studies", "sources"):
        for t, o in (hand.get(section) or {}).items():
            o = KEY.get(o, o)
            if t in T and o in O: pairs[t] = o
    oev = [n for n in ours["nodes"] if n["type"] == "Evidence"]
    for t in [n for n in theirs["nodes"] if n["type"] == "Evidence"]:
        best = max(oev, key=lambda o: len(nums(t["text"]) & nums(o["text"])), default=None)
        if best and len(nums(t["text"]) & nums(best["text"])) >= 2:
            pairs[t["id"]] = best["id"]
    inv = {}
    for t, o in pairs.items(): inv.setdefault(o, []).append(t)
    align = {"theirs_to_ours": pairs, "ours_to_theirs": inv,
             "summary": {"theirs": len(T), "ours": len(O), "matched_theirs": len(pairs), "ours_with_counterpart": len(inv)}}
    json.dump(align, open(out, "w"), indent=1)
    print(json.dumps(align["summary"]))
    for t in theirs["nodes"]:
        if t["id"] not in pairs: print(f"  theirs only: {t['type']:14} {t['id']:5} {t['text'][:80]}")

if __name__ == "__main__":
    main()
