## System
You read one scientific article and list its studies and the procedures they followed. You answer with JSON only.

A **study** is an experiment with its own participants or data set (for example "Study 1, behavioural, 40 participants, outside the scanner"). A **protocol** is a named procedure a study followed: the task, a manipulation, a measure, a model, an analysis pipeline. Name protocols at the grain at which a result can be *about* one of them: a task, a happiness probe, a risk-attitude estimation, a set of computational models, a mixed-model analysis, an fMRI acquisition-and-analysis pipeline, a connectivity analysis, a comparison with a published signature. Not one per paragraph, not one per sentence.

Every item carries an `anchor`: a passage copied character for character from the article (whitespace and punctuation included) that states it. For a study, the anchor names the participants. For a protocol, the anchor is the Methods sentence that defines it.

Output shape:
{"studies":[{"key":"st1","text":"Study 1: …","description":"one or two plain sentences","anchor":"…"}],
 "protocols":[{"key":"p_task","text":"short name","description":"one or two plain sentences","anchor":"…","followed_by":["st1","st2"]}]}

## User
Article text follows. List its studies and protocols as JSON.

{{text}}
