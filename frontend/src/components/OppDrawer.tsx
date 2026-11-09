import { useEffect, useState } from "react";
import { api, type Discussion, type GraphData, type M365Status, type OppDetail } from "../api";
import { aed, cls, DOMAIN_COLOR, fd, pct, pts, rel } from "../format";
import { Approval, Chip, Loading, OutlookChip, Prob, Score5, Spark, useApp, useData } from "../ui";
import DraftModal from "./DraftModal";
import GraphView from "./GraphView";

const TABS = ["Summary", "Prediction", "Activity", "Discussion", "Knowledge graph", "Workspace"] as const;
type Tab = (typeof TABS)[number];
const STAGES = ["Exploratory", "Active Engagement", "Proposal", "Negotiation", "Agreement", "Execution", "Closed Won", "Closed Lost", "On Hold"];

export default function OppDrawer({ id, onClose }: { id: string; onClose: () => void }) {
  const { bump } = useApp();
  const { data: o, error, reload } = useData(() => api.get<OppDetail>(`/api/opportunities/${id}`), [id]);
  const [tab, setTab] = useState<Tab>("Summary");
  const [draft, setDraft] = useState<null | "memo" | "email">(null);

  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);

  const changed = () => { reload(); bump(); };

  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Opportunity detail">
        {!o ? <div className="db"><Loading error={error} /></div> : (
          <>
            <div className="dh">
              <div className="dh-row">
                <div>
                  <div className="idc">{o.id} · {o.sensitivity || "—"} · {o.domain} · {o.country}{o.region ? ` (${o.region})` : ""}</div>
                  <h3>{o.name}</h3>
                  <div className="idc">{o.counterparty}</div>
                </div>
                <button className="x" onClick={onClose} aria-label="Close">×</button>
              </div>
              <div className="filters">
                <Prob p={o.score.p} delta={o.score.delta_14d} />
                <span className="hint">EV <b className="mono">{aed(o.score.ev)}</b> of {aed(o.value)}</span>
                {o.score.trend && <Spark values={o.score.trend} />}
                <span className="grow" style={{ flex: 1 }} />
                <button className="btn sm" onClick={() => setDraft("memo")}>Draft briefing memo</button>
                <button className="btn sm" onClick={() => setDraft("email")}>Draft sponsor email</button>
              </div>
              <div className="tabs" role="tablist">
                {TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>{t}{t === "Discussion" && o.discussions.length ? ` (${o.discussions.length})` : ""}</button>)}
              </div>
            </div>
            <div className="db">
              {tab === "Summary" && <Summary o={o} onChange={changed} />}
              {tab === "Prediction" && <Prediction o={o} />}
              {tab === "Activity" && <Activity o={o} onChange={changed} />}
              {tab === "Discussion" && <Thread o={o} onChange={changed} />}
              {tab === "Knowledge graph" && <OppGraph id={o.id} />}
              {tab === "Workspace" && <Workspace o={o} onChange={changed} />}
            </div>
          </>
        )}
      </aside>
      {draft && o && (
        <DraftModal title={draft === "memo" ? `Intervention briefing · ${o.id}` : `Sponsor email · ${o.id}`}
          path={`/api/opportunities/${o.id}/draft`} body={{ kind: draft }} onClose={() => setDraft(null)} outlookOpp={o.id} />
      )}
    </div>
  );
}

