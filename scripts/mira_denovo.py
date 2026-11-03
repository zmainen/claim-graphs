#!/usr/bin/env python3
"""mira_denovo — the staged MIRA extraction, de novo, per docs/design/2026-11-01-mira-denovo-stages.md.

Eight stages. Each stage renders a prompt from extract/prompts/mira/stage-N-*.md, calls the model
(stage 8 is code), checks the reply, and writes to runs/<paper>/mira-denovo/:
  stageN.json          accepted items            stageN.rejected.json   refused items with reasons
  calls/stageN[-k].prompt.txt / .raw.txt / .meta.json   every call, for the harness page
Anchors must be verbatim in text.txt; anything else is refused, not repaired.

Usage:
  mira_denovo.py run <paper> [--msid 105391 | --text file.txt] [--from N] [--to N] [--model M] [--dry-run] [--reference graph.json]
  mira_denovo.py stage <paper> N                      # one stage, inputs from the files on disk
--dry-run renders every prompt it can from the inputs on disk and makes no call.
Model default: anthropic/claude-sonnet-4.5 (OpenRouter id); the key comes from the Keychain.
"""
import json, os, re, subprocess, sys, time
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.environ.get("CLAIM_GRAPHS_ROOT") or os.getcwd()   # the corpus, where runs/ lives
sys.path.insert(0, HERE)
from mira_baseline import stream, key as _key   # noqa: E402  (OpenRouter client, Keychain key)

CG = os.path.dirname(HERE)   # claim-graphs, where the prompts live
PROMPTS = os.path.join(CG, "extract", "prompts", "mira")
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"
STAGES = ["inventory", "evidence", "findings", "hypotheses", "alternatives", "checks-cited-requests", "questions-summaries", "assemble"]
PANEL_RE = re.compile(r"\b(Figure \d+[A-Z]?|Table \d+|Supplementary Figure \d+[A-Z]?|Supplementary Table \d+)\b")

# ── files ──────────────────────────────────────────────────────────────────────────────────────

def paths(paper):
    d = os.path.join(ROOT, "runs", paper, "mira-denovo"); os.makedirs(os.path.join(d, "calls"), exist_ok=True); return d

def jload(p, default=None):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default

def jdump(o, p):
    json.dump(o, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

def prompt_file(n):
    return os.path.join(PROMPTS, f"stage-{n}-{STAGES[n-1]}.md")

def render(n, vars):
    src = open(prompt_file(n), encoding="utf-8").read()
    system, user = src.split("## User", 1); system = system.split("## System", 1)[1].strip(); user = user.strip()
    for k, v in vars.items():
        v = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=1)
        user = user.replace("{{" + k + "}}", v)
    missing = re.findall(r"\{\{(\w+)\}\}", user)
    return system, user, missing

def parse_json(t):
    t = t.strip(); m = re.match(r"^```[^\n]*\n([\s\S]*?)\n```$", t)
    if m: t = m.group(1).strip()
    for s in (t, t[t.find("{"): t.rfind("}") + 1]):
        try: return json.loads(s)
        except Exception: pass
    return None

# ── calls ──────────────────────────────────────────────────────────────────────────────────────

