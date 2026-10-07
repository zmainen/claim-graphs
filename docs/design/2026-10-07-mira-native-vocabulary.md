# A MIRA-native vocabulary: kinds on the node, function on the edge

**Status:** proposed
**Issue:** [#77](https://github.com/zmainen/claim-graphs/issues/77)
**Frames:** `2026-09-10-stance-and-alternative-claims.md` · `2026-09-14-modules.md` · `2026-09-14-scope-representation.md` · claim-graphs#28 (prediction outcomes)
**Depends on:** `extract/prompts/contract/vocabulary.md`, `scripts/relations.py`, `scripts/export_mira.py`, MIRA-science/schema `mira.yaml` at 483f0b2
**Evidence:** `gadeke-2026-guilt-insula`, claim-tree v7 (68 claim files, 85 relations); eLife's integration at https://epp.elifepathways.org/mira/105391; the MIRA community tool's own extraction of the same paper
**Artefacts:** `2026-10-07-gadeke-core.py` builds the appendix as MIRA JSON-LD from the corpus's own sentences; `2026-10-07-gadeke-core.jsonld` is its output, which passes MIRA's closed shapes except for the upstream `sh:in` defect that `validate_mira.py` already isolates

This note proposes replacing the home-grown claim vocabulary — seven claim types, nine roles, a stance field, a grain, and twenty-two relations — with MIRA's six node types and six relations, plus one relation of our own, `entails`. Everything the roles currently record is then either a node type or a view computed from edges. The argument is made from one paper, Gädeke 2026, whose complete node-by-node translation is the appendix. The proposal is a scheme ruling in the sense of `2026-09-12-kinds-of-decision.md`: it changes what every claim file means, so every run under the old scheme becomes stale.

## 1. The problem is where function lives

A paper's graph has to answer two questions about each node. *What kind of thing is this* — a question, an assertion, an observation, an activity, a method, a document? And *what does it do in the argument* — answer, support, oppose, produce, follow? MIRA puts the first on the node, as its type, and the second on the edges. Our format puts both on the node. `role: control` is not a kind of thing; it is a job. So are `scope`, `methodological` and `literature-context`. The claim vocabulary even says so of scope — "it asserts nothing about the world" — and then stores it as a claim.

Function stored as a node property has three consequences, and Gädeke shows all of them.

**A node that does two jobs needs two labels, so classifications multiply.** The tree carries `claim_type`, `role`, `stance` and the modules layer's `grain`, each added when the previous one could not express a distinction a layer needed. Grain was introduced because role could not separate what a paper argues from the apparatus it argues with; stance because role could not say which hypotheses the paper rejects. None retired the one before it, and the MIRA exporter reads the oldest.

**A function judged wrongly is undetectable.** Nothing can check `role: control` against the claim's text, because the role is a judgement about purpose, not a property of the sentence. Of Gädeke's twelve controls, five are checks (manipulation checks, a design precondition, an assumption test), four eliminate a rival, one is specificity, one is convergent support, and one is a null that weakens the hypothesis it is filed under. All twelve pass every gate in `make check`.

**A definition that bundles two jobs produces artefacts to keep the bundle consistent.** `control` is defined as a result that eliminates an alternative *or* shows a manipulation worked. The stance layer, following the rule that `rules-out` must point at a node the paper does not assert, then gave every control's target a rival node. For the five checks that meant inventing propositions nobody holds — "the model-based GLM does not recover known signals", "the imaging pipeline does not recover established effects", "participants chose at random" — each with `role: hypothesis` and its own research question. Three of Gädeke's six "alternatives" are of this kind. eLife's page now shows them as scientific claims, each with evidence listed beneath it and nothing to say the evidence stands against it; the exporter, finding no stated questions after a regeneration dropped them, derived ten questions from ten hypothesis-role claims, six of which were these.

The relations show the same drift. A result that tests a prediction carries `tests` and `confirms` to the prediction and `supports` to the hypothesis: one fact, three edges. `derived-from` mirrors `entails`. `validates` is declared with range Claim and none of its eight Gädeke instances points at one. Four documented relations — `contradicts`, `opposes`, `qualifies`, `replicates` — have no use in the corpus; `in-tension-with` and `dissociates-with` have one each. A vocabulary that large cannot be learned by a model or audited by a person, and the "confused for each other" section of the contract is the measure of it.

## 2. The proposal

Adopt MIRA's node types and relations as the core, pinned to a schema commit, and add one relation. Define every role we currently store as a view over that core.

### 2.1 Node types (MIRA, unchanged)

| Type | MIRA definition | What of ours it absorbs |
|:--|:--|:--|
| `Question` | a scientific unknown addressable by research methods | `questions:` in `index.md` |
| `Claim` | an atomic, generalized assertion that (proposes to) answer a question | hypothesis, rival, prediction, finding-as-statement, synthesis, interpretation |
| `Evidence` | a specific empirical observation from a particular application of a method | every `empirical` and `control` claim; the readers' output |
| `Study` | an activity — an experiment or analysis — that produces evidence | scope: sample, design, preparation; also our verification re-analyses |
| `Protocol` | the method a Study follows to generate its evidence | `methodological` |
| `SourceDocument` | a document that reports a study | `literature-context`, via the cited work |
| `Request` | a unit of work the community can pick up | called-for future work, not captured today |

### 2.2 Relations (MIRA, unchanged)

| Relation | From → To | What of ours it absorbs |
|:--|:--|:--|
| `addresses` | Claim → Question | `addresses` |
| `supports` | Evidence or Claim → Claim | `supports`, `confirms`, `validates`, `extends`, `replicates`, `tests` (positive) |
| `opposes` | Evidence or Claim → Claim | `rules-out`, `refutes`, `contradicts`, `tests` (negative) |
| `observationStatement` | Evidence → Claim | the claim an observation makes: `part-of`, and the finding grain of `modules` |
| `grounds` | Study → Evidence | `scopes`, `requires` (result → scope) |
| `follows` | Study → Protocol | `enables-method`, `requires` (result → method) |
| `sourceDocument` | Evidence → SourceDocument | the paper; `panel` and the anchor quote hang here |
| `describesActivity` | SourceDocument → Study | the literature chain |

### 2.3 One addition

**`entails`, Claim → Claim**, from a hypothesis to a prediction it commits the paper to. MIRA has no deductive relation. Without it, evidence gathered to *test* a hypothesis's prediction and evidence that happens to agree with the hypothesis are indistinguishable — the loss the gap report has called "the paper's deductive spine" and the one distinction this project exists to make. With it, a test outcome needs no new relation: the Evidence `supports` or `opposes` the prediction, and a consumer reads the result back to the hypothesis through `entails`.

Nothing else is added now. Candidates are listed in §5 with the condition under which each would be justified.

### 2.4 Roles become views

Every role, the stance field and the modules grain are computable from types and edges:

| View | Definition over the core |
|:--|:--|
| hypothesis | a Claim that `addresses` a Question and is the source of `entails` |
| prediction | a Claim that is the target of `entails` |
| finding | a Claim that is the `observationStatement` of at least one Evidence |
| confirmed prediction | a prediction that is also a finding — the observation stated what the hypothesis predicted |
| refuted prediction | a prediction `opposed` by Evidence whose `observationStatement` is some other Claim |
| rival | a Claim that `addresses` a Question, is `opposed`, and is not `supported` from this paper |
| open alternative (stance `entertains`) | a Claim that `addresses` a Question with no incoming argument edge from this paper |
| discriminating control | Evidence that `opposes` a rival and `supports` the hypothesis of the same Question |
| check | Evidence that `supports` a finding without being its `observationStatement` |
| replication | two Evidence from different Studies with the same `observationStatement` |
| interpretation | a Claim `supported` only by Claims, with no Evidence of its own |
| scope | the description of the Study that `grounds` the Evidence |
| module | a Question and everything reachable from it through `addresses`, `entails`, `supports`, `opposes`, `observationStatement` |

A view cannot be wrong in the way a stored role can. If the pipeline wires a check as the `observationStatement` of a finding, the error is in one edge, and it is visible: the finding now states something its evidence does not observe. The checker's job narrows to two questions — is each node the kind of thing its type says, and does each edge join the kinds its definition allows — and the second is mechanical.

The confirmed-prediction view deserves a word, because it removes a class of node. In the current tree a prediction ("if responsibility generates guilt, then happiness should decrease more after low partner outcomes when the participant chose") and the finding that confirmed it ("when the partner received the low outcome, happiness was lower when the participant had chosen — interaction β = 0.37") are two claims joined by `tests` and `confirms`. In the core they are one Claim: the hypothesis `entails` it, and the Evidence from Study 1 and Study 2 each have it as their `observationStatement`. Gädeke's five predictions were all confirmed; all five collapse this way. A refuted prediction stays a Claim of its own, `opposed` by the Evidence, whose statement is whatever was actually observed. The "if … then" phrasing the vocabulary requires of predictions goes: the "if" is the `entails` edge.

## 3. The Claim / Evidence line

The one judgement the core still asks of a reader is whether a sentence is Evidence or a Claim, and it needs a rubric that a person can apply and a checker can sample. MIRA's own extraction prompt has one worth adopting verbatim in spirit: Evidence is *the observation itself, distilled* — one observation, past tense, what was measured, in what sample, with the paper's numbers — and a statement of what is generally true, or of what a method can do, is a Claim. Our vocabulary's "what would verify it" test is the operational form: the same computation on the same data is one Evidence; a proposition that several computations bear on is a Claim.

Two corollaries. Numbers belong on Evidence and not on Claims, which ends the practice of folding the interpretation into the result sentence ("… — operationalizing interpersonal guilt"). And the caption reader's panel-level numerics, which the current tree calls claims and the modules note calls "results that are not claims on the paper", are what they always were: Evidence.

## 4. What the process becomes

The layers were built around candidates and measures, and most survive unchanged; what changes is the vocabulary the middle of the pipeline speaks.

- **Readers, reconcile.** Unchanged. A reader's output — a sentence with numbers, anchored to a panel, with a verbatim quote — *is* an Evidence node with `sourceDocument` and an anchor. The three-slice partition remains the defence against hallucinated numbers.
- **External review → the Claim layer.** The one place a model composes rather than extracts: it writes the Questions, the hypotheses, each finding as a statement, the predictions, the interpretations, and the Requests, and it is where adjudication should concentrate. Its prompt inherits the Introduction/Discussion reading the external reviewer already does.
- **Edge inference.** From twenty-two relations to seven. The "confused for each other" appendix shrinks to one entry: `supports` versus `observationStatement`, which is the Claim/Evidence line seen from the edge.
- **Stance, questions, parts.** Fold into the Claim layer and `observationStatement`. No field for stance; it is a view.
- **Modules.** Already mechanical; becomes the module view in §2.4 with no layer of its own.
- **Coverage, adjudication, gap-claim, plain-claim, abstract-map.** Unchanged in purpose. `plain-claim` supplies the node `title` beside the full `description`, which is what eLife asked for as "summaries".
- **Verification.** Gains a representation it lacked. A reproduction is a Study of ours that `follows` a Protocol (the script, pinned) and `grounds` Evidence (the reproduced value) that `supports` or `opposes` the finding. The extended file's `cg:VerificationRecord` becomes core MIRA.
- **Export.** The identity, plus `validate_mira.py`. The extended file carries only `entails` and provenance.

Three checks become possible that are not possible today: endpoint kinds for every edge (a `supports` whose target is Evidence is an error, not a style); no Evidence without a Study that `grounds` it and a Protocol it `follows`; every Claim that `addresses` a Question names one that exists. The last would have caught the regeneration that dropped Gädeke's questions on 13 September while leaving the `addresses` fields pointing at them.

## 5. What is given up, and the price of each

| Lost | Corpus use | Judgement |
|:--|--:|:--|
| synthesis vs interpretation (inside the paper's evidence vs. reaching to a framework) | 6 in Gädeke | real, modest; recoverable as a Claim subtype when a reader needs it |
| `in-tension-with`, `dissociates-with` | 1 each | two findings that both stand need no edge; a description sentence carries the tension |
| `qualifies`, `extends`, `replicates`, `contradicts`, `opposes` | 1, 1, 0, 0, 0 | drop; replication is a view |
| a stored `check` label | — | a view; what is lost is a label on something that already reads correctly |
| the paper's own stance (`rejects` vs `entertains`) | 6 | a view in every Gädeke case |
| `requires` (dependency) | 9 | becomes `grounds`/`follows` for scope and method, `supports` from a premise for literature |
| a light literature-context node | 3 | the SourceDocument → Study → Evidence chain is heavier and is what a citation is; `reference-check` already resolves the DOI |

Nothing here is information about the paper. It is pre-computed labelling, and the labelling was wrong often enough in Gädeke that computing it from edges is the improvement.

**Candidates for later addition**, each with its trigger: a `Claim` subtype distinguishing interpretation from synthesis, when a consumer renders them differently; a marked check relation, when a funder-impact consumer is found counting checks as support; a tension relation, when a paper's argument turns on one. The discipline is the MIRA prompt's rule 10: prefer the smaller accurate graph.

## 6. Risks

MIRA is a working version — seven classes, open comments in its own YAML — and will move. We pin the commit as the extraction tool does, namespace `entails`, and treat changes as proposals we are party to; eLife and SciOS are the other implementers, and three implementations settle a schema faster than discussion. The Claim/Evidence line will be applied inconsistently at first; §3 is the rubric and adjudication of one paper is the calibration. Thirteen trees carry role labels that are discarded; not one has been adjudicated by a person, so what is discarded is unreviewed model output, and the rebuild is the occasion to produce the first approved tree, which the evaluation layer has lacked as a reference since it began.

## 7. What to propose to MIRA

After the translation the list of things MIRA cannot express is short and each item comes with a worked example:

1. **`entails`.** Hypothesis → prediction, and the reading of a test outcome back through it. Gädeke has four hypotheses and five predictions.
2. **Checks.** That "Evidence supports the finding Claim" is the right form, and whether a standard way to mark it is wanted so impact metrics do not count checks as support. Gädeke has five.
3. **Confirmed prediction = finding.** That a prediction Claim and the `observationStatement` of the confirming Evidence are one node. This is a reading of the schema rather than a change to it, and worth confirming.
4. **Study as the home of scope.** Including a re-analysis by a third party as a Study of its own — the reproduction record.
5. **Conventions for consumers.** `title` as the short form and `description` as the full statement; the anchor quote; naming the base predicate in every edge's `@type` as MIRA's own sample does, so a consumer need not resolve a `RelationDef` chain to learn that an edge opposes.

## 8. How to proceed

Not with the pipeline. Build Gädeke by hand in the core vocabulary — the appendix is the first draft — then: validate it with `validate_mira.py` and the §2.4 views; check that every one of the 68 current nodes landed somewhere defensible; compare the finding Claims with the MIRA community tool's six-claim extraction of the same paper, which tests whether the reader grain falls out of the structure; and show the result to eLife as the answer to their 6 October questions. The hand-built graph becomes the specification the pipeline is rebuilt to reproduce, and the first adjudicated reference.

---

## Appendix: Gädeke 2026, node by node

Every claim file in `claims/gadeke-2026-guilt-insula/` (tree v7) and where it goes. **E** = Evidence, **C** = Claim, **Q** = Question, **S** = Study, **P** = Protocol, **D** = SourceDocument. Edges are written source → relation → target. Where the translation exposes an error in the current tree it is marked ⚠.

### Questions (3, from the 12 September `index.md`; the rivals are removed from their wording because they are now Claims)

| | Question |
|:--|:--|
| **Q1** | Does responsibility for a social choice that leaves a partner worse off produce interpersonal guilt — a larger fall in the decision-maker's momentary happiness than when the partner made the same choice? |
| **Q2** | Is the anterior insula, with its condition- and choice-dependent connectivity to prefrontal cortex, the neural substrate of that guilt? |
| **Q3** | Does a neural substrate track the participant's responsibility for the partner's outcomes — representing the partner's reward prediction errors more strongly when they follow the participant's own choice? |

### Studies and Protocols (from the scope and methodological claims)

| Current slug (role) | Becomes |
|:--|:--|
| `findings-rest-two-samples-healthy` (scope) | **S1** Study 1, behavioural, N = 40; **S2** Study 2, fMRI, N = 44. Both `grounds` their Evidence; the "scopes *" edge is this. |
| `study-reproduced-study-design-inside` (scope) | description of **S2**: identical design in the scanner, ISI 3–11 s, experimenter partners outside the scanner |
| `each-trial-participants-chose-between` (scope) | **P-task**: the lottery choice task with Solo / Social / Partner conditions. S1 and S2 `follows` it. |
| `hold-partner-behaviour-constant-across` (methodological) | detail of **P-task**: the partner's choices were an EV-maximising algorithm |
| `momentary-happiness-modelled-five-computational` (methodological) | **P-happiness**: five computational happiness models |
| `model-selection-among-happiness-models` (methodological) | detail of **P-happiness**: likelihood-ratio comparison |
| `model-based-glm-entered-best-fitting-computational` (methodological) | **P-GLM2**: model-based GLM with CR, EV, sRPE, social_pRPE, partner_pRPE regressors |
| `during-receipt-lottery-versus-safe` (empirical, fig4d) | **P-ROI**: regions more active for lottery than safe outcomes define the ROIs. The localizer result is E attached to this Protocol, not to any Claim — the paper does not argue from it. |
| *(implicit)* | **P-LMM**: linear mixed models on happiness; **P-PPI**: gPPI seed-to-voxel connectivity |

### Q1 — behavioural guilt

| Current slug (role) | Becomes | Edges |
|:--|:--|:--|
| `responsibility-social-choice-yields-low` (hypothesis) | **C-H1** | `addresses` Q1; `entails` C-P1a, C-P1b |
| `responsibility-outcomes-generates-guilt-participant` (prediction) + `when-partner-received-low-lottery` (empirical, fig3d/h) + `both-studies-participants-felt-worse` (synthesis) | **C-P1a**, one Claim: *happiness fell more after a low partner outcome when the participant rather than the partner had chosen.* The vocabulary's own "same" example already says the synthesis and the result are one; the confirmed prediction is that same statement. | H1 `entails` P1a. **E-guilt-S1**, **E-guilt-S2** (the interaction, per study) `observationStatement` P1a; S1, S2 `grounds` them. |
| `responsibility-partner-outcomes-influences-participant` (prediction) | **C-P1b**: *a happiness model including the partner's RPEs from the participant's own choices fits better than models without them, with social_pRPE weights above zero.* | H1 `entails` P1b |
| `likelihood-ratio-test-showed-responsibility` (empirical, table1) | **E** | `observationStatement` P1b |
| `partner-reward-prediction-errors-resulting` (empirical) | **E** (weights > 0) | `observationStatement` P1b |
| `responsibility-model-yielded-higher-values` (empirical, table1) | **E** (R²) | `supports` P1b |
| `among-computational-models-fitted-momentary` (methodological ⚠ a result, not a method) | **E** (AIC favours Redux) | `supports` P1b; description notes AIC prefers Redux where LR prefers Responsibility |
| `responsibility-redux-model-incorporating-expected` (empirical, fig3c/g) | **E** (Redux fit) | `supports` P1b |
| `parameter-recovery-procedure-synthetic-data-generated` (methodological) | **E**, a check | `supports` P1b |
| `risk-aversion-parameter-not-differ-between` (control) | **E**, a check (justifies pooling gain and loss) | `supports` P1b, or a sentence in P-happiness's description |
| `participant-momentary-happiness-varied-rewards` / `-2` (empirical, fig3a/b/e/f) | **E** ×2 | `observationStatement` **C-F-rewards**: *momentary happiness tracked the participant's and the partner's rewards.* A finding under Q1 with no hypothesis; the premise the modelling builds on. |
| `rutledge-colleagues-established-changes-momentary` (literature-context) | **D-Rutledge** → `describesActivity` → S-Rutledge → `grounds` → E → `supports` C-F-rewards | the inherited premise, as a chain |
| `participants-own-reward-prediction-errors` (empirical) | **E** | `observationStatement` **C-F-ownRPE**: *the participant's own RPEs weighed more than the partner's.* A finding under Q1; neither supports nor opposes H1. |
| `linear-mixed-model-containing-all` (methodological) | **E**, a check (Model 5 preferred) | `supports` P1a; the model itself is P-LMM |
| `pre-task-icebreaker-succeeded-establishing-positive` (control) | **E**, a check (positive bond, a precondition of the guilt definition) | `supports` P1a |
| `responsibility-choices-not-influence-happiness` (control) | **E**, specificity (no effect after *good* partner outcomes) | `supports` P1a |
| `guilt-effect-occurred-whether-participant` (control) | **E**, discriminating | `supports` P1a; `opposes` C-R-own |
| `alt-guilt-effect-driven-by-own-outcome` (hypothesis, rejects) | **C-R-own**, a rival | `addresses` Q1 |
| `participant-happiness-lower-when-participant` (empirical) | **E** | `observationStatement` **C-F-agency**: *being the decision-maker lowered happiness, independent of outcome.* ⚠ The current tree aims `rules-out` from this evidence at the agency-aversion rival. But this result *shows* an agency cost; it does not eliminate the rival. What eliminates the rival is that the guilt interaction (P1a) holds *over and above* the decision-maker main effect, in a model containing both. The paper asserts both findings. |
| `alt-agency-aversion-not-guilt` (hypothesis, rejects) | **C-R-agency**, a rival: *the Social-condition cost is agency aversion alone, not contingent on the partner's outcome.* | `addresses` Q1; C-P1a `opposes` it (Claim → Claim, legal in MIRA) |
| `lower-happiness-when-participant-decision-maker` (interpretation) | **C-I-responsibility-aversion** | C-F-agency `supports` it |
| `participants-showed-very-similar-risk` (synthesis) | **C-F-risk**: *risk preferences were very similar in Solo and Social, with a tendency to higher risk aversion in Social in Study 1 only.* | `opposes` C-R-risk |
| `risk-premiums-not-differ-between` (control, fig2b/e) | **E** | `observationStatement` C-F-risk |
| `participants-slightly-more-risk-averse` (empirical, fig2c/f) | **E** | `observationStatement` C-F-risk |
| `participants-chose-risky-option-lottery` (empirical, fig2a/d) | **E** | `observationStatement` C-F-risk |
| `mixed-effects-regressions-choices-social-condition` (empirical, app1table1) | **E** | `observationStatement` C-F-risk (the `part-of` edge, absorbed) |
| `no-significant-interaction-between-difference` (control) | **E** | `observationStatement` C-F-risk |
| `alt-social-context-shifts-risk-attitude` (hypothesis, rejects) | **C-R-risk**, a rival | `addresses` Q1 |
| `participants-probability-choosing-risky-option` (control, fig2a/d) | **E**, a check (choices tracked expected value) | `supports` P1a and C-F-risk |
| `alt-participants-insensitive-to-value` (hypothesis, rejects) | **removed** ⚠ — a validity threat written as a proposition nobody holds; the check above is its content | — |
| `behavioural-guilt-effect-larger-happiness` (interpretation) | **C-I-simple-guilt**: *the behavioural effect is compatible with "simple guilt".* | C-P1a `supports` it |

### Q2 — the anterior insula and its connectivity

| Current slug (role) | Becomes | Edges |
|:--|:--|:--|
| `anterior-insula-neural-substrate-guilt` (hypothesis) | **C-H2** | `addresses` Q2; `entails` C-P2 |
| `prior-literature-documents-association-between` (literature-context) | **D** chain → E → `supports` C-H2 | |
| `anterior-insula-tracks-guilt-insula` (prediction) + `insula-rois-responded-more-low` (empirical, fig4e) | **C-P2**, one Claim: *insula BOLD was higher for the partner's low outcomes in the Social than the Partner condition, with the Social × low-outcome interaction.* | H2 `entails` P2 |
| `insula-rois-responded-more-low` | **E** (ROI result) | `observationStatement` P2 |
| `mass-univariate-voxel-wise-analysis-found-small` (empirical, fig4f) | **E** | `observationStatement` P2 |
| `difference-response-between-low-high` (empirical, app1table10) | **E** | `observationStatement` P2 (`part-of`, absorbed) |
| `during-outcome-phase-responses-low` (empirical, app1table9) | **E** | `observationStatement` P2 (`part-of`, absorbed) |
| `bilateral-ventral-striatum-more-active` (control, fig4a) | **E**, a check (the pipeline recovers an established effect) | `supports` P2 |
| `alt-imaging-contrast-invalid` (hypothesis, rejects) | **removed** ⚠ — validity threat as straw claim | — |
| `dot-products-between-individual-neural` (control ⚠ convergent support, not a check) | **E** | `observationStatement` **C-F-signature**: *the insula guilt response matched a published guilt-related brain signature.* C-F-signature `supports` H2. |
| `individual-grbs-dot-product-values-not` (control ⚠ a weakening null filed as a control) | **E** | `observationStatement` **C-F-signature-individual**: *the signature match did not track individual differences in behavioural guilt.* A finding under Q2 with no argument edge; the `in-tension-with` edge becomes a sentence in its description. |
| `functional-connectivity-between-guilt-responsibility-related` (hypothesis) | **C-H2b** | `addresses` Q2; `entails` C-P2b |
| `prior-functional-connectivity-work-shown` (literature-context) | **D** chain → E → `supports` C-H2b | |
| `connectivity-between-guilt-responsibility-related-outcome-ph` (prediction) + `functional-connectivity-between-left-anterior` (empirical, fig5) | **C-P2b**, one Claim: *insula-seeded connectivity with right IFG varied with condition and choice, highest for risky-self / safe-both.* | H2b `entails` P2b; the fig5 result is **E** `observationStatement` P2b; S2 `follows` P-PPI |
| `left-ifg-cluster-showed-opposite` (empirical, fig5s1) | **E** (STS-seeded, opposite pattern, uncorrected) | `supports` P2b, weakly; description carries "did not survive correction". The `qualifies` edge is dropped. |
| `connectivity-between-left-anterior-insula` (interpretation) | **C-I-IFG**: *right IFG is sensitive to guilt-related information during social choice.* | C-P2b `supports` it |
| `decisions-social-compared-solo-condition` (empirical, fig4b) + `only-precuneus-tpj-showed-positive` (empirical, fig4c) | **E** ×2 | `observationStatement` **C-F-social-network**: *Social versus Solo decisions engaged precuneus, TPJ and mPFC.* ⚠ Addresses no stated question; either the paper has an unstated fourth question about the networks of social choice, or the Claim stands un-addressed. |

### Q3 — a substrate of responsibility

| Current slug (role) | Becomes | Edges |
|:--|:--|:--|
| `neural-substrate-tracks-participant-responsibility` (hypothesis) | **C-H3** | `addresses` Q3; `entails` C-P3 |
| `neural-substrate-tracks-participant-responsibility-2` (prediction) + `one-cluster-left-sts-responded` (empirical, fig4h) | **C-P3**, one Claim: *a left STS cluster responded more to the partner's RPEs from the participant's than from the partner's choices.* | H3 `entails` P3; the fig4h result is **E** `observationStatement` P3; S2 `follows` P-GLM2 |
| `left-superior-temporal-sulcus-cluster` (empirical, fig4i) | **E** (the cluster's response across both sessions) | `supports` P3 |
| `manipulation-check-bilateral-ventral-striatum` (control, fig4g) | **E**, a check (GLM2's reward regressor recovers ventral striatum) | `supports` P3 |
| `alt-model-based-glm-invalid` (hypothesis, rejects) | **removed** ⚠ — validity threat as straw claim | — |
| `authors-suggest-left-sts-region` (interpretation) | **C-I-STS**: *this STS region tracks a partner's unexpected outcomes less when they do not follow from the participant's decisions.* | C-P3 `supports` it |

### Not yet captured

**Requests.** The Discussion's calls for future work are not in the current tree and would be the Claim layer's to extract as `Request` nodes with `request_target` the Claims they concern.

### The count

| | Current tree | Core vocabulary |
|:--|--:|--:|
| Questions | 0 in tree (10 derived at export) | 3 |
| Claims | 68 files, 24 exported as `mira:Claim` | 23: 4 hypotheses, 3 rivals, 5 confirmed predictions, 7 further findings, 4 interpretations |
| Evidence | 34 | 38 from the paper (four reclassified from methodological/control/scope), plus 3 carried by the cited works |
| Studies | 0 | 2, plus one per cited work (+ one per verification, later) |
| Protocols | 7 | 6 |
| SourceDocuments | 3 (as claims) | 3 (+ the paper) |
| Relations | 85 across 14 types, 41% dropped at export | 115 across 8 types, 1 type outside MIRA |
| Straw claims | 3 | 0 |

The MIRA community tool, extracting the same paper from its PDF with a free model, produced six Claims. Five of them are, to the sentence, C-P1a, C-P1b, C-P2, C-P2b and C-P3 above; the sixth is C-F-risk. The reader grain is not a grouping heuristic. It is the finding view of §2.4.
