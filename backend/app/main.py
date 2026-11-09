"""Precast API."""
from __future__ import annotations

from datetime import date, datetime, timezone
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import assistant, config, db, drafts, extract, ingest, llm, m365, ontology, scoring, seed
from .service import snapshot

@asynccontextmanager
async def lifespan(_: FastAPI):
    if config.SEED_ON_START:
        seed.seed()
    yield


app = FastAPI(title="Precast API", version="1.0.0", lifespan=lifespan,
              description="Predictive pipeline intelligence: scoring, forecasting, bilingual Q&A and executive drafting.")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


def write_guard(request: Request) -> None:
    if config.API_KEY and request.headers.get("x-api-key") != config.API_KEY:
        raise HTTPException(401, "Missing or invalid X-API-Key")


@app.exception_handler(m365.M365Error)
def _m365_error(_: Request, e: m365.M365Error):
    return JSONResponse({"detail": str(e)}, status_code=502)


def _d(v: Any) -> date | None:
    return scoring.to_date(v)


# ------------------------------------------------------------------ meta
@app.get("/api/health")
def health():
    return {"ok": True, "llm": llm.status(), "m365": m365.status()["configured"], "records": db.count("opportunities")}


@app.get("/api/llm/status")
def llm_status():
    return llm.status(force=True)


# ------------------------------------------------------------------ overview
@app.get("/api/overview")
def overview():
    s = snapshot()
    today = date.today()
    live, active = s.live, s.active
    sc = s.scores
    pipe = sum(o.get("value") or 0 for o in active)
    ev = sum(sc[o["id"]]["ev"] for o in active)
    inter = [o for o in active if (o.get("intervention") or "").lower() == "yes"]
    open_a = [a for a in s.acts if scoring.OPEN_ACTION(a)]
    overdue = [a for a in open_a if _d(a.get("due")) and _d(a["due"]) < today]
    blocked = [a for a in open_a if a.get("status") == "Blocked"]
    stale = [o for o in active if not _d(o.get("verified")) or (today - _d(o["verified"])).days > 30]
    fc = scoring.forecast(live, sc)
    q_now = fc["quarters"][0]

    def agg(key: str, keys: list[str]):
        out = []
        for k in keys:
            rows = [o for o in active if o.get(key) == k]
            out.append({"key": k, "count": len(rows), "value": sum(o.get("value") or 0 for o in rows),
                        "ev": round(sum(sc[o["id"]]["ev"] for o in rows), 2)})
        return out

    att = []
    for o in active:
        r, hi = [], False
        x = sc[o["id"]]
        if (o.get("intervention") or "").lower() == "yes":
            r.append(["Intervention required", "neg"]); hi = True
        if o.get("outlook") == "Negative":
            r.append(["Negative outlook", "neg"]); hi = True
        if x.get("delta_14d", 0) <= -0.05:
            r.append([f"Probability {round(x['delta_14d'] * 100)} pts in 14d", "neg"]); hi = True
        oa = [a for a in open_a if a["opp"] == o["id"]]
        od = sum(1 for a in oa if _d(a.get("due")) and _d(a["due"]) < today)
        if od:
            r.append([f"{od} overdue action{'s' if od > 1 else ''}", "neu"])
        if any(a.get("status") == "Blocked" for a in oa):
            r.append(["Blocked action", "neu"])
        if any((a.get("escalate") or "").lower() == "yes" for a in oa):
            r.append(["Escalation requested", "neu"])
        md = _d(o.get("milestone_date"))
        if md and md < today and o.get("status") != "Execution":
            r.append(["Milestone overdue", "neu"])
        if r:
            att.append({"id": o["id"], "name": o["name"], "country": o.get("country"), "status": o.get("status"),
                        "sponsor": o.get("sponsor"), "value": o.get("value"), "p": x["p"], "delta": x.get("delta_14d"),
                        "priority": o.get("priority"), "reasons": r, "high": hi})
    att.sort(key=lambda a: (-a["high"], -(a["priority"] or 0), -(a["value"] or 0)))

    items = []
    for o in active:
        md = _d(o.get("milestone_date"))
        if md and o.get("milestone"):
            items.append({"date": md.isoformat(), "title": o["milestone"], "meta": o["name"], "kind": "Milestone", "opp": o["id"]})
    for a in open_a:
        if _d(a.get("due")):
            nm = (s.opp(a["opp"]) or {}).get("name", a["opp"])
            items.append({"date": a["due"], "title": a.get("title"), "meta": f"{nm} · {a.get('owner')}",
                          "kind": "Blocked" if a.get("status") == "Blocked" else "Action", "opp": a["opp"]})
    for a in s.anns:
        if _d(a.get("target")) and a.get("readiness") not in ("Announced", "Cancelled"):
            items.append({"date": a["target"], "title": a.get("title"), "meta": f"Announcement · {a.get('readiness')}",
                          "kind": "Announcement", "opp": a["opp"]})
    items = sorted([i for i in items if -60 <= (_d(i["date"]) - today).days <= 45], key=lambda i: i["date"])

    movers = sorted([{"id": o["id"], "name": o["name"], "p": sc[o["id"]]["p"], "delta": sc[o["id"]].get("delta_14d", 0),
                      "trend": sc[o["id"]].get("trend", [])} for o in active], key=lambda m: -abs(m["delta"]))[:6]
    return {
        "as_of": today.isoformat(),
        "kpis": {
            "active": len(active), "register": len(live), "closed_or_hold": len(live) - len(active),
            "pipeline": pipe, "expected_value": round(ev, 2), "ev_ratio": round(ev / pipe, 3) if pipe else 0,
            "forecast_quarter": q_now["quarter"], "forecast_commit": q_now["commit"], "forecast_weighted": q_now["weighted"],
            "interventions": len(inter), "intervention_value": sum(o.get("value") or 0 for o in inter),
            "announcements": sum((o.get("announce") or "").lower() == "yes" for o in active),
            "announcements_considered": sum("consideration" in (o.get("announce") or "").lower() for o in active),
            "overdue": len(overdue), "blocked": len(blocked), "stale": len(stale),
            "due30": sum(1 for a in open_a if _d(a.get("due")) and 0 <= (_d(a["due"]) - today).days <= 30),
            "avg_p": round(sum(sc[o["id"]]["p"] for o in active) / len(active), 3) if active else 0,
        },
        "stages": agg("status", scoring.STAGES),
        "closed": [{"key": k, "count": sum(o.get("status") == k for o in live),
                    "value": sum(o.get("value") or 0 for o in live if o.get("status") == k)} for k in scoring.INACTIVE],
        "outlook": agg("outlook", ["Positive", "Neutral", "Negative"]),
        "domains": agg("domain", list(ontology.VOCAB["Domain"])),
        "forecast": fc, "attention": att, "timeline": items[:14], "movers": movers,
        "calibration": s.cal.as_dict(),
    }


