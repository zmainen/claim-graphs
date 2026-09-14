"""`canon --render`: one standalone HTML page from the canon and the toy study.

In the register of the design pages built this week (IBM Plex, the token palette, light and dark
via `prefers-color-scheme` and `data-theme`, fonts from Google with fallbacks, no external
scripts): a masthead with the canon version and what changed since the previous committed render;
one card per concept with its definition, distinctions, enforcement, its toy example opened in
place with `<details>`, and its references; the toy study rendered as modules with clusters
folded, in each of the four ways; and, when `CLAIM_GRAPHS_ROOT` is set, per concept the count of
corpus instances and which runs were made under which canon version.

`--check` holds the committed page equal to the rendered one. "Changed since" is diffed against
a committed baseline (`docs/canon.baseline.json`) rather than against the page being checked, so
the render is a pure function of the entries and the baseline and the check is stable; a human
resets the baseline deliberately with `--bless`.
"""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from . import canon_version, entries, ROOT as CANON_ROOT, TOY_STUDY, TOY_PAPER
from .entries import ACCEPTED_DECLARATIONS

REPO = CANON_ROOT.parent
PAGE = REPO / "docs" / "canon.html"
BASELINE = REPO / "docs" / "canon.baseline.json"


def _esc(s) -> str:
    return html.escape(str(s), quote=False)


def _entry_digest(e: dict) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(e, sort_keys=True, default=str).encode()).hexdigest()[:8]


def snapshot() -> dict:
    """The per-entry digests and version — what the baseline records and the changelog diffs."""
    return {"version": canon_version(),
            "entries": {eid: _entry_digest(e) for eid, e in entries().items()}}


def _changelog(baseline: dict | None) -> tuple[str, list[str]]:
    now = snapshot()
    if not baseline:
        return now["version"], ["first render"]
    prev = baseline.get("entries", {})
    added = sorted(set(now["entries"]) - set(prev))
    removed = sorted(set(prev) - set(now["entries"]))
    changed = sorted(e for e in now["entries"] if e in prev and now["entries"][e] != prev[e])
    lines = []
    if baseline.get("version") == now["version"]:
        lines.append(f"unchanged since {baseline['version']}")
    for e in added:
        lines.append(f"added {e}")
    for e in changed:
        lines.append(f"changed {e}")
    for e in removed:
        lines.append(f"removed {e}")
    return now["version"], lines or [f"unchanged since {baseline['version']}"]


# ── corpus instance counts (when a graph is present) ─────────────────────────


def _corpus_counts() -> dict[str, int] | None:
    """Per concept, how many corpus instances — relations by edge, roles by claim role.

    Only what a mechanical read of the claim files gives: relation entries count edges of that
    relation, role entries count claims of that role. Returns None with no graph.
    """
    root = os.environ.get("CLAIM_GRAPHS_ROOT")
    claims = os.environ.get("CLAIM_GRAPHS_CORPUS_DIR") or (root and str(Path(root) / "claims"))
    if not claims or not Path(claims).is_dir():
        return None
    code = (
        "import os,sys,json,collections; sys.path.insert(0,'scripts');"
        "from export_mira import public_papers, load_paper, relations;"
        "rc=collections.Counter(); ro=collections.Counter();"
        "pp=public_papers();"
        "\nfor p in pp:\n"
        " for c in load_paper(p):\n"
        "  ro[c.get('role')]+=1\n"
        "  for k,_ in relations(c): rc[k]+=1\n"
        "print(json.dumps({'rel':dict(rc),'role':dict(ro)}))")
    try:
        out = subprocess.run([sys.executable, "-c", code], cwd=str(REPO),
                             capture_output=True, text=True, env=dict(os.environ))
        if out.returncode != 0:
            return None
        d = json.loads(out.stdout)
    except Exception:                                              # noqa: BLE001
        return None
    counts: dict[str, int] = {}
    for name, n in d.get("rel", {}).items():
        counts[f"relation:{name}"] = n
    for name, n in d.get("role", {}).items():
        if name:
            counts[f"role:{name}"] = n
    return counts


