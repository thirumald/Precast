import { useState } from "react";
import { api, type Engagement, type Opp, type Score } from "../api";
import { fd, pct, pts } from "../format";
import { Chip, EngineBadge, Loading, useApp, useData } from "../ui";

type Extracted = { engagement: Engagement & { opp: string | null }; match_confidence: number; engine: string; opportunity: Opp | null };
const TYPES = ["Meeting", "Call", "Email", "Workshop", "Event", "Executive Engagement", "Site Visit"];
const SAMPLE = `Meeting with Municipal Development Authority (Riyadh) on smart city phase 2 — 6 Nov 2026.
Attendees: Deputy Mayor's office, CIO
Presight: Director Urban Solutions, solution architect
Pilot KPIs reviewed; the authority is supportive and keen to accelerate phase 2 scope.
Agreed: phased rollout across 12 districts, local partner annex required
Action: submit revised proposal with partner annex by 20 Nov, owner Director Urban Solutions`;

export default function Engagements() {
  const { openOpp, toast, bump } = useApp();
  const { data, error, reload } = useData(() => api.get<Engagement[]>("/api/engagements"));
  const opps = useData(() => api.get<Opp[]>("/api/opportunities?include_closed=false"));
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [ex, setEx] = useState<Extracted | null>(null);
  const [form, setForm] = useState<Partial<Engagement> & { create_action?: boolean }>({});
  const [q, setQ] = useState("");

  async function run() {
    if (!notes.trim()) return;
    setBusy(true);
    try { const r = await api.post<Extracted>("/api/engagements/extract", { text: notes }); setEx(r); setForm({ ...r.engagement, opp: r.engagement.opp || "", create_action: !!r.engagement.follow_up }); }
    catch (e) { toast((e as Error).message); }
    setBusy(false);
  }
  async function save() {
    if (!form.opp) { toast("Choose the opportunity"); return; }
    try {
      const r = await api.post<{ score: Score }>("/api/engagements", form);
      const before = ex?.opportunity?.score.p;
      toast(`Logged. Win probability now ${pct(r.score.p)}${before != null ? ` (${pts(r.score.p - before)})` : ""}`);
      setEx(null); setNotes(""); reload(); bump();
    } catch (e) { toast((e as Error).message); }
  }
  const f = (k: keyof Engagement) => ({ value: (form[k] as string) || "", onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value }) });
  const rows = (data || []).filter((e) => !q || [e.summary, e.opp_name, e.type, e.follow_up].join(" ").toLowerCase().includes(q.toLowerCase()));
  return (
    <>
      <section className="grid g2">
        <div className="panel">
          <div className="ph"><h2>Capture meeting notes</h2><span className="hint">Paste notes; the local model extracts a structured entry for you to confirm</span></div>
          <textarea className="in" rows={9} placeholder="Paste meeting notes, a call summary or an email…" value={notes} onChange={(e) => setNotes(e.target.value)} />
          <div className="filters">
            <button className="btn primary" disabled={busy || !notes.trim()} onClick={run}>{busy ? <span className="spin" /> : null} Extract entry</button>
            <button className="btn ghost" onClick={() => setNotes(SAMPLE)}>Use sample notes</button>
          </div>
        </div>
        <div className="panel">
          <div className="ph"><h2>Review before saving</h2>{ex && <span className="filters"><EngineBadge engine={ex.engine} /><Chip tone={ex.match_confidence >= 0.8 ? "pos" : "neu"}>match {pct(ex.match_confidence)}</Chip></span>}</div>
          {!ex ? <div className="empty">Extracted fields appear here. Nothing is saved until you confirm.</div> : (
            <div className="formgrid">
              <label className="f wide">Opportunity<select className="in" {...f("opp")}><option value="">Choose…</option>{(opps.data || []).map((o) => <option key={o.id} value={o.id}>{o.id} · {o.name}</option>)}</select></label>
              <label className="f">Date<input className="in" type="date" {...f("date")} /></label>
              <label className="f">Type<select className="in" {...f("type")}>{TYPES.map((t) => <option key={t}>{t}</option>)}</select></label>
              <label className="f">External participants<input className="in" {...f("external")} /></label>
              <label className="f wide">Summary / outcome<textarea className="in" rows={2} {...f("summary")} /></label>
              <label className="f wide">Commitments made<input className="in" {...f("commitments")} /></label>
              <label className="f">Follow-up action<input className="in" {...f("follow_up")} /></label>
              <label className="f">Action owner<input className="in" {...f("owner")} /></label>
              <label className="f">Due date<input className="in" type="date" {...f("due")} /></label>
              <label className="hint wide" style={{ display: "flex", gap: 6, alignItems: "center" }}><input type="checkbox" checked={!!form.create_action} onChange={(e) => setForm({ ...form, create_action: e.target.checked })} /> Also create the follow-up as a tracked action</label>
              <div className="filters wide"><button className="btn primary" onClick={save}>Save to Engagement Log</button><button className="btn ghost" onClick={() => setEx(null)}>Discard</button></div>
            </div>
          )}
        </div>
      </section>
      <section className="panel">
        <div className="ph"><h2>Engagement Log</h2><input className="in" type="search" placeholder="Search engagements" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        {!data ? <Loading error={error} /> : (
          <div className="tw"><table><thead><tr><th>Date</th><th>Opportunity</th><th>Type</th><th>Summary / outcome</th><th>Follow-up</th><th>Due</th><th>Source</th></tr></thead>
            <tbody>{rows.map((e) => (
              <tr key={e.id} className="click" onClick={() => openOpp(e.opp)}>
                <td className="mono">{fd(e.date, false)}</td><td>{e.opp_name}</td><td>{e.type}</td><td>{e.summary}</td><td>{e.follow_up || "—"}</td>
                <td className="mono">{fd(e.due, false)}</td><td>{e.source && e.source !== "seed" ? <Chip tone="acc">{e.source}</Chip> : <span className="idc">manual</span>}</td>
              </tr>))}</tbody></table></div>
        )}
      </section>
    </>
  );
}