# ------------------------------------------------------------------ opportunities
@app.get("/api/opportunities")
def list_opps(include_closed: bool = True):
    s = snapshot()
    rows = s.live if include_closed else s.active
    return [s.enriched(o) for o in rows]


@app.get("/api/opportunities/{oid}")
def get_opp(oid: str):
    s = snapshot()
    o = s.opp(oid)
    if not o:
        raise HTTPException(404, "Opportunity not found")
    return {**s.enriched(o),
            "actions": sorted([a for a in s.acts if a["opp"] == oid], key=lambda a: a.get("due") or ""),
            "engagements": sorted([e for e in s.engs if e["opp"] == oid], key=lambda e: e.get("date") or "", reverse=True),
            "announcements": [a for a in s.anns if a["opp"] == oid],
            "discussions": sorted([d for d in s.discs if d["opp"] == oid], key=lambda d: d.get("created") or ""),
            "region": ontology.region_of(o.get("country"))}


class OppIn(BaseModel):
    model_config = {"extra": "allow"}


@app.post("/api/opportunities", dependencies=[Depends(write_guard)])
def create_opp(body: dict):
    body = dict(body)
    body.setdefault("id", db.next_id("opportunities", "OPP"))
    body.setdefault("created", date.today().isoformat())
    try:
        clean, warns = ontology.validate("opportunities", body)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if (clean.get("lat") is None) and clean.get("country") in ingest.CENTROIDS:
        clean["lat"], clean["lon"] = ingest.CENTROIDS[clean["country"]]
    return {"record": db.upsert("opportunities", clean), "warnings": warns}


