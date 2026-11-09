"""Predictive deal scoring and forecasting.

The model is a transparent logistic score: a stage base rate, calibrated against the
historical win/loss ratio of each domain, adjusted by engagement momentum, sentiment
of the Engagement Log, execution health (overdue / blocked actions) and the recorded
outlook. Every adjustment is returned as a named factor so an executive can see *why*
a probability moved. No black box, and it works from the first day with little history.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

STAGES = ["Exploratory", "Active Engagement", "Proposal", "Negotiation", "Agreement", "Execution"]
INACTIVE = ["Closed Won", "Closed Lost", "On Hold"]
OPEN_ACTION = lambda a: (a.get("status") or "") not in ("Completed", "Cancelled", "Done")  # noqa: E731

# Prior probability of eventually closing won, by current stage.
STAGE_BASE = {
    "Exploratory": 0.10, "Active Engagement": 0.20, "Proposal": 0.35, "Negotiation": 0.55,
    "Agreement": 0.80, "Execution": 0.95, "On Hold": 0.05,
}
# Typical days remaining to contract signature from each stage.
STAGE_DAYS = {"Exploratory": 240, "Active Engagement": 180, "Proposal": 120, "Negotiation": 60, "Agreement": 21, "Execution": 0}
OUTLOOK_W = {"Positive": 0.5, "Neutral": 0.0, "Negative": -0.7}

POS_WORDS = set("""agreed agree positive strong support supportive impressed keen confirmed exceeded praised accepted
approve approved progress constructive happy interest interested aligned alignment ahead stable well success
successful resolved quickly preference commit committed secured endorse endorsed
موافقة إيجابي دعم ممتاز نجاح تقدم""".split())
NEG_WORDS = set("""delay delayed concern concerns risk competing competitor pressure questioned slow stalled stalling
tense blocked reject rejected lost issue issues gap gaps uncertain reprioritising reprioritizing cut decline declined
dispute objection escalate escalation postpone postponed
تأخير مخاوف مخاطر رفض منافس مشكلة""".split())


def to_date(v: Any) -> date | None:
    if not v:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def sentiment(text: str) -> float:
    """Lexicon sentiment in [-1, 1]. Bilingual word lists; cheap and explainable."""
    words = re.findall(r"[\w؀-ۿ]+", (text or "").lower())
    if not words:
        return 0.0
    pos = sum(w in POS_WORDS for w in words)
    neg = sum(w in NEG_WORDS for w in words)
    if pos == neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def potential_band(v: float) -> int:
    m = (v or 0) / 1e6
    return 5 if m >= 250 else 4 if m >= 100 else 3 if m >= 25 else 2 if m >= 5 else 1


def logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


@dataclass
class Calibration:
    global_rate: float
    domain_rate: dict[str, float]
    domain_n: dict[str, tuple[int, int]]

    def as_dict(self) -> dict:
        return {
            "global_win_rate": round(self.global_rate, 3),
            "domains": [
                {"domain": d, "won": self.domain_n.get(d, (0, 0))[0], "lost": self.domain_n.get(d, (0, 0))[1],
                 "win_rate": round(r, 3)}
                for d, r in sorted(self.domain_rate.items())
            ],
        }


def calibrate(opps: list[dict]) -> Calibration:
    won = [o for o in opps if o.get("status") == "Closed Won"]
    lost = [o for o in opps if o.get("status") == "Closed Lost"]
    total = len(won) + len(lost)
    g = (len(won) + 1) / (total + 2) if total else 0.5
    rates, ns = {}, {}
    # Beta prior centred on the global rate, worth 4 deals: shrinks small samples toward the mean.
    k = 4
    for d in {o.get("domain") for o in opps if o.get("domain")}:
        w = sum(o.get("domain") == d for o in won)
        l = sum(o.get("domain") == d for o in lost)
        rates[d] = (w + k * g) / (w + l + k)
        ns[d] = (w, l)
    return Calibration(g, rates, ns)


def _quarter(d: date) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def score(o: dict, engs: list[dict], acts: list[dict], cal: Calibration, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    status = o.get("status") or ""
    value = float(o.get("value") or 0)
    if status == "Closed Won":
        return _result(o, 1.0, [], value, as_of, closed=True)
    if status == "Closed Lost":
        return _result(o, 0.0, [], value, as_of, closed=True)

    base = STAGE_BASE.get(status, 0.15)
    x = logit(base)
    factors: list[dict] = [{"key": "stage", "label": f"Stage base rate ({status or 'unstaged'})", "impact": 0.0,
                            "detail": f"{round(base * 100)}% of deals at this stage historically close"}]

    def add(key: str, label: str, impact: float, detail: str) -> None:
        nonlocal x
        if abs(impact) < 1e-6:
            return
        x += impact
        factors.append({"key": key, "label": label, "impact": round(impact, 3), "detail": detail})

    dom = o.get("domain")
    if dom in cal.domain_rate:
        adj = 0.8 * (logit(cal.domain_rate[dom]) - logit(cal.global_rate))
        w, l = cal.domain_n.get(dom, (0, 0))
        add("domain", f"{dom} win/loss history", adj,
            f"{w} won, {l} lost; win rate {round(cal.domain_rate[dom] * 100)}% vs {round(cal.global_rate * 100)}% overall")

    add("outlook", f"Outlook: {o.get('outlook') or 'not set'}", OUTLOOK_W.get(o.get("outlook") or "", 0.0),
        o.get("rationale") or "Owner's recorded outlook")

    past = [e for e in engs if (to_date(e.get("date")) or date.min) <= as_of]
    recent = [e for e in past if (as_of - to_date(e["date"])).days <= 60]
    n = len(recent)
    freq = -0.55 if n == 0 else 0.0 if n == 1 else 0.25 if n <= 3 else 0.4
    add("frequency", "Engagement frequency", freq, f"{n} engagement{'s' if n != 1 else ''} in the last 60 days")

    if past:
        last = max(to_date(e["date"]) for e in past)
        gap = (as_of - last).days
        if gap > 45:
            add("recency", "Engagement gone quiet", -0.45 if gap > 60 else -0.25, f"Last contact {gap} days ago")
        elif gap <= 10:
            add("recency", "Recent contact", 0.15, f"Last contact {gap} days ago")
        # Recency-weighted sentiment: newer notes count more.
        ws = [(math.exp(-(as_of - to_date(e["date"])).days / 30), sentiment(e.get("summary", "") + " " + (e.get("commitments") or "")))
              for e in past[-8:]]
        tw = sum(w for w, _ in ws)
        s = sum(w * v for w, v in ws) / tw if tw else 0
        if abs(s) > 0.05:
            add("sentiment", "Engagement Log sentiment", round(0.6 * s, 3),
                f"{'Positive' if s > 0 else 'Negative'} tone in recent notes ({s:+.2f})")
    else:
        add("recency", "No engagement logged", -0.3, "No contact recorded yet")

    live = [a for a in acts if (to_date(a.get("created")) or date.min) <= as_of]
    open_a = [a for a in live if OPEN_ACTION(a)]
    overdue = [a for a in open_a if to_date(a.get("due")) and to_date(a["due"]) < as_of]
    blocked = [a for a in open_a if (a.get("status") or "") == "Blocked"]
    if overdue:
        add("overdue", "Overdue actions", -min(0.5, 0.2 * len(overdue)),
            f"{len(overdue)} open action{'s' if len(overdue) > 1 else ''} past due")
    if blocked:
        add("blocked", "Blocked actions", -0.4, "; ".join(a.get("blocker") or a.get("title", "") for a in blocked)[:160])
    md = to_date(o.get("milestone_date"))
    if md and md < as_of and status not in ("Execution",):
        add("milestone", "Milestone slipped", -0.25, f"{o.get('milestone') or 'Milestone'} was due {md.isoformat()}")
    comp = int(o.get("competitors") or 0)
    if comp >= 3:
        add("competition", "Competitive field", -0.1 * (comp - 2), f"{comp} competitors identified")
    ver = to_date(o.get("verified"))
    if not ver or (as_of - ver).days > 30:
        add("stale", "Record not verified", -0.1, "Not verified in 30+ days; treat with caution")

    floor = logit(base) - 2.2
    if x < floor:
        factors.append({"key": "floor", "label": "Penalty cap", "impact": round(floor - x, 3),
                        "detail": "Combined negative signals capped so a deal is never written off by the model alone"})
        x = floor
    return _result(o, sigmoid(x), factors, value, as_of, open_actions=len(open_a), overdue=len(overdue), blocked=len(blocked))


def _result(o: dict, p: float, factors: list[dict], value: float, as_of: date, closed: bool = False, **extra) -> dict:
    status = o.get("status") or ""
    ev = value * p
    if closed:
        close = to_date(o.get("closed")) or as_of
    elif status == "Execution":
        close = as_of
    else:
        days = STAGE_DAYS.get(status, 180)
        # Weaker deals take longer: stretch the timeline up to 1.8x as probability falls.
        days = int(days * (1 + max(0.0, 0.6 - p) * 1.3))
        if status == "On Hold":
            days = 365
        close = as_of + timedelta(days=days)
    return {
        "id": o["id"], "p": round(p, 4), "ev": round(ev, 2), "value": value,
        "potential_manual": int(o.get("commercial") or 0), "potential_dynamic": potential_band(ev) if not closed else potential_band(value),
        "expected_close": close.isoformat(), "quarter": _quarter(close),
        "risk": "high" if p < 0.3 else "medium" if p < 0.6 else "low",
        "factors": factors, **extra,
    }


def score_portfolio(opps: list[dict], engs: list[dict], acts: list[dict], as_of: date | None = None,
                    with_trend: bool = True) -> dict[str, dict]:
    as_of = as_of or date.today()
    cal = calibrate(opps)
    by_e: dict[str, list] = {}
    by_a: dict[str, list] = {}
    for e in sorted(engs, key=lambda e: e.get("date") or ""):
        by_e.setdefault(e.get("opp"), []).append(e)
    for a in acts:
        by_a.setdefault(a.get("opp"), []).append(a)
    out = {}
    for o in opps:
        if o["id"].startswith("HIS-"):
            continue
        e, a = by_e.get(o["id"], []), by_a.get(o["id"], [])
        s = score(o, e, a, cal, as_of)
        if with_trend and o.get("status") not in INACTIVE:
            trend = [round(score(o, e, a, cal, as_of - timedelta(days=7 * w))["p"], 4) for w in range(8, -1, -1)]
            s["trend"] = trend
            prev = trend[-3]  # two weeks ago
            s["delta_14d"] = round(s["p"] - prev, 4)
            # Momentum projection one week ahead, damped.
            nxt = min(0.99, max(0.01, s["p"] + 0.5 * s["delta_14d"]))
            s["p_next"] = round(nxt, 4)
            s["potential_next"] = potential_band(s["value"] * nxt)
            s["direction"] = "up" if s["delta_14d"] > 0.02 else "down" if s["delta_14d"] < -0.02 else "flat"
        out[o["id"]] = s
    return out


def forecast(opps: list[dict], scores: dict[str, dict], quarters: int = 4, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    qs = []
    d = date(as_of.year, (as_of.month - 1) // 3 * 3 + 1, 1)
    for _ in range(quarters):
        qs.append(_quarter(d))
        m = d.month + 3
        d = date(d.year + (m > 12), (m - 1) % 12 + 1, 1)
    buckets = {q: {"quarter": q, "commit": 0.0, "best_case": 0.0, "pipeline": 0.0, "weighted": 0.0, "count": 0} for q in qs}
    later = {"quarter": "Later", "commit": 0.0, "best_case": 0.0, "pipeline": 0.0, "weighted": 0.0, "count": 0}
    for o in opps:
        s = scores.get(o["id"])
        if not s or o.get("status") in INACTIVE or o.get("status") == "Execution":
            continue
        b = buckets.get(s["quarter"], later)
        tier = "commit" if s["p"] >= 0.7 else "best_case" if s["p"] >= 0.4 else "pipeline"
        b[tier] += s["value"]
        b["weighted"] += s["ev"]
        b["count"] += 1
    rows = list(buckets.values()) + ([later] if later["count"] else [])
    for r in rows:
        for k in ("commit", "best_case", "pipeline", "weighted"):
            r[k] = round(r[k], 2)
    return {"quarters": rows, "as_of": as_of.isoformat()}
