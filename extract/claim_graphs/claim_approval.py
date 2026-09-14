"""Approving a claim, and knowing when that approval still stands.

A layer approval is granted to a *version* of an output and does not follow the layer forward:
re-run it and the approval is superseded, because the thing approved no longer exists. That is
right for an output and wrong for a claim. A claim is a proposition. Someone who has checked
that a paper's reported current density is what a claim says it is has judged the proposition,
and re-running the extraction chain does not undo that judgement — unless the re-run changed
the claim.

So a claim approval names a content hash. It stands while the claim says the same thing and
lapses the moment it does not, which is the behaviour the distinction actually calls for.

WHAT IS HASHED is the part of the file that makes the claim the claim:

    claim, claim-type, role, epistemic, and for each assertion its paper, doi and panel.

WHAT IS NOT, and why it would be wrong to include it:

    warrant, warrant_why, warrant_from, check_verification, priority   computed by layers. Put
        these in the hash and every warrant re-run voids every approval in the corpus, for a
        reason that has nothing to do with anyone's judgement.

    entails, supported_by and the other relations   the shape of the argument, which is what a
        claim-tree approval is for. A claim approval says this proposition is true of this
        paper and typed correctly; rewiring what it entails is a different judgement, and
        collapsing the two loses the ability to hold one without the other.

    reproductions   these change when a verification runs, which is evidence about the claim
        rather than a change to it.

    the body prose   extraction notes and evidence quotes, rewritten wholesale by a re-run that
        may reach the identical claim.

    uuid, slug   identity, not content.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import claimfile

# Ordered, so the canonical form does not depend on dict ordering.
HASHED_FIELDS = ("claim", "claim-type", "role", "epistemic")
HASHED_ASSERTION_FIELDS = ("paper-slug", "doi", "panel")


def content(front: dict) -> dict:
    """The part of a claim's front matter an approval is granted to."""
    out: dict = {k: front.get(k) for k in HASHED_FIELDS}
    out["assertions"] = [
        {k: a.get(k) for k in HASHED_ASSERTION_FIELDS}
        for a in (front.get("assertions") or [])
        if isinstance(a, dict)
    ]
    return out


def content_hash(front: dict) -> str:
    """Twelve hex characters of sha256 over the canonical form.

    Canonical means sorted keys and no insignificant whitespace, so reformatting the file or
    reordering its front matter does not lapse an approval; changing what it says does.
    """
    blob = json.dumps(content(front), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def hash_of_file(path: str | Path) -> str | None:
    front = claimfile.frontmatter(path)
    return content_hash(front) if front else None
