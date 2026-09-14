#!/usr/bin/env python3
"""The pipeline: layer declarations, the run ledger, and computed state.

A layer runs against a paper and produces a version. Whether that version is still good is
not a matter of memory: the run recorded what it read, by path and content hash, so the
question "is this current" is asked of the files rather than of a person.

The repository already answered this question three times, locally and incompatibly:

    runs/<paper>/manifest.json          prompt path + hash, model, output + hash
    verification/<paper>/provenance.json  argv, interpreter, data commit, files opened
    mappings/<paper>.json               a sha per verdict, discarded on mismatch

plus byte-stable exports, where `git diff` is the check. Four mechanisms, one problem. This
module is the fourth answer, and the point of it is that it is the only one: every layer
appends to one ledger in one shape, so staleness and propagation are computed once.

    python3 scripts/pipeline.py graph            the DAG, from the declaration
    python3 scripts/pipeline.py backfill         write ledgers from what already exists
    python3 scripts/pipeline.py state            the paper x layer matrix
    python3 scripts/pipeline.py state --json     the same, for the site
    python3 scripts/pipeline.py run   <paper> <layer>   run it, and its unmet dependencies
    python3 scripts/pipeline.py run   <paper> <layer> --answer FILE   record an answer made elsewhere
    python3 scripts/pipeline.py approve <paper> <layer> --by NAME   record that someone read it
    python3 scripts/pipeline.py approve --declaration <layer> --by NAME   rule on what it means

Usage as a library: `load()`, `state()`, `declaration_state()`.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required:  pip install pyyaml")


def _canon_version() -> str | None:
    """The canon's content digest, so a run records the meaning of *warrant* it was made under.

    Loaded lazily and by path from the machinery, so a graph checkout with no canon beside it
    (older machinery) records nothing rather than failing.
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from canon import canon_version
        return canon_version()
    except Exception:                                              # noqa: BLE001
        return None


def _canon_entry_version(concept: str) -> str | None:
    """The per-entry digest for `approve --declaration canon/<concept>`, keyed so a change to
    that entry invalidates the acceptance — the same shape a layer's declaration version has."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from canon import entries
        e = entries().get(concept)
        if e is None:
            return None
        return hashlib.sha256(json.dumps(e, sort_keys=True, default=str).encode()).hexdigest()[:12]
    except Exception:                                              # noqa: BLE001
        return None

# Two roots, because there are two repositories.
#
# The machinery — the declaration, the runners, the prompts, the schema — is this checkout.
# The graph is somewhere else: `runs/`, `claims/`, `coverage/`, `exports/` belong to whoever
# asserts the claims, which is a paper's own repository or a corpus of readings of other
# people's papers. Before the split the two were one directory and `ROOT` meant both, so the
# runner resolved everything beside itself and could not touch a graph anywhere else — the
# step that validates an answer and writes the ledger was the one step that could not cross
# the boundary the split opened (issue #6).
#
# `CLAIM_GRAPHS_ROOT` names the graph; absent, it is this checkout, which is what a repository
# still holding both means and what every existing invocation gets.
MACHINERY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.abspath(os.path.expanduser(
    os.environ.get("CLAIM_GRAPHS_ROOT") or MACHINERY))
DECL = os.path.join(MACHINERY, "pipeline", "layers.yaml")

# Declared paths under these belong to the machinery; everything else to the graph. A layer's
# `reads:` names prompts and scripts, its `produces:` names artifacts, and after the split
# those live in different checkouts — so a declared path cannot be resolved against one root.
MACHINERY_DIRS = ("pipeline/", "scripts/", "extract/", "schema/", "docs/", "api/")


def _child_env() -> dict:
    """The environment a layer command runs in: the graph root, named explicitly.

    A command runs in the machinery checkout, because that is where the runners are. It must
    still read and write the graph, and it learns which one from here rather than from its own
    location.
    """
    env = dict(os.environ)
    env["CLAIM_GRAPHS_ROOT"] = ROOT
    env.setdefault("CLAIM_GRAPHS_CORPUS_DIR", os.path.join(ROOT, "claims"))
    return env


def base_of(rel: str) -> str:
    """Which root a declared path is resolved against."""
    return MACHINERY if rel.replace(os.sep, "/").startswith(MACHINERY_DIRS) else ROOT


def where(rel: str) -> str:
    """Absolute path of a declared path, in whichever checkout owns it."""
    return os.path.join(base_of(rel), rel)

# States a cell can be in. Ordered worst-first for reporting.
OPEN, STALE, ABSENT, BLOCKED, NA, CURRENT = (
    "open", "stale", "absent", "blocked", "n/a", "current")


# ── declaration ───────────────────────────────────────────────────────────────

def load(path: str = DECL) -> dict:
    """Read the declaration and index it by id, checking the graph is well formed."""
    with open(path, encoding="utf-8") as fh:
        decl = yaml.safe_load(fh)
    layers = OrderedDict((l["id"], l) for l in decl["layers"])

    for lid, l in layers.items():
        for dep in l.get("needs") or []:
            if dep not in layers:
                raise SystemExit(f"{lid}: needs unknown layer {dep!r}")
        if l.get("group") and l["group"] not in (decl.get("groups") or {}):
            raise SystemExit(f"{lid}: unknown group {l['group']!r}")
    _toposort(layers)                      # raises on a cycle
    decl["by_id"] = layers
    return decl


def _toposort(layers: dict) -> list[str]:
    """Dependency order. A cycle here would make staleness undecidable."""
    seen, order, stack = set(), [], set()

    def visit(lid):
        if lid in seen:
            return
        if lid in stack:
            raise SystemExit(f"cycle in the pipeline at {lid!r}")
        stack.add(lid)
        for dep in layers[lid].get("needs") or []:
            visit(dep)
        stack.discard(lid)
        seen.add(lid)
        order.append(lid)

    for lid in layers:
        visit(lid)
    return order


def papers(decl_path: str | None = None) -> list[str]:
    """Papers the site publishes, in corpus order.

    The manifest belongs to the graph, not to the machinery: it says which papers *this*
    corpus holds. A machinery checkout with no graph beside it has no papers, which is a
    true answer and not an error.
    """
    decl_path = decl_path or os.path.join(ROOT, "corpus.yaml")
    if not os.path.isfile(decl_path):
        return []
    with open(decl_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    out = []
    for _, c in (data.get("corpora") or {}).items():
        if c.get("public") and c.get("in_site_corpus", True):
            out += c.get("papers") or []
    return sorted(out)


def under_contract(decl_path: str | None = None) -> list[str]:
    """Papers a corpus declares as re-answered under the current contract.

    Which paper is under an active ruling is a fact about a corpus, and it was a set literal in
    `check_relations.py` naming one paper — machinery carrying a corpus's working state. A corpus
    entry marks itself with `contract-current: true`; a machinery checkout with no graph declares
    nothing, and every outcome case is then a warning rather than an error.
    """
    decl_path = decl_path or os.path.join(ROOT, "corpus.yaml")
    if not os.path.isfile(decl_path):
        return []
    with open(decl_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    out: list[str] = []
    for _, c in (data.get("corpora") or {}).items():
        if c.get("contract-current"):
            out += c.get("papers") or []
    return sorted(out)


def corpora(decl_path: str | None = None) -> tuple[list[str], list[str]]:
    """The graph's manifest, split: (papers the site publishes, papers kept as method examples).

    The manifest belongs to the graph and the reader belongs here, which is the same division
    `papers()` makes. It lives in the runner rather than in the graph's own `corpus_facts.py`
    because scripts that need it — `review_queue`, `audit_verifications` — are machinery and
    cannot import across a repository boundary. A machinery checkout with no graph beside it
    gets two empty lists, which is true rather than an error.
    """
    decl_path = decl_path or os.path.join(ROOT, "corpus.yaml")
    if not os.path.isfile(decl_path):
        return [], []
    with open(decl_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    site: list[str] = []
    examples: list[str] = []
    for _, c in (data.get("corpora") or {}).items():
        if not c.get("public"):
            continue
        (site if c.get("in_site_corpus", True) else examples).extend(c.get("papers") or [])
    return sorted(site), sorted(examples)


# ── paths and hashes ──────────────────────────────────────────────────────────

def expand(patterns, paper: str | None, doi: str | None = None) -> list[str]:
    """Resolve a layer's declared paths for one paper, globbing where they glob."""
    out = []
    for pat in (patterns or []):
        pat = pat.replace("{paper}", paper or "").replace("{doi}", doi or "")
        base = base_of(pat)
        hits = sorted(glob.glob(os.path.join(base, pat)))
        out += [os.path.relpath(h, base) for h in hits] if hits else [pat]
    return out


