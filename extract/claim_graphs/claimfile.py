"""Reading a claim file — the one frontmatter parser.

There were three: `export_mira.load_frontmatter`, `corpus_facts.frontmatter`, and the repair
inside `schema/to_claim_set.py`, each carrying its own copy of the same regex for the same
defect. The split made the duplication load-bearing rather than merely untidy: the manifest puts
`corpus_facts.py` with the graph and five machinery scripts import `frontmatter` from it, so the
machinery could not be checked out on its own.

It lives in the package rather than in `scripts/` because `scripts/` is not importable across a
repository boundary. After the split the graph repository has the machinery as a pinned
dependency, so `from claim_graphs.claimfile import frontmatter` resolves there; `from
export_mira import ...` would not.

The two error contracts the callers had are both kept, because they were both deliberate:
`frontmatter` returns None for a file it cannot parse, and `load` raises. A reporting pass wants
to skip a bad file and count it; a gate wants to stop.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

# `key:` with `[]` or `{}` at column 0 on the next line. Written by layers that templated their
# frontmatter instead of dumping it; strict YAML rejects the whole block, so a file carrying it
# is not checked by anything, it is silently skipped. The corpus files are repaired, and readers
# still normalise what they are handed because a claim file from elsewhere is not ours to reject.
EMPTY_COLLECTION_AT_COLUMN_ZERO = re.compile(r"^([A-Za-z0-9_-]+):\n(\[\]|\{\})\s*$", re.M)

FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.S)


def loadable(body: str) -> str:
    """Frontmatter text YAML can parse."""
    return EMPTY_COLLECTION_AT_COLUMN_ZERO.sub(r"\1: \2", body)


def split(path: str | Path) -> str | None:
    """The raw frontmatter block of a claim file, or None if it has none."""
    m = FRONTMATTER.match(Path(path).read_text(encoding="utf-8"))
    return m.group(1) if m else None


def load(path: str | Path) -> dict:
    """Parse a claim file's frontmatter. Raises on a file it cannot read."""
    body = split(path)
    if body is None:
        raise ValueError(f"no YAML frontmatter in {path}")
    return yaml.safe_load(loadable(body))


def frontmatter(path: str | Path) -> dict | None:
    """Parse a claim file's frontmatter, or None if it has none or will not parse."""
    try:
        return load(path)
    except (ValueError, yaml.YAMLError):
        return None