@app.patch("/api/opportunities/{oid}", dependencies=[Depends(write_guard)])
def patch_opp(oid: str, body: dict):
    if not db.get_row("opportunities", oid):
        raise HTTPException(404, "Opportunity not found")
    clean, warns = ontology.validate("opportunities", {"id": oid, "name": "x", **body})
    clean = {k: v for k, v in clean.items() if k in body}
    return {"record": db.update("opportunities", oid, clean), "warnings": warns}


@app.delete("/api/opportunities/{oid}", dependencies=[Depends(write_guard)])
def del_opp(oid: str):
    db.delete("opportunities", oid)
    return {"deleted": oid}


# ------------------------------------------------------------------ scoring / matrix / forecast / geo
@app.get("/api/forecast")
def get_forecast(quarters: int = 4):
    s = snapshot()
    return {**scoring.forecast(s.live, s.scores, quarters), "calibration": s.cal.as_dict()}


@app.get("/api/matrix")
def matrix(potential: str = "dynamic"):
    s = snapshot()
    pts = []
    for o in s.active:
        x = s.scores[o["id"]]
        c_now = x["potential_dynamic"] if potential == "dynamic" else int(o.get("commercial") or 0)
        c_next = x.get("potential_next", c_now) if potential == "dynamic" else c_now
        pts.append({"id": o["id"], "name": o["name"], "priority": int(o.get("priority") or 0), "potential": c_now,
                    "potential_next": c_next, "p": x["p"], "p_next": x.get("p_next"), "delta": x.get("delta_14d"),
                    "direction": x.get("direction"), "value": o.get("value"), "ev": x["ev"], "domain": o.get("domain")})
    return {"mode": potential, "points": pts}


@app.get("/api/geo")
def geo():
    s = snapshot()
    feats, countries = [], {}
    for o in s.live:
        if o.get("lat") is None or o.get("lon") is None:
            continue
        x = s.scores.get(o["id"], {})
        active = o.get("status") not in scoring.INACTIVE
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [o["lon"], o["lat"]]},
                      "properties": {"id": o["id"], "name": o["name"], "site": o.get("site"), "country": o.get("country"),
                                     "domain": o.get("domain"), "status": o.get("status"), "value": o.get("value") or 0,
                                     "ev": x.get("ev", 0), "p": x.get("p", 0), "risk": x.get("risk"), "active": active,
                                     "at_risk_value": (o.get("value") or 0) * (1 - x.get("p", 0)) if active else 0,
                                     "competitors": o.get("competitors") or 0}})
        if active:
            c = countries.setdefault(o.get("country"), {"country": o.get("country"), "region": ontology.region_of(o.get("country")),
                                                        "count": 0, "value": 0, "ev": 0, "competitors": 0, "lat": 0, "lon": 0})
            c["count"] += 1
            c["value"] += o.get("value") or 0
            c["ev"] += x.get("ev", 0)
            c["competitors"] += o.get("competitors") or 0
            c["lat"] += o["lat"]
            c["lon"] += o["lon"]
    for c in countries.values():
        c["lat"] /= c["count"]
        c["lon"] /= c["count"]
        c["risk"] = round(1 - c["ev"] / c["value"], 3) if c["value"] else 0
        c["competitor_density"] = round(c["competitors"] / c["count"], 2)
    return {"type": "FeatureCollection", "features": feats, "countries": sorted(countries.values(), key=lambda c: -c["value"])}


# ------------------------------------------------------------------ engagements / actions / announcements
@app.get("/api/engagements")
def list_eng(limit: int = 200):
    s = snapshot()
    names = {o["id"]: o["name"] for o in s.opps}
    rows = sorted(s.engs, key=lambda e: e.get("date") or "", reverse=True)[:limit]
    return [{**e, "opp_name": names.get(e["opp"], e["opp"])} for e in rows]


