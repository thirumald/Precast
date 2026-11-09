"""Ask Precast: bilingual natural-language questions over the pipeline.

Pipeline questions are answered by *computing*, not by letting the model guess numbers:
1. the LLM (or a keyword parser) turns the question into structured filters,
2. Python applies them to the scored register and totals the figures,
3. BM25 retrieves relevant engagement notes,
4. the LLM writes a short answer grounded only in those facts (or a template does).
"""
from __future__ import annotations

import json
import re
from datetime import date

from . import llm, ontology, retrieval, scoring
from .service import Snapshot

DOMAIN_TERMS = list(ontology.VOCAB["Domain"])


def _has(t: str, term: str) -> bool:
    return re.search(rf"(?<![\w\u0600-\u06FF]){re.escape(term)}(?![\w\u0600-\u06FF])", t) is not None


SCHEMA_HINT = """Return JSON with keys:
"domain": one of Security, Defense, Urban, Financial, Energy or null;
"country": country name in English or null;
"stage": one of Exploratory, Active Engagement, Proposal, Negotiation, Agreement, Execution, Closed Won, Closed Lost, On Hold or null;
"outlook": Positive, Neutral, Negative or null;
"intervention": true if the user asks about CEO/executive intervention, else null;
"blocked": true if the user asks about blocked, stuck or escalated deals, else null;
"at_risk": true if the user asks about at-risk, low-probability or negative deals, else null;
"overdue": true if asking about overdue actions or slipped milestones, else null;
"this_quarter": true if asking about this quarter, else null;
"sponsor": executive sponsor title or null;
"metric": "value" for revenue/pipeline/amount questions, "count" for how-many, "list" otherwise.
Use null for anything not mentioned. Output JSON only."""


def parse_keywords(q: str, countries: list[str]) -> dict:
    """Keyword parser driven by the ontology's bilingual labels and synonyms."""
    t = " " + q.lower() + " "
    f: dict = {}
    for syn, term in ontology.synonyms("Domain").items():
        if _has(t, syn):
            f["domain"] = term
            break
    for syn, term in ontology.synonyms("Country").items():
        if _has(t, syn.lower()):
            f["country"] = term
            break
    for c in countries:
        if "country" not in f and _has(t, c.lower()):
            f["country"] = c
    for syn, term in ontology.synonyms("Stage").items():
        if len(syn) > 3 and _has(t, syn):
            f["stage"] = term
            break
    for syn, term in ontology.synonyms("Outlook").items():
        if len(syn) > 3 and _has(t, syn) and term != "Negative":
            f["outlook"] = term
    if re.search(r"block|stuck|stall|escalat|محظور|متوقف|معطل|متعثر|تصعيد", t):
        f["blocked"] = True
    if re.search(r"interven|ceo|chief executive|تدخل|الرئيس التنفيذي", t):
        f["intervention"] = True
    if re.search(r"risk|at-risk|weak|negative|losing|مخاطر|خطر|سلبي", t):
        f["at_risk"] = True
    if re.search(r"overdue|late|slipp|متأخر", t):
        f["overdue"] = True
    if re.search(r"this quarter|current quarter|هذا الربع|الربع الحالي", t):
        f["this_quarter"] = True
    if re.search(r"how many|count|number of|كم عدد|عدد", t):
        f["metric"] = "count"
    elif re.search(r"revenue|value|pipeline|impact|worth|amount|aed|إيرادات|قيمة|الأثر|تأثير", t):
        f["metric"] = "value"
    else:
        f["metric"] = "list"
    return f


def apply_filters(snap: Snapshot, f: dict) -> list[dict]:
    stage = f.get("stage")
    rows = snap.live if stage in scoring.INACTIVE else snap.active
    today = date.today()
    q_now = f"{today.year}-Q{(today.month - 1) // 3 + 1}"
    out = []
    for o in rows:
        s = snap.scores.get(o["id"], {})
        acts = [a for a in snap.acts if a["opp"] == o["id"] and scoring.OPEN_ACTION(a)]
        if f.get("domain") and o.get("domain") != f["domain"]:
            continue
        if f.get("country") and (o.get("country") or "").lower() != str(f["country"]).lower():
            continue
        if stage and o.get("status") != stage:
            continue
        if f.get("outlook") and o.get("outlook") != f["outlook"]:
            continue
        if f.get("sponsor") and str(f["sponsor"]).lower() not in (o.get("sponsor") or "").lower():
            continue
        if f.get("intervention") and (o.get("intervention") or "").lower() != "yes":
            continue
        if f.get("blocked") and not any(a.get("status") == "Blocked" or (a.get("escalate") or "").lower() == "yes" for a in acts):
            continue
        if f.get("at_risk") and not (s.get("p", 1) < 0.35 or o.get("outlook") == "Negative"):
            continue
        if f.get("overdue"):
            od = any(scoring.to_date(a.get("due")) and scoring.to_date(a["due"]) < today for a in acts)
            md = scoring.to_date(o.get("milestone_date"))
            if not (od or (md and md < today)):
                continue
        if f.get("this_quarter") and s.get("quarter") != q_now:
            continue
        out.append(o)
    return sorted(out, key=lambda o: -snap.scores.get(o["id"], {}).get("ev", 0))


def _fmt(v: float) -> str:
    return f"AED {v / 1e9:.2f}bn" if v >= 1e9 else f"AED {v / 1e6:.1f}m" if v >= 1e6 else f"AED {v:,.0f}"


