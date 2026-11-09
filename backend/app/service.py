"""Loads the working set and derived scores in one place so every endpoint sees the same numbers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import db, scoring


@dataclass
class Snapshot:
    opps: list[dict]
    engs: list[dict]
    acts: list[dict]
    anns: list[dict]
    discs: list[dict]
    scores: dict[str, dict]
    cal: scoring.Calibration

    def opp(self, oid: str) -> dict | None:
        return next((o for o in self.opps if o["id"] == oid), None)

    @property
    def live(self) -> list[dict]:
        """Opportunities in the working register (historical calibration records excluded)."""
        return [o for o in self.opps if not o["id"].startswith("HIS-")]

    @property
    def active(self) -> list[dict]:
        return [o for o in self.live if o.get("status") not in scoring.INACTIVE]

    def enriched(self, o: dict) -> dict:
        s = self.scores.get(o["id"], {})
        acts = [a for a in self.acts if a["opp"] == o["id"]]
        return {**o, "score": s, "actions_open": sum(scoring.OPEN_ACTION(a) for a in acts),
                "actions_blocked": sum(a.get("status") == "Blocked" for a in acts),
                "escalation": any((a.get("escalate") or "").lower() == "yes" and scoring.OPEN_ACTION(a) for a in acts)}


def snapshot(as_of: date | None = None) -> Snapshot:
    opps = db.all_rows("opportunities")
    engs = db.all_rows("engagements")
    acts = db.all_rows("actions")
    anns = db.all_rows("announcements")
    discs = db.all_rows("discussions")
    scores = scoring.score_portfolio(opps, engs, acts, as_of)
    return Snapshot(opps, engs, acts, anns, discs, scores, scoring.calibrate(opps))
