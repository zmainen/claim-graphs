# claim-graphs

Induce a typed claim graph from a scientific document, and export it to MIRA, OXA and
Discourse Graphs. Format, machinery and standards mappings — no corpus.

Split out of the repository that holds the corpus it was developed against, on 2026-09-13,
with the history of the moved paths intact. That repository keeps the eLife corpus, the site and
the collaboration record, and depends on this one. The reasoning, the file-by-file manifest and
the order of work are in [`docs/design/2026-09-13-the-split.md`](docs/design/2026-09-13-the-split.md).

## What a claim graph is

A claim is a proposition, not a result and not a figure — an entity several documents may
assert, that a reproduction may test, and that other claims may depend on. A document asserting
a claim in a particular panel, on particular data, is an **assertion**, and that is a property
of the document. The same proposition asserted by one paper and rejected by another is one
claim with two assertions, and the disagreement becomes visible.

Relations are not citations. `A requires B` says A would be invalid if B were false, which is
why the graph is worth building: invalidity propagates along the edges.

The graph is **directed, typed, multi-edged and cyclic**. Converse pairs are the reason — a
hypothesis `entails` a prediction and the prediction `tests` the hypothesis, and both directions
carry information. Measured on the seed corpus: 183 cycles across twelve papers, in every one.
Consumers must not assume acyclicity; `views` in the schema carries acyclic projections for
anything that needs a tree.

## The interchange format

[`schema/claim-set-v0.schema.json`](schema/claim-set-v0.schema.json) is the contract — one JSON
document per source document, JSON Schema 2020-12. A consumer needs nothing else: not this
package, not Python, not the pipeline, and not any publisher.

```
{ schemaVersion, document, provenance, questions[], claims[], edges[], views[] }
```

`provenance.reviewed` is first-class, and `none` means every claim and edge is machine output
that no person has checked. A consumer displaying a claim set cannot fail to know.

[`schema/to_claim_set.py`](schema/to_claim_set.py) converts the authoring form (one Markdown
file per claim) and validates the result, exiting non-zero on any defect, so it works as a gate.

## The machinery

`pipeline/layers.yaml` declares the processing graph — what each layer asks, what it reads, what
it produces — and `scripts/pipeline.py` runs one after running whatever it still needs,
recording every run with the content hash of each input.

Where a document comes from is `extract/claim_graphs/sources.py` and nowhere else. A `Source`
resolves a reference to a cached local file and says what format it is in; it does not parse,
because JATS is a standard rather than a publisher's. `ElifeSource` and `FileSource` ship here,
and others register through the `claim_graphs.sources` entry point group:

```toml
[project.entry-points."claim_graphs.sources"]
my-press = "my_package.sources:MyPressSource"
```

## Using it as an agent

The canon, `docs/canon.html`, defines every concept once — the atom, the relations, the roles,
modules and clusters, scope, warrant, the checks, the kinds of decision — versioned by content
and rendered into the contract, the skill, the method and the schema; `scripts/canon.py --check`
holds them to it. Source: `canon/entries.py`; example: `canon/toy-study/`.

`skills/claim-structures/` is the agent-facing entry point: what a claim is, the vocabulary, the
checks, and a runbook for inducing a graph with subagents instead of an API key. It is
**rendered**, not written — every relation, rule, role and step in it is substituted from the
declaration that defines it (`scripts/relations.py`, `scripts/check_relations.py`,
`vocabulary.py`, `pipeline/layers.yaml`, and the prompt contract), so an agent that loads the
skill and a run of the CLI are given the same definitions and the same sequence.

```bash
make skill CORPUS=/path/to/claims   # regenerate after changing a declaration or docs/skill/
```

`make check` fails when the committed skill is not what its sources generate. Edit
`docs/skill/`, never `skills/claim-structures/`. To add a capability — a layer, a workflow, a
check — see [`docs/extending.md`](docs/extending.md).

## Reading a claim set

Python, in the package:

