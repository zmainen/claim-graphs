#!/usr/bin/env python3
"""mira-baseline — the MIRA community extractor's single model call, run on one paper, as a layer.

Step 1 of the programme on claim-graphs#77: a reproducible baseline from the community extractor
(MIRA-science/MIRA-extraction @ main, 2026-08-11) on the same prepared text our readers used,
before any of our own machinery is judged against it.

The call is reproduced exactly as `src/core.ts` composes it — the system message verbatim, the
user message `USER_PREAMBLE_PAPER + "\\n\\n---\\n" + paper`, temperature 0.2, a 60,000-token
output cap, streaming with usage accounting, bounded retries when the reply parses to no graph,
and the same fence-stripping parse — without executing the extractor's own TypeScript, which is
unlicensed third-party code. Not reproduced: the post-call duplicate fold, the consolidation
pass and the JSON-LD projection. What is saved per run is the raw graph the model returned.

Produces, under runs/<paper>/mira-baseline/:
  <tag>.run<i>.graph.json   the model's graph (nodes, edges, paper), when it parsed
  <tag>.run<i>.raw.txt      the raw reply
  <tag>.run<i>.meta.json    model that answered, seconds, tokens, cost, attempts, errors
  summary.json              one record per run — what the site's table view renders
  README.md                 the narrative and the error catalogue, kept by hand

The OpenRouter key is read from the Keychain at run time (`secrets get OPENROUTER_API_KEY`) and is
never written anywhere.

Usage:
  mira_baseline.py run <paper> [--model id] [--runs N] [--tag name]
  mira_baseline.py summarize <paper>
"""
from __future__ import annotations

import glob, json, os, re, subprocess, sys, time, urllib.error, urllib.request
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from roots import GRAPH as ROOT  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPTS = os.path.join(os.path.dirname(HERE), "extract", "prompts", "external", "mira-extraction")
URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"   # the extractor's pinned default
RETRIES, PACE_S = 2, 20                                     # core.ts parseRetries and its pacing
SINGLE_CALL_MAX = 400_000                                   # core.ts SINGLE_CALL_MAX

# ── the paper text, assembled the same way for every run and for our own track ───────────────

def paper_text(paper):
    d = json.load(open(os.path.join(ROOT, "runs", paper, "prepared.json"), encoding="utf-8"))
    parts = [d["title"], ", ".join(d["authors"]), f"DOI: {d['doi']}", "", "Abstract", d["abstract"], "",
             d["introduction_text"], "", d["results_text"], "", d["discussion_text"], "", d["methods_text"],
             "", "Figure captions", d["captions_text"], "", d["appendix_text"]]
    return "\n\n".join(parts)

# ── the call ─────────────────────────────────────────────────────────────────────────────────

def key():
    k = subprocess.run([os.path.expanduser("~/Projects/secrets-cli/secrets"), "get", "OPENROUTER_API_KEY"],
                       capture_output=True, text=True).stdout.strip()
    if not k:
        sys.exit("no OPENROUTER_API_KEY in the Keychain")
    return k

def parse_graph(t):
    t = t.strip()
    m = re.match(r"^```[^\n]*\n([\s\S]*?)\n```$", t)
    if m:
        t = m.group(1).strip()
    for s in (t, t[t.find("{"): t.rfind("}") + 1]):
        try:
            g = json.loads(s)
            if isinstance(g, dict) and "nodes" in g and "edges" in g:
                return g
        except Exception:
            pass
    return None

def stream(body):
    """One streamed call. Returns (content, reasoning_chars, model, usage, error)."""
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + key(), "Content-Type": "application/json", "Accept": "text/event-stream",
        "HTTP-Referer": "https://github.com/zmainen/claim-graphs", "X-Title": "claim-graphs mira-baseline"})
    content, reasoning, model, usage, error = [], 0, None, None, None
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    j = json.loads(payload)
                except Exception:
                    continue
                if j.get("error"):
                    error = j["error"]
                model = j.get("model") or model
                if j.get("usage"):
                    usage = j["usage"]
                for ch in j.get("choices") or []:
                    d = ch.get("delta") or {}
                    if d.get("content"):
                        content.append(d["content"])
                    if d.get("reasoning"):
                        reasoning += len(d["reasoning"])
    except urllib.error.HTTPError as e:
        error = {"http": e.code, "body": e.read().decode("utf-8", "replace")[:500]}
    except Exception as e:
        error = {"exception": str(e)[:300]}
    return "".join(content), reasoning, model, usage, error

