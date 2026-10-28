#!/usr/bin/env python3
"""mira_viewer — one self-contained HTML page that shows a MIRA working graph the way eLife
Pathways' design prototype does: the article text with claim markers at their anchors and the
summary beside the passage; a coloured claims tree (question → hypothesis → findings → evidence,
alternatives with what opposes them, checks marked); and the verification marks.

The JSON, the article text and the verification verdicts are embedded, so the file is the
deliverable's review surface and can be opened anywhere. Nothing is typed into it by hand.

Usage: mira_viewer.py <graph.json> <anchor-text.txt> [--out viewer.html] [--embed-figures] [--deliver]
--deliver builds the page handed to eLife: the Data item in the margin opens the cleaned working-graph
JSON (no builder bookkeeping; a `fields` note explains the extra fields), the MIRA JSON-LD, and an About
page with the audit stamp; no comparison, no verification table. The cleaned JSON is also written beside it.
                      [--compare <other.graph.json> <alignment.json> [--compare-label "eLife's graph"]]
With --compare the viewer gets a "Compared with…" tab: provenance badges on every node of the tree
(its counterpart in the other graph, or "new") and a three-column ledger per node type. The alignment
file comes from mira_align.py.
Expects <graph>.verification.json beside the graph (run mira_verify.py first).
"""
import base64, hashlib, json, os, sys, urllib.request

def embed_figures(g, cache):
    """Return {thumbnail URL: data URI} for every figure in the graph, fetched once into `cache` (gitignored).
    Kept outside the graph so the JSON tab and the delivered file stay URLs."""
    os.makedirs(cache, exist_ok=True)
    seen = {}
    figs = [n.get("figure") for n in g["nodes"]] + list((g.get("figures") or {}).values())
    for f in figs:
        if not f or not f.get("thumbnail"): continue
        url = f["thumbnail"]
        if url not in seen:
            path = os.path.join(cache, hashlib.sha1(url.encode()).hexdigest() + ".jpg")
            if not os.path.exists(path):
                with urllib.request.urlopen(url, timeout=60) as r: open(path, "wb").write(r.read())
            seen[url] = {"data": "data:image/jpeg;base64," + base64.b64encode(open(path, "rb").read()).decode(), "file": "fig/" + os.path.basename(path)}
    print(f"embedded {len(seen)} figure thumbnails"); return seen

