#!/usr/bin/env python3
"""mira_viewer — one self-contained HTML page that shows a MIRA working graph the way eLife
Pathways' design prototype does: the article text with claim markers at their anchors and the
summary beside the passage; a coloured claims tree (question → hypothesis → findings → evidence,
alternatives with what opposes them, checks marked); and the verification marks.

The JSON, the article text and the verification verdicts are embedded, so the file is the
deliverable's review surface and can be opened anywhere. Nothing is typed into it by hand.

Usage: mira_viewer.py <graph.json> <anchor-text.txt> [--out viewer.html]
                      [--compare <other.graph.json> <alignment.json> [--compare-label "eLife's graph"]]
With --compare the viewer gets a "Compared with…" tab: provenance badges on every node of the tree
(its counterpart in the other graph, or "new") and a three-column ledger per node type. The alignment
file comes from mira_align.py.
Expects <graph>.verification.json beside the graph (run mira_verify.py first).
"""
import json, os, sys

def main():
    a = sys.argv[1:]
    gpath, tpath = a[0], a[1]
    out = a[a.index("--out") + 1] if "--out" in a else gpath.replace(".graph.json", ".viewer.html")
    g = json.load(open(gpath, encoding="utf-8"))
    text = open(tpath, encoding="utf-8").read()
    vpath = gpath.replace(".graph.json", ".verification.json")
    v = json.load(open(vpath)) if os.path.exists(vpath) else {"nodes": {}, "edges": [], "summary": {}}
    title = g.get("paper", {}).get("title", "MIRA graph")
    cmp = None
    if "--compare" in a:
        i = a.index("--compare")
        cmp = {"graph": json.load(open(a[i + 1], encoding="utf-8")), "align": json.load(open(a[i + 2], encoding="utf-8")),
               "label": a[a.index("--compare-label") + 1] if "--compare-label" in a else "eLife's graph"}
    payload = json.dumps({"graph": g, "text": text, "verification": v, "compare": cmp}, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("__TITLE__", title.replace("<", "&lt;")).replace("__PAYLOAD__", payload)
    open(out, "w", encoding="utf-8").write(html)
    print(f"wrote {out} ({len(html) // 1024} KB)")

TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="claude:viewport-fit-sides" content="cover"><title>Gädeke claims viewer</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=Source+Sans+3:wght@400;600&family=JetBrains+Mono:wght@400&display=swap">
<style>
/* One line per node, one id chip per node; full text only on demand in the side panel. Palette: paper white, one colour per kind, used only on the chip. */
:root{color-scheme:light;--paper:#fff;--paper-2:#f4f4f2;--ink:#212121;--ink-2:#555;--ink-3:#888;--rule:#dcdcd8;--link:#0a4f8a;
 --Q:#6b3f9c;--H:#1f4e9c;--F:#2b6b3f;--A:#b03a2e;--E:#4a7a5a;--K:#b8740f;--R:#7a5c2e;--S:#777;--P:#777;--D:#777;
 --serif:"Source Serif 4",Georgia,serif;--sans:"Source Sans 3","Helvetica Neue",Arial,sans-serif;--mono:"JetBrains Mono",ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--paper:#17181b;--paper-2:#202228;--ink:#e8e6e1;--ink-2:#b5b2aa;--ink-3:#85827b;--rule:#32353c;--link:#8fb8ea;
 --Q:#c7a3e6;--H:#8fb0ea;--F:#86c79a;--A:#e38b80;--E:#86c79a;--K:#e0aa55;--R:#d6b27c;--S:#999;--P:#999;--D:#999}}
:root[data-theme="dark"]{color-scheme:dark;--paper:#17181b;--paper-2:#202228;--ink:#e8e6e1;--ink-2:#b5b2aa;--ink-3:#85827b;--rule:#32353c;--link:#8fb8ea;
 --Q:#c7a3e6;--H:#8fb0ea;--F:#86c79a;--A:#e38b80;--E:#86c79a;--K:#e0aa55;--R:#d6b27c;--S:#999;--P:#999;--D:#999}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--paper);color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.5;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
a{color:var(--link)} button{font:inherit;cursor:pointer}
header.top{display:flex;flex-wrap:wrap;gap:.4rem 1.2rem;align-items:baseline;padding:.8rem 0 .4rem;border-bottom:1px solid var(--rule);position:sticky;top:env(safe-area-inset-top,0px);background:var(--paper);z-index:3}
header.top h1{font:600 1.05rem var(--sans);margin:0}
.tabs{display:flex;gap:.2rem;margin-left:auto}.tabs button{background:none;border:1px solid var(--rule);border-radius:4px;padding:.3rem .7rem;color:var(--ink-2)}.tabs button[aria-selected="true"]{background:var(--paper-2);color:var(--ink);border-color:var(--ink-3)}
.legend{display:flex;flex-wrap:wrap;gap:.3rem .9rem;font-size:.82rem;color:var(--ink-2)}
main{padding-block:1rem 4rem}main:not(.on){display:none !important}main.on{display:block}
/* id chip: the one thing every node shows everywhere */
.id{display:inline-block;font:600 .72rem var(--mono);padding:.02rem .3rem;border-radius:3px;color:#fff;background:var(--ink-3);min-width:2.2em;text-align:center;cursor:pointer;vertical-align:1px}
.id.Q{background:var(--Q)}.id.H{background:var(--H)}.id.F{background:var(--F)}.id.A{background:var(--A)}.id.E{background:var(--E)}.id.K{background:var(--K)}.id.R{background:var(--R)}
.prov{font-size:.7rem;color:var(--ink-3);margin-left:.4rem;white-space:nowrap}.prov.new{color:var(--F)}
/* article */
#article.on{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:2rem}@media (max-width:900px){#article.on{grid-template-columns:1fr}}
.text{font-family:var(--serif);font-size:1.06rem;line-height:1.65;max-width:70ch}.text h2{font:600 1.25rem var(--sans);margin:1.8rem 0 .5rem}.text p{margin:0 0 .9rem}
.text .fig{font-size:.92rem;color:var(--ink-2);border-left:3px solid var(--rule);padding-left:.8rem;margin:1rem 0}
mark.anc{background:none;border-bottom:2px solid var(--rule);cursor:pointer;padding-bottom:1px}mark.anc:hover,mark.anc.on{background:var(--paper-2)}
.text .id{margin-left:.2rem;vertical-align:2px}
.margin{font-size:.85rem;color:var(--ink-2);border-left:2px solid var(--rule);padding-left:.7rem;margin:.2rem 0 1rem}.margin div{margin:.2rem 0;cursor:pointer;display:flex;gap:.5rem;align-items:baseline}.margin div:hover{color:var(--ink)}
aside.panel{position:sticky;top:4.2rem;align-self:start;max-height:calc(100vh - 5rem);overflow:auto;background:var(--paper-2);border:1px solid var(--rule);border-radius:6px;padding:1rem;font-size:.92rem;display:grid;gap:.5rem}
aside.panel h3{margin:0;font:600 1.05rem var(--serif)}aside.panel .sum{font-size:.95rem}aside.panel .q{color:var(--ink-2);font-style:italic}aside.panel .m{color:var(--ink-3);font-size:.82rem}
aside.panel ul{margin:0;padding-left:1.1rem}aside.panel img{max-width:100%;border:1px solid var(--rule);background:#fff}
.verify{display:flex;flex-wrap:wrap;gap:.3rem}.verify span{font-size:.72rem;padding:.05rem .4rem;border-radius:2px;background:var(--paper);border:1px solid var(--rule)}.verify .ok{color:var(--F)}.verify .bad{color:var(--A);border-color:var(--A)}
.rel{font-family:var(--mono);font-size:.75rem;color:var(--link)}
/* tree: rows */
#tree{max-width:80ch;margin-inline:auto}.qb{margin:1.6rem 0}.qb>h2{font:600 1.15rem var(--serif);margin:0 0 .2rem;display:flex;gap:.6rem;align-items:baseline}.qb>.s{color:var(--ink-2);margin:0 0 .6rem}
.row{display:grid;grid-template-columns:auto 1fr;gap:.6rem;align-items:baseline;padding:.3rem 0;border-top:1px solid var(--rule)}.row:hover{background:var(--paper-2)}
.row .t{cursor:pointer}.row .w{font:600 .68rem var(--sans);letter-spacing:.05em;text-transform:uppercase;color:var(--ink-3);margin-right:.4rem}
.row.lvl1{margin-left:0}.row.lvl2{margin-left:1.6rem}.row.lvl3{margin-left:3.2rem;font-size:.92rem}.row.lvl3 .t{color:var(--ink-2)}
details.ev{margin-left:3.2rem}details.ev>summary{cursor:pointer;font-size:.82rem;color:var(--ink-3);padding:.15rem 0}details.ev .row{margin-left:0;font-size:.9rem}
.note{font-size:.82rem;color:var(--ink-3);margin-left:3.2rem;padding:.2rem 0}
/* checks, compare, json */
#checks{max-width:90ch;margin-inline:auto}#checks table{width:100%;border-collapse:collapse;font-size:.9rem}#checks td,#checks th{text-align:left;vertical-align:top;padding:.3rem .5rem;border-top:1px solid var(--rule)}
#compare.on{display:block;max-width:1200px;margin:0 auto;padding:1rem 0}#compare table{width:100%;border-collapse:collapse;font-size:.9rem;margin:.4rem 0 1.4rem}#compare th,#compare td{vertical-align:top;text-align:left;padding:.35rem .5rem;border-top:1px solid var(--rule);width:33%}#compare th{font-weight:600;color:var(--ink-2)}#compare td>div{margin:.25rem 0}#compare .s{color:var(--ink-3);font-size:.8rem}#compare h2{font-size:1rem;margin:1.2rem 0 .2rem}
#json pre{font:.78rem var(--mono);white-space:pre-wrap;word-break:break-word}
</style></head><body>
<header class="top"><h1>__TITLE__</h1>
<div class="legend"><span><span class="id Q">Q</span> question</span><span><span class="id H">H</span> hypothesis</span><span><span class="id F">F</span> finding</span><span><span class="id A">A</span> alternative</span><span><span class="id E">E</span> evidence</span><span><span class="id K">K</span> check</span><span><span class="id R">R</span> request</span></div>
<div class="tabs" role="tablist"><button role="tab" data-tab="article" aria-selected="true">Article</button><button role="tab" data-tab="tree">Claims tree</button><button role="tab" data-tab="checks">Verification</button><button role="tab" data-tab="compare" id="cmptab" hidden>Compared</button><button role="tab" data-tab="json">JSON</button></div></header>
<main id="article" class="on"><div class="text" id="text"></div><aside class="panel" id="panel"><h3>Select a marker</h3><p class="q">Click an underlined passage, an id chip or a row to see the full text, the quote in the paper, its figure and what it supports or opposes.</p></aside></main>
<main id="tree"></main><main id="checks"></main><main id="compare"></main><main id="json"><pre id="jsonpre"></pre></main>
<script id="data" type="application/json">__PAYLOAD__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);const G=D.graph,T=D.text,V=D.verification,C=D.compare;
const N=Object.fromEntries(G.nodes.map(n=>[n.id,n]));const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const WORD={Q:'question',H:'hypothesis',F:'finding',A:'alternative',E:'evidence',K:'check',R:'request',S:'study',P:'protocol',D:'source'};
const pre=n=>n.subtype==='Hypothesis'?'H':n.subtype==='Alternative'?'A':n.subtype==='Check'?'K':n.type==='Claim'?'F':n.type==='Evidence'?'E':n.type==='Question'?'Q':n.type==='Request'?'R':n.type==='Study'?'S':n.type==='Protocol'?'P':'D';
const chip=n=>`<span class="id ${pre(n)}" data-go="${n.id}">${n.id}</span>`;
const outs={},ins={};for(const e of G.edges){(outs[e.subject]??=[]).push(e);(ins[e.object]??=[]).push(e)}
const TN=C?Object.fromEntries(C.graph.nodes.map(n=>[n.id,n])):{};const O2T=C?C.align.ours_to_theirs:null;
const prov=n=>!C?'':O2T[n.id]?`<span class="prov" title="${esc(O2T[n.id].map(t=>TN[t].text).join('\n'))}">= ${O2T[n.id].join(', ')} in ${esc(C.label)}</span>`:n.type==='Evidence'?'':`<span class="prov new">new</span>`;
const studyOf=n=>n.study?N[n.study]?.text.split(':')[0]||n.study:'';
// tabs
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tabs button').forEach(x=>x.setAttribute('aria-selected',x===b));document.querySelectorAll('main').forEach(m=>m.classList.toggle('on',m.id===b.dataset.tab))});
// ── article: mark anchors; margin shows chip + summary ──────────────────────────────────
const anchored=G.nodes.filter(n=>n.anchor&&T.includes(n.anchor)&&n.type!=='SourceDocument').sort((a,b)=>b.anchor.length-a.anchor.length);
let segs=[{t:T}];
for(const n of anchored){const out=[];for(const s of segs){if(s.n){out.push(s);continue}let i=s.t.indexOf(n.anchor);if(i<0){out.push(s);continue}out.push({t:s.t.slice(0,i)});out.push({t:n.anchor,n});out.push({t:s.t.slice(i+n.anchor.length)})}segs=out.filter(s=>s.t.length)}
const html=[];let para=[];const flush=()=>{if(!para.length)return;const h=para.join('');const ids=[...new Set([...h.matchAll(/data-id="([^"]+)"/g)].map(m=>m[1]))];
 const body=h.startsWith('## ')?`<h2>${h.slice(3)}</h2>`:h.startsWith('[Figure')||h.startsWith('[Table')?`<p class="fig">${h}</p>`:`<p>${h}</p>`;
 html.push(body);if(ids.length)html.push(`<div class="margin">${ids.map(id=>`<div data-go="${id}">${chip(N[id])}<span>${esc(N[id].description||N[id].text)}</span></div>`).join('')}</div>`);para=[]};
for(const s of segs){const parts=s.t.split('\n\n');parts.forEach((p,i)=>{if(i>0){flush()}const t=p.replace(/\n/g,' ');if(!t)return;para.push(s.n?`<mark class="anc" data-id="${s.n.id}">${esc(t)}</mark><span class="id ${pre(s.n)}" data-id="${s.n.id}">${s.n.id}</span>`:esc(t))})}
flush();document.getElementById('text').innerHTML=html.join('');
function verifyBadges(id){const v=V.nodes?.[id]||{};return `<div class="verify">${Object.entries(v).map(([c,r])=>`<span class="${r.ok?'ok':'bad'}" title="${esc(r.note)}">${c} ${r.ok?'✓':'✗'}</span>`).join('')}</div>`}
function show(id){const n=N[id];if(!n)return;document.querySelectorAll('mark.anc.on').forEach(m=>m.classList.remove('on'));document.querySelectorAll(`mark[data-id="${id}"]`).forEach(m=>m.classList.add('on'));
 const rel=(list,dir)=>(list||[]).filter(e=>['supports','opposes','addresses','observationStatement','request_target','grounds'].includes(e.relation)).map(e=>{const o=N[dir==='out'?e.object:e.subject];return `<li><span class="rel">${e.relation}</span> ${dir==='in'?'← ':'→ '}${chip(o)} ${esc(o.description||o.text)}</li>`}).join('');
 const fig=n.figure?`<a href="${esc(n.figure.page)}" target="_blank">open ${esc(n.panel)} on eLife ↗</a><img src="${esc(n.figure.thumbnail)}" alt="${esc(n.panel)}">`:'';
 document.getElementById('panel').innerHTML=`<div>${chip(n)} <span class="m">${WORD[pre(n)]}${n.panel?` · ${esc(n.panel)}`:''}${n.study?` · ${esc(studyOf(n))}`:''}${prov(n)}</span></div><h3>${esc(n.text)}</h3>${n.description&&n.description!==n.text?`<p class="sum">${esc(n.description)}</p>`:''}${n.notes?`<p class="q">${esc(n.notes)}</p>`:''}
 <p class="q">“${esc(n.anchor)}”</p>${fig}${verifyBadges(id)}<ul>${rel(outs[id],'out')}${rel(ins[id],'in')}</ul>`;
 document.querySelector(`mark[data-id="${id}"]`)?.scrollIntoView({block:'center',behavior:'smooth'})}
document.body.addEventListener('click',e=>{const el=e.target.closest('[data-id],[data-go]');if(!el)return;e.preventDefault();const id=el.dataset.id||el.dataset.go;if(!N[id])return;document.querySelector('[data-tab="article"]').click();show(id)});
// ── tree: one row per node — chip, then summary (claims) or text (evidence) ─────────────
const line=n=>n.type==='Evidence'||!n.description?n.text:n.description;
const row=(n,lvl,extra='')=>`<div class="row lvl${lvl}">${chip(n)}<div class="t" data-go="${n.id}">${extra}${esc(line(n))}${prov(n)}</div></div>`;
const evidenceFor=c=>(ins[c.id]||[]).filter(e=>N[e.subject]?.type==='Evidence').map(e=>({e:N[e.subject],rel:e.relation}));
const evBlock=c=>{const ev=evidenceFor(c);if(!ev.length)return'';const sup=ev.filter(x=>x.rel==='supports'&&x.e.subtype!=='Check'),opp=ev.filter(x=>x.rel==='opposes'),chk=ev.filter(x=>x.e.subtype==='Check');
 const label=[sup.length?`${sup.length} supporting`:'',opp.length?`${opp.length} opposing`:'',chk.length?`${chk.length} check${chk.length>1?'s':''}`:''].filter(Boolean).join(', ');
 return `<details class="ev"><summary>${label}</summary>${[...sup,...opp,...chk].map(({e,rel})=>row(e,3,rel==='opposes'?'<span class="w">opposes</span>':'')).join('')}</details>`};
let tree='';for(const q of G.nodes.filter(n=>n.type==='Question')){
 const addr=(ins[q.id]||[]).filter(e=>e.relation==='addresses').map(e=>N[e.subject]);
 const hyps=addr.filter(n=>n.subtype==='Hypothesis'),alts=addr.filter(n=>n.subtype==='Alternative'),plain=addr.filter(n=>!n.subtype);
 tree+=`<section class="qb"><h2>${chip(q)}<span data-go="${q.id}" style="cursor:pointer">${esc(q.text)}</span></h2><p class="s">${esc(q.description||'')}</p>`;
 for(const h of hyps){tree+=row(h,1,'<span class="w">hypothesis</span>');for(const f of (ins[h.id]||[]).filter(e=>e.relation==='supports'&&N[e.subject].type==='Claim').map(e=>N[e.subject]))tree+=row(f,2)+evBlock(f)}
 if(plain.length){tree+=`<div class="row lvl1"><span></span><div class="t"><span class="w">other findings</span></div></div>`;for(const c of plain){tree+=row(c,2)+evBlock(c);for(const d of (ins[c.id]||[]).filter(e=>e.relation==='supports'&&N[e.subject].type==='Claim').map(e=>N[e.subject]))tree+=row(d,3,'<span class="w">from</span>')}}
 for(const a of alts){tree+=row(a,1,'<span class="w">alternative</span>');const op=evidenceFor(a).filter(x=>x.rel==='opposes'),sp=evidenceFor(a).filter(x=>x.rel==='supports');
  tree+=op.length?`<details class="ev"><summary>ruled out by ${op.length} result${op.length>1?'s':''}${sp.length?`, ${sp.length} for it`:''}</summary>${op.map(({e})=>row(e,3)).join('')}${sp.map(({e})=>row(e,3,'<span class="w">supports</span>')).join('')}</details>`:`<div class="note">left open: nothing in the paper opposes it</div>`}
 tree+='</section>'}
const reqs=G.nodes.filter(n=>n.type==='Request');if(reqs.length)tree+=`<section class="qb"><h2>What the authors call for next</h2>${reqs.map(r=>row(r,1,'',)+`<div class="note">about ${(outs[r.id]||[]).map(e=>chip(N[e.object])).join(' ')}</div>`).join('')}</section>`;
const rest=G.nodes.filter(n=>['Study','Protocol','SourceDocument'].includes(n.type));tree+=`<section class="qb"><h2>Studies, methods, sources</h2>${rest.map(n=>row(n,1,`<span class="w">${WORD[pre(n)]}</span>`)).join('')}</section>`;
document.getElementById('tree').innerHTML=tree;
// ── checks ──────────────────────────────────────────────────────────────────────────────
const S=V.summary||{};const rows=Object.entries(V.nodes||{}).map(([id,v])=>{const bad=Object.entries(v).filter(([,r])=>!r.ok);return bad.length?`<tr><td>${chip(N[id])}</td><td>${esc(N[id]?.text||'')}</td><td>${bad.map(([c,r])=>`<span class="verify"><span class="bad">${c}: ${esc(r.note)}</span></span>`).join(' ')}</td></tr>`:''}).join('');
const badEdges=(V.edges||[]).filter(e=>!e.ok);
document.getElementById('checks').innerHTML=`<p><b>${S.passed??'?'} of ${S.nodes??'?'} nodes pass every check</b> · ${S.edges??'?'} edges${badEdges.length?`, <span style="color:var(--A)">${badEdges.length} illegal</span>`:', all legal'} · anchors checked against ${(S.text_chars||0).toLocaleString()} characters of the article as eLife Pathways serves it.</p>
<p class="s">Checks: <b>shape</b> (id, type, text) · <b>summary</b> (questions, claims and requests: one or two plain sentences) · <b>anchor</b> (verbatim in the text) · <b>evidence</b> (grounded in a study or a cited source, names its panel) · <b>figure</b> (a figure panel links to its figure) · <b>structure</b> (every claim reaches a question; every piece of evidence argues something).</p>
${rows?`<table><thead><tr><th>node</th><th>text</th><th>failing</th></tr></thead><tbody>${rows}</tbody></table>`:'<p>No node fails a check.</p>'}`;
document.getElementById('jsonpre').textContent=JSON.stringify(G,null,1);
// ── compare ─────────────────────────────────────────────────────────────────────────────
if(C){document.getElementById('cmptab').hidden=false;document.getElementById('cmptab').textContent=`Compared with ${C.label}`;
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
