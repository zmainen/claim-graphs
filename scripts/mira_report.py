#!/usr/bin/env python3
"""mira_report — the MIRA track's readable record, one static page per run, built from the files.

Reads, for one paper under CLAIM_GRAPHS_ROOT:
  runs/<paper>/mira-baseline/*.meta.json + *.graph.json        every extractor run and second pass
  runs/<paper>/mira-baseline/elife-prototype-*.graph.json      eLife's own extractor run, for comparison
  experiments/2026-10-16-mira-extractor-gadeke/                the Fable full-pipeline run (elife-claim-trees#178)
  runs/<paper>/mira-hand/<paper>-hand.graph.json + the page text it was anchored to
  extract/prompts/external/mira-extraction/                    the vendored prompt, its variants, VARIANTS.md
Writes runs/<paper>/mira-report/site/: index.html, prompt.html, graph-hand.html, run-<id>.html.
Publish the directory as a multi-page artifact (index.html as the page, the rest as files).

Nothing on the pages is typed by hand: counts, claims, anchors, edges and the comparison tables
all come from the run files, so a new run is one more page the next time this is built.

Usage:  mira_report.py <paper>
"""
import glob, html, json, os, re, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from roots import GRAPH as ROOT  # noqa: E402
from mira_baseline import paper_text, PROMPTS  # noqa: E402

E = html.escape
TYPES = ["Question", "Claim", "Evidence", "Study", "Protocol", "SourceDocument", "Request"]
RELS = ["addresses", "supports", "opposes", "grounds", "follows", "describesActivity", "request_target", "request_for"]

