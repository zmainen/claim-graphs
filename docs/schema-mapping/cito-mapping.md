# CiTO edge-type mapping

> **Superseded by [`mappings.md`](mappings.md)**, which is generated from `standards.yaml` — the
> file the exporters read. This page's table had drifted: it documented `dissociates-with` as
> `cito:disagreesWith`, which the #125 ruling removed and `scripts/formats_report.py` asserts is
> gone, and it listed 14 relations of 21.

CiTO is designed for document-to-document relations, but its OWL axioms do not constrain
domain/range, so claim-level entities are valid subjects and objects. Three categories: exact
matches, close matches usable with documented semantic narrowing, and extensions declared as
subproperties of CiTO for entailment compatibility (`claimrel:`).

Which relation falls in which category is `standards.yaml`, and the generated table renders it.
