"""Generative drafting: intervention briefings, sponsor follow-up emails and press-release drafts.

Every draft is marked as a draft for human review. Press releases are never presented as
cleared for publication unless Legal, IR and the counterparty have all approved.
"""
from __future__ import annotations

import json
from datetime import date

from . import db, llm, scoring
from .service import Snapshot


def _fmt(v: float) -> str:
    v = float(v or 0)
    return f"AED {v / 1e9:.2f}bn" if v >= 1e9 else f"AED {v / 1e6:.0f}m" if v >= 1e6 else f"AED {v:,.0f}"


def _context(snap: Snapshot, oid: str) -> dict:
    o = snap.opp(oid)
    if not o:
        raise KeyError(oid)
    s = snap.scores.get(oid, {})
    acts = [a for a in snap.acts if a["opp"] == oid and scoring.OPEN_ACTION(a)]
    engs = sorted([e for e in snap.engs if e["opp"] == oid], key=lambda e: e.get("date") or "", reverse=True)[:5]
    discs = sorted([d for d in snap.discs if d["opp"] == oid], key=lambda d: d.get("created") or "", reverse=True)[:6]
    return {"o": o, "s": s, "acts": acts, "engs": engs, "discs": discs,
            "blockers": [a for a in acts if a.get("status") == "Blocked" or (a.get("escalate") or "").lower() == "yes"]}


def intervention(snap: Snapshot, oid: str, kind: str = "memo", lang: str = "en") -> dict:
    c = _context(snap, oid)
    o, s = c["o"], c["s"]
    facts = {
        "opportunity": {k: o.get(k) for k in ("id", "name", "counterparty", "country", "domain", "status", "outlook",
                                               "value", "sponsor", "owner", "latest", "rationale", "next_action",
                                               "milestone", "milestone_date")},
        "win_probability": s.get("p"), "change_14d": s.get("delta_14d"), "expected_value": s.get("ev"),
        "score_drivers": [f["label"] + ": " + f["detail"] for f in s.get("factors", []) if f["impact"] < 0][:5],
        "blocked_or_escalated_actions": [{k: a.get(k) for k in ("id", "title", "owner", "due", "status", "blocker")} for a in c["blockers"]],
        "recent_engagements": [{k: e.get(k) for k in ("date", "type", "summary", "follow_up")} for e in c["engs"]],
        "internal_discussion": [{"author": d.get("author"), "date": (d.get("created") or "")[:10], "text": (d.get("body") or "")[:300]} for d in c["discs"]],
    }
    fmt = ("a one-page briefing memo with headings: Situation, Blocker, Counterparty history, Recommended intervention, "
           "Ask of the sponsor, Risk if no action" if kind == "memo" else
           "a short follow-up email from the executional owner to the executive sponsor with a subject line")
    prompt = [
        {"role": "system", "content": "You draft concise, factual executive communications for a technology company's "
         "C-suite. Use ONLY the facts provided. Do not invent names, numbers or commitments. Plain professional tone. "
         + ("Write in Arabic." if lang == "ar" else "Write in British English.")},
        {"role": "user", "content": f"Write {fmt}.\nFACTS:\n{json.dumps(facts, default=str, ensure_ascii=False)}"},
    ]
    text = llm.chat(prompt, temperature=0.3, max_tokens=900)
    engine = "llm" if text else "template"
    if not text:
        text = _memo_template(c) if kind == "memo" else _email_template(c)
    db.log_ai(f"intervention_{kind}", oid, json.dumps(facts, default=str), text, engine)
    return {"draft": text, "engine": engine, "kind": kind, "opp": oid, "status": "Draft for review"}