function Summary({ o, onChange }: { o: OppDetail; onChange: () => void }) {
  const { toast } = useApp();
  const kv = (k: string, v: React.ReactNode) => <div><span>{k}</span>{v}</div>;
  async function set(field: string, value: string) {
    try { await api.patch(`/api/opportunities/${o.id}`, { [field]: value, verified: new Date().toISOString().slice(0, 10) }); onChange(); toast("Saved; scores recalculated"); }
    catch (e) { toast((e as Error).message); }
  }
  return (
    <>
      <div className="kv">
        {kv("Stage", <select className="in" value={o.status} onChange={(e) => set("status", e.target.value)}>{STAGES.map((s) => <option key={s}>{s}</option>)}</select>)}
        {kv("Outlook", <select className="in" value={o.outlook} onChange={(e) => set("outlook", e.target.value)}>{["Positive", "Neutral", "Negative"].map((s) => <option key={s}>{s}</option>)}</select>)}
        {kv("Intervention required", <select className="in" value={o.intervention || "No"} onChange={(e) => set("intervention", e.target.value)}><option>Yes</option><option>No</option></select>)}
        {kv("Estimated value", <span className="mono">{aed(o.value)}</span>)}
        {kv("Executive sponsor", o.sponsor || "—")}
        {kv("Executional owner", o.owner || "—")}
        {kv("Priority", <Score5 n={o.priority} />)}
        {kv("Potential: manual → dynamic", <span><Score5 n={o.score.potential_manual} /> → <Score5 n={o.score.potential_dynamic} /></span>)}
        {kv("Expected close", <span className="mono">{fd(o.score.expected_close)} · {o.score.quarter}</span>)}
        {kv("Next milestone", <span>{o.milestone || "—"} <span className={cls("idc", o.milestone_date && rel(o.milestone_date).includes("overdue") && "bad")}>{fd(o.milestone_date)}</span></span>)}
        {kv("Last engagement", fd(o.last_engagement))}
        {kv("Last verified", <span className={cls((!o.verified || (Date.now() - +new Date(o.verified)) > 30 * 864e5) && "bad")}>{fd(o.verified)}</span>)}
      </div>
      <div className="prose">
        {o.latest && <><h4>Latest development</h4><p>{o.latest}</p></>}
        {o.rationale && <><h4>Outlook rationale</h4><p>{o.rationale}</p></>}
        {o.next_action && <><h4>Next action</h4><p>{o.next_action} {o.action_owner && <span className="idc">· {o.action_owner}</span>}</p></>}
      </div>
    </>
  );
}

function Prediction({ o }: { o: OppDetail }) {
  const s = o.score;
  const max = Math.max(0.5, ...s.factors.map((f) => Math.abs(f.impact)));
  return (
    <>
      <div className="grid g3">
        <div className="kpi"><span className="lab">Win probability</span><span className="val">{pct(s.p)}</span><span className="sub">{pts(s.delta_14d)} vs 14 days ago</span></div>
        <div className="kpi"><span className="lab">Next-week projection</span><span className="val">{pct(s.p_next)}</span><span className="sub">Momentum, damped 50%</span></div>
        <div className="kpi"><span className="lab">Expected value</span><span className="val"><small>AED</small>{aed(s.ev, false)}</span><span className="sub">Risk-weighted, {aed(o.value)} face value</span></div>
      </div>
      <div className="panel">
        <div className="ph"><h2>Why the model says {pct(s.p)}</h2><span className="hint">Log-odds contribution of each signal</span></div>
        <div>
          {s.factors.map((f) => {
            const w = (Math.abs(f.impact) / max) * 50;
            return (
              <div className="factor" key={f.key}>
                <div><div>{f.label}</div><div className="m">{f.detail}</div></div>
                <div className="fbar" aria-hidden="true">{f.impact !== 0 && <i style={{ left: f.impact > 0 ? "50%" : `${50 - w}%`, width: `${w}%`, background: f.impact > 0 ? "var(--pos)" : "var(--neg)" }} />}</div>
                <div className={cls("mono", f.impact > 0 ? "ok" : f.impact < 0 ? "bad" : "")} style={{ textAlign: "end", fontSize: 12 }}>{f.key === "stage" ? "base" : (f.impact > 0 ? "+" : "") + f.impact.toFixed(2)}</div>
              </div>
            );
          })}
        </div>
      </div>
      {s.trend && (
        <div className="panel">
          <div className="ph"><h2>Probability, last 8 weeks</h2><span className="hint">Recomputed as of each week from the Engagement Log and actions</span></div>
          <Spark values={s.trend} w={720} h={90} color="var(--accent)" />
          <div className="filters hint">{s.trend.map((v, i) => <span key={i} className="mono">W-{8 - i}: {pct(v)}</span>)}</div>
        </div>
      )}
    </>
  );
}

