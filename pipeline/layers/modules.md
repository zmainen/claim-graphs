The steps above atomize a paper into dozens of claims. That is the right unit for coverage and
verification, which work over atoms with spans and panels; it is the wrong unit for a reader,
who holds a paper as a handful of questions and what answered them. A *module* is that unit. It
is derived from the edges the tree already has, so it costs one mechanical pass and no model
call — `python3 scripts/modules.py <paper-slug>`, driven through `pipeline.py run` like any
other layer.

A module is **one question under test**. It carries the question, the hypothesis the paper
commits to, the alternatives it raises in order to reject (with what eliminated each), the
predictions the hypothesis entails (with the outcome `prediction-outcome` recorded), the
findings that test them or bear on the hypothesis directly, and the interpretation drawn. That
is the *argument grain* — the nodes a reader keeps in mind. A module's warrant is its
hypothesis's, and its summary sentence, for a question module, is the hypothesis.

Below the argument, **a finding and the analysis results that bear on it are one cluster**. The
finding is a claim on the paper; the results are its details — the parts it is composed of, the
controls that validate it, the sub-results that support it, the caveats that qualify it or stand
in tension with it. Results are atoms, and nothing that shows or exports a module may call them
claims. The cluster is the unit twice over: of *identity* across versions (the finding carries
its results, so a result appearing or vanishing is a change inside the finding, not a new claim
on the paper — the matcher should later align findings, not atoms), and of *strength* (a
finding's warrant is a function of its results, which the layer records explicitly as
`combine`, naming exactly which results each level was computed from).

**Scope sits beside the argument, in two halves.** The domain is what the claims apply to — the
sample, the task, the design — drawn from what `scopes` the members. The apparatus is what they
rest on — the models, the GLM, the localizer — drawn from what the members `require`. Scope
claims stay claims, cited to a span, but they are the module's ground, not members of its
argument.

**An observation is a finding that answers no declared question** — a whole-brain result no
hypothesis predicted, a model that fitted best. It is a cluster of the second kind, and it is
what a later paper makes a hypothesis of.

**Loose is a lint, not a category.** What no edge places is listed with the edge it would take
to place it: a synthesis wanting an argument edge outward, an apparatus claim wanting a
`requires`, a result reaching no finding. A paper with nothing loose is one whose argument the
graph fully holds; a loose list is a to-do for the edge task, and `check_relations.py` echoes
it once the layer has run.

The derivation writes two files. `runs/<paper>/modules.json` is the full structure — every
module with its member list, and the per-claim owner and grain. `views/<paper>.modules.json` is
the nested view the site reads: the argument grain open, the finding grain folded into clusters.
Both are byte-stable, so a re-run on an unchanged tree changes nothing. The one reading this
cannot do — a sentence for an observation, or for a hypothesis too long to serve as a summary —
is the optional `module-summaries` step, one prompt per paper.
