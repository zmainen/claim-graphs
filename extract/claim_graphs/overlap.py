"""When two claim sentences state the same proposition.

Every comparison between claim tables needs this and none of them should answer it differently:
the asymmetry report, the replicate report, and any scoring of one tree against another are all
asking whether two sentences say the same thing. It lives here so they ask it the same way.

The test is word overlap, and it has a measured limit that decides what it may be used for.

USE IT FOR REPEATED RUNS OF ONE READER. NOT FOR TWO DIFFERENT READERS.

Two samples of one reader on one prompt phrase a proposition similarly, so overlap tracks
agreement well enough to measure reproducibility. Two *differently framed* readers do not.
Checked against the only ground truth available — the three claims a reconciler model judged
to be one proposition seen by both the results and caption readers of the same paper — the
pairs score 0.19, 0.26 and 0.07. No threshold recovers them: at 0.25 one of the three is
caught and unrelated pairs start arriving. They are the same claim in almost entirely
different words:

    "Cognition is not confined to higher-order cortex; it surfaces in incidental movements"
    "Because movement is part of the computation rather than its output, the variables ..."

So deciding whether two readers found the same proposition is a judgement, and it belongs to a
model-answered layer, not to this file. Anything built on this function to compare two readers
would report every claim as one-sided and would be measuring its own vocabulary.

One consequence worth stating where it will be read: because this under-matches, an agreement
number computed with it is a LOWER bound on propositional agreement. Two runs reported as
agreeing 0.76 agree at least that much and probably more. The bias has a known direction, which
is what makes the number usable for comparing two models measured the same way.

The threshold is a knob, not a truth: raise it and near-duplicates separate, lower it and
distinct claims about one subject collapse together.
"""
from __future__ import annotations

import re

DEFAULT_THRESHOLD = 0.6

# Function words carry no proposition and two readers use different ones for the same claim, so
# they are dropped before comparing. Kept deliberately short: a long stopword list starts
# removing words that do distinguish claims ("no", "not", "without" are not on it, and must
# never be, because they invert a proposition rather than decorating it).
_STOP = frozenset("""a an the of in on at to for from by with and or as is are was were be been
being that this these those it its their they them he she we you i than then so such
which who whom whose what when where how why can could may might must shall should will would
do does did done have has had having there here also more most much many very each both other
into over under between within across during about after before while if but because""".split())

# Crude suffix stripping, not stemming. "reports" and "reported" are the same word for this
# purpose, and a paraphrase between two readers turns on exactly that kind of difference. It
# over-collapses — "modelling" and "models" land together, and so would "bases" and "basing" —
# which is the right error to make here: a false match merges two claims a reader can see are
# distinct, while a false miss silently inflates the divergence this is used to measure.
# Enforced, not merely intended: the list above was written once with "not", "no" and "nor" in
# it, which made a claim and its own negation score 1.00. A comment saying so did not prevent it.
_NEGATIONS = frozenset({"not", "no", "nor", "never", "without", "neither", "cannot", "none"})
assert not (_STOP & _NEGATIONS), f"negations must not be stopwords: {sorted(_STOP & _NEGATIONS)}"

_SUFFIXES = ("ational", "ization", "isation", "ingly", "edly", "ing", "ed", "es", "s")


def _stem(w: str) -> str:
    for suf in _SUFFIXES:
        if len(w) - len(suf) >= 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def words(claim) -> set[str]:
    text = claim.get("claim") if isinstance(claim, dict) else getattr(claim, "claim", "")
    raw = re.sub(r"[^a-z0-9 ]", " ", str(text or "").lower()).split()
    return {_stem(w) for w in raw if w not in _STOP and len(w) > 1}


def similarity(a, b) -> float:
    wa, wb = words(a), words(b)
    return len(wa & wb) / len(wa | wb) if (wa and wb) else 0.0


def _negated(claim) -> bool:
    text = claim.get("claim") if isinstance(claim, dict) else getattr(claim, "claim", "")
    return bool(_NEGATIONS & set(re.sub(r"[^a-z0-9 ]", " ", str(text or "").lower()).split()))


def same(a, b, threshold: float = DEFAULT_THRESHOLD) -> bool:
    """Whether two claims state the same proposition.

    Negation disqualifies regardless of overlap. Word overlap cannot see it — "movement is part
    of the computation" and "movement is *not* part of the computation" differ by one token and
    score 0.75, comfortably above any threshold that matches real paraphrases — and treating a
    claim and its negation as one claim is the worst error this function can make: it is the
    case the vocabulary calls `contradicts`, and merging the pair would delete a disagreement
    rather than record it.

    Crude in the other direction too: "no effect was found" and "an effect was found" are caught,
    while "the effect was absent" and "the effect was present" are not, because only one of them
    carries a negation word. This finds the cheap half of the problem and does not pretend to
    the rest.
    """
    if _negated(a) != _negated(b):
        return False
    return similarity(a, b) > threshold


def pair_up(left: list, right: list, threshold: float = DEFAULT_THRESHOLD
            ) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Greedy one-to-one matching: (pairs, unmatched-left, unmatched-right).

    One-to-one rather than nearest-neighbour, because a claim in one table must not be allowed
    to account for two in the other: the counts are read as "how many propositions did each side
    have to itself", and double-matching would silently shrink both.
    """
    taken: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for i, x in enumerate(left):
        best, best_j = threshold, None
        for j, y in enumerate(right):
            if j in taken:
                continue
            s = similarity(x, y) if not (_negated(x) ^ _negated(y)) else 0.0
            if s > best:
                best, best_j = s, j
        if best_j is not None:
            taken.add(best_j)
            pairs.append((i, best_j))
    matched_left = {i for i, _ in pairs}
    return (pairs,
            [i for i in range(len(left)) if i not in matched_left],
            [j for j in range(len(right)) if j not in taken])
