import { useRef, useState } from "react";
import { api, apiKey, type M365Status } from "../api";
import { Chip, Loading, useApp, useData } from "../ui";

type Import = { mode: string; counts: Record<string, number>; warnings: string[]; skipped: number; file?: string; source?: string };
type LLM = { available: boolean; engine: string; model?: string; endpoint?: string; detail?: string };

const FIELDS: [string, string, string][] = [
  ["tenant_id", "Directory (tenant) ID", "Entra ID → App registrations → Overview"],
  ["client_id", "Application (client) ID", ""],
  ["client_secret", "Client secret", "Stored in the Precast database; shown masked"],
  ["sp_site", "SharePoint site", "contoso.sharepoint.com:/sites/StrategyOffice"],
  ["sp_tracker_path", "Tracker workbook path", "/Precast/Strategic Opportunities Tracker.xlsx"],
  ["sp_opp_root", "Opportunity folders root", "/Precast/Opportunities"],
  ["teams_team_id", "Teams team ID", "The team that holds one channel per opportunity"],
  ["teams_webhook", "Teams Workflows webhook (optional)", "Lets Precast post discussion messages into channels"],
  ["outlook_mailbox", "Outlook mailbox (UPN)", "strategy-office@contoso.com"],
];

export default function Data() {
  const { toast, bump } = useApp();
  const file = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"merge" | "replace">("merge");
  const [res, setRes] = useState<Import | null>(null);
  const [busy, setBusy] = useState("");
  const llm = useData(() => api.get<LLM>("/api/llm/status"));
  const m365 = useData(() => api.get<M365Status>("/api/integrations/m365"));
  const [cfg, setCfg] = useState<Record<string, string> | null>(null);
  const [key, setKey] = useState(apiKey.get());
  const s = cfg ?? m365.data?.settings ?? {};

  async function upload(f?: File | null) {
    if (!f) return;
    setBusy("upload");
    const fd = new FormData(); fd.append("file", f); fd.append("mode", mode);
    try { const r = await api.upload<Import>("/api/ingest/xlsx", fd); setRes(r); bump(); toast(`Loaded ${r.counts.opportunities ?? 0} opportunities`); }
    catch (e) { toast((e as Error).message); }
    setBusy(""); if (file.current) file.current.value = "";
  }
  async function act<T>(k: string, fn: () => Promise<T>, msg: (r: T) => string) {
    setBusy(k);
    try { const r = await fn(); toast(msg(r)); bump(); m365.reload(); } catch (e) { toast((e as Error).message); }
    setBusy("");
  }
  const st = m365.data;
  return (
    <>
      <section className="grid g2">
        <div className="panel">
          <div className="ph"><h2>Tracker workbook</h2><span className="hint">Same sheets and columns as the MVP tracker</span></div>
          <div className="filters">
            <a className="btn primary" href="/api/ingest/template" download>Download Excel template</a>
            <a className="btn" href="/api/ingest/template?examples=false" download>Blank template</a>
            <a className="btn" href="/api/export" download>Export current data</a>
          </div>
          <p className="hint">The template has Instructions, Opportunities, Engagement Log, Actions & Milestones and Announcements sheets, with dropdowns from the ontology and an example row in each sheet.</p>
          <div className="filters">
            <div className="seg" role="group" aria-label="Import mode">
              <button aria-pressed={mode === "merge"} onClick={() => setMode("merge")}>Merge (update + add)</button>
              <button aria-pressed={mode === "replace"} onClick={() => setMode("replace")}>Replace register</button>
            </div>
            <button className="btn primary" disabled={!!busy} onClick={() => file.current?.click()}>{busy === "upload" ? <span className="spin" /> : null} Load tracker (.xlsx)</button>
            <input ref={file} type="file" accept=".xlsx,.xlsm" hidden onChange={(e) => upload(e.target.files?.[0])} />
          </div>
          {res && (
            <div className={"notice " + (res.warnings.length ? "" : "ok")}>
              <b>{res.file || res.source}</b> ({res.mode}): {Object.entries(res.counts).map(([t, n]) => `${n} ${t}`).join(", ")}{res.skipped ? `; ${res.skipped} skipped` : ""}.
              {res.warnings.length > 0 && <ul style={{ margin: "6px 0 0", paddingInlineStart: 18 }}>{res.warnings.slice(0, 12).map((w, i) => <li key={i}>{w}</li>)}</ul>}
            </div>
          )}
        </div>
        <div className="panel">
          <div className="ph"><h2>CRM / ERP sync API</h2><span className="hint">Replaces manual uploads</span></div>
          <p className="hint">Connectors push batches to <span className="mono">POST /api/ingest/crm</span>. Records are validated against the ontology and upserted by ID. Full API docs: <a href="/docs" target="_blank" rel="noreferrer">/docs</a>.</p>
          <pre className="draft mono" style={{ fontSize: 12 }}>{`curl -X POST $PRECAST/api/ingest/crm \\
  -H "Content-Type: application/json" -H "X-API-Key: $KEY" \\
  -d '{"opportunities":[{"id":"OPP-201","name":"…","country":"KSA",
        "domain":"security","status":"Proposal","value":120000000}],
       "engagements":[{"id":"ENG-501","opp":"OPP-201",
        "date":"2026-11-08","type":"Meeting","summary":"…"}]}'`}</pre>
          <div className="ph"><h2>Local LLM</h2>{llm.data && <Chip tone={llm.data.available ? "pos" : "neu"}>{llm.data.available ? "Connected" : "Template mode"}</Chip>}</div>
          {llm.data ? <p className="hint">Model <span className="mono">{llm.data.model || "—"}</span> at <span className="mono">{llm.data.endpoint || "—"}</span>. {llm.data.detail} {!llm.data.available && "Drafting, Q&A and extraction still work with deterministic templates; start Ollama to enable generation."}</p> : <Loading error={llm.error} />}
          <label className="f">API key for write actions (if the server sets one)<div className="filters"><input className="in" type="password" value={key} onChange={(e) => setKey(e.target.value)} /><button className="btn sm" onClick={() => { apiKey.set(key); toast("Saved in this browser"); }}>Save</button></div></label>
        </div>
      </section>

      <section className="panel">
        <div className="ph"><h2>Microsoft 365</h2><span className="hint">SharePoint · Teams · Outlook via Microsoft Graph (app-only)</span></div>
        {!st ? <Loading error={m365.error} /> : (
          <>
            <div className="grid g3">
              <div className="integ"><div className="ic" style={{ background: "#0B6A60" }}>SP</div><div><b>SharePoint</b><div className="hint">Pull the tracker from a document library, push exports back, and keep a document folder per opportunity.</div></div>
                <Chip tone={st.sharepoint ? "pos" : ""}>{st.sharepoint ? "Ready" : "Not set"}</Chip></div>
              <div className="integ"><div className="ic" style={{ background: "#4B53BC" }}>T</div><div><b>Teams</b><div className="hint">A channel per opportunity; channel messages sync into each opportunity's Discussion tab.</div></div>
                <Chip tone={st.teams ? "pos" : ""}>{st.teams ? (st.teams_posting ? "Ready · 2-way" : "Ready · read") : "Not set"}</Chip></div>
              <div className="integ"><div className="ic" style={{ background: "#0F6CBD" }}>O</div><div><b>Outlook</b><div className="hint">Auto-log emails and meetings tagged [OPP-###]; save AI drafts to Drafts; create milestone invites.</div></div>
                <Chip tone={st.outlook ? "pos" : ""}>{st.outlook ? "Ready" : "Not set"}</Chip></div>
            </div>
            <div className="filters">
              <button className="btn" disabled={!st.sharepoint || !!busy} onClick={() => act("pull", () => api.post<Import>("/api/integrations/sharepoint/pull"), (r) => { setRes(r); return `Pulled ${r.counts.opportunities ?? 0} opportunities from SharePoint`; })}>Pull tracker from SharePoint</button>
              <button className="btn" disabled={!st.sharepoint || !!busy} onClick={() => act("push", () => api.post<{ path: string }>("/api/integrations/sharepoint/push"), (r) => `Exported to ${r.path}`)}>Push export to SharePoint</button>
              <button className="btn" disabled={!st.outlook || !!busy} onClick={() => act("ol", () => api.post<{ added: number }>("/api/integrations/outlook/sync?days=30"), (r) => `${r.added} engagements logged from Outlook`)}>Sync Outlook (30 days)</button>
              <span className="hint">Last sync: SharePoint {st.last_sync.sharepoint?.slice(0, 16) || "never"} · Teams {st.last_sync.teams?.slice(0, 16) || "never"} · Outlook {st.last_sync.outlook?.slice(0, 16) || "never"}</span>
            </div>
            <details>
              <summary style={{ cursor: "pointer", fontWeight: 600 }}>Connection settings</summary>
              <div className="formgrid" style={{ marginTop: 12 }}>
                {FIELDS.map(([k, l, h]) => (
                  <label key={k} className="f">{l}<input className="in" type={k === "client_secret" || k === "teams_webhook" ? "password" : "text"} placeholder={h} value={s[k] || ""} onChange={(e) => setCfg({ ...s, [k]: e.target.value })} /></label>
                ))}
              </div>
              <div className="filters" style={{ marginTop: 10 }}>
                <button className="btn primary" disabled={!cfg || !!busy} onClick={() => act("save", () => api.put<M365Status>("/api/integrations/m365", cfg), () => { setCfg(null); return "Settings saved"; })}>Save settings</button>
                <button className="btn" disabled={!st.configured || !!busy} onClick={() => act("test", () => api.post<{ sharepoint_site?: string }>("/api/integrations/m365/test"), (r) => `Signed in to Microsoft 365${r.sharepoint_site ? "; SharePoint site found" : ""}`)}>Test connection</button>
              </div>
              <p className="hint">Grant the app registration these Graph application permissions with admin consent: Sites.ReadWrite.All (or Sites.Selected), Channel.Create, ChannelMessage.Read.All, Team.ReadBasic.All, Mail.ReadWrite, Calendars.ReadWrite. Restrict mailbox access with an Exchange application access policy. Values saved here take precedence over environment variables.</p>
            </details>
          </>
        )}
      </section>

      <section className="panel">
        <div className="ph"><h2>Sample data</h2></div>
        <div className="filters"><button className="btn danger" disabled={!!busy} onClick={() => { if (confirm("Replace all data with the illustrative sample?")) act("reset", () => api.post("/api/admin/reset-sample"), () => "Sample data restored"); }}>Restore sample data</button>
          <span className="hint">Replaces the register with illustrative “Example:” records.</span></div>
      </section>
    </>
  );
}
