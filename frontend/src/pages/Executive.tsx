import { useState } from "react";
import { api, href } from "../api";
import Filters, { qs, type F } from "../components/Filters";
import ReportView, { fmtUnit, KpiTile, Stack, type Kpi, type Report } from "../components/ReportView";
import { fd } from "../format";
import { Chip, EngineBadge, Loading, Modal, useApp, useData } from "../ui";

type KpiResp = { as_of: string; scope: string; kpis: Kpi[]; summary: { green: number; amber: number; red: number };
  headline: { active: number; pipeline: number; ev: number; won_value: number; forecast_quarter: string; forecast_weighted: number; forecast_commit: number } };

export const goReport = (id: string, f: F = {}) => { location.hash = `#/reports/${id}${qs(f)}`; };

const HERO = ["weighted_pipeline", "quarter_forecast", "win_rate", "at_risk_value"];
const GROUPS: [string, string[]][] = [
  ["Growth & forecast", ["pipeline", "coverage", "avg_p", "velocity"]],
  ["Execution & risk", ["interventions", "action_on_time", "cycle_days", "announcement_readiness"]],
  ["Coverage & data quality", ["engagement_coverage", "freshness"]],
];

export default function Executive() {
  const [f, setF] = useState<F>({});
  const [editing, setEditing] = useState(false);
  const k = useData(() => api.get<KpiResp>("/api/kpis" + qs(f)), [JSON.stringify(f)]);
  const board = useData(() => api.get<Report>("/api/reports/executive-summary" + qs(f)), [JSON.stringify(f)]);
  if (!k.data) return <Loading error={k.error} />;
  const by = Object.fromEntries(k.data.kpis.map((x) => [x.key, x]));
  const open = (r: string) => goReport(r, f);
  const text = board.data?.sections.find((s) => s.kind === "text") as { body: string; engine?: string } | undefined;
  const stack = board.data?.sections.find((s) => s.kind === "stack");
  const decisions = board.data?.sections.find((s) => s.kind === "table" && s.title.startsWith("Decisions"));
  return (
    <>
      <div className="exec-bar">
        <div>
          <div className="hint">{k.data.scope} · As of {fd(k.data.as_of)}</div>
          <div className="chips" style={{ marginTop: 6 }}>
            <Chip tone="pos">{k.data.summary.green} on target</Chip><Chip tone="neu">{k.data.summary.amber} near target</Chip><Chip tone="neg">{k.data.summary.red} off target</Chip>
          </div>
        </div>
        <span style={{ flex: 1 }} />
        <button className="btn" onClick={() => setEditing(true)}>Set targets</button>
        <a className="btn" href={href("/api/reports/executive-summary.xlsx" + qs(f))} download aria-disabled={!href("/api/reports/executive-summary.xlsx" + qs(f))}>Export to Excel</a>
        <button className="btn primary" onClick={() => open("executive-summary")}>Open board pack</button>
      </div>
      <Filters value={f} onChange={setF} />

      <section className="kgrid hero">{HERO.map((key) => by[key] && <KpiTile key={key} k={by[key]} onOpen={open} big />)}</section>

      <section className="grid g-wide">
        <div className="panel">
          <div className="ph"><h2>Executive summary</h2>{text && <EngineBadge engine={text.engine} />}</div>
          {text ? <p className="rep-text" style={{ margin: 0 }}>{text.body}</p> : <Loading error={board.error} />}
          {stack && stack.kind === "stack" && <Stack s={stack} />}
        </div>
        <div className="panel">
          <div className="ph"><h2>Headline</h2></div>
          <div className="kv" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <div><span>Active opportunities</span><b className="num" style={{ fontSize: 22 }}>{k.data.headline.active}</b></div>
            <div><span>Face value</span><b className="num" style={{ fontSize: 22 }}>{fmtUnit(k.data.headline.pipeline, "aed")}</b></div>
            <div><span>Risk-weighted</span><b className="num" style={{ fontSize: 22 }}>{fmtUnit(k.data.headline.ev, "aed")}</b></div>
            <div><span>Won, last 12 months</span><b className="num" style={{ fontSize: 22 }}>{fmtUnit(k.data.headline.won_value, "aed")}</b></div>
            <div><span>{k.data.headline.forecast_quarter} weighted</span><b className="num" style={{ fontSize: 22 }}>{fmtUnit(k.data.headline.forecast_weighted, "aed")}</b></div>
            <div><span>{k.data.headline.forecast_quarter} commit</span><b className="num" style={{ fontSize: 22 }}>{fmtUnit(k.data.headline.forecast_commit, "aed")}</b></div>
          </div>
          <div className="ph"><h2>Reports</h2></div>
          <div className="chips">
            {[["executive-summary", "Board pack"], ["forecast", "Forecast"], ["pipeline-health", "Pipeline health"], ["risk", "Risk"], ["win-loss", "Win/loss"],
              ["regional", "Regional"], ["sponsor-scorecard", "Sponsors"], ["engagement", "Engagement"], ["announcements", "Announcements"]].map(([id, l]) =>
              <button key={id} className="btn sm" onClick={() => open(id)}>{l}</button>)}
          </div>
        </div>
      </section>

      {GROUPS.map(([title, keys]) => (
        <section key={title} className="panel">
          <div className="ph"><h2>{title}</h2><span className="hint">Click a KPI to open the report behind it</span></div>
          <div className="kgrid">{keys.map((key) => by[key] && <KpiTile key={key} k={by[key]} onOpen={open} />)}</div>
        </section>
      ))}

      {decisions && decisions.kind === "table" && (
        <section className="panel">
          <ReportView rep={{ ...(board.data as Report), sections: [decisions] }} onOpenReport={open} bare />
        </section>
      )}
      {editing && <Targets onClose={() => setEditing(false)} onSaved={() => { setEditing(false); k.reload(); board.reload(); }} />}
    </>
  );
}