def once(paper, text, model, out, tag, i, prompt="system_message.txt"):
    sysm = open(os.path.join(PROMPTS, prompt), encoding="utf-8").read()
    pre = open(os.path.join(PROMPTS, "user_preamble.txt"), encoding="utf-8").read()
    body = {"model": model, "temperature": 0.2, "max_tokens": 60000, "stream": True, "usage": {"include": True},
            "messages": [{"role": "system", "content": sysm},
                         {"role": "user", "content": f"{pre}\n\n---\n{text}"}]}
    base = os.path.join(out, f"{tag}.run{i}")
    attempts, graph, content = [], None, ""
    for attempt in range(RETRIES + 1):
        t0 = time.time()
        content, reasoning, answered, usage, error = stream(body)
        graph = parse_graph(content) if content else None
        attempts.append({"attempt": attempt + 1, "seconds": round(time.time() - t0, 1), "model_answered": answered,
                         "usage": usage, "error": error, "content_chars": len(content),
                         "reasoning_chars": reasoning, "parsed": graph is not None})
        print(json.dumps(attempts[-1]), flush=True)
        if graph:
            break
        if attempt < RETRIES:
            time.sleep(PACE_S)
    last = attempts[-1]
    meta = {"paper": paper, "tag": tag, "run": i, "model_requested": model, "model_answered": last["model_answered"],
            "seconds": round(sum(a["seconds"] for a in attempts), 1), "usage": last["usage"], "attempts": attempts,
            "parsed": graph is not None, "nodes": len(graph["nodes"]) if graph else None,
            "edges": len(graph["edges"]) if graph else None, "input_chars": len(text), "prompt": prompt, "route": "openrouter api",
            "when": time.strftime("%Y-%m-%dT%H:%M:%S")}
    open(base + ".raw.txt", "w", encoding="utf-8").write(content)
    json.dump(meta, open(base + ".meta.json", "w"), indent=1)
    if graph:
        json.dump(graph, open(base + ".graph.json", "w"), indent=1, ensure_ascii=False)
    print("RESULT", json.dumps({k: meta[k] for k in ("tag", "run", "parsed", "nodes", "edges", "seconds")}), flush=True)

def run(paper, args):
    model = args[args.index("--model") + 1] if "--model" in args else DEFAULT_MODEL
    runs = int(args[args.index("--runs") + 1]) if "--runs" in args else 1
    tag = args[args.index("--tag") + 1] if "--tag" in args else model.split("/")[-1].replace(":", "-")
    prompt = args[args.index("--prompt") + 1] if "--prompt" in args else "system_message.txt"
    out = os.path.join(ROOT, "runs", paper, "mira-baseline")
    os.makedirs(out, exist_ok=True)
    text = paper_text(paper)
    if len(text) > SINGLE_CALL_MAX:
        sys.exit(f"paper too big for one call: {len(text)} chars")
    start = 1 + len(glob.glob(os.path.join(out, f"{tag}.run*.meta.json")))
    for i in range(start, start + runs):
        once(paper, text, model, out, tag, i, prompt)
    summarize(paper)

# ── the summary the site renders ─────────────────────────────────────────────────────────────

