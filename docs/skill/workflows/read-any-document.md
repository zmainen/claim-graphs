# Read any document into claims

{{generated-note}}

Use this when the document is not a primary research paper in IMRaD form — a review, a
perspective, an opinion piece, a grant, a proposal, a preprint that keeps its numbers in
running prose — or when you do not know what form it is in and would rather not assume.

It is the same claim structure and the same vocabulary as
[analyze-paper.md](analyze-paper.md). What differs is where the readings come from.

## Why there is a second way in

[analyze-paper.md](analyze-paper.md) runs three readers over three slices of a paper: the
Results, the captions, the methods. `reconcile` then grades a claim by how many of them found
it, and that grade is worth exactly what the slicing is worth. It is worth a lot on an eLife
paper. It is worth nothing on a document that has no Results section, because two of the three
readers are handed empty text and the third reads everything — and nothing in the chain says
so. The slices come back `results:0c captions:0c methods:0c` and the pipeline runs anyway.

So this path does not slice. Both readers are given the **whole document**, and they differ by
the question they are asked:

| reader | works | asks |
|:--|:--|:--|
| `evidence-reader` | upward, from the parts | what does this document show, and where exactly? |
| `argument-reader` | downward, from the question | what does it claim, and how does the claim hang together? |

Two readings of one whole document cannot converge by accident of where a cut fell. So
`converge` does not count them. It records, per claim, **which side it came from**:

| `origin` | what the document is doing |
|:--|:--|
| `both` | the argument and the evidence meet here |
| `argument-only` | asserted, with nothing in the document showing it |
| `evidence-only` | shown, and no part of the argument uses it |

Neither one-sided category is a fault by itself. A review is *supposed* to be thick with
`argument-only` claims standing on citations; a methods paper with `evidence-only` ones. The
point is that you can see the shape and read it against what the document is trying to be,
rather than have it averaged into a grade. **Read the asymmetry, not the tally.**

## The runbook

Set the graph root as in [analyze-paper.md](analyze-paper.md), then:

```bash
python3 scripts/pipeline.py agent <paper> converge --json \
    --by "<the model answering>" --tokens <what that session spent>
```

Same loop as the other path: run it, read the `prompt` it names, answer it, write the `answer`
file, run it again. It stops at each layer a model must answer and exits 10 while one is
waiting, 0 when the target is current, 11 when the validator refused an answer.

**The two readers are `independent`, and it matters more here than there.** `converge`'s whole
output is a statement about which reading found what. A reader that has seen the other's prompt
or answer makes that statement a record of your copy-and-paste rather than of the document. One
subagent per reader, each in its own context.

## What to check when it comes back

**The inventory first.** `prepare` prints the slices and the evidence reader is given a part
inventory built from them. A document whose inventory lists no parts at all has not been read —
that is an intake failure wearing the costume of a thin document.

**Then the shape of `origin`**, against what the document is:

- A **review** with few `argument-only` claims has probably not had its inherited premises
  surfaced — a review's evidence is its citations, and they should appear as
  `literature-context` claims on the evidence side.
- A **research paper** with many `argument-only` claims is asserting things it does not show.
  Read them: some will be citations, and the rest are the interesting ones.
- Many `evidence-only` claims mean results the argument never uses. In a paper that is a
  finding about the paper. In a grant it usually means preliminary data doing no work.

**Then the rivals.** Every position the document argues against needs a claim of its own or the
eliminative move has nothing to point at. Where evidence does the eliminating the edge is
`rules-out`, and the evidence may be inherited — a `literature-context` claim is a legal source,
which is how a document that owns no experiment eliminates anything. Where argument alone does
it, the edge is `opposes`.

**Then the gate**, as ever: [../references/checks.md](../references/checks.md).

## What this path does not do

It does not replace [analyze-paper.md](analyze-paper.md) for an eLife-shaped paper, where the
caption reader anchored to real `<fig>` elements is doing work these two do not.

It does not read a folder. Discovery here walks one prepared document; pointing it at a
directory of code, figures and notes is the next thing this needs and is not built.

And it does not make a one-sided claim into a two-sided one. If you find yourself wanting to
add a counterpart on the missing side so the table looks balanced, stop: the imbalance is the
measurement.