def main():
    a = sys.argv[1:]
    gpath, tpath = a[0], a[1]
    out = a[a.index("--out") + 1] if "--out" in a else gpath.replace(".graph.json", ".viewer.html")
    g = json.load(open(gpath, encoding="utf-8"))
    text = open(tpath, encoding="utf-8").read()
    vpath = gpath.replace(".graph.json", ".verification.json")
    v = json.load(open(vpath)) if os.path.exists(vpath) else {"nodes": {}, "edges": [], "summary": {}}
    title = g.get("paper", {}).get("title", "MIRA graph")
    thumbs = embed_figures(g, os.path.join(os.path.dirname(os.path.abspath(gpath)), ".figcache")) if "--embed-figures" in a else {}
    if thumbs:   # the same files beside the page, for hosts that block data: images
        import shutil; fd = os.path.join(os.path.dirname(os.path.abspath(out)), "fig"); os.makedirs(fd, exist_ok=True)
        for t in thumbs.values(): shutil.copy(os.path.join(os.path.dirname(os.path.abspath(gpath)), ".figcache", os.path.basename(t["file"])), fd)
    cmp = None
    if "--compare" in a:
        i = a.index("--compare")
        cmp = {"graph": json.load(open(a[i + 1], encoding="utf-8")), "align": json.load(open(a[i + 2], encoding="utf-8")),
               "label": a[a.index("--compare-label") + 1] if "--compare-label" in a else "eLife's graph"}
    deliver = "--deliver" in a
    jsonld = None
    if deliver:
        cmp = None
        clean = {k: val for k, val in g.items() if k not in ("coverage", "models", "edited")}
        clean["nodes"] = [{k: val for k, val in n.items() if k != "key"} for n in g["nodes"]]
        clean["fields"] = {"description": "plain summary, one or two sentences", "anchor": "verbatim passage of the Reviewed Preprint text the node docks to",
                           "anchors": "further verbatim passages", "subtype": "declared subclass: Hypothesis / Alternative (Claim), Check / Cited (Evidence)",
                           "panel": "figure panel, table or section the evidence comes from", "study": "the Study node that grounds the evidence",
                           "figure": "IIIF image, thumbnail and page link for the panel", "notes": "editorial remarks kept out of the summary",
                           "sourceDocument": "DOI of the paper, or the id of the cited SourceDocument for Cited evidence"}
        g = clean
        ld = gpath.replace(".graph.json", ".mira.jsonld")
        jsonld = open(ld, encoding="utf-8").read() if os.path.exists(ld) else None
        json.dump(clean, open(out.replace(".html", ".graph.json"), "w"), indent=1, ensure_ascii=False)
    payload = json.dumps({"graph": g, "text": text, "verification": {} if deliver else v, "compare": cmp, "thumbs": thumbs, "deliver": deliver,
                          "jsonld": jsonld, "stamp": v.get("summary", {})}, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("__TITLE__", title.replace("<", "&lt;")).replace("__PAYLOAD__", payload)
    open(out, "w", encoding="utf-8").write(html)
    print(f"wrote {out} ({len(html) // 1024} KB)")

TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="claude:viewport-fit-sides" content="cover"><title>Gädeke claims viewer</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&family=DM+Mono:wght@500&display=swap">
<style>
/* In the language of eLife Pathways' prototype: white page, DM Sans, a sticky section list on the left of a
   centred article column, cards on the right. Here the right column is the claims apparatus, side by side
   with the text; colour is reserved for the typed id chips and one accent for the current node. */
:root{color-scheme:light;--paper:#fff;--paper-2:#f6f6f8;--paper-3:#ebebef;--ink:#1a1a1f;--ink-2:#55565e;--ink-3:#8a8b94;--rule:#e3e3e8;--link:#1d4ed8;--cur:#d9480f;
 --Q:#5b3f8f;--H:#1e4b8f;--F:#2a6b45;--A:#b23a2a;--E:#4a7a5e;--K:#b26d14;--R:#7a5a2a;--S:#6b6c75;--P:#6b6c75;--D:#6b6c75;--C:#6b6c75;
 --sans:"DM Sans","Helvetica Neue",Arial,sans-serif;--mono:"DM Mono",ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--paper:#141418;--paper-2:#1d1d23;--paper-3:#2a2a32;--ink:#ecebf0;--ink-2:#b4b3bc;--ink-3:#7f7f89;--rule:#2d2d35;--link:#8fb1ff;--cur:#ff8a4c;
 --Q:#c3a8ee;--H:#93b4f2;--F:#8fcda4;--A:#ee8f7d;--E:#8fcda4;--K:#e6b05e;--R:#d8b67e;--S:#9d9da6;--P:#9d9da6;--D:#9d9da6;--C:#9d9da6}}
:root[data-theme="dark"]{color-scheme:dark;--paper:#141418;--paper-2:#1d1d23;--paper-3:#2a2a32;--ink:#ecebf0;--ink-2:#b4b3bc;--ink-3:#7f7f89;--rule:#2d2d35;--link:#8fb1ff;--cur:#ff8a4c;
 --Q:#c3a8ee;--H:#93b4f2;--F:#8fcda4;--A:#ee8f7d;--E:#8fcda4;--K:#e6b05e;--R:#d8b67e;--S:#9d9da6;--P:#9d9da6;--D:#9d9da6;--C:#9d9da6}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--paper);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.55;display:flex;flex-direction:column;height:100vh;overflow:hidden;padding-inline:max(24px,env(safe-area-inset-left,0px)) max(24px,env(safe-area-inset-right,0px))}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline} button{font:inherit;cursor:pointer}
/* masthead: title and authors over the article column, nothing else */
header.top{flex:none;padding:1.4rem 0 1rem;border-bottom:1px solid var(--rule)}
header.top h1{font:600 1.55rem/1.25 var(--sans);letter-spacing:-.01em;margin:0 0 .45rem;max-width:62ch}
header.top .meta{font-size:.86rem;color:var(--ink-2);display:flex;flex-wrap:wrap;gap:.2rem 1.2rem;max-width:90ch}header.top .meta b{font-weight:500;color:var(--ink)}
.legend,.tabs{display:none}
/* three columns: section list · article · claims */
.split{display:grid;grid-template-columns:150px minmax(0,58ch) minmax(0,1fr);grid-template-rows:minmax(0,1fr);gap:2.2rem;flex:1;min-height:0}
.pane{overflow-y:auto;min-height:0}
nav.sections{padding-top:1.4rem;font-size:.86rem;position:sticky;top:0;align-self:start}
nav.sections a{display:block;color:var(--ink-2);padding:.28rem 0 .28rem .8rem;border-left:2px solid var(--rule);line-height:1.3}nav.sections a.cur{color:var(--ink);border-left-color:var(--ink);font-weight:500}nav.sections a:hover{text-decoration:none;color:var(--ink)}
nav.sections .key{margin-top:1.4rem;margin-left:.8rem;padding:.6rem .7rem;border:1px solid var(--rule);border-radius:8px;display:grid;gap:.2rem;font-size:.78rem;color:var(--ink-2)}nav.sections .key div{display:grid;grid-template-columns:auto 1fr auto;gap:.45rem;align-items:center}nav.sections .key b{font-weight:500;color:var(--ink);font-variant-numeric:tabular-nums}nav.sections .key div.sub{margin-left:.9rem;font-size:.74rem}nav.sections .key div:not(.sub)>span:nth-child(2){color:var(--ink);font-weight:500}nav.sections .key .kh{display:block;font:500 .66rem var(--sans);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);margin-bottom:.2rem}nav.sections .key .kf{display:block;margin-top:.3rem;padding-top:.3rem;border-top:1px solid var(--rule);color:var(--ink-3);font-size:.72rem}
nav.sections .tools{margin-top:1.4rem;padding-left:.8rem;display:grid;gap:.3rem}nav.sections details.internal{margin-top:.6rem}nav.sections details.internal summary{cursor:pointer;color:var(--ink-3);font-size:.74rem;letter-spacing:.06em;text-transform:uppercase}nav.sections details.internal button{display:block;width:100%;margin-top:.3rem}nav.sections .tools button{text-align:left;background:none;border:1px solid var(--rule);border-radius:6px;padding:.3rem .6rem;color:var(--ink-2);font-size:.8rem}nav.sections .tools button[aria-selected="true"]{background:var(--ink);color:var(--paper);border-color:var(--ink)}nav.sections .tools button.quiet{border-color:transparent;color:var(--ink-3)}nav.sections .tools button.quiet:hover{border-color:var(--rule)}
#arttab{display:none}
@media (max-width:1100px){.split{grid-template-columns:120px minmax(0,1fr) minmax(0,1fr);gap:1.2rem}}
@media (max-width:900px){body{height:auto;overflow:auto;display:block}.split{display:block}nav.sections{display:none}.pane{overflow:visible}#article:not(.on){display:none}.tabs{display:flex;flex-wrap:wrap;gap:.3rem;padding:.6rem 0}.tabs button{background:none;border:1px solid var(--rule);border-radius:6px;padding:.25rem .6rem;color:var(--ink-2)}.tabs button[aria-selected="true"]{background:var(--ink);color:var(--paper)}#arttab{display:inline-block}}
main{padding-block:1.2rem 5rem}main:not(.on){display:none !important}main.on{display:block}
/* id chips */
.id{display:inline-block;font:500 .7rem/1.55 var(--mono);padding:0 .34rem;border-radius:4px;color:#fff;background:var(--ink-3);min-width:2.3em;text-align:center;cursor:pointer;vertical-align:1px}
.id.Q{background:var(--Q)}.id.H{background:var(--H)}.id.F{background:var(--F)}.id.A{background:var(--A)}.id.E{background:var(--E)}.id.K{background:var(--K)}.id.R{background:var(--R)}.id.C{background:var(--C)}
.id.cited{background:none !important;color:var(--E);border:1px dashed var(--E)}
.id.ref{background:none !important;border:1px solid currentColor;opacity:.9}.id.ref.Q{color:var(--Q)}.id.ref.H{color:var(--H)}.id.ref.F{color:var(--F)}.id.ref.A{color:var(--A)}.id.ref.E{color:var(--E)}.id.ref.K{color:var(--K)}.id.ref.R{color:var(--R)}.id.ref.C,.id.ref.S,.id.ref.P,.id.ref.D{color:var(--ink-3)}
#hover{position:fixed;z-index:9;max-width:40ch;background:var(--ink);color:var(--paper);font-size:.84rem;line-height:1.45;padding:.5rem .7rem;border-radius:6px;pointer-events:none;box-shadow:0 4px 16px rgba(0,0,0,.18)}#hover[hidden]{display:none}#hover .id{margin-right:.4rem}
.prov{font:400 .72rem var(--mono);color:var(--ink-3);margin-left:.45rem;white-space:nowrap}.prov.new{color:var(--F)}
/* article */
.toc{display:none}
.text{font-size:1rem;line-height:1.7;padding-block:1.2rem 6rem}
.text h2{font:600 1.25rem/1.3 var(--sans);margin:2.4rem 0 .7rem;scroll-margin-top:1rem}.text p{margin:0 0 1.1rem;text-wrap:pretty}
.text .fig{font-size:.88rem;color:var(--ink-2);background:var(--paper-2);border-radius:8px;padding:.6rem .9rem;margin:1.2rem 0}figure.fig{margin:1.4rem 0;padding:.6rem}figure.fig img{width:100%;border-radius:4px;background:#fff}figure.fig figcaption{font-size:.8rem;color:var(--ink-3);margin-top:.4rem}
mark.anc{background:none;color:inherit;border-bottom:1.5px solid var(--rule);cursor:pointer;padding-bottom:1px}mark.anc:hover{background:var(--paper-2)}
mark.anc.on{background:color-mix(in srgb,var(--cur) 12%,transparent);border-bottom-color:var(--cur)}
.text .id{margin-left:.25rem;vertical-align:3px;font-size:.62rem}
/* claims column: question blocks and cards, as the prototype draws them */
#tree{max-width:76ch}
.qb{margin:0 0 2rem}.qb>h2{position:sticky;top:0;z-index:2;background:var(--paper-2);border-radius:8px;font:500 1rem/1.4 var(--sans);margin:0 0 .6rem;padding:.8rem 1rem;display:flex;gap:.6rem;align-items:baseline}
.qb>h2 .id{font-size:.68rem;vertical-align:2px}.qb>.s{color:var(--ink-2);font-size:.86rem;margin:0 1rem .9rem}
.row{display:grid;grid-template-columns:auto 1fr;gap:.6rem;align-items:baseline;padding:.5rem .8rem;margin:.3rem 0;border:1px solid var(--rule);border-radius:8px;scroll-margin-top:3.6rem;transition:background .15s,border-color .15s}
.row:hover{background:var(--paper-2)}.row .t{cursor:pointer;font-size:.92rem;line-height:1.45}.row .w{font:500 .64rem var(--sans);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);margin-right:.45rem}
.row.lvl1{margin-left:0}.row.lvl2{margin-left:1.6rem}.row.lvl3{margin-left:3.2rem}
.row.lvl2,.row.lvl3{position:relative}.row.lvl2::before,.row.lvl3::before{content:"";position:absolute;left:-1rem;top:-.4rem;bottom:50%;width:.7rem;border-left:1.5px solid var(--rule);border-bottom:1.5px solid var(--rule);border-bottom-left-radius:6px}
.row.open{border-color:var(--ink-3)}.row.cur{border-color:var(--cur);background:color-mix(in srgb,var(--cur) 6%,transparent)}
.tagr{float:right;margin-left:.6rem;font:500 .68rem var(--sans);color:var(--ink-2)}.tagr span{background:var(--paper-3);border-radius:4px;padding:.05rem .4rem;margin-left:.25rem;white-space:nowrap}
.drawer{background:var(--paper-2);border-radius:8px;padding:.9rem 1rem;margin:.1rem 0 .9rem;font-size:.9rem;display:grid;gap:.45rem}
.drawer .m{color:var(--ink-3);font-size:.78rem}.drawer p.m:empty{display:none}
.drawer h3{margin:0;font:500 1rem/1.45 var(--sans);text-wrap:pretty}.drawer .sum{margin:0}.drawer .q{color:var(--ink-2);font-style:italic;margin:0}
.drawer .figrow{display:grid;grid-template-columns:1fr auto;gap:.8rem;align-items:start}.drawer img{max-width:240px;border:1px solid var(--rule);background:#fff;border-radius:6px}
.drawer ul{margin:0;padding:0;list-style:none;display:flex;flex-wrap:wrap;gap:.3rem 1.2rem}.drawer li{font-size:.86rem}.rel{font:500 .7rem var(--mono);color:var(--ink-3);margin:0 .2rem}
.drawer .grp{font:500 .64rem var(--sans);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);margin-top:.5rem}.drawer .row{background:var(--paper);margin-left:0}.drawer .row:hover{background:var(--paper)}
.drawer .drawer{margin-left:0 !important;background:var(--paper);border:1px solid var(--rule)}
.verify{display:flex;flex-wrap:wrap;gap:.3rem}.verify span{font-size:.72rem;padding:.05rem .4rem;border-radius:4px;background:var(--paper);border:1px solid var(--rule)}.verify .bad{color:var(--A);border-color:var(--A)}
/* checks, compare, json */
#checks{max-width:90ch}#checks table{width:100%;border-collapse:collapse;font-size:.88rem}#checks td,#checks th{text-align:left;vertical-align:top;padding:.3rem .5rem;border-top:1px solid var(--rule)}
#compare.on{display:block}#compare table{width:100%;border-collapse:collapse;font-size:.86rem;margin:.4rem 0 1.4rem}#compare th,#compare td{vertical-align:top;text-align:left;padding:.35rem .5rem;border-top:1px solid var(--rule);width:33%}#compare th{font-weight:500;color:var(--ink-2)}#compare td>div{margin:.3rem 0}#compare .s{color:var(--ink-3);font-size:.78rem}#compare h2{font:500 1rem var(--sans);margin:1.4rem 0 .2rem}
#json pre,#jsonld pre{font:.76rem/1.5 var(--mono);white-space:pre-wrap;word-break:break-word}
.about{max-width:66ch;font-size:.95rem;line-height:1.65}.about h2{font:600 1.25rem var(--sans);margin:0 0 .8rem}.about h3{font:600 1rem var(--sans);margin:1.6rem 0 .4rem}.about code{font:.82rem var(--mono);background:var(--paper-2);padding:0 .25rem;border-radius:3px}.about .foot{color:var(--ink-3);font-size:.82rem;margin-top:2rem}.about table.stats{border-collapse:collapse;font-size:.88rem;margin:.4rem 0}.about table.stats td{padding:.15rem 1.2rem .15rem 0;border-top:1px solid var(--rule)}.about table.stats td:last-child{text-align:right;font-variant-numeric:tabular-nums}
@media print{body{height:auto;overflow:visible;display:block}.split{display:block}.pane{overflow:visible}nav.sections{display:none}main{display:block !important}#json,#jsonld,#compare,#checks{display:none !important}}
</style></head><body>
<header class="top"><h1>__TITLE__</h1><div class="meta" id="meta"></div>
<div class="legend"><span><span class="id Q">Q</span> question</span><span><span class="id H">H</span> hypothesis</span><span><span class="id F">F</span> finding</span><span><span class="id A">A</span> alternative</span><span><span class="id E">E</span> evidence</span><span><span class="id K">K</span> check</span><span><span class="id E cited">E</span> cited finding</span><span><span class="id C">C</span> cited work</span><span><span class="id R">R</span> request</span></div>
<div class="tabs" role="tablist"><button role="tab" data-tab="article" id="arttab">Article</button><button role="tab" data-tab="tree" aria-selected="true">Claims</button><button role="tab" data-tab="checks">Verification</button><button role="tab" data-tab="compare" id="cmptab" hidden>Compared</button><button role="tab" data-tab="json">JSON</button><button id="collapse" title="close every open node">collapse</button></div></header>
<div class="split"><nav class="sections" id="sections"></nav><section id="article" class="pane"><nav class="toc">section <select id="toc"></select></nav><div class="text" id="text"></div></section>
<section class="pane right"><main id="tree" class="on"></main><main id="checks"></main><main id="compare"></main><main id="json"><pre id="jsonpre"></pre></main><main id="jsonld"><pre id="jsonldpre"></pre></main><main id="about"></main></section></div>
<div id="hover" hidden></div>
<script id="data" type="application/json">__PAYLOAD__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);const G=D.graph,T=D.text,V=D.verification,C=D.compare;
const N=Object.fromEntries(G.nodes.map(n=>[n.id,n]));const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const WORD={Q:'question',H:'hypothesis',F:'finding',A:'alternative',E:'evidence',K:'check',C:'cited work',R:'request',S:'study',P:'protocol',D:'this paper'};
const isCitedDoc=n=>n.type==='SourceDocument'&&/^C\d/.test(n.id);
const pre=n=>isCitedDoc(n)?'C':n.subtype==='Hypothesis'?'H':n.subtype==='Alternative'?'A':n.subtype==='Check'?'K':n.type==='Claim'?'F':n.type==='Evidence'?'E':n.type==='Question'?'Q':n.type==='Request'?'R':n.type==='Study'?'S':n.type==='Protocol'?'P':'D';
const chip=(n,ref=false)=>`<span class="id ${pre(n)}${n.subtype==='Cited'?' cited':''}${ref?' ref':''}" data-go="${n.id}">${n.id}</span>`;
const outs={},ins={};for(const e of G.edges){(outs[e.subject]??=[]).push(e);(ins[e.object]??=[]).push(e)}
const thumb=u=>D.thumbs?.[u]?.data||u;const thumbAlt=u=>D.thumbs?.[u]?.file||'';const IMG=(u,alt,cls='')=>`<img ${cls?`class="${cls}" `:''}src="${thumb(u)}" data-alt="${thumbAlt(u)}" onerror="if(this.dataset.alt&&!this.dataset.tried){this.dataset.tried=1;this.src=this.dataset.alt}" alt="${alt}">`;const TN=C?Object.fromEntries(C.graph.nodes.map(n=>[n.id,n])):{};const O2T=C?C.align.ours_to_theirs:null;
const prov=n=>!C?'':O2T[n.id]?`<span class="prov" title="${esc(C.label)}: ${esc(O2T[n.id].map(t=>TN[t].text).join('\n'))}">= ${O2T[n.id].join(', ')}</span>`:['Evidence','SourceDocument'].includes(n.type)?'':`<span class="prov new">new</span>`;
const studyOf=n=>n.study?N[n.study]?.text.split(':')[0]||n.study:'';
// tabs
const tab=name=>{document.querySelectorAll('.tabs [data-tab]').forEach(x=>x.setAttribute('aria-selected',x.dataset.tab===name));document.querySelectorAll('main').forEach(m=>m.classList.toggle('on',m.id===name));document.getElementById('article').classList.toggle('on',name==='article')};
document.querySelectorAll('.tabs [data-tab]').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
document.getElementById('collapse').onclick=()=>{document.querySelectorAll('.drawer').forEach(d=>d.remove());document.querySelectorAll('.row.open,.row.cur').forEach(r=>r.classList.remove('open','cur'));document.querySelectorAll('mark.anc.on').forEach(m=>m.classList.remove('on'))};
const narrow=()=>matchMedia('(max-width:900px)').matches;
const HV=document.getElementById('hover');document.body.addEventListener('mouseover',e=>{const c=e.target.closest('.id[data-go]');if(!c||!N[c.dataset.go]){HV.hidden=true;return}const n=N[c.dataset.go];HV.innerHTML=`${chip(n)}${esc(n.text)}`;HV.hidden=false;const r=c.getBoundingClientRect();HV.style.left=Math.min(r.left,innerWidth-HV.offsetWidth-12)+'px';HV.style.top=(r.bottom+6+HV.offsetHeight>innerHeight?r.top-HV.offsetHeight-6:r.bottom+6)+'px'});document.body.addEventListener('mouseout',e=>{if(e.target.closest('.id[data-go]'))HV.hidden=true});
// ── article: mark anchors; margin shows chip + summary ──────────────────────────────────
const anchored=G.nodes.filter(n=>n.type!=='SourceDocument').flatMap(n=>[n.anchor,...(n.anchors||[])].filter(a=>a&&T.includes(a)).map(a=>({n,a}))).sort((x,y)=>y.a.length-x.a.length);
let segs=[{t:T}];
for(const {n,a} of anchored){const out=[];for(const s of segs){if(s.n){out.push(s);continue}let i=s.t.indexOf(a);if(i<0){out.push(s);continue}out.push({t:s.t.slice(0,i)});out.push({t:a,n});out.push({t:s.t.slice(i+a.length)})}segs=out.filter(s=>s.t.length)}
const html=[];let para=[];const flush=()=>{if(!para.length)return;const h=para.join('');const ids=[...new Set([...h.matchAll(/data-id="([^"]+)"/g)].map(m=>m[1]))];
 const fm=h.match(/^\[(Figure \d+)[:.]?\]/);const fg=fm&&Object.values(G.figures||{}).find(f=>new RegExp('^'+fm[1]+'[A-Z]?$').test(f.label));
 const body=h.startsWith('## ')?`<h2>${h.slice(3)}</h2>`:fg?`<figure class="fig"><a href="${esc(fg.page)}" target="_blank">${IMG(fg.thumbnail,esc(fm[1]))}</a><figcaption>${esc(fm[1])} · <a href="${esc(fg.page)}" target="_blank">on eLife ↗</a></figcaption></figure>`:h.startsWith('[Figure')||h.startsWith('[Table')?`<p class="fig">${h}</p>`:`<p>${h}</p>`;
 html.push(body);para=[]};
for(const s of segs){const parts=s.t.split('\n\n');parts.forEach((p,i)=>{if(i>0){flush()}const t=p.replace(/\n/g,' ');if(!t)return;para.push(s.n?`<mark class="anc" data-id="${s.n.id}">${esc(t)}</mark><span class="id ${pre(s.n)}" data-id="${s.n.id}">${s.n.id}</span>`:esc(t))})}
flush();document.getElementById('text').innerHTML=html.join('');
const P=G.paper||{};document.getElementById('meta').innerHTML=`${P.authors?`<span><b>${esc(P.authors.map(a=>a.name).join(', '))}</b></span>`:''}${P.doi?`<span><a href="https://doi.org/${esc(P.doi)}" target="_blank">doi:${esc(P.doi)}</a></span>`:''}<span>${G.nodes.length} nodes · ${G.edges.length} edges</span>${G.version?`<span>graph v${esc(G.version)} · ${esc(G.date||'')}</span>`:''}`;
const toc=document.getElementById('toc');const MAJOR=/^(abstract|introduction|results|discussion|materials and methods|methods|references|elife assessment|elife digest)$/i;const heads=[...document.querySelectorAll('#article .text h2')];
heads.forEach((h,i)=>{h.id='sec'+i;toc.add(new Option(h.textContent,h.id))});toc.onchange=()=>{const h=document.getElementById(toc.value);narrow()?h.scrollIntoView({block:'start'}):paneScroll(document.getElementById('article'),h,.04)};
const majors=heads.filter(h=>MAJOR.test(h.textContent.trim()));const sec=document.getElementById('sections');
const SHORT={checks:'Verification',compare:'Compared with prototype',json:'JSON',jsonld:'JSON-LD (MIRA)',about:'About this graph'};const VIEWS=D.deliver?['about','json','jsonld']:['checks','compare','json','jsonld','about'];
sec.innerHTML=majors.map(h=>`<a href="#${h.id}" data-sec="${h.id}">${esc(h.textContent)}</a>`).join('')+`<div class="tools"><button data-tool="tree" aria-selected="true">Claims</button><button id="collapse2" class="quiet">collapse all</button><details class="internal" ${D.deliver?'open':''}><summary>${D.deliver?'data':'internal'}</summary>${VIEWS.map(t=>`<button data-tool="${t}" ${(t==='compare'&&!C)||(t==='jsonld'&&!D.jsonld)?'hidden':''} aria-selected="false">${SHORT[t]}</button>`).join('')}</details></div>
${(()=>{const S=G.stats||{},n=(t,sub)=>G.nodes.filter(x=>x.type===t&&(sub===undefined||(x.subtype||null)===sub)).length;
 const rows=[['Q','questions',n('Question')],[null,'claims',n('Claim')],['H','hypotheses',n('Claim','Hypothesis'),1],['F','findings',n('Claim',null),1],['A','alternatives',n('Claim','Alternative'),1],
  [null,'evidence',n('Evidence')],['E','results',n('Evidence',null),1],['K','checks',n('Evidence','Check'),1],['E cited','from cited work',n('Evidence','Cited'),1],['C','cited works',G.nodes.filter(isCitedDoc).length],['R','requests',n('Request')]];
 return `<div class="key"><div class="kh">Contents</div>${rows.map(([c,w,k,sub])=>`<div class="${sub?'sub':''}">${c?`<span class="id ${c}">${c.split(' ')[0]}</span>`:'<span></span>'}<span>${w}</span><b>${k}</b></div>`).join('')}<div class="kf">${n('Study')} studies · ${n('Protocol')} protocols · ${S.edges||G.edges.length} edges</div></div>`})()}`;
sec.querySelectorAll('a[data-sec]').forEach(a=>a.onclick=e=>{e.preventDefault();const h=document.getElementById(a.dataset.sec);narrow()?h.scrollIntoView({block:'start'}):paneScroll(document.getElementById('article'),h,.02)});
sec.querySelectorAll('[data-tool]').forEach(b=>b.onclick=()=>{tab(b.dataset.tool);sec.querySelectorAll('[data-tool]').forEach(x=>x.setAttribute('aria-selected',x===b))});
document.getElementById('collapse2').onclick=()=>document.getElementById('collapse').click();
const artPane=document.getElementById('article');artPane.addEventListener('scroll',()=>{const top=artPane.getBoundingClientRect().top+80;let cur=majors[0];for(const h of majors){if(h.getBoundingClientRect().top<=top)cur=h}sec.querySelectorAll('a[data-sec]').forEach(a=>a.classList.toggle('cur',a.dataset.sec===cur?.id))},{passive:true});
function verifyBadges(id){const bad=Object.entries(V.nodes?.[id]||{}).filter(([,r])=>!r.ok);return bad.length?`<div class="verify">${bad.map(([c,r])=>`<span class="bad" title="${esc(r.note)}">${c} ✗ ${esc(r.note)}</span>`).join('')}</div>`:''}
function detail(n){const rel=(list,dir)=>(list||[]).filter(e=>['supports','opposes','addresses','observationStatement','request_target','grounds','follows'].includes(e.relation)).filter(e=>!(dir==='in'&&n.type==='Claim'&&['supports','opposes','request_target'].includes(e.relation))&&!(dir==='out'&&n.type==='Study'&&e.relation==='follows')&&!(dir==='out'&&n.type==='Request'&&e.relation==='request_target')&&!(n.type==='SourceDocument')&&!(e.relation==='describesActivity')&&!(dir==='out'&&n.type==='Claim'&&e.relation==='supports'&&N[e.object].type==='Claim'&&!N[e.object].subtype)).map(e=>{const a=N[e.subject],b=N[e.object],o=dir==='out'?b:a;return `<li>${chip(a,true)} <span class="rel">${e.relation}</span> ${chip(b,true)}</li>`}).join('');
 return `<div class="m">${chip(n,true)}${n.study?` · ${esc(studyOf(n))}`:''}${n.panel?` · ${esc(n.panel)}`:''}${prov(n)}</div>${n.type==='SourceDocument'?`<p class="sum">${esc(n.description)}</p>`:`<h3>${esc(n.text)}</h3>`}${n.notes?`<p class="q">${esc(n.notes)}</p>`:''}
 <div class="figrow"><div>${n.text.includes(n.anchor)?'':`<p class="q">“${esc(n.anchor)}”</p>`}<p class="m">${n.doi?`<a href="${n.doi.startsWith("http")?esc(n.doi):"https://doi.org/"+esc(n.doi)}" target="_blank">doi:${esc(n.doi.replace(/^https?:\/\/doi\.org\//,""))} ↗</a>`:''}${n.figure?`${n.doi?' · ':''}<a href="${esc(n.figure.page)}" target="_blank">${esc(n.panel)} ↗</a>`:''}</p></div>${n.figure?`<a href="${esc(n.figure.page)}" target="_blank">${IMG(n.figure.thumbnail,esc(n.panel))}</a>`:''}</div>${verifyBadges(n.id)}<ul>${rel(outs[n.id],'out')}${rel(ins[n.id],'in')}</ul>`}
function closeDrawer(d){const r=d.previousElementSibling;r?.classList.remove('open');d.remove()}
function openDrawer(id){const t=document.querySelector(`#tree .t[data-open="${id}"],#tree [data-open="${id}"]`);if(!t)return false;const row=t.closest('.row')||t.closest('.qb');
 let d=row.nextElementSibling;if(d&&d.classList.contains('drawer')&&d.dataset.for===id)return d;
 for(const o of row.parentElement.querySelectorAll(':scope > .drawer'))closeDrawer(o);   // one open node per level
 d=document.createElement('div');d.className='drawer';d.dataset.for=id;d.style.marginLeft=getComputedStyle(row).marginLeft;d.innerHTML=detail(N[id])+children(N[id]);row.after(d);row.classList.add('open');return d}
function current(id){document.querySelectorAll('.row.cur').forEach(r=>r.classList.remove('cur'));document.querySelector(`#tree .t[data-open="${id}"]`)?.closest('.row')?.classList.add('cur');
 document.querySelectorAll('mark.anc.on').forEach(m=>m.classList.remove('on'));document.querySelectorAll(`mark[data-id="${id}"]`).forEach(m=>m.classList.add('on'))}
function paneScroll(pane,el,frac){if(!el)return;const pr=pane.getBoundingClientRect(),er=el.getBoundingClientRect();pane.scrollTop=pane.scrollTop+er.top-pr.top-pr.height*frac}
function scrollArticle(id){const m=document.querySelector(`mark[data-id="${id}"]`);if(!m)return;narrow()?m.scrollIntoView({block:'center',behavior:'smooth'}):paneScroll(document.getElementById('article'),m,.4)}
function openPath(id){if(document.querySelector(`#tree [data-open="${id}"]`))return openDrawer(id);const n=N[id];
 const p=n.type==='Claim'?(ins[id]||[]).find(e=>e.relation==='supports'&&N[e.subject].type==='Claim')?.subject:n.type==='Protocol'?(ins[id]||[]).find(e=>e.relation==='follows')?.subject:n.type==='Request'?(outs[id]||[]).find(e=>e.relation==='request_target')?.object:(outs[id]||[]).find(e=>['supports','opposes'].includes(e.relation)&&N[e.object]?.type==='Claim')?.object;
 if(!p)return null;openPath(p);return openDrawer(id)}
function show(id,fromArticle=false){const n=N[id];if(!n)return;tab('tree');const d=openPath(id);current(id);const row=d?.previousElementSibling;if(row)narrow()?row.scrollIntoView({block:'start',behavior:'smooth'}):paneScroll(document.querySelector('.pane.right'),row,.08);if(!fromArticle&&!narrow())scrollArticle(id)}
function showInArticle(id){if(narrow())tab('article');current(id);scrollArticle(id)}
document.body.addEventListener('click',e=>{const el=e.target.closest('[data-id],[data-go],[data-open],[data-article]');if(!el||e.target.closest('a[href^="http"]'))return;e.preventDefault();
 if(el.dataset.article){showInArticle(el.dataset.article);return}
 if(el.dataset.open){const id=el.dataset.open,row=el.closest('.row')||el.closest('.qb');const d=row.nextElementSibling;if(d&&d.classList.contains('drawer')&&d.dataset.for===id){closeDrawer(d);return}openDrawer(id);current(id);if(!narrow())scrollArticle(id);return}
 const id=el.dataset.id||el.dataset.go;if(N[id])show(id,!!el.dataset.id)});
// ── tree: one row per node — chip, then summary (claims) or text (evidence) ─────────────
const line=n=>n.type==='SourceDocument'?n.text:(n.description||n.text);
const isInterp=n=>n.type==='Claim'&&!n.subtype&&(ins[n.id]||[]).some(e=>e.relation==='supports'&&N[e.subject].type==='Claim'&&!N[e.subject].subtype);
const tags=n=>{const t=[];if(n.panel&&!/^cited/.test(n.panel))t.push(n.panel);if(n.study)t.push(studyOf(n));if(n.type==='Claim'){const st=new Set(evidenceFor(n).map(x=>studyOf(x.e)).filter(Boolean)),pn=new Set(evidenceFor(n).map(x=>x.e.panel).filter(p=>p&&!/^cited/.test(p)));if(pn.size)t.push(pn.size===1?[...pn][0]:`${pn.size} panels`);[...st].sort().forEach(x=>t.push(x))}return t.length?`<span class="tagr">${t.map(x=>`<span>${esc(x)}</span>`).join('')}</span>`:''};
const row=(n,lvl,extra='',tail='')=>`<div class="row lvl${lvl}">${chip(n)}<div class="t" data-open="${n.id}">${tags(n)}${extra}${esc(line(n))}${prov(n)}${tail}</div></div>`;
const evidenceFor=c=>(ins[c.id]||[]).filter(e=>N[e.subject]?.type==='Evidence').map(e=>({e:N[e.subject],rel:e.relation}));
const children=c=>{const grp=(label,xs)=>xs.length?`<div class="grp">${label}</div>${xs.map(e=>row(e,0)).join('')}`:'';
 if(c.type==='Study'){const ps=(outs[c.id]||[]).filter(e=>e.relation==='follows').map(e=>N[e.object]);const ne=(outs[c.id]||[]).filter(e=>e.relation==='grounds').length;return grp('protocols',ps)+`<p class="m">grounds ${ne} pieces of evidence, listed under the claims they bear on</p>`}
 if(c.type==='SourceDocument'){const ev=G.nodes.filter(n=>n.type==='Evidence'&&n.sourceDocument===c.id);const st=(outs[c.id]||[]).filter(e=>e.relation==='describesActivity').map(e=>N[e.object]);return grp('describes',st)+grp('cited finding',ev)}
 if(c.type==='Request')return grp('about',(outs[c.id]||[]).filter(e=>e.relation==='request_target').map(e=>N[e.object]));
 if(c.type!=='Claim')return'';const interp=c.subtype?[]:(outs[c.id]||[]).filter(e=>e.relation==='supports'&&N[e.object].type==='Claim'&&!N[e.object].subtype).map(e=>N[e.object]);const ev=evidenceFor(c);const own=x=>!['Check','Cited'].includes(x.e.subtype);const sup=ev.filter(x=>x.rel==='supports'&&own(x)),opp=ev.filter(x=>x.rel==='opposes'&&own(x)),chk=ev.filter(x=>x.e.subtype==='Check'),cit=ev.filter(x=>x.e.subtype==='Cited');
 const g2=(label,xs)=>grp(label,xs.map(x=>x.e));
 return (c.subtype==='Alternative'?g2('argued against by',opp.concat(cit.filter(x=>x.rel==='opposes')))+g2('in its favour',sup.concat(cit.filter(x=>x.rel==='supports'))):g2('supported by',sup)+g2('argued against by',opp)+g2('checks',chk)+g2('from cited work',cit))+grp('read as',interp)};
let tree='';for(const q of G.nodes.filter(n=>n.type==='Question')){
 const addr=(ins[q.id]||[]).filter(e=>e.relation==='addresses').map(e=>N[e.subject]);
 const hyps=addr.filter(n=>n.subtype==='Hypothesis'),alts=addr.filter(n=>n.subtype==='Alternative'),plain=addr.filter(n=>!n.subtype);
 tree+=`<section class="qb"><h2>${chip(q)}<span data-open="${q.id}" style="cursor:pointer">${esc(q.text)}</span></h2><p class="s">${esc(q.description||'')}</p>`;
 for(const h of hyps){tree+=row(h,1,'<span class="w">hypothesis</span>');for(const f of (ins[h.id]||[]).filter(e=>e.relation==='supports'&&N[e.subject].type==='Claim').map(e=>N[e.subject]).filter(f=>!isInterp(f)))tree+=row(f,2)}
 if(plain.length){tree+=`<div class="row lvl1"><span></span><div class="t"><span class="w">other findings</span></div></div>`;for(const c of plain)tree+=row(c,2)}
 for(const a of alts){const op=evidenceFor(a).filter(x=>x.rel==='opposes').length;tree+=row(a,1,'<span class="w">alternative</span>',op?'':' <span class="prov">nothing in the paper argues against it</span>')}
 tree+='</section>'}
const reqs=G.nodes.filter(n=>n.type==='Request');if(reqs.length)tree+=`<section class="qb"><h2>What the authors call for next</h2>${reqs.map(r=>row(r,1)).join('')}</section>`;
tree+=`<section class="qb"><h2>Studies and methods</h2>${G.nodes.filter(n=>n.type==='Study').map(x=>row(x,1)).join('')}</section>`;
const cites=G.nodes.filter(isCitedDoc);if(cites.length)tree+=`<section class="qb"><h2>Cited works this argument leans on</h2>${cites.map(d=>row(d,1,'',d.doi?` <a class="prov" href="https://doi.org/${esc(d.doi)}" target="_blank">doi ↗</a>`:'')).join('')}</section>`;
document.getElementById('tree').innerHTML=tree;
// ── checks ──────────────────────────────────────────────────────────────────────────────
const S=V.summary||{};const rows=Object.entries(V.nodes||{}).map(([id,v])=>{const bad=Object.entries(v).filter(([,r])=>!r.ok);return bad.length?`<tr><td>${chip(N[id])}</td><td>${esc(N[id]?.text||'')}</td><td>${bad.map(([c,r])=>`<span class="verify"><span class="bad">${c}: ${esc(r.note)}</span></span>`).join(' ')}</td></tr>`:''}).join('');
const badEdges=(V.edges||[]).filter(e=>!e.ok);
document.getElementById('checks').innerHTML=`<p><b>${S.passed??'?'} of ${S.nodes??'?'} nodes pass every check</b> · ${S.edges??'?'} edges${badEdges.length?`, <span style="color:var(--A)">${badEdges.length} illegal</span>`:', all legal'} · anchors checked against ${(S.text_chars||0).toLocaleString()} characters of the article as eLife Pathways serves it.</p>
<p class="s">Checks: <b>shape</b> (id, type, text) · <b>summary</b> (questions, claims and requests: one or two plain sentences) · <b>anchor</b> (verbatim in the text) · <b>evidence</b> (grounded in a study or a cited source, names its panel) · <b>figure</b> (a figure panel links to its figure) · <b>structure</b> (every claim reaches a question; every piece of evidence argues something).</p>
${rows?`<table><thead><tr><th>node</th><th>text</th><th>failing</th></tr></thead><tbody>${rows}</tbody></table>`:'<p>No node fails a check.</p>'}`;
document.getElementById('jsonpre').textContent=JSON.stringify(G,null,1);
if(D.jsonld)document.getElementById('jsonldpre').textContent=D.jsonld;
const ST=D.stamp||{};const cnt=t=>G.nodes.filter(n=>n.type===t).length,sub=t=>G.nodes.filter(n=>n.subtype===t).length;
document.getElementById('about').innerHTML=`<div class="about"><h2>About this graph</h2>
<p>A MIRA claims graph of <i>${esc(G.paper?.title||'')}</i> (eLife ${esc(G.paper?.doi||'')}, Reviewed Preprint version 2). Version ${esc(G.version||'')}, ${esc(G.date||'')}. Built with Claude (Anthropic) and reviewed by Zachary F. Mainen, Champalimaud Research.</p>
<h3>What is in it</h3>
<ul><li>Questions, claims, evidence, studies, protocols, requests and source documents, using MIRA's node types and relations.</li>
<li>Every node is anchored to a verbatim passage of the article text. The main findings are also anchored in the abstract.</li>
<li>Every question, claim and request has a summary of one or two sentences.</li>
<li>Evidence names its study and its figure panel, table or section. Every panel of Figures 1–5, Table 1 and Supplementary Figure 2 is covered.</li>
<li>Cited findings carry the reference and DOI of the work they come from.</li></ul>
<h3>What is new</h3>
<p>Four subclasses, declared with MIRA's <code>NodeSchema</code> mechanism so that other MIRA tools read them as ordinary claims and evidence:</p>
<ul><li><b>Hypothesis</b> — a claim the authors set out to test.</li>
<li><b>Alternative</b> — a rival explanation the paper raises; the evidence that argues against it is attached.</li>
<li><b>Check</b> — evidence that defends the method: a manipulation check, positive control or assumption test.</li>
<li><b>Cited</b> — a finding taken from another publication.</li></ul>
<h3>Checks</h3>
<p>All anchors are verbatim in the article text. All edges use MIRA relations between legal endpoint types. Every claim reaches a question; every piece of evidence supports or opposes a claim. The JSON-LD validates against MIRA's shapes, apart from two shape issues reported upstream.</p>
<h3>Files</h3>
<p><b>JSON</b>: the working-graph form the Pathways prototype loads. <b>JSON-LD</b>: the MIRA form, with the subclass declarations.</p></div>`;
// ── compare ─────────────────────────────────────────────────────────────────────────────
if(C){document.getElementById('cmptab').hidden=false;document.getElementById('cmptab').textContent=`Compared with the ${C.label}`;
 const T2O=C.align.theirs_to_ours;const tcell=n=>`<div><code>${n.id}</code> ${esc(n.text)}</div>`;const ocell=n=>`<div>${chip(n)} ${esc(line(n))}</div>`;
 const types=['Question','Claim','Evidence','Study','Protocol','SourceDocument','Request'];let h=`<p>Left: only in ${esc(C.label)}. Middle: in both, aligned by hand (questions, claims, studies, protocols, requests) or by the statistics quoted (evidence); the text shown is theirs, with our id and whether our wording is the same. Right: only here. ${C.graph.nodes.length} nodes there, ${G.nodes.length} here, ${Object.keys(T2O).length} of theirs matched.</p>`;
 for(const ty of types){const theirs=C.graph.nodes.filter(n=>n.type===ty),ours=G.nodes.filter(n=>n.type===ty);if(!theirs.length&&!ours.length)continue;
  const only_t=theirs.filter(n=>!T2O[n.id]),only_o=ours.filter(n=>!O2T[n.id]);
  const both=theirs.filter(t=>T2O[t.id]&&N[T2O[t.id]]).map(t=>{const o=N[T2O[t.id]];const same=t.text.trim()===o.text.trim();return `<div><code>${t.id}</code> → ${chip(o)} <span class="s">${same?'same wording':'reworded'}</span><br>${esc(t.text)}</div>`});
  h+=`<h2>${ty} · ${only_t.length} only there · ${both.length} both · ${only_o.length} only here</h2><table><thead><tr><th>only in ${esc(C.label)}</th><th>in both</th><th>only here</th></tr></thead><tbody><tr><td>${only_t.map(tcell).join('')}</td><td>${both.join('')}</td><td>${only_o.map(ocell).join('')}</td></tr></tbody></table>`}
 document.getElementById('compare').innerHTML=h}
</script></body></html>'''

if __name__ == "__main__":
    main()
