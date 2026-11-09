"""Executive KPIs and management reports.

Every number is computed live from the register, filtered by domain / region / country /
segment / sponsor. Trends are reconstructed by re-running the scoring model as of each of
the last eight weeks. Reports are returned as typed sections (kpis, chart, table, text) so
one renderer draws them on screen, in print and in Excel.
"""
from __future__ import annotations

import io
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any, Callable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import db, llm, ontology, scoring
from .service import Snapshot

# ------------------------------------------------------------------ targets
DEFAULT_TARGETS: dict[str, float] = {
    "weighted_pipeline": 1.2e9,      # AED, risk-weighted value of the open pipeline
    "annual_bookings": 8e8,          # AED, used for coverage ratio
    "coverage": 3.0,                 # x, open pipeline due in next 4 quarters ÷ annual bookings target
    "quarter_forecast": 1.5e8,       # AED, weighted forecast for the current quarter
    "win_rate": 0.5,
    "avg_p": 0.5,
    "at_risk_value": 4e8,            # AED, lower is better
    "interventions": 3,              # count, lower is better
    "action_on_time": 0.85,
    "engagement_coverage": 0.8,
    "freshness": 0.9,
    "cycle_days": 240,               # lower is better
    "announcement_readiness": 0.6,
    "velocity": 1.5e6,               # AED per day
}


def targets() -> dict[str, float]:
    t = dict(DEFAULT_TARGETS)
    try:
        t.update({k: float(v) for k, v in json.loads(db.get_setting("kpi.targets", "{}") or "{}").items() if k in t})
    except (ValueError, TypeError):
        pass
    return t


def save_targets(values: dict[str, Any]) -> dict[str, float]:
    cur = targets()
    for k, v in values.items():
        if k in DEFAULT_TARGETS and v not in (None, ""):
            cur[k] = float(v)
    db.set_setting("kpi.targets", json.dumps(cur))
    return cur


# ------------------------------------------------------------------ filtering
FILTER_KEYS = ("domain", "region", "country", "segment", "sponsor")


def _match(o: dict, f: dict) -> bool:
    if f.get("domain") and o.get("domain") != f["domain"]:
        return False
    if f.get("country") and o.get("country") != f["country"]:
        return False
    if f.get("region") and ontology.region_of(o.get("country")) != f["region"]:
        return False
    if f.get("segment") and o.get("segment") != f["segment"]:
        return False
    if f.get("sponsor") and o.get("sponsor") != f["sponsor"]:
        return False
    return True


class View:
    """A filtered slice of the snapshot."""

    def __init__(self, snap: Snapshot, f: dict):
        self.snap, self.f = snap, {k: v for k, v in f.items() if k in FILTER_KEYS and v}
        self.all = [o for o in snap.opps if _match(o, self.f)]           # includes historical, for win/loss
        self.live = [o for o in self.all if not o["id"].startswith("HIS-")]
        self.active = [o for o in self.live if o.get("status") not in scoring.INACTIVE]
        ids = {o["id"] for o in self.all}
        self.acts = [a for a in snap.acts if a["opp"] in ids]
        self.engs = [e for e in snap.engs if e["opp"] in ids]
        self.anns = [a for a in snap.anns if a["opp"] in ids]
        self.sc = snap.scores
        self.today = date.today()

    def s(self, o: dict) -> dict:
        return self.sc.get(o["id"], {})

    def closed(self, days: int = 365) -> tuple[list[dict], list[dict]]:
        cut = self.today - timedelta(days=days)
        rows = [o for o in self.all if o.get("status") in ("Closed Won", "Closed Lost")
                and (scoring.to_date(o.get("closed")) or self.today) >= cut]
        return [o for o in rows if o["status"] == "Closed Won"], [o for o in rows if o["status"] == "Closed Lost"]

    def filter_label(self) -> str:
        return " · ".join(f"{k.title()}: {v}" for k, v in self.f.items()) or "All domains, regions and sponsors"


def _quarter(d: date) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def _sum(rows, fn) -> float:
    return float(sum(fn(r) for r in rows))


def _fmt(v: float) -> str:
    v = float(v or 0)
    return f"AED {v / 1e9:.2f}bn" if abs(v) >= 1e9 else f"AED {v / 1e6:.1f}m" if abs(v) >= 1e6 else f"AED {v:,.0f}"


# ------------------------------------------------------------------ KPI engine
def _rag(value: float, target: float, higher_better: bool) -> str:
    if target in (None, 0) and higher_better:
        return "green"
    if higher_better:
        return "green" if value >= target else "amber" if value >= 0.85 * target else "red"
    return "green" if value <= target else "amber" if value <= 1.2 * target else "red"


def _metrics(v: View, as_of: date, scores: dict[str, dict]) -> dict[str, float]:
    """KPI values for one point in time (used for current value and trend points)."""
    act = [o for o in v.active if (scoring.to_date(o.get("created")) or date.min) <= as_of]
    s = lambda o: scores.get(o["id"], {})  # noqa: E731
    pipe = _sum(act, lambda o: o.get("value") or 0)
    ev = _sum(act, lambda o: s(o).get("ev", 0))
    at_risk = _sum([o for o in act if s(o).get("p", 1) < 0.3], lambda o: (o.get("value") or 0) * (1 - s(o).get("p", 0)))
    engaged = {e["opp"] for e in v.engs if (scoring.to_date(e.get("date")) or date.min) <= as_of
               and (as_of - scoring.to_date(e["date"])).days <= 30}
    acts_due = [a for a in v.acts if scoring.to_date(a.get("due")) and scoring.to_date(a["due"]) <= as_of
                and (scoring.to_date(a.get("created")) or date.min) <= as_of]
    on_time = [a for a in acts_due if a.get("status") in ("Completed", "Done")]
    return {
        "pipeline": pipe, "weighted_pipeline": ev,
        "avg_p": (_sum(act, lambda o: s(o).get("p", 0)) / len(act)) if act else 0,
        "at_risk_value": at_risk,
        "engagement_coverage": len([o for o in act if o["id"] in engaged]) / len(act) if act else 0,
        "action_on_time": (len(on_time) / len(acts_due)) if acts_due else 0.0,
        "deals": len(act),
    }


