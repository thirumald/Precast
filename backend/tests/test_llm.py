"""LLM code paths against a fake OpenAI-compatible endpoint (no model needed)."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config, llm
from app.main import app


class Fake:
    def __init__(self):
        self.calls = []

    def get(self, url, **kw):
        return httpx.Response(200, json={"data": [{"id": "qwen2.5:3b-instruct"}]}, request=httpx.Request("GET", url))

    def post(self, url, json=None, **kw):  # noqa: A002
        self.calls.append(json)
        sys = json["messages"][0]["content"]
        if "convert executive questions" in sys:
            content = '{"domain": "defence", "country": "KSA", "stage": null, "intervention": true, "metric": "list"}'
        elif "Extract a CRM engagement" in sys:
            content = '{"opportunity_id": "OPP-008", "type": "Workshop", "date": "2026-11-02", "summary": "Fusion centre workshop.", "follow_up_action": "Send pack", "due_date": "2026-11-20"}'
        else:
            content = "Generated text"
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]}, request=httpx.Request("POST", url))


@pytest.fixture
def fake(monkeypatch):
    f = Fake()
    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(llm.httpx, "get", f.get)
    monkeypatch.setattr(llm.httpx, "post", f.post)
    llm._status.update(ok=None, checked=0)
    yield f
    llm._status.update(ok=None, checked=0)


def test_llm_paths(fake):
    with TestClient(app) as c:
        r = c.post("/api/ask", json={"question": "defence deals needing CEO help in KSA"}).json()
        assert r["engine"] == "llm" and r["answer"] == "Generated text"
        # model output is snapped onto ontology terms
        assert r["filters"]["domain"] == "Defense" and r["filters"]["country"] == "Saudi Arabia"
        d = c.post("/api/opportunities/OPP-004/draft", json={"kind": "email", "lang": "ar"}).json()
        assert d["engine"] == "llm"
        assert "Arabic" in fake.calls[-1]["messages"][0]["content"]
        x = c.post("/api/engagements/extract", json={"text": "workshop notes, nothing else"}).json()
        assert x["engine"] == "llm" and x["engagement"]["opp"] == "OPP-008" and x["engagement"]["type"] == "Workshop"


def test_llm_down_falls_back(monkeypatch):
    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(config, "LLM_BASE_URL", "http://127.0.0.1:9")
    llm._status.update(ok=None, checked=0)
    with TestClient(app) as c:
        r = c.post("/api/ask", json={"question": "how many opportunities are in negotiation?"}).json()
        assert r["engine"] == "template" and r["summary"]["matched"] >= 1
    llm._status.update(ok=None, checked=0)
