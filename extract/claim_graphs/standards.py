"""The standards mappings, read from `standards.yaml`.

The mappings lived in three Python dicts — `export_mira.RELATION_DEFS`, `oxa.EDGE_MAP`,
`export_discourse_graphs.RELATION_TO_DG` — and in two prose tables under `docs/schema-mapping/`.
The prose had already gone stale: `cito-mapping.md` documents `dissociates-with` as
`cito:disagreesWith`, which the #125 ruling removed and `formats_report.py` now asserts is gone.

One table, in data, read by whatever exports. A mapping nobody can check against what is exported
is a mapping that drifts, and this project has now watched that happen four times.

It is a data file at the repository root rather than a module because a standards mapping is not
code: it is a set of claims about other people's vocabularies, and the right way to argue with one
is to edit a table.
"""

from __future__ import annotations

import functools
from pathlib import Path

import yaml

PATH = Path(__file__).resolve().parents[2] / "standards.yaml"


@functools.lru_cache(maxsize=1)
def load() -> dict:
    with PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def contexts() -> dict[str, str]:
    """Namespace prefix -> IRI."""
    return dict(load().get("contexts") or {})


def relations() -> dict[str, dict]:
    """Relation name -> its mapping in each standard."""
    return dict(load().get("relations") or {})


def mira_defs() -> dict[str, tuple[str | None, str, str, str]]:
    """`(predicate, domain, range, description)` per relation, as export_mira wants it.

    A `predicate` of None means MIRA has no term and the edge hangs at AbstractRelationDef
    rather than being forced under supports or opposes. That is a deliberate export decision,
    not a gap to fill in: see the note beside it.
    """
    return {name: (m.get("predicate"), m["domain"], m["range"], m["note"])
            for name, r in relations().items() if (m := r.get("mira"))}


def cito() -> dict[str, str]:
    """Relation name -> CiTO IRI, omitting the relations CiTO has no term for."""
    return {name: r["cito"] for name, r in relations().items() if r.get("cito")}


def discourse_graphs() -> dict[str, str]:
    """Relation name -> one of DG's four predicates, omitting what DG cannot express.

    Keyed on the relation, not on the CiTO IRI it maps to. Keying on CiTO meant DG inherited
    whatever CiTO happened to say, and left a dead entry behind when the #125 ruling stopped
    `dissociates-with` mapping to `cito:disagreesWith`.
    """
    return {name: r["dg"] for name, r in relations().items() if r.get("dg")}


def discourse_graphs_by_cito() -> dict[str, str]:
    """CiTO IRI -> DG predicate, composed from the table.

    The DG exporter reads OXA documents, and OXA stores the CiTO IRI in `relationType`, so it
    cannot key on our relation names. Composing the map rather than keeping a third hand-written
    one is what drops a dead entry automatically: `cito:disagreesWith` was in the old map long
    after the #125 ruling stopped any relation mapping to it.

    A collision — two relations sharing a CiTO IRI but disagreeing about DG — is a contradiction
    in the table and raises rather than resolving itself by dictionary order.
    """
    cito_of, dg_of, out = cito(), discourse_graphs(), {}
    for name, iri in cito_of.items():
        dgv = dg_of.get(name)
        if dgv is None:
            continue
        if iri in out and out[iri] != dgv:
            raise ValueError(
                f"standards.yaml: {iri} maps to both {out[iri]!r} and {dgv!r} in DG, "
                f"via different relations — one of them is wrong")
        out[iri] = dgv
    return out
