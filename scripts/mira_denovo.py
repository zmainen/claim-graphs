#!/usr/bin/env python3
"""mira_denovo — the staged MIRA extraction, de novo, per docs/design/2026-11-01-mira-denovo-stages.md.

Eight stages. Each stage renders a prompt from extract/prompts/mira/stage-N-*.md, calls the model
(stage 8 is code), checks the reply, and writes to runs/<paper>/mira-denovo/:
  stageN.json          accepted items            stageN.rejected.json   refused items with reasons
  calls/stageN[-k].prompt.txt / .raw.txt / .meta.json   every call, for the harness page
Anchors must be verbatim in text.txt; anything else is refused, not repaired.

Usage:
  mira_denovo.py run <paper> [--msid 105391 | --text file.txt] [--from N] [--to N] [--model M] [--dry-run] [--reference graph.json]
  mira_denovo.py stage <paper> N [same options]       # one stage, inputs from the files on disk
A reply that is not JSON, or a call that fails, stops the run; resume with --from N.
--dry-run renders every prompt it can from the inputs on disk and makes no call.
Model default: anthropic/claude-sonnet-4.5 (OpenRouter id); the key comes from the Keychain.
--model claude:<id> (e.g. claude:claude-sonnet-4-5) runs each call through `claude -p` on the Max subscription
instead, isolated so the model sees only the stage prompt: empty temp cwd, no settings, CLAUDE.md, memory,
tools or MCP. The output cap is set to the same 30000 tokens; temperature cannot be set there.
"""
import json, os, re, subprocess, sys, tempfile, time
from collections import Counter, OrderedDict
import click

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.environ.get("CLAIM_GRAPHS_ROOT") or os.getcwd()   # the corpus, where runs/ lives
sys.path.insert(0, HERE)
from mira_baseline import stream, key as _key   # noqa: E402  (OpenRouter client, Keychain key)

CG = os.path.dirname(HERE)   # claim-graphs, where the prompts live
PROMPTS = os.path.join(CG, "extract", "prompts", "mira")
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"
STAGES = ["inventory", "evidence", "findings", "hypotheses", "alternatives", "checks-cited-requests", "questions-summaries", "assemble"]
# a figure or table, then its panel letters as written: "Figure 3D", "Figure 2B, C", "Figure 3A–D", "Figure 4A and B"
PANEL_RE = re.compile(r"\b((?:Supplementary )?(?:Figure|Table) \d+)((?:[A-Z](?![A-Za-z])(?:\s*(?:[–-]|,|and)\s*[A-Z](?![A-Za-z]))*)?)")
L = lambda i, k: i.get(k) or []   # a list field the model may have sent as null
T = lambda i, k: str(i.get(k) or "")   # likewise a string field

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