def _runs_by_canon_version() -> list[tuple[str, str, str]] | None:
    """(paper, layer, canon-version) for ledger entries that recorded a canon version."""
    root = os.environ.get("CLAIM_GRAPHS_ROOT")
    if not root:
        return None
    out = []
    runs = Path(root) / "runs"
    for led in sorted(runs.glob("*/ledger.jsonl")):
        paper = led.parent.name
        for line in led.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("canon"):
                out.append((paper, rec.get("layer", "?"), rec["canon"]))
    return out or None


# ── the toy study, four ways ─────────────────────────────────────────────────


def _toy_modules() -> dict:
    code = ("import sys,json; sys.path.insert(0,'scripts'); import modules;"
            "print(json.dumps(modules.build('%s')[0]))" % TOY_PAPER)
    env = dict(os.environ, CLAIM_GRAPHS_ROOT=str(TOY_STUDY),
               CLAIM_GRAPHS_CORPUS_DIR=str(TOY_STUDY / "claims"))
    out = subprocess.run([sys.executable, "-c", code], cwd=str(REPO), env=env,
                         capture_output=True, text=True)
    return json.loads(out.stdout)


def _cluster_html(c: dict) -> str:
    results = ", ".join(f"<code>{_esc(r)}</code>" for r in c["results"]) or "—"
    parts = ", ".join(c["combine"]["parts"]) or "—"
    return (f"<details class='cluster'><summary><code>{_esc(c['finding'])}</code> "
            f"<span class='muted'>· {len(c['results'])} results, folded</span></summary>"
            f"<div class='cluster-body'><p class='muted'>results: {results}</p>"
            f"<p class='muted'>combine · parts: {_esc(parts)}</p></div></details>")


def _module_html(m: dict) -> str:
    out = [f"<div class='mod'><div class='mod-head'><span class='chip c-q'>{_esc(m['kind'])}"
           f"</span> <b>{_esc(m.get('question') or m.get('summary') or m['id'])}</b></div>"]
    if m["kind"] == "question":
        out.append(f"<p class='muted'>hypothesis: <code>{_esc(m['hypotheses'][0])}</code></p>")
        for a in m["alternatives"]:
            out.append(f"<p class='muted'>alternative <code>{_esc(a['slug'])}</code> — eliminated "
                       f"by {', '.join(f'<code>{_esc(x)}</code>' for x in a['eliminated_by'])}</p>")
        clusters = {}
        for p in m["predictions"]:
            out.append(f"<p class='muted'>prediction <code>{_esc(p['prediction'])}</code> — "
                       f"<b>{_esc(p['outcome'])}</b></p>")
            for f in p["findings"]:
                clusters[f["finding"]] = f
        for f in m["findings"]:
            clusters[f["finding"]] = f
        for c in clusters.values():
            out.append(_cluster_html(c))
        out.append(f"<p class='muted'>domain: {', '.join(f'<code>{_esc(x)}</code>' for x in m['domain']) or '—'} · "
                   f"apparatus: {', '.join(f'<code>{_esc(x)}</code>' for x in m['apparatus']) or '—'}</p>")
    else:
        out.append(_cluster_html(m["finding"]))
    out.append("</div>")
    return "\n".join(out)


