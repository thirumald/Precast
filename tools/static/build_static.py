"""Build the static, offline edition of Precast into ./static.

    cd frontend && npm run build:static      # bundle -> static/assets
    python tools/static/build_static.py      # snapshot, downloads, one HTML page per use case

The script starts the real backend in-process on a fresh database (sample data, template engine),
records every API response the pages need into static/data/snapshot.js, exports the Excel and
ontology downloads, and writes the HTML pages. Point PRECAST_DB at a copy of a production
database to snapshot real data instead (handle the output as Confidential).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "static"
os.environ.setdefault("PRECAST_DB", str(Path(tempfile.mkdtemp()) / "static.db"))
os.environ.setdefault("PRECAST_LLM_ENABLED", "0")
os.environ["PRECAST_STATIC"] = str(Path(tempfile.mkdtemp()) / "none")
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

ASK = [  # suggestions shown on the Ask page (answered by the server logic at build time)
    "What is the revenue impact of blocked security deals in Saudi Arabia?",
    "List all defense opportunities requiring CEO intervention",
    "Which deals are at risk this quarter?",
    "How many opportunities are in negotiation?",
    "ما هي الفرص الدفاعية التي تتطلب تدخل الرئيس التنفيذي؟",
    "ما قيمة خط الأنابيب في الإمارات؟",
]
SAMPLE_NOTES = """Meeting with Municipal Development Authority (Riyadh) on smart city phase 2 — 6 Nov 2026.
Attendees: Deputy Mayor's office, CIO
Presight: Director Urban Solutions, solution architect
Pilot KPIs reviewed; the authority is supportive and keen to accelerate phase 2 scope.
Agreed: phased rollout across 12 districts, local partner annex required
Action: submit revised proposal with partner annex by 20 Nov, owner Director Urban Solutions"""

# (file, title, route, description, group)
PAGES = [
    ("executive-dashboard", "Executive Dashboard", "executive", "Top-management KPI scorecard against target with trends, summary and decisions required.", "Executive"),
    ("pipeline-overview", "Pipeline Overview", "overview", "Pipeline, expected value, quarterly forecast, probability movers, attention list and milestones.", "Pipeline"),
    ("forecast-scoring", "Forecast & Scoring", "forecast", "Six-quarter forecast, model calibration and explainable win probability for every deal.", "Pipeline"),
    ("executive-matrix", "Executive Matrix", "matrix", "Priority × commercial potential with AI potential and next-week movement vectors.", "Pipeline"),
    ("geospatial", "Geospatial Intelligence", "map", "Opportunities on an offline map with clustering, value-at-risk heat and competitor density.", "Pipeline"),
    ("interventions", "Interventions", "interventions", "Deals needing executive action, ordered by value at risk, with drafted briefing memos.", "Action"),
    ("announcements", "Announcement Readiness", "announcements", "Legal, IR and counterparty clearance workflow with gated press-release drafts.", "Action"),
    ("engagement-log", "Engagement Log", "engagements", "Engagement history and AI extraction of meeting notes into structured entries.", "Action"),
    ("opportunity-register", "Opportunity Register", "register", "Sortable, filterable register with probability and expected value.", "Pipeline"),
    ("opportunity-360", "Opportunity 360", "register", "One opportunity end to end: summary, prediction drivers, activity, discussion, graph, workspace.", "Pipeline"),
    ("ask-precast", "Ask Precast", "ask", "Bilingual natural-language questions answered from computed figures.", "AI"),
    ("ontology-graph", "Ontology & Knowledge Graph", "ontology", "The Precast ontology and the portfolio knowledge graph.", "AI"),
    ("data-integrations", "Data & Integrations", "data", "Excel tracker template, CRM API, local LLM and Microsoft 365 (SharePoint, Teams, Outlook).", "Platform"),
]
OPP_360 = "OPP-004"


def qs(params: dict) -> str:
    items = sorted((k, v) for k, v in params.items() if v)
    return ("?" + urlencode(items)) if items else ""


def main() -> None:
    get: dict[str, object] = {}
    post: dict[str, object] = {}
    with TestClient(app) as c:
        c.post("/api/admin/reset-sample")

        def g(path: str) -> object:
            r = c.get(path)
            r.raise_for_status()
            get[path] = r.json()
            return get[path]

        for p in ["/api/health", "/api/llm/status", "/api/overview", "/api/opportunities", "/api/opportunities?include_closed=false",
                  "/api/opportunities?include_closed=true", "/api/forecast?quarters=6", "/api/matrix?potential=dynamic",
                  "/api/matrix?potential=manual", "/api/geo", "/api/engagements", "/api/actions", "/api/announcements",
                  "/api/ontology", "/api/graph", "/api/integrations/m365", "/api/kpis/targets", "/api/reports"]:
            g(p)
        opts = g("/api/filters")
        for o in get["/api/opportunities"]:
            g(f"/api/opportunities/{o['id']}")
            if o["status"] not in ("Closed Won", "Closed Lost", "On Hold"):
                g(f"/api/graph?focus={o['id']}")
            for kind in ("memo", "email"):
                post[f"/api/opportunities/{o['id']}/draft|{kind}"] = c.post(f"/api/opportunities/{o['id']}/draft", json={"kind": kind}).json()
        for a in get["/api/announcements"]:
            post[f"/api/announcements/{a['id']}/draft|memo"] = c.post(f"/api/announcements/{a['id']}/draft", json={}).json()
        for q in ASK:
            post[f"/api/ask|{q}"] = c.post("/api/ask", json={"question": q}).json()
        post[f"/api/engagements/extract|{SAMPLE_NOTES.strip()}"] = c.post("/api/engagements/extract", json={"text": SAMPLE_NOTES}).json()

        # KPIs and every report: unfiltered plus each single filter value.
        reports = [r["id"] for r in get["/api/reports"]]
        variants = [{}] + [{k: v} for k, vals in opts.items() for v in vals]
        for f in variants:
            g("/api/kpis" + qs(f))
            for rid in reports:
                g(f"/api/reports/{rid}" + qs(f))

        dl = OUT / "downloads"
        if dl.exists():
            shutil.rmtree(dl)
        (dl / "reports").mkdir(parents=True)
        (dl / "Precast_Tracker_Template.xlsx").write_bytes(c.get("/api/ingest/template").content)
        (dl / "Precast_Tracker_Template_blank.xlsx").write_bytes(c.get("/api/ingest/template?examples=false").content)
        (dl / "Precast_Tracker_Export.xlsx").write_bytes(c.get("/api/export").content)
        (dl / "precast-ontology.ttl").write_text(c.get("/api/ontology.ttl").text, encoding="utf-8")
        (dl / "precast-ontology.jsonld").write_text(c.get("/api/ontology.jsonld").text, encoding="utf-8")
        for rid in reports:
            (dl / "reports" / f"Precast_{rid}.xlsx").write_bytes(c.get(f"/api/reports/{rid}.xlsx").content)

    built = date.today().isoformat()
    snap = {"built": built, "get": get, "post": post}
    (OUT / "data").mkdir(parents=True, exist_ok=True)
    body = json.dumps(snap, ensure_ascii=False, separators=(",", ":"), default=str)
    (OUT / "data" / "snapshot.js").write_text(
        "/* Precast static snapshot — generated by tools/static/build_static.py. Illustrative sample data. */\n"
        f"window.__PRECAST_SNAPSHOT__={body};\n", encoding="utf-8")

    brand = OUT / "brand"
    brand.mkdir(exist_ok=True)
    for f in ("presight-logo.svg", "presight-logo-white.svg"):
        shutil.copy(ROOT / "frontend" / "public" / "brand" / f, brand / f)
    shutil.copy(ROOT / "frontend" / "public" / "favicon.svg", OUT / "favicon.svg")

    def page(file: str, title: str, route: str, opp: str | None = None) -> str:
        boot = f'window.__PRECAST_ROUTE__="{route}";' + (f'window.__PRECAST_OPEN_OPP__="{opp}";' if opp else "")
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · Precast</title>
<meta name="description" content="Precast by Presight: {title}. Static edition, data snapshot {built}.">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<div id="root"></div>
<noscript>Precast needs JavaScript enabled.</noscript>
<script>{boot}</script>
<script src="data/snapshot.js"></script>
<script src="assets/precast.js"></script>
</body>
</html>
"""

    for file, title, route, _, _ in PAGES:
        (OUT / f"{file}.html").write_text(page(file, title, route, OPP_360 if file == "opportunity-360" else None), encoding="utf-8")
    report_pages = []
    for r in get["/api/reports"]:
        fname = f"report-{r['id']}"
        (OUT / f"{fname}.html").write_text(page(fname, r["title"], f"reports/{r['id']}"), encoding="utf-8")
        report_pages.append((fname, r))

    k = get["/api/kpis"]
    h = k["headline"]
    fmt = lambda v: f"AED {v / 1e9:.2f}bn" if v >= 1e9 else f"AED {v / 1e6:.1f}m"  # noqa: E731

    def card(href: str, title: str, desc: str, tag: str) -> str:
        return f'<a class="card" href="{href}"><span class="tag">{tag}</span><b>{title}</b><span>{desc}</span><i>Open →</i></a>'

    groups = {}
    for file, title, _, desc, grp in PAGES:
        groups.setdefault(grp, []).append(card(f"{file}.html", title, desc, grp))
    index = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Precast · Strategic Intelligence Hub · Use cases</title>
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="assets/style.css">
<style>
body{{margin:0;background:var(--bg)}}
.wrap{{max-width:1240px;margin:0 auto;padding:40px 24px 64px;display:flex;flex-direction:column;gap:28px}}
.hero{{display:flex;flex-direction:column;gap:14px;padding:32px;border-radius:16px;background:linear-gradient(135deg,#0D1A22 0%,#0A3F48 60%,#0A6E7C 100%);color:#fff}}
.hero img{{height:40px;width:auto;align-self:flex-start}}
.hero h1{{font-size:clamp(30px,4vw,44px);letter-spacing:-.02em}}
.hero .t{{color:#9FE3EA;font-weight:600;letter-spacing:.02em}}
.hero p{{margin:0;max-width:70ch;color:#C9D6DB;font-size:15.5px}}
.stats{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:8px}}
.stats div{{background:rgba(255,255,255,.08);border-radius:10px;padding:12px 14px}}
.stats span{{display:block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#9FB8BF}}
.stats b{{font-family:var(--f-display);font-size:24px}}
h2{{font-size:13px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px}}
.card{{display:flex;flex-direction:column;gap:6px;padding:16px;border-radius:12px;background:var(--surface);border:1px solid var(--line);color:var(--ink);text-decoration:none;min-height:150px}}
.card:hover{{border-color:var(--accent);box-shadow:0 4px 18px rgba(0,0,0,.06)}}
.card b{{font-family:var(--f-display);font-size:16.5px}}
.card span{{color:var(--muted);font-size:13.5px}}
.card .tag{{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);font-weight:600}}
.card i{{margin-top:auto;font-style:normal;color:var(--accent);font-weight:600;font-size:13px}}
.note{{font-size:13px;color:var(--muted);border-top:1px solid var(--line);padding-top:16px}}
@media (max-width:760px){{.stats{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <img src="brand/presight-logo-white.svg" alt="Presight">
    <div class="t">Predict. Forecast. Precast.</div>
    <h1>Precast · Strategic Intelligence Hub</h1>
    <p>AI-native command centre for the strategic pipeline: explainable win probabilities, risk-weighted forecasts, executive KPIs and reports, drafted interventions, bilingual Q&amp;A, ontology and Microsoft 365 integration. Every page below is a working, offline view of one use case.</p>
    <div class="stats">
      <div><span>Active opportunities</span><b>{h['active']}</b></div>
      <div><span>Pipeline</span><b>{fmt(h['pipeline'])}</b></div>
      <div><span>Risk-weighted</span><b>{fmt(h['ev'])}</b></div>
      <div><span>KPIs on / near / off target</span><b>{k['summary']['green']} / {k['summary']['amber']} / {k['summary']['red']}</b></div>
    </div>
  </header>
  {''.join(f'<section><h2>{grp}</h2><div class="cards">{"".join(cs)}</div></section>' for grp, cs in groups.items())}
  <section><h2>Management reports</h2><div class="cards">{''.join(card(f + '.html', r['title'], r['description'], r['audience']) for f, r in report_pages)}</div></section>
  <section><h2>Downloads</h2><div class="cards">
    {card('downloads/Precast_Tracker_Template.xlsx', 'Excel tracker template', 'Sheets, dropdowns and an example row per sheet; loads into Precast unchanged.', 'Excel')}
    {card('downloads/Precast_Tracker_Export.xlsx', 'Sample data export', 'The sample register in tracker layout.', 'Excel')}
    {card('downloads/precast-ontology.ttl', 'Ontology (OWL/Turtle)', 'Classes, relations and bilingual vocabularies.', 'Ontology')}
  </div></section>
  <p class="note">Static edition built {built} from illustrative sample data (every counterparty is prefixed “Example:”). Pages open directly from disk or any static web host. Read-only: editing, live AI generation, imports and Microsoft 365 sync need the full Precast app (<code>docker compose up</code>). Filters cover one value at a time.</p>
</div>
</body>
</html>
"""
    (OUT / "index.html").write_text(index, encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    size = (OUT / "data" / "snapshot.js").stat().st_size
    print(f"static edition: {len(PAGES) + len(report_pages) + 1} pages, snapshot {size / 1e6:.1f} MB, "
          f"{len(get)} GET + {len(post)} POST responses")


if __name__ == "__main__":
    main()