# ── CSS ──────────────────────────────────────────────────────────────────────────────────────
CSS = """
:root { color-scheme: light;
  --paper:#f7f6f2; --paper-2:#efede6; --ink:#1d1f24; --ink-2:#4b4f58; --ink-3:#7a7f8a; --rule:#d9d6cc;
  --blue:#1f4e9c; --blue-soft:#dbe5f6; --green:#2b6b3f; --red:#9b2f2f;
  --q:#7a3e9d; --c:#1f4e9c; --e:#2b6b3f; --s:#a65b1e; --p:#6b6b6b; --d:#8a6d1e; --r:#9b2f2f;
  --display:"Newsreader",Georgia,"Times New Roman",serif; --body:"Source Sans 3","Helvetica Neue",Arial,sans-serif; --mono:"JetBrains Mono",ui-monospace,Menlo,monospace; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { color-scheme: dark;
  --paper:#15171c; --paper-2:#1d2027; --ink:#e9e7e0; --ink-2:#b7b4aa; --ink-3:#8a8780; --rule:#2f333c;
  --blue:#8fb0ea; --blue-soft:#1f2a40; --green:#7fbf93; --red:#e08a8a;
  --q:#c69be0; --c:#8fb0ea; --e:#7fbf93; --s:#e0a070; --p:#a0a0a0; --d:#d4b35a; --r:#e08a8a; } }
:root[data-theme="dark"] { color-scheme: dark;
  --paper:#15171c; --paper-2:#1d2027; --ink:#e9e7e0; --ink-2:#b7b4aa; --ink-3:#8a8780; --rule:#2f333c;
  --blue:#8fb0ea; --blue-soft:#1f2a40; --green:#7fbf93; --red:#e08a8a;
  --q:#c69be0; --c:#8fb0ea; --e:#7fbf93; --s:#e0a070; --p:#a0a0a0; --d:#d4b35a; --r:#e08a8a; }
*{box-sizing:border-box} html,body{margin:0}
body{background:var(--paper);color:var(--ink);font-family:var(--body);font-size:17px;line-height:1.55;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:0 64px}
a{color:var(--blue);text-decoration-thickness:1px;text-underline-offset:2px} a:focus-visible,summary:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
code,pre{font-family:var(--mono);font-size:.86em}
h1,h2,h3,h4{font-family:var(--display);font-weight:600;text-wrap:balance;margin:0}
h1{font-size:clamp(2rem,5vw,3.1rem);line-height:1.08;letter-spacing:-.01em} h2{font-size:1.7rem;line-height:1.2;margin-block:2.6rem .9rem}
h3{font-size:1.25rem;margin-block:1.8rem .6rem} h4{font-size:1.08rem;line-height:1.3} p{margin:0}
.wrap{max-width:72ch;margin-inline:auto;display:grid;gap:.9rem} .wide{max-width:1180px;margin-inline:auto}
.eyebrow{font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3)}
.lede{font-size:1.15rem;color:var(--ink-2);font-family:var(--display);font-style:italic}
.muted{color:var(--ink-3)} .small{font-size:.9rem} .num{font-variant-numeric:tabular-nums;text-align:right}
nav.index{position:sticky;top:env(safe-area-inset-top,0px);z-index:2;background:color-mix(in srgb,var(--paper) 92%,transparent);backdrop-filter:blur(6px);border-bottom:1px solid var(--rule);
  margin-inline:calc(-1*max(16px,env(safe-area-inset-left,0px))) calc(-1*max(16px,env(safe-area-inset-right,0px)));padding-inline:max(16px,env(safe-area-inset-left,0px)) max(16px,env(safe-area-inset-right,0px))}
nav.index ul{list-style:none;margin:0 auto;padding:.6rem 0;max-width:1180px;display:flex;gap:1.4rem;flex-wrap:wrap;font-size:.9rem}
nav.index a{text-decoration:none;color:var(--ink-2)} nav.index a:hover,nav.index a[aria-current]{color:var(--blue)}
header.hero{padding-block:3rem 1rem}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--rule);border:1px solid var(--rule);margin-block:1.4rem}
.fact{background:var(--paper);padding:.8rem .9rem;display:grid;gap:.15rem} .fact b{font-family:var(--display);font-size:1.5rem;line-height:1.1;font-variant-numeric:tabular-nums} .fact span{font-size:.8rem;color:var(--ink-3)}
table{border-collapse:collapse;width:100%;font-size:.95rem} th,td{text-align:left;padding:.45rem .6rem;border-bottom:1px solid var(--rule);vertical-align:top}
th{font-weight:600;color:var(--ink-2);font-size:.82rem;letter-spacing:.04em;text-transform:uppercase}
.two{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem} @media (max-width:640px){.two{grid-template-columns:1fr}}
.rel{font-family:var(--mono);font-size:.8em;color:var(--blue)}
details{border:1px solid var(--rule);background:var(--paper-2)} details>summary{cursor:pointer;padding:.7rem .9rem;font-weight:600;list-style:none;display:flex;justify-content:space-between;gap:1rem}
details>summary::after{content:"open";font-weight:400;font-size:.85rem;color:var(--ink-3)} details[open]>summary::after{content:"close"} details>summary::-webkit-details-marker{display:none}
pre.prompt{margin:0;padding:1rem;overflow:auto;white-space:pre-wrap;word-break:break-word;line-height:1.5;font-size:.8rem;border-top:1px solid var(--rule);max-height:70vh}
.msg{display:grid;grid-template-columns:7rem 1fr;gap:.6rem 1rem;align-items:baseline;font-size:.95rem} .msg .k{font-family:var(--mono);font-size:.8rem;color:var(--ink-3)} .msg code{background:var(--paper-2);padding:.1rem .35rem}
.drawing{border:1px solid var(--rule);background:var(--paper-2);overflow-x:auto;margin-block:1rem} .drawing svg{display:block;min-width:760px;width:100%;height:auto}
.svg-col{font:600 13px var(--body);fill:var(--ink-2);letter-spacing:.04em} .svg-id{font:11px var(--mono);fill:var(--ink-3)}
.edge{stroke:var(--ink-3);stroke-opacity:.35;stroke-width:1} .edge.e-supports{stroke:var(--blue);stroke-opacity:.7;stroke-width:1.4} .edge.e-opposes{stroke:var(--red);stroke-opacity:.9;stroke-width:1.6}
.edge.e-addresses{stroke:var(--q);stroke-opacity:.7;stroke-width:1.4} .edge.e-request_target,.edge.e-request_for{stroke:var(--r);stroke-opacity:.5;stroke-dasharray:3 3}
.node circle{stroke:var(--paper);stroke-width:1.5} .n-Question circle{fill:var(--q)} .n-Claim circle{fill:var(--c)} .n-Evidence circle{fill:var(--e)} .n-Study circle{fill:var(--s)} .n-Protocol circle{fill:var(--p)} .n-SourceDocument circle{fill:var(--d)} .n-Request circle{fill:var(--r)}
.legend{display:flex;gap:1rem 1.4rem;flex-wrap:wrap;font-size:.85rem;color:var(--ink-2)} .legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:.35rem;vertical-align:-1px} .legend .ln{display:inline-block;width:22px;height:0;border-top:2px solid;margin-right:.4rem;vertical-align:3px}
.type-block{margin-block:1.5rem} .type-block h3 .count{font-family:var(--body);font-weight:400;color:var(--ink-3);font-size:1rem;margin-left:.4rem}
.cards{display:grid;gap:.8rem} .node-card{border-top:2px solid var(--rule);padding-top:.7rem;display:grid;gap:.45rem;scroll-margin-top:4rem} .node-card header{display:grid;grid-template-columns:auto 1fr;gap:.7rem;align-items:baseline} .nid{color:var(--ink-3)}
#type-Question .node-card{border-top-color:var(--q)} #type-Claim .node-card{border-top-color:var(--c)} #type-Evidence .node-card{border-top-color:var(--e)} #type-Study .node-card{border-top-color:var(--s)} #type-Protocol .node-card{border-top-color:var(--p)} #type-SourceDocument .node-card{border-top-color:var(--d)} #type-Request .node-card{border-top-color:var(--r)}
.desc{color:var(--ink-2);font-size:.95rem} blockquote.anchor{margin:0;font-family:var(--display);font-style:italic;color:var(--ink-2);font-size:.98rem} blockquote.anchor .q{color:var(--ink-3)}
.anchor-state{font-family:var(--body);font-style:normal;font-size:.75rem;letter-spacing:.04em;text-transform:uppercase;margin-left:.5rem} .anchor-state.ok{color:var(--green)} .anchor-state.miss{color:var(--red)}
ul.edges{margin:0;padding-left:1.1rem;font-size:.9rem;display:grid;gap:.15rem}
.callout{border-left:3px solid var(--blue);background:var(--blue-soft);padding:.8rem 1rem;display:grid;gap:.4rem}
.list{display:grid;gap:1rem;margin:0;padding:0;list-style:none} .list>li{display:grid;gap:.3rem;border-top:1px solid var(--rule);padding-top:.7rem} .paper-says{font-family:var(--display);font-style:italic;color:var(--ink-2)}
.runs{display:grid;gap:1px;background:var(--rule);border:1px solid var(--rule)} .run{background:var(--paper);padding:.9rem 1rem;display:grid;grid-template-columns:1fr auto;gap:.3rem 1rem;align-items:baseline;text-decoration:none;color:inherit}
.run h3{margin:0;font-size:1.15rem} .run .meta{grid-column:1/-1;font-size:.9rem;color:var(--ink-2)} .run .state{font-size:.78rem;letter-spacing:.05em;text-transform:uppercase} .run .state.ok{color:var(--green)} .run .state.fail{color:var(--red)}
.badge{display:inline-block;font:600 .7rem var(--body);letter-spacing:.06em;text-transform:uppercase;padding:.1rem .45rem;border-radius:2px;margin-right:.5rem;vertical-align:middle;color:var(--paper)}
.b-Hypothesis{background:var(--c)} .b-Alternative{background:var(--red)} .b-Check{background:var(--s)}
.arg{border-left:3px solid var(--rule);padding:.6rem 1rem;margin-block:1rem;display:grid;gap:.5rem} .arg-q{font-family:var(--display);font-size:1.15rem;font-weight:600}
.arg-h{margin-top:.3rem} .arg-f{margin:0;padding-left:1.2rem;font-size:.95rem;color:var(--ink-2)} .arg-a{padding-left:.2rem}
.thumb{display:block;max-width:100%;width:240px;height:auto;border:1px solid var(--rule);margin-top:.4rem;background:#fff}
table.cov td{vertical-align:top} table.cov .thumb{width:160px;margin:0} .panel-line{font-size:.9rem}
footer{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--rule);font-size:.85rem;color:var(--ink-3)}
@media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}
"""