def _four_ways_html() -> str:
    mods = _toy_modules()
    design = (TOY_STUDY / "design.yaml").read_text(encoding="utf-8")
    manifest = json.loads((TOY_STUDY / "analysis" / "manifest.json").read_text(encoding="utf-8"))
    verdict = json.loads((TOY_STUDY / "review" / "verdict.json").read_text(encoding="utf-8"))
    induced = "\n".join(_module_html(m) for m in mods["modules"])
    if mods.get("loose"):
        induced += ("<p class='muted'>loose: " +
                    ", ".join(f"<code>{_esc(it['slug'])}</code>" for it in mods["loose"]) + "</p>")

    def block(title, note, body):
        return (f"<div class='way'><h3>{_esc(title)}</h3><p class='sec-note'>{_esc(note)}</p>"
                f"{body}</div>")

    derived_rows = "".join(
        f"<li><code>{_esc(r['slug'])}</code> — {_esc(r.get('value',''))} "
        f"<span class='muted'>({_esc(r.get('panel','—'))}, {_esc(r.get('script','—'))})</span></li>"
        for r in manifest["results"])
    v_rows = "".join(
        f"<li><code>{_esc(v['slug'])}</code> — {_esc(v['verdict'])}"
        + (f", warrant <b>{_esc(v['warrant'])}</b>" if v.get('warrant') else "")
        + f" <span class='muted'>{_esc(v.get('why',''))}</span></li>"
        for v in verdict["claim_verdicts"])
    return (
        block("Induced", "the written-up study read into claim files and derived into modules — "
              "the argument grain shown, the finding clusters folded", induced) +
        block("Composed", "what the design commits to before any result exists — the question, "
              "the hypothesis, the rival, the prediction and the control it owes",
              f"<pre>{_esc(design)}</pre>") +
        block("Derived", "the analysis results with provenance, folding under the finding they "
              "bear on", f"<ul>{derived_rows}</ul>") +
        block("Asserted about", "the review's verdicts, warrant, the caveat, the tension, the "
              "observation and the loose claim",
              f"<ul>{v_rows}</ul><p class='muted'>observation: "
              f"<code>{_esc(verdict['observations'][0])}</code> · loose: "
              f"<code>{_esc(verdict['loose'][0]['slug'])}</code> — "
              f"{_esc(verdict['loose'][0]['reason'])}</p>"))


# ── the page ─────────────────────────────────────────────────────────────────


def _card(eid: str, e: dict, count: int | None) -> str:
    status = e["status"]
    parts = [f"<article class='card' id='{_esc(eid)}'>",
             f"<div class='card-head'><h3><code>{_esc(eid)}</code></h3>"
             f"<span class='chip c-{status}'>{status}</span>",
             (f"<span class='count'>{count} in corpus</span>" if count is not None else ""),
             "</div>",
             f"<p>{_esc(e['definition'])}</p>"]
    if e.get("distinct_from"):
        parts.append("<div class='distinct'><b>Distinct from</b><ul>")
        for other, why in e["distinct_from"]:
            parts.append(f"<li><code>{_esc(other)}</code> — {_esc(why)}</li>")
        parts.append("</ul></div>")
    parts.append(f"<p class='muted'><b>Enforced by</b> {_esc(e['enforced_by'])}</p>")
    if e.get("operations"):
        parts.append(f"<p class='muted'><b>Operations</b> {_esc(e['operations'])}</p>")
    exj = e["example"]
    parts.append(f"<details class='example'><summary>Example — {_esc(exj['stage'])}</summary>"
                 f"<p><code>{_esc(exj['ref'])}</code></p></details>")
    refs = e.get("references") or {}
    if refs:
        bits = []
        if refs.get("note"):
            bits.append(f"note <code>{_esc(refs['note'])}</code>")
        if refs.get("corpus"):
            bits.append(f"corpus <code>{_esc(refs['corpus'])}</code>")
        parts.append(f"<p class='refs muted'>{' · '.join(bits)}</p>")
    parts.append("</article>")
    return "\n".join(parts)