const TARGET_META: [string, string, string][] = [
  ["weighted_pipeline", "Risk-weighted pipeline (AED)", "aed"], ["annual_bookings", "Annual bookings target (AED)", "aed"],
  ["coverage", "Pipeline coverage (×)", "x"], ["quarter_forecast", "Quarterly weighted forecast (AED)", "aed"],
  ["win_rate", "Win rate (0–1)", "pct"], ["avg_p", "Average win probability (0–1)", "pct"],
  ["at_risk_value", "Max value at risk (AED)", "aed"], ["interventions", "Max open interventions", "count"],
  ["action_on_time", "Actions on time (0–1)", "pct"], ["engagement_coverage", "Engagement coverage (0–1)", "pct"],
  ["freshness", "Data freshness (0–1)", "pct"], ["cycle_days", "Max sales cycle (days)", "days"],
  ["velocity", "Pipeline velocity (AED/day)", "aed_day"], ["announcement_readiness", "Announcement readiness (0–1)", "pct"],
];

function Targets({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const { toast } = useApp();
  const { data } = useData(() => api.get<{ targets: Record<string, number>; defaults: Record<string, number> }>("/api/kpis/targets"));
  const [vals, setVals] = useState<Record<string, string>>({});
  if (!data) return <Modal title="KPI targets" onClose={onClose}><Loading /></Modal>;
  const get = (k: string) => vals[k] ?? String(data.targets[k]);
  async function save() {
    try { await api.put("/api/kpis/targets", Object.fromEntries(Object.entries(vals).map(([k, v]) => [k, Number(v)]))); toast("Targets saved"); onSaved(); }
    catch (e) { toast((e as Error).message); }
  }
  return (
    <Modal title="KPI targets" onClose={onClose}>
      <p className="hint">Targets drive the red/amber/green status. Amber is within 15% of target (20% for limits).</p>
      <div className="formgrid">
        {TARGET_META.map(([k, l, u]) => (
          <label key={k} className="f">{l}<input className="in" type="number" step="any" value={get(k)} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} />
            <span className="hint">{fmtUnit(Number(get(k)), u)} · default {fmtUnit(data.defaults[k], u)}</span></label>
        ))}
      </div>
      <div className="filters"><button className="btn primary" onClick={save} disabled={!Object.keys(vals).length}>Save targets</button>
        <button className="btn ghost" onClick={() => setVals(Object.fromEntries(Object.entries(data.defaults).map(([k, v]) => [k, String(v)])))}>Reset to defaults</button></div>
    </Modal>
  );
}
