import { useState } from "react";
import { api, type Announcement, type Opp } from "../api";
import { cls, fd, rel } from "../format";
import { Chip, Loading, useApp, useData } from "../ui";
import DraftModal from "../components/DraftModal";

const STATES = ["Pending", "Approved", "Rejected", "Not Required"];
const tone = (v?: string) => (/approved|not required/i.test(v || "") ? "pos" : /rejected/i.test(v || "") ? "neg" : "neu");

export default function Announcements() {
  const { openOpp, toast, bump } = useApp();
  const { data, error, reload } = useData(() => api.get<Announcement[]>("/api/announcements"));
  const opps = useData(() => api.get<Opp[]>("/api/opportunities?include_closed=true"));
  const [draft, setDraft] = useState<string | null>(null);
  const [nw, setNw] = useState({ opp: "", title: "", type: "Contract Award", target: "" });
  if (!data) return <Loading error={error} />;
  async function set(id: string, field: string, v: string) {
    try { await api.patch(`/api/announcements/${id}`, { [field]: v }); reload(); bump(); } catch (e) { toast((e as Error).message); }
  }
  async function add() {
    if (!nw.opp || !nw.title) { toast("Choose an opportunity and a title"); return; }
    try { await api.post("/api/announcements", { ...nw, target: nw.target || null }); setNw({ opp: "", title: "", type: "Contract Award", target: "" }); reload(); }
    catch (e) { toast((e as Error).message); }
  }
  const sel = (a: Announcement, f: "legal" | "ir" | "counterparty") => (
    <select className={cls("in", "chip", tone(a[f]))} style={{ border: 0 }} value={a[f] || "Pending"} onChange={(e) => set(a.id, f, e.target.value)} aria-label={f}>
      {STATES.map((s) => <option key={s}>{s}</option>)}</select>
  );
  return (
    <>
      <div className="notice">A potential announcement is not clearance to publish. Readiness moves to <b>Approved</b> only when Legal, IR and the counterparty have all approved, and drafts carry a clearance banner.</div>
      <section className="panel">
        <div className="ph"><h2>Clearance workflow</h2><span className="hint">{data.length} announcements</span></div>
        <div className="tw"><table><thead><tr><th>Announcement</th><th>Target</th><th>Readiness</th><th>Legal</th><th>IR / disclosure</th><th>Counterparty</th><th /></tr></thead>
          <tbody>{data.map((a) => (
            <tr key={a.id}>
              <td><button className="btn ghost" style={{ padding: 0 }} onClick={() => openOpp(a.opp)}>{a.title}</button><div className="idc">{a.id} · {a.opp_name} · {a.event}</div></td>
              <td className={cls("mono", rel(a.target).includes("overdue") && !a.cleared && "bad")}>{fd(a.target, false)}<div className="idc">{rel(a.target)}</div></td>
              <td><Chip tone={a.readiness === "Approved" ? "pos" : a.readiness === "Deferred" ? "neg" : "neu"}>{a.readiness}</Chip></td>
              <td>{sel(a, "legal")}</td><td>{sel(a, "ir")}</td><td>{sel(a, "counterparty")}</td>
              <td><button className="btn sm" onClick={() => setDraft(a.id)}>Draft press release</button></td>
            </tr>))}</tbody></table></div>
        <div className="filters">
          <select className="in" value={nw.opp} onChange={(e) => setNw({ ...nw, opp: e.target.value })} aria-label="Opportunity">
            <option value="">Opportunity…</option>{(opps.data || []).map((o) => <option key={o.id} value={o.id}>{o.id} {o.name}</option>)}</select>
          <input className="in" style={{ flex: 1 }} placeholder="Proposed announcement" value={nw.title} onChange={(e) => setNw({ ...nw, title: e.target.value })} />
          <select className="in" value={nw.type} onChange={(e) => setNw({ ...nw, type: e.target.value })} aria-label="Type">{["Contract Award", "Partnership", "JV Launch", "MoU Signing", "Milestone", "Product Launch"].map((t) => <option key={t}>{t}</option>)}</select>
          <input className="in" type="date" value={nw.target} onChange={(e) => setNw({ ...nw, target: e.target.value })} aria-label="Target date" />
          <button className="btn" onClick={add}>Add announcement</button>
        </div>
      </section>
      {draft && <DraftModal title={`Press release draft · ${draft}`} path={`/api/announcements/${draft}/draft`} body={{}} onClose={() => setDraft(null)} />}
    </>
  );
}
