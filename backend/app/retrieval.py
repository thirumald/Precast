"""Small BM25 index over unstructured pipeline text (engagement notes, developments, rationale).

Dependency-free so it runs fully offline. Swap for a vector store if the corpus grows large.
"""
from __future__ import annotations

import math
import re
from collections import Counter

STOP = set("""the a an and or of to in on for with is are was were be by at from this that it as what which who
how all any list show me our we their there has have had do does did not no yes about into than then
في من على إلى عن ما هي هو التي الذي كل""".split())


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[\w؀-ۿ]+", (text or "").lower()) if t not in STOP and len(t) > 1]


class BM25:
    def __init__(self, docs: list[tuple[str, str, dict]], k1: float = 1.4, b: float = 0.75):
        self.docs = docs  # (doc_id, text, meta)
        self.toks = [tokens(t) for _, t, _ in docs]
        self.k1, self.b = k1, b
        self.avg = sum(map(len, self.toks)) / max(1, len(self.toks))
        df = Counter(t for ts in self.toks for t in set(ts))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 5) -> list[dict]:
        q = tokens(query)
        out = []
        for (did, text, meta), ts in zip(self.docs, self.toks):
            tf = Counter(ts)
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf.get(t, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(ts) / self.avg))
            if s > 0:
                out.append({"id": did, "text": text, "score": round(s, 3), **meta})
        return sorted(out, key=lambda r: -r["score"])[:k]


def build_index(opps: list[dict], engs: list[dict], discs: list[dict] | None = None) -> BM25:
    names = {o["id"]: o["name"] for o in opps}
    docs = []
    for e in engs:
        docs.append((e["id"], f"{e.get('summary') or ''} {e.get('commitments') or ''} {e.get('follow_up') or ''}",
                     {"opp": e.get("opp"), "opp_name": names.get(e.get("opp"), ""), "date": e.get("date"), "kind": "engagement"}))
    for d in discs or []:
        docs.append((d["id"], d.get("body") or "", {"opp": d.get("opp"), "opp_name": names.get(d.get("opp"), ""),
                     "date": (d.get("created") or "")[:10], "kind": "discussion", "author": d.get("author")}))
    for o in opps:
        if o["id"].startswith("HIS-"):
            continue
        docs.append((o["id"], f"{o['name']} {o.get('counterparty') or ''} {o.get('latest') or ''} {o.get('rationale') or ''}",
                     {"opp": o["id"], "opp_name": o["name"], "date": o.get("verified"), "kind": "opportunity"}))
    return BM25(docs)
