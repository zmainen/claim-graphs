#!/usr/bin/env python3
"""The canon CLI: one declaration of every concept, checked and (in PR 2) rendered.

    python3 scripts/canon.py --check        # entries complete, vocabulary resolves, surfaces render
    python3 scripts/canon.py --version      # the canon's content digest
    python3 scripts/canon.py --list         # every concept and its status

`--check` runs in `make check`. The contract and skill checks are folded into it, so a drift in
any rendered surface fails here too (with a corpus present).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from canon import canon_version, entries          # noqa: E402
from canon.check import check                      # noqa: E402
from canon import page as page_mod                 # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="run every canon check")
    ap.add_argument("--render", action="store_true", help="write docs/canon.html (corpus-free)")
    ap.add_argument("--with-corpus", action="store_true",
                    help="with --render, enrich a local view with corpus counts (not committed)")
    ap.add_argument("--bless", action="store_true",
                    help="reset the page's changelog baseline to the current entries")
    ap.add_argument("--version", action="store_true", help="print the canon version and exit")
    ap.add_argument("--list", action="store_true", help="list every concept and its status")
    a = ap.parse_args()

    if a.version:
        print(canon_version())
        return 0

    if a.bless:
        print(f"blessed baseline: {page_mod.bless()}")
        return 0

    if a.render:
        print(f"wrote {page_mod.write(a.with_corpus)}")
        return 0

    if a.list:
        reg = entries()
        for eid, e in reg.items():
            print(f"{e['status']:9s} {eid:28s} {e['definition'].split('.')[0][:70]}")
        print(f"\n{len(reg)} concepts; canon {canon_version()}")
        return 0

    if a.check:
        problems = check()
        if problems:
            for p in problems:
                print(f"  FAIL  {p}", file=sys.stderr)
            print(f"\n{len(problems)} problem(s); canon {canon_version()}", file=sys.stderr)
            return 1
        print(f"canon ok: {len(entries())} concepts, version {canon_version()}")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