def kpis(snap: Snapshot, f: dict) -> dict:
    v = View(snap, f)
    t = targets()
    today = v.today
    weeks = [today - timedelta(days=7 * w) for w in range(7, -1, -1)]
    series: dict[str, list[float]] = defaultdict(list)
    for d in weeks:
        sc = v.sc if d == today else scoring.score_portfolio(snap.opps, snap.engs, snap.acts, d, with_trend=False)
        for k, val in _metrics(v, d, sc).items():
            series[k].append(round(val, 4))
    now = {k: s[-1] for k, s in series.items()}

    won, lost = v.closed(365)
    win_rate = len(won) / (len(won) + len(lost)) if (won or lost) else 0
    cycles = [(scoring.to_date(o.get("closed")) - scoring.to_date(o.get("created"))).days for o in won
              if scoring.to_date(o.get("closed")) and scoring.to_date(o.get("created"))]
    cycle = sum(cycles) / len(cycles) if cycles else 0
    q_now = _quarter(today)
    fc = scoring.forecast(v.live, v.sc, 4)["quarters"]
    q_row = next((q for q in fc if q["quarter"] == q_now), {"weighted": 0, "commit": 0})
    next4 = _sum(fc[:4], lambda q: q["commit"] + q["best_case"] + q["pipeline"])
    coverage = next4 / t["annual_bookings"] if t["annual_bookings"] else 0
    inter = [o for o in v.active if (o.get("intervention") or "").lower() == "yes"]
    fresh = [o for o in v.active if scoring.to_date(o.get("verified")) and (today - scoring.to_date(o["verified"])).days <= 30]
    upcoming = [a for a in v.anns if a.get("readiness") not in ("Announced", "Cancelled")
                and scoring.to_date(a.get("target")) and 0 <= (scoring.to_date(a["target"]) - today).days <= 90]
    ready = [a for a in upcoming if all((a.get(k) or "").lower() in ("approved", "not required") for k in ("legal", "ir", "counterparty"))]
    avg_deal = now["pipeline"] / now["deals"] if now["deals"] else 0
    velocity = (now["deals"] * avg_deal * win_rate / cycle) if cycle else 0

    def k(key, label, value, unit, higher=True, target_key=None, trend=None, desc="", report=None, fmt=None):
        tk = target_key or key
        tgt = t.get(tk)
        tr = trend or []
        base = tr[-5] if len(tr) >= 5 else None
        return {"key": key, "label": label, "value": round(value, 4), "unit": unit, "target": tgt, "higher_better": higher,
                "status": _rag(value, tgt, higher) if tgt is not None else "neutral", "trend": tr,
                "delta_4w": round(value - base, 4) if base is not None else None, "description": desc, "report": report}

    items = [
        k("weighted_pipeline", "Risk-weighted pipeline", now["weighted_pipeline"], "aed", trend=series["weighted_pipeline"],
          desc="Σ value × win probability across active opportunities", report="pipeline-health"),
        k("pipeline", "Total pipeline (face value)", now["pipeline"], "aed", target_key="__none", trend=series["pipeline"],
          desc="Σ estimated value of active opportunities", report="pipeline-health"),
        k("coverage", "Pipeline coverage", coverage, "x", desc="Open value expected to close in the next 4 quarters ÷ annual bookings target",
          report="forecast"),
        k("quarter_forecast", f"Forecast {q_now} (weighted)", q_row["weighted"], "aed",
          desc=f"Risk-weighted value expected to close in {q_now}; commit {_fmt(q_row['commit'])}", report="forecast"),
        k("win_rate", "Win rate (12 months)", win_rate, "pct", desc=f"{len(won)} won, {len(lost)} lost in the last 12 months", report="win-loss"),
        k("avg_p", "Average win probability", now["avg_p"], "pct", trend=series["avg_p"], desc="Mean model probability of active deals",
          report="forecast"),
        k("at_risk_value", "Value at risk", now["at_risk_value"], "aed", higher=False, trend=series["at_risk_value"],
          desc="Σ value × (1 − p) for deals below 30% probability", report="risk"),
        k("interventions", "Executive interventions open", len(inter), "count", higher=False,
          desc=f"{_fmt(_sum(inter, lambda o: o.get('value') or 0))} of pipeline flagged for intervention", report="risk"),
        k("action_on_time", "Actions completed on time", now["action_on_time"], "pct", trend=series["action_on_time"],
          desc="Share of actions due to date that are completed", report="risk"),
        k("engagement_coverage", "Engagement coverage (30 days)", now["engagement_coverage"], "pct", trend=series["engagement_coverage"],
          desc="Active opportunities with a logged engagement in the last 30 days", report="engagement"),
        k("freshness", "Data freshness", len(fresh) / len(v.active) if v.active else 0, "pct",
          desc="Active records verified within 30 days", report="pipeline-health"),
        k("cycle_days", "Average sales cycle", cycle, "days", higher=False, desc="Days from creation to Closed Won, last 12 months",
          report="win-loss"),
        k("velocity", "Pipeline velocity", velocity, "aed_day", desc="Deals × average size × win rate ÷ cycle length", report="forecast"),
        k("announcement_readiness", "Announcement readiness (90 days)", len(ready) / len(upcoming) if upcoming else 1.0, "pct",
          desc=f"{len(ready)} of {len(upcoming)} upcoming announcements fully cleared", report="announcements"),
    ]
    for it in items:
        if it["target"] is None or it["key"] == "pipeline":
            it["target"], it["status"] = None, "neutral"
    counts = Counter(i["status"] for i in items)
    return {"as_of": today.isoformat(), "filters": v.f, "scope": v.filter_label(), "weeks": [d.isoformat() for d in weeks],
            "kpis": items, "summary": {"green": counts["green"], "amber": counts["amber"], "red": counts["red"]},
            "headline": {"active": len(v.active), "pipeline": now["pipeline"], "ev": now["weighted_pipeline"],
                         "won_value": _sum(won, lambda o: o.get("value") or 0), "forecast_quarter": q_now,
                         "forecast_weighted": q_row["weighted"], "forecast_commit": q_row["commit"]}}


