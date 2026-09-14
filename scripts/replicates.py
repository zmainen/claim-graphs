#!/usr/bin/env python3
"""Repeated samples of one layer, recorded and compared.

A layer answered by a model is not a function. Run the same reader twice against the same
prompt and you get two different claim tables — measurably so: four Opus samples of one
results-reader prompt agreed pairwise on 0.76 of their claims, and only 64% of any one run's
claims appeared in all four. The pipeline records which run produced a tree and hashes every
input, so it can say the tree is current; it has no way to say how reproducible it was.

Replicates are that missing axis, and they are deliberately NOT versions. A version supersedes
its predecessor — v2 is the better answer, v1 is history. Replicates are peers: N draws from
one distribution, all equally valid, none superseding another. Folding them into the version
counter would destroy the distinction the ledger exists to record and would mark downstream
layers stale N times for no change of input. So they live in their own directory with their
own index, touch neither `<layer>.output.json` nor the ledger, and nothing downstream sees
them until something asks.

    replicates.py record <paper> <layer> <answer.json> --by <model>   # add one sample
    replicates.py report <paper> <layer>                              # what the samples agree on

`report` gives each distinct claim a `seen` count — the number of replicates that surfaced it.
That count is what a confidence grade should be built on: it measures reproducibility of one
reader against itself, which is the null that any cross-reader agreement signal has to beat.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from roots import graph  # noqa: E402


def _dir(paper: str, layer: str) -> Path:
    return Path(graph("runs", paper, "replicates", layer))


def _claims(doc) -> list[dict]:
    """The claim list, whichever shape the layer's answer takes."""
    if isinstance(doc, list):
        return doc
    for key in ("claims", "additions", "reconciled"):
        if isinstance(doc.get(key), list):
            return doc[key]
    return []


def _words(claim: dict) -> set[str]:
    return set(re.sub(r"[^a-z0-9 ]", "", str(claim.get("claim") or "").lower()).split())


def _same(a: dict, b: dict, thr: float = 0.6) -> bool:
    wa, wb = _words(a), _words(b)
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) > thr


def cmd_record(args) -> int:
    d = _dir(args.paper, args.layer)
    d.mkdir(parents=True, exist_ok=True)
    src = Path(args.answer)
    if not src.is_file():
        print(f"error: no answer file at {src}", file=sys.stderr)
        return 2
    body = src.read_text(encoding="utf-8")
    try:
        doc = json.loads(body)
    except json.JSONDecodeError as e:
        print(f"error: {src} is not JSON ({e})", file=sys.stderr)
        return 2
    n = 1 + max((int(m.group(1)) for f in d.glob("r*.output.json")
                 if (m := re.fullmatch(r"r(\d+)\.output", f.stem))), default=0)
    (d / f"r{n}.output.json").write_text(body, encoding="utf-8")
    rec = {
        "n": n,
        "by": args.by,
        "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "answer_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "prompt_sha256": (hashlib.sha256(Path(args.prompt).read_bytes()).hexdigest()
                          if args.prompt else None),
        "claims": len(_claims(doc)),
        "note": args.note,
    }
    with open(d / "index.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(f"recorded replicate r{n} of {args.layer} for {args.paper} "
          f"({rec['claims']} claims, by {args.by})")
    return 0


def cmd_report(args) -> int:
    d = _dir(args.paper, args.layer)
    files = sorted(d.glob("r*.output.json"),
                   key=lambda f: int(re.fullmatch(r"r(\d+)\.output", f.stem).group(1)))
    if not files:
        print(f"no replicates recorded for {args.paper}/{args.layer}", file=sys.stderr)
        return 2
    runs = [_claims(json.loads(f.read_text(encoding="utf-8"))) for f in files]
    meta = {}
    if (d / "index.jsonl").is_file():
        for line in open(d / "index.jsonl", encoding="utf-8"):
            r = json.loads(line)
            meta[r["n"]] = r
    # Grouped by what answered them, because a noise floor is a property of a model. Pooling
    # samples from two models would report their disagreement with each other as if it were
    # one model's disagreement with itself, which is the number this exists to measure.
    groups: dict[str, list[list[dict]]] = {}
    for f, cl in zip(files, runs):
        n = int(re.fullmatch(r"r(\d+)\.output", f.stem).group(1))
        groups.setdefault(meta.get(n, {}).get("by", "unrecorded"), []).append(cl)

    print(f"{args.paper} / {args.layer} — {len(runs)} replicate(s), "
          f"{len(groups)} answering model(s)")
    out_rows = []
    for by, cls in sorted(groups.items()):
        N = len(cls)
        print(f"\n  {by}  ({N} replicate(s), {', '.join(str(len(c)) for c in cls)} claims)")
        pairs = []
        for i in range(N):
            for j in range(i + 1, N):
                used, m = set(), 0
                for x in cls[i]:
                    for k, y in enumerate(cls[j]):
                        if k not in used and _same(x, y):
                            used.add(k); m += 1; break
                pairs.append(2 * m / (len(cls[i]) + len(cls[j])))
        if pairs:
            print(f"    self-agreement: mean {sum(pairs)/len(pairs):.2f}  "
                  f"min {min(pairs):.2f}  max {max(pairs):.2f}   ({len(pairs)} pairs)")
        buckets: list[dict] = []
        for i, cl in enumerate(cls):
            for c in cl:
                for b in buckets:
                    if _same(c, b["rep"]):
                        b["seen"].add(i); break
                else:
                    buckets.append({"rep": c, "seen": {i}})
        hist: dict[int, int] = {}
        for b in buckets:
            hist[len(b["seen"])] = hist.get(len(b["seen"]), 0) + 1
        print(f"    {len(buckets)} distinct claim(s); by how many replicates surfaced each:")
        for k in sorted(hist, reverse=True):
            share = hist[k] / len(buckets)
            print(f"      {k}/{N}: {hist[k]:3d} ({share:.0%})"
                  + ("   <- the stable core" if k == N else ""))
        out_rows += [{"by": by, "claim": b["rep"].get("claim"), "role": b["rep"].get("role"),
                      "seen": len(b["seen"]), "of": N} for b in buckets]
    if args.json:
        Path(args.json).write_text(json.dumps(out_rows, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
        print(f"\n  per-claim counts written to {args.json}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record", help="record one sample of a layer")
    r.add_argument("paper"); r.add_argument("layer"); r.add_argument("answer")
    r.add_argument("--by", required=True, help="what answered it — pin the model, do not guess")
    r.add_argument("--prompt", help="the prompt file, hashed so samples of different prompts "
                                    "are not compared as if they were the same question")
    r.add_argument("--note")
    r.set_defaults(fn=cmd_record)
    p = sub.add_parser("report", help="what the samples agree on")
    p.add_argument("paper"); p.add_argument("layer")
    p.add_argument("--json", help="also write per-claim replicate counts here")
    p.set_defaults(fn=cmd_report)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