@app.post("/api/engagements", dependencies=[Depends(write_guard)])
def add_eng(body: dict):
    if not body.get("opp") or not db.get_row("opportunities", body["opp"]):
        raise HTTPException(422, "A valid opportunity is required")
    body = {**body, "id": body.get("id") or db.next_id("engagements", "ENG"), "date": body.get("date") or date.today().isoformat()}
    body.setdefault("source", "manual")
    rec = db.upsert("engagements", body)
    o = db.get_row("opportunities", body["opp"])
    if not o.get("last_engagement") or rec["date"] > o["last_engagement"]:
        db.update("opportunities", body["opp"], {"last_engagement": rec["date"]})
    if body.get("follow_up") and body.get("create_action"):
        db.upsert("actions", {"id": db.next_id("actions", "ACT"), "opp": body["opp"], "title": body["follow_up"],
                              "category": "Commercial", "owner": body.get("owner"), "due": body.get("due"),
                              "status": "Not Started", "priority": "Normal", "escalate": "No", "created": date.today().isoformat()})
    new = snapshot().scores.get(body["opp"], {})
    return {"record": rec, "score": new}


class NotesIn(BaseModel):
    text: str
    opp: str | None = None


@app.post("/api/engagements/extract")
def extract_notes(body: NotesIn):
    if not body.text.strip():
        raise HTTPException(422, "Paste some meeting notes first")
    return extract.extract(snapshot(), body.text, body.opp)


@app.get("/api/actions")
def list_actions():
    s = snapshot()
    names = {o["id"]: o["name"] for o in s.opps}
    return [{**a, "opp_name": names.get(a["opp"], a["opp"])} for a in sorted(s.acts, key=lambda a: a.get("due") or "")]


@app.post("/api/actions", dependencies=[Depends(write_guard)])
def add_action(body: dict):
    if not body.get("opp") or not db.get_row("opportunities", body["opp"]):
        raise HTTPException(422, "A valid opportunity is required")
    body = {"id": db.next_id("actions", "ACT"), "status": "Not Started", "escalate": "No", "created": date.today().isoformat(), **body}
    clean, _ = ontology.validate("actions", body)
    return db.upsert("actions", clean)


@app.patch("/api/actions/{aid}", dependencies=[Depends(write_guard)])
def patch_action(aid: str, body: dict):
    clean, _ = ontology.validate("actions", {"id": aid, "opp": "x", **body})
    return db.update("actions", aid, {k: v for k, v in clean.items() if k in body})


@app.get("/api/announcements")
def list_ann():
    s = snapshot()
    names = {o["id"]: o["name"] for o in s.opps}
    return [{**a, "opp_name": names.get(a["opp"], a["opp"]),
             "cleared": all((a.get(k) or "").lower() in ("approved", "not required") for k in ("legal", "ir", "counterparty"))}
            for a in sorted(s.anns, key=lambda a: a.get("target") or "9999")]


@app.patch("/api/announcements/{aid}", dependencies=[Depends(write_guard)])
def patch_ann(aid: str, body: dict):
    if not db.get_row("announcements", aid):
        raise HTTPException(404, "Announcement not found")
    clean, warns = ontology.validate("announcements", {"id": aid, "opp": "x", **body})
    clean = {k: v for k, v in clean.items() if k in body}
    rec = db.update("announcements", aid, clean)
    cleared = all((rec.get(k) or "").lower() in ("approved", "not required") for k in ("legal", "ir", "counterparty"))
    if cleared and rec.get("readiness") in ("Planning", "Pending Approvals"):
        rec = db.update("announcements", aid, {"readiness": "Approved"})
    elif not cleared and rec.get("readiness") == "Approved":
        rec = db.update("announcements", aid, {"readiness": "Pending Approvals"})
    return {"record": rec, "warnings": warns}


@app.post("/api/announcements", dependencies=[Depends(write_guard)])
def add_ann(body: dict):
    if not body.get("opp") or not db.get_row("opportunities", body["opp"]):
        raise HTTPException(422, "A valid opportunity is required")
    body = {"id": db.next_id("announcements", "ANN"), "readiness": "Planning", "legal": "Pending", "ir": "Pending",
            "counterparty": "Pending", **body}
    clean, _ = ontology.validate("announcements", body)
    return db.upsert("announcements", clean)