STYLE = """
:root{--ground:#f4f4f2;--surface:#fbfbfa;--surface-2:#ecedea;--ink:#1b1d1c;--ink-2:#4a4e4b;
--ink-3:#767b77;--rule:#d9dbd6;--rule-firm:#b9bcb6;--accent:#8a5a12;--accent-soft:#f0e6d4;
--accepted:#2f6f46;--accepted-bg:#e3efe6;--proposed:#9a6b0f;--proposed-bg:#f7ecd6;
--move:#3d5a80;--move-bg:#e0e7ef;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ground:#121413;
--surface:#1a1d1b;--surface-2:#232725;--ink:#e9ebe8;--ink-2:#b3b8b3;--ink-3:#838883;
--rule:#2e332f;--rule-firm:#454b46;--accent:#d9a35c;--accent-soft:#34291a;--accepted:#6fbc8c;
--accepted-bg:#1c2c22;--proposed:#d8ab52;--proposed-bg:#2e2618;--move:#8fb0d4;--move-bg:#1b242e;}}
:root[data-theme="dark"]{--ground:#121413;--surface:#1a1d1b;--surface-2:#232725;--ink:#e9ebe8;
--ink-2:#b3b8b3;--ink-3:#838883;--rule:#2e332f;--rule-firm:#454b46;--accent:#d9a35c;
--accent-soft:#34291a;--accepted:#6fbc8c;--accepted-bg:#1c2c22;--proposed:#d8ab52;
--proposed-bg:#2e2618;--move:#8fb0d4;--move-bg:#1b242e;}
*{box-sizing:border-box;}
body{background:var(--ground);color:var(--ink);font-family:"IBM Plex Sans",system-ui,sans-serif;
font-size:15.5px;line-height:1.62;-webkit-font-smoothing:antialiased;margin:0;}
.wrap{max-width:1100px;margin:0 auto;padding:0 28px 96px;}
header.mast{padding:60px 0 32px;border-bottom:2px solid var(--ink);margin-bottom:44px;}
.kicker{font-family:"IBM Plex Mono",monospace;font-size:11.5px;letter-spacing:.14em;
text-transform:uppercase;color:var(--accent);margin:0 0 16px;}
h1{font-family:"IBM Plex Serif",Georgia,serif;font-weight:600;font-size:clamp(2rem,4.4vw,2.95rem);
line-height:1.08;letter-spacing:-.018em;margin:0 0 18px;}
.standfirst{font-size:18px;line-height:1.55;color:var(--ink-2);max-width:62ch;margin:0;}
.status{display:flex;flex-wrap:wrap;gap:8px 26px;margin-top:24px;font-family:"IBM Plex Mono",
monospace;font-size:11.5px;color:var(--ink-3);}
.status b{color:var(--ink-2);font-weight:500;letter-spacing:.06em;text-transform:uppercase;
margin-right:6px;}
.changed{margin-top:14px;font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--ink-3);}
.changed span{margin-right:14px;}
section{margin:0 0 58px;}
h2{font-family:"IBM Plex Serif",Georgia,serif;font-size:25px;font-weight:600;margin:44px 0 6px;}
.sec-note{color:var(--ink-3);font-size:14.5px;margin:0 0 26px;max-width:64ch;}
p{margin:0 0 12px;max-width:72ch;}
code{font-family:"IBM Plex Mono",monospace;font-size:.86em;background:var(--surface-2);
padding:.1em .38em;border-radius:2px;}
b,strong{color:var(--ink);font-weight:600;}
.chip{display:inline-block;font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.06em;
text-transform:uppercase;padding:2px 7px;border-radius:2px;white-space:nowrap;}
.c-accepted{background:var(--accepted-bg);color:var(--accepted);}
.c-proposed{background:var(--proposed-bg);color:var(--proposed);}
.c-q{background:var(--move-bg);color:var(--move);}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;}
.card{border:1px solid var(--rule);background:var(--surface);padding:18px 18px 14px;border-radius:3px;}
.card-head{display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-wrap:wrap;}
.card-head h3{margin:0;font-size:15px;font-family:"IBM Plex Sans",sans-serif;}
.count{margin-left:auto;font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--ink-3);}
.distinct{font-size:13.5px;margin:6px 0;}
.distinct ul,.card ul{margin:4px 0 0;padding-left:18px;}
.distinct li{margin:3px 0;color:var(--ink-2);}
.muted{color:var(--ink-3);font-size:13.5px;}
details.example,details.cluster{margin:8px 0;}
summary{cursor:pointer;font-size:13.5px;color:var(--accent);}
pre{background:var(--surface-2);padding:12px 14px;border-radius:3px;overflow-x:auto;font-size:12.5px;
font-family:"IBM Plex Mono",monospace;}
.ways{display:grid;gap:18px;}
.way{border:1px solid var(--rule);background:var(--surface);padding:18px 20px;border-radius:3px;}
.way h3{margin:0 0 4px;font-family:"IBM Plex Serif",serif;}
.mod{border-left:3px solid var(--accent);padding:6px 0 6px 16px;margin:12px 0;}
.mod-head{margin-bottom:6px;}
.cluster-body{padding-left:8px;}
.runs{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--ink-3);}
"""