# ------------------------------------------------------------------ report sections
def _table(title: str, columns: list[tuple[str, str, str]], rows: list[dict], note: str = "") -> dict:
    """columns: (key, label, type) with type in text|aed|pct|int|date|days|x."""
    return {"kind": "table", "title": title, "columns": [{"key": k, "label": l, "type": t} for k, l, t in columns],
            "rows": rows, "note": note}


def _bars(title: str, items: list[dict], value: str = "value", second: str | None = None, unit: str = "aed", note: str = "") -> dict:
    return {"kind": "bars", "title": title, "items": items, "value": value, "second": second, "unit": unit, "note": note}


def _kpis(items: list[dict]) -> dict:
    return {"kind": "kpis", "items": items}


def _text(title: str, body: str, engine: str = "template") -> dict:
    return {"kind": "text", "title": title, "body": body, "engine": engine}


def _opp_row(v: View, o: dict) -> dict:
    s = v.s(o)
    return {"id": o["id"], "name": o["name"], "country": o.get("country"), "domain": o.get("domain"), "stage": o.get("status"),
            "sponsor": o.get("sponsor"), "value": o.get("value") or 0, "p": s.get("p", 0), "ev": s.get("ev", 0),
            "delta": s.get("delta_14d"), "close": s.get("expected_close"), "quarter": s.get("quarter"),
            "outlook": o.get("outlook"), "milestone": o.get("milestone"), "milestone_date": o.get("milestone_date")}


OPP_COLS = [("id", "ID", "text"), ("name", "Opportunity", "text"), ("country", "Country", "text"), ("stage", "Stage", "text"),
            ("value", "Value", "aed"), ("p", "Win prob.", "pct"), ("ev", "Expected value", "aed")]


def _group(v: View, key: Callable[[dict], str | None], rows: list[dict] | None = None) -> list[dict]:
    g: dict[str, list[dict]] = defaultdict(list)
    for o in rows if rows is not None else v.active:
        g[key(o) or "—"].append(o)
    out = []
    for name, rs in g.items():
        val = _sum(rs, lambda o: o.get("value") or 0)
        ev = _sum(rs, lambda o: v.s(o).get("ev", 0))
        out.append({"label": name, "count": len(rs), "value": val, "ev": ev, "p": (ev / val) if val else 0,
                    "at_risk": _sum([o for o in rs if v.s(o).get("p", 1) < 0.3], lambda o: (o.get("value") or 0))})
    return sorted(out, key=lambda r: -r["value"])


def _forecast_section(v: View, quarters: int = 6) -> tuple[dict, dict]:
    fc = scoring.forecast(v.live, v.sc, quarters)["quarters"]
    t = targets()
    rows = [{**q, "total": q["commit"] + q["best_case"] + q["pipeline"], "target": t["quarter_forecast"] if q["quarter"] != "Later" else None,
             "attain": (q["weighted"] / t["quarter_forecast"]) if q["quarter"] != "Later" and t["quarter_forecast"] else None} for q in fc]
    chart = {"kind": "stack", "title": "Quarterly forecast", "items": rows, "series": [
        {"key": "commit", "label": "Commit (p ≥ 70%)"}, {"key": "best_case", "label": "Best case (40–70%)"},
        {"key": "pipeline", "label": "Pipeline (< 40%)"}], "line": "weighted", "line_label": "Risk-weighted",
        "target": t["quarter_forecast"]}
    table = _table("Forecast by quarter", [("quarter", "Quarter", "text"), ("commit", "Commit", "aed"), ("best_case", "Best case", "aed"),
                                           ("pipeline", "Pipeline", "aed"), ("weighted", "Weighted", "aed"), ("target", "Target", "aed"),
                                           ("attain", "Attainment", "pct"), ("count", "Deals", "int")], rows)
    return chart, table


def _narrative(kind: str, facts: dict, fallback: str) -> tuple[str, str]:
    text = llm.chat([
        {"role": "system", "content": "You are the chief of staff writing for the CEO and board of a technology company. "
         "Write 4-6 crisp sentences: performance against target, the biggest risks, and the decisions needed. "
         "Use only the FACTS. AED with m/bn. No headings, no bullet points. British English."},
        {"role": "user", "content": f"REPORT: {kind}\nFACTS: {json.dumps(facts, default=str)[:6000]}"},
    ], temperature=0.3, max_tokens=420)
    return (text, "llm") if text else (fallback, "template")