def summarize(paper):
    out = os.path.join(ROOT, "runs", paper, "mira-baseline")
    rows = []
    for mf in sorted(glob.glob(os.path.join(out, "*.meta.json"))):
        m = json.load(open(mf))
        gf = mf.replace(".meta.json", ".graph.json")
        name = os.path.basename(mf)[:-len(".meta.json")]   # <tag>.run<i>
        row = {"run": name, "model": m.get("model_answered") or m["model_requested"],
               "parsed": m["parsed"], "seconds": m["seconds"],
               "attempts": len(m.get("attempts", [])),
               "tokens_in": (m.get("usage") or {}).get("prompt_tokens"),
               "tokens_out": (m.get("usage") or {}).get("completion_tokens"),
               "cost_usd": round((m.get("usage") or {}).get("cost", 0) or 0, 4),
               "error": ((m["attempts"][-1].get("error") or {}).get("message") if m.get("attempts") else None)}
        if os.path.exists(gf):
            g = json.load(open(gf))
            nodes = Counter(n.get("type") for n in g["nodes"])
            edges = Counter(e.get("relation") for e in g["edges"])
            row.update({"nodes": len(g["nodes"]), "edges": len(g["edges"]),
                        "questions": nodes.get("Question", 0), "claims": nodes.get("Claim", 0),
                        "evidence": nodes.get("Evidence", 0), "studies": nodes.get("Study", 0),
                        "protocols": nodes.get("Protocol", 0), "requests": nodes.get("Request", 0),
                        "supports": edges.get("supports", 0), "opposes": edges.get("opposes", 0),
                        "anchored": sum(1 for n in g["nodes"] if n.get("anchor"))})
        rows.append(row)
    summary = {"layer": "mira-baseline", "paper": paper, "extractor": "MIRA-science/MIRA-extraction @ main 2026-08-11",
               "runs": rows}
    json.dump(summary, open(os.path.join(out, "summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))

def answer(paper, args):
    """Record a reply produced outside this script — a Claude Code subagent answering the dumped
    prompt, as the extractor's own `--answer` mode does — as a run, with the same parse and files.
    Usage: answer <paper> <reply-file> --tag <tag> --model <id> [--prompt <system-message-name>]"""
    path = args[0]
    tag = args[args.index("--tag") + 1]
    model = args[args.index("--model") + 1]
    prompt = args[args.index("--prompt") + 1] if "--prompt" in args else "system_message.txt"
    out = os.path.join(ROOT, "runs", paper, "mira-baseline")
    content = open(path, encoding="utf-8").read()
    graph = parse_graph(content)
    i = 1 + len(glob.glob(os.path.join(out, f"{tag}.run*.meta.json")))
    base = os.path.join(out, f"{tag}.run{i}")
    meta = {"paper": paper, "tag": tag, "run": i, "model_requested": model, "model_answered": model, "seconds": None,
            "usage": None, "attempts": [{"attempt": 1, "seconds": None, "model_answered": model, "usage": None, "error": None,
                                         "content_chars": len(content), "reasoning_chars": 0, "parsed": graph is not None}],
            "parsed": graph is not None, "nodes": len(graph["nodes"]) if graph else None,
            "edges": len(graph["edges"]) if graph else None, "prompt": prompt, "route": "claude-code subagent",
            "input_chars": len(paper_text(paper)), "when": time.strftime("%Y-%m-%dT%H:%M:%S")}
    open(base + ".raw.txt", "w", encoding="utf-8").write(content)
    json.dump(meta, open(base + ".meta.json", "w"), indent=1)
    if graph:
        json.dump(graph, open(base + ".graph.json", "w"), indent=1, ensure_ascii=False)
    print("RESULT", json.dumps({k: meta[k] for k in ("tag", "run", "parsed", "nodes", "edges", "prompt")}))
    summarize(paper)

def second_pass(paper, args):
    """A second stage over an existing run's graph: one model call given the graph and the paper, whose
    reply is a PATCH (new nodes, new edges) merged onto the base graph and recorded as a new run.
    Usage: pass <paper> <base-run-name> --prompt <pass-prompt> --tag <tag> [--model id]"""
    base_name = args[0]
    prompt = args[args.index("--prompt") + 1]
    tag = args[args.index("--tag") + 1]
    model = args[args.index("--model") + 1] if "--model" in args else "anthropic/claude-sonnet-4.5"
    out = os.path.join(ROOT, "runs", paper, "mira-baseline")
    base = json.load(open(os.path.join(out, base_name + ".graph.json")))
    text = paper_text(paper)
    sysm = open(os.path.join(PROMPTS, prompt), encoding="utf-8").read()
    listing = "\n".join(f'{n["id"]}  [{n["type"]}]  {n["text"]}' for n in base["nodes"])
    edges = "\n".join(f'{e["relation"]}  {e["subject"]} -> {e["object"]}' for e in base["edges"]
                      if e["relation"] in ("addresses", "supports", "opposes"))
    user = (f"EXISTING GRAPH — nodes:\n{listing}\n\nEXISTING GRAPH — argument edges:\n{edges}\n\n---\n"
            f"THE PAPER:\n{text}")
    body = {"model": model, "temperature": 0.2, "max_tokens": 30000, "stream": True, "usage": {"include": True},
            "messages": [{"role": "system", "content": sysm}, {"role": "user", "content": user}]}
    i = 1 + len(glob.glob(os.path.join(out, f"{tag}.run*.meta.json")))
    name = f"{tag}.run{i}"
    t0 = time.time()
    content, reasoning, answered, usage, error = stream(body)
    secs = round(time.time() - t0, 1)
    patch = None
    if content:
        t = content.strip()
        m = re.match(r"^```[^\n]*\n([\s\S]*?)\n```$", t)
        if m:
            t = m.group(1).strip()
        for s in (t, t[t.find("{"): t.rfind("}") + 1]):
            try:
                p = json.loads(s)
                if isinstance(p, dict) and "nodes" in p and "edges" in p:
                    patch = p
                    break
            except Exception:
                pass
    open(os.path.join(out, name + ".raw.txt"), "w", encoding="utf-8").write(content or "")
    merged = None
    dropped = []
    if patch:
        ids = {n["id"] for n in base["nodes"]} | {n["id"] for n in patch["nodes"]}
        legal = {"addresses": ("Claim", "Question"), "supports": (("Evidence", "Claim"), "Claim"),
                 "opposes": (("Evidence", "Claim"), "Claim"), "grounds": ("Study", "Evidence")}
        types = {n["id"]: n["type"] for n in base["nodes"] + patch["nodes"]}
        keep = []
        for e in patch["edges"]:
            ok = e.get("subject") in ids and e.get("object") in ids and e.get("relation") in legal
            if ok:
                s, o = legal[e["relation"]]
                ok = (types[e["subject"]] in (s if isinstance(s, tuple) else (s,))) and types[e["object"]] == o
            (keep if ok else dropped).append(e)
        merged = {**base, "nodes": base["nodes"] + patch["nodes"], "edges": base["edges"] + keep,
                  "second_pass": {"prompt": prompt, "base": base_name, "added_nodes": len(patch["nodes"]),
                                  "added_edges": len(keep), "dropped_edges": dropped, "notes": patch.get("notes")}}
        json.dump(merged, open(os.path.join(out, name + ".graph.json"), "w"), indent=1, ensure_ascii=False)
        json.dump(patch, open(os.path.join(out, name + ".patch.json"), "w"), indent=1, ensure_ascii=False)
    meta = {"paper": paper, "tag": tag, "run": i, "model_requested": model, "model_answered": answered, "seconds": secs,
            "usage": usage, "attempts": [{"attempt": 1, "seconds": secs, "model_answered": answered, "usage": usage,
                                          "error": error, "content_chars": len(content or ""), "reasoning_chars": reasoning,
                                          "parsed": patch is not None}],
            "parsed": patch is not None, "nodes": len(merged["nodes"]) if merged else None,
            "edges": len(merged["edges"]) if merged else None, "prompt": prompt, "route": "openrouter api",
            "second_pass_over": base_name, "input_chars": len(user), "when": time.strftime("%Y-%m-%dT%H:%M:%S")}
    json.dump(meta, open(os.path.join(out, name + ".meta.json"), "w"), indent=1)
    print("RESULT", json.dumps({"run": name, "parsed": patch is not None,
                                "added_nodes": len(patch["nodes"]) if patch else None,
                                "added_edges": len(merged["edges"]) - len(base["edges"]) if merged else None,
                                "dropped_edges": len(dropped), "seconds": secs, "error": error}))
    if patch and patch.get("notes"):
        print("NOTES", patch["notes"])
    summarize(paper)

def main():
    cmds = {"run": run, "answer": answer, "pass": second_pass, "summarize": lambda p, a: summarize(p)}
    if len(sys.argv) < 3 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[sys.argv[1]](sys.argv[2], sys.argv[3:])

if __name__ == "__main__":
    main()