# ------------------------------------------------------------------ AI
class DraftIn(BaseModel):
    kind: str = "memo"
    lang: str = "en"


@app.post("/api/opportunities/{oid}/draft")
def draft_intervention(oid: str, body: DraftIn):
    try:
        return drafts.intervention(snapshot(), oid, body.kind, body.lang)
    except KeyError:
        raise HTTPException(404, "Opportunity not found") from None


@app.post("/api/announcements/{aid}/draft")
def draft_pr(aid: str, body: DraftIn):
    try:
        return drafts.press_release(snapshot(), aid, body.lang)
    except KeyError:
        raise HTTPException(404, "Announcement not found") from None


class AskIn(BaseModel):
    question: str
    history: list[dict] = []


@app.post("/api/ask")
def ask(body: AskIn):
    if not body.question.strip():
        raise HTTPException(422, "Ask a question")
    return assistant.answer(snapshot(), body.question, body.history)


# ------------------------------------------------------------------ ontology / knowledge graph
@app.get("/api/ontology")
def get_ontology():
    return ontology.as_dict()


@app.get("/api/ontology.ttl", response_class=PlainTextResponse)
def get_ttl():
    return PlainTextResponse(ontology.to_turtle(), media_type="text/turtle",
                             headers={"Content-Disposition": 'attachment; filename="precast-ontology.ttl"'})


@app.get("/api/ontology.jsonld")
def get_jsonld():
    return JSONResponse(ontology.to_jsonld(), media_type="application/ld+json",
                        headers={"Content-Disposition": 'attachment; filename="precast-ontology.jsonld"'})


@app.get("/api/graph")
def graph(focus: str | None = None):
    s = snapshot()
    if focus and not s.opp(focus):
        raise HTTPException(404, "Opportunity not found")
    return ontology.knowledge_graph(s, focus)


# ------------------------------------------------------------------ discussions (per opportunity, synced with Teams)
class DiscIn(BaseModel):
    body: str
    author: str = "Precast user"
    parent: str | None = None
    post_to_teams: bool = True


@app.get("/api/opportunities/{oid}/discussions")
def list_disc(oid: str):
    return sorted(db.all_rows("discussions", "opp=?", (oid,)), key=lambda d: d.get("created") or "")


@app.post("/api/opportunities/{oid}/discussions", dependencies=[Depends(write_guard)])
def add_disc(oid: str, body: DiscIn):
    if not db.get_row("opportunities", oid):
        raise HTTPException(404, "Opportunity not found")
    if not body.body.strip():
        raise HTTPException(422, "Write a message")
    rec = db.upsert("discussions", {"id": db.next_id("discussions", "DSC"), "opp": oid, "parent": body.parent,
                                    "author": body.author.strip() or "Precast user", "body": body.body.strip(),
                                    "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": "precast"})
    posted = m365.teams_post(oid, body.body.strip(), rec["author"]) if body.post_to_teams else False
    return {"record": rec, "posted_to_teams": posted}


@app.delete("/api/discussions/{did}", dependencies=[Depends(write_guard)])
def del_disc(did: str):
    db.delete("discussions", did)
    return {"deleted": did}