# ------------------------------------------------------------------ report builders
def r_executive(v: View, k: dict) -> list[dict]:
    items = k["kpis"]
    red = [i for i in items if i["status"] == "red"]
    top = sorted(v.active, key=lambda o: -v.s(o).get("ev", 0))[:10]
    risks = sorted([o for o in v.active if v.s(o).get("p", 1) < 0.35 or (o.get("intervention") or "").lower() == "yes"],
                   key=lambda o: -((o.get("value") or 0) * (1 - v.s(o).get("p", 0))))[:8]
    h = k["headline"]
    lines = [
        f"The active pipeline stands at {_fmt(h['pipeline'])} across {h['active']} opportunities, worth {_fmt(h['ev'])} once weighted by win probability.",
        f"{h['forecast_quarter']} is forecast at {_fmt(h['forecast_weighted'])} weighted, with {_fmt(h['forecast_commit'])} in commit.",
        f"{k['summary']['green']} KPIs are on target, {k['summary']['amber']} are close and {k['summary']['red']} are off target"
        + (f": {'; '.join(i['label'] for i in red[:3])}." if red else "."),
    ]
    if risks:
        r0 = risks[0]
        lines.append(f"The largest exposure is {r0['name']} ({_fmt(r0.get('value'))}, {round(v.s(r0).get('p', 0) * 100)}% win probability).")
    inter = [o for o in v.active if (o.get("intervention") or "").lower() == "yes"]
    if inter:
        lines.append(f"{len(inter)} opportunities need executive intervention; briefing memos can be generated from the Interventions view.")
    text, engine = _narrative("Executive summary", {"headline": h, "kpis": [{x: i[x] for x in ("label", "value", "target", "status")} for i in items],
                                                     "top_risks": [_opp_row(v, o) for o in risks[:5]]}, " ".join(lines))
    chart, ftable = _forecast_section(v, 4)
    decisions = [{"id": o["id"], "name": o["name"], "sponsor": o.get("sponsor"), "value": o.get("value") or 0, "p": v.s(o).get("p", 0),
                  "ask": o.get("next_action") or "Sponsor-level engagement",
                  "driver": "; ".join(f["label"] for f in v.s(o).get("factors", []) if f["impact"] < 0)[:120]} for o in inter]
    return [
        _text("Summary", text, engine),
        _kpis(items),
        chart,
        _table("Top 10 opportunities by expected value", OPP_COLS + [("quarter", "Expected close", "text")], [_opp_row(v, o) for o in top]),
        _table("Decisions required from leadership", [("id", "ID", "text"), ("name", "Opportunity", "text"), ("sponsor", "Sponsor", "text"),
                                                       ("value", "Value", "aed"), ("p", "Win prob.", "pct"), ("ask", "Ask", "text"),
                                                       ("driver", "What is pulling it down", "text")], decisions),
        _table("Top risks", OPP_COLS + [("delta", "14-day change", "pct")], [_opp_row(v, o) for o in risks]),
        ftable,
    ]


def r_pipeline(v: View, k: dict) -> list[dict]:
    stages = [{"label": s, **{x: y for x, y in g.items() if x != "label"}} for s in scoring.STAGES
              for g in [next((g for g in _group(v, lambda o: o.get("status")) if g["label"] == s),
                             {"count": 0, "value": 0, "ev": 0, "p": 0, "at_risk": 0})]]
    aging = defaultdict(lambda: {"count": 0, "value": 0.0})
    for o in v.active:
        c = scoring.to_date(o.get("created"))
        d = (v.today - c).days if c else None
        b = "Unknown" if d is None else "< 90 days" if d < 90 else "90–180 days" if d < 180 else "180–365 days" if d < 365 else "> 1 year"
        aging[b]["count"] += 1
        aging[b]["value"] += o.get("value") or 0
    dq = []
    for o in v.active:
        issues = []
        if not o.get("value"):
            issues.append("no value")
        ver = scoring.to_date(o.get("verified"))
        if not ver or (v.today - ver).days > 30:
            issues.append("not verified 30d")
        if not o.get("milestone_date"):
            issues.append("no milestone date")
        elif scoring.to_date(o["milestone_date"]) < v.today and o.get("status") != "Execution":
            issues.append("milestone overdue")
        if not o.get("sponsor"):
            issues.append("no sponsor")
        if issues:
            dq.append({"id": o["id"], "name": o["name"], "owner": o.get("owner"), "issues": ", ".join(issues), "verified": o.get("verified")})
    return [
        _kpis([i for i in k["kpis"] if i["key"] in ("pipeline", "weighted_pipeline", "avg_p", "freshness", "coverage")]),
        _bars("Pipeline by stage", stages, "value", "ev", note="Face value (light) vs expected value (solid)"),
        _table("Stage breakdown", [("label", "Stage", "text"), ("count", "Deals", "int"), ("value", "Value", "aed"), ("ev", "Expected value", "aed"),
                                   ("p", "Weighted p", "pct")], stages),
        _bars("Pipeline by domain", _group(v, lambda o: o.get("domain")), "value", "ev"),
        _bars("Pipeline by segment", _group(v, lambda o: o.get("segment")), "value", "ev"),
        _table("Pipeline aging (time since creation)", [("label", "Age", "text"), ("count", "Deals", "int"), ("value", "Value", "aed")],
               [{"label": b, **aging[b]} for b in ("< 90 days", "90–180 days", "180–365 days", "> 1 year", "Unknown") if b in aging]),
        _table("Data quality exceptions", [("id", "ID", "text"), ("name", "Opportunity", "text"), ("owner", "Owner", "text"),
                                           ("issues", "Issues", "text"), ("verified", "Last verified", "date")], dq,
               note="Records with gaps reduce forecast reliability."),
    ]


