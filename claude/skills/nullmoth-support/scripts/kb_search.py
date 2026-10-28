#!/usr/bin/env python3
# <wtl> project: agents | file: claude/skills/nullmoth-support/scripts/kb_search.py | author: watchthelight </wtl>
"""Search the nullmoth knowledge base and print the best hits with a link for each.

    python kb_search.py "black screen after wake" [--n 12] [--kind docs|issues|releases|code|notes|answers]
    python kb_search.py --exact "nvrmsettle"          # one literal string, every place it appears

Ranking: Bash's server notes and the repos' docs first, then release notes, then closed issues a maintainer answered,
then other issues, then code. Each hit prints the lines that matched, with line numbers, and a URL to cite.
"""
import argparse
import json
import os
import re
from pathlib import Path

OWNER = "nullmoth"
KB = Path(os.environ.get("NULLMOTH_KB", Path.home() / "src" / "nullmoth-kb"))
TEXT = {".md", ".txt", ".conf", ".plist", ".toml", ".yml", ".yaml", ".json", ".html", ".py", ".rs", ".c", ".h",
        ".m", ".mm", ".cpp", ".hpp", ".swift", ".sh", ".ps1", ".cs", ".xml", ""}
SKIP_DIRS = {".git", "nvk", "upstream", "licenses", "node_modules", "vendor", "third_party", "target", "build"}
DOC_NAMES = {"README.md", "CHANGELOG.md", "CONTRIBUTING.md", "NOTICE.md", "AGENTS.md", "README.txt",
             "REPORTS-README.txt", "instructions.html"}
STOP = set("a an the and or of to in on is it for with my i me how do does what why can not no this that be "
           "from at as are was when after get got".split())


def kind_of(p: Path) -> str:
    rel = p.relative_to(KB).parts
    if rel[0] in ("notes", "answers", "releases", "issues"):
        return rel[0]
    if rel[0] == "repos":
        if "docs" in rel or p.name in DOC_NAMES or ".github" in rel:
            return "docs"
        return "code"
    return "other"


def url_of(p: Path, line: int, state: dict, text: str) -> str:
    rel = p.relative_to(KB).parts
    if rel[0] == "repos":
        sha = state.get("repos", {}).get(rel[1], {}).get("sha", "main")
        return f"https://github.com/{OWNER}/{rel[1]}/blob/{sha[:12]}/{'/'.join(rel[2:])}#L{line}"
    if rel[0] == "issues":
        # cite the comment the hit sits in when there is one, else the issue
        m = re.search(r"^url: (\S+)", text, re.M)
        url = m.group(1) if m else ""
        for i, l in enumerate(text.splitlines(), 1):
            if i > line:
                break
            m = re.match(r"^(?:url: |## .*\()(https://\S+?)\)?$", l)
            if m:
                url = m.group(1)
        return url
    if rel[0] == "releases":
        url = ""
        for i, l in enumerate(text.splitlines(), 1):
            if i > line:
                break
            if l.startswith("url: "):
                url = l[5:]
        return url or f"https://github.com/{OWNER}/{p.stem}/releases"
    return str(p)


def files():
    for root, dirs, fs in os.walk(KB):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and d != "data"]
        for f in fs:
            p = Path(root) / f
            if p.suffix.lower() in TEXT and p.name != "state.json" and p.stat().st_size < 1_500_000:
                yield p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?")
    ap.add_argument("--exact")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--kind")
    a = ap.parse_args()
    if not (KB / "state.json").exists():
        raise SystemExit(f"no knowledge base at {KB}: run kb_sync.py first")
    state = json.loads((KB / "state.json").read_text(encoding="utf-8"))
    if a.exact:
        terms, pat = [a.exact.lower()], re.compile(re.escape(a.exact), re.I)
    else:
        terms = [t for t in re.findall(r"[\w.\-]+", (a.query or "").lower()) if t not in STOP and len(t) > 1]
        if not terms:
            raise SystemExit("empty query")
        pat = re.compile("|".join(re.escape(t) for t in terms), re.I)
    weight = {"notes": 2.0, "docs": 1.8, "answers": 1.4, "releases": 1.5, "issues": 1.0, "code": 0.5, "other": 0.5}
    hits = []
    for p in files():
        k = kind_of(p)
        if a.kind and k != a.kind:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        low = text.lower()
        present = [t for t in terms if t in low]
        if not present:
            continue
        coverage = len(present) / len(terms)
        if not a.exact and coverage < 0.5:
            continue
        lines = [(i, l) for i, l in enumerate(text.splitlines(), 1) if pat.search(l)]
        density = sum(min(low.count(t), 8) for t in present)
        score = weight[k] * (coverage ** 2) * (1 + density) ** 0.5
        if k == "issues":
            head = text[:600]
            if "state: closed (completed)" in head or "state: closed\n" in head:
                score *= 1.2
            if "[maintainer]" in text:
                score *= 1.3
        best = sorted(lines, key=lambda il: -sum(t in il[1].lower() for t in terms))[:4]
        hits.append((score, k, p, sorted(best), text))
    hits.sort(key=lambda h: -h[0])
    for score, k, p, best, text in hits[:a.n]:
        first = best[0][0] if best else 1
        title = text.splitlines()[0][:110] if k in ("issues",) else str(p.relative_to(KB))
        print(f"[{k} {score:.1f}] {title}\n  {url_of(p, first, state, text)}\n  file: {p}")
        for i, l in best:
            print(f"    {i}: {l.strip()[:160]}")
    print(f"{len(hits)} file(s) matched, showing {min(len(hits), a.n)}")


if __name__ == "__main__":
    main()
