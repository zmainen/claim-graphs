# Relations

{{generated-note}}

A relation is a proposition about logical structure between two claims — never a citation.
Each is a top-level YAML key whose value is a list of target slugs:

```yaml
tests: [prediction-distal-dendritic-spike-mechanism]
requires: [l5-model-single-cell-scope, naturalistic-drive-parameterization]
rules-out: [alt-distal-inhibition-raises-somatic-threshold]
```

An older list form, `belongings: [{relation: requires, target: …}]`, is equivalent and appears
in existing corpora. Both are the schema; a tool that reads only one undercounts.

## The vocabulary

{{relations-table}}

## The six moves

**Deduction.** `entails` and `derived-from` carry the hypothesis-to-prediction arc. One
hypothesis normally entails several predictions; each is derived-from it. `derived-from` is
written mechanically as the reciprocal and should not be emitted by hand.

**Induction and support.** `requires` and `supports` carry dependency and evidence. A standalone
empirical claim outside any hypothesis loop still supports the higher-order claims it grounds.

**Abduction.** `supports` and `refutes` running from results back to hypotheses close the
abductive loop: a result that supports one hypothesis while refuting the prediction of its rival
is abduction by elimination.

**Elimination.** `rules-out` is the move a control makes. It needs a target the paper does not
assert, which is why alternatives are authored as claims.

**Contrast and tension.** `dissociates-with` joins two results that are both true and *differ*;
the contrast is the finding, and neither bears on the other's truth. `in-tension-with` is the
mild opposition split from it: two claims the paper asserts, both standing, that pull a shared
implication in opposite directions. Reach for the first when the difference *is* the result, the
second when the difference is a problem the paper has not resolved.

**Scope and warrant.** `scopes` and `enables-method` say where a result stops and what makes it
interpretable. They run *from* the bounding or enabling claim *to* the results affected —
opposite to `requires`, which runs from the result to what it depends on.

## Pairs that get confused

{{relations-confusable}}

## One example of each, from the corpus

{{relations-examples}}

## Reading an edge aloud

{{relations-directions}}

## Open question

Whether `supports` and a hypothetical `consistent-with` assert different things, and whether
opposition is one relation or several, is unsettled — the `relation-vocab` layer, issue #19.
Everything downstream of that question is provisional in the exact sense that it would change if
the answer did. Do not resolve it silently in a new graph: use `rules-out` for elimination,
`dissociates-with` for a contrast that is itself the finding, `in-tension-with` for an
unresolved pull, and `contradicts` or `opposes` only where two claims genuinely cannot both
hold.