def r_forecast(v: View, k: dict) -> list[dict]:
    chart, table = _forecast_section(v, 6)
    q_now = _quarter(v.today)
    nq = _quarter(date(v.today.year + (v.today.month > 9), ((v.today.month - 1) // 3 * 3 + 3) % 12 + 1, 1))
    this_q = [o for o in v.active if v.s(o).get("quarter") == q_now and o.get("status") != "Execution"]
    next_q = [o for o in v.active if v.s(o).get("quarter") == nq]
    slipped = [o for o in v.active if scoring.to_date(o.get("milestone_date")) and scoring.to_date(o["milestone_date"]) < v.today
               and o.get("status") != "Execution"]
    movers = sorted([o for o in v.active if v.s(o).get("delta_14d") is not None], key=lambda o: v.s(o)["delta_14d"])
    tier = lambda o: "Commit" if v.s(o)["p"] >= 0.7 else "Best case" if v.s(o)["p"] >= 0.4 else "Pipeline"  # noqa: E731
    return [
        _kpis([i for i in k["kpis"] if i["key"] in ("quarter_forecast", "coverage", "avg_p", "velocity", "weighted_pipeline")]),
        chart, table,
        _table(f"Deals expected to close in {q_now}", OPP_COLS + [("tier", "Category", "text"), ("close", "Expected close", "date")],
               [{**_opp_row(v, o), "tier": tier(o)} for o in sorted(this_q, key=lambda o: -v.s(o)["ev"])]),
        _table(f"Deals expected to close in {nq}", OPP_COLS + [("tier", "Category", "text")],
               [{**_opp_row(v, o), "tier": tier(o)} for o in sorted(next_q, key=lambda o: -v.s(o)["ev"])]),
        _table("Probability movers (14 days)", OPP_COLS + [("delta", "Change", "pct")],
               [_opp_row(v, o) for o in (movers[:5] + movers[-5:][::-1]) if abs(v.s(o)["delta_14d"]) >= 0.02]),
        _table("Slipped milestones", [("id", "ID", "text"), ("name", "Opportunity", "text"), ("milestone", "Milestone", "text"),
                                      ("milestone_date", "Was due", "date"), ("value", "Value", "aed"), ("p", "Win prob.", "pct")],
               [_opp_row(v, o) for o in slipped]),
    ]


def r_winloss(v: View, k: dict) -> list[dict]:
    won, lost = v.closed(730)
    by = defaultdict(lambda: {"won": 0, "lost": 0, "won_value": 0.0, "lost_value": 0.0})
    for o in won + lost:
        d = by[o.get("domain") or "—"]
        tag = "won" if o["status"] == "Closed Won" else "lost"
        d[tag] += 1
        d[tag + "_value"] += o.get("value") or 0
    rows = [{"label": dmn, **x, "win_rate": x["won"] / (x["won"] + x["lost"]) if (x["won"] + x["lost"]) else 0} for dmn, x in by.items()]
    rows.sort(key=lambda r: -(r["won"] + r["lost"]))
    cal = v.snap.cal.as_dict()
    sizes = defaultdict(lambda: {"won": 0, "lost": 0})
    for o in won + lost:
        b = scoring.potential_band(o.get("value") or 0)
        sizes[b]["won" if o["status"] == "Closed Won" else "lost"] += 1
    size_rows = [{"label": {1: "< AED 5m", 2: "AED 5–24m", 3: "AED 25–99m", 4: "AED 100–249m", 5: "AED 250m+"}[b], **sizes[b],
                  "win_rate": sizes[b]["won"] / (sizes[b]["won"] + sizes[b]["lost"])} for b in sorted(sizes)]
    recent = sorted(won + lost, key=lambda o: o.get("closed") or "", reverse=True)[:15]
    return [
        _kpis([i for i in k["kpis"] if i["key"] in ("win_rate", "cycle_days", "velocity")] + [
            {"key": "won_value", "label": "Value won (24 months)", "value": _sum(won, lambda o: o.get("value") or 0), "unit": "aed",
             "status": "neutral", "target": None, "trend": []},
            {"key": "lost_value", "label": "Value lost (24 months)", "value": _sum(lost, lambda o: o.get("value") or 0), "unit": "aed",
             "status": "neutral", "target": None, "trend": []}]),
        _bars("Win rate by domain", [{"label": r["label"], "value": r["win_rate"]} for r in rows], "value", unit="pct"),
        _table("Win/loss by domain (24 months)", [("label", "Domain", "text"), ("won", "Won", "int"), ("lost", "Lost", "int"),
                                                  ("win_rate", "Win rate", "pct"), ("won_value", "Value won", "aed"), ("lost_value", "Value lost", "aed")], rows),
        _table("Win rate by deal size", [("label", "Deal size", "text"), ("won", "Won", "int"), ("lost", "Lost", "int"), ("win_rate", "Win rate", "pct")],
               size_rows),
        _table("Model calibration (all history)", [("domain", "Domain", "text"), ("won", "Won", "int"), ("lost", "Lost", "int"),
                                                   ("win_rate", "Calibrated rate", "pct")], cal["domains"],
               note=f"Overall {round(cal['global_win_rate'] * 100)}%. Rates are Beta-smoothed toward the overall rate."),
        _table("Recent outcomes", [("id", "ID", "text"), ("name", "Opportunity", "text"), ("domain", "Domain", "text"), ("country", "Country", "text"),
                                   ("status", "Outcome", "text"), ("value", "Value", "aed"), ("closed", "Closed", "date")],
               [{**{x: o.get(x) for x in ("id", "name", "domain", "country", "status", "closed")}, "value": o.get("value") or 0} for o in recent]),
    ]


def r_risk(v: View, k: dict) -> list[dict]:
    open_a = [a for a in v.acts if scoring.OPEN_ACTION(a)]
    names = {o["id"]: o["name"] for o in v.all}
    at_risk = sorted([o for o in v.active if v.s(o).get("p", 1) < 0.35 or o.get("outlook") == "Negative"
                      or (o.get("intervention") or "").lower() == "yes"], key=lambda o: -((o.get("value") or 0) * (1 - v.s(o).get("p", 0))))
    rows = []
    for o in at_risk:
        s = v.s(o)
        neg = sorted([f for f in s.get("factors", []) if f["impact"] < 0], key=lambda f: f["impact"])[:3]
        rows.append({**_opp_row(v, o), "exposure": (o.get("value") or 0) * (1 - s.get("p", 0)),
                     "drivers": "; ".join(f["label"] for f in neg),
                     "intervention": o.get("intervention")})
    blocked = [{"id": a["id"], "opp": names.get(a["opp"], a["opp"]), "title": a.get("title"), "owner": a.get("owner"), "due": a.get("due"),
                "status": a.get("status"), "blocker": a.get("blocker"), "escalate": a.get("escalate"),
                "days": (v.today - scoring.to_date(a["due"])).days if scoring.to_date(a.get("due")) else None}
               for a in open_a if a.get("status") == "Blocked" or (a.get("escalate") or "").lower() == "yes"
               or (scoring.to_date(a.get("due")) and scoring.to_date(a["due"]) < v.today)]
    blocked.sort(key=lambda r: -(r["days"] or 0))
    return [
        _kpis([i for i in k["kpis"] if i["key"] in ("at_risk_value", "interventions", "action_on_time", "avg_p")]),
        _bars("Value at risk by domain", [{"label": g["label"], "value": g["value"] - g["ev"]} for g in _group(v, lambda o: o.get("domain"))],
              note="Σ value × (1 − p)"),
        _bars("Value at risk by region", [{"label": g["label"], "value": g["value"] - g["ev"]}
                                          for g in _group(v, lambda o: ontology.region_of(o.get("country")))]),
        _table("At-risk opportunities and drivers", [("id", "ID", "text"), ("name", "Opportunity", "text"), ("sponsor", "Sponsor", "text"),
                                                     ("value", "Value", "aed"), ("p", "Win prob.", "pct"), ("exposure", "Exposure", "aed"),
                                                     ("delta", "14-day change", "pct"), ("intervention", "Intervention", "text"),
                                                     ("drivers", "Main negative drivers", "text")], rows),
        _table("Blocked, escalated and overdue actions", [("id", "ID", "text"), ("opp", "Opportunity", "text"), ("title", "Action", "text"),
                                                          ("owner", "Owner", "text"), ("due", "Due", "date"), ("days", "Days overdue", "int"),
                                                          ("status", "Status", "text"), ("blocker", "Blocker", "text"), ("escalate", "Escalate", "text")], blocked),
    ]


def r_regional(v: View, k: dict) -> list[dict]:
    regions = _group(v, lambda o: ontology.region_of(o.get("country")) or "Other")
    countries = []
    for g in _group(v, lambda o: o.get("country")):
        comp = [o.get("competitors") or 0 for o in v.active if (o.get("country") or "—") == g["label"]]
        countries.append({**g, "region": ontology.region_of(g["label"]), "risk": 1 - g["p"] if g["value"] else 0,
                          "competitors": sum(comp) / len(comp) if comp else 0})
    doms = list(ontology.VOCAB["Domain"])
    mat = []
    for r in regions:
        row = {"label": r["label"]}
        for d in doms:
            row[d] = _sum([o for o in v.active if (ontology.region_of(o.get("country")) or "Other") == r["label"] and o.get("domain") == d],
                          lambda o: o.get("value") or 0)
        row["total"] = r["value"]
        mat.append(row)
    return [
        _bars("Pipeline by region", regions, "value", "ev"),
        _table("Region summary", [("label", "Region", "text"), ("count", "Deals", "int"), ("value", "Value", "aed"), ("ev", "Expected value", "aed"),
                                  ("p", "Weighted p", "pct"), ("at_risk", "Value in deals < 30%", "aed")], regions),
        _table("Country detail", [("label", "Country", "text"), ("region", "Region", "text"), ("count", "Deals", "int"), ("value", "Value", "aed"),
                                  ("ev", "Expected value", "aed"), ("risk", "Value at risk", "pct"), ("competitors", "Competitors / deal", "x")], countries),
        _table("Region × domain (face value)", [("label", "Region", "text")] + [(d, d, "aed") for d in doms] + [("total", "Total", "aed")], mat),
    ]


def r_sponsor(v: View, k: dict) -> list[dict]:
    rows = []
    for sp in sorted({o.get("sponsor") for o in v.active if o.get("sponsor")}):
        os_ = [o for o in v.active if o.get("sponsor") == sp]
        ids = {o["id"] for o in os_}
        acts = [a for a in v.acts if a["opp"] in ids and scoring.OPEN_ACTION(a)]
        recent = {e["opp"] for e in v.engs if e["opp"] in ids and scoring.to_date(e.get("date")) and (v.today - scoring.to_date(e["date"])).days <= 30}
        val = _sum(os_, lambda o: o.get("value") or 0)
        ev = _sum(os_, lambda o: v.s(o).get("ev", 0))
        rows.append({"label": sp, "count": len(os_), "value": val, "ev": ev, "p": ev / val if val else 0,
                     "interventions": sum((o.get("intervention") or "").lower() == "yes" for o in os_),
                     "overdue": sum(1 for a in acts if scoring.to_date(a.get("due")) and scoring.to_date(a["due"]) < v.today),
                     "blocked": sum(a.get("status") == "Blocked" for a in acts),
                     "engaged": len(recent) / len(os_) if os_ else 0,
                     "fresh": sum(1 for o in os_ if scoring.to_date(o.get("verified")) and (v.today - scoring.to_date(o["verified"])).days <= 30) / len(os_)})
    rows.sort(key=lambda r: -r["ev"])
    owners = []
    for ow in sorted({o.get("owner") for o in v.active if o.get("owner")}):
        os_ = [o for o in v.active if o.get("owner") == ow]
        owners.append({"label": ow, "count": len(os_), "value": _sum(os_, lambda o: o.get("value") or 0),
                       "ev": _sum(os_, lambda o: v.s(o).get("ev", 0)),
                       "avg_p": _sum(os_, lambda o: v.s(o).get("p", 0)) / len(os_)})
    owners.sort(key=lambda r: -r["ev"])
    return [
        _bars("Expected value by executive sponsor", rows, "value", "ev"),
        _table("Executive sponsor scorecard", [("label", "Sponsor", "text"), ("count", "Deals", "int"), ("value", "Value", "aed"),
                                               ("ev", "Expected value", "aed"), ("p", "Weighted p", "pct"), ("interventions", "Interventions", "int"),
                                               ("overdue", "Overdue actions", "int"), ("blocked", "Blocked", "int"),
                                               ("engaged", "Engaged 30d", "pct"), ("fresh", "Verified 30d", "pct")], rows),
        _table("Executional owner portfolio", [("label", "Owner", "text"), ("count", "Deals", "int"), ("value", "Value", "aed"),
                                               ("ev", "Expected value", "aed"), ("avg_p", "Average p", "pct")], owners),
    ]


def r_engagement(v: View, k: dict) -> list[dict]:
    weeks = []
    start = v.today - timedelta(days=v.today.weekday()) - timedelta(weeks=11)
    for w in range(12):
        ws = start + timedelta(weeks=w)
        es = [e for e in v.engs if scoring.to_date(e.get("date")) and ws <= scoring.to_date(e["date"]) < ws + timedelta(days=7)]
        weeks.append({"label": ws.strftime("%d %b"), "value": len(es)})
    types = Counter(e.get("type") or "—" for e in v.engs if scoring.to_date(e.get("date")) and (v.today - scoring.to_date(e["date"])).days <= 90)
    src = Counter((e.get("source") if e.get("source") not in (None, "seed") else "manual") for e in v.engs)
    quiet = []
    for o in v.active:
        es = [scoring.to_date(e["date"]) for e in v.engs if e["opp"] == o["id"] and scoring.to_date(e.get("date"))]
        last = max(es) if es else None
        gap = (v.today - last).days if last else None
        if gap is None or gap > 30:
            quiet.append({"id": o["id"], "name": o["name"], "owner": o.get("owner"), "last": last.isoformat() if last else None,
                          "gap": gap, "value": o.get("value") or 0, "p": v.s(o).get("p", 0)})
    quiet.sort(key=lambda r: -(r["gap"] or 9999))
    per_opp = []
    for o in v.active:
        es = [e for e in v.engs if e["opp"] == o["id"] and scoring.to_date(e.get("date")) and (v.today - scoring.to_date(e["date"])).days <= 90]
        sent = [scoring.sentiment(e.get("summary") or "") for e in es]
        per_opp.append({"id": o["id"], "name": o["name"], "count": len(es),
                        "sentiment": sum(sent) / len(sent) if sent else 0, "p": v.s(o).get("p", 0)})
    per_opp.sort(key=lambda r: -r["count"])
    return [
        _kpis([i for i in k["kpis"] if i["key"] in ("engagement_coverage", "action_on_time", "freshness")]),
        {"kind": "columns", "title": "Engagements per week (12 weeks)", "items": weeks},
        _bars("Engagement mix (90 days)", [{"label": t, "value": n} for t, n in types.most_common()], unit="int"),
        _bars("Engagement source", [{"label": t, "value": n} for t, n in src.most_common()], unit="int",
              note="Outlook and Teams sources appear once Microsoft 365 is connected"),
        _table("Opportunities without contact in 30+ days", [("id", "ID", "text"), ("name", "Opportunity", "text"), ("owner", "Owner", "text"),
                                                              ("last", "Last contact", "date"), ("gap", "Days", "int"), ("value", "Value", "aed"),
                                                              ("p", "Win prob.", "pct")], quiet),
        _table("Engagement intensity and tone (90 days)", [("id", "ID", "text"), ("name", "Opportunity", "text"), ("count", "Engagements", "int"),
                                                           ("sentiment", "Tone (−1…+1)", "x"), ("p", "Win prob.", "pct")], per_opp),
    ]


def r_announcements(v: View, k: dict) -> list[dict]:
    names = {o["id"]: o["name"] for o in v.all}
    rows = []
    for a in sorted(v.anns, key=lambda a: a.get("target") or "9999"):
        pending = [lab for key, lab in (("legal", "Legal"), ("ir", "IR"), ("counterparty", "Counterparty"))
                   if (a.get(key) or "").lower() not in ("approved", "not required")]
        t = scoring.to_date(a.get("target"))
        rows.append({"id": a["id"], "title": a.get("title"), "opp": names.get(a["opp"], a["opp"]), "type": a.get("type"),
                     "target": a.get("target"), "days": (t - v.today).days if t else None, "readiness": a.get("readiness"),
                     "pending": ", ".join(pending) or "—", "legal": a.get("legal"), "ir": a.get("ir"), "cp": a.get("counterparty"),
                     "risk": "At risk" if pending and t and (t - v.today).days < 14 else "On track" if not pending else "Pending"})
    stage = Counter(r["readiness"] or "—" for r in rows)
    gate = Counter()
    for r in rows:
        for p in r["pending"].split(", "):
            if p != "—":
                gate[p] += 1
    return [
        _kpis([i for i in k["kpis"] if i["key"] == "announcement_readiness"]),
        _bars("Announcements by readiness", [{"label": s_, "value": n} for s_, n in stage.most_common()], unit="int"),
        _bars("Pending approvals by gate", [{"label": g, "value": n} for g, n in gate.most_common()], unit="int"),
        _table("Announcement pipeline", [("id", "ID", "text"), ("title", "Announcement", "text"), ("opp", "Opportunity", "text"),
                                         ("target", "Target", "date"), ("days", "Days to go", "int"), ("readiness", "Readiness", "text"),
                                         ("pending", "Awaiting", "text"), ("risk", "Status", "text")], rows,
               note="A potential announcement is not clearance to publish."),
    ]


REPORTS: dict[str, dict[str, Any]] = {
    "executive-summary": {"title": "Executive Summary", "audience": "CEO / Board", "fn": r_executive,
                          "description": "One-page board view: KPI scorecard against target, forecast, top deals, decisions required and top risks."},
    "pipeline-health": {"title": "Pipeline Health", "audience": "C-suite", "fn": r_pipeline,
                        "description": "Pipeline by stage, domain and segment; aging; data-quality exceptions that weaken the forecast."},
    "forecast": {"title": "Forecast & Commit", "audience": "CEO / CFO", "fn": r_forecast,
                 "description": "Six-quarter forecast against target, deals closing this and next quarter, probability movers, slipped milestones."},
    "win-loss": {"title": "Win / Loss Analysis", "audience": "CCO / Strategy", "fn": r_winloss,
                 "description": "Win rate by domain and deal size, value won and lost, sales cycle and model calibration."},
    "risk": {"title": "Risk & Interventions", "audience": "CEO / COO", "fn": r_risk,
             "description": "Value at risk by domain and region, at-risk deals with model drivers, blocked and overdue actions."},
    "regional": {"title": "Regional Performance", "audience": "Regional leadership", "fn": r_regional,
                 "description": "Region and country exposure, risk and competition; region × domain matrix."},
    "sponsor-scorecard": {"title": "Sponsor Scorecard", "audience": "CEO / ExCo", "fn": r_sponsor,
                          "description": "Accountability view per executive sponsor and executional owner."},
    "engagement": {"title": "Engagement Activity", "audience": "Domain directors", "fn": r_engagement,
                   "description": "Weekly engagement volume, mix and sources, quiet opportunities, tone of recent notes."},
    "announcements": {"title": "Announcement Readiness", "audience": "Communications / IR", "fn": r_announcements,
                      "description": "Announcement pipeline, approvals pending by gate, timing risk."},
}


def catalogue() -> list[dict]:
    return [{"id": k, "title": r["title"], "audience": r["audience"], "description": r["description"]} for k, r in REPORTS.items()]


def build(snap: Snapshot, rid: str, f: dict) -> dict:
    if rid not in REPORTS:
        raise KeyError(rid)
    meta = REPORTS[rid]
    v = View(snap, f)
    k = kpis(snap, f)
    sections = meta["fn"](v, k)
    return {"id": rid, "title": meta["title"], "audience": meta["audience"], "description": meta["description"],
            "as_of": v.today.isoformat(), "scope": v.filter_label(), "filters": v.f, "sections": sections}


# ------------------------------------------------------------------ Excel
def _xl_value(val: Any, typ: str) -> tuple[Any, str | None]:
    if val is None or val == "":
        return None, None
    if typ == "aed":
        return float(val), '#,##0'
    if typ == "pct":
        return float(val), '0%'
    if typ == "x":
        return float(val), '0.00'
    if typ in ("int", "days"):
        return val, '0'
    if typ == "date":
        try:
            return date.fromisoformat(str(val)[:10]), 'dd-mmm-yyyy'
        except ValueError:
            return val, None
    return val, None


UNIT_FMT = {"aed": '#,##0', "pct": '0%', "x": '0.00"x"', "count": '0', "days": '0', "aed_day": '#,##0', "int": '0'}


def to_xlsx(rep: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    head = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="0D1A22")
    ws["A1"] = f"Precast · {rep['title']}"
    ws["A1"].font = Font(size=16, bold=True, color="0D1A22")
    ws["A2"] = f"As of {rep['as_of']} · {rep['scope']} · Audience: {rep['audience']}"
    ws["A2"].font = Font(italic=True, color="56666F")
    r = 4
    used = {"Summary"}
    for sec in rep["sections"]:
        if sec["kind"] == "text":
            ws.cell(r, 1, sec["title"]).font = Font(bold=True)
            c = ws.cell(r + 1, 1, sec["body"])
            c.alignment = Alignment(wrap_text=True, vertical="top")
            ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=6)
            ws.row_dimensions[r + 1].height = 110
            r += 3
        elif sec["kind"] == "kpis":
            for ci, h in enumerate(["KPI", "Value", "Target", "Status", "Change (4 wks)", "Definition"], 1):
                c = ws.cell(r, ci, h); c.font, c.fill = head, fill
            for it in sec["items"]:
                r += 1
                ws.cell(r, 1, it["label"])
                c = ws.cell(r, 2, it["value"]); c.number_format = UNIT_FMT.get(it["unit"], "General")
                if it.get("target") is not None:
                    c = ws.cell(r, 3, it["target"]); c.number_format = UNIT_FMT.get(it["unit"], "General")
                st = ws.cell(r, 4, (it.get("status") or "").upper())
                st.fill = PatternFill("solid", fgColor={"green": "DCF0E3", "amber": "F5ECD2", "red": "F8DEDB"}.get(it.get("status"), "FFFFFF"))
                if it.get("delta_4w") is not None:
                    c = ws.cell(r, 5, it["delta_4w"]); c.number_format = UNIT_FMT.get(it["unit"], "General")
                ws.cell(r, 6, it.get("description", ""))
            r += 3
        elif sec["kind"] in ("table", "bars", "stack", "columns"):
            if sec["kind"] == "table":
                cols, rows = sec["columns"], sec["rows"]
            elif sec["kind"] == "stack":
                cols = [{"key": "quarter", "label": "Quarter", "type": "text"}] + [{"key": s_["key"], "label": s_["label"], "type": "aed"} for s_ in sec["series"]] \
                       + [{"key": sec["line"], "label": sec["line_label"], "type": "aed"}]
                rows = sec["items"]
            else:
                unit = sec.get("unit", "int" if sec["kind"] == "columns" else "aed")
                cols = [{"key": "label", "label": "Item", "type": "text"}, {"key": sec.get("value", "value"), "label": "Value", "type": unit}]
                if sec.get("second"):
                    cols.append({"key": sec["second"], "label": "Expected value", "type": unit})
                rows = sec["items"]
            name = "".join(ch for ch in sec["title"] if ch not in '[]:*?/\\')[:31]
            base, n = name, 2
            while name in used:
                name = f"{base[:28]} {n}"; n += 1
            used.add(name)
            sh = wb.create_sheet(name)
            sh["A1"] = sec["title"]; sh["A1"].font = Font(size=13, bold=True)
            if sec.get("note"):
                sh["A2"] = sec["note"]; sh["A2"].font = Font(italic=True, color="56666F")
            for ci, col in enumerate(cols, 1):
                c = sh.cell(4, ci, col["label"]); c.font, c.fill = head, fill
                sh.column_dimensions[get_column_letter(ci)].width = 40 if col["type"] == "text" and ci <= 3 else 16
            for ri, row in enumerate(rows, 5):
                for ci, col in enumerate(cols, 1):
                    val, nf = _xl_value(row.get(col["key"]), col["type"])
                    c = sh.cell(ri, ci, val)
                    if nf:
                        c.number_format = nf
            sh.freeze_panes = "A5"
    ws.column_dimensions["A"].width = 38
    for col in "BCDE":
        ws.column_dimensions[col].width = 18
    ws.column_dimensions["F"].width = 70
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
