# MIRA de novo prompts

One file per stage of `docs/design/2026-11-01-mira-denovo-stages.md`. Each file has a `## System`
part (the role, the contract, the output shape) and a `## User` part with `{{placeholders}}` the
runner fills: `{{text}}` the article as eLife Pathways serves it, `{{inventory}}`, `{{evidence}}`,
`{{findings}}`, `{{hypotheses}}`, `{{alternatives}}`, `{{questions}}`, `{{panel}}` and
`{{panel_text}}` for the per-panel stage. Agents propose; `scripts/mira_denovo.py` checks. Every
output is JSON; every node carries an `anchor` copied character for character from the text, and
anything whose anchor is not found verbatim is refused, not repaired.
