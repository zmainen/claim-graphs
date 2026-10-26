#!/usr/bin/env python3
"""mira_score — score extractor graphs against a paper's own eliminative structure.

Not a comparison with our graph: a check of what a run represents of what the paper argues.
For each graph: the alternatives the paper raises (listed per paper in ALTERNATIVES below, each
as a regex over Claim text), whether each appears as a Claim and whether anything opposes it;
the Questions; hypotheses kept apart from findings (Claim→Claim supports); Evidence split by
study; and the straw-rival guard (a check turned into an opposed Claim).

Keyword matching is a first pass for a person to confirm, not a verdict.

Usage:
  mira_score.py <paper> [graph.json ...]      scores every *.graph.json under runs/<paper>/mira-baseline/
                                              plus any extra graph files given
"""
import glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from roots import GRAPH as ROOT  # noqa: E402

# The alternatives a paper raises — four argued against and one left open, for Gädeke — found by
# reading the paper (eliminating sentences in the Results, the compared models, the control
# rationale in the Introduction, the Discussion's "cannot exclude"), not by any extractor.
ALTERNATIVES = {
    "gadeke-2026-guilt-insula": {
        "own-outcome disappointment": r"own (lottery )?outcome|disappoint|self-directed",
        "general responsibility / agency effect": r"(positive|high|good) (partner )?(lottery )?outcomes?.*(responsib|happiness)|responsibility aversion|decision-making burden|general responsibility|agency aversion|weight of (the )?responsibility",
        "risk-attitude shift": r"risk (preference|attitude|aversion|premium)",
        "inequality aversion": r"inequal|guilt-envy|envy",
        "empathy / other emotion rather than guilt (open)": r"empath|bad luck|failure|shame",
        "validity: algorithm partner": r"algorithm",
    },
}
CHECKS = r"manipulation check|ventral striatum|icebreaker|ice-breaker|parameter recovery|expected value of the lottery|value-sensitive|replicat"

def score(name, g, alts):
    N = {n["id"]: n for n in g["nodes"]}
    claims = [n for n in g["nodes"] if n["type"] == "Claim"]
    ev = [n for n in g["nodes"] if n["type"] == "Evidence"]
    opp = [e for e in g["edges"] if e["relation"] == "opposes"]
    opposed = {e["object"] for e in opp}
    cc = [e for e in g["edges"] if e["relation"] == "supports" and N.get(e["subject"], {}).get("type") == "Claim"]
    qs = [n for n in g["nodes"] if n["type"] == "Question"]
    print(f"\n#### {name}: {len(g['nodes'])} nodes · {len(qs)} Q · {len(claims)} C · {len(ev)} E · opposes {len(opp)} · claim→claim supports {len(cc)}")
    for q in qs:
        print("   Q:", q["text"][:150])
    print("  alternatives as Claims:")
    for label, pat in alts.items():
        hits = [c for c in claims if re.search(pat, c["text"], re.I)]
        for c in hits:
            print(f"   [{'OPPOSED' if c['id'] in opposed else 'open   '}] {label}: {c['text'][:120]}")
        if not hits:
            print(f"   [absent ] {label}")
    for e in opp:
        if e["subject"] in N and e["object"] in N:
            print(f"  opposes: {N[e['subject']]['type']} '{N[e['subject']]['text'][:70]}' → '{N[e['object']]['text'][:70]}'")
    straw = [c for c in claims if re.search(CHECKS, c["text"], re.I) and c["id"] in opposed]
    print(f"  straw rivals (checks opposed as claims): {len(straw)}")
    by_study = sum(1 for n in ev if re.search(r"\bStudy [12]\b", n["text"]))
    pooled = sum(1 for n in ev if re.search(r"both studies|either study|in each study", n["text"], re.I))
    print(f"  evidence naming one study: {by_study}/{len(ev)} · pooled across studies: {pooled} · with a number: {sum(1 for n in ev if re.search('[0-9]', n['text']))}/{len(ev)}")

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    paper = sys.argv[1]
    alts = ALTERNATIVES.get(paper)
    if not alts:
        sys.exit(f"no alternatives listed for {paper}; add them to ALTERNATIVES after reading the paper")
    d = os.path.join(ROOT, "runs", paper, "mira-baseline")
    for f in sorted(glob.glob(os.path.join(d, "*.graph.json"))) + sys.argv[2:]:
        score(os.path.basename(f)[:-len(".graph.json")], json.load(open(f)), alts)

if __name__ == "__main__":
    main()