def _memo_template(c: dict) -> str:
    o, s = c["o"], c["s"]
    blk = c["blockers"]
    drivers = [f for f in s.get("factors", []) if f["impact"] < 0]
    hist = "\n".join(f"- {e['date']} ({e.get('type')}): {e.get('summary')}" for e in c["engs"][:4]) or "- No engagements logged."
    blockers = "\n".join(f"- {a['id']} {a['title']} (owner {a.get('owner')}, due {a.get('due')}, {a.get('status')})"
                         + (f": {a['blocker']}" if a.get("blocker") else "") for a in blk) or "- No action is formally blocked; see score drivers."
    delta = s.get("delta_14d")
    trend = f", {'+' if delta and delta > 0 else ''}{round((delta or 0) * 100)} pts in 14 days" if delta is not None else ""
    return f"""INTERVENTION BRIEFING (DRAFT FOR REVIEW)
To: {o.get('sponsor') or 'Executive Sponsor'}
From: {o.get('owner') or 'Executional Owner'}
Re: {o['id']} {o['name']} ({o.get('counterparty')})
Date: {date.today().isoformat()}

SITUATION
{o.get('status')} stage, {o.get('country')}, {o.get('domain')}. Estimated value {_fmt(o.get('value'))}; Precast win probability {round(s.get('p', 0) * 100)}%{trend}; risk-weighted expected value {_fmt(s.get('ev'))}.
Latest: {o.get('latest') or 'n/a'}

BLOCKER
{blockers}

WHAT IS PULLING THE PROBABILITY DOWN
{chr(10).join('- ' + f['label'] + ': ' + f['detail'] for f in drivers[:4]) or '- No material negative drivers.'}

COUNTERPARTY HISTORY
{hist}

INTERNAL DISCUSSION (latest)
{chr(10).join('- ' + (d.get('created') or '')[:10] + ' ' + (d.get('author') or '') + ': ' + (d.get('body') or '')[:200] for d in c['discs'][:3]) or '- None recorded.'}

RECOMMENDED INTERVENTION
{o.get('next_action') or 'Sponsor-level call with the counterparty decision-maker to unblock the open items above.'}

ASK OF THE SPONSOR
- Confirm availability for a sponsor-to-counterparty call within 7 days.
- Decide on the commercial or structural flexibility the team may offer.

RISK IF NO ACTION
Milestone "{o.get('milestone') or 'next milestone'}" ({o.get('milestone_date') or 'undated'}) is at risk, with {_fmt(o.get('value'))} of pipeline exposed.
"""


def _email_template(c: dict) -> str:
    o, s = c["o"], c["s"]
    blk = c["blockers"][0] if c["blockers"] else None
    return f"""Subject: {o['id']} {o['name']}: sponsor support needed

Dear {o.get('sponsor') or 'Sponsor'},

{o['name']} with {o.get('counterparty')} is at {o.get('status')} stage ({_fmt(o.get('value'))}). Precast currently puts the win probability at {round(s.get('p', 0) * 100)}%.

{('The main blocker is "' + blk['title'] + '"' + (' – ' + blk['blocker'] if blk.get('blocker') else '') + '.') if blk else 'Latest: ' + (o.get('latest') or '')}

Proposed next step: {o.get('next_action') or 'a sponsor-level call with the counterparty'}. Could we find 20 minutes this week to agree the approach?

Kind regards,
{o.get('owner') or ''}

[Draft generated by Precast for review before sending]
"""


def press_release(snap: Snapshot, aid: str, lang: str = "en") -> dict:
    a = next((x for x in snap.anns if x["id"] == aid), None)
    if not a:
        raise KeyError(aid)
    o = snap.opp(a.get("opp")) or {}
    approvals = {"legal": a.get("legal"), "ir": a.get("ir"), "counterparty": a.get("counterparty")}
    cleared = all((v or "").lower() in ("approved", "not required") for v in approvals.values())
    pending = [k for k, v in approvals.items() if (v or "").lower() not in ("approved", "not required")]
    facts = {"announcement": {k: a.get(k) for k in ("title", "type", "target", "event")},
             "opportunity": {k: o.get(k) for k in ("name", "counterparty", "country", "domain", "type", "latest")}}
    text = llm.chat([
        {"role": "system", "content": "You write press-release drafts for Presight, an applied AI company. Use ONLY the facts. "
         "Do NOT state contract values unless given as public. Use [PLACEHOLDER] for quotes and details not provided. "
         + ("Write in Arabic." if lang == "ar" else "Write in British English.")},
        {"role": "user", "content": "Draft a press release: headline, dateline, 3 short paragraphs, a [QUOTE: executive] "
         f"placeholder, a [QUOTE: counterparty] placeholder and a boilerplate placeholder.\nFACTS: {json.dumps(facts, default=str, ensure_ascii=False)}"},
    ], temperature=0.4, max_tokens=800)
    engine = "llm" if text else "template"
    if not text:
        cp = (o.get("counterparty") or "the counterparty").replace("Example: ", "")
        text = f"""{a.get('title')}

[CITY], [DATE] – Presight, the applied AI company, today announced {(a.get('type') or 'an agreement').lower()} with {cp} for {o.get('name', '').lower() or 'a strategic programme'} in {o.get('country') or '[COUNTRY]'}.

The programme will apply Presight's {(o.get('domain') or 'AI').lower()} analytics capabilities to [SCOPE SUMMARY – confirm with delivery lead]. {o.get('latest') or ''}

[QUOTE: Presight executive]

[QUOTE: {cp} representative]

Further details will be shared at {a.get('event') or '[EVENT / PLATFORM]'}.

About Presight
[BOILERPLATE]
"""
    banner = ("CLEARED: Legal, IR and counterparty approvals recorded. Final proof-read still required."
              if cleared else f"NOT CLEARED FOR RELEASE: awaiting {', '.join(pending)} approval. A draft is not clearance to publish.")
    db.log_ai("press_release", aid, json.dumps(facts, default=str), text, engine)
    return {"draft": text, "engine": engine, "cleared": cleared, "pending": pending, "banner": banner, "announcement": aid}
