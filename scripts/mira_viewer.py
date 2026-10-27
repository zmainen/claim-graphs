#!/usr/bin/env python3
"""mira_viewer — one self-contained HTML page that shows a MIRA working graph the way eLife
Pathways' design prototype does: the article text with claim markers at their anchors and the
summary beside the passage; a coloured claims tree (question → hypothesis → findings → evidence,
alternatives with what opposes them, checks marked); and the verification marks.

The JSON, the article text and the verification verdicts are embedded, so the file is the
deliverable's review surface and can be opened anywhere. Nothing is typed into it by hand.

Usage: mira_viewer.py <graph.json> <anchor-text.txt> [--out viewer.html] [--embed-figures]
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
    for n in g["nodes"]:
        f = n.get("figure")
        if not f or not f.get("thumbnail"): continue
        url = f["thumbnail"]
        if url not in seen:
            path = os.path.join(cache, hashlib.sha1(url.encode()).hexdigest() + ".jpg")
            if not os.path.exists(path):
                with urllib.request.urlopen(url, timeout=60) as r: open(path, "wb").write(r.read())
            seen[url] = "data:image/jpeg;base64," + base64.b64encode(open(path, "rb").read()).decode()
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
    cmp = None
    if "--compare" in a:
        i = a.index("--compare")
        cmp = {"graph": json.load(open(a[i + 1], encoding="utf-8")), "align": json.load(open(a[i + 2], encoding="utf-8")),
               "label": a[a.index("--compare-label") + 1] if "--compare-label" in a else "eLife's graph"}
    payload = json.dumps({"graph": g, "text": text, "verification": v, "compare": cmp, "thumbs": thumbs}, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("__TITLE__", title.replace("<", "&lt;")).replace("__PAYLOAD__", payload)
    open(out, "w", encoding="utf-8").write(html)
    print(f"wrote {out} ({len(html) // 1024} KB)")

TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="claude:viewport-fit-sides" content="cover"><title>Gädeke claims viewer</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap">
<style>
/* Editorial reading tool. Two columns: the article as a journal page on the left, the claims apparatus on the right.
   Paper is warm; colour belongs only to the typed id chips; the current node is marked in vermilion on both sides. */
:root{color-scheme:light;--paper:#faf8f3;--paper-2:#f1ede4;--paper-3:#e8e2d5;--ink:#1c1a16;--ink-2:#55514a;--ink-3:#8c877d;--rule:#ddd6c8;--link:#1f4e8c;--cur:#c8401e;
 --Q:#5b3f8f;--H:#1f4e8c;--F:#2d6b45;--A:#b2402d;--E:#4d7a5f;--K:#b2731c;--R:#7a5a2a;--S:#6b665c;--P:#6b665c;--D:#6b665c;--C:#6b665c;
 --serif:"Newsreader",Georgia,"Times New Roman",serif;--sans:"IBM Plex Sans","Helvetica Neue",Arial,sans-serif;--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--paper:#191814;--paper-2:#22201b;--paper-3:#2c2923;--ink:#e9e4d8;--ink-2:#b7b1a3;--ink-3:#847e72;--rule:#35322b;--link:#8fb4ea;--cur:#f07a55;
 --Q:#c2a6ea;--H:#8fb4ea;--F:#8ccaa0;--A:#ea8e7a;--E:#8ccaa0;--K:#e4ae5a;--R:#d6b47c;--S:#9b958a;--P:#9b958a;--D:#9b958a;--C:#9b958a}}
:root[data-theme="dark"]{color-scheme:dark;--paper:#191814;--paper-2:#22201b;--paper-3:#2c2923;--ink:#e9e4d8;--ink-2:#b7b1a3;--ink-3:#847e72;--rule:#35322b;--link:#8fb4ea;--cur:#f07a55;
 --Q:#c2a6ea;--H:#8fb4ea;--F:#8ccaa0;--A:#ea8e7a;--E:#8ccaa0;--K:#e4ae5a;--R:#d6b47c;--S:#9b958a;--P:#9b958a;--D:#9b958a;--C:#9b958a}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--paper);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.5;display:flex;flex-direction:column;height:100vh;overflow:hidden;
 padding-left:max(20px,env(safe-area-inset-left,0px));padding-right:max(20px,env(safe-area-inset-right,0px))}
a{color:var(--link);text-decoration-thickness:1px;text-underline-offset:2px} button{font:inherit;cursor:pointer}
/* masthead */
header.top{flex:none;display:grid;grid-template-columns:1fr auto;gap:.2rem 2rem;align-items:end;padding:.9rem 0 .6rem;border-bottom:2px solid var(--ink)}
header.top h1{font:500 1.35rem/1.2 var(--serif);letter-spacing:-.005em;margin:0;max-width:60ch}
header.top .meta{grid-column:1;font-size:.8rem;color:var(--ink-2);display:flex;flex-wrap:wrap;gap:.2rem 1rem}header.top .meta b{font-weight:500;color:var(--ink)}
.legend{grid-column:2;grid-row:1;display:flex;flex-wrap:wrap;justify-content:end;gap:.25rem .7rem;font-size:.74rem;color:var(--ink-2)}
.tabs{grid-column:2;grid-row:2;display:flex;justify-content:end;gap:.15rem}.tabs button{background:none;border:1px solid transparent;border-radius:3px;padding:.2rem .6rem;color:var(--ink-2);font-size:.82rem;letter-spacing:.01em}
.tabs button[aria-selected="true"]{background:var(--ink);color:var(--paper);border-color:var(--ink)}.tabs button:hover:not([aria-selected="true"]){border-color:var(--rule)}
#collapse{margin-left:.5rem;color:var(--ink-3);border:1px dashed var(--rule)}
/* panes */
.split{display:grid;grid-template-columns:minmax(0,11fr) minmax(0,13fr);grid-template-rows:minmax(0,1fr);gap:0;flex:1;min-height:0}
.pane{overflow-y:auto;min-height:0}#article{border-right:1px solid var(--rule);padding-right:1.6rem}.pane.right{padding-left:1.6rem}
#arttab{display:none}
@media (max-width:900px){body{height:auto;overflow:auto;display:block}.split{display:block}.pane{overflow:visible}#article{border:0;padding:0}.pane.right{padding:0}#article:not(.on){display:none}#arttab{display:inline-block}header.top{display:flex;flex-wrap:wrap;gap:.4rem 1rem}}
main{padding-block:1rem 5rem}main:not(.on){display:none !important}main.on{display:block}
/* id chip */
.id{display:inline-block;font:500 .7rem/1.5 var(--mono);padding:0 .32rem;border-radius:2px;color:var(--paper);background:var(--ink-3);min-width:2.3em;text-align:center;cursor:pointer;vertical-align:1px;letter-spacing:.02em}
.id.Q{background:var(--Q)}.id.H{background:var(--H)}.id.F{background:var(--F)}.id.A{background:var(--A)}.id.E{background:var(--E)}.id.K{background:var(--K)}.id.R{background:var(--R)}.id.C{background:var(--C)}
.id.cited{background:none !important;color:var(--E);border:1px dashed var(--E)}
.id.ref{background:none !important;border:1px solid currentColor;font-weight:500;opacity:.9}.id.ref.Q{color:var(--Q)}.id.ref.H{color:var(--H)}.id.ref.F{color:var(--F)}.id.ref.A{color:var(--A)}.id.ref.E{color:var(--E)}.id.ref.K{color:var(--K)}.id.ref.R{color:var(--R)}.id.ref.C,.id.ref.S,.id.ref.P,.id.ref.D{color:var(--ink-3)}
.prov{font:400 .7rem var(--mono);color:var(--ink-3);margin-left:.45rem;white-space:nowrap}.prov.new{color:var(--F)}
/* article */
.toc{position:sticky;top:0;z-index:2;background:var(--paper);padding:.6rem 0 .5rem;border-bottom:1px solid var(--rule);display:flex;gap:.6rem;align-items:center;font-size:.78rem;color:var(--ink-3)}
.toc select{font:inherit;color:var(--ink-2);background:var(--paper-2);border:1px solid var(--rule);border-radius:3px;padding:.15rem .4rem;max-width:100%}
.text{font-family:var(--serif);font-size:1.12rem;line-height:1.6;max-width:66ch;padding-block:1.2rem 5rem;font-variation-settings:"opsz" 16}
.text h2{font:500 1.3rem/1.25 var(--serif);margin:2.2rem 0 .6rem;scroll-margin-top:3.2rem}.text p{margin:0 0 1rem;text-wrap:pretty}
.text .fig{font:.9rem/1.5 var(--sans);color:var(--ink-2);border-left:3px solid var(--paper-3);padding-left:.8rem;margin:1.2rem 0}
mark.anc{background:none;color:inherit;border-bottom:1.5px solid var(--rule);cursor:pointer;padding-bottom:1px;transition:background .15s}mark.anc:hover{background:var(--paper-2)}
mark.anc.on{background:color-mix(in srgb,var(--cur) 12%,transparent);border-bottom-color:var(--cur)}
.text .id{margin-left:.25rem;vertical-align:3px;font-size:.62rem}
/* claims pane */
#tree{max-width:84ch}
.qb{margin:0 0 2.4rem}.qb>h2{position:sticky;top:0;z-index:2;background:var(--paper);font:500 1.15rem/1.3 var(--serif);margin:0;padding:.7rem 0 .4rem;display:flex;gap:.6rem;align-items:baseline;border-bottom:1px solid var(--ink)}
.qb>h2 .id{font-size:.68rem;vertical-align:2px}.qb>.s{color:var(--ink-2);font-size:.88rem;margin:.5rem 0 .8rem}
.row{display:grid;grid-template-columns:auto 1fr;gap:.65rem;align-items:baseline;padding:.38rem 0;border-top:1px solid var(--rule);scroll-margin-top:3.4rem;transition:background .15s}
.row:hover{background:var(--paper-2)}.row .t{cursor:pointer;font-size:.95rem;line-height:1.45}.row .w{font:500 .64rem var(--sans);letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3);margin-right:.45rem}
.row.lvl1{margin-left:0}.row.lvl2{margin-left:1.8rem}.row.lvl3{margin-left:3.6rem}
.row.open>.id{box-shadow:0 0 0 2px var(--paper),0 0 0 3.5px currentColor}.row.cur{background:color-mix(in srgb,var(--cur) 8%,transparent)}.row.cur>.id{outline:2px solid var(--cur);outline-offset:1px}
.drawer{background:var(--paper-2);border-left:3px solid var(--paper-3);padding:.8rem 1rem .9rem 1.1rem;margin:.1rem 0 .8rem;font-size:.9rem;display:grid;gap:.45rem}
.drawer .m{color:var(--ink-3);font-size:.78rem;font-family:var(--mono)}.drawer .m a{font-family:var(--sans)}
.drawer h3{margin:0;font:500 1.08rem/1.35 var(--serif);text-wrap:pretty}.drawer .sum{margin:0;font-size:.95rem}.drawer .q{color:var(--ink-2);font-style:italic;margin:0;font-family:var(--serif);font-size:.98rem}
.drawer .figrow{display:grid;grid-template-columns:1fr auto;gap:.8rem;align-items:start}.drawer img{max-width:260px;border:1px solid var(--rule);background:#fff;border-radius:2px}
.drawer ul{margin:0;padding:0;list-style:none;display:grid;gap:.2rem}.drawer li{font-size:.86rem}.rel{font:500 .7rem var(--mono);color:var(--ink-3);margin:0 .2rem;letter-spacing:.02em}
.drawer .grp{font:500 .64rem var(--sans);letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3);margin-top:.5rem}.drawer .row{border-top:1px solid var(--rule);padding:.3rem 0;margin-left:0}.drawer .row:hover{background:var(--paper)}
.drawer .drawer{margin-left:0 !important;background:var(--paper);border-left-color:var(--rule)}
.verify{display:flex;flex-wrap:wrap;gap:.3rem}.verify span{font-size:.72rem;padding:.05rem .4rem;border-radius:2px;background:var(--paper);border:1px solid var(--rule)}.verify .bad{color:var(--A);border-color:var(--A)}
/* checks, compare, json */
#checks{max-width:90ch}#checks table{width:100%;border-collapse:collapse;font-size:.88rem}#checks td,#checks th{text-align:left;vertical-align:top;padding:.3rem .5rem;border-top:1px solid var(--rule)}
#compare.on{display:block;max-width:1200px}#compare table{width:100%;border-collapse:collapse;font-size:.86rem;margin:.4rem 0 1.4rem}#compare th,#compare td{vertical-align:top;text-align:left;padding:.35rem .5rem;border-top:1px solid var(--rule);width:33%}#compare th{font-weight:500;color:var(--ink-2)}#compare td>div{margin:.3rem 0}#compare .s{color:var(--ink-3);font-size:.78rem}#compare h2{font:500 1.05rem var(--serif);margin:1.4rem 0 .2rem}
#json pre{font:.76rem/1.5 var(--mono);white-space:pre-wrap;word-break:break-word}
@media print{body{height:auto;overflow:visible;display:block}.split{display:block}.pane{overflow:visible}#article{border:0}.tabs,#collapse,.toc{display:none}main{display:block !important}#json,#compare,#checks{display:none !important}}
</style></head><body>
<header class="top"><h1>__TITLE__</h1><div class="meta" id="meta"></div>
<div class="legend"><span><span class="id Q">Q</span> question</span><span><span class="id H">H</span> hypothesis</span><span><span class="id F">F</span> finding</span><span><span class="id A">A</span> alternative</span><span><span class="id E">E</span> evidence</span><span><span class="id K">K</span> check</span><span><span class="id E cited">E</span> cited finding</span><span><span class="id C">C</span> cited work</span><span><span class="id R">R</span> request</span></div>
<div class="tabs" role="tablist"><button role="tab" data-tab="article" id="arttab">Article</button><button role="tab" data-tab="tree" aria-selected="true">Claims</button><button role="tab" data-tab="checks">Verification</button><button role="tab" data-tab="compare" id="cmptab" hidden>Compared</button><button role="tab" data-tab="json">JSON</button><button id="collapse" title="close every open node">collapse</button></div></header>
<div class="split"><section id="article" class="pane"><nav class="toc">section <select id="toc"></select></nav><div class="text" id="text"></div></section>
<section class="pane right"><main id="tree" class="on"></main><main id="checks"></main><main id="compare"></main><main id="json"><pre id="jsonpre"></pre></main></section></div>
<script id="data" type="application/json">__PAYLOAD__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);const G=D.graph,T=D.text,V=D.verification,C=D.compare;
const N=Object.fromEntries(G.nodes.map(n=>[n.id,n]));const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const WORD={Q:'question',H:'hypothesis',F:'finding',A:'alternative',E:'evidence',K:'check',C:'cited work',R:'request',S:'study',P:'protocol',D:'this paper'};
const isCitedDoc=n=>n.type==='SourceDocument'&&/^C\d/.test(n.id);
const pre=n=>isCitedDoc(n)?'C':n.subtype==='Hypothesis'?'H':n.subtype==='Alternative'?'A':n.subtype==='Check'?'K':n.type==='Claim'?'F':n.type==='Evidence'?'E':n.type==='Question'?'Q':n.type==='Request'?'R':n.type==='Study'?'S':n.type==='Protocol'?'P':'D';
const chip=(n,ref=false)=>`<span class="id ${pre(n)}${n.subtype==='Cited'?' cited':''}${ref?' ref':''}" data-go="${n.id}">${n.id}</span>`;
const outs={},ins={};for(const e of G.edges){(outs[e.subject]??=[]).push(e);(ins[e.object]??=[]).push(e)}
const thumb=u=>D.thumbs?.[u]||u;const TN=C?Object.fromEntries(C.graph.nodes.map(n=>[n.id,n])):{};const O2T=C?C.align.ours_to_theirs:null;
const prov=n=>!C?'':O2T[n.id]?`<span class="prov" title="${esc(C.label)}: ${esc(O2T[n.id].map(t=>TN[t].text).join('\n'))}">= ${O2T[n.id].join(', ')}</span>`:['Evidence','SourceDocument'].includes(n.type)?'':`<span class="prov new">new</span>`;
const studyOf=n=>n.study?N[n.study]?.text.split(':')[0]||n.study:'';
// tabs
const tab=name=>{document.querySelectorAll('.tabs [data-tab]').forEach(x=>x.setAttribute('aria-selected',x.dataset.tab===name));document.querySelectorAll('main').forEach(m=>m.classList.toggle('on',m.id===name));document.getElementById('article').classList.toggle('on',name==='article')};
document.querySelectorAll('.tabs [data-tab]').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
document.getElementById('collapse').onclick=()=>{document.querySelectorAll('.drawer').forEach(d=>d.remove());document.querySelectorAll('.row.open,.row.cur').forEach(r=>r.classList.remove('open','cur'));document.querySelectorAll('mark.anc.on').forEach(m=>m.classList.remove('on'))};
const narrow=()=>matchMedia('(max-width:900px)').matches;
// ── article: mark anchors; margin shows chip + summary ──────────────────────────────────
const anchored=G.nodes.filter(n=>n.anchor&&T.includes(n.anchor)&&n.type!=='SourceDocument').sort((a,b)=>b.anchor.length-a.anchor.length);
let segs=[{t:T}];
for(const n of anchored){const out=[];for(const s of segs){if(s.n){out.push(s);continue}let i=s.t.indexOf(n.anchor);if(i<0){out.push(s);continue}out.push({t:s.t.slice(0,i)});out.push({t:n.anchor,n});out.push({t:s.t.slice(i+n.anchor.length)})}segs=out.filter(s=>s.t.length)}
const html=[];let para=[];const flush=()=>{if(!para.length)return;const h=para.join('');const ids=[...new Set([...h.matchAll(/data-id="([^"]+)"/g)].map(m=>m[1]))];
 const body=h.startsWith('## ')?`<h2>${h.slice(3)}</h2>`:h.startsWith('[Figure')||h.startsWith('[Table')?`<p class="fig">${h}</p>`:`<p>${h}</p>`;
 html.push(body);para=[]};
for(const s of segs){const parts=s.t.split('\n\n');parts.forEach((p,i)=>{if(i>0){flush()}const t=p.replace(/\n/g,' ');if(!t)return;para.push(s.n?`<mark class="anc" data-id="${s.n.id}">${esc(t)}</mark><span class="id ${pre(s.n)}" data-id="${s.n.id}">${s.n.id}</span>`:esc(t))})}
flush();document.getElementById('text').innerHTML=html.join('');
const P=G.paper||{};document.getElementById('meta').innerHTML=`${P.authors?`<span><b>${esc(P.authors.map(a=>a.name).join(', '))}</b></span>`:''}${P.doi?`<span><a href="https://doi.org/${esc(P.doi)}" target="_blank">doi:${esc(P.doi)}</a></span>`:''}<span>${G.nodes.length} nodes · ${G.edges.length} edges</span>${G.source?`<span>${esc(G.source)}</span>`:''}`;
const toc=document.getElementById('toc');document.querySelectorAll('#article .text h2').forEach((h,i)=>{h.id='sec'+i;toc.add(new Option(h.textContent,h.id))});toc.onchange=()=>{const h=document.getElementById(toc.value);narrow()?h.scrollIntoView({block:'start'}):paneScroll(document.getElementById('article'),h,.04)};
function verifyBadges(id){const bad=Object.entries(V.nodes?.[id]||{}).filter(([,r])=>!r.ok);return bad.length?`<div class="verify">${bad.map(([c,r])=>`<span class="bad" title="${esc(r.note)}">${c} ✗ ${esc(r.note)}</span>`).join('')}</div>`:''}
function detail(n){const rel=(list,dir)=>(list||[]).filter(e=>['supports','opposes','addresses','observationStatement','request_target','grounds','follows'].includes(e.relation)).filter(e=>!(dir==='in'&&n.type==='Claim'&&['supports','opposes','request_target'].includes(e.relation))&&!(dir==='out'&&n.type==='Study'&&e.relation==='follows')&&!(dir==='out'&&n.type==='Request'&&e.relation==='request_target')&&!(n.type==='SourceDocument')&&!(e.relation==='describesActivity')&&!(dir==='out'&&n.type==='Claim'&&e.relation==='supports'&&N[e.object].type==='Claim'&&!N[e.object].subtype)).map(e=>{const a=N[e.subject],b=N[e.object],o=dir==='out'?b:a;return `<li>${chip(a,true)} <span class="rel">${e.relation}</span> ${chip(b,true)} ${esc(o.description||o.text)}</li>`}).join('');
 return `<div class="m">${chip(n,true)}${n.study?` · ${esc(studyOf(n))}`:''}${n.panel?` · ${esc(n.panel)}`:''}${prov(n)}</div>${n.type==='SourceDocument'?`<p class="sum">${esc(n.description)}</p>`:`<h3>${esc(n.text)}</h3>`}${n.notes?`<p class="q">${esc(n.notes)}</p>`:''}
 <div class="figrow"><div>${n.text.includes(n.anchor)?'':`<p class="q">“${esc(n.anchor)}”</p>`}<p class="m"><a href="#" data-article="${n.id}">article</a>${n.doi?` · <a href="${n.doi.startsWith("http")?esc(n.doi):"https://doi.org/"+esc(n.doi)}" target="_blank">doi:${esc(n.doi.replace(/^https?:\/\/doi\.org\//,""))} ↗</a>`:''}${n.figure?` · <a href="${esc(n.figure.page)}" target="_blank">${esc(n.panel)} ↗</a>`:''}</p></div>${n.figure?`<a href="${esc(n.figure.page)}" target="_blank"><img src="${thumb(n.figure.thumbnail)}" alt="${esc(n.panel)}"></a>`:''}</div>${verifyBadges(n.id)}<ul>${rel(outs[n.id],'out')}${rel(ins[n.id],'in')}</ul>`}
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
const row=(n,lvl,extra='',tail='')=>`<div class="row lvl${lvl}">${chip(n)}<div class="t" data-open="${n.id}">${extra}${esc(line(n))}${prov(n)}${tail}</div></div>`;
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
