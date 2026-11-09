import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app import ontology, scoring
from app.main import app


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        client.post("/api/admin/reset-sample")
        yield client


def test_overview_kpis(c):
    ov = c.get("/api/overview").json()
    k = ov["kpis"]
    assert k["active"] > 10
    assert 0 < k["expected_value"] < k["pipeline"]
    assert len(ov["forecast"]["quarters"]) >= 4
    assert ov["attention"], "seed data should flag at least one opportunity"


def test_scores_are_explainable_and_bounded(c):
    for o in c.get("/api/opportunities").json():
        s = o["score"]
        assert 0 <= s["p"] <= 1
        assert s["ev"] == pytest.approx(s["value"] * s["p"], rel=1e-3)
        if o["status"] not in scoring.INACTIVE:
            assert s["factors"][0]["key"] == "stage"
            assert len(s["trend"]) == 9


def test_negative_signals_lower_probability():
    cal = scoring.calibrate([])
    base = {"id": "X", "status": "Proposal", "outlook": "Neutral", "value": 1e8, "verified": "2999-01-01"}
    good = scoring.score({**base, "outlook": "Positive"}, [], [], cal)["p"]
    bad = scoring.score({**base, "outlook": "Negative"}, [], [{"status": "Blocked", "due": "2000-01-01"}], cal)["p"]
    assert good > bad


def test_ask_prd_examples(c):
    r = c.post("/api/ask", json={"question": "What is the revenue impact of blocked security deals in Saudi Arabia?"}).json()
    assert r["filters"]["domain"] == "Security" and r["filters"]["country"] == "Saudi Arabia" and r["filters"]["blocked"]
    assert r["summary"]["matched"] >= 1
    r = c.post("/api/ask", json={"question": "List all defense opportunities requiring CEO intervention"}).json()
    assert all(x["domain"] == "Defense" and x["intervention"] == "Yes" for x in r["rows"])
    r = c.post("/api/ask", json={"question": "ما هي الفرص الدفاعية في السعودية؟"}).json()
    assert r["filters"].get("domain") == "Defense"


def test_drafts_and_pr_gate(c):
    d = c.post("/api/opportunities/OPP-004/draft", json={"kind": "memo"}).json()
    assert "BLOCKER" in d["draft"] and d["status"] == "Draft for review"
    pr = c.post("/api/announcements/ANN-001/draft", json={}).json()
    assert pr["cleared"] is False and "NOT CLEARED" in pr["banner"]
    pr2 = c.post("/api/announcements/ANN-002/draft", json={}).json()
    assert pr2["cleared"] is True


def test_announcement_workflow(c):
    c.patch("/api/announcements/ANN-004", json={"ir": "approved", "counterparty": "Approved"})
    a = next(x for x in c.get("/api/announcements").json() if x["id"] == "ANN-004")
    assert a["cleared"] and a["readiness"] == "Approved" and a["ir"] == "Approved"


def test_extract_and_log_engagement(c):
    notes = ("Call with Ministry of Interior on the border data fusion JV, 3 Nov 2026.\n"
             "Agreed: revisit local content at 45%\nAction: send revised JV model by 20 Nov, owner Director Defense Programs")
    x = c.post("/api/engagements/extract", json={"text": notes}).json()
    e = x["engagement"]
    assert e["opp"] == "OPP-004" and e["type"] == "Call" and e["due"].endswith("-11-20")
    assert e["follow_up"] == "send revised JV model"
    r = c.post("/api/engagements", json={**e, "create_action": True}).json()
    assert r["record"]["id"].startswith("ENG-")


def test_ontology_normalises_synonyms():
    clean, warns = ontology.validate("opportunities", {"id": "OPP-900", "name": "t", "country": "KSA", "domain": "defence",
                                                       "status": "tender", "outlook": "إيجابي", "priority": 9})
    assert clean["country"] == "Saudi Arabia" and clean["domain"] == "Defense" and clean["status"] == "Proposal"
    assert clean["outlook"] == "Positive" and clean["priority"] == 5 and warns
    with pytest.raises(ValueError):
        ontology.validate("opportunities", {"id": "", "name": "x"})
    ttl = ontology.to_turtle()
    assert "owl:Class" in ttl and "skos:Concept" in ttl and "pc:precedes" in ttl


