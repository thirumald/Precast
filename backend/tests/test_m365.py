"""Microsoft Graph integration against a mocked Graph endpoint."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import db, ingest, m365
from app.main import app

CFG = {"tenant_id": "t", "client_id": "c", "client_secret": "s", "sp_site": "contoso.sharepoint.com:/sites/Strategy",
       "sp_tracker_path": "/Precast/Tracker.xlsx", "sp_opp_root": "/Precast/Opportunities", "teams_team_id": "team1",
       "teams_webhook": "", "outlook_mailbox": "strategy@contoso.com"}


def handler(request: httpx.Request) -> httpx.Response:
    u = str(request.url)
    if "login.microsoftonline.com" in u:
        return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    assert request.headers["Authorization"] == "Bearer tok"
    if u.endswith("/sites/contoso.sharepoint.com:/sites/Strategy"):
        return httpx.Response(200, json={"id": "site1"})
    if "/drive/root:" in u and u.endswith(":/content") and request.method == "GET":
        return httpx.Response(200, content=ingest.export_workbook())
    if "/drive/root:" in u and u.endswith(":/content") and request.method == "PUT":
        return httpx.Response(201, json={"webUrl": "https://sp/Tracker.xlsx"})
    if "/drive/root:" in u and u.endswith(":/children?$top=100"):
        return httpx.Response(200, json={"value": [{"name": "Proposal.docx", "webUrl": "https://sp/p.docx", "size": 10}]})
    if "/drive/root:" in u and request.method == "GET":
        return httpx.Response(200, json={"webUrl": "https://sp/folder", "folder": {}})
    if u.endswith("/teams/team1/channels") and request.method == "POST":
        body = json.loads(request.content)
        assert body["membershipType"] == "standard"
        return httpx.Response(201, json={"id": "19:chan", "webUrl": "https://teams/chan"})
    if "/channels/19:chan/messages?" in u:
        return httpx.Response(200, json={"value": [
            {"id": "m1", "messageType": "message", "createdDateTime": "2026-11-01T09:00:00Z",
             "from": {"user": {"displayName": "Sara"}}, "body": {"content": "<p>Client <b>agreed</b> the pricing</p>"}}]})
    if "/replies" in u:
        return httpx.Response(200, json={"value": [
            {"id": "m2", "replyToId": "m1", "messageType": "message", "createdDateTime": "2026-11-01T10:00:00Z",
             "from": {"user": {"displayName": "Omar"}}, "body": {"content": "Great news"}}]})
    if "/messages?$search=" in u:
        return httpx.Response(200, json={"value": [
            {"id": "mail1", "subject": "[OPP-001] Pricing follow-up", "receivedDateTime": "2099-01-01T08:00:00Z",
             "from": {"emailAddress": {"name": "Client CIO"}}, "bodyPreview": "Thanks for the call", "webLink": "https://o/1"}]})
    if "/calendarView" in u:
        return httpx.Response(200, json={"value": [
            {"id": "ev1", "subject": "Steering committee OPP-008", "start": {"dateTime": "2026-11-05T10:00:00"},
             "attendees": [{"emailAddress": {"name": "Agency DG"}}], "bodyPreview": "", "webLink": "https://o/e"}]})
    if u.endswith("/users/strategy@contoso.com/messages") and request.method == "POST":
        return httpx.Response(201, json={"id": "draft1", "webLink": "https://o/d"})
    if u.endswith("/users/strategy@contoso.com/events"):
        return httpx.Response(201, json={"id": "evt1", "webLink": "https://o/evt"})
    return httpx.Response(404, json={"error": {"message": "unmocked " + u}})


@pytest.fixture
def g():
    with TestClient(app):
        m365.Graph._token_cache.clear()
        yield m365.Graph(CFG, transport=httpx.MockTransport(handler))


def test_requires_config():
    with pytest.raises(m365.M365Error):
        m365.Graph({"tenant_id": ""})


def test_sharepoint_pull_push_folder(g):
    r = m365.sharepoint_pull(g)
    assert r["counts"]["opportunities"] > 0
    assert m365.sharepoint_push(g)["web_url"].startswith("https://sp")
    f = m365.sharepoint_folder("OPP-001", g)
    assert f["files"][0]["name"] == "Proposal.docx"
    assert db.get_row("opportunities", "OPP-001")["sharepoint_url"] == "https://sp/folder"


def test_teams_channel_and_sync(g):
    db.update("opportunities", "OPP-002", {"teams_channel_id": None, "teams_web_url": None})
    ch = m365.teams_channel("OPP-002", g)
    assert ch["created"] and ch["id"] == "19:chan"
    assert m365.teams_channel("OPP-002", g)["created"] is False
    assert m365.teams_sync("OPP-002", g)["added"] == 2
    assert m365.teams_sync("OPP-002", g)["added"] == 0  # idempotent
    msgs = db.all_rows("discussions", "opp='OPP-002' AND source='teams'")
    assert any(m["body"] == "Client agreed the pricing" for m in msgs)
    assert any(m["parent"] for m in msgs)


def test_outlook(g):
    r = m365.outlook_sync(30, g)
    opps = {e["opp"] for e in r["engagements"]}
    assert {"OPP-001", "OPP-008"} <= opps
    assert m365.outlook_sync(30, g)["added"] == 0
    assert m365.outlook_draft("[OPP-001] x", "body", ["a@b.com"], g)["id"] == "draft1"
    from datetime import datetime
    assert m365.outlook_event("OPP-001", datetime(2026, 12, 1, 10), 30, ["a@b.com"], graph=g)["id"] == "evt1"


def test_settings_mask_secrets():
    with TestClient(app) as c:
        s = c.put("/api/integrations/m365", json={"tenant_id": "abc", "client_secret": "topsecret"}).json()
        assert s["settings"]["client_secret"] == "••••••••"
        c.put("/api/integrations/m365", json={"client_secret": "••••••••"})
        assert m365.settings()["client_secret"] == "topsecret"
        c.put("/api/integrations/m365", json={"tenant_id": "", "client_secret": ""})