def head(title):
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="claude:viewport-fit-sides" content="cover"><title>{E(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&family=Source+Sans+3:wght@400;600&family=JetBrains+Mono:wght@400;500&display=swap">
<style>{CSS}</style></head><body>'''

# ── inputs ───────────────────────────────────────────────────────────────────────────────────
def load(paper):
    B = os.path.join(ROOT, "runs", paper, "mira-baseline")
    H = os.path.join(ROOT, "runs", paper, "mira-hand")
    text = paper_text(paper)                                  # what the API runs were given (v1 JATS)
    system = open(os.path.join(PROMPTS, "system_message.txt"), encoding="utf-8").read()
    preamble = open(os.path.join(PROMPTS, "user_preamble.txt"), encoding="utf-8").read()
    variant = open(os.path.join(PROMPTS, "system_message.variant-1.txt"), encoding="utf-8").read() if os.path.exists(os.path.join(PROMPTS, "system_message.variant-1.txt")) else ""
    variants_md = open(os.path.join(PROMPTS, "VARIANTS.md"), encoding="utf-8").read() if os.path.exists(os.path.join(PROMPTS, "VARIANTS.md")) else ""
    runs = []
    for mf in sorted(glob.glob(os.path.join(B, "*.meta.json"))):
        m = json.load(open(mf)); name = os.path.basename(mf)[:-len(".meta.json")]
        gf = mf.replace(".meta.json", ".graph.json")
        g = json.load(open(gf)) if os.path.exists(gf) else None
        att = m.get("attempts") or [{"attempt": 1, "seconds": m.get("seconds"), "model_answered": m.get("model_answered"), "usage": m.get("usage"), "error": None, "parsed": m.get("parsed")}]
        is_pass = m.get("second_pass_over") is not None
        variant_run = (not is_pass) and m.get("prompt", "system_message.txt") != "system_message.txt"
        VAR = ('<b>This run used variant-1 of the prompt</b>: Claim redefined to admit what the paper argues against, a rule for eliminated alternatives, rival distinguished from check, '
               'hypotheses as Claims that findings support, one Question per hypothesis, Evidence per study, Study per analysis. Output vocabulary unchanged. See <a href="prompt.html#variant">the prompt page</a>.')
        if is_pass:
            sp = (g or {}).get("second_pass", {})
            note = (f'<b>A second stage over an existing graph.</b> Base: <a href="run-{E(m["second_pass_over"])}.html">{E(m["second_pass_over"])}</a>. This call was given that graph\'s nodes and argument edges plus the whole paper, with one job: '
                    f'find the alternatives the paper argues against or leaves open, state each as a Claim, draw <span class="rel">opposes</span> from the results that count against it, and add any eliminating result the first pass dropped. '
                    f'Prompt <code>{E(m["prompt"])}</code>. Added {sp.get("added_nodes", "?")} nodes and {sp.get("added_edges", "?")} edges (ids <code>a…</code>, <code>ae…</code>); {len(sp.get("dropped_edges", []))} proposed edges failed the grammar. '
                    + (f'Model\'s note: <i>{E(sp["notes"])}</i>' if sp.get("notes") else ""))
            src = f"second pass (alternatives) over {m['second_pass_over']} · API"
        elif m.get("route") == "claude-code subagent":
            note = (f'The extractor\'s call answered by a Claude Code subagent, as the extractor\'s own <code>--answer</code> mode allows: the subagent read <code>{E(m["prompt"])}</code> and the user message through a file-reading tool, in pages, and wrote the JSON, '
                    f'parsed as the extractor parses a reply. The paper reaches the model as page reads, not inside the prompt; both subagent runs came out about half the size of the same model through the API. '
                    + (VAR if variant_run else "The original prompt, unchanged: the control arm."))
            src = "prepared JATS text · Sonnet subagent · " + ("variant-1 prompt" if variant_run else "original prompt")
        else:
            note = ("The extractor's call reproduced from its source: message composition, temperature 0.2, 60,000-token cap, streaming, retries and parse, with the paper inside the prompt. Only the model call; not the extractor's fold, consolidation or projection. "
                    + (VAR if variant_run else "The original system message, verbatim."))
            src = "prepared JATS text · API · " + ("variant-1 prompt" if variant_run else "original prompt")
        runs.append({"id": name, "label": name.replace(".run", " · run "), "model": m.get("model_answered") or m["model_requested"], "requested": m["model_requested"],
                     "when": m.get("when", "")[:10], "seconds": m.get("seconds"), "usage": m.get("usage"), "attempts": att, "graph": g, "text": text,
                     "source": src, "note": note, "variant": variant_run, "is_pass": is_pass})
    # eLife's own run (the design prototype's graph)
    for pf in sorted(glob.glob(os.path.join(B, "elife-prototype-*.graph.json"))):
        pg = json.load(open(pf))
        runs.insert(0, {"id": os.path.basename(pf)[:-len(".graph.json")], "label": "eLife prototype · July 2026", "model": pg["models"][0], "requested": pg["models"][0],
                        "when": "2026-07", "seconds": None, "usage": None, "attempts": [], "graph": pg, "text": None, "variant": False, "is_pass": False,
                        "source": "the paper's PDF · marked edited",
                        "note": "The output eLife's design prototype carries, produced by the extractor itself from the PDF with its pinned free model and marked <code>edited: true</code>. Shown as a run so all can be read the same way."})
    # the Fable full-pipeline run (elife-claim-trees#178)
    F = os.path.join(ROOT, "experiments", "2026-10-16-mira-extractor-gadeke")
    if os.path.exists(os.path.join(F, "gadeke-2026-guilt-insula.graph.json")):
        fg = json.load(open(os.path.join(F, "gadeke-2026-guilt-insula.graph.json")))
        fmd = open(os.path.join(F, "gadeke-2026-guilt-insula.md"), encoding="utf-8").read()
        runs.append({"id": "fable-5.1-subagent", "label": "Fable 5.1 subagent · October 2026", "model": fg["models"][0], "requested": fg["models"][0], "when": "2026-10-16",
                     "seconds": None, "usage": None, "attempts": [], "graph": fg, "text": fmd, "variant": False, "is_pass": False,
                     "source": "the paper as markdown · the extractor's full pipeline",
                     "note": 'The extractor itself, with its one call answered by a Claude Code subagent (<code>claude-fable-5-1</code>): the CLI dumped the prompt, the subagent wrote the JSON, the CLI parsed, folded, grammar-checked and projected it. Validates against MIRA\'s shapes. Kept in <a href="https://github.com/zmainen/elife-claim-trees/pull/178">elife-claim-trees#178</a> with a written comparison. Its input was a markdown rendering (89,276 characters), not the prepared text the other October runs used.'})
    hand = hand_text = None
    hf = glob.glob(os.path.join(H, "*-hand.graph.json"))
    if hf:
        hand = json.load(open(hf[0]))
        tf = glob.glob(os.path.join(H, "*v2.txt")) + glob.glob(os.path.join(H, "*-page.txt"))
        hand_text = open(tf[0], encoding="utf-8").read() if tf else ""
    return dict(B=B, H=H, text=text, system=system, preamble=preamble, variant=variant, variants_md=variants_md, runs=runs, hand=hand, hand_text=hand_text)

# ── shared pieces ─────────────────────────────────────────────────────────────────────────────
def counts(g, text):
    by = Counter(n["type"] for n in g["nodes"]); rel = Counter(e["relation"] for e in g["edges"])
    anc = [n for n in g["nodes"] if n.get("anchor")]; found = sum(1 for n in anc if text and n["anchor"] in text)
    return by, rel, len(anc), found

def drawing(g):
    nodes, edges = g["nodes"], g["edges"]; N = {n["id"]: n for n in nodes}
    by = {t: [n for n in nodes if n["type"] == t] for t in TYPES}; cols = [t for t in TYPES if by[t]]
    W, rowh, top, left = 1180, 22, 44, 70; colw = (W - 140) / max(1, len(cols) - 1)
    pos = {n["id"]: (left + ci * colw, top + 30 + ri * rowh) for ci, t in enumerate(cols) for ri, n in enumerate(by[t])}
    H = top + 30 + rowh * max(len(v) for v in by.values()) + 20
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{len(nodes)} nodes in {len(cols)} columns by type, {len(edges)} edges">']
    s += [f'<text x="{left + ci * colw:.0f}" y="{top}" text-anchor="middle" class="svg-col">{t} · {len(by[t])}</text>' for ci, t in enumerate(cols)]
    for e in edges:
        if e["subject"] not in pos or e["object"] not in pos: continue
        (x1, y1), (x2, y2) = pos[e["subject"]], pos[e["object"]]; cx = (x1 + x2) / 2
        s.append(f'<path d="M{x1:.0f},{y1:.0f} C{cx:.0f},{y1:.0f} {cx:.0f},{y2:.0f} {x2:.0f},{y2:.0f}" class="edge e-{E(e["relation"])}" fill="none"><title>{E(e["relation"])}: {E(N[e["subject"]]["text"][:80])} → {E(N[e["object"]]["text"][:80])}</title></path>')
    for n in nodes:
        x, y = pos[n["id"]]
        s.append(f'<g class="node n-{E(n["type"])}"><circle cx="{x:.0f}" cy="{y:.0f}" r="7"/><text x="{x + 11:.0f}" y="{y + 4:.0f}" class="svg-id">{E(n["id"])}</text><title>{E(n["type"])} {E(n["id"])}: {E(n["text"])}</title></g>')
    return '<div class="drawing">' + "\n".join(s) + "</svg></div>"

LEGEND = '''<p class="legend"><span><i style="background:var(--q)"></i>Question</span><span><i style="background:var(--c)"></i>Claim</span><span><i style="background:var(--e)"></i>Evidence</span><span><i style="background:var(--s)"></i>Study</span><span><i style="background:var(--p)"></i>Protocol</span><span><i style="background:var(--d)"></i>Source document</span><span><i style="background:var(--r)"></i>Request</span>
<span><span class="ln" style="border-color:var(--q)"></span>addresses</span><span><span class="ln" style="border-color:var(--blue)"></span>supports</span><span><span class="ln" style="border-color:var(--red)"></span>opposes</span><span><span class="ln" style="border-color:var(--ink-3)"></span>grounds · follows · describesActivity</span></p>'''

def node_cards(g, text):
    nodes, edges = g["nodes"], g["edges"]; N = {n["id"]: n for n in nodes}
    outs, ins = defaultdict(list), defaultdict(list)
    for e in edges: outs[e["subject"]].append(e); ins[e["object"]].append(e)
    def card(n):
        o = "".join(f'<li><span class="rel">{E(e["relation"])}</span> → <a href="#{E(e["object"])}"><code>{E(e["object"])}</code></a> <span class="muted">{E(N[e["object"]]["text"])}</span></li>' for e in outs[n["id"]] if e["object"] in N)
        i = "".join(f'<li><a href="#{E(e["subject"])}"><code>{E(e["subject"])}</code></a> <span class="rel">{E(e["relation"])}</span> → this <span class="muted">{E(N[e["subject"]]["text"])}</span></li>' for e in ins[n["id"]] if e["subject"] in N)
        a = n.get("anchor"); hit = bool(a) and bool(text) and a in text
        anc = f'<blockquote class="anchor"><span class="q">“</span>{E(a)}<span class="q">”</span><span class="anchor-state {"ok" if hit else "miss"}">{"found verbatim" if hit else ("not found verbatim" if text else "not checked")}</span></blockquote>' if a else '<p class="muted small">no anchor</p>'
        desc = f'<p class="desc">{E(n["description"])}</p>' if n.get("description") else ""
        return f'<article class="node-card" id="{E(n["id"])}"><header><code class="nid">{E(n["id"])}</code><h4>{E(n["text"])}</h4></header>{desc}{anc}{f"<ul class=edges>{o}{i}</ul>" if o or i else "<p class=\"muted small\">no edges</p>"}</article>'
    by = {t: [n for n in nodes if n["type"] == t] for t in TYPES}
    return "".join(f'<section class="type-block" id="type-{t}"><h3>{t} <span class="count">{len(by[t])}</span></h3><div class="cards">{"".join(card(n) for n in by[t])}</div></section>' for t in TYPES if by[t])

# ── pages ─────────────────────────────────────────────────────────────────────────────────────
def nav(D, current):
    items = [("index.html", "Overview")] + ([("graph-hand.html", "The argument")] if D["hand"] else []) + [("prompt.html", "The prompt")] + [(f"run-{r['id']}.html", r["label"]) for r in D["runs"]]
    return '<nav class="index" aria-label="Pages"><ul>' + "".join(f'<li><a href="{E(h)}"{" aria-current=\"page\"" if h == current else ""}>{E(t)}</a></li>' for h, t in items) + "</ul></nav>"

FOOT = '''<footer class="wrap"><p>claim-graphs <a href="https://github.com/zmainen/claim-graphs/issues/77">#77</a>, the MIRA track. Run files: <code>runs/&lt;paper&gt;/mira-baseline/</code> and <code>mira-hand/</code> in zmainen/elife-claim-trees. Extractor: <a href="https://github.com/MIRA-science/MIRA-extraction">MIRA-science/MIRA-extraction</a> at main, 11 August 2026. Paper: Gädeke et al., eLife 105391, CC BY 4.0. Built by <code>scripts/mira_report.py</code>.</p></footer></body></html>'''

def run_page(D, r):
    g = r["graph"]; u = r["usage"] or {}
    facts = [(r["model"].split("/")[-1], "model that answered")]
    if r["seconds"]: facts.append((f"{r['seconds']:.0f} s", "wall time"))
    if u.get("prompt_tokens"): facts += [(f"{u['prompt_tokens']:,}", "tokens in"), (f"{u.get('completion_tokens', 0):,}", "tokens out"), (f"${u.get('cost', 0):.2f}", "cost")]
    if g:
        by, rel, na, nf = counts(g, r["text"])
        facts += [(str(len(g["nodes"])), "nodes"), (str(len(g["edges"])), "edges"), (str(rel.get("opposes", 0)), "opposes edges"), (f"{nf}/{na}", "anchors verbatim" + (" in its input" if r["text"] is not None else " (not checked)"))]
    facts_html = "".join(f'<div class="fact"><b>{E(a)}</b><span>{E(b)}</span></div>' for a, b in facts)
    att = ""
    if r["attempts"]:
        rows = "".join(f'<tr><td>{a["attempt"]}</td><td>{(a.get("seconds") or 0):.0f} s</td><td>{E(str(a.get("model_answered") or "—"))}</td><td>{"yes" if a.get("parsed") else "no"}</td><td>{E(str((a.get("error") or {}).get("message") or (a.get("error") or {}).get("exception") or "—"))}</td></tr>' for a in r["attempts"])
        att = f'<h3>Attempts</h3><table><thead><tr><th>#</th><th>time</th><th>model</th><th>parsed</th><th>error</th></tr></thead><tbody>{rows}</tbody></table>'
    if g:
        by, rel, na, nf = counts(g, r["text"])
        trows = "".join(f'<tr><td>{t}</td><td class="num">{by.get(t, 0)}</td></tr>' for t in TYPES)
        rrows = "".join(f'<tr><td><span class="rel">{rl}</span></td><td class="num">{rel.get(rl, 0)}</td></tr>' for rl in RELS)
        body = f'''<section class="wide" id="graph"><div class="wrap"><h2>The graph</h2><p>{len(g["nodes"])} nodes and {len(g["edges"])} edges. Each column is a node type; each curve a relation, subject to object. Hover for text.</p></div>{drawing(g)}<div class="wrap">{LEGEND}
<div class="two" style="margin-top:1.2rem"><table><thead><tr><th>node type</th><th class="num">count</th></tr></thead><tbody>{trows}</tbody></table><table><thead><tr><th>relation</th><th class="num">count</th></tr></thead><tbody>{rrows}</tbody></table></div></div></section>
<section class="wrap" id="nodes"><h2>Every node</h2><p>Grouped by type, in the order the model returned them, with description, anchor (checked against the text this run was given) and edges.</p>{node_cards(g, r["text"])}</section>'''
    else:
        body = '<section class="wrap"><div class="callout"><p><b>No graph.</b> Every attempt ended without a reply that parsed. The extractor has no fallback model, so its own run would have failed the same way.</p></div></section>'
    return head(f"{r['label']} — MIRA track") + nav(D, f"run-{r['id']}.html") + f'''
<header class="hero wrap"><p class="eyebrow">MIRA extractor · run</p><h1>{E(r["label"])}</h1><p class="lede">{E(r["source"])}</p></header>
<main><section class="wrap" id="run"><h2>The run</h2><p>{r["note"]}</p><div class="facts">{facts_html}</div>
<div class="msg"><span class="k">requested</span><span><code>{E(r["requested"])}</code></span><span class="k">system</span><span><a href="prompt.html">the extractor's system message</a></span><span class="k">user</span><span><code>{E(D["preamble"])}</code> then <code>---</code> then the paper</span><span class="k">when</span><span>{E(r["when"])}</span></div>{att}</section>{body}</main>''' + FOOT

def prompt_page(D):
    return head("The prompt — MIRA track") + nav(D, "prompt.html") + f'''
<header class="hero wrap"><p class="eyebrow">MIRA extractor · the instruction set</p><h1>The prompt</h1><p class="lede">Seven node types, eight relations, an output shape, twelve rules. The maintainers' comment: "editing it changes every graph the tool produces".</p></header>
<main class="wide"><div class="wrap"><p>Every run sent exactly two messages: the system message, and a user message made of the preamble, a rule, and the whole paper.</p></div>
<details open style="margin-top:1rem"><summary>System message <span class="muted small">{len(D["system"]):,} characters</span></summary><pre class="prompt">{E(D["system"])}</pre></details>
<details style="margin-top:.6rem"><summary>User message <span class="muted small">preamble, then the paper · {len(D["text"]):,} characters</span></summary><pre class="prompt">{E(D["preamble"])}

---
{E(D["text"])}</pre></details>
<div class="wrap" style="margin-top:2rem" id="variant"><h2>Variant 1 of the prompt</h2><p>Our altered system message, written from the baseline runs. Output shape, types and relations unchanged, so runs under it compare node for node.</p></div>
<details style="margin-top:1rem"><summary>What changed <span class="muted small">VARIANTS.md</span></summary><pre class="prompt">{E(D["variants_md"])}</pre></details>
<details style="margin-top:.6rem"><summary>System message, variant 1 <span class="muted small">{len(D["variant"]):,} characters</span></summary><pre class="prompt">{E(D["variant"])}</pre></details>
<div class="wrap" style="margin-top:2rem"><h2>What the original prompt says about alternatives</h2><p>Nothing. No rule mentions alternatives, rivals, controls, confounds, null results or manipulation checks. The only relation that could carry an eliminative argument is <span class="rel">opposes</span>, and three things keep it from firing: a Claim is defined as "an atomic, generalized assertion the authors make", so a rival the paper argues against is not a Claim; <span class="rel">opposes</span> can therefore only target the authors' own claims; and rule 10 drops any result that "does no work in the graph", which is what a null result becomes once there is no rival for it to oppose.</p></div></main>''' + FOOT

def hand_page(D):
    g, text = D["hand"], D["hand_text"]; N = {n["id"]: n for n in g["nodes"]}
    outs, ins = defaultdict(list), defaultdict(list)
    for e in g["edges"]: outs[e["subject"]].append(e); ins[e["object"]].append(e)
    def card(n, show=("supports", "opposes", "addresses")):
        o = "".join(f'<li><span class="rel">{E(e["relation"])}</span> → <a href="#{E(e["object"])}"><code>{E(e["object"])}</code></a> <span class="muted">{E(N[e["object"]]["text"])}</span></li>' for e in outs[n["id"]] if e["relation"] in show)
        i = "".join(f'<li><a href="#{E(e["subject"])}"><code>{E(e["subject"])}</code></a> <span class="rel">{E(e["relation"])}</span> → this <span class="muted">{E(N[e["subject"]]["text"])}</span></li>' for e in ins[n["id"]] if e["relation"] in show)
        badge = f'<span class="badge b-{E(n["subtype"])}">{E(n["subtype"])}</span>' if n.get("subtype") else ""
        fig = n.get("figure")
        panel = (f'<p class="panel-line"><span class="muted small">{E(n["panel"])} · {E(n["study"].replace("st", "Study "))}</span>'
                 + (f' · <a class="small" href="{E(fig["page"])}">open on eLife ↗</a><a href="{E(fig["image"])}"><img class="thumb" src="{E(fig["thumbnail"])}" alt="{E(fig["label"])}" loading="lazy"></a>' if fig else "") + "</p>") if n.get("panel") else ""
        hit = n["anchor"] in text if text else None
        return f'''<article class="node-card" id="{E(n["id"])}"><header><code class="nid">{E(n["id"])}</code><h4>{badge}{E(n["text"])}</h4></header>
<p class="desc">{E(n["description"])}</p>{panel}<blockquote class="anchor"><span class="q">“</span>{E(n["anchor"])}<span class="q">”</span><span class="anchor-state {"ok" if hit else "miss"}">{"verbatim in the page text" if hit else "not found"}</span></blockquote>
{f"<ul class=edges>{o}{i}</ul>" if o or i else ""}</article>'''
    def block(title, nodes, lede="", show=("supports", "opposes", "addresses")):
        return f'<section class="type-block"><h3>{title} <span class="count">{len(nodes)}</span></h3>{f"<p class=small>{lede}</p>" if lede else ""}<div class="cards">{"".join(card(n, show) for n in nodes)}</div></section>'
    qs = [n for n in g["nodes"] if n["type"] == "Question"]
    hyps = [n for n in g["nodes"] if n.get("subtype") == "Hypothesis"]; alts = [n for n in g["nodes"] if n.get("subtype") == "Alternative"]
    finds = [n for n in g["nodes"] if n["type"] == "Claim" and not n.get("subtype")]; checks = [n for n in g["nodes"] if n.get("subtype") == "Check"]
    evs = [n for n in g["nodes"] if n["type"] == "Evidence" and not n.get("subtype") and n.get("panel")]; cited = [n for n in g["nodes"] if n["type"] == "Evidence" and not n.get("panel")]
    rest = [n for n in g["nodes"] if n["type"] in ("Study", "Protocol", "SourceDocument", "Request")]
    figs = g.get("figures", {})
    def figcell(p):
        f = figs.get(p)
        return f'<a href="{E(f["page"])}" title="open {E(p)} on eLife"><img class="thumb" src="{E(f["thumbnail"])}" alt="{E(p)}" loading="lazy"></a>' if f else '<span class="muted small">not on the page</span>'
    covrows = "".join(f'<tr><td>{E(p)}</td><td>{figcell(p)}</td><td>{"<br>".join(f"<a href=#{E(i)}><code>{E(i)}</code></a> <span class=small>{E(N[i]["text"])}</span>" for i in ids) or "<span class=muted>—</span>"}</td></tr>' for p, ids in g.get("coverage", {}).items())
    arg = ""
    for q in qs:
        hs = [N[e["subject"]] for e in ins[q["id"]] if e["relation"] == "addresses" and N[e["subject"]].get("subtype") == "Hypothesis"]
        rs = [N[e["subject"]] for e in ins[q["id"]] if e["relation"] == "addresses" and N[e["subject"]].get("subtype") == "Alternative"]
        arg += f'<div class="arg"><p class="arg-q">{E(q["text"])}</p>'
        for h in hs:
            fs = [N[e["subject"]] for e in ins[h["id"]] if e["relation"] == "supports" and N[e["subject"]]["type"] == "Claim"]
            arg += f'<p class="arg-h"><span class="badge b-Hypothesis">Hypothesis</span> {E(h["text"])}</p><ul class="arg-f">' + "".join(f'<li>{E(f["text"])} <span class="muted small">({sum(1 for e in ins[f["id"]] if e["relation"]=="supports" and N[e["subject"]]["type"]=="Evidence")} observations)</span></li>' for f in fs) + "</ul>"
        for r in rs:
            op = [N[e["subject"]] for e in ins[r["id"]] if e["relation"] == "opposes"]
            arg += f'<p class="arg-a"><span class="badge b-Alternative">Alternative</span> {E(r["text"])}</p>' + (f'<ul class="arg-f">{"".join(f"<li><span class=rel>opposes</span> {E(o['text'])}</li>" for o in op)}</ul>' if op else '<p class="small muted" style="padding-left:1rem">left open: nothing in the paper opposes it</p>')
        arg += "</div>"
    ct = Counter(n["type"] for n in g["nodes"]); sub = Counter(n.get("subtype") for n in g["nodes"] if n.get("subtype")); rel = Counter(e["relation"] for e in g["edges"])
    return head("The paper's argument — MIRA track") + nav(D, "graph-hand.html") + f'''
<header class="hero wrap"><p class="eyebrow">hand-built · the text eLife Pathways serves · pure MIRA + three declared subclasses</p><h1>The paper's argument, as a MIRA graph</h1>
<p class="lede">Built by hand for adjudication and for the claims-tree prototype. {len(g["nodes"])} nodes, {len(g["edges"])} edges; every node anchored verbatim; every figure panel accounted for.</p></header>
<main>
<section class="wrap"><div class="facts">
<div class="fact"><b>{ct["Question"]}</b><span>questions</span></div><div class="fact"><b>{sub["Hypothesis"]}</b><span>hypotheses</span></div><div class="fact"><b>{len(finds)}</b><span>findings</span></div><div class="fact"><b>{sub["Alternative"]}</b><span>alternatives</span></div>
<div class="fact"><b>{ct["Evidence"]}</b><span>evidence</span></div><div class="fact"><b>{sub["Check"]}</b><span>of which checks</span></div><div class="fact"><b>{rel["opposes"]}</b><span>opposes edges</span></div><div class="fact"><b>{ct["Request"]}</b><span>requests</span></div></div>
<p>Three subclasses are declared the way MIRA and Discourse Graphs intend, as <code>NodeSchema</code> nodes pointing at their base type: <b>Hypothesis</b> and <b>Alternative</b> under Claim, <b>Check</b> under Evidence. A consumer that knows none of them still reads a valid MIRA graph.</p></section>
<section class="wrap" id="argument"><h2>The argument</h2><p>Each question with the hypothesis the paper commits to, the findings that support it, and the alternatives it raises, opposed or left open.</p>{arg}</section>
<section class="wide" id="drawing"><div class="wrap"><h2>The graph</h2></div>{drawing(g)}<div class="wrap">{LEGEND}</div></section>
<section class="wrap" id="coverage"><h2>Figure-panel coverage</h2><table class="cov"><thead><tr><th>panel</th><th>figure</th><th>evidence</th></tr></thead><tbody>{covrows}</tbody></table></section>
<section class="wrap" id="nodes"><h2>Every node</h2>
{block("Questions", qs, show=())}{block("Hypotheses", hyps, "What the paper sets out to test. Subclass of Claim.")}{block("Findings", finds, "The results as propositions, one per group of panels.")}
{block("Alternatives", alts, "Rival explanations the paper raises, stated as their proponents would. An alternative with no opposing edge is one the authors leave open.")}
{block("Checks", checks, "Observations that defend a finding or a method rather than argue for a hypothesis. Subclass of Evidence.")}{block("Evidence", evs, "One node per study and panel or statistic, with the numbers.")}
{block("Cited findings", cited, "From cited works the argument leans on, each grounded in the study the cited work reports.")}{block("Studies, protocols, source documents, requests", rest, show=("request_target",))}
</section></main>''' + FOOT

def index_page(D):
    runs = D["runs"]
    def runrow(r):
        g = r["graph"]
        if g:
            by, rel, na, nf = counts(g, r["text"])
            return f'<tr><td><a href="run-{E(r["id"])}.html">{E(r["label"])}</a></td><td class="small muted">{E(r["source"])}</td><td class="num">{len(g["nodes"])}</td><td class="num">{by.get("Question",0)}</td><td class="num">{by.get("Claim",0)}</td><td class="num">{by.get("Evidence",0)}</td><td class="num">{rel.get("opposes",0)}</td><td class="num">{nf}/{na}</td></tr>'
        return f'<tr><td><a href="run-{E(r["id"])}.html">{E(r["label"])}</a></td><td class="small muted">{E(r["source"])}</td><td colspan="6" class="muted">no graph: {len(r["attempts"])} attempts, each a timeout</td></tr>'
    base = [r for r in runs if not r["is_pass"] and not r["variant"] and "subagent-control" not in r["id"]]
    var = [r for r in runs if (r["variant"] or "subagent-control" in r["id"]) and not r["is_pass"]]
    passes = [r for r in runs if r["is_pass"]]
    table = lambda rs: f'<div style="overflow-x:auto"><table><thead><tr><th>run</th><th>how</th><th class="num">nodes</th><th class="num">Q</th><th class="num">claims</th><th class="num">evidence</th><th class="num"><span class="rel">opposes</span></th><th class="num">anchors</th></tr></thead><tbody>{"".join(runrow(r) for r in rs)}</tbody></table></div>'
    hand = ""
    if D["hand"]:
        hb = Counter(n["type"] for n in D["hand"]["nodes"]); hsub = Counter(n.get("subtype") for n in D["hand"]["nodes"] if n.get("subtype")); hrel = Counter(e["relation"] for e in D["hand"]["edges"])
        hand = f'''<section class="wrap" id="start"><h2>Start here: the paper's argument</h2>
<div class="runs"><a class="run" href="graph-hand.html"><h3>The hand-built graph</h3><span class="state ok">for adjudication</span><span class="meta">{len(D["hand"]["nodes"])} nodes · {len(D["hand"]["edges"])} edges · {hb["Question"]} questions · {hsub["Hypothesis"]} hypotheses · {hb["Claim"]-hsub["Hypothesis"]-hsub["Alternative"]} findings · {hsub["Alternative"]} alternatives ({hrel["opposes"]} <span class="rel">opposes</span>) · {hb["Evidence"]} evidence incl. {hsub["Check"]} checks · {hb["Request"]} requests · every anchor verbatim · every figure panel covered</span></a></div>
<p>Built from the text eLife Pathways serves, in pure MIRA plus three declared subclasses so the prototype can colour them. This is the graph to read the paper by, and the yardstick the extractor runs are measured against.</p></section>'''
    return head("Gädeke through the MIRA extractor") + nav(D, "index.html") + f'''
<header class="hero wrap"><p class="eyebrow">claim-graphs · MIRA track · Gädeke et al. 2026, eLife 105391</p><h1>Gädeke through the MIRA extractor</h1>
<p class="lede">One paper, taken apart three ways: by the MIRA community extractor as it is, by that extractor with an altered prompt and a second pass, and by hand. What each recovers of the paper's argument, and what it leaves out.</p></header>
<main>{hand}
<section class="wrap" id="experiments"><h2>The experiments</h2>
<h3>1 · Baseline: the extractor as it is</h3><p>The community extractor's single call, reproduced exactly, on the same prepared text, plus the two outside runs we can compare with. All recover the abstract's findings; none recovers a rival the paper eliminates; the pinned free model never completed.</p>{table(base)}
<h3>2 · An altered prompt</h3><p>Variant-1 against the original, same model and text, through the API and through a subagent. The structural rules took (Study per analysis, Evidence per study, one Question per hypothesis); the argument rules did not. <a href="prompt.html#variant">What changed.</a></p>{table(var)}
<h3>3 · A second pass for the alternatives</h3><p>One more call over a baseline graph with one job: the alternatives. <span class="rel">opposes</span> goes from zero to between one and five; the open empathy alternative every time, a Results-based elimination once, the design- and model-comparison-based ones never. The run over the original base drew <span class="rel">opposes</span> from the guilt-signature match to the emotion-labelling alternatives, which on rereading the Discussion ("we thus believe that our participants did experience guilt") is an inference the paper makes.</p>{table(passes)}
<p><b>Together:</b> the extractor's shape is set by its prompt's definition of a Claim as "an assertion the authors make"; neither a stronger model nor an altered prompt in one pass produces the paper's argument against its alternatives; a dedicated pass does, partly. The hand-built graph shows what the target looks like in pure MIRA.</p></section>
<section class="wrap" id="reference"><h2>Reference</h2><ul class="list">
<li><a href="prompt.html"><b>The prompt</b></a><span class="small muted">The extractor's system message verbatim, the user message with the paper, and variant-1 with its diff.</span></li>
<li><b>Every run</b><span class="small muted">{" · ".join(f'<a href="run-{E(r["id"])}.html">{E(r["label"])}</a>' for r in runs)}</span></li>
<li><b>Files</b><span class="small muted">runs/gadeke-2026-guilt-insula/mira-baseline/ and mira-hand/ in zmainen/elife-claim-trees; the runbook: docs/mira-track.md in zmainen/claim-graphs; <a href="https://github.com/zmainen/claim-graphs/issues/77">#77</a>.</span></li></ul></section></main>''' + FOOT

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    paper = sys.argv[1]
    D = load(paper)
    out = os.path.join(ROOT, "runs", paper, "mira-report", "site")
    os.makedirs(out, exist_ok=True)
    files = {"index.html": index_page(D), "prompt.html": prompt_page(D)}
    if D["hand"]: files["graph-hand.html"] = hand_page(D)
    for r in D["runs"]: files[f"run-{r['id']}.html"] = run_page(D, r)
    for name, content in files.items():
        open(os.path.join(out, name), "w", encoding="utf-8").write(content)
    print(f"wrote {len(files)} pages to {os.path.relpath(out, ROOT)}:", ", ".join(files))

if __name__ == "__main__":
    main()
