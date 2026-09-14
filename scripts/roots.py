"""Which checkout a path belongs to.

The machinery and the graph were one directory until the split, so a script could say
`os.path.dirname(os.path.dirname(__file__))` and mean both. They are two repositories now and
that expression means exactly one of them — the machinery — while most of what these scripts
read and write is the graph's: `runs/`, `claims/`, `review/`, `verification/`, `site/`.

Getting it wrong is not loud. A corpus build writes `review/prediction-outcome.json` into the
machinery checkout, someone sees an untracked file in their working tree and commits it, and a
public repository acquires a corpus's content (#50, and the cleanup in #43). Reading the wrong
root is the same defect from the other side (#42).

So the choice lives here, once, rather than in each script's header. `GRAPH` is what
`CLAIM_GRAPHS_ROOT` names, falling back to the machinery — which is what a repository holding
both means, and what every invocation predating the split gets.
"""

from __future__ import annotations

import os

MACHINERY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GRAPH = os.path.abspath(os.path.expanduser(
    os.environ.get("CLAIM_GRAPHS_ROOT") or MACHINERY))

# The claim files need not sit under the graph root: a corpus may keep them elsewhere, and the
# package's `contract.claims_dir` reads the same variable.
CLAIMS = os.path.abspath(os.path.expanduser(
    os.environ.get("CLAIM_GRAPHS_CORPUS_DIR") or os.path.join(GRAPH, "claims")))


def graph(*parts: str) -> str:
    """A path in the corpus being worked on — runs, claims, review, verification, site."""
    return os.path.join(GRAPH, *parts)


def machinery(*parts: str) -> str:
    """A path in this checkout — prompts, layer declarations, schemas."""
    return os.path.join(MACHINERY, *parts)
