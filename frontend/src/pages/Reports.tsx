import { useEffect, useState } from "react";
import { api } from "../api";
import Filters, { qs, type F } from "../components/Filters";
import ReportView, { type Report } from "../components/ReportView";
import { cls } from "../format";
import { Loading, useData } from "../ui";

type Cat = { id: string; title: string; audience: string; description: string };

function parseHash(): { id: string; f: F } {
  const m = location.hash.match(/^#\/reports\/?([\w-]*)\??(.*)$/);
  const f: F = {};
  new URLSearchParams(m?.[2] || "").forEach((v, k) => { (f as Record<string, string>)[k] = v; });
  return { id: m?.[1] || "executive-summary", f };
}

export default function Reports() {
  const [{ id, f }, setState] = useState(parseHash);
  useEffect(() => { const h = () => setState(parseHash()); window.addEventListener("hashchange", h); return () => window.removeEventListener("hashchange", h); }, []);
  const go = (nid: string, nf: F = f) => { history.replaceState(null, "", `#/reports/${nid}${qs(nf)}`); setState({ id: nid, f: nf }); };
  const cat = useData(() => api.get<Cat[]>("/api/reports"));
  const rep = useData(() => api.get<Report>(`/api/reports/${id}${qs(f)}`), [id, JSON.stringify(f)]);
  return (
    <div className="rep-layout">
      <aside className="panel rep-list no-print">
        <div className="ph"><h2>Management reports</h2></div>
        {(cat.data || []).map((c) => (
          <button key={c.id} className={cls("rep-item", c.id === id && "on")} onClick={() => go(c.id)}>
            <b>{c.title}</b><span className="hint">{c.audience}</span><span className="m">{c.description}</span>
          </button>
        ))}
      </aside>
      <div style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 12 }}>
        <div className="filters no-print">
          <Filters value={f} onChange={(nf) => go(id, nf)} />
          <span style={{ flex: 1 }} />
          <button className="btn" onClick={() => rep.reload()}>Refresh</button>
          <a className="btn" href={`/api/reports/${id}.xlsx${qs(f)}`} download>Excel</a>
          <button className="btn primary" onClick={() => window.print()}>Print / PDF</button>
        </div>
        <div className="panel">{rep.data ? <ReportView rep={rep.data} onOpenReport={(r) => go(r)} /> : <Loading error={rep.error} label="Building report" />}</div>
      </div>
    </div>
  );
}
