# Prompt variants

`system_message.txt` is the community extractor's prompt, verbatim (see SOURCE.md). Variants are ours,
written to test one thing: whether the structure the baseline misses is extractable in a single call once
the prompt asks for it. Each variant keeps the output shape, the seven node types and the eight relations
unchanged, so a run under a variant is pure MIRA and comparable node for node with the baseline.

## variant-1 (2026-10-16) — alternatives, hypotheses, provenance

Written from the Gädeke baseline runs (prototype, Sonnet 4.5, Fable 5.1): all recovered the abstract's
findings; none recovered a rival the paper eliminates; Sonnet collapsed the questions to one and pooled
evidence across studies; every run flattened hypothesis, prediction and interpretation into one finding.

Changes, by rule number in the variant:

- **Claim (node type).** "an atomic, generalized assertion the authors make" → "a proposition the paper puts
  in play: what it asserts, what it hypothesizes, and what it raises in order to test or argue against";
  whether the authors hold it is carried by edges. Root cause of zero `opposes` in every run.
- **Study (node type).** An analysis of an experiment's data is a Study in its own right.
- **Rule 4 (Evidence).** One node per producing study or analysis, with its own statistics; never "in both
  studies", never pooled.
- **Rule 5 (Questions and hypotheses).** Replaces "infer at most one or two" with one Question per hypothesis
  the paper commits to; the hypothesis is a Claim addressing it; the finding is a separate Claim that supports
  (or opposes) the hypothesis; Evidence supports the finding. A check gets no Question.
- **Rule 6 (provenance).** A Study per analysis where one experiment feeds several, each following its own
  Protocol, instead of one Study following the union.
- **Rule 7.** Adds "a finding that bears on the hypothesis it tested" to the legitimate Claim→Claim uses.
- **Rule 8 (new).** Alternatives the paper argues against: emit as a Claim stated as its proponent would,
  addressing the favoured explanation's Question, opposed by the result that counts against it; the four
  places alternatives live (eliminating sentences; compared models; control-condition rationale; the
  Discussion's "cannot exclude"); an open alternative addresses the Question with no opposing edge; and the
  distinction between an alternative and a check, which is Evidence supporting the finding it defends.
- **Rule 11 (was 10).** A null result or control does work when it opposes an alternative or defends a
  finding — keep it.

Unchanged: rules 1–3, 9 (Requests), 10 (omit unknowns), 12 (paper), 13 (anchors), the output object, and
every type and relation name.
