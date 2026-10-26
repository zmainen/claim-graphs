#!/usr/bin/env python3
"""mira_viewer — one self-contained HTML page that shows a MIRA working graph the way eLife
Pathways' design prototype does: the article text with claim markers at their anchors and the
summary beside the passage; a coloured claims tree (question → hypothesis → findings → evidence,
alternatives with what opposes them, checks marked); and the verification marks.

The JSON, the article text and the verification verdicts are embedded, so the file is the
deliverable's review surface and can be opened anywhere. Nothing is typed into it by hand.

Usage: mira_viewer.py <graph.json> <anchor-text.txt> [--out viewer.html]
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
    payload = json.dumps({"graph": g, "text": text, "verification": v}, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("__TITLE__", title.replace("<", "&lt;")).replace("__PAYLOAD__", payload)
    open(out, "w", encoding="utf-8").write(html)
    print(f"wrote {out} ({len(html) // 1024} KB)")

TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="claude:viewport-fit-sides" content="cover"><title>Gädeke claims viewer</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=Source+Sans+3:wght@400;600&family=JetBrains+Mono:wght@400&display=swap">
<style>
/* Layout: a two-column reading view (article | side panel) under a tab bar; tree and checks are single columns. Palette: paper white, eLife-like blue, and one colour per claim kind. */
:root{color-scheme:light;--paper:#fff;--paper-2:#f4f4f2;--ink:#212121;--ink-2:#555;--ink-3:#888;--rule:#dcdcd8;--link:#0a4f8a;
 --hyp:#1f4e9c;--find:#2b6b3f;--alt:#b03a2e;--chk:#b8740f;--ev:#4a7a5a;--q:#6b3f9c;--req:#7a5c2e;
 --serif:"Source Serif 4",Georgia,serif;--sans:"Source Sans 3","Helvetica Neue",Arial,sans-serif;--mono:"JetBrains Mono",ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--paper:#17181b;--paper-2:#202228;--ink:#e8e6e1;--ink-2:#b5b2aa;--ink-3:#85827b;--rule:#32353c;--link:#8fb8ea;
 --hyp:#8fb0ea;--find:#86c79a;--alt:#e38b80;--chk:#e0aa55;--ev:#86c79a;--q:#c7a3e6;--req:#d6b27c}}
:root[data-theme="dark"]{color-scheme:dark;--paper:#17181b;--paper-2:#202228;--ink:#e8e6e1;--ink-2:#b5b2aa;--ink-3:#85827b;--rule:#32353c;--link:#8fb8ea;
 --hyp:#8fb0ea;--find:#86c79a;--alt:#e38b80;--chk:#e0aa55;--ev:#86c79a;--q:#c7a3e6;--req:#d6b27c}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--paper);color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.5;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
a{color:var(--link)} button{font:inherit;cursor:pointer}
header.top{display:flex;flex-wrap:wrap;gap:.4rem 1.2rem;align-items:baseline;padding:.8rem 0 .4rem;border-bottom:1px solid var(--rule);position:sticky;top:env(safe-area-inset-top,0px);background:var(--paper);z-index:3}
header.top h1{font:600 1.05rem var(--sans);margin:0}
.tabs{display:flex;gap:.2rem;margin-left:auto}.tabs button{background:none;border:1px solid var(--rule);border-radius:4px;padding:.3rem .7rem;color:var(--ink-2)}.tabs button[aria-selected="true"]{background:var(--paper-2);color:var(--ink);border-color:var(--ink-3)}
.legend{display:flex;flex-wrap:wrap;gap:.3rem .9rem;font-size:.82rem;color:var(--ink-2)}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:.3rem;vertical-align:-1px}
main{padding-block:1rem 4rem}main:not(.on){display:none !important}main.on{display:block}
/* article */
#article.on{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:2rem}@media (max-width:900px){#article.on{grid-template-columns:1fr}}
.text{font-family:var(--serif);font-size:1.06rem;line-height:1.65;max-width:70ch}.text h2{font:600 1.25rem var(--sans);margin:1.8rem 0 .5rem}.text p{margin:0 0 .9rem}
.text .fig{font-size:.92rem;color:var(--ink-2);border-left:3px solid var(--rule);padding-left:.8rem;margin:1rem 0}
mark.anc{background:none;border-bottom:2px solid;cursor:pointer;padding-bottom:1px}mark.anc:hover,mark.anc.on{background:var(--paper-2)}
.tag{display:inline-block;font:600 .66rem var(--sans);letter-spacing:.05em;text-transform:uppercase;padding:.05rem .35rem;border-radius:2px;color:#fff;margin-left:.25rem;vertical-align:middle;cursor:pointer}
.k-Hypothesis{background:var(--hyp)}.k-Finding{background:var(--find)}.k-Alternative{background:var(--alt)}.k-Check{background:var(--chk)}.k-Evidence{background:var(--ev)}.k-Question{background:var(--q)}.k-Request{background:var(--req)}.k-Other{background:var(--ink-3)}
mark.anc{border-color:var(--ink-3)}mark.anc.k-Hypothesis{border-color:var(--hyp)}mark.anc.k-Finding{border-color:var(--find)}mark.anc.k-Alternative{border-color:var(--alt)}mark.anc.k-Check{border-color:var(--chk)}mark.anc.k-Evidence{border-color:var(--ev)}mark.anc.k-Question{border-color:var(--q)}mark.anc.k-Request{border-color:var(--req)}
.margin{font-size:.85rem;color:var(--ink-2);border-left:2px solid var(--rule);padding-left:.7rem;margin:.2rem 0 1rem}.margin div{margin:.2rem 0;cursor:pointer}.margin div:hover{color:var(--ink)}
aside.panel{position:sticky;top:4.2rem;align-self:start;max-height:calc(100vh - 5rem);overflow:auto;background:var(--paper-2);border:1px solid var(--rule);border-radius:6px;padding:1rem;font-size:.92rem;display:grid;gap:.5rem}
aside.panel h3{margin:0;font:600 1.05rem var(--sans)}aside.panel .sum{font-family:var(--serif);font-size:1rem}aside.panel .q{color:var(--ink-2);font-style:italic}
aside.panel ul{margin:0;padding-left:1.1rem}aside.panel img{max-width:100%;border:1px solid var(--rule);background:#fff}
.verify{display:flex;flex-wrap:wrap;gap:.3rem}.verify span{font-size:.72rem;padding:.05rem .4rem;border-radius:2px;background:var(--paper);border:1px solid var(--rule)}.verify .ok{color:var(--find)}.verify .bad{color:var(--alt);border-color:var(--alt)}
.rel{font-family:var(--mono);font-size:.75rem;color:var(--link)}
/* tree */
#tree{max-width:78ch;margin-inline:auto}.qb{border:1px solid var(--rule);border-radius:6px;padding:1rem;margin:1rem 0}.qb>h2{font:600 1.2rem var(--serif);margin:0 0 .6rem}
.node{padding:.45rem .6rem;border-left:4px solid var(--ink-3);margin:.4rem 0;background:var(--paper)}.node.Hypothesis{border-color:var(--hyp)}.node.Finding{border-color:var(--find)}.node.Alternative{border-color:var(--alt)}.node.Check{border-color:var(--chk)}.node.Evidence{border-color:var(--ev)}.node.Request{border-color:var(--req)}
.node .t{font-family:var(--serif);font-size:1rem}.node .s{color:var(--ink-2);font-size:.9rem}.node .m{font-size:.8rem;color:var(--ink-3)}.node .m a{margin-left:.4rem}
.kids{margin-left:1.2rem}details.ev>summary{cursor:pointer;font-size:.85rem;color:var(--ink-2);padding:.2rem 0}
.thumb{width:150px;border:1px solid var(--rule);background:#fff;display:block;margin:.3rem 0}
/* checks */
#checks{max-width:78ch;margin-inline:auto}table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{text-align:left;padding:.35rem .5rem;border-bottom:1px solid var(--rule);vertical-align:top}th{font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;color:var(--ink-2)}
pre{font-size:.78rem;white-space:pre-wrap;word-break:break-word}
</style></head><body>
<header class="top"><h1>__TITLE__</h1>
<div class="legend"><span><i style="background:var(--q)"></i>question</span><span><i style="background:var(--hyp)"></i>hypothesis</span><span><i style="background:var(--find)"></i>finding</span><span><i style="background:var(--alt)"></i>alternative</span><span><i style="background:var(--ev)"></i>evidence</span><span><i style="background:var(--chk)"></i>check</span><span><i style="background:var(--req)"></i>request</span></div>
<div class="tabs" role="tablist"><button role="tab" data-tab="article" aria-selected="true">Article</button><button role="tab" data-tab="tree">Claims tree</button><button role="tab" data-tab="checks">Verification</button><button role="tab" data-tab="json">JSON</button></div></header>
<main id="article" class="on"><div class="text" id="text"></div><aside class="panel" id="panel"><h3>Select a marker</h3><p class="q">Click an underlined passage or a tag to see the claim, its summary, where it comes from and what it supports or opposes.</p></aside></main>
<main id="tree"></main><main id="checks"></main><main id="json"><pre id="jsonpre"></pre></main>
<script id="data" type="application/json">__PAYLOAD__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);const G=D.graph,T=D.text,V=D.verification;
const N=Object.fromEntries(G.nodes.map(n=>[n.id,n]));const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const kind=n=>n.subtype==='Hypothesis'?'Hypothesis':n.subtype==='Alternative'?'Alternative':n.subtype==='Check'?'Check':n.type==='Claim'?'Finding':n.type==='Evidence'?'Evidence':n.type==='Question'?'Question':n.type==='Request'?'Request':'Other';
const outs={},ins={};for(const e of G.edges){(outs[e.subject]??=[]).push(e);(ins[e.object]??=[]).push(e)}
// tabs
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tabs button').forEach(x=>x.setAttribute('aria-selected',x===b));document.querySelectorAll('main').forEach(m=>m.classList.toggle('on',m.id===b.dataset.tab))});
// ── article: mark anchors ───────────────────────────────────────────────────────────────
const anchored=G.nodes.filter(n=>n.anchor&&T.includes(n.anchor)&&n.type!=='SourceDocument').sort((a,b)=>b.anchor.length-a.anchor.length);
let segs=[{t:T}];// split text into plain/anchor segments, longest anchors first so nesting is avoided
for(const n of anchored){const out=[];for(const s of segs){if(s.n){out.push(s);continue}let i=s.t.indexOf(n.anchor);if(i<0){out.push(s);continue}out.push({t:s.t.slice(0,i)});out.push({t:n.anchor,n});out.push({t:s.t.slice(i+n.anchor.length)})}segs=out.filter(s=>s.t.length)}
const html=[];let para=[];const flush=()=>{if(!para.length)return;const h=para.join('');const ids=[...new Set([...h.matchAll(/data-id="([^"]+)"/g)].map(m=>m[1]))];
 const body=h.startsWith('## ')?`<h2>${h.slice(3)}</h2>`:h.startsWith('[Figure')||h.startsWith('[Table')?`<p class="fig">${h}</p>`:`<p>${h}</p>`;
 html.push(body);if(ids.length)html.push(`<div class="margin">${ids.map(id=>`<div data-go="${id}"><span class="tag k-${kind(N[id])}">${kind(N[id])}</span> ${esc(N[id].description||N[id].text)}</div>`).join('')}</div>`);para=[]};
for(const s of segs){const parts=s.t.split('\n\n');parts.forEach((p,i)=>{if(i>0){flush()}const t=p.replace(/\n/g,' ');if(!t)return;para.push(s.n?`<mark class="anc k-${kind(s.n)}" data-id="${s.n.id}">${esc(t)}</mark><span class="tag k-${kind(s.n)}" data-id="${s.n.id}">${s.n.id}</span>`:esc(t))})}
flush();document.getElementById('text').innerHTML=html.join('');
function verifyBadges(id){const v=V.nodes?.[id]||{};return `<div class="verify">${Object.entries(v).map(([c,r])=>`<span class="${r.ok?'ok':'bad'}" title="${esc(r.note)}">${c} ${r.ok?'✓':'✗'}</span>`).join('')}</div>`}
function show(id){const n=N[id];if(!n)return;document.querySelectorAll('mark.anc.on').forEach(m=>m.classList.remove('on'));document.querySelectorAll(`mark[data-id="${id}"]`).forEach(m=>m.classList.add('on'));
 const rel=(list,dir)=>(list||[]).filter(e=>['supports','opposes','addresses','observationStatement','request_target'].includes(e.relation)).map(e=>{const o=N[dir==='out'?e.object:e.subject];return `<li><span class="rel">${e.relation}</span> ${dir==='in'?'← ':'→ '}<a href="#" data-go="${o.id}">${esc(o.text)}</a></li>`}).join('');
 const fig=n.figure?`<a href="${esc(n.figure.page)}" target="_blank">open ${esc(n.panel)} on eLife ↗</a><img src="${esc(n.figure.thumbnail)}" alt="${esc(n.panel)}">`:(n.panel?`<span class="m">${esc(n.panel)}</span>`:'');
 document.getElementById('panel').innerHTML=`<div><span class="tag k-${kind(n)}">${kind(n)}</span> <code>${n.id}</code>${n.study?` · ${esc(n.study.replace('st','Study '))}`:''}</div><h3>${esc(n.text)}</h3><p class="sum">${esc(n.description||'')}</p>${n.notes?`<p class="q">${esc(n.notes)}</p>`:''}
 <p class="q">“${esc(n.anchor)}”</p>${fig}${verifyBadges(id)}<ul>${rel(outs[id],'out')}${rel(ins[id],'in')}</ul>`;
 document.querySelector(`mark[data-id="${id}"]`)?.scrollIntoView({block:'center',behavior:'smooth'})}
document.body.addEventListener('click',e=>{const el=e.target.closest('[data-id],[data-go]');if(!el)return;e.preventDefault();const id=el.dataset.id||el.dataset.go;document.querySelector('[data-tab="article"]').click();show(id)});
// ── tree ────────────────────────────────────────────────────────────────────────────────
const node=(n,extra='')=>`<div class="node ${kind(n)}" id="t-${n.id}"><div class="t">${esc(n.text)}</div><div class="s">${esc(n.description||'')}</div><div class="m"><code>${n.id}</code>${n.panel?` · ${esc(n.panel)}`:''}${n.study?` · ${esc(n.study.replace('st','Study '))}`:''}${n.figure?` <a href="${esc(n.figure.page)}" target="_blank">figure ↗</a>`:''}${n.anchor?` <a href="#" data-go="${n.id}">in text</a>`:''}</div>${n.figure?`<img class="thumb" src="${esc(n.figure.thumbnail)}" alt="">`:''}${extra}</div>`;
const evidenceFor=c=>(ins[c.id]||[]).filter(e=>e.relation!=='addresses'&&N[e.subject]?.type==='Evidence').map(e=>({e:N[e.subject],rel:e.relation}));
const evBlock=c=>{const ev=evidenceFor(c);return ev.length?`<details class="ev"><summary>${ev.length} piece${ev.length>1?'s':''} of evidence</summary><div class="kids">${ev.map(({e,rel})=>node(e,`<div class="m"><span class="rel">${rel}</span></div>`)).join('')}</div></details>`:''};
let tree='';for(const q of G.nodes.filter(n=>n.type==='Question')){
 const addr=(ins[q.id]||[]).filter(e=>e.relation==='addresses').map(e=>N[e.subject]);
 const hyps=addr.filter(n=>n.subtype==='Hypothesis'),alts=addr.filter(n=>n.subtype==='Alternative'),plain=addr.filter(n=>!n.subtype);
 tree+=`<section class="qb"><h2>${esc(q.text)}</h2><p class="s">${esc(q.description||'')}</p>`;
 for(const h of hyps){const finds=(ins[h.id]||[]).filter(e=>e.relation==='supports'&&N[e.subject].type==='Claim').map(e=>N[e.subject]);
  tree+=node(h,`<div class="kids">${finds.map(f=>node(f,evBlock(f))).join('')}</div>`)}
 for(const c of plain)tree+=node(c,evBlock(c));
 for(const a of alts){const op=(ins[a.id]||[]).filter(e=>e.relation==='opposes').map(e=>N[e.subject]);const sup=(ins[a.id]||[]).filter(e=>e.relation==='supports').map(e=>N[e.subject]);
  tree+=node(a,`<div class="kids">${op.length?op.map(o=>node(o,`<div class="m"><span class="rel">opposes</span> this alternative</div>`)).join(''):'<div class="m">left open: nothing in the paper opposes it</div>'}${sup.map(o=>node(o,`<div class="m"><span class="rel">supports</span> this alternative</div>`)).join('')}</div>`)}
 tree+='</section>'}
const orphans=G.nodes.filter(n=>n.type==='Claim'&&!(ins[n.id]||[]).some(e=>e.relation==='supports'&&N[e.subject].type==='Claim')&&!(outs[n.id]||[]).some(e=>e.relation==='addresses')&&!(outs[n.id]||[]).some(e=>e.relation==='supports'&&N[e.object].subtype==='Hypothesis'));
if(orphans.length)tree+=`<section class="qb"><h2>Findings not under a hypothesis</h2>${orphans.map(c=>node(c,evBlock(c))).join('')}</section>`;
const reqs=G.nodes.filter(n=>n.type==='Request');if(reqs.length)tree+=`<section class="qb"><h2>What the authors call for next</h2>${reqs.map(r=>node(r,`<div class="m">${(outs[r.id]||[]).map(e=>`<a href="#" data-go="${e.object}">${esc(N[e.object].text)}</a>`).join(' · ')}</div>`)).join('')}</section>`;
const rest=G.nodes.filter(n=>['Study','Protocol','SourceDocument'].includes(n.type));tree+=`<section class="qb"><h2>Studies, methods, sources</h2>${rest.map(n=>node(n)).join('')}</section>`;
document.getElementById('tree').innerHTML=tree;
// ── checks ──────────────────────────────────────────────────────────────────────────────
const S=V.summary||{};const rows=Object.entries(V.nodes||{}).map(([id,v])=>{const bad=Object.entries(v).filter(([,r])=>!r.ok);return bad.length?`<tr><td><a href="#" data-go="${id}"><code>${id}</code></a></td><td>${esc(N[id]?.text||'')}</td><td>${bad.map(([c,r])=>`<span class="verify"><span class="bad">${c}: ${esc(r.note)}</span></span>`).join(' ')}</td></tr>`:''}).join('');
const badEdges=(V.edges||[]).filter(e=>!e.ok);
document.getElementById('checks').innerHTML=`<p><b>${S.passed??'?'} of ${S.nodes??'?'} nodes pass every check</b> · ${S.edges??'?'} edges${badEdges.length?`, <span style="color:var(--alt)">${badEdges.length} illegal</span>`:', all legal'} · anchors checked against ${(S.text_chars||0).toLocaleString()} characters of the article as eLife Pathways serves it.</p>
<p class="s">Checks: <b>shape</b> (id, type, text) · <b>summary</b> (questions, claims and requests: one or two plain sentences) · <b>anchor</b> (verbatim in the text) · <b>evidence</b> (grounded in a study, names its panel) · <b>figure</b> (a figure panel links to its figure) · <b>structure</b> (every claim reaches a question; every piece of evidence argues something).</p>
${rows?`<table><thead><tr><th>node</th><th>text</th><th>failing</th></tr></thead><tbody>${rows}</tbody></table>`:'<p>No node fails a check.</p>'}`;
document.getElementById('jsonpre').textContent=JSON.stringify(G,null,1);
</script></body></html>'''

if __name__ == "__main__":
    main()
