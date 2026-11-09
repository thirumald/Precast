import { useMemo, useState } from "react";
import { api, type Opp, type Overview } from "../api";
import { aed, cls, DOMAIN_COLOR, fd, pct } from "../format";
import { Loading, Prob, Score5, Spark, useApp, useData } from "../ui";
import { ForecastChart } from "./Overview";

type Fc = { quarters: Overview["forecast"]["quarters"]; calibration: Overview["calibration"] };

export default function Forecast() {
  const { openOpp } = useApp();
  const fc = useData(() => api.get<Fc>("/api/forecast?quarters=6"));
  const opps = useData(() => api.get<Opp[]>("/api/opportunities?include_closed=false"));
  const [sort, setSort] = useState<"ev" | "p" | "delta" | "close">("ev");
  const rows = useMemo(() => {
    const r = [...(opps.data || [])];
    const key = { ev: (o: Opp) => -o.score.ev, p: (o: Opp) => -o.score.p, delta: (o: Opp) => o.score.delta_14d ?? 0, close: (o: Opp) => +new Date(o.score.expected_close) }[sort];
    return r.sort((a, b) => key(a) - key(b));
  }, [opps.data, sort]);
  if (!fc.data || !opps.data) return <Loading error={fc.error || opps.error} />;
  const mism = rows.filter((o) => o.score.potential_dynamic !== o.score.potential_manual);
  return (
    <>
      <section className="grid g-wide">
        <div className="panel">
          <div className="ph"><h2>Six-quarter forecast</h2><span className="hint">Face value tiered by win probability; line = risk-weighted expected value</span></div>
          <ForecastChart quarters={fc.data.quarters} height={260} />
          <div className="tw"><table><thead><tr><th>Quarter</th><th className="n">Commit</th><th className="n">Best case</th><th className="n">Pipeline</th><th className="n">Weighted</th><th className="n">Deals</th></tr></thead>
            <tbody>{fc.data.quarters.map((q) => <tr key={q.quarter}><td className="mono">{q.quarter}</td><td className="n mono">{aed(q.commit)}</td><td className="n mono">{aed(q.best_case)}</td><td className="n mono">{aed(q.pipeline)}</td><td className="n mono"><b>{aed(q.weighted)}</b></td><td className="n mono">{q.count}</td></tr>)}</tbody></table></div>
        </div>
        <div className="panel">
          <div className="ph"><h2>Model calibration</h2><span className="hint">Historical win/loss by domain (Beta-smoothed)</span></div>
          <div className="bars">
            {fc.data.calibration.domains.map((d) => (
              <div className="bar" key={d.domain}>
                <span className="name"><span className="dot" style={{ background: DOMAIN_COLOR[d.domain] }} />{d.domain}</span>
                <div className="track"><div className="fill" style={{ width: `${d.win_rate * 100}%`, background: DOMAIN_COLOR[d.domain] }} /></div>
                <span className="v">{pct(d.win_rate)}<i>{d.won}W {d.lost}L</i></span>
              </div>
            ))}
          </div>
          <p className="hint">Overall win rate {pct(fc.data.calibration.global_win_rate)}. Domains with stronger history lift stage base rates; weaker ones lower them. Every closed deal you record re-calibrates the model.</p>
          <div className="ph"><h2>Potential re-rated by the model</h2><span className="hint">{mism.length} opportunities</span></div>
          <div className="list">
            {mism.slice(0, 6).map((o) => (
              <button key={o.id} className="li" onClick={() => openOpp(o.id)} style={{ gridTemplateColumns: "minmax(0,1fr) auto" }}>
                <div><div className="t">{o.name}</div><div className="m">Manual {o.score.potential_manual} → dynamic {o.score.potential_dynamic} (EV {aed(o.score.ev)})</div></div>
                <div className={cls("r", o.score.potential_dynamic > o.score.potential_manual ? "ok" : "bad")}>{o.score.potential_dynamic > o.score.potential_manual ? "▲" : "▼"}</div>
              </button>
            ))}
          </div>
        </div>
      </section>
      <section className="panel">
        <div className="ph"><h2>Predictive deal scoring</h2>
          <div className="seg" role="group" aria-label="Sort">
            {([["ev", "Expected value"], ["p", "Probability"], ["delta", "Biggest drop"], ["close", "Expected close"]] as const).map(([k, l]) => <button key={k} aria-pressed={sort === k} onClick={() => setSort(k)}>{l}</button>)}
          </div>
        </div>
        <div className="tw"><table><thead><tr><th>Opportunity</th><th>Stage</th><th>Win probability</th><th>8-week trend</th><th className="n">Value</th><th className="n">Expected value</th><th>Potential (manual → AI)</th><th>Expected close</th><th>Risk</th></tr></thead>
          <tbody>{rows.map((o) => (
            <tr key={o.id} className="click" onClick={() => openOpp(o.id)}>
              <td><div>{o.name}</div><div className="idc">{o.id} · {o.country}</div></td>
              <td>{o.status}</td>
              <td><Prob p={o.score.p} delta={o.score.delta_14d} /></td>
              <td><Spark values={o.score.trend || []} /></td>
              <td className="n mono">{aed(o.value, false)}</td>
              <td className="n mono"><b>{aed(o.score.ev, false)}</b></td>
              <td><Score5 n={o.score.potential_manual} /> → <Score5 n={o.score.potential_dynamic} /></td>
              <td className="mono">{fd(o.score.expected_close, false)} <span className="idc">{o.score.quarter}</span></td>
              <td><span className={cls("chip", o.score.risk === "high" ? "neg" : o.score.risk === "medium" ? "neu" : "pos")}>{o.score.risk}</span></td>
            </tr>))}</tbody></table></div>
      </section>
    </>
  );
}
