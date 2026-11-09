import { useMemo, useState } from "react";
import { api, type Opp } from "../api";
import { aed, cls, DOMAIN_COLOR, fd, rel } from "../format";
import { Loading, Modal, OutlookChip, Prob, Score5, useApp, useData } from "../ui";

const DOMAINS = ["Security", "Defense", "Urban", "Financial", "Energy"];
const STAGES = ["Exploratory", "Active Engagement", "Proposal", "Negotiation", "Agreement", "Execution", "Closed Won", "Closed Lost", "On Hold"];
type K = "id" | "name" | "domain" | "country" | "status" | "outlook" | "priority" | "value" | "p" | "ev" | "milestone_date" | "sponsor";

export default function Register() {
  const { openOpp, toast, bump } = useApp();
  const { data, error } = useData(() => api.get<Opp[]>("/api/opportunities"));
  const [f, setF] = useState({ domain: "", segment: "", country: "", sponsor: "", q: "" });
  const [sort, setSort] = useState<{ k: K; d: 1 | -1 }>({ k: "ev", d: -1 });
  const [adding, setAdding] = useState(false);
  const [nw, setNw] = useState<Record<string, string>>({ status: "Exploratory", outlook: "Neutral", domain: "Security", segment: "Government", priority: "3", commercial: "3" });

  const rows = useMemo(() => {
    const q = f.q.toLowerCase();
    const get = (o: Opp, k: K): number | string => (k === "p" ? o.score.p : k === "ev" ? o.score.ev : k === "status" ? STAGES.indexOf(o.status || "") : (o[k] as string | number) ?? "");
    return (data || []).filter((o) => (!f.domain || o.domain === f.domain) && (!f.segment || o.segment === f.segment) && (!f.country || o.country === f.country) && (!f.sponsor || o.sponsor === f.sponsor)
      && (!q || [o.id, o.name, o.counterparty, o.owner, o.sponsor, o.country].join(" ").toLowerCase().includes(q)))
      .sort((a, b) => { const x = get(a, sort.k), y = get(b, sort.k); return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) * sort.d; });
  }, [data, f, sort]);
  if (!data) return <Loading error={error} />;
  const uniq = (k: keyof Opp) => [...new Set(data.map((o) => o[k] as string).filter(Boolean))].sort();
  const th = (k: K, label: string, n?: boolean) => (
    <th className={cls("s", n && "n")} aria-sort={sort.k === k ? (sort.d > 0 ? "ascending" : "descending") : "none"}
      onClick={() => setSort((s) => ({ k, d: s.k === k ? (s.d === 1 ? -1 : 1) : (["value", "p", "ev", "priority"].includes(k) ? -1 : 1) }))}>{label}</th>
  );
  async function create() {
    if (!nw.name) { toast("Name is required"); return; }
    try {
      const r = await api.post<{ record: Opp; warnings: string[] }>("/api/opportunities", { ...nw, priority: +nw.priority, commercial: +nw.commercial, value: +(nw.value || 0), verified: new Date().toISOString().slice(0, 10) });
      setAdding(false); bump(); openOpp(r.record.id); if (r.warnings.length) toast(r.warnings.join("; "));
    } catch (e) { toast((e as Error).message); }
  }
  const inp = (k: string, type = "text") => <input className="in" type={type} value={nw[k] || ""} onChange={(e) => setNw({ ...nw, [k]: e.target.value })} />;
  const sel = (k: string, opts: string[]) => <select className="in" value={nw[k] || ""} onChange={(e) => setNw({ ...nw, [k]: e.target.value })}>{opts.map((o) => <option key={o}>{o}</option>)}</select>;
  return (
    <>
      <div className="filters">
        <div className="seg" role="group" aria-label="Domain">{["", ...DOMAINS].map((d) => <button key={d} aria-pressed={f.domain === d} onClick={() => setF({ ...f, domain: d })}>{d || "All domains"}</button>)}</div>
        <label className="f">Segment<select className="in" value={f.segment} onChange={(e) => setF({ ...f, segment: e.target.value })}><option value="">All</option><option>Government</option><option>Enterprise</option></select></label>
        <label className="f">Country<select className="in" value={f.country} onChange={(e) => setF({ ...f, country: e.target.value })}><option value="">All</option>{uniq("country").map((c) => <option key={c}>{c}</option>)}</select></label>
        <label className="f">Executive sponsor<select className="in" value={f.sponsor} onChange={(e) => setF({ ...f, sponsor: e.target.value })}><option value="">All</option>{uniq("sponsor").map((c) => <option key={c}>{c}</option>)}</select></label>
        <input className="in" type="search" placeholder="Search opportunity, counterparty, owner" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} style={{ minWidth: 240 }} />
        <span style={{ flex: 1 }} />
        <button className="btn primary" onClick={() => setAdding(true)}>New opportunity</button>
      </div>
      <section className="panel">
        <div className="ph"><h2>Opportunity register</h2><span className="hint">{rows.length} of {data.length}</span></div>
        <div className="tw"><table><thead><tr>
          {th("id", "ID")}{th("name", "Opportunity")}{th("domain", "Domain")}{th("country", "Country")}{th("status", "Stage")}{th("outlook", "Outlook")}{th("priority", "Priority")}
          {th("p", "Win probability")}{th("value", "Value (AED)", true)}{th("ev", "Expected (AED)", true)}{th("milestone_date", "Next milestone")}{th("sponsor", "Sponsor")}
        </tr></thead><tbody>{rows.map((o) => (
          <tr key={o.id} className="click" tabIndex={0} onClick={() => openOpp(o.id)} onKeyDown={(e) => e.key === "Enter" && openOpp(o.id)}>
            <td className="idc">{o.id}</td><td><div>{o.name}</div><div className="idc">{o.counterparty}</div></td>
            <td><span className="dot" style={{ background: DOMAIN_COLOR[o.domain || ""] }} /> {o.domain}</td><td>{o.country}</td><td>{o.status}</td>
            <td><OutlookChip v={o.outlook} /></td><td><Score5 n={o.priority} /></td><td><Prob p={o.score.p} delta={o.score.delta_14d} /></td>
            <td className="n mono">{aed(o.value, false)}</td><td className="n mono">{aed(o.score.ev, false)}</td>
            <td><div>{o.milestone || "—"}</div><div className={cls("idc", rel(o.milestone_date).includes("overdue") && !["Closed Won", "Closed Lost", "On Hold"].includes(o.status || "") && "bad")}>{fd(o.milestone_date, false)}</div></td>
            <td>{o.sponsor}</td>
          </tr>))}</tbody></table></div>
      </section>
      {adding && (
        <Modal title="New opportunity" onClose={() => setAdding(false)}>
          <div className="formgrid">
            <label className="f wide">Opportunity / engagement{inp("name")}</label>
            <label className="f">Counterparty{inp("counterparty")}</label>
            <label className="f">Country{inp("country")}</label>
            <label className="f">Domain{sel("domain", DOMAINS)}</label>
            <label className="f">Segment{sel("segment", ["Government", "Enterprise"])}</label>
            <label className="f">Stage{sel("status", STAGES)}</label>
            <label className="f">Outlook{sel("outlook", ["Positive", "Neutral", "Negative"])}</label>
            <label className="f">Estimated value (AED){inp("value", "number")}</label>
            <label className="f">Strategic priority{sel("priority", ["1", "2", "3", "4", "5"])}</label>
            <label className="f">Commercial potential{sel("commercial", ["1", "2", "3", "4", "5"])}</label>
            <label className="f">Executive sponsor{inp("sponsor")}</label>
            <label className="f">Executional owner{inp("owner")}</label>
            <label className="f">Next milestone{inp("milestone")}</label>
            <label className="f">Milestone date{inp("milestone_date", "date")}</label>
            <label className="f wide">Latest development{inp("latest")}</label>
          </div>
          <p className="hint">Country, domain and stage are normalised against the ontology (e.g. “KSA” → Saudi Arabia). The map location defaults to the country centre.</p>
          <div className="filters"><button className="btn primary" onClick={create}>Create</button><button className="btn ghost" onClick={() => setAdding(false)}>Cancel</button></div>
        </Modal>
      )}
    </>
  );
}