function Activity({ o, onChange }: { o: OppDetail; onChange: () => void }) {
  const { toast } = useApp();
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  async function add() {
    if (!title.trim()) return;
    try { await api.post("/api/actions", { opp: o.id, title, due: due || null, owner: o.owner }); setTitle(""); setDue(""); onChange(); }
    catch (e) { toast((e as Error).message); }
  }
  async function setStatus(aid: string, status: string) {
    try { await api.patch(`/api/actions/${aid}`, { status }); onChange(); } catch (e) { toast((e as Error).message); }
  }
  return (
    <>
      <div className="panel">
        <div className="ph"><h2>Actions & milestones</h2></div>
        <div className="tw"><table><thead><tr><th>Action</th><th>Owner</th><th>Due</th><th>Status</th></tr></thead><tbody>
          {o.actions.map((a) => (
            <tr key={a.id}>
              <td>{a.title}{a.blocker && <div className="idc bad">Blocker: {a.blocker}</div>}{a.escalate === "Yes" && <Chip tone="neg">Escalation</Chip>}</td>
              <td>{a.owner}</td>
              <td className={cls("mono", rel(a.due).includes("overdue") && !["Completed", "Cancelled"].includes(a.status || "") && "bad")}>{fd(a.due, false)}</td>
              <td><select className="in" value={a.status} onChange={(e) => setStatus(a.id, e.target.value)}>{["Not Started", "In Progress", "Blocked", "Completed", "Cancelled"].map((s) => <option key={s}>{s}</option>)}</select></td>
            </tr>
          ))}
          {!o.actions.length && <tr><td colSpan={4}><div className="empty">No actions.</div></td></tr>}
        </tbody></table></div>
        <div className="filters">
          <input className="in" style={{ flex: 1 }} placeholder="New action" value={title} onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} />
          <input className="in" type="date" value={due} onChange={(e) => setDue(e.target.value)} aria-label="Due date" />
          <button className="btn" onClick={add}>Add action</button>
        </div>
      </div>
      <div className="panel">
        <div className="ph"><h2>Engagement Log</h2><span className="hint">{o.engagements.length} entries</span></div>
        {o.engagements.map((e) => (
          <div key={e.id} className="tl-item">
            <div className="tl-date">{fd(e.date, false)}<em>{e.type}</em></div>
            <div><div>{e.summary}</div><div className="hint">{e.follow_up && <>Follow-up: {e.follow_up} · </>}{e.source !== "seed" && e.source && <Chip tone="acc">{e.source}</Chip>} {e.link && <a href={e.link} target="_blank" rel="noopener noreferrer">Open in Outlook</a>}</div></div>
          </div>
        ))}
        {!o.engagements.length && <div className="empty">No engagements logged.</div>}
      </div>
      {o.announcements.length > 0 && (
        <div className="panel">
          <div className="ph"><h2>Announcements</h2></div>
          {o.announcements.map((a) => <div key={a.id}>{a.title} <span className="idc">· {a.readiness} · {fd(a.target)} · Legal <Approval v={a.legal} /> · IR <Approval v={a.ir} /> · Counterparty <Approval v={a.counterparty} /></span></div>)}
        </div>
      )}
    </>
  );
}

