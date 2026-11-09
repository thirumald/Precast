import { api, type Overview as OV } from "../api";
import { aed, cls, DOMAIN_COLOR, fd, OUTLOOK_COLOR, pct, pts, rel } from "../format";
import { useT } from "../i18n";
import { Chip, Loading, Spark, useApp, useData } from "../ui";

export function ForecastChart({ quarters, height = 220 }: { quarters: OV["forecast"]["quarters"]; height?: number }) {
  const W = 640, H = height, pad = { l: 56, r: 12, t: 12, b: 28 };
  const max = Math.max(1, ...quarters.map((q) => q.commit + q.best_case + q.pipeline));
  const bw = (W - pad.l - pad.r) / quarters.length;
  const y = (v: number) => H - pad.b - (v / max) * (H - pad.t - pad.b);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);
  const tiers: [keyof OV["forecast"]["quarters"][0], string, string][] = [
    ["commit", "var(--accent)", "Commit (p ≥ 70%)"], ["best_case", "color-mix(in srgb,var(--accent) 50%,var(--surface))", "Best case (40–70%)"],
    ["pipeline", "color-mix(in srgb,var(--accent) 18%,var(--surface))", "Pipeline (< 40%)"]];
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Forecast by quarter">
        {ticks.map((t, i) => <g key={i}><line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="var(--line)" /><text x={pad.l - 6} y={y(t) + 4} textAnchor="end" fontSize="10" fill="var(--muted)" fontFamily="var(--f-mono)">{aed(t, false)}</text></g>)}
        {quarters.map((q, i) => {
          let acc = 0;
          const x = pad.l + i * bw + bw * 0.18, w = bw * 0.64;
          return (
            <g key={q.quarter}>
              {tiers.map(([k, c, label]) => {
                const v = q[k] as number; const y0 = y(acc), y1 = y(acc + v); acc += v;
                return v > 0 ? <rect key={k} x={x} y={y1} width={w} height={Math.max(0, y0 - y1)} fill={c} rx="2"><title>{`${q.quarter} ${label}: ${aed(v)}`}</title></rect> : null;
              })}
              <line x1={x - 4} x2={x + w + 4} y1={y(q.weighted)} y2={y(q.weighted)} stroke="var(--ink)" strokeWidth="2"><title>{`Weighted: ${aed(q.weighted)}`}</title></line>
              <text x={x + w / 2} y={H - 10} textAnchor="middle" fontSize="11" fill="var(--muted)" fontFamily="var(--f-mono)">{q.quarter}</text>
              <text x={x + w / 2} y={y(acc) - 4} textAnchor="middle" fontSize="10" fill="var(--ink)" fontFamily="var(--f-mono)">{q.count ? aed(q.weighted, false) : ""}</text>
            </g>
          );
        })}
      </svg>
      <div className="chips">{tiers.map(([k, c, l]) => <span key={k} className="chip"><span className="dot" style={{ background: c }} />{l}</span>)}<span className="chip"><span className="dot" style={{ background: "var(--ink)", height: 2 }} />Risk-weighted expected value</span></div>
    </div>
  );
}