# ------------------------------------------------------------------ ingestion
@app.get("/api/ingest/template")
def template(examples: bool = True):
    return Response(ingest.build_template(examples), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="Precast_Tracker_Template.xlsx"'})


@app.get("/api/export")
def export():
    return Response(ingest.export_workbook(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="Precast_Tracker_{date.today().isoformat()}.xlsx"'})


@app.post("/api/ingest/xlsx", dependencies=[Depends(write_guard)])
async def ingest_xlsx(file: UploadFile = File(...), mode: str = Form("merge")):
    if mode not in ("merge", "replace"):
        raise HTTPException(422, "mode must be merge or replace")
    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(413, "Workbook larger than 25 MB")
    try:
        return {**ingest.import_workbook(content, mode), "file": file.filename}
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/ingest/crm", dependencies=[Depends(write_guard)])
def ingest_crm(body: dict):
    """Batch upsert from a CRM/ERP connector: {"opportunities": [...], "engagements": [...], "actions": [...], "announcements": [...]}."""
    out = {"counts": {}, "warnings": []}
    for table in ("opportunities", "engagements", "actions", "announcements"):
        n = 0
        for rec in body.get(table, []) or []:
            try:
                clean, warns = ontology.validate(table, rec)
            except ValueError as e:
                out["warnings"].append(str(e))
                continue
            if table != "opportunities" and not db.get_row("opportunities", clean.get("opp")):
                out["warnings"].append(f"{clean['id']}: unknown opportunity {clean.get('opp')}")
                continue
            if table == "opportunities" and clean.get("lat") is None and clean.get("country") in ingest.CENTROIDS:
                clean["lat"], clean["lon"] = ingest.CENTROIDS[clean["country"]]
            out["warnings"].extend(warns)
            db.upsert(table, {k: v for k, v in clean.items() if v is not None})
            n += 1
        out["counts"][table] = n
    return out


@app.post("/api/admin/reset-sample", dependencies=[Depends(write_guard)])
def reset_sample():
    seed.seed(force=True)
    return {"ok": True, "records": db.count("opportunities")}


# ------------------------------------------------------------------ Microsoft 365
@app.get("/api/integrations/m365")
def m365_status():
    return m365.status()


@app.put("/api/integrations/m365", dependencies=[Depends(write_guard)])
def m365_save(body: dict):
    m365.save_settings(body)
    return m365.status()


@app.post("/api/integrations/m365/test", dependencies=[Depends(write_guard)])
def m365_test():
    g = m365.Graph()
    g.token()
    out = {"auth": True}
    if g.cfg.get("sp_site"):
        out["sharepoint_site"] = g.site_id()
    return out


@app.post("/api/integrations/sharepoint/pull", dependencies=[Depends(write_guard)])
def sp_pull(mode: str = "merge"):
    return m365.sharepoint_pull(mode=mode)


@app.post("/api/integrations/sharepoint/push", dependencies=[Depends(write_guard)])
def sp_push():
    return m365.sharepoint_push()


@app.post("/api/opportunities/{oid}/sharepoint", dependencies=[Depends(write_guard)])
def sp_folder(oid: str):
    try:
        return m365.sharepoint_folder(oid)
    except KeyError:
        raise HTTPException(404, "Opportunity not found") from None


@app.post("/api/opportunities/{oid}/teams/channel", dependencies=[Depends(write_guard)])
def teams_channel(oid: str):
    try:
        return m365.teams_channel(oid)
    except KeyError:
        raise HTTPException(404, "Opportunity not found") from None


@app.post("/api/opportunities/{oid}/teams/sync", dependencies=[Depends(write_guard)])
def teams_sync(oid: str):
    return m365.teams_sync(oid)


@app.post("/api/integrations/outlook/sync", dependencies=[Depends(write_guard)])
def outlook_sync(days: int = 30, opp: str | None = None):
    return m365.outlook_sync(days=days, only=opp)


class MailIn(BaseModel):
    subject: str
    body: str
    to: list[str] = []


@app.post("/api/opportunities/{oid}/outlook/draft", dependencies=[Depends(write_guard)])
def outlook_draft(oid: str, body: MailIn):
    subj = body.subject if f"[{oid}]" in body.subject else f"[{oid}] {body.subject}"
    return m365.outlook_draft(subj, body.body, body.to)


class EventIn(BaseModel):
    start: datetime
    minutes: int = 30
    attendees: list[str] = []
    timezone: str = "Arabian Standard Time"


@app.post("/api/opportunities/{oid}/outlook/event", dependencies=[Depends(write_guard)])
def outlook_event(oid: str, body: EventIn):
    try:
        return m365.outlook_event(oid, body.start, body.minutes, body.attendees, body.timezone)
    except KeyError:
        raise HTTPException(404, "Opportunity not found") from None


# ------------------------------------------------------------------ static frontend
if config.STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=config.STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = config.STATIC_DIR / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(config.STATIC_DIR / "index.html")
