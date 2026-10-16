# MIRA-extraction prompt, vendored

`system_message.txt` is `SYSTEM_MESSAGE` and `user_preamble.txt` is `USER_PREAMBLE_PAPER`, copied
verbatim from `src/prompt.ts` of https://github.com/MIRA-science/MIRA-extraction at main
(commit of 2026-08-11, "feat: one call per paper"). They are the community extractor's product
— "editing it changes every graph the tool produces" — and are kept here unedited so the
`mira-baseline` layer reproduces the extractor's call exactly. The call is composed as
`src/core.ts` composes it: system message; user message `preamble + "\n\n---\n" + paper text`;
temperature 0.2; 60,000-token cap; streamed. Re-vendor by hand when the upstream pin moves,
and say so here.