def claude_cli(system, user, model):
    """One call through Claude Code headless on the subscription. Returns stream()'s (content, reasoning_chars, model, usage, error)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "CLAUDE_CODE_USE_", "CLAUDECODE"))}
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "30000"   # the OpenRouter path's max_tokens
    cmd = ["claude", "-p", "--model", model, "--system-prompt", system, "--output-format", "json", "--max-turns", "1",
           "--tools", "", "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence",
           "--exclude-dynamic-system-prompt-sections"]
    with tempfile.TemporaryDirectory() as cwd:
        try: r = subprocess.run(cmd, input=user, capture_output=True, text=True, cwd=cwd, env=env, timeout=1800)
        except subprocess.TimeoutExpired: return "", 0, model, None, "timeout"
    try: ev = json.loads(r.stdout); ev = ev if isinstance(ev, list) else [ev]
    except ValueError: return "", 0, model, None, (r.stderr or r.stdout)[-2000:] or f"exit {r.returncode}"
    init = next((e for e in ev if e.get("type") == "system"), {}); j = next((e for e in reversed(ev) if e.get("type") == "result"), {})
    usage = dict(j.get("usage") or {}, cost_usd_equivalent=j.get("total_cost_usd"), auth=init.get("apiKeySource"),
                 tools=init.get("tools"), mcp_servers=init.get("mcp_servers"), cli_version=init.get("claude_code_version"), stop_reason=j.get("stop_reason"))
    error = (j.get("result") or j.get("subtype") or "no result") if j.get("is_error") or not j else \
        "output cap reached" if j.get("stop_reason") == "max_tokens" else None
    return j.get("result") or "", 0, ",".join(j.get("modelUsage") or {}) or model, usage, error

def call(d, tag, system, user, model, dry):
    base = os.path.join(d, "calls", tag)
    open(base + ".prompt.txt", "w", encoding="utf-8").write("## System\n\n" + system + "\n\n## User\n\n" + user)
    if dry: return None
    if model.startswith("claude:"):
        t0 = time.time(); content, reasoning, used, usage, error = claude_cli(system, user, model[7:])
    else:
        body = {"model": model, "temperature": 0.2, "max_tokens": 30000, "stream": True,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        t0 = time.time(); content, reasoning, used, usage, error = stream(body)
    open(base + ".raw.txt", "w", encoding="utf-8").write(content)
    jdump({"model": model, "served_by": used, "usage": usage, "error": error, "seconds": round(time.time() - t0, 1),
           "prompt_chars": len(system) + len(user), "reply_chars": len(content), "reasoning_chars": reasoning,
           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}, base + ".meta.json")
    rep = parse_json(content)
    if error or rep is None:
        sys.exit(f"  {tag}: {error or 'reply is not JSON'} (see {base}.raw.txt); fix and resume with --from {tag[5]}")
    return rep

# ── checkers: every stage returns (accepted, rejected) ─────────────────────────────────────────

def verbatim(text, a):
    return bool(a) and a in text

def check_items(items, text, rules, need=("key", "text")):
    """rules: list of (name, predicate(item) -> True|reason). Verbatim anchor and the `need` fields are always checked first."""
    ok, bad = [], []
    for it in items or []:
        why = ([] if verbatim(text, it.get("anchor")) else ["anchor not verbatim"]) + [f"no {f}" for f in need if not it.get(f)]
        for name, pred in rules:
            r = pred(it)
            if r is not True: why.append(f"{name}: {r}")
        (bad if why else ok).append(dict(it, **({"refused": why} if why else {})))
    return ok, bad

# ── stage 1: inventory ─────────────────────────────────────────────────────────────────────────

def panel_refs(s):
    """Every panel a string cites, ranges and lists expanded: "Figure 3A–C" -> Figure 3A, Figure 3B, Figure 3C."""
    for m in PANEL_RE.finditer(s or ""):
        fig, toks = m.group(1), re.findall(r"[A-Z]|[–-]", m.group(2))
        if not toks: yield fig; continue
        for i, t in enumerate(toks):
            if t in "–-": continue
            lo = ord(toks[i - 2]) + 1 if i >= 2 and toks[i - 1] in "–-" else ord(t)
            yield from (fig + chr(c) for c in range(lo, ord(t) + 1))

def panels_in(text):
    seen = OrderedDict.fromkeys(panel_refs(text))
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
    studies, bad_s = check_items(rep.get("studies"), text, [])
    skeys = {s["key"] for s in studies}
    protocols, bad_p = check_items(rep.get("protocols"), text, [
        ("followed", lambda i: True if any(k in skeys for k in L(i, "followed_by")) else "no study follows it")])
    panels = panels_in(text)
    inv = {"panels": panels, "groups": groups_of(panels), "studies": studies, "protocols": protocols}
    if not dry: jdump(inv, os.path.join(d, "stage1.json")); jdump({"studies": bad_s, "protocols": bad_p}, os.path.join(d, "stage1.rejected.json"))
    return inv

# ── stage 2: evidence per panel group ──────────────────────────────────────────────────────────

def passages(text, panels, width=700):
    """Paragraphs mentioning any of the panels, with their neighbours, deduplicated and in order."""
    paras, want = text.split("\n\n"), set(panels)
    hit = {i for i, p in enumerate(paras) if want & set(panel_refs(p))}
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
            ("study", lambda i: True if i.get("study") in skeys else f"unknown study {i.get('study')!r}")], need=("key", "text", "panel"))
        seen = {e["key"] for e in acc}
        for it in ok:   # each group's call names its keys blind to the others; a clash gets the group number
            it["group"] = fig
            if it["key"] in seen: it["key"] = f"{it['key']}_g{k}"
            seen.add(it["key"])
        acc += ok; rej += bad
    covered = {p for e in acc for p in panel_refs(e["panel"])} | {e["panel"] for e in acc}
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
        ("supported", lambda i: True if any(k in ekeys for k in L(i, "supported_by")) else "no known evidence supports it"),
        ("no statistic", lambda i: True if not re.search(r"\bp\s*[<=>]|t\(\d|BF10|β\s*=", T(i, "text")) else "statistic in text")])
    used = {k for f in ok for k in L(f, "supported_by") + L(f, "opposed_by")}
    out = {"findings": ok, "evidence_unused": sorted(ekeys - used)}
    if not dry: jdump(out, os.path.join(d, "stage3.json")); jdump(bad, os.path.join(d, "stage3.rejected.json"))
    return out

def stage4(d, text, fnd, model, dry):
    system, user, _ = render(4, {"findings": fnd["findings"], "text": text})
    rep = call(d, "stage4", system, user, model, dry) or {}
    fkeys = {f["key"] for f in fnd["findings"]}
    ok, bad = check_items(rep.get("hypotheses"), text, [
        ("tested", lambda i: True if any(k in fkeys for k in L(i, "supported_by") + L(i, "opposed_by")) else "no finding tests it")])
    out = {"hypotheses": ok}
    if not dry: jdump(out, os.path.join(d, "stage4.json")); jdump(bad, os.path.join(d, "stage4.rejected.json"))
    return out

def stage5(d, text, hyp, fnd, ev, model, dry):
    system, user, _ = render(5, {"hypotheses": hyp["hypotheses"], "findings": fnd["findings"], "evidence": ev["evidence"], "text": text})
    rep = call(d, "stage5", system, user, model, dry) or {}
    ekeys = {e["key"] for e in ev["evidence"]}
    def edges_ok(i):   # the precision guard: every opposes/supports edge carries its own verbatim inference sentence
        for side in ("opposed_by", "supported_by"):
            for e in L(i, side):
                if e.get("evidence") not in ekeys: return f"{side}: unknown evidence {e.get('evidence')!r}"
                if not verbatim(text, e.get("anchor")): return f"{side}: edge anchor not verbatim"
        return True
    ok, bad = check_items(rep.get("alternatives"), text, [
        ("positive", lambda i: True if not re.match(r"^(The .* (is|was) not|There is no|No )", T(i, "text")) else "stated as a negation"),
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
    checks = [c for c in L(rep, "checks") if c.get("evidence") in ekeys and c.get("role")]
    cited, bad_c = check_items(rep.get("cited"), text, need=("key", "authors", "year", "title", "journal", "finding"), rules=[
        ("doi", lambda i: True if re.match(r"^10\.\d{4,}/", T(i, "doi")) else "no DOI"),
        ("authors", lambda i: True if isinstance(i.get("authors"), list) else "authors not a list"),
        ("bears_on", lambda i: True if i.get("bears_on") in ckeys else f"unknown claim {i.get('bears_on')!r}")])
    requests, bad_r = check_items(rep.get("requests"), text, [
        ("about", lambda i: True if any(k in ckeys for k in L(i, "about")) else "no known target")])
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
        if not isinstance(s, str): bad_s[k] = {"summary": s, "refused": "not text"}; continue
        n = len([x for x in re.split(r"(?<=[.!?])\s+", s.strip()) if x])
        if 1 <= n <= 2 and not EDITORIAL.match(s) and not re.search(r"\d", s): summaries[k] = s
        else: bad_s[k] = {"summary": s, "refused": "sentences" if n > 2 else "editorial" if EDITORIAL.match(s) else "contains a number"}
    out = {"questions": questions, "summaries": summaries}
    if not dry: jdump(out, os.path.join(d, "stage7.json")); jdump({"questions": bad_q, "summaries": bad_s}, os.path.join(d, "stage7.rejected.json"))
    return out

# ── stage 8: assemble ──────────────────────────────────────────────────────────────────────────

def stage8(d, paper, text, model, s1, s2, s3, s4, s5, s6, s7, reference):
    fj = jload(os.path.join(d, "figures.json"), {}) or {}
    figs = fj.get("figures", fj) if isinstance(fj, dict) else fj
    figmap = {f["label"].rstrip(":. "): f for f in figs if f.get("label")}   # eLife labels read "Figure 1:"
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
        for st in L(p, "followed_by"): edge("follows", st, p["key"])
    paper_meta = jload(os.path.join(d, "paper.json"), {}) or {"title": paper}; doi = paper_meta.get("doi", "")
    node("d_paper", "SourceDocument", paper_meta.get("title", paper), "The paper this graph is extracted from.", text[:80].strip(), doi=doi)
    for st in s1["studies"]: edge("describesActivity", "d_paper", st["key"])
    checks = {c["evidence"]: c["role"] for c in s6["checks"]}
    for e in s2["evidence"]:
        node(e["key"], "Evidence", e["text"], S.get(e["key"]), e["anchor"], subtype="Check" if e["key"] in checks else None, panel=e.get("panel"),
             study=e.get("study"), figure=figure_for(e.get("panel")), sourceDocument=doi or None, notes=("Check: " + checks[e["key"]]) if e["key"] in checks else None)
        edge("grounds", e["study"], e["key"])
    for h in s4["hypotheses"]: node(h["key"], "Claim", h["text"], S.get(h["key"]), h["anchor"], subtype="Hypothesis")
    for f in s3["findings"]:
        node(f["key"], "Claim", f["text"], S.get(f["key"]), f["anchor"], notes=f.get("notes"))
        for k in L(f, "supported_by"): edge("supports", k, f["key"])
        for k in L(f, "opposed_by"): edge("opposes", k, f["key"])
        if f.get("interprets"): edge("supports", f["interprets"], f["key"])
    for h in s4["hypotheses"]:
        for k in L(h, "supported_by"): edge("supports", k, h["key"])
        for k in L(h, "opposed_by"): edge("opposes", k, h["key"])
    for a in s5["alternatives"]:
        node(a["key"], "Claim", a["text"], S.get(a["key"]), a["anchor"], subtype="Alternative", notes=a.get("notes"))
        for e in L(a, "opposed_by"): edge("opposes", e["evidence"], a["key"])
        for e in L(a, "supported_by"): edge("supports", e["evidence"], a["key"])
    for c in s6["cited"]:
        entry = f"{', '.join(c['authors'])} ({c['year']}). {c['title']}. {c['journal']} {T(c, 'volume')}:{T(c, 'pages')}."
        node(c["key"], "SourceDocument", entry, f"Cited work this paper leans on.", c["anchor"], doi=c["doi"], url="https://doi.org/" + c["doi"],
             authors=c["authors"], year=c["year"], journal=c["journal"], volume=c.get("volume"), pages=c.get("pages"), title=c["title"])
        ek = "e_" + c["key"]; node(ek, "Evidence", c["finding"], S.get(ek), c["anchor"], subtype="Cited", sourceDocument=c["key"], panel=f"cited: {entry.split('(')[0].strip()}")
        edge(c.get("relation", "supports"), ek, c["bears_on"])
    for r in s6["requests"]:
        node(r["key"], "Request", r["text"], S.get(r["key"]), r["anchor"])
        for k in L(r, "about"): edge("request_target", r["key"], k)
    for q in s7["questions"]:
        ad = q.get("addresses") or {}
        for k in L(ad, "hypotheses") + L(ad, "alternatives") + L(ad, "findings"): edge("addresses", k, q["key"])
    # typed ids
    PREFIX = {("Question", None): "Q", ("Claim", "Hypothesis"): "H", ("Claim", None): "F", ("Claim", "Alternative"): "A", ("Evidence", None): "E",
              ("Evidence", "Check"): "K", ("Evidence", "Cited"): "E", ("Request", None): "R", ("Study", None): "S", ("Protocol", None): "P", ("SourceDocument", None): "D"}
    dup = [k for k, c in Counter(n["key"] for n in N).items() if c > 1]
    if dup: sys.exit(f"stage 8: keys used by more than one node: {dup}")
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
    graph = {"version": "0.1.0", "date": time.strftime("%Y-%m-%d"), "source": f"de novo, staged extraction ({model}); unadjudicated", "slug": paper,
             "paper": paper_meta, "subtypes": {"Hypothesis": "Claim", "Alternative": "Claim", "Check": "Evidence", "Cited": "Evidence"},
             "stats": stats, "nodes": N, "edges": E, "figures": figmap}
    gpath = os.path.join(d, f"{paper}-denovo.graph.json"); jdump(graph, gpath)
    tpath = os.path.join(d, "text.txt")
    if subprocess.run([sys.executable, os.path.join(HERE, "mira_verify.py"), gpath, tpath]).returncode:
        print("  stage 8: verification found problems; see the verification file beside the graph")
    if reference:
        subprocess.run(check=True, args=[sys.executable, os.path.join(HERE, "mira_align.py"), gpath, reference, os.path.join(d, "alignment.map.json") if os.path.exists(os.path.join(d, "alignment.map.json")) else "/dev/null", "--out", os.path.join(d, "alignment.json")])
    subprocess.run(check=True, args=[sys.executable, os.path.join(HERE, "mira_viewer.py"), gpath, tpath, "--embed-figures"] + (["--compare", reference, os.path.join(d, "alignment.json"), "--compare-label", "hand-built reference"] if reference and os.path.exists(os.path.join(d, "alignment.json")) else []))
    print(json.dumps(stats))
    return graph

# ── driver ─────────────────────────────────────────────────────────────────────────────────────

def ensure_text(d, msid, text_file):
    tpath = os.path.join(d, "text.txt")
    if msid:
        subprocess.run([sys.executable, os.path.join(HERE, "mira_page_text.py"), msid, "--out", d], check=True)
        for f in os.listdir(d):
            if f.endswith(".txt") and f != "text.txt" and not f.startswith("references"): os.replace(os.path.join(d, f), tpath)
    elif text_file:
        import shutil; shutil.copy(text_file, tpath)
    if not os.path.exists(tpath): sys.exit("no text: pass --msid or --text")
    text = open(tpath, encoding="utf-8").read()
    if not os.path.exists(os.path.join(d, "paper.json")):
        fj = jload(os.path.join(d, "figures.json"), {}) or {}
        jdump({"title": text.split("\n", 1)[0].strip(), "doi": fj.get("doi", ""), "version": fj.get("version", "")}, os.path.join(d, "paper.json"))
    return text

def run(paper, msid=None, text_file=None, lo=1, hi=8, model=DEFAULT_MODEL, dry=False, reference=None):
    d = paths(paper); text = ensure_text(d, msid, text_file)
    get = lambda n: jload(os.path.join(d, f"stage{n}.json"))
    s = {}
    for n in range(1, 9):
        if n < lo: s[n] = get(n); continue
        if n > hi: break
        print(f"stage {n} {STAGES[n-1]}" + (" (dry)" if dry else ""))
        g = lambda k: s[k] or get(k)
        if n == 1: s[1] = stage1(d, text, model, dry)
        elif n == 2: s[2] = stage2(d, text, g(1), model, dry)
        elif n == 3: s[3] = stage3(d, text, g(2), model, dry)
        elif n == 4: s[4] = stage4(d, text, g(3), model, dry)
        elif n == 5: s[5] = stage5(d, text, g(4), g(3), g(2), model, dry)
        elif n == 6: s[6] = stage6(d, text, g(2), g(3), g(4), g(5), model, dry)
        elif n == 7: s[7] = stage7(d, text, g(4), g(3), g(5), g(2), g(6), model, dry)
        elif dry: print("  stage 8 is code; nothing to render")
        else: s[8] = stage8(d, paper, text, model, *(g(k) for k in range(1, 8)), reference)

def options(f):
    for o in reversed([
            click.option("--msid", help="eLife manuscript id; fetches the page text"),
            click.option("--text", "text_file", type=click.Path(exists=True), help="a text file instead of --msid"),
            click.option("--model", default=DEFAULT_MODEL, show_default=True, help="OpenRouter id, or claude:<id> for the Max subscription"),
            click.option("--dry-run", "dry", is_flag=True, help="render every prompt; make no call"),
            click.option("--reference", type=click.Path(exists=True), help="hand-built graph to align against after assembly")]):
        f = o(f)
    return f

@click.group(help=__doc__)
def cli(): pass

@cli.command("run")
@click.argument("paper")
@click.option("--from", "lo", type=click.IntRange(1, 8), default=1)
@click.option("--to", "hi", type=click.IntRange(1, 8), default=8)
@options
def run_cmd(paper, **kw): run(paper, **kw)

@cli.command("stage")
@click.argument("paper")
@click.argument("n", type=click.IntRange(1, 8))
@options
def stage_cmd(paper, n, **kw): run(paper, lo=n, hi=n, **kw)

if __name__ == "__main__":
    cli()