function initials(n?: string) {
  return (n || "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
}

function Thread({ o, onChange }: { o: OppDetail; onChange: () => void }) {
  const { toast } = useApp();
  const [text, setText] = useState("");
  const [author, setAuthor] = useState(() => { try { return localStorage.getItem("precast.author") || ""; } catch { return ""; } });
  const [replyTo, setReplyTo] = useState<Discussion | null>(null);
  const [busy, setBusy] = useState(false);
  const roots = o.discussions.filter((d) => !d.parent || !o.discussions.some((x) => x.id === d.parent));
  const replies = (id: string) => o.discussions.filter((d) => d.parent === id);

  async function post() {
    if (!text.trim()) return;
    setBusy(true);
    try { localStorage.setItem("precast.author", author); } catch { /* ignore */ }
    try {
      const r = await api.post<{ posted_to_teams: boolean }>(`/api/opportunities/${o.id}/discussions`, { body: text, author: author || "Precast user", parent: replyTo?.id ?? null });
      setText(""); setReplyTo(null); onChange();
      toast(r.posted_to_teams ? "Posted and mirrored to Teams" : "Posted");
    } catch (e) { toast((e as Error).message); }
    setBusy(false);
  }
  async function sync() {
    setBusy(true);
    try { const r = await api.post<{ added: number }>(`/api/opportunities/${o.id}/teams/sync`); toast(`${r.added} new Teams message(s)`); onChange(); }
    catch (e) { toast((e as Error).message); }
    setBusy(false);
  }
  const Post = ({ d, reply }: { d: Discussion; reply?: boolean }) => (
    <div className={cls("post", reply && "reply")}>
      <div className="avatar">{initials(d.author)}</div>
      <div className="b">
        <div className="h"><b>{d.author}</b><span>{d.created ? new Date(d.created).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : ""}</span>
          {d.source === "teams" && <Chip tone="acc">Teams</Chip>}
          {d.web_url && <a href={d.web_url} target="_blank" rel="noopener noreferrer">Open</a>}
          {!reply && <button className="btn ghost sm" onClick={() => setReplyTo(d)}>Reply</button>}
        </div>
        <div style={{ whiteSpace: "pre-wrap" }}>{d.body}</div>
      </div>
    </div>
  );
  return (
    <>
      <div className="filters">
        <span className="hint">Internal discussion on this opportunity. {o.teams_channel_id ? "Linked to a Teams channel." : "Create a Teams channel in Workspace to sync both ways."}</span>
        <span style={{ flex: 1 }} />
        {o.teams_channel_id && <button className="btn sm" onClick={sync} disabled={busy}>Sync from Teams</button>}
        {o.teams_web_url && <a className="btn sm" href={o.teams_web_url} target="_blank" rel="noopener noreferrer">Open channel</a>}
      </div>
      <div className="thread">
        {roots.map((d) => <div key={d.id} className="thread"><Post d={d} />{replies(d.id).map((r) => <Post key={r.id} d={r} reply />)}</div>)}
        {!roots.length && <div className="empty">No discussion yet. Start the thread below.</div>}
      </div>
      <div className="panel">
        {replyTo && <div className="hint">Replying to {replyTo.author}: “{replyTo.body?.slice(0, 80)}” <button className="btn ghost sm" onClick={() => setReplyTo(null)}>Cancel</button></div>}
        <textarea className="in" rows={3} placeholder="Share an update, a decision or a question for the team…" value={text} onChange={(e) => setText(e.target.value)} />
        <div className="filters">
          <input className="in" placeholder="Your name" value={author} onChange={(e) => setAuthor(e.target.value)} />
          <button className="btn primary" onClick={post} disabled={busy || !text.trim()}>Post</button>
        </div>
      </div>
    </>
  );
}

function OppGraph({ id }: { id: string }) {
  const { data, error } = useData(() => api.get<GraphData>(`/api/graph?focus=${id}`), [id]);
  if (!data) return <Loading error={error} />;
  return <div className="graph" style={{ height: 520 }}><GraphView data={data} height={520} /></div>;
}

function Workspace({ o, onChange }: { o: OppDetail; onChange: () => void }) {
  const { toast } = useApp();
  const { data: st } = useData(() => api.get<M365Status>("/api/integrations/m365"), []);
  const [files, setFiles] = useState<{ name: string; web_url: string; modified?: string; folder?: boolean }[] | null>(null);
  const [busy, setBusy] = useState("");
  const [when, setWhen] = useState("");
  const [att, setAtt] = useState("");
  async function run<T>(key: string, fn: () => Promise<T>, ok: (r: T) => string) {
    setBusy(key);
    try { const r = await fn(); toast(ok(r)); onChange(); } catch (e) { toast((e as Error).message); }
    setBusy("");
  }
  const notConf = st && !st.configured;
  return (
    <>
      {notConf && <div className="notice">Microsoft 365 isn't connected yet. An administrator can add the Entra ID app details under <b>Data & Integrations</b>.</div>}
      <div className="integ">
        <div className="ic" style={{ background: "#0B6A60" }}>SP</div>
        <div><b>SharePoint documents</b><div className="hint">{o.sharepoint_url ? <a href={o.sharepoint_url} target="_blank" rel="noopener noreferrer">{o.sharepoint_url}</a> : "A folder for proposals, BoQs and contracts."}</div></div>
        <button className="btn sm" disabled={!st?.sharepoint || !!busy}
          onClick={() => run("sp", () => api.post<{ files: typeof files }>(`/api/opportunities/${o.id}/sharepoint`), (r) => { setFiles(r.files); return "Folder ready"; })}>
          {o.sharepoint_url ? "Refresh files" : "Create folder"}</button>
      </div>
      {files && <div className="panel">{files.length ? files.map((f) => <div key={f.web_url}><a href={f.web_url} target="_blank" rel="noopener noreferrer">{f.folder ? "📁 " : ""}{f.name}</a> <span className="idc">{fd(f.modified)}</span></div>) : <div className="empty">Folder is empty.</div>}</div>}
      <div className="integ">
        <div className="ic" style={{ background: "#4B53BC" }}>T</div>
        <div><b>Teams channel</b><div className="hint">{o.teams_web_url ? <a href={o.teams_web_url} target="_blank" rel="noopener noreferrer">Open channel</a> : "One standard channel per opportunity in the Precast team."} Discussion syncs into the Discussion tab.</div></div>
        <button className="btn sm" disabled={!st?.teams || !!busy || !!o.teams_channel_id}
          onClick={() => run("teams", () => api.post<{ created: boolean }>(`/api/opportunities/${o.id}/teams/channel`), (r) => (r.created ? "Channel created" : "Channel already linked"))}>
          {o.teams_channel_id ? "Linked" : "Create channel"}</button>
      </div>
      <div className="integ">
        <div className="ic" style={{ background: "#0F6CBD" }}>O</div>
        <div><b>Outlook</b><div className="hint">Logs emails and meetings tagged <span className="mono">[{o.id}]</span> or naming the counterparty into the Engagement Log.</div></div>
        <button className="btn sm" disabled={!st?.outlook || !!busy}
          onClick={() => run("ol", () => api.post<{ added: number }>(`/api/integrations/outlook/sync?days=60&opp=${o.id}`), (r) => `${r.added} engagement(s) logged`)}>Sync mail & calendar</button>
      </div>
      <div className="panel">
        <div className="ph"><h2>Schedule a milestone meeting in Outlook</h2></div>
        <div className="filters">
          <label className="f">Start<input className="in" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} /></label>
          <label className="f" style={{ flex: 1 }}>Attendees (emails, comma-separated)<input className="in" value={att} onChange={(e) => setAtt(e.target.value)} /></label>
          <button className="btn" disabled={!st?.outlook || !when || !!busy}
            onClick={() => run("ev", () => api.post<{ web_url?: string }>(`/api/opportunities/${o.id}/outlook/event`, { start: when, minutes: 30, attendees: att.split(",").map((s) => s.trim()).filter(Boolean) }), () => "Invite created in Outlook")}>Create invite</button>
        </div>
      </div>
      <p className="hint">Domain colour: <span className="dot" style={{ background: DOMAIN_COLOR[o.domain || ""] }} /> {o.domain}. Outlook: <OutlookChip v={o.outlook} /></p>
    </>
  );
}