# ── which machinery ran ───────────────────────────────────────────────────────
#
# `reads:` names machinery files and the runner hashes them into each record, which worked while
# the machinery and the graph were one directory. After the split those paths are a pinned
# dependency outside the graph root, so hashing them from the graph asks about a file that is not
# there — and upgrading the dependency would leave every cell reporting `current` when the code
# that produced it has been replaced. That defeats the one thing the ledger is for (issue #2).
#
# So a record also says which machinery ran. Two fields, because they answer different questions:
# the version is what a reader cites, and the contract hash is what actually changes what a model
# was told. A version bump with an unchanged contract does not invalidate a model answer; a
# contract change with an unchanged version does, and has happened.

CONTRACT_DIR = os.path.join(MACHINERY, "extract", "prompts", "contract")


def _contract_sha() -> str | None:
    """Hash of the rendered prompt contract — the machinery's words, as the model receives them."""
    if not os.path.isdir(CONTRACT_DIR):
        return None
    h = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(CONTRACT_DIR, "*.md"))):
        h.update(os.path.basename(f).encode())
        with open(f, "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()[:12]


def machinery_stamp() -> dict:
    """What to record about the machinery that ran a layer."""
    version = None
    try:
        sys.path.insert(0, os.path.join(MACHINERY, "extract"))
        from claim_graphs import __version__ as version           # noqa: PLC0415
    except Exception:                                             # noqa: BLE001
        pass
    out = {"contract": _contract_sha()}
    if version:
        out["version"] = version
    return {k: v for k, v in out.items() if v}


def machinery_drift(run: dict) -> list[str]:
    """How the machinery differs from the one that produced `run`.

    A record written before this field existed says nothing about its machinery, and silence is
    not agreement — but it is not disagreement either, and calling every historical record stale
    would be a worse answer than admitting the record cannot say. Those are reported by the
    absent-input path instead, which is honest: the file it named is genuinely not there.
    """
    was = run.get("machinery")
    if not was:
        return []
    now = machinery_stamp()
    return [f"{k}: {was.get(k)} -> {now.get(k)}"
            for k in sorted(set(was) | set(now)) if was.get(k) != now.get(k)]


def digest(rel: str) -> str | None:
    """Content hash of one file, or None when it does not exist.

    A directory of claim files hashes as the sorted concatenation of its members, so adding
    a claim changes the tree's hash — which is the whole point: it is what makes every
    export downstream of it stale.
    """
    p = where(rel)
    if not os.path.exists(p):
        return None
    h = hashlib.sha256()
    if os.path.isdir(p):
        for f in sorted(glob.glob(os.path.join(p, "**", "*"), recursive=True)):
            if os.path.isfile(f):
                h.update(os.path.relpath(f, p).encode())
                h.update(open(f, "rb").read())
    else:
        h.update(open(p, "rb").read())
    return h.hexdigest()[:12]


GLOB_CHARS = "*?["


def patterns_of(layer: dict, by_id: dict, paper: str | None, doi=None) -> list[str]:
    """The same inputs as `inputs_of`, unexpanded — the patterns themselves."""
    out = []
    for dep in layer.get("needs") or []:
        out += (by_id[dep].get("produces") or [])
    out += (layer.get("reads") or [])
    return [p.replace("{paper}", paper or "").replace("{doi}", doi or "") for p in out]


def manifest(pat: str) -> str | None:
    """Which files a pattern matches right now — their names, not their contents.

    `digest` already hashes a *directory* as the sorted concatenation of its members, so that
    adding a file to one moves it. Nothing recorded a directory: `expand` resolves
    `claims/{paper}/*.md` into the files that existed at that moment, and staleness then
    re-hashes exactly those paths. A file that appeared afterwards is on nobody's list, so
    nothing looks at it.

    Adding a claim file is precisely that edit, and it is how a gap gets closed — so the one
    change the corpus most needs to notice was the one change it could not. This is the
    missing half: contents per file in `in`, membership per pattern here.
    """
    if not any(ch in pat for ch in GLOB_CHARS):
        return None
    base = base_of(pat)
    hits = sorted(glob.glob(os.path.join(base, pat)))
    names = [os.path.relpath(h, base) for h in hits]
    return hashlib.sha256("\n".join(names).encode("utf-8")).hexdigest()[:12]


def input_sets(layer: dict, by_id: dict, paper: str | None, doi=None) -> list[dict]:
    """Membership fingerprints for every input pattern of this layer that globs."""
    out = []
    for pat in patterns_of(layer, by_id, paper, doi):
        sha = manifest(pat)
        if sha:
            out.append({"pat": pat, "sha": sha})
    return out


def inputs_of(layer: dict, by_id: dict, paper: str | None, doi=None) -> list[str]:
    """Every path a run of this layer reads: its dependencies' outputs, plus `reads`."""
    out = []
    for dep in layer.get("needs") or []:
        out += expand(by_id[dep].get("produces"), paper, doi)
    out += expand(layer.get("reads"), paper, doi)
    return out


# ── the ledger ────────────────────────────────────────────────────────────────

def ledger_path(paper: str) -> str:
    return os.path.join(ROOT, "runs", paper, "ledger.jsonl")


def read_ledger(paper: str) -> list[dict]:
    p = ledger_path(paper)
    if not os.path.isfile(p):
        return []
    out = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def append(paper: str, record: dict) -> None:
    """Append one run record. The ledger is append-only: a version is not edited."""
    p = ledger_path(paper)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def _latest(entries: list[dict], layer_id: str) -> dict | None:
    runs = [e for e in entries if e.get("layer") == layer_id]
    if not runs:
        return None
    return max(runs, key=lambda e: (e.get("v", 0), e.get("ran", "")))


def _by_from_output(layer: dict, outs: list[str], paper: str | None = None) -> str | None:
    """Who answered, read out of what the layer produced.

    From outside the command the runner can only record that it invoked something, which is
    how every entry came to say `scripts/pipeline.py run` while the interesting fact — which
    model wrote these claims — lived in a hand-kept manifest.json beside it. A layer that a
    model answers declares `by_from`, and the answer travels in its own output.

    A layer whose output is one file for the whole corpus — `summaries` writes every paper's
    entry into one paper-summaries.json — has no top-level place for the model, so it records
    it inside the paper's entry. When the top-level key is absent and the file is a dict keyed
    by paper, fall back to that entry, so `by_from: model` finds it either way.
    """
    key = layer.get("by_from")
    if not key or not outs:
        return None
    p = where(outs[0])
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None
    if isinstance(data, dict):
        if data.get(key):
            return data[key]
        if paper and isinstance(data.get(paper), dict):
            return data[paper].get(key) or None
    return None


ANSWERED_TOKENS_ENV = "CLAIM_GRAPHS_ANSWERED_TOKENS"


def answered_tokens(flag: int | None = None) -> int | None:
    """What the session that answered this layer spent, if anybody said.

    Every layer in this corpus is answered by something other than the configured backend: a
    prompt is dumped, an agent or a person answers it, and the answer comes back through
    `--answer`. That route makes no API call, so the usage the call path records is zero, and
    the ledger has carried `supplied:<path>` — how the answer arrived — with nothing about what
    it cost. The one number that exists at that moment lives in the answering session's own
    accounting and had nowhere to go.

    A runner takes it from `--tokens` when invoked directly, or from the environment when
    `pipeline.py run` invokes it, because the declared command is fixed and cannot carry a
    value that changes every run.

    It is deliberately not called `input_tokens`: a session total covers reading the prompt,
    the contract and the corpus, then fixing what the validator refused. Summing it into the
    API's four fields would make two different things look like one measurement.
    """
    if flag:
        return int(flag)
    raw = (os.environ.get(ANSWERED_TOKENS_ENV) or "").strip()
    return int(raw) if raw.isdigit() and int(raw) else None


def answered_usage(tokens: int | None) -> dict:
    """The usage block for a layer answered outside a backend call."""
    return {"answered_tokens": int(tokens)} if tokens else {}


def _usage_from_outputs(outs: list[str], root: str = ROOT) -> dict:
    """Scan the layer's output JSON files for a top-level 'usage' dict; merge and return."""
    merged: dict = {}
    for path in outs:
        if not path.endswith(".json") or "*" in path:
            continue
        full = os.path.join(root, path)
        try:
            with open(full, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        usage = data.get("usage") if isinstance(data, dict) else None
        if not isinstance(usage, dict):
            continue
        for key, val in usage.items():
            if isinstance(val, (int, float)):
                merged[key] = merged.get(key, 0) + val
    return merged


def record(paper: str, layer: dict, by_id: dict, *, note: str, by: str,
           doi: str | None = None) -> dict:
    """Build a run record for a layer that has just run, hashing what it read and wrote."""
    entries = read_ledger(paper)
    prev = _latest(entries, layer["id"])
    ins = inputs_of(layer, by_id, paper, doi)
    outs = expand(layer.get("produces"), paper, doi)
    by = _by_from_output(layer, outs, paper) or by
    usage = _usage_from_outputs(outs)
    entry: dict = {
        "layer": layer["id"],
        "v": (prev["v"] + 1) if prev else 1,
        "ran": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": layer.get("kind", "step"),
        "note": note,
        "by": by,
        "in": [{"path": r, "sha": digest(r)} for r in ins if digest(r)],
        "in_sets": input_sets(layer, by_id, paper, doi),
        "out": [{"path": r, "sha": digest(r)} for r in outs if digest(r)],
        "machinery": machinery_stamp(),
    }
    cv = _canon_version()
    if cv:
        entry["canon"] = cv
    if usage:
        entry["usage"] = usage
    return entry


# ── state ─────────────────────────────────────────────────────────────────────

def keep_versions(rec: dict, root: str = ROOT) -> list[str]:
    """Keep a versioned copy of each single file this run produced under runs/.

    A records layer's output file holds only its latest version — the reader, the
    reconciler, the reviewer and the edge step each overwrite one file per run — so an
    earlier version's bytes are otherwise unrecoverable, and the site's two-version
    comparison has nothing to read the older side from. Copying `<name>.<ext>` to
    `<name>.v<N>.<ext>` beside it, where N is the version this run just recorded, makes each
    version addressable without moving the layer's own output path (which everything
    downstream reads) or touching the ledger.

    Only single files under `runs/`: `claims/` versions itself by archiving the whole tree
    into `runs/<paper>/claim-tree.v<N>/`, and a path outside `runs/` is not this runner's to
    duplicate. Nothing is backfilled — a versioned copy exists only for a version this ran.

    Returns the copies made, for the caller to report and a test to assert.
    """
    made: list[str] = []
    for o in rec.get("out", []):
        path = o["path"]
        if not path.startswith("runs/") or "*" in path:
            continue
        src = os.path.join(root, path)
        if not os.path.isfile(src):
            continue
        stem, ext = os.path.splitext(path)
        kept = f"{stem}.v{rec['v']}{ext}"
        shutil.copyfile(src, os.path.join(root, kept))
        made.append(kept)
    return made


def approvals_path(paper: str) -> str:
    return os.path.join(ROOT, "runs", paper, "approvals.jsonl")


def claim_approvals_path(paper: str) -> str:
    return os.path.join(ROOT, "runs", paper, "claim-approvals.jsonl")


# The claim files need not sit under the graph root: a corpus may keep them elsewhere, and the
# package's contract.claims_dir reads the same variable.
CLAIMS = os.path.abspath(os.path.expanduser(
    os.environ.get("CLAIM_GRAPHS_CORPUS_DIR") or os.path.join(ROOT, "claims")))


def claim_path(paper: str, slug: str) -> str:
    return os.path.join(CLAIMS, paper, f"{slug}.md")


def _claim_hash(paper: str, slug: str) -> str | None:
    """The claim's content hash, from the package beside this runner."""
    sys.path.insert(0, os.path.join(MACHINERY, "extract"))
    from claim_graphs.claim_approval import hash_of_file      # noqa: PLC0415
    return hash_of_file(claim_path(paper, slug))


def approve_claim(paper: str, slug: str, *, by: str, note: str = "") -> dict:
    """Record that a person judged one claim, against the content they judged.

    Unlike a layer approval this is not granted to a version. A claim is a proposition, and
    re-running the chain does not undo a judgement about it — but changing what the claim says
    does. The hash is what makes that difference expressible: it covers the claim sentence, its
    type and role, and what it is asserted about, and not the fields layers compute. See
    claim_graphs/claim_approval.py for what is in it and why each excluded field is excluded.
    """
    digest = _claim_hash(paper, slug)
    if digest is None:
        raise SystemExit(f"error: no claim {slug!r} in {paper}")
    rec = {"slug": slug, "hash": digest, "by": by, "note": note,
           "when": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    p = claim_approvals_path(paper)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def read_claim_approvals(paper: str) -> dict[str, dict]:
    """The standing approval per claim, with whether it still applies.

    Last record wins, so re-approving after an edit supersedes rather than duplicates.
    `applies` is False when the claim has changed since: the judgement was real and is recorded,
    and it was made about something this claim no longer says.
    """
    out: dict[str, dict] = {}
    p = claim_approvals_path(paper)
    if not os.path.isfile(p):
        return out
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("slug"):
                out[rec["slug"]] = rec
    for slug, rec in out.items():
        rec["applies"] = (_claim_hash(paper, slug) == rec.get("hash"))
    return out


def read_approvals(paper: str) -> list[dict]:
    """Approvals recorded for this paper's layer versions.

    An approval is an operation on a version, not a layer of its own: a person read what a
    layer produced and approved *that* output. It names the version it was granted to, so
    when the layer runs again the approval does not follow — it was given to text that no
    longer exists.
    """
    p = approvals_path(paper)
    if not os.path.isfile(p):
        return []
    out = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def approve(paper: str, layer_id: str, v: int, *, by: str, note: str = "",
            procedure: int | None = None) -> dict:
    """Record that a person approved one version of one layer.

    `procedure` names the adjudication procedure version the reading was made under, for a
    claim-tree approval bound to a verdict file; it is omitted for a plain output approval.
    """
    rec = {"layer": layer_id, "v": v, "by": by, "note": note,
           "when": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if procedure is not None:
        rec["procedure"] = procedure
    p = approvals_path(paper)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


# ── the scheme: a declaration, and the ruling on it ─────────────────────────────
#
# An adjudication is an operation on a *version* of one paper's output. A scheme ruling is the
# other kind of decision (docs/design/2026-09-12-kinds-of-decision.md): a person accepts what a
# layer *means*, for every paper, once. What is accepted is the declaration — the layers.yaml
# entry plus the files that define its meaning: the prompt task file, and for a corpus-scope
# vocabulary scripts/relations.py and the like — which is exactly what `reads` already names and
# staleness already hashes. So a declaration version reuses `digest` rather than inventing a
# second hash, and moves when the entry or one of those files does. The ruling lives in one
# corpus-level ledger, in the same shape as a per-paper approval.

ACCEPTED, PROPOSED = "accepted", "proposed"

# A declaration that is not a layer: a design note ruled on and versioned, keyed on the note's
# own content hash the way a layer's declaration is keyed on `digest`. The adjudication procedure
# — the steps and verdict vocabulary in this note — is one such scheme, ruled on under #108.
DOC_DECLARATIONS = {"procedure": "docs/design/2026-09-12-kinds-of-decision.md"}


def corpus_approvals_path() -> str:
    return os.path.join(ROOT, "runs", "approvals.jsonl")


def read_corpus_approvals() -> list[dict]:
    """Scheme rulings: a person's approval of a declaration version, corpus-wide."""
    p = corpus_approvals_path()
    if not os.path.isfile(p):
        return []
    out = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def declaration_version(layer: dict) -> str:
    """The hash of a layer's declaration: its entry, plus the files the ruling is *about*.

    Those files are `governs`, a subset of `reads`. The two used to be the same list, on the
    reasoning that a ruling made under one wording is a ruling under that wording and no other.
    That is true of wording and false of everything else `reads` names, and the difference cost
    every ruling this corpus has:

        13:22  relation-vocab accepted — "once #125 and #28 were written in"
        14:13  8414ae8 writes #125 into scripts/relations.py
               relations.py is in `reads` → the hash moves → the approval reads superseded

    Carrying a ruling out is indistinguishable from revising it under a content hash, so the
    gate stood at nought accepted of thirty-five with six rulings genuinely made: no true
    positive, six false ones. A gate that has never been right and is red on everything carries
    no information, and it teaches re-approval as a reflex — `runs/approvals.jsonl` already
    holds two lines doing exactly that.

    This is the same correction #54 made one grain down, for the same reason: a claim approval
    named a run version and lapsed whenever the layer ran, which is right for an output and
    wrong for a proposition. As there, each exclusion earns its place:

      implementations — scripts/relations.py, prediction_outcome.py, warrant.py — are the
      ruling carried out. Drift between them and the ruled meaning is real, and it is caught
      by check_relations.py and the contract tests, continuously and loudly, which is a better
      instrument than a hash that cannot say what changed.

      generated files — extract/prompts/contract/*, docs/schema-mapping/claim-relations.ttl —
      say "Do not edit; edit the source and regenerate". Their content is a function of their
      sources, so they carry no decision of their own; ruling on one would be ruling on a
      derivative.

      checkers — check_relations.py — enforce the ruling rather than state it.

    What stays is hand-written text that *is* the decision: docs/claim-format.md for the claim
    format, and each model-answered layer's own task prompt, which is what the model is told a
    part or a question or a warrant is.

    The entry itself is still hashed whole. Nothing has yet lapsed a ruling through it — all six
    lapses here were file-driven — so narrowing it would be a change with no evidence behind it.

    A layer with no `governs` key falls back to `reads`, which is the old behaviour exactly, so
    this loosens nothing that has not been looked at.
    """
    h = hashlib.sha256()
    h.update(json.dumps(layer, sort_keys=True, default=str).encode("utf-8"))
    for r in governs_of(layer):
        h.update(f"{r}:{digest(r)}".encode("utf-8"))
    return h.hexdigest()[:12]


def governs_of(layer: dict) -> list[str]:
    """The files a ruling on this layer is about: `governs` if declared, else all of `reads`.

    `governs: []` is a declaration that no file carries the decision — the entry's own prose
    does — and is distinct from the key being absent, so the test is membership rather than
    truthiness.
    """
    return list(layer["governs"] or []) if "governs" in layer else list(layer.get("reads") or [])


def approve_declaration(layer_id: str, version: str, *, by: str, note: str = "") -> dict:
    """Record that a person accepted one version of one layer's declaration."""
    rec = {"declaration": layer_id, "version": version, "by": by, "note": note,
           "when": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    p = corpus_approvals_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def declaration_state(decl: dict | None = None) -> dict:
    """Per layer, the scheme its declaration is in.

    `accepted` when a ruling names the current declaration version; `proposed` when the
    declaration has moved past the accepted one, or the entry itself says `status: proposed`
    and nothing is accepted; `open` otherwise. `provisional_on` lists the corpus-scope
    declarations a layer needs that are not accepted — a tree built while `relation-vocab` is
    open is provisional on its own cell, and this is what says which decision it waits on.
    """
    decl = decl or load()
    by_id = decl["by_id"]
    latest: dict[str, dict] = {}
    for a in read_corpus_approvals():
        lid = a.get("declaration")
        if not lid:
            continue
        if lid not in latest or a.get("when", "") >= latest[lid].get("when", ""):
            latest[lid] = a

    out: dict[str, dict] = {}
    for lid, layer in by_id.items():
        ver = declaration_version(layer)
        ok = latest.get(lid)
        if ok and ok.get("version") == ver:
            out[lid] = {"scheme": ACCEPTED, "version": ver,
                        "approved": {"version": ver, "by": ok.get("by"),
                                     "when": ok.get("when"), "note": ok.get("note")}}
        elif ok:
            out[lid] = {"scheme": PROPOSED, "version": ver,
                        "approved": {"version": ok.get("version"), "by": ok.get("by"),
                                     "when": ok.get("when"), "note": ok.get("note"),
                                     "superseded": True}}
        elif layer.get("status") == PROPOSED:
            out[lid] = {"scheme": PROPOSED, "version": ver}
        else:
            out[lid] = {"scheme": OPEN, "version": ver}

    def corpus_deps(lid: str, seen: set[str] | None = None) -> set[str]:
        seen = seen if seen is not None else set()
        for d in by_id[lid].get("needs") or []:
            if d not in seen:
                seen.add(d)
                corpus_deps(d, seen)
        return seen

    for lid in by_id:
        waits = sorted(d for d in corpus_deps(lid)
                       if by_id[d].get("scope") == "corpus" and out[d]["scheme"] != ACCEPTED)
        if waits:
            out[lid]["provisional_on"] = waits
    return out


def state(decl: dict | None = None, slugs: list[str] | None = None) -> dict:
    """The paper x layer matrix.

    A cell is `current` only if it ran and every input still hashes to what that run
    recorded. It is `stale` if an input moved, `blocked` if something it needs is not
    current, `absent` if it never ran, `n/a` if declared impossible, `open` if it is an
    undecided question.
    """
    decl = decl or load()
    by_id = decl["by_id"]
    slugs = slugs or papers()
    order = _toposort(by_id)
    na = decl.get("not_applicable") or {}
    # A corpus-scope cell's mechanism follows the scheme, which is computed from the rulings —
    # not from a hand-written `open:` flag that nobody updates when a question is answered.
    # Keeping both meant the site could print "undecided" beside an "accepted" chip for the
    # same layer, which is what it did for relation-vocab after #125 was ruled and written in.
    scheme = declaration_state(decl)
    current_canon = _canon_version()

    out = {}
    for paper in slugs:
        entries = read_ledger(paper)
        oks = read_approvals(paper)
        cells = {}
        for lid in order:
            layer = by_id[lid]
            if layer.get("scope") == "corpus":
                # `proposed` is a rule that exists and runs, so mechanically it is current;
                # the scheme chip beside it is what says a person has not accepted this
                # version. Only a genuinely unanswered question reads `open`.
                cells[lid] = {"state": OPEN if scheme[lid]["scheme"] == OPEN else CURRENT,
                              "scope": "corpus"}
                continue
            if lid in (na.get(paper) or {}):
                cells[lid] = {"state": NA, "why": na[paper][lid]}
                continue

            run = _latest(entries, lid)
            produced = [r for r in expand(layer.get("produces"), paper) if digest(r)]

            # Propagation, and the reason the graph is walked in dependency order. Only
            # staleness propagates: an input that *changed* since the run makes this output
            # wrong. An input that was never *recorded* is a different complaint — nine of
            # these papers were extracted before the ledger existed, and their exports are
            # perfectly consistent with the claim files they were built from. Conflating the
            # two would paint the whole corpus red and say nothing.
            upstream = [d for d in (layer.get("needs") or [])
                        if by_id[d].get("scope") != "corpus"
                        and cells.get(d, {}).get("state") in (STALE, BLOCKED)]
            unrecorded = [d for d in (layer.get("needs") or [])
                          if by_id[d].get("scope") != "corpus"
                          and cells.get(d, {}).get("state") == ABSENT]

            if not run or run.get("backfilled"):
                # No observed run. Either there is no entry at all, or there is a backfilled
                # one — which records that an artifact exists, not that a run was watched.
                # A backfilled entry carries no inputs, so it cannot answer "is this still
                # current"; saying `unrecorded` is the honest answer and is what the state
                # means. The artifact may be perfectly good.
                st = ABSENT if not produced else "unrecorded"

                # What the entry *does* carry is kept. Declining to assert inputs a backfill
                # never observed is the point of #30; discarding the version, the date and the
                # model alongside them was not. Thirteen of Gaedeke's fifteen `unrecorded`
                # cells have an entry naming all three, and the site rendered every one of
                # them as a bare "no run recorded" directly above the artifact it names —
                # which reads as nothing having happened, in a corpus where something did.
                #
                # `by` is written as the literal "unrecorded" when the backfill could not tell
                # who answered, so it is dropped here rather than rendered as an author.
                if run:
                    by = run.get("by")
                    cells[lid] = {"state": st, "v": run["v"], "ran": run.get("ran"),
                                  "note": run.get("note"), "backfilled": True,
                                  "by": None if by == "unrecorded" else by}
            else:
                # Three ways a run can be out of date, and they call for different actions.
                #
                # `moved`   an input this graph holds has different content now — re-run.
                # `drift`   the machinery is not the one that ran it (issue #2) — re-run, but
                #           the graph did not change, so the claim may be identical. Both a
                #           changed machinery file and a changed stamp land here: they are the
                #           same fact at different grain, and while the machinery is still
                #           reachable the per-file answer is the more useful of the two.
                # `absent`  the run named a machinery path that is not in this graph root. Every
                #           record predating the split does, because the package was renamed
                #           under it. Not evidence the input changed: evidence the record cannot
                #           say. Reported as its own thing rather than as a content change,
                #           which is what `digest() is None` would otherwise be read as.
                drift = machinery_drift(run)
                moved, absent = [], []
                for i in run.get("in", []):
                    now = digest(i["path"])
                    if now == i["sha"]:
                        continue
                    if base_of(i["path"]) != MACHINERY:
                        moved.append(i["path"])                    # the graph's own input
                    elif now is None:
                        absent.append(i["path"])                   # not in this graph at all
                    else:
                        drift.append(i["path"])                    # a machinery file, changed
                lost = [o["path"] for o in run.get("out", []) if not digest(o["path"])]
                # A pattern whose membership has changed: a file it matches appeared or was
                # removed since the run. Entries recorded before `in_sets` existed carry
                # none, and are left alone rather than guessed at.
                appeared = [x["pat"] for x in run.get("in_sets", []) if manifest(x["pat"]) != x["sha"]]
                st = STALE if (moved or lost or appeared or drift or absent) else CURRENT
                cells[lid] = {"state": st, "v": run["v"], "ran": run.get("ran"),
                              "note": run.get("note"), "by": run.get("by"),
                              "moved": moved, "lost": lost, "appeared": appeared,
                              "drift": drift, "absent": absent}
                # A run made under an older canon was made under an older meaning of the
                # concepts it records — shown beside the mechanism state, not folded into it.
                if run.get("canon") and current_canon and run["canon"] != current_canon:
                    cells[lid]["canon_stale"] = {"ran_under": run["canon"],
                                                 "current": current_canon}
            if lid not in cells:
                cells[lid] = {"state": st}
            if st == CURRENT and upstream:
                cells[lid]["state"] = BLOCKED
                cells[lid]["blocked_by"] = upstream
            if unrecorded:
                # Not a state — the artifact may be perfectly good. A gap in how it can be
                # accounted for, which is worth showing beside it rather than instead of it.
                cells[lid]["unrecorded_upstream"] = unrecorded

            # Approval, which is about this cell's version rather than about its inputs.
            # An approval of v2 says nothing about v3, so it is reported beside the state
            # rather than folded into it: the output can be perfectly current and unread.
            ok = max((a for a in oks if a.get("layer") == lid),
                     key=lambda a: (a.get("v", 0), a.get("when", "")), default=None)
            if ok:
                cells[lid]["approved"] = {
                    "v": ok["v"], "by": ok.get("by"), "when": ok.get("when"),
                    "note": ok.get("note"),
                    "applies": bool(run) and ok["v"] == run.get("v"),
                }
        out[paper] = cells
    return out


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_graph(args) -> int:
    """Print the DAG in dependency order, so the declaration can be read as a shape."""
    decl = load()
    by_id, groups = decl["by_id"], decl.get("groups") or {}
    scheme = declaration_state(decl)
    print("pipeline — %d layers, %d groups\n" % (len(by_id), len(groups)))
    for lid in _toposort(by_id):
        l = by_id[lid]
        needs = ", ".join(l.get("needs") or []) or "—"
        flag = " ·OPEN" if scheme[lid]["scheme"] == OPEN else (
            " ·HUMAN" if l.get("requires_human") else "")
        grp = f"[{l['group']}] " if l.get("group") else ""
        print(f"  {lid:18} {l.get('kind',''):10} {l.get('scope',''):7}{flag}")
        print(f"  {'':18} {grp}needs: {needs}")
        if l.get("produces"):
            print(f"  {'':18} → {', '.join(l['produces'])}")
        print()
    return 0


def cmd_backfill(args) -> int:
    """Write ledgers from the run records the repository already keeps.

    Nothing here invents history. A layer gets an entry only where an artifact of it exists
    on disk; the date comes from the record that carries one, else from git, else the file's
    own mtime. The note says where the entry came from, because a backfilled entry is
    weaker evidence than a recorded one and should not pretend otherwise.
    """
    decl = load()
    by_id = decl["by_id"]
    written = 0

    for paper in papers():
        if read_ledger(paper) and not args.force:
            print(f"  {paper:38} ledger exists — skipping (--force to rewrite)")
            continue
        p = ledger_path(paper)
        if args.force and os.path.isfile(p):
            os.remove(p)

        manifest = os.path.join(ROOT, "runs", paper, "manifest.json")
        man = json.load(open(manifest, encoding="utf-8")) if os.path.isfile(manifest) else {}
        by_role = {r["role"]: r for r in (man.get("roles") or [])}

        n = 0
        for lid in _toposort(by_id):
            layer = by_id[lid]
            if layer.get("scope") == "corpus":
                continue
            outs = [r for r in expand(layer.get("produces"), paper) if digest(r)]
            if not outs:
                continue

            role = by_role.get(lid) or by_role.get(lid.replace("-", "_"))
            ran = man.get("recorded") if role else _git_date(outs[0])
            rec = {
                "layer": lid,
                "v": 1,
                "ran": ran or "unknown",
                "kind": layer.get("kind", "step"),
                "note": "backfilled from " + ("runs/manifest.json" if role else "the artifact on disk"),
                "by": (role or {}).get("model") or "unrecorded",
                "backfilled": True,
                # No `in`. Backfill can name the paths the *declaration* says this layer
                # reads, and hash them as they stand now — but that is a guess about a run
                # nobody observed, in the same shape as a measurement. For Gädeke's
                # claim-tree the guess was false: the claim files were committed
                # 2026-03-30 and the reader outputs the declaration points at on
                # 2026-09-10, five months later, sharing no claim text with them. The
                # entry asserted a lineage that never existed, and `state` read those
                # hashes and called the cell current.
                "out": [{"path": r, "sha": digest(r)} for r in outs],
            }
            append(paper, rec)
            n += 1
        written += n
        print(f"  {paper:38} {n} layer(s)")
    print(f"\n{written} ledger entries written across {len(papers())} papers")
    return 0


def _git_date(rel: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", rel],
            cwd=base_of(rel), capture_output=True, text=True, timeout=10).stdout.strip()
        return out[:19] + "Z" if out else None
    except Exception:                                                  # noqa: BLE001
        return None


GLYPH = {CURRENT: "✓", STALE: "~", ABSENT: "·", BLOCKED: "!",
         NA: "—", OPEN: "?", "unrecorded": "u"}


def cmd_state(args) -> int:
    decl = load()
    st = state(decl)
    paper_layers = [lid for lid, l in decl["by_id"].items() if l.get("scope") != "corpus"]

    if args.json:
        print(json.dumps(st, indent=2, sort_keys=True))
        return 0

    head = "".join(f"{lid[:7]:>9}" for lid in paper_layers)
    print(f"{'paper':26}{head}")
    for paper, cells in st.items():
        row = "".join(f"{GLYPH.get(cells[lid]['state'], '?'):>9}" for lid in paper_layers)
        print(f"{paper[:25]:26}{row}")

    counts = {}
    for cells in st.values():
        for lid in paper_layers:
            counts[cells[lid]["state"]] = counts.get(cells[lid]["state"], 0) + 1
    print("\n  " + "  ".join(f"{GLYPH.get(k,'?')} {k} {v}" for k, v in sorted(counts.items())))

    stale = [(p, lid, c[lid]) for p, c in st.items() for lid in paper_layers
             if c[lid]["state"] == STALE]
    if stale:
        # Grouped by cause, because the causes call for different actions: a changed input
        # means re-run and expect a different answer; a changed machinery means re-run and
        # the answer may be identical; a record that cannot name its machinery means re-run
        # to get one, and nothing can be concluded about it until then (issue #2).
        by_cause: dict[str, list[str]] = {"input": [], "machinery": [], "unrecorded": []}
        for p, lid, cell in stale:
            for path in (cell.get("moved") or [])[:3]:
                by_cause["input"].append(f"  {p} · {lid}  ←  {path}")
            for path in (cell.get("lost") or [])[:3]:
                by_cause["input"].append(f"  {p} · {lid}  ←  {path} (output gone)")
            for what in (cell.get("drift") or [])[:3]:
                by_cause["machinery"].append(f"  {p} · {lid}  ←  {what}")
            for path in (cell.get("absent") or [])[:2]:
                by_cause["unrecorded"].append(f"  {p} · {lid}  ←  {path} (not in this graph)")

        print(f"\n{len(stale)} stale cell(s):")
        if by_cause["input"]:
            print(f"\n  an input moved, vanished or appeared since the run "
                  f"({len(by_cause['input'])}):")
            print("\n".join(by_cause["input"]))
        if by_cause["machinery"]:
            print(f"\n  the machinery is not the one that ran it "
                  f"({len(by_cause['machinery'])}) — the graph did not change:")
            print("\n".join(by_cause["machinery"]))
        if by_cause["unrecorded"]:
            print(f"\n  the run named a machinery path this graph does not hold "
                  f"({len(by_cause['unrecorded'])}) — recorded before the split, so it cannot "
                  f"say which machinery ran:")
            print("\n".join(by_cause["unrecorded"]))
    if args.fail_on_stale and stale:
        return 1
    return 0


def _wanted_waves(wanted: list, by_id: dict) -> list:
    """Partition *wanted* (topological order) into depth-based waves.

    Layers in the same wave have no dependency relationship with each other within the
    wanted set, so they can run concurrently. The partition is: depth 0 has no
    predecessors in wanted; depth k has only depth-(k-1)-or-lower predecessors.

    The resulting list of lists preserves the overall topological order: all layers in
    wave k complete before wave k+1 starts.
    """
    wanted_set = set(wanted)
    depths: dict[str, int] = {}

    def depth_of(lid):
        if lid in depths:
            return depths[lid]
        d = max(
            (depth_of(dep) + 1 for dep in (by_id[lid].get("needs") or []) if dep in wanted_set),
            default=0,
        )
        depths[lid] = d
        return d

    for lid in wanted:
        depth_of(lid)

    if not depths:
        return []
    max_d = max(depths.values())
    return [[lid for lid in wanted if depths[lid] == d] for d in range(max_d + 1)]


def cmd_run(args) -> int:
    """Run a layer for one paper, and its unmet dependencies first.

    The command comes from the declaration, so there is one definition of how a layer is
    produced and the site's copy-and-run text cannot drift from what actually runs. A layer
    already `current` is skipped: re-running it would produce the same bytes and a second
    ledger entry claiming to be a new version.
    """
    decl = load()
    by_id = decl["by_id"]
    if args.layer not in by_id:
        print(f"error: no layer {args.layer!r}", file=sys.stderr)
        return 2
    if args.paper not in papers():
        print(f"error: no paper {args.paper!r}", file=sys.stderr)
        return 2

    # Ask the named layer for the prompt it would send and stop. Nothing is produced, so no
    # ledger entry is written — the answer comes back through `--answer`, which does record a
    # version. The seam every model-answered layer has (`--dump-prompt`/`--answer` on the CLI),
    # reached through `run` so the command is the declared one and cannot drift.
    if getattr(args, "dump_prompt", None):
        layer = by_id[args.layer]
        cmd = layer.get("command")
        if not cmd or "claim_graphs.cli" not in cmd:
            print(f"error: {args.layer} has no model prompt to dump", file=sys.stderr)
            return 3
        cmd = cmd.replace("{paper}", args.paper).replace("{doi}", _doi_of(args.paper) or "")
        cmd += f" --dump-prompt {shlex.quote(args.dump_prompt)}"
        if args.profile:
            cmd += f" --profile {shlex.quote(args.profile)}"
        print(f"  {args.layer}: {cmd}")
        return subprocess.run(cmd, shell=True, cwd=MACHINERY, env=_child_env()).returncode

    st = state(decl, [args.paper])[args.paper]

    # Dependency order, restricted to this layer's ancestors — and pruned at the ones that
    # are already satisfied.
    #
    # Walking *through* a satisfied ancestor rebuilds a subtree nothing is waiting for. That
    # was harmless while the induction layers declared no command, because each one printed
    # "no runner declared" and was skipped; now that they run, asking for `coverage` on a
    # paper whose claim tree is current would re-run induction underneath it — three reader
    # calls, a reconciliation and an Opus review, to rebuild inputs to a file that is already
    # correct. A satisfied ancestor is a leaf, which is what make has always done.
    #
    # Satisfied means the outputs are there and nothing says they are wrong: `current`, or
    # `unrecorded` — produced before the ledger existed, and consistent with what it was
    # built from as far as anything can tell. `stale` and `blocked` are rebuilt.
    SATISFIED = (CURRENT, "unrecorded")
    wanted, seen = [], set()

    def walk(lid, target=False):
        if lid in seen:
            return
        seen.add(lid)
        if not target and st.get(lid, {}).get("state") in SATISFIED:
            return
        for dep in by_id[lid].get("needs") or []:
            walk(dep)
        wanted.append(lid)

    walk(args.layer, target=True)
    if args.no_deps:
        wanted = [args.layer]

    doi = _doi_of(args.paper)
    ran = 0
    jobs = getattr(args, "jobs", 1)

    def _prepare_one(lid):
        """Check skip conditions and build the shell command for one layer.

        Returns a dict with keys:
          skip:   True if the layer should not run (or None for fatal skips)
          fatal:  True if the skip is a caller error (return code 3)
          cmd:    the shell command string (None when skip=True)
          answered_kept: path of the kept answer file (None when not --answer)
        """
        layer = by_id[lid]
        if layer.get("scope") == "corpus":
            return {"skip": True, "fatal": False, "cmd": None, "answered_kept": None}
        cur = st.get(lid, {}).get("state")
        if lid != args.layer and cur == CURRENT:
            return {"skip": True, "fatal": False, "cmd": None, "answered_kept": None}
        if layer.get("requires_human"):
            print(f"  {lid}: requires a person — not runnable from here")
            return {"skip": True, "fatal": lid == args.layer, "cmd": None, "answered_kept": None}
        cmd = layer.get("command")
        if not cmd:
            print(f"  {lid}: no runner declared — skipping"
                  f"{' (this is the layer you asked for)' if lid == args.layer else ''}")
            return {"skip": True, "fatal": lid == args.layer, "cmd": None, "answered_kept": None}

        cmd = cmd.replace("{paper}", args.paper).replace("{doi}", doi or "")
        # A profile travels to the command that understands it. The declared commands that
        # call a model go through `claim_graphs.cli`, which takes `--profile`; the others
        # (article_json.py, prediction_outcome.py) do not, so the flag is appended only to the
        # former. The ledger's `by` records the profile too, below.
        if getattr(args, "profile", None) and "claim_graphs.cli" in cmd:
            cmd += f" --profile {shlex.quote(args.profile)}"
        # An answer made somewhere other than the configured backend — a subagent, a person —
        # goes through the same runner and the same validation, so the ledger records it the
        # same way. Before this the answered path could only be taken by calling the CLI by
        # hand, which recorded nothing, and the first end-to-end run of the chain had to live
        # in experiments/ because the ledger could not hold it.
        answered = args.answer if lid == args.layer and args.answer else None
        answered_kept = None
        if answered:
            # The raw reply is kept beside the output, before validation and under the
            # version it will get: a verdict whose prompt and output are not both recorded
            # cannot be disputed, and the prompt is already hashed through `reads`. The CLI
            # is handed the kept copy, so the output's `model` field names a path in the
            # repository rather than wherever the reply happened to be written.
            prev = _latest(read_ledger(args.paper), lid)
            answered_kept = os.path.join(
                "runs", args.paper,
                f"{lid}.answer.v{(prev['v'] + 1) if prev else 1}.json",
            )
            os.makedirs(os.path.dirname(os.path.join(ROOT, answered_kept)), exist_ok=True)
            shutil.copyfile(answered, os.path.join(ROOT, answered_kept))
            cmd += f" --answer {shlex.quote(answered_kept)}"
        print(f"  {lid}: {cmd}")
        return {"skip": False, "fatal": False, "cmd": cmd, "answered_kept": answered_kept}

    def _run_one(lid, prep):
        """Run a prepared layer's command. Returns (rc, lid)."""
        env = _child_env()
        if getattr(args, "tokens", None):
            env[ANSWERED_TOKENS_ENV] = str(args.tokens)
        rc = subprocess.run(prep["cmd"], shell=True, cwd=MACHINERY, env=env).returncode
        return rc, lid

    for wave in _wanted_waves(wanted, by_id):
        # Prepare every layer in this wave (skip checks, build cmds).
        preps = {lid: _prepare_one(lid) for lid in wave}

        # Check for fatal skips before launching anything.
        for lid in wave:
            if preps[lid]["fatal"]:
                return 3

        # Collect the runnable layers (not skipped, not dry-run).
        runnable = [lid for lid in wave if not preps[lid]["skip"]]
        if args.dry_run or not runnable:
            continue

        # Run the wave — concurrently when jobs > 1 and the wave has multiple layers.
        results: dict[str, int] = {}  # lid -> returncode
        if jobs > 1 and len(runnable) > 1:
            with ThreadPoolExecutor(max_workers=min(jobs, len(runnable))) as pool:
                futures = {pool.submit(_run_one, lid, preps[lid]): lid for lid in runnable}
                for fut in as_completed(futures):
                    rc, lid = fut.result()
                    results[lid] = rc
        else:
            for lid in runnable:
                rc, _ = _run_one(lid, preps[lid])
                results[lid] = rc

        # Write ledger entries in deterministic (wanted) order after all subprocesses finish.
        # This ensures no interleaving even when the wave ran in parallel.
        for lid in wave:
            if lid not in results:
                continue
            rc = results[lid]
            if rc != 0:
                print(f"  {lid}: exited {rc}", file=sys.stderr)
                return rc
            layer = by_id[lid]
            rec = record(args.paper, layer, by_id,
                         note=args.note or "ran via scripts/pipeline.py",
                         by="scripts/pipeline.py run", doi=doi)
            # The command is the record. Deriving `by` from its first token gave "cd" for
            # every layer whose command starts by changing directory.
            rec["cmd"] = preps[lid]["cmd"]
            answered_kept = preps[lid]["answered_kept"]
            if answered_kept:
                rec["answer"] = {"path": answered_kept, "sha": digest(answered_kept)}
                # The output can only say the answer was supplied; who supplied it is known
                # to whoever ran this, and is the fact the ledger exists to keep.
                if args.by:
                    rec["by"] = args.by
            # The profile is the other half of who answered: `<model> · <profile>`. The model
            # came from the output (via `by_from`) or from --by; the profile is appended here,
            # unless it is already the tail of `by` (a re-run of the same command).
            if getattr(args, "profile", None) and rec.get("by"):
                tail = f" · {args.profile}"
                if not str(rec["by"]).endswith(tail):
                    rec["by"] = f"{rec['by']}{tail}"
            append(args.paper, rec)
            # Keep this version's bytes addressable for the site's two-version comparison.
            # Only single files under runs/; claims/ archives itself into claim-tree.v<N>/.
            for kept in keep_versions(rec):
                print(f"  {lid}: kept {kept}")
            ran += 1

    print(f"\n{ran} layer(s) run" + (" (dry run)" if args.dry_run else ""))
    return 0


def cmd_approve(args) -> int:
    """Record that a person read one version of one layer and approved it.

    The counterpart to `run`, and the half that was missing: `approve()` and the reporting
    in `state()` were both written, and nothing could call them, so approvals.jsonl could
    only be written by hand and every cell in the corpus reads unapproved.

    Approval names a version. It defaults to the version currently on the ledger, because
    approving a version that is not the one on disk is almost always a mistake — but it can
    be named explicitly, since reading v2 and recording it after v3 has run is a coherent
    thing to have done.

    With `--declaration` it is the other kind of decision: a scheme ruling on what a layer
    means, recorded against the declaration's version in the corpus-level ledger.
    """
    if args.declaration:
        return cmd_approve_declaration(args)
    if args.claim:
        return cmd_approve_claim(args)
    if not args.paper or not args.layer:
        print("error: approve needs <paper> <layer>, or --declaration <layer>",
              file=sys.stderr)
        return 2
    decl = load()
    if args.layer not in decl["by_id"]:
        print(f"error: no layer {args.layer!r}", file=sys.stderr)
        return 2
    if args.paper not in papers():
        print(f"error: no paper {args.paper!r}", file=sys.stderr)
        return 2

    run = _latest(read_ledger(args.paper), args.layer)
    if not run:
        print(f"error: {args.layer} has never run for {args.paper} — "
              f"there is no version to approve", file=sys.stderr)
        return 3

    v = args.v if args.v is not None else run["v"]
    if v > run["v"]:
        print(f"error: {args.layer} is at v{run['v']}; cannot approve v{v}", file=sys.stderr)
        return 3

    rec = approve(args.paper, args.layer, v, by=args.by, note=args.note or "")
    current = " (the current version)" if v == run["v"] else \
              f" (superseded — the ledger is at v{run['v']})"
    print(f"{args.paper}/{args.layer} v{v} approved by {rec['by']}{current}")
    if rec["note"]:
        print(f"  {rec['note']}")
    return 0


def cmd_approve_claim(args) -> int:
    """Approve one claim, or every claim in a paper with --claim all.

    The two grains answer different questions and are worth holding apart. A claim-tree
    approval says the argument is a fair reading of the paper; a claim approval says this
    proposition is true of it. Someone can reasonably grant either without the other.
    """
    if not args.paper:
        print("error: approve --claim needs <paper>", file=sys.stderr)
        return 2
    if args.paper not in papers():
        print(f"error: no paper {args.paper!r}", file=sys.stderr)
        return 2

    if args.claim == "all":
        slugs = sorted(os.path.splitext(os.path.basename(f))[0]
                       for f in glob.glob(os.path.join(CLAIMS, args.paper, "*.md"))
                       if os.path.basename(f) != "index.md")
    else:
        slugs = [args.claim]

    standing = read_claim_approvals(args.paper)
    done = skipped = 0
    for slug in slugs:
        if not os.path.isfile(claim_path(args.paper, slug)):
            print(f"error: no claim {slug!r} in {args.paper}", file=sys.stderr)
            return 2
        prior = standing.get(slug)
        if prior and prior.get("applies") and not args.again:
            skipped += 1
            continue
        rec = approve_claim(args.paper, slug, by=args.by, note=args.note or "")
        done += 1
        if len(slugs) == 1:
            print(f"approved {slug} @ {rec['hash']} — by {rec['by']} on {rec['when'][:10]}")
    if len(slugs) > 1:
        print(f"approved {done} claim(s) in {args.paper}"
              + (f"; {skipped} already stood (use --again to re-approve)" if skipped else ""))
    return 0


def cmd_approve_declaration(args) -> int:
    """Record a scheme ruling: a person accepts what a layer — or a versioned design note — means.

    A layer is keyed on its declaration version; a design note in `DOC_DECLARATIONS` (the
    adjudication procedure) is keyed on the note's own content hash, the same `digest`.
    """
    lid = args.declaration
    if lid.startswith("canon/"):
        concept = lid[len("canon/"):]
        ver = _canon_entry_version(concept)
        if ver is None:
            print(f"error: no canon concept {concept!r}", file=sys.stderr)
            return 2
    elif lid in DOC_DECLARATIONS:
        ver = digest(DOC_DECLARATIONS[lid])
        if ver is None:
            print(f"error: {DOC_DECLARATIONS[lid]} does not exist", file=sys.stderr)
            return 2
    else:
        decl = load()
        if lid not in decl["by_id"]:
            print(f"error: no layer {lid!r}", file=sys.stderr)
            return 2
        ver = declaration_version(decl["by_id"][lid])
        was = declaration_state(decl)[lid]
        if was["scheme"] == ACCEPTED:
            print(f"{lid}: declaration {ver} is already accepted by {was['approved']['by']} — "
                  f"recording another ruling on the same version")
    rec = approve_declaration(lid, ver, by=args.by, note=args.note or "")
    print(f"{lid} declaration {ver} accepted by {rec['by']}")
    if rec["note"]:
        print(f"  {rec['note']}")
    return 0


def _doi_of(paper: str) -> str | None:
    """The paper's DOI, from its claim-tree index."""
    p = os.path.join(ROOT, "claims", paper, "index.md")
    if not os.path.isfile(p):
        return None
    import re
    m = re.search(r"^doi:\s*(\S+)", open(p, encoding="utf-8").read(), re.M)
    return m.group(1).strip("'\"") if m else None


# ── agent mode ────────────────────────────────────────────────────────────────
#
# `run` assumes something will answer a model call when the command reaches a backend. An
# agent answering the layers itself has no backend, and the three-step loop it must perform
# instead — dump the prompt, answer it, record the answer — was written down in prose and
# performed by hand. Prose is not a mechanism: the first end-to-end subagent run was eighteen
# steps an operator read off a page, and every one of them was a chance to use the wrong path,
# skip a layer, or answer two independent readers in one context.
#
# So the loop is a command. `agent` walks the same declaration `run` walks, executes every
# layer that needs no model, and stops at the first that does — leaving the exact prompt on
# disk and saying where to put the answer. Called again, it finds the answer, records it
# through `run` (the same validation, the same ledger), and carries on. The caller repeats one
# command until it says done, and never needs to know what the layers are.
#
# Exit codes are the protocol: 0 done, 10 a prompt is waiting, 11 an answer was refused.

AGENT_WAITING, AGENT_REFUSED = 10, 11

class _stdout_to_stderr:
    """Everything a child says goes to stderr, so stdout carries only the JSON.

    `--json` is a machine contract: the caller parses stdout. The layer commands underneath
    print their own progress, and a subprocess writes to the file descriptor rather than to
    `sys.stdout`, so redirecting the Python object is not enough — the descriptor itself has
    to move. Without this the first agent-mode run emitted a prompt path and a progress line
    in front of the JSON and nothing could parse it.
    """

    def __init__(self, active: bool):
        self.active = active

    def __enter__(self):
        if self.active:
            sys.stdout.flush()
            self.saved = os.dup(1)
            os.dup2(2, 1)
        return self

    def __exit__(self, *exc):
        if self.active:
            sys.stdout.flush()
            os.dup2(self.saved, 1)
            os.close(self.saved)
        return False




def agent_dir(paper: str) -> str:
    """Where a prompt waiting for an answer lives — in the graph, beside its run."""
    return os.path.join(ROOT, "runs", paper, "agent")


def _agent_paths(paper: str, lid: str) -> tuple[str, str, str]:
    d = agent_dir(paper)
    return (os.path.join(d, f"{lid}.prompt.txt"),
            os.path.join(d, f"{lid}.answer.json"),
            os.path.join(d, f"{lid}.answer.recorded.json"))


def _agent_args(paper: str, lid: str, **kw):
    """A `run` invocation for one layer, with every flag cmd_run reads."""
    base = dict(paper=paper, layer=lid, no_deps=True, dry_run=False, jobs=1,
                note=None, tokens=None, dump_prompt=None, answer=None, by=None,
                profile=None)
    base.update(kw)
    return argparse.Namespace(**base)


def _agent_emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    st = payload["status"]
    if st == "done":
        print(f"  done — {payload['layer']} is current for {payload['paper']}")
        return
    if st == "waiting":
        print(f"\n  {payload['layer']}: needs an answer")
        print(f"    question   {payload['question']}")
        print(f"    prompt     {payload['prompt']}")
        print(f"    answer to  {payload['answer']}")
        print(f"    then       {payload['next']}")
        if payload.get("independent"):
            print(f"    NOTE       {payload['independent']}")
        return
    if st == "refused":
        print(f"\n  {payload['layer']}: the answer was refused — rewrite "
              f"{payload['answer']} and run the same command again")


def cmd_agent(args) -> int:
    """Drive the chain one layer at a time, stopping wherever a model has to answer."""
    decl = load()
    by_id = decl["by_id"]
    if args.layer not in by_id:
        print(f"error: no layer {args.layer!r}", file=sys.stderr)
        return 2
    if args.paper not in papers():
        print(f"error: no paper {args.paper!r}", file=sys.stderr)
        return 2

    st = state(decl, [args.paper])[args.paper]
    SATISFIED = (CURRENT, "unrecorded")
    wanted, seen = [], set()

    def walk(lid, target=False):
        if lid in seen:
            return
        seen.add(lid)
        if not target and st.get(lid, {}).get("state") in SATISFIED:
            return
        for dep in by_id[lid].get("needs") or []:
            walk(dep)
        wanted.append(lid)

    walk(args.layer, target=True)

    os.makedirs(agent_dir(args.paper), exist_ok=True)
    profile = args.profile or "subagent"

    for lid in wanted:
        layer = by_id[lid]
        if layer.get("scope") == "corpus" or not layer.get("command"):
            continue
        if lid != args.layer and st.get(lid, {}).get("state") in SATISFIED:
            continue

        prompt, answer, recorded = _agent_paths(args.paper, lid)

        # A layer no model answers is just run.
        if not layer.get("by_from"):
            with _stdout_to_stderr(args.json):
                rc = cmd_run(_agent_args(args.paper, lid, note=args.note,
                                         profile=args.profile))
            if rc:
                return rc
            continue

        # One a model answers: record the answer if it is there, otherwise ask for it.
        if os.path.isfile(answer) and os.path.getsize(answer):
            with _stdout_to_stderr(args.json):
                rc = cmd_run(_agent_args(args.paper, lid, answer=answer, by=args.by,
                                         tokens=args.tokens, note=args.note,
                                         profile=args.profile))
            if rc:
                _agent_emit({"status": "refused", "paper": args.paper, "layer": lid,
                             "answer": answer}, args.json)
                return AGENT_REFUSED
            os.replace(answer, recorded)
            continue

        with _stdout_to_stderr(args.json):
            rc = cmd_run(_agent_args(args.paper, lid, dump_prompt=prompt, profile=profile))
        if rc:
            return rc
        me = os.path.relpath(os.path.abspath(__file__), os.getcwd())
        payload = {
            "status": "waiting",
            "paper": args.paper,
            "layer": lid,
            "question": " ".join(str(layer.get("question", "")).split()),
            "prompt": prompt,
            "answer": answer,
            "next": f"python3 {me} agent {args.paper} {args.layer}",
            "remaining": [l for l in wanted[wanted.index(lid):] if by_id[l].get("by_from")],
        }
        if lid in READER_LAYERS:
            payload["independent"] = (
                "a reader: answer it in its own context, having seen no other reader's "
                "prompt or answer — reconcile grades a claim by how many readers "
                "independently surfaced it")
        _agent_emit(payload, args.json)
        return AGENT_WAITING

    _agent_emit({"status": "done", "paper": args.paper, "layer": args.layer}, args.json)
    return 0


# The layers whose independence the confidence grade is computed from. Named here rather than
# inferred, because "is a reader" is a fact about what reconcile does with them.
READER_LAYERS = ("results-reader", "caption-reader", "structure-reader")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("graph", help="print the declared DAG").set_defaults(fn=cmd_graph)
    b = sub.add_parser("backfill", help="write ledgers from existing artifacts")
    b.add_argument("--force", action="store_true", help="rewrite ledgers that already exist")
    b.set_defaults(fn=cmd_backfill)
    s = sub.add_parser("state", help="the paper x layer matrix")
    s.add_argument("--json", action="store_true")
    s.add_argument("--fail-on-stale", action="store_true", help="exit non-zero if any cell is stale")
    s.set_defaults(fn=cmd_state)
    a = sub.add_parser(
        "agent", help="drive the chain, stopping wherever a model has to answer")
    a.add_argument("paper")
    a.add_argument("layer", help="the layer to reach, e.g. claim-tree")
    a.add_argument("--by", help="who answers, recorded in the ledger")
    a.add_argument("--tokens", type=int, metavar="N",
                   help="what the answering session spent, for the record")
    a.add_argument("--note", help="the changelog line for each ledger entry")
    a.add_argument("--profile", help="model profile (default: subagent)")
    a.add_argument("--json", action="store_true", help="emit the step as JSON")
    a.set_defaults(fn=cmd_agent)

    r = sub.add_parser("run", help="run a layer for one paper, and its unmet dependencies")
    r.add_argument("paper")
    r.add_argument("layer")
    r.add_argument("--no-deps", action="store_true", help="run only the named layer")
    r.add_argument("--dry-run", action="store_true", help="print the commands, run nothing")
    r.add_argument("--jobs", type=int, default=3, metavar="N",
                   help="max concurrent layer commands within a wave (default: 3)")
    r.add_argument("--note", help="the changelog line for the ledger entry")
    r.add_argument("--tokens", type=int, metavar="N",
                   help="what the session that answered this layer spent. Every layer here is "
                        "answered outside the configured backend, so the usage the call path "
                        "records is zero and the ledger knew how the answer arrived but not "
                        "what it cost. The declared command is fixed, so this reaches the "
                        "runner through the environment.")
    r.add_argument("--dump-prompt", metavar="PATH",
                   help="write the exact prompt the named layer would send to PATH and exit, so "
                        "whatever answers it answers the same question. Nothing is run or "
                        "recorded; hand the reply back with --answer.")
    r.add_argument("--answer", metavar="FILE",
                   help="record this file as the named layer's answer instead of calling a "
                        "backend; the raw reply is kept beside the output as a version")
    r.add_argument("--by", help="with --answer: who answered, e.g. the model of the subagent")
    r.add_argument("--profile", help="model profile to pass through to each layer command "
                   "(frontier, standard, open, subagent). The ledger's `by` records it.")
    r.set_defaults(fn=cmd_run)
    a = sub.add_parser("approve", help="approve one paper's output, or a layer's declaration")
    a.add_argument("paper", nargs="?", help="the paper (omit with --declaration)")
    a.add_argument("layer", nargs="?", help="the layer (omit with --declaration)")
    a.add_argument("--declaration", metavar="LAYER",
                   help="record a scheme ruling on this layer's declaration instead")
    a.add_argument("--claim", metavar="SLUG",
                   help="approve one claim instead of a layer, or `all` for every claim in the "
                        "paper. A claim approval names the claim's content hash rather than a "
                        "version, so it survives a re-run that leaves the claim saying the same "
                        "thing and lapses when it does not.")
    a.add_argument("--again", action="store_true",
                   help="re-approve claims whose approval already stands")
    a.add_argument("--by", required=True, help="who decided")
    a.add_argument("--v", type=int, help="which version (default: the one on the ledger)")
    a.add_argument("--note", help="what they checked")
    a.set_defaults(fn=cmd_approve)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