def call(d, tag, system, user, model, dry):
    base = os.path.join(d, "calls", tag)
    open(base + ".prompt.txt", "w", encoding="utf-8").write("## System\n\n" + system + "\n\n## User\n\n" + user)
    if dry: return None
    body = {"model": model, "temperature": 0.2, "max_tokens": 30000, "stream": True,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    t0 = time.time(); content, reasoning, used, usage, error = stream(body)
    open(base + ".raw.txt", "w", encoding="utf-8").write(content)
    jdump({"model": model, "served_by": used, "usage": usage, "error": error, "seconds": round(time.time() - t0, 1),
           "prompt_chars": len(system) + len(user), "reply_chars": len(content), "reasoning_chars": reasoning,
           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}, base + ".meta.json")
    if error: print(f"  {tag}: error {error}")
    return parse_json(content)

# ── checkers: every stage returns (accepted, rejected) ─────────────────────────────────────────

def verbatim(text, a):
    return bool(a) and a in text

def check_items(items, text, rules):
    """rules: list of (name, predicate(item) -> True|reason). Verbatim anchor is always first."""
    ok, bad = [], []
    for it in items or []:
        why = [] if verbatim(text, it.get("anchor")) else ["anchor not verbatim"]
        for name, pred in rules:
            r = pred(it)
            if r is not True: why.append(f"{name}: {r}")
        (bad if why else ok).append(dict(it, **({"refused": why} if why else {})))
    return ok, bad

# ── stage 1: inventory ─────────────────────────────────────────────────────────────────────────

def panels_in(text):
    seen = OrderedDict()
    for m in PANEL_RE.finditer(text): seen.setdefault(m.group(1), 0); seen[m.group(1)] += 1
    # a figure's letters imply the figure; keep letters, drop the bare figure when letters exist
    letters = {p for p in seen if re.search(r"\d[A-Z]$", p)}
    bare = {re.sub(r"[A-Z]$", "", p) for p in letters}
    return [p for p in seen if not (p in bare and p not in letters)]

def groups_of(panels):
    g = OrderedDict()
    for p in panels: g.setdefault(re.sub(r"[A-Z]$", "", p), []).append(p)
    return g

def stage1(d, text, model, dry):
    system, user, _ = render(1, {"text": text})
    rep = call(d, "stage1", system, user, model, dry) or {}
    studies, bad_s = check_items(rep.get("studies"), text, [("text", lambda i: True if i.get("text") else "no text")])
    skeys = {s["key"] for s in studies}
    protocols, bad_p = check_items(rep.get("protocols"), text, [
        ("followed", lambda i: True if any(k in skeys for k in i.get("followed_by", [])) else "no study follows it")])
    inv = {"panels": panels_in(text), "groups": groups_of(panels_in(text)), "studies": studies, "protocols": protocols}
    if not dry: jdump(inv, os.path.join(d, "stage1.json")); jdump({"studies": bad_s, "protocols": bad_p}, os.path.join(d, "stage1.rejected.json"))
    return inv

# ── stage 2: evidence per panel group ──────────────────────────────────────────────────────────

def passages(text, panels, width=700):
    """Paragraphs mentioning any of the panels, with their neighbours, deduplicated and in order."""
    paras = [p for p in text.split("\n\n")]
    hit = {i for i, p in enumerate(paras) if any(re.search(r"\b" + re.escape(x) + r"\b", p) for x in panels)}
    keep = sorted({j for i in hit for j in (i - 1, i, i + 1) if 0 <= j < len(paras)})
    return "\n\n".join(paras[j] for j in keep)

def stage2(d, text, inv, model, dry):
    acc, rej = [], []
    skeys = {s["key"] for s in inv["studies"]}
    for k, (fig, panels) in enumerate(inv["groups"].items(), 1):
        label = fig if len(panels) == 1 else f"{fig} ({', '.join(p[-1] for p in panels if p[-1].isalpha())})"
        system, user, _ = render(2, {"inventory": {"studies": inv["studies"], "protocols": inv["protocols"]}, "panel": label,
                                     "panel_text": passages(text, panels + [fig])})
        rep = call(d, f"stage2-{k:02d}", system, user, model, dry) or {}
        ok, bad = check_items(rep.get("evidence"), text, [
            ("study", lambda i: True if i.get("study") in skeys else f"unknown study {i.get('study')!r}"),
            ("panel", lambda i: True if i.get("panel") else "no panel"),
            ("text", lambda i: True if i.get("text") else "no text")])
        for it in ok: it["group"] = fig
        acc += ok; rej += bad
    covered = {p for e in acc for p in PANEL_RE.findall(e.get("panel", ""))} | {e.get("panel") for e in acc}
    uncovered = [p for p in inv["panels"] if p not in covered and re.sub(r"[A-Z]$", "", p) not in covered]
    out = {"evidence": acc, "uncovered_panels": uncovered}
    if not dry: jdump(out, os.path.join(d, "stage2.json")); jdump(rej, os.path.join(d, "stage2.rejected.json"))
    if uncovered: print(f"  stage 2: {len(uncovered)} panels uncovered: {uncovered}")
    return out

# ── stages 3–7: one call each ──────────────────────────────────────────────────────────────────

def stage3(d, text, ev, model, dry):
    system, user, _ = render(3, {"evidence": ev["evidence"], "text": text})
    rep = call(d, "stage3", system, user, model, dry) or {}
    ekeys = {e["key"] for e in ev["evidence"]}
    ok, bad = check_items(rep.get("findings"), text, [
        ("supported", lambda i: True if any(k in ekeys for k in i.get("supported_by", [])) else "no known evidence supports it"),
        ("no statistic", lambda i: True if not re.search(r"\bp\s*[<=>]|t\(\d|BF10|β\s*=", i.get("text", "")) else "statistic in text")])
    used = {k for f in ok for k in f.get("supported_by", []) + f.get("opposed_by", [])}
    out = {"findings": ok, "evidence_unused": sorted(ekeys - used)}
    if not dry: jdump(out, os.path.join(d, "stage3.json")); jdump(bad, os.path.join(d, "stage3.rejected.json"))
    return out

def stage4(d, text, fnd, model, dry):
    system, user, _ = render(4, {"findings": fnd["findings"], "text": text})
    rep = call(d, "stage4", system, user, model, dry) or {}
    fkeys = {f["key"] for f in fnd["findings"]}
    ok, bad = check_items(rep.get("hypotheses"), text, [
        ("tested", lambda i: True if any(k in fkeys for k in i.get("supported_by", []) + i.get("opposed_by", [])) else "no finding tests it")])
    out = {"hypotheses": ok}
    if not dry: jdump(out, os.path.join(d, "stage4.json")); jdump(bad, os.path.join(d, "stage4.rejected.json"))
    return out

def stage5(d, text, hyp, fnd, ev, model, dry):
    system, user, _ = render(5, {"hypotheses": hyp["hypotheses"], "findings": fnd["findings"], "evidence": ev["evidence"], "text": text})
    rep = call(d, "stage5", system, user, model, dry) or {}
    ekeys = {e["key"] for e in ev["evidence"]}
    def edges_ok(i):   # the precision guard: every opposes/supports edge carries its own verbatim inference sentence
        for side in ("opposed_by", "supported_by"):
            for e in i.get(side, []):
                if e.get("evidence") not in ekeys: return f"{side}: unknown evidence {e.get('evidence')!r}"
                if not verbatim(text, e.get("anchor")): return f"{side}: edge anchor not verbatim"
        return True
    ok, bad = check_items(rep.get("alternatives"), text, [
        ("positive", lambda i: True if not re.match(r"^(The .* (is|was) not|There is no|No )", i.get("text", "")) else "stated as a negation"),
        ("edges", edges_ok), ("source", lambda i: True if i.get("source") in ("design", "model", "discussion") else "no source")])
    out = {"alternatives": ok}
    if not dry: jdump(out, os.path.join(d, "stage5.json")); jdump(bad, os.path.join(d, "stage5.rejected.json"))
    return out

def references_of(d):
    p = os.path.join(d, "references.txt"); return open(p, encoding="utf-8").read() if os.path.exists(p) else "(no reference list on disk; resolve DOIs from the citations in the text)"

def stage6(d, text, ev, fnd, hyp, alt, model, dry):
    system, user, _ = render(6, {"evidence": ev["evidence"], "findings": fnd["findings"], "hypotheses": hyp["hypotheses"],
                                 "alternatives": alt["alternatives"], "references": references_of(d), "text": text})
    rep = call(d, "stage6", system, user, model, dry) or {}
    ekeys = {e["key"] for e in ev["evidence"]}; ckeys = {f["key"] for f in fnd["findings"]} | {h["key"] for h in hyp["hypotheses"]} | {a["key"] for a in alt["alternatives"]}
    checks = [c for c in rep.get("checks", []) if c.get("evidence") in ekeys]
    cited, bad_c = check_items(rep.get("cited"), text, [
        ("doi", lambda i: True if re.match(r"^10\.\d{4,}/", i.get("doi", "")) else "no DOI"),
        ("bears_on", lambda i: True if i.get("bears_on") in ckeys else f"unknown claim {i.get('bears_on')!r}")])
    requests, bad_r = check_items(rep.get("requests"), text, [
        ("about", lambda i: True if any(k in ckeys for k in i.get("about", [])) else "no known target")])
    out = {"checks": checks, "cited": cited, "requests": requests}
    if not dry: jdump(out, os.path.join(d, "stage6.json")); jdump({"cited": bad_c, "requests": bad_r}, os.path.join(d, "stage6.rejected.json"))
    return out

EDITORIAL = re.compile(r"^(Rival|Check\b|Argued against|Alternative to|Raised by the authors|A limitation|Cited finding|Manipulation check|Positive control|Weak\b)", re.I)

def stage7(d, text, hyp, fnd, alt, ev, req, model, dry):
    system, user, _ = render(7, {"hypotheses": hyp["hypotheses"], "findings": fnd["findings"], "alternatives": alt["alternatives"],
                                 "evidence": ev["evidence"], "requests": req["requests"], "text": text})
    rep = call(d, "stage7", system, user, model, dry) or {}
    questions, bad_q = check_items(rep.get("questions"), text, [
        ("addressed", lambda i: True if any((i.get("addresses") or {}).get(k) for k in ("hypotheses", "alternatives", "findings")) else "nothing addresses it")])
    summaries, bad_s = {}, {}
    for k, s in (rep.get("summaries") or {}).items():
        n = len([x for x in re.split(r"(?<=[.!?])\s+", s.strip()) if x])
        if 1 <= n <= 2 and not EDITORIAL.match(s) and not re.search(r"\d", s): summaries[k] = s
        else: bad_s[k] = {"summary": s, "refused": "sentences" if n > 2 else "editorial" if EDITORIAL.match(s) else "contains a number"}
    out = {"questions": questions, "summaries": summaries}
    if not dry: jdump(out, os.path.join(d, "stage7.json")); jdump({"questions": bad_q, "summaries": bad_s}, os.path.join(d, "stage7.rejected.json"))
    return out

# ── stage 8: assemble ──────────────────────────────────────────────────────────────────────────

def stage8(d, paper, text, s1, s2, s3, s4, s5, s6, s7, reference):
    fj = jload(os.path.join(d, "figures.json"), {}) or {}
    figs = fj.get("figures", fj) if isinstance(fj, dict) else fj
    figmap = {f["label"]: f for f in figs if f.get("label")}
    def figure_for(panel):
        m = re.match(r"(Figure \d+)", panel or ""); f = figmap.get(m.group(1)) if m else None
        return {"label": panel, "image": f["image"], "thumbnail": f["thumbnail"], "page": f["page"]} if f and f.get("image") else None
    N, E = [], []
    def node(key, type, text_, desc, anchor, **x):
        n = {"key": key, "type": type, "text": text_, "description": desc or "", "anchor": anchor}; n.update({k: v for k, v in x.items() if v not in (None, "", [])}); N.append(n)
    def edge(rel, s, o): E.append({"relation": rel, "subject": s, "object": o})
    S = s7["summaries"]
    for q in s7["questions"]: node(q["key"], "Question", q["text"], q.get("description"), q["anchor"])
    for st in s1["studies"]: node(st["key"], "Study", st["text"], st.get("description"), st["anchor"])
    for p in s1["protocols"]:
        node(p["key"], "Protocol", p["text"], p.get("description"), p["anchor"])
        for st in p.get("followed_by", []): edge("follows", st, p["key"])
    doi = (jload(os.path.join(d, "paper.json"), {}) or {}).get("doi", "")
    node("d_paper", "SourceDocument", (jload(os.path.join(d, "paper.json"), {}) or {}).get("title", paper), "The paper this graph is extracted from.", text[:80].strip(), doi=doi)
    for st in s1["studies"]: edge("describesActivity", "d_paper", st["key"])
    checks = {c["evidence"]: c["role"] for c in s6["checks"]}
    for e in s2["evidence"]:
        node(e["key"], "Evidence", e["text"], S.get(e["key"]), e["anchor"], subtype="Check" if e["key"] in checks else None, panel=e.get("panel"),
             study=e.get("study"), figure=figure_for(e.get("panel")), sourceDocument=doi or None, notes=("Check: " + checks[e["key"]]) if e["key"] in checks else None)
        edge("grounds", e["study"], e["key"])
    for h in s4["hypotheses"]: node(h["key"], "Claim", h["text"], S.get(h["key"]), h["anchor"], subtype="Hypothesis")
    for f in s3["findings"]:
        node(f["key"], "Claim", f["text"], S.get(f["key"]), f["anchor"], notes=f.get("notes"))
        for k in f.get("supported_by", []): edge("supports", k, f["key"])
        for k in f.get("opposed_by", []): edge("opposes", k, f["key"])
        if f.get("interprets"): edge("supports", f["interprets"], f["key"])
    for h in s4["hypotheses"]:
        for k in h.get("supported_by", []): edge("supports", k, h["key"])
        for k in h.get("opposed_by", []): edge("opposes", k, h["key"])
    for a in s5["alternatives"]:
        node(a["key"], "Claim", a["text"], S.get(a["key"]), a["anchor"], subtype="Alternative", notes=a.get("notes"))
        for e in a.get("opposed_by", []): edge("opposes", e["evidence"], a["key"])
        for e in a.get("supported_by", []): edge("supports", e["evidence"], a["key"])
    for c in s6["cited"]:
        entry = f"{', '.join(c['authors'])} ({c['year']}). {c['title']}. {c['journal']} {c.get('volume', '')}:{c.get('pages', '')}."
        node(c["key"], "SourceDocument", entry, f"Cited work this paper leans on.", c["anchor"], doi=c["doi"], url="https://doi.org/" + c["doi"],
             authors=c["authors"], year=c["year"], journal=c["journal"], volume=c.get("volume"), pages=c.get("pages"), title=c["title"])
        ek = "e_" + c["key"]; node(ek, "Evidence", c["finding"], S.get(ek), c["anchor"], subtype="Cited", sourceDocument=c["key"], panel=f"cited: {entry.split('(')[0].strip()}")
        edge(c.get("relation", "supports"), ek, c["bears_on"])
    for r in s6["requests"]:
        node(r["key"], "Request", r["text"], S.get(r["key"]), r["anchor"])
        for k in r.get("about", []): edge("request_target", r["key"], k)
    for q in s7["questions"]:
        ad = q.get("addresses") or {}
        for k in ad.get("hypotheses", []) + ad.get("alternatives", []) + ad.get("findings", []): edge("addresses", k, q["key"])
    # typed ids
    PREFIX = {("Question", None): "Q", ("Claim", "Hypothesis"): "H", ("Claim", None): "F", ("Claim", "Alternative"): "A", ("Evidence", None): "E",
              ("Evidence", "Check"): "K", ("Evidence", "Cited"): "E", ("Request", None): "R", ("Study", None): "S", ("Protocol", None): "P", ("SourceDocument", None): "D"}
    counts, ID = Counter(), {}
    for n in N:
        pre = "C" if n["type"] == "SourceDocument" and n["key"] != "d_paper" else PREFIX[(n["type"], n.get("subtype"))]
        counts[pre] += 1; ID[n["key"]] = f"{pre}{counts[pre]}"
    keys = set(ID); E = [e for e in E if e["subject"] in keys and e["object"] in keys]
    for n in N:
        n["id"] = ID[n["key"]]
        for f in ("study", "sourceDocument"):
            if n.get(f) in ID: n[f] = ID[n[f]]
    for e in E: e["subject"], e["object"] = ID[e["subject"]], ID[e["object"]]
    stats = {"nodes": len(N), "edges": len(E), "by_type": dict(sorted(Counter(n["type"] for n in N).items())),
             "by_relation": dict(sorted(Counter(e["relation"] for e in E).items())), "uncovered_panels": s2.get("uncovered_panels", [])}
    graph = {"version": "0.1.0", "date": time.strftime("%Y-%m-%d"), "source": f"de novo, staged extraction ({DEFAULT_MODEL}); unadjudicated", "slug": paper,
             "paper": jload(os.path.join(d, "paper.json"), {"title": paper}), "subtypes": {"Hypothesis": "Claim", "Alternative": "Claim", "Check": "Evidence", "Cited": "Evidence"},
             "stats": stats, "nodes": N, "edges": E, "figures": figmap}
    gpath = os.path.join(d, f"{paper}-denovo.graph.json"); jdump(graph, gpath)
    tpath = os.path.join(d, "text.txt")
    subprocess.run([sys.executable, os.path.join(HERE, "mira_verify.py"), gpath, tpath])
    if reference:
        subprocess.run([sys.executable, os.path.join(HERE, "mira_align.py"), gpath, reference, os.path.join(d, "alignment.map.json") if os.path.exists(os.path.join(d, "alignment.map.json")) else "/dev/null", "--out", os.path.join(d, "alignment.json")])
    subprocess.run([sys.executable, os.path.join(HERE, "mira_viewer.py"), gpath, tpath, "--embed-figures"] + (["--compare", reference, os.path.join(d, "alignment.json"), "--compare-label", "hand-built reference"] if reference and os.path.exists(os.path.join(d, "alignment.json")) else []))
    print(json.dumps(stats))
    return graph

# ── driver ─────────────────────────────────────────────────────────────────────────────────────

def ensure_text(d, args):
    tpath = os.path.join(d, "text.txt")
    if "--msid" in args:
        subprocess.run([sys.executable, os.path.join(HERE, "mira_page_text.py"), args[args.index("--msid") + 1], "--out", d], check=True)
        for f in os.listdir(d):
            if f.endswith(".txt") and f != "text.txt" and not f.startswith("references"): os.replace(os.path.join(d, f), tpath)
    elif "--text" in args:
        import shutil; shutil.copy(args[args.index("--text") + 1], tpath)
    if not os.path.exists(tpath): sys.exit("no text: pass --msid or --text")
    text = open(tpath, encoding="utf-8").read()
    if not os.path.exists(os.path.join(d, "paper.json")):
        fj = jload(os.path.join(d, "figures.json"), {}) or {}
        jdump({"title": text.split("\n", 1)[0].strip(), "doi": fj.get("doi", ""), "version": fj.get("version", "")}, os.path.join(d, "paper.json"))
    return text

def run(paper, args):
    d = paths(paper); text = ensure_text(d, args)
    model = args[args.index("--model") + 1] if "--model" in args else DEFAULT_MODEL
    dry = "--dry-run" in args
    lo = int(args[args.index("--from") + 1]) if "--from" in args else 1
    hi = int(args[args.index("--to") + 1]) if "--to" in args else 8
    ref = args[args.index("--reference") + 1] if "--reference" in args else None
    L = lambda n: jload(os.path.join(d, f"stage{n}.json"))
    s = {}
    for n in range(1, 9):
        if n < lo: s[n] = L(n); continue
        if n > hi: break
        print(f"stage {n} {STAGES[n-1]}" + (" (dry)" if dry else ""))
        if n == 1: s[1] = stage1(d, text, model, dry)
        elif n == 2: s[2] = stage2(d, text, s[1] or L(1), model, dry)
        elif n == 3: s[3] = stage3(d, text, s[2] or L(2), model, dry)
        elif n == 4: s[4] = stage4(d, text, s[3] or L(3), model, dry)
        elif n == 5: s[5] = stage5(d, text, s[4] or L(4), s[3] or L(3), s[2] or L(2), model, dry)
        elif n == 6: s[6] = stage6(d, text, s[2] or L(2), s[3] or L(3), s[4] or L(4), s[5] or L(5), model, dry)
        elif n == 7: s[7] = stage7(d, text, s[4] or L(4), s[3] or L(3), s[5] or L(5), s[2] or L(2), s[6] or L(6), model, dry)
        elif n == 8:
            if dry: print("  stage 8 is code; nothing to render"); break
            s[8] = stage8(d, paper, text, *(s[k] or L(k) for k in range(1, 8)), ref)
        if dry and n < 8 and s[n] is not None and not any(s[n].get(k) for k in s[n] if isinstance(s[n].get(k), list)):
            # a dry run has no replies: later prompts render against empty inputs, which is still useful to read
            pass

def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("run", "stage"): sys.exit(__doc__)
    if a[0] == "run": run(a[1], a[2:])
    else: run(a[1], ["--from", a[2], "--to", a[2]] + a[3:])

if __name__ == "__main__":
    main()