def test_graph(c):
    g = c.get("/api/graph?focus=OPP-001").json()
    rels = {e["relation"] for e in g["edges"]}
    assert {"hasCounterparty", "locatedIn", "hasPrediction", "explainedBy", "hasAction"} <= rels
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])


def test_template_and_roundtrip(c):
    t = c.get("/api/ingest/template")
    wb = load_workbook(io.BytesIO(t.content))
    assert {"Instructions", "Opportunities", "Engagement Log", "Actions & Milestones", "Announcements", "Lists"} <= set(wb.sheetnames)
    assert wb["Opportunities"].data_validations.dataValidation, "dropdowns expected"
    exp = c.get("/api/export").content
    before = len(c.get("/api/opportunities").json())
    r = c.post("/api/ingest/xlsx", files={"file": ("t.xlsx", exp)}, data={"mode": "replace"}).json()
    assert r["counts"]["opportunities"] == before
    assert len(c.get("/api/opportunities").json()) == before
    bad = c.post("/api/ingest/xlsx", files={"file": ("x.xlsx", b"not a workbook")})
    assert bad.status_code == 422


def test_crm_ingest(c):
    r = c.post("/api/ingest/crm", json={"opportunities": [{"id": "OPP-950", "name": "CRM sync test", "country": "Egypt",
                                                            "domain": "energy", "status": "Proposal", "value": 3e7}]}).json()
    assert r["counts"]["opportunities"] == 1
    o = c.get("/api/opportunities/OPP-950").json()
    assert o["domain"] == "Energy" and o["lat"] is not None


def test_discussions(c):
    r = c.post("/api/opportunities/OPP-001/discussions", json={"body": "CFO is aligned on pricing.", "author": "Thirumal"}).json()
    assert r["record"]["source"] == "precast" and r["posted_to_teams"] is False
    d = c.get("/api/opportunities/OPP-001").json()["discussions"]
    assert any("CFO" in x["body"] for x in d)


def test_geo_and_matrix(c):
    g = c.get("/api/geo").json()
    assert g["features"] and g["countries"][0]["value"] >= g["countries"][-1]["value"]
    m = c.get("/api/matrix").json()
    assert all(1 <= p["potential"] <= 5 for p in m["points"])


def test_kpis_and_reports(c):
    k = c.get("/api/kpis").json()
    assert len(k["kpis"]) == 14 and sum(k["summary"].values()) >= 12
    assert all(i["status"] in ("green", "amber", "red", "neutral") for i in k["kpis"])
    trended = [i for i in k["kpis"] if len(i["trend"]) == 8]
    assert len(trended) >= 5
    fk = c.get("/api/kpis?domain=Security&region=GCC").json()
    assert fk["headline"]["active"] < k["headline"]["active"] and "Security" in fk["scope"]
    cat = c.get("/api/reports").json()
    assert len(cat) == 9
    for r in cat:
        rep = c.get(f"/api/reports/{r['id']}?domain=Urban").json()
        assert rep["sections"] and rep["filters"] == {"domain": "Urban"}
        x = c.get(f"/api/reports/{r['id']}.xlsx")
        assert x.status_code == 200 and x.content[:2] == b"PK"
    assert c.get("/api/reports/nope").status_code == 404


def test_targets_change_status(c):
    c.put("/api/kpis/targets", json={"win_rate": 0.99})
    wr = next(i for i in c.get("/api/kpis").json()["kpis"] if i["key"] == "win_rate")
    assert wr["target"] == 0.99 and wr["status"] == "red"
    c.put("/api/kpis/targets", json={"win_rate": 0.5})