```python
from claim_graphs.claimset import load, validate, edges_of, unaccounted
problems = validate("gadeke-2026-guilt-insula.claims.json")   # [] means valid
```

JavaScript, with no dependencies and no build step — `js/claim-set.mjs`:

```js
import { claimSet } from './claim-set.mjs'
const s = claimSet(JSON.parse(text))
s.has(key)             // does this key name a claim — the check before accepting a mark
s.text(key)            // the plain wording where there is one, else the authors'
s.edges(key)           // every edge touching it, in either direction
s.unaccounted(marked)  // what nothing accounts for — the coverage denominator
s.view()               // an acyclic projection, for anything that needs a tree
```

Neither fetches. Where the set comes from is the caller's business, and an editor that needs the
network to render a mark is worse than one that does not.

`validate` returns a list rather than raising on the first problem, and checks what a JSON Schema
cannot express: that every reference resolves. That is the defect this corpus actually had — eleven
dangling edges, and six claims addressing questions their index no longer declared.

`view()` is there because the graph is cyclic. It walks the relations it is given and stops at the
first already-visited node; a naive tree walk over these edges does not return.

## Standards

`standards.yaml` is the one mapping table and the exporters read it: MIRA predicates with their
domain and range, CiTO IRIs, Discourse Graphs predicates, and the note saying why where a standard
has no term. `docs/schema-mapping/mappings.md` is generated from it, and `make check` fails when the
committed copy is stale.

Where a standard has no term the table says so rather than forcing one — 11 of 21 relations have a
MIRA predicate, 14 a CiTO term, 11 a Discourse Graphs one, and the rest export at the abstract root
with the gap report naming them. The mappings were three Python dicts and two prose tables, and the
prose had already drifted: `cito-mapping.md` documented a CiTO term for `dissociates-with` that the
#125 ruling removed.

## Running it

```bash
cd extract && pip install -e .
make check                         # the whole gate; 6 tests skip without a corpus
make test
```

A corpus is optional. Six tests need one — four prompt-contract tests, because the contract
teaches each relation by rendering a real claim pair and so reads claim files, and two warrant
tests that read a real tree. They skip with a reason saying how to supply one. Point at a
checkout to run them:

```bash
make check CORPUS=path/to/corpus/claims    # 119 tests
```

Every script reaches the claim files through `export_mira.CLAIMS_DIR`, which resolves
`CLAIM_GRAPHS_CORPUS_DIR`, so pointing that at a corpus is enough to make all of them work
against it.

Environment: `CLAIM_GRAPHS_ROOT`, `CLAIM_GRAPHS_CORPUS_DIR`, `CLAIM_GRAPHS_BACKEND`,
`CLAIM_GRAPHS_MODEL_*`, `CLAIM_GRAPHS_ANSWERED_TOKENS`. A flag beats the environment: an explicit
`--root` wins over an exported `CLAIM_GRAPHS_CORPUS_DIR`.

Running against Vertex needs **your own** GCP project — set `VERTEX_PROJECT_ID` and
`VERTEX_REGION`. There is no default, deliberately: there used to be one particular project,
which meant anyone who did not set the variable authenticated against somebody else's account.

## Why eLife appears here

This is machinery, developed against a corpus of eLife papers and split out of the repository that
holds it. Two eLife-specific things are deliberate and the rest was removed before publishing:
`ElifeSource` (the built-in adapter that proves the `Source` protocol carries a real publisher) and
the worked examples in the prompts (real claims teach a relation vocabulary better than invented
ones). [`docs/what-is-elife-doing-here.md`](docs/what-is-elife-doing-here.md) is the reasoning, and
it is the whole list — anything else is a bug.

## Status

The format and the machinery work; the split is not finished. `docs/design/2026-09-13-the-split.md`
§ 7 is the live checklist. Nothing here has a stable release, the schema URL is not yet served,
and the JavaScript reader does not exist yet.

Licence: MIT, as in [`LICENSE`](LICENSE).
