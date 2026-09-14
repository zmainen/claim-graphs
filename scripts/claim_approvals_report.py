#!/usr/bin/env python3
"""Resolve each paper's claim approvals into one file the site can read.

The site cannot answer "does this approval still stand" on its own: that is a question about a
content hash, and the hash is defined in claim_graphs/claim_approval.py. Duplicating the rule in
JavaScript would give two definitions of the same fact and no way to notice when they disagree,
so the resolution happens here and the site reads the answer.

Writes site/src/data/claim-approvals.json in the graph:

    {"<paper>": {"<slug>": {"by": ..., "when": ..., "note": ..., "applies": true}}}

`applies` false means the approval was real and was granted to something the claim no longer
says — worth showing as lapsed rather than hiding, because a judgement that has been overtaken
is a different state from one that was never made.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roots  # noqa: E402
from roots import GRAPH as ROOT  # noqa: E402

sys.path.insert(0, roots.machinery("extract"))

import pipeline  # noqa: E402

OUT = roots.graph("site", "src", "data", "claim-approvals.json")


def build() -> dict:
    out: dict[str, dict] = {}
    for paper in pipeline.papers():
        standing = pipeline.read_claim_approvals(paper)
        if not standing:
            continue
        out[paper] = {
            slug: {"by": r.get("by"), "when": r.get("when"),
                   "note": r.get("note") or "", "applies": bool(r.get("applies"))}
            for slug, r in sorted(standing.items())
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help=f"write {os.path.relpath(OUT, ROOT)}")
    args = ap.parse_args()

    data = build()
    n = sum(len(v) for v in data.values())
    standing = sum(1 for v in data.values() for r in v.values() if r["applies"])

    if args.write:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        print(f"claim approvals → {os.path.relpath(OUT, ROOT)}")
    print(f"  {n} approval(s) across {len(data)} paper(s); {standing} still stand")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
