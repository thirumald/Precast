"""Turn unstructured meeting notes into a structured Engagement Log entry.

The result is a proposal shown to the user for confirmation; nothing is saved automatically.
"""
from __future__ import annotations

import difflib
import re
from datetime import date, timedelta

from . import llm
from .service import Snapshot

TYPES = ["Meeting", "Call", "Email", "Workshop", "Event", "Executive Engagement", "Site Visit"]
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _match_opp(snap: Snapshot, text: str, hint: str | None) -> tuple[str | None, float]:
    if hint and snap.opp(hint):
        return hint, 1.0
    m = re.search(r"\b(OPP-\d{3})\b", text, re.I)
    if m and snap.opp(m.group(1).upper()):
        return m.group(1).upper(), 1.0
    low = text.lower()
    best, score = None, 0.0
    for o in snap.active:
        cands = [o["name"], (o.get("counterparty") or "").replace("Example: ", ""), o.get("site") or ""]
        for c in filter(None, cands):
            if c.lower() in low:
                return o["id"], 0.95
            words = [w for w in re.findall(r"\w{4,}", c.lower())]
            hits = sum(w in low for w in words)
            r = hits / max(1, len(words))
            r = max(r, difflib.SequenceMatcher(None, c.lower(), low[:400]).ratio() * 0.6)
            if r > score:
                best, score = o["id"], r
    return (best, round(score, 2)) if score >= 0.34 else (None, round(score, 2))


def _find_date(text: str, default: date | None = None) -> str | None:
    m = re.search(r"\b(20\d\d)-(\d\d)-(\d\d)\b", text)
    if m:
        return m.group(0)
    m = re.search(r"\b(\d{1,2})\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*(20\d\d)?", text, re.I)
    if m:
        y = int(m.group(3) or date.today().year)
        try:
            return date(y, MONTHS[m.group(2).lower()[:3]], int(m.group(1))).isoformat()
        except ValueError:
            pass
    m = re.search(r"\b(?:in|within)\s+(\d+)\s*(day|week)s?", text, re.I)
    if m:
        n = int(m.group(1)) * (7 if m.group(2).lower().startswith("week") else 1)
        return (date.today() + timedelta(days=n)).isoformat()
    if re.search(r"next week", text, re.I):
        return (date.today() + timedelta(days=7)).isoformat()
    return default.isoformat() if default else None


def _heuristic(text: str) -> dict:
    lines = [l.strip(" -•*\t") for l in text.splitlines() if l.strip()]
    low = text.lower()
    typ = next((t for t in TYPES if t.lower() in low), "Call" if "call" in low else "Meeting")
    follow, owner, due, commits, ext, internal = "", "", None, [], "", ""
    for l in lines:
        ll = l.lower()
        if re.match(r"(action|follow[- ]?up|next step|todo|to do)s?\s*[:\-]", ll):
            follow = follow or re.split(r"[:\-]", l, maxsplit=1)[1].strip()
            due = due or _find_date(l)
            om = re.search(r"(?:owner|by|@)\s*[:\-]?\s*([A-Z][\w .,'-]{2,40}?)(?:\s+(?:by|due|before)\b|[,;(]|$)", l)
            owner = owner or (om.group(1).strip() if om else "")
            follow = re.sub(r"[,;]?\s*(owner|@)\s*[:\-]?\s*[^,;]+", "", follow, flags=re.I)
            follow = re.sub(r"\s+(by|before|due)\s+(\d{1,2}\s*\w{3,9}|\d{4}-\d\d-\d\d|next week|end of \w+)\b.*$", "", follow, flags=re.I).strip(" ,;")
        elif re.match(r"(commit|agreed|decision)s?\w*\s*[:\-]", ll):
            commits.append(re.split(r"[:\-]", l, maxsplit=1)[1].strip())
        elif re.match(r"(attendees|participants|with|client side|external)\s*[:\-]", ll):
            ext = ext or re.split(r"[:\-]", l, maxsplit=1)[1].strip()
        elif re.match(r"(presight|internal|our side)\s*[:\-]", ll):
            internal = re.split(r"[:\-]", l, maxsplit=1)[1].strip()
    body = [l for l in lines if not re.match(r"(action|follow|next step|todo|commit|agreed|attendees|participants|presight|internal|date)\w*\s*[:\-]", l.lower())]
    summary = " ".join(body)[:400] or text[:400]
    return {"type": typ, "date": _find_date(text, date.today()), "summary": summary, "commitments": "; ".join(commits),
            "follow_up": follow, "owner": owner, "due": due, "external": ext, "internal": internal}


def extract(snap: Snapshot, text: str, opp_hint: str | None = None) -> dict:
    opp, conf = _match_opp(snap, text, opp_hint)
    base = _heuristic(text)
    engine = "template"
    names = "; ".join(f"{o['id']} = {o['name']} ({(o.get('counterparty') or '').replace('Example: ', '')})" for o in snap.active)
    data = llm.chat_json([
        {"role": "system", "content": "Extract a CRM engagement record from meeting notes. Output JSON only with keys: "
         "opportunity_id (one of the listed IDs or null), type (" + ", ".join(TYPES) + "), date (YYYY-MM-DD or null), "
         "external_participants, presight_participants, summary (max 2 sentences, English), commitments, follow_up_action, "
         f"action_owner, due_date (YYYY-MM-DD or null). Today is {date.today().isoformat()}. Opportunities: {names}"},
        {"role": "user", "content": text[:6000]},
    ], max_tokens=500)
    if data:
        engine = "llm"
        mapping = {"type": "type", "date": "date", "external_participants": "external", "presight_participants": "internal",
                   "summary": "summary", "commitments": "commitments", "follow_up_action": "follow_up",
                   "action_owner": "owner", "due_date": "due"}
        for src, dst in mapping.items():
            v = data.get(src)
            if isinstance(v, list):
                v = ", ".join(map(str, v))
            if v and str(v).lower() != "null":
                base[dst] = str(v)
        cand = data.get("opportunity_id")
        if cand and snap.opp(str(cand)) and (not opp or conf < 0.9):
            opp, conf = str(cand), max(conf, 0.7)
    if base.get("type") not in TYPES:
        base["type"] = "Meeting"
    for k in ("date", "due"):
        if base.get(k) and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(base[k])):
            base[k] = _find_date(str(base[k]))
    return {"engagement": {**base, "opp": opp}, "match_confidence": conf, "engine": engine,
            "opportunity": snap.enriched(snap.opp(opp)) if opp else None}