def _describe(f: dict, ar: bool) -> str:
    parts = []
    if f.get("blocked"):
        parts.append("المتعثرة" if ar else "blocked or escalated")
    if f.get("at_risk"):
        parts.append("المعرضة للخطر" if ar else "at-risk")
    if f.get("intervention"):
        parts.append("التي تتطلب تدخلاً تنفيذياً" if ar else "requiring executive intervention")
    if f.get("overdue"):
        parts.append("المتأخرة" if ar else "with overdue items")
    if f.get("domain"):
        parts.append(f.get("domain"))
    if f.get("stage"):
        parts.append(f.get("stage"))
    if f.get("country"):
        parts.append(("في " if ar else "in ") + f["country"])
    if f.get("this_quarter"):
        parts.append("هذا الربع" if ar else "closing this quarter")
    return " ".join(parts) or ("كل الفرص النشطة" if ar else "all active")


def answer(snap: Snapshot, question: str, history: list[dict] | None = None) -> dict:
    ar = llm.is_arabic(question)
    countries = sorted({o.get("country") for o in snap.opps if o.get("country")}, key=len, reverse=True)
    kw = parse_keywords(question, countries)
    parsed = llm.chat_json([
        {"role": "system", "content": "You convert executive questions about a sales pipeline into filters. " + ontology.prompt_summary() + "\n" + SCHEMA_HINT},
        {"role": "user", "content": question},
    ], max_tokens=250)
    filters = kw
    engine = "template"
    if parsed:
        engine = "llm"
        filters = {k: v for k, v in parsed.items() if v not in (None, "", False, "null")}
        # Keep keyword hits the small model missed; a filter the user clearly said should not be dropped.
        for k, v in kw.items():
            filters.setdefault(k, v)
        # Snap model output back onto ontology terms; drop anything that is not a known term.
        for key, scheme in (("domain", "Domain"), ("stage", "Stage"), ("outlook", "Outlook"), ("country", "Country")):
            if filters.get(key):
                canon = ontology.normalise(scheme, filters[key])
                filters[key] = canon or (filters[key] if key == "country" else kw.get(key))
                if not filters[key]:
                    filters.pop(key)
    rows = apply_filters(snap, filters)
    total = sum(float(o.get("value") or 0) for o in rows)
    ev = sum(snap.scores.get(o["id"], {}).get("ev", 0) for o in rows)
    facts = [{
        "id": o["id"], "name": o["name"], "country": o.get("country"), "domain": o.get("domain"), "stage": o.get("status"),
        "value_aed": o.get("value"), "win_probability": snap.scores[o["id"]]["p"], "expected_value_aed": snap.scores[o["id"]]["ev"],
        "sponsor": o.get("sponsor"), "latest": o.get("latest"), "next_action": o.get("next_action"),
    } for o in rows[:10]]
    idx = retrieval.build_index(snap.opps, snap.engs, snap.discs)
    notes = idx.search(question + " " + " ".join(o["name"] for o in rows[:3]), k=4)
    if rows:
        ids = {o["id"] for o in rows}
        notes = [n for n in notes if n.get("opp") in ids] or notes[:2]

    summary = {"matched": len(rows), "total_value_aed": round(total), "expected_value_aed": round(ev),
               "scope": _describe(filters, False)}
    text = llm.chat([
        {"role": "system", "content": (
            "You are Precast, a strategic pipeline analyst for C-suite executives. " + ontology.prompt_summary() + " Answer ONLY from the FACTS JSON. "
            "Never invent figures. Use AED with m/bn. Be concise: 2-5 sentences, then at most 5 bullet points "
            "naming opportunities with their IDs. Mention risk-weighted expected value where relevant. "
            + ("Answer in Arabic." if ar else "Answer in English."))},
        *[{"role": m["role"], "content": m["content"][:1500]} for m in (history or [])[-4:] if m.get("role") in ("user", "assistant")],
        {"role": "user", "content": f"QUESTION: {question}\n\nFACTS: {json.dumps({'summary': summary, 'opportunities': facts, 'notes': [{'opp': n.get('opp'), 'date': n.get('date'), 'text': n['text'][:300]} for n in notes]}, default=str)}"},
    ], max_tokens=600)
    if text:
        engine = "llm"
    else:
        text = _template_answer(rows, snap, filters, total, ev, ar)
    return {"answer": text, "engine": engine, "filters": filters, "summary": summary,
            "rows": [snap.enriched(o) for o in rows[:25]], "citations": notes}


def _template_answer(rows: list[dict], snap: Snapshot, f: dict, total: float, ev: float, ar: bool) -> str:
    scope = _describe(f, ar)
    if not rows:
        return f"لا توجد فرص مطابقة ({scope})." if ar else f"No opportunities match ({scope})."
    if ar:
        head = (f"{len(rows)} فرصة ({scope}) بقيمة إجمالية {_fmt(total)}، والقيمة المتوقعة المرجحة بالمخاطر {_fmt(ev)}.")
    else:
        head = (f"{len(rows)} opportunit{'y' if len(rows) == 1 else 'ies'} ({scope}) worth {_fmt(total)} in total; "
                f"risk-weighted expected value is {_fmt(ev)} ({round(ev / total * 100) if total else 0}% of face value).")
    lines = [head, ""]
    for o in rows[:5]:
        s = snap.scores[o["id"]]
        lines.append(f"- {o['id']} {o['name']} ({o.get('country')}, {o.get('status')}): {_fmt(o.get('value') or 0)}, "
                     f"{round(s['p'] * 100)}% win probability. {o.get('latest') or ''}".strip())
    if len(rows) > 5:
        lines.append(f"- … و{len(rows) - 5} أخرى" if ar else f"- …and {len(rows) - 5} more")
    return "\n".join(lines)
