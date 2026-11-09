"""Microsoft 365 integration over Microsoft Graph: SharePoint, Teams and Outlook.

Authentication is the OAuth 2.0 client-credentials flow for an Entra ID app registration
(app-only). Configure with environment variables or the Settings API:

  PRECAST_M365_TENANT_ID, PRECAST_M365_CLIENT_ID, PRECAST_M365_CLIENT_SECRET
  PRECAST_SP_SITE          e.g. contoso.sharepoint.com:/sites/StrategyOffice
  PRECAST_SP_TRACKER_PATH  e.g. /Precast/Strategic Opportunities Tracker.xlsx
  PRECAST_SP_OPP_ROOT      document-library folder for per-opportunity folders, e.g. /Precast/Opportunities
  PRECAST_TEAMS_TEAM_ID    the Team that holds one channel per opportunity
  PRECAST_TEAMS_WEBHOOK    optional Teams Workflows webhook used to post Precast messages to channels
  PRECAST_OUTLOOK_MAILBOX  shared mailbox / user whose mail and calendar are scanned (UPN)

Graph application permissions needed (admin consent):
  SharePoint  Sites.ReadWrite.All (or Sites.Selected for the one site)
  Teams       Channel.Create, ChannelMessage.Read.All (protected API, requires Microsoft approval), Team.ReadBasic.All
  Outlook     Mail.Read, Mail.ReadWrite (drafts), Calendars.ReadWrite  — scope with an application access policy
"""
from __future__ import annotations

import hashlib
import html
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx

from . import db

GRAPH = "https://graph.microsoft.com/v1.0"
KEYS = ["tenant_id", "client_id", "client_secret", "sp_site", "sp_tracker_path", "sp_opp_root",
        "teams_team_id", "teams_webhook", "outlook_mailbox"]
SECRET_KEYS = {"client_secret", "teams_webhook"}


class M365Error(RuntimeError):
    pass


def settings() -> dict[str, str]:
    out = {}
    for k in KEYS:
        env = os.getenv("PRECAST_" + ("M365_" if k in ("tenant_id", "client_id", "client_secret") else "") + k.upper())
        out[k] = db.get_setting("m365." + k) or env or ""
    return out


def save_settings(values: dict[str, str]) -> None:
    for k in KEYS:
        if k in values and values[k] is not None:
            v = str(values[k]).strip()
            if k in SECRET_KEYS and v and set(v) == {"•"}:
                continue  # masked value echoed back from the UI: keep stored secret
            db.set_setting("m365." + k, v or None)


def status() -> dict:
    s = settings()
    auth = bool(s["tenant_id"] and s["client_id"] and s["client_secret"])
    masked = {k: ("••••••••" if k in SECRET_KEYS and v else v) for k, v in s.items()}
    return {
        "configured": auth,
        "sharepoint": auth and bool(s["sp_site"]),
        "teams": auth and bool(s["teams_team_id"]),
        "teams_posting": bool(s["teams_webhook"]),
        "outlook": auth and bool(s["outlook_mailbox"]),
        "settings": masked,
        "last_sync": {k: db.get_setting("m365.last." + k) for k in ("sharepoint", "teams", "outlook")},
    }