def render(with_corpus: bool = False) -> str:
    """The page. Corpus-free by default — the committed page ships without a corpus and `--check`
    holds regardless of the ambient environment. `with_corpus=True` enriches a local view with
    per-concept corpus counts and the runs-by-canon-version table; that view is not committed."""
    reg = entries()
    baseline = None
    if BASELINE.is_file():
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    version, changes = _changelog(baseline)
    counts = (_corpus_counts() or {}) if with_corpus else {}
    runs = _runs_by_canon_version() if with_corpus else None

    grains = [("Atoms", ["claim", "assertion", "result", "claim-type"]),
              ("The paper's situation", ["stance", "confidence", "readers", "question"]),
              ("Structure", ["module", "finding-cluster", "scope-domain", "scope-apparatus",
                             "observation", "loose"]),
              ("Assessment", ["warrant", "verification-check"]),
              ("Decision", ["decision:code", "decision:scheme", "decision:adjudication",
                            "decision:run", "adjudication-procedure", "verdict"])]
    placed = {eid for _, ids in grains for eid in ids}
    rel_ids = [k for k in reg if k.startswith("relation:")]
    role_ids = [k for k in reg if k.startswith("role:")]

    out = ['<meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           '<title>The Canon</title>',
           '<link rel="preconnect" href="https://fonts.googleapis.com">',
           '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
           'family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&'
           'family=IBM+Plex+Serif:wght@400;500;600&display=swap">',
           f"<style>{STYLE}</style>", '<div class="wrap">',
           '<header class="mast">',
           '<p class="kicker">claim-graphs · the canon</p>',
           '<h1>One declaration of every concept the system has</h1>',
           '<p class="standfirst">Every concept the machinery relies on — the atom, the relations, '
           'the roles, the module, scope, warrant, the checks, the kinds of decision — defined '
           'once, versioned, and rendered here. A concept not in the canon is not a concept the '
           'system has.</p>',
           '<div class="status">'
           f'<span><b>canon version</b> {_esc(version)}</span>'
           f'<span><b>concepts</b> {len(reg)}</span>'
           f'<span><b>corpus</b> {"attached" if with_corpus and counts else "not attached"}</span></div>',
           '<div class="changed"><b>changed since previous render:</b> '
           + " ".join(f"<span>{_esc(c)}</span>" for c in changes) + '</div>',
           '</header>']

    def section(title, note, ids):
        out.append(f"<section><h2>{_esc(title)}</h2><p class='sec-note'>{_esc(note)}</p>"
                   "<div class='cards'>")
        for eid in ids:
            if eid in reg:
                out.append(_card(eid, reg[eid], counts.get(eid)))
        out.append("</div></section>")

    for title, ids in grains:
        section(title, "", ids)
    section("Relations", "The typed logical edges between claims. The vocabulary is closed.",
            rel_ids)
    section("Roles", "The work a claim does in the paper's argument.", role_ids)

    out.append("<section><h2>The toy study, four ways</h2>"
               "<p class='sec-note'>One synthetic study — does polishing a widget raise its "
               "shine — carried through the four ways a claim is made. The same concepts in all "
               "four; the finding clusters open in place.</p><div class='ways'>")
    out.append(_four_ways_html())
    out.append("</div></section>")

    if runs:
        out.append("<section><h2>Runs by canon version</h2>"
                   "<p class='sec-note'>Which corpus runs were made under which canon version, "
                   "read from the ledger.</p><div class='runs'>")
        for paper, layer, cv in runs:
            out.append(f"<div>{_esc(paper)} · {_esc(layer)} · canon {_esc(cv)}</div>")
        out.append("</div></section>")

    out.append("</div>")
    body = "\n".join(out)
    return body if body.endswith("\n") else body + "\n"


def check() -> list[str]:
    problems = []
    if not PAGE.is_file():
        return ["docs/canon.html is not committed (run `canon --render`)"]
    if PAGE.read_text(encoding="utf-8") != render():
        problems.append("docs/canon.html differs from what the canon renders (run `canon --render`)")
    return problems


def write(with_corpus: bool = False) -> Path:
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(render(with_corpus), encoding="utf-8")
    return PAGE


def bless() -> Path:
    """Reset the changelog baseline to the current entries."""
    BASELINE.write_text(json.dumps(snapshot(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return BASELINE
