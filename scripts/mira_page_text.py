#!/usr/bin/env python3
"""mira_page_text — the article text as eLife Pathways serves it, flattened for anchoring.

A hand-built graph's anchors must be found character-for-character in the text the consumer
will dock them to. eLife Pathways renders a Reviewed Preprint version from its article JSON
(the page's __NEXT_DATA__), which differs from the JATS our `prepare` layer reads (v1 vs v2,
statistics formatted differently, sections renamed, no appendix). This flattens that page's
content — title, abstract, headings, paragraphs, figure captions — into one text file, and
records the figure ids and image URLs the page uses, so anchors and figure links both match.

Usage:
  mira_page_text.py <msid> [--out <paper-dir>]     e.g. mira_page_text.py 105391 --out runs/gadeke-2026-guilt-insula/mira-hand
Writes <out>/<slug>-page.txt and <out>/figures.json.
"""
import json, os, re, sys, urllib.request

PAGE = "https://epp.elifepathways.org/mira/{msid}"
IIIF = "https://iiif.elifesciences.org/epp/{msid}%2F{ver}%2Fcontent%2F{file}/full/{w}/0/default.jpg"

def flatten(node):
    if isinstance(node, str): return node
    if isinstance(node, list): return "".join(flatten(n) for n in node)
    if isinstance(node, dict):
        t = node.get("type")
        if t == "Heading": return "\n\n## " + flatten(node.get("content", "")) + "\n"
        if t == "Paragraph": return "\n" + flatten(node.get("content", "")) + "\n"
        if t == "Figure": return f"\n[{node.get('label', '')}] {flatten(node.get('caption', ''))}\n"
        if "content" in node: return flatten(node["content"])
        if "text" in node: return node["text"]
    return ""

def figures(content, msid):
    out = []
    def walk(n):
        if isinstance(n, dict):
            if n.get("type") == "Figure":
                urls = []
                def u(x):
                    if isinstance(x, dict):
                        for k, v in x.items():
                            if k in ("contentUrl", "url", "src") and isinstance(v, str): urls.append(v)
                            u(v)
                    elif isinstance(x, list): [u(i) for i in x]
                u(n)
                rel = next((x for x in urls if x.endswith((".tif", ".jpg", ".png"))), None)
                ver, file = (rel.split("/")[1], rel.split("/")[-1]) if rel else (None, None)
                out.append({"id": n.get("id"), "label": n.get("label"), "file": rel,
                            "image": IIIF.format(msid=msid, ver=ver, file=file, w="max") if rel else None,
                            "thumbnail": IIIF.format(msid=msid, ver=ver, file=file, w="480,") if rel else None,
                            "page": PAGE.format(msid=msid) + "#" + (n.get("id") or "")})
            for v in n.values(): walk(v)
        elif isinstance(n, list): [walk(i) for i in n]
    walk(content)
    return out

def main():
    a = sys.argv[1:]
    msid = a[0]
    out = a[a.index("--out") + 1] if "--out" in a else "."
    html = urllib.request.urlopen(PAGE.format(msid=msid), timeout=60).read().decode("utf-8")
    d = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S).group(1))
    p = d["props"]["pageProps"]; md = p["metaData"]
    text = md["article"]["title"] + "\n\n" + flatten(md["article"]["abstract"]) + "\n" + flatten(md["article"]["content"])
    text = re.sub(r"[ \t]+", " ", text); text = re.sub(r"\n{3,}", "\n\n", text)
    os.makedirs(out, exist_ok=True)
    slug = p.get("msidWithVersion", msid)
    open(os.path.join(out, f"{slug}-page.txt"), "w", encoding="utf-8").write(text)
    json.dump({"msid": msid, "version": slug, "doi": md.get("versionDoi"), "figures": figures(md["article"]["content"], msid)},
              open(os.path.join(out, "figures.json"), "w"), indent=1)
    print(f"{slug}: {len(text):,} chars → {out}/{slug}-page.txt; {len(figures(md['article']['content'], msid))} figures → figures.json")

if __name__ == "__main__":
    main()