class Graph:
    """Thin Graph client. `transport` lets tests inject an httpx.MockTransport."""

    _token_cache: dict[str, tuple[str, float]] = {}

    def __init__(self, cfg: dict[str, str] | None = None, transport: httpx.BaseTransport | None = None):
        self.cfg = cfg or settings()
        if not (self.cfg.get("tenant_id") and self.cfg.get("client_id") and self.cfg.get("client_secret")):
            raise M365Error("Microsoft 365 is not configured. Add the tenant ID, client ID and client secret in Data & Integrations.")
        self.http = httpx.Client(transport=transport, timeout=30)

    def token(self) -> str:
        key = self.cfg["tenant_id"] + self.cfg["client_id"]
        tok = self._token_cache.get(key)
        if tok and tok[1] > time.time() + 60:
            return tok[0]
        r = self.http.post(
            f"https://login.microsoftonline.com/{self.cfg['tenant_id']}/oauth2/v2.0/token",
            data={"client_id": self.cfg["client_id"], "client_secret": self.cfg["client_secret"],
                  "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"})
        if r.status_code != 200:
            raise M365Error(f"Sign-in to Microsoft Entra ID failed ({r.status_code}): {r.text[:200]}")
        j = r.json()
        self._token_cache[key] = (j["access_token"], time.time() + int(j.get("expires_in", 3599)))
        return j["access_token"]

    def req(self, method: str, path: str, **kw) -> httpx.Response:
        url = path if path.startswith("http") else GRAPH + path
        headers = {"Authorization": f"Bearer {self.token()}", **kw.pop("headers", {})}
        for attempt in range(3):
            r = self.http.request(method, url, headers=headers, **kw)
            if r.status_code in (429, 503) and attempt < 2:
                time.sleep(min(10, int(r.headers.get("Retry-After", "2"))))
                continue
            break
        if r.status_code >= 400:
            msg = r.text[:300]
            try:
                msg = r.json().get("error", {}).get("message", msg)
            except Exception:  # noqa: BLE001
                pass
            raise M365Error(f"Graph {method} {path.split('?')[0]} failed ({r.status_code}): {msg}")
        return r

    def get(self, path: str, **kw) -> dict:
        return self.req("GET", path, **kw).json()

    def paged(self, path: str, limit: int = 500) -> list[dict]:
        out, url = [], path
        while url and len(out) < limit:
            j = self.get(url)
            out.extend(j.get("value", []))
            url = j.get("@odata.nextLink")
        return out[:limit]

    # ---------------- SharePoint
    def site_id(self) -> str:
        site = self.cfg.get("sp_site")
        if not site:
            raise M365Error("Set the SharePoint site (e.g. contoso.sharepoint.com:/sites/Strategy).")
        cached = db.get_setting("m365.cache.site_id." + site)
        if cached:
            return cached
        sid = self.get(f"/sites/{site}")["id"]
        db.set_setting("m365.cache.site_id." + site, sid)
        return sid

    def download(self, path: str) -> bytes:
        return self.req("GET", f"/sites/{self.site_id()}/drive/root:{quote(path)}:/content").content

    def upload(self, path: str, content: bytes) -> dict:
        return self.req("PUT", f"/sites/{self.site_id()}/drive/root:{quote(path)}:/content", content=content,
                        headers={"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}).json()

    def ensure_folder(self, path: str) -> dict:
        try:
            return self.get(f"/sites/{self.site_id()}/drive/root:{quote(path)}")
        except M365Error:
            parent, name = path.rstrip("/").rsplit("/", 1)
            parent_ref = f"/sites/{self.site_id()}/drive/root" + (f":{quote(parent)}:" if parent else "")
            return self.req("POST", f"{parent_ref}/children",
                            json={"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "replace"}).json()

    def list_folder(self, path: str) -> list[dict]:
        return self.paged(f"/sites/{self.site_id()}/drive/root:{quote(path)}:/children?$top=100")

    # ---------------- Teams
    def create_channel(self, name: str, description: str) -> dict:
        team = self.cfg.get("teams_team_id")
        if not team:
            raise M365Error("Set the Teams team ID that will hold opportunity channels.")
        return self.req("POST", f"/teams/{team}/channels",
                        json={"displayName": name[:50], "description": description[:1024], "membershipType": "standard"}).json()

    def channel_messages(self, channel_id: str, limit: int = 200) -> list[dict]:
        team = self.cfg["teams_team_id"]
        msgs = self.paged(f"/teams/{team}/channels/{channel_id}/messages?$top=50", limit)
        out = []
        for m in msgs:
            out.append(m)
            if m.get("id"):
                try:
                    out.extend(self.paged(f"/teams/{team}/channels/{channel_id}/messages/{m['id']}/replies?$top=50", 100))
                except M365Error:
                    pass
        return out

    # ---------------- Outlook
    def mailbox(self) -> str:
        mb = self.cfg.get("outlook_mailbox")
        if not mb:
            raise M365Error("Set the Outlook mailbox (UPN) Precast should read.")
        return mb

    def search_mail(self, query: str, top: int = 25) -> list[dict]:
        q = quote(f'"{query}"')
        return self.get(f"/users/{self.mailbox()}/messages?$search={q}&$top={top}"
                        "&$select=id,subject,from,toRecipients,ccRecipients,receivedDateTime,bodyPreview,webLink,conversationId",
                        headers={"ConsistencyLevel": "eventual"}).get("value", [])

    def calendar(self, start: datetime, end: datetime) -> list[dict]:
        s, e = start.strftime("%Y-%m-%dT%H:%M:%S"), end.strftime("%Y-%m-%dT%H:%M:%S")
        return self.paged(f"/users/{self.mailbox()}/calendarView?startDateTime={s}&endDateTime={e}&$top=100"
                          "&$select=id,subject,start,end,organizer,attendees,bodyPreview,webLink,location", 500)

    def create_draft(self, subject: str, body: str, to: list[str]) -> dict:
        return self.req("POST", f"/users/{self.mailbox()}/messages", json={
            "subject": subject, "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": a}} for a in to if a]}).json()

    def create_event(self, subject: str, body: str, start: datetime, minutes: int, attendees: list[str], tz: str) -> dict:
        end = start + timedelta(minutes=minutes)
        return self.req("POST", f"/users/{self.mailbox()}/events", json={
            "subject": subject, "body": {"contentType": "Text", "content": body},
            "start": {"dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": tz},
            "end": {"dateTime": end.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": tz},
            "attendees": [{"emailAddress": {"address": a}, "type": "required"} for a in attendees if a]}).json()


def _strip_html(s: str) -> str:
    s = re.sub(r"<(br|/p|/div)\s*/?>", "\n", s or "", flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _stamp(key: str) -> None:
    db.set_setting("m365.last." + key, datetime.now(timezone.utc).isoformat(timespec="seconds"))


# ---------------------------------------------------------------- SharePoint operations
def sharepoint_pull(graph: Graph | None = None, mode: str = "merge") -> dict:
    from . import ingest
    g = graph or Graph()
    path = g.cfg.get("sp_tracker_path")
    if not path:
        raise M365Error("Set the tracker workbook path in the SharePoint document library.")
    res = ingest.import_workbook(g.download(path), mode=mode)
    _stamp("sharepoint")
    return {**res, "source": f"SharePoint:{path}"}


def sharepoint_push(graph: Graph | None = None) -> dict:
    from . import ingest
    g = graph or Graph()
    path = g.cfg.get("sp_tracker_path") or "/Precast/Strategic Opportunities Tracker.xlsx"
    item = g.upload(path, ingest.export_workbook())
    _stamp("sharepoint")
    return {"path": path, "web_url": item.get("webUrl")}


def sharepoint_folder(oid: str, graph: Graph | None = None) -> dict:
    g = graph or Graph()
    o = db.get_row("opportunities", oid)
    if not o:
        raise KeyError(oid)
    root = (g.cfg.get("sp_opp_root") or "/Precast/Opportunities").rstrip("/")
    safe = re.sub(r'[~"#%&*:<>?/\\{|}]', "-", f"{oid} {o['name']}")[:120].strip()
    folder = g.ensure_folder(f"{root}/{safe}")
    db.update("opportunities", oid, {"sharepoint_url": folder.get("webUrl")})
    files = [{"name": f["name"], "web_url": f.get("webUrl"), "modified": f.get("lastModifiedDateTime"),
              "size": f.get("size"), "folder": "folder" in f} for f in g.list_folder(f"{root}/{safe}")]
    return {"web_url": folder.get("webUrl"), "files": files}


# ---------------------------------------------------------------- Teams operations
def teams_channel(oid: str, graph: Graph | None = None) -> dict:
    g = graph or Graph()
    o = db.get_row("opportunities", oid)
    if not o:
        raise KeyError(oid)
    if o.get("teams_channel_id"):
        return {"id": o["teams_channel_id"], "web_url": o.get("teams_web_url"), "created": False}
    ch = g.create_channel(f"{oid} {o['name']}", f"Precast discussion for {o['name']} ({o.get('counterparty') or ''}).")
    db.update("opportunities", oid, {"teams_channel_id": ch.get("id"), "teams_web_url": ch.get("webUrl")})
    return {"id": ch.get("id"), "web_url": ch.get("webUrl"), "created": True}


def teams_sync(oid: str, graph: Graph | None = None) -> dict:
    g = graph or Graph()
    o = db.get_row("opportunities", oid)
    if not o or not o.get("teams_channel_id"):
        raise M365Error("This opportunity has no Teams channel yet. Create one first.")
    have = {d["external_id"] for d in db.all_rows("discussions", "opp=? AND source='teams'", (oid,)) if d.get("external_id")}
    added = 0
    for m in g.channel_messages(o["teams_channel_id"]):
        if m.get("messageType") not in (None, "message") or m.get("deletedDateTime") or m["id"] in have:
            continue
        body = _strip_html((m.get("body") or {}).get("content", ""))
        if not body:
            continue
        author = ((m.get("from") or {}).get("user") or {}).get("displayName") or \
                 ((m.get("from") or {}).get("application") or {}).get("displayName") or "Teams"
        db.upsert("discussions", {"id": "TMS-" + hashlib.sha1(m["id"].encode()).hexdigest()[:12], "opp": oid,
                                  "parent": ("TMS-" + hashlib.sha1(m["replyToId"].encode()).hexdigest()[:12]) if m.get("replyToId") else None,
                                  "author": author, "body": body, "created": m.get("createdDateTime"), "source": "teams",
                                  "external_id": m["id"], "web_url": m.get("webUrl")})
        added += 1
    _stamp("teams")
    return {"added": added}


def teams_post(oid: str, text: str, author: str, transport: httpx.BaseTransport | None = None) -> bool:
    """Post a Precast discussion message to the opportunity's channel via a Teams Workflows webhook.

    Graph does not allow app-only posting of channel messages, so a Workflows webhook is used.
    The flow should post the card to the channel named in `channel`.
    """
    s = settings()
    if not s.get("teams_webhook"):
        return False
    o = db.get_row("opportunities", oid) or {}
    card = {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {
        "type": "AdaptiveCard", "version": "1.4", "body": [
            {"type": "TextBlock", "text": f"{oid} · {o.get('name', '')}", "weight": "Bolder", "wrap": True},
            {"type": "TextBlock", "text": text, "wrap": True},
            {"type": "TextBlock", "text": f"— {author} via Precast", "isSubtle": True, "size": "Small"}]}}],
        "channel": o.get("teams_channel_id"), "opportunity": oid}
    try:
        r = httpx.Client(transport=transport, timeout=15).post(s["teams_webhook"], json=card)
        return r.status_code < 300
    except httpx.HTTPError:
        return False


# ---------------------------------------------------------------- Outlook operations
def _addr(r: dict | None) -> str:
    e = (r or {}).get("emailAddress") or {}
    return e.get("name") or e.get("address") or ""


def outlook_sync(days: int = 30, graph: Graph | None = None, only: str | None = None) -> dict:
    """Log emails and meetings tied to an opportunity into the Engagement Log.

    A message or meeting is tied to an opportunity when its subject carries the tag [OPP-001]
    (recommended convention) or mentions the counterparty name. Re-running is idempotent.
    """
    g = graph or Graph()
    opps = [o for o in db.all_rows("opportunities") if not o["id"].startswith("HIS-")
            and o.get("status") not in ("Closed Won", "Closed Lost") and (not only or o["id"] == only)]
    have = {e["id"] for e in db.all_rows("engagements", "source LIKE 'outlook%'")}
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    added: list[dict] = []

    def match(text: str) -> str | None:
        m = re.search(r"\[?(OPP-\d{3,})\]?", text or "", re.I)
        if m and any(o["id"] == m.group(1).upper() for o in opps):
            return m.group(1).upper()
        low = (text or "").lower()
        for o in opps:
            cp = (o.get("counterparty") or "").replace("Example:", "").strip().lower()
            if len(cp) > 5 and cp in low:
                return o["id"]
        return None

    def add(eid: str, oid: str, d: str, typ: str, summary: str, ext: str, url: str | None) -> None:
        if eid in have:
            return
        db.upsert("engagements", {"id": eid, "opp": oid, "date": d[:10], "type": typ, "summary": summary[:600],
                                  "external": ext[:300], "internal": g.cfg.get("outlook_mailbox", ""),
                                  "source": "outlook", "link": url})
        have.add(eid)
        added.append({"id": eid, "opp": oid, "type": typ, "date": d[:10]})

    terms = {o["id"] for o in opps} | {(o.get("counterparty") or "").replace("Example:", "").strip() for o in opps}
    for term in sorted(t for t in terms if t):
        for m in g.search_mail(term, top=15):
            rcv = m.get("receivedDateTime") or ""
            try:
                if datetime.fromisoformat(rcv.replace("Z", "+00:00")) < cutoff:
                    continue
            except ValueError:
                continue
            oid = match((m.get("subject") or "") + " " + (m.get("bodyPreview") or ""))
            if oid:
                add("OUT-M-" + hashlib.sha1(m["id"].encode()).hexdigest()[:10], oid, rcv, "Email",
                    f"{m.get('subject')}: {m.get('bodyPreview') or ''}", _addr(m.get("from")), m.get("webLink"))
    now = datetime.now(timezone.utc)
    for ev in g.calendar(now - timedelta(days=days), now):
        oid = match((ev.get("subject") or "") + " " + (ev.get("bodyPreview") or ""))
        if oid:
            att = ", ".join(_addr(a) for a in ev.get("attendees", [])[:8])
            add("OUT-C-" + hashlib.sha1(ev["id"].encode()).hexdigest()[:10], oid, (ev.get("start") or {}).get("dateTime", ""),
                "Meeting", f"{ev.get('subject')}: {ev.get('bodyPreview') or ''}", att, ev.get("webLink"))
    for oid in {a["opp"] for a in added}:
        last = max(e["date"] for e in db.all_rows("engagements", "opp=?", (oid,)))
        db.update("opportunities", oid, {"last_engagement": last})
    _stamp("outlook")
    return {"added": len(added), "engagements": added}


def outlook_draft(subject: str, body: str, to: list[str], graph: Graph | None = None) -> dict:
    g = graph or Graph()
    m = g.create_draft(subject, body, to)
    return {"id": m.get("id"), "web_url": m.get("webLink")}


def outlook_event(oid: str, when: datetime, minutes: int, attendees: list[str], tz: str = "Arabian Standard Time",
                  graph: Graph | None = None) -> dict:
    g = graph or Graph()
    o = db.get_row("opportunities", oid)
    if not o:
        raise KeyError(oid)
    ev = g.create_event(f"[{oid}] {o.get('milestone') or o['name']}",
                        f"{o['name']} ({o.get('counterparty')})\nNext action: {o.get('next_action') or ''}\nScheduled from Precast.",
                        when, minutes, attendees, tz)
    return {"id": ev.get("id"), "web_url": ev.get("webLink")}