export default function Overview() {
  const t = useT();
  const { openOpp } = useApp();
  const { data, error } = useData(() => api.get<OV>("/api/overview"));
  if (!data) return <Loading error={error} />;
  const k = data.kpis as Record<string, number>;
  const smax = Math.max(1, ...data.stages.map((s) => s.value));
  const dmax = Math.max(1, ...data.domains.map((s) => s.value));
  const otot = data.outlook.reduce((a, x) => a + x.count, 0) || 1;
  return (
    <>
      <section className="kpis">
        <div className="kpi hero"><span className="lab">{t("Risk-weighted expected value")}</span><span className="val"><small>AED</small>{aed(k.expected_value, false)}</span><span className="sub">{pct(k.ev_ratio)} of {aed(k.pipeline)} pipeline · avg p {pct(k.avg_p)}</span></div>
        <div className="kpi"><span className="lab">{t("Indicative pipeline")}</span><span className="val"><small>AED</small>{aed(k.pipeline, false)}</span><span className="sub">{k.active} {t("Active opportunities").toLowerCase()} · {k.closed_or_hold} closed / on hold</span></div>
        <div className="kpi"><span className="lab">Forecast {data.kpis.forecast_quarter}</span><span className="val"><small>AED</small>{aed(k.forecast_weighted, false)}</span><span className="sub">Weighted · commit {aed(k.forecast_commit)}</span></div>
        <div className={cls("kpi", k.interventions > 0 && "alert")}><span className="lab">{t("Executive interventions")}</span><span className="val">{k.interventions}</span><span className="sub">{aed(k.intervention_value)} at stake · {k.announcements} announcements</span></div>
      </section>
      <section className="minis">
        <div className={cls("mini", k.overdue > 0 && "warn")}><span>{t("Overdue open actions")}</span><b>{k.overdue}</b></div>
        <div className="mini"><span>{t("Due in next 30 days")}</span><b>{k.due30}</b></div>
        <div className={cls("mini", k.blocked > 0 && "warn")}><span>{t("Blocked actions")}</span><b>{k.blocked}</b></div>
        <div className={cls("mini", k.stale > 0 && "warn")}><span>{t("Not verified in 30+ days")}</span><b>{k.stale}</b></div>
      </section>

      <section className="grid g-wide">
        <div className="panel">
          <div className="ph"><h2>{t("Forecast by quarter")}</h2><span className="hint">By expected close date; Execution excluded (already contracted)</span></div>
          <ForecastChart quarters={data.forecast.quarters} />
        </div>
        <div className="panel">
          <div className="ph"><h2>{t("Biggest probability moves (14 days)")}</h2></div>
          <div className="list">
            {data.movers.map((m) => (
              <button key={m.id} className="li" onClick={() => openOpp(m.id)} style={{ gridTemplateColumns: "minmax(0,1fr) auto auto" }}>
                <div><div className="t">{m.name}</div><div className="m">{m.id} · now {pct(m.p)}</div></div>
                <Spark values={m.trend} />
                <div className={cls("r", m.delta > 0 ? "ok" : "bad")}>{pts(m.delta)}</div>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="grid g-wide">
        <div className="panel">
          <div className="ph"><h2>{t("Pipeline by stage")}</h2><span className="hint">Face value (light) vs expected value (solid) · count</span></div>
          <div className="bars">
            {data.stages.map((s) => (
              <div className="bar" key={s.key}>
                <span className="name">{s.key}</span>
                <div className="track"><div className="fill ghost" style={{ width: `${(s.value / smax) * 100}%` }} /><div className="fill" style={{ width: `${(s.ev / smax) * 100}%` }} /></div>
                <span className="v">{aed(s.ev, false)} / {aed(s.value, false)}<i>{s.count}</i></span>
              </div>
            ))}
          </div>
          <div className="chips">{data.closed.map((c) => <span key={c.key} className="chip">{c.key} <b className="mono">{c.count}</b> · {aed(c.value)}</span>)}</div>
        </div>
        <div className="panel">
          <div className="ph"><h2>{t("Outlook distribution")}</h2></div>
          <div className="stack">{data.outlook.map((o) => <div key={o.key} title={`${o.key}: ${o.count}`} style={{ width: `${(o.count / otot) * 100}%`, background: OUTLOOK_COLOR[o.key] }} />)}</div>
          <div className="legend">{data.outlook.map((o) => <div key={o.key}><span className="t"><span className="dot" style={{ background: OUTLOOK_COLOR[o.key] }} />{o.key}</span><b>{o.count}</b><em>{aed(o.value)}</em></div>)}</div>
          <div className="ph"><h2>{t("Pipeline by domain")}</h2></div>
          <div className="bars">
            {data.domains.map((d) => (
              <div className="bar" key={d.key}>
                <span className="name"><span className="dot" style={{ background: DOMAIN_COLOR[d.key] }} />{d.key}</span>
                <div className="track"><div className="fill ghost" style={{ width: `${(d.value / dmax) * 100}%`, background: `color-mix(in srgb,${DOMAIN_COLOR[d.key]} 28%,transparent)` }} /><div className="fill" style={{ width: `${(d.ev / dmax) * 100}%`, background: DOMAIN_COLOR[d.key] }} /></div>
                <span className="v">{aed(d.ev, false)}<i>{d.count}</i></span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid g2">
        <div className="panel">
          <div className="ph"><h2>{t("Needs leadership attention")}</h2><span className="hint">{data.attention.length} opportunities</span></div>
          <div className="list">
            {data.attention.slice(0, 8).map((a) => (
              <button key={a.id} className="li" onClick={() => openOpp(a.id)}>
                <span className={cls("sev", a.high && "hi")} />
                <div><div className="t">{a.name}</div><div className="m">{[a.id, a.country, a.status, a.sponsor].filter(Boolean).join(" · ")}</div>
                  <div className="chips" style={{ marginTop: 6 }}>{a.reasons.map(([r, tone]) => <Chip key={r} tone={tone}>{r}</Chip>)}</div></div>
                <div className="r">{aed(a.value)}<div className="m">p {pct(a.p)}</div></div>
              </button>
            ))}
            {!data.attention.length && <div className="empty">Nothing flagged.</div>}
          </div>
        </div>
        <div className="panel">
          <div className="ph"><h2>{t("Near-term milestones")}</h2><span className="hint">Overdue and next 45 days</span></div>
          <div>
            {data.timeline.map((i, n) => (
              <div key={n} className="tl-item" style={{ cursor: "pointer" }} onClick={() => openOpp(i.opp)}>
                <div className={cls("tl-date", rel(i.date).includes("overdue") && "over")}>{fd(i.date, false)}<em>{rel(i.date)}</em></div>
                <div><div>{i.title} <Chip tone={i.kind === "Blocked" ? "neg" : i.kind === "Announcement" ? "acc" : ""}>{i.kind}</Chip></div><div className="hint">{i.meta}</div></div>
              </div>
            ))}
            {!data.timeline.length && <div className="empty">Nothing due.</div>}
          </div>
        </div>
      </section>
    </>
  );
}
