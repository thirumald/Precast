import { aed, cls, fd, pct } from "../format";
import { EngineBadge, Spark, useApp } from "../ui";

export type Kpi = { key: string; label: string; value: number; unit: string; target: number | null; higher_better?: boolean;
  status: "green" | "amber" | "red" | "neutral"; trend: number[]; delta_4w?: number | null; description?: string; report?: string | null };
type Col = { key: string; label: string; type: string };
export type Section =
  | { kind: "text"; title: string; body: string; engine?: string }
  | { kind: "kpis"; items: Kpi[] }
  | { kind: "table"; title: string; columns: Col[]; rows: Record<string, unknown>[]; note?: string }
  | { kind: "bars"; title: string; items: Record<string, unknown>[]; value: string; second?: string | null; unit: string; note?: string }
  | { kind: "columns"; title: string; items: { label: string; value: number }[] }
  | { kind: "stack"; title: string; items: Record<string, number | string>[]; series: { key: string; label: string }[]; line: string; line_label: string; target?: number };
export type Report = { id: string; title: string; audience: string; description: string; as_of: string; scope: string; sections: Section[] };

export function fmtUnit(v: number | null | undefined, unit: string): string {
  if (v == null || Number.isNaN(v)) return "—";
  switch (unit) {
    case "aed": return aed(v);
    case "pct": return pct(v);
    case "x": return v.toFixed(1) + "×";
    case "days": return Math.round(v) + " days";
    case "aed_day": return aed(v) + "/day";
    default: return Math.round(v).toLocaleString("en-GB");
  }
}
function fmtDelta(v: number | null | undefined, unit: string) {
  if (v == null || Math.abs(v) < 1e-9) return "no change";
  const sign = v > 0 ? "+" : "−";
  const a = Math.abs(v);
  return sign + (unit === "pct" ? Math.round(a * 100) + " pts" : fmtUnit(a, unit));
}
const RAG: Record<string, string> = { green: "var(--pos)", amber: "var(--neu)", red: "var(--neg)", neutral: "var(--muted)" };
const RAG_LABEL: Record<string, string> = { green: "On target", amber: "Near target", red: "Off target", neutral: "Tracking" };

export function KpiTile({ k, onOpen, big }: { k: Kpi; onOpen?: (r: string) => void; big?: boolean }) {
  const prog = k.target ? (k.higher_better === false ? Math.min(1, k.target / Math.max(k.value, 1e-9)) : Math.min(1, k.value / k.target)) : null;
  const good = k.delta_4w == null || Math.abs(k.delta_4w) < 1e-9 ? null : (k.delta_4w > 0) === (k.higher_better !== false);
  return (
    <button className={cls("kt", big && "big")} onClick={() => k.report && onOpen?.(k.report)} disabled={!k.report || !onOpen}
      title={k.description} style={{ ["--rag" as string]: RAG[k.status] }}>
      <div className="kt-h"><span className="kt-l">{k.label}</span><span className="kt-s"><i />{RAG_LABEL[k.status]}</span></div>
      <div className="kt-v">{fmtUnit(k.value, k.unit)}</div>
      {prog != null && <div className="kt-p"><span style={{ width: `${prog * 100}%` }} /></div>}
      <div className="kt-f">
        <span>{k.target != null ? `Target ${k.higher_better === false ? "≤ " : ""}${fmtUnit(k.target, k.unit)}` : k.description}</span>
        {k.trend?.length > 1 && <Spark values={k.trend} w={70} h={22} color={good == null ? "var(--accent)" : good ? "var(--pos)" : "var(--neg)"} />}
      </div>
      {k.delta_4w != null && <div className={cls("kt-d", good ? "ok" : good === false ? "bad" : "")}>{fmtDelta(k.delta_4w, k.unit)} vs 4 weeks ago</div>}
    </button>
  );
}

function cell(v: unknown, type: string) {
  if (v == null || v === "") return "—";
  if (type === "aed") return aed(Number(v), false);
  if (type === "pct") return pct(Number(v));
  if (type === "x") return Number(v).toFixed(2);
  if (type === "date") return fd(String(v), true);
  if (type === "int" || type === "days") return Number(v).toLocaleString("en-GB");
  return String(v);
}

function Bars({ s }: { s: Extract<Section, { kind: "bars" }> }) {
  const max = Math.max(1e-9, ...s.items.map((i) => Number(i[s.value]) || 0));
  return (
    <div className="bars">
      {s.items.map((i, n) => {
        const a = Number(i[s.value]) || 0, b = s.second ? Number(i[s.second]) || 0 : null;
        return (
          <div className="bar" key={n}>
            <span className="name">{String(i.label)}</span>
            <div className="track">
              <div className={cls("fill", b != null && "ghost")} style={{ width: `${(a / max) * 100}%` }} />
              {b != null && <div className="fill" style={{ width: `${(b / max) * 100}%` }} />}
            </div>
            <span className="v">{b != null ? `${fmtUnit(b, s.unit)} / ` : ""}{fmtUnit(a, s.unit)}{i.count != null && <i>{String(i.count)}</i>}</span>
          </div>
        );
      })}
      {!s.items.length && <div className="empty">No data for this selection.</div>}
    </div>
  );
}

function Columns({ s }: { s: Extract<Section, { kind: "columns" }> }) {
  const W = 640, H = 180, max = Math.max(1, ...s.items.map((i) => i.value)), bw = (W - 20) / s.items.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={s.title}>
      {s.items.map((i, n) => {
        const h = (i.value / max) * (H - 40);
        return <g key={n}><rect x={10 + n * bw + bw * 0.15} y={H - 22 - h} width={bw * 0.7} height={h} rx="3" fill="var(--accent)"><title>{`${i.label}: ${i.value}`}</title></rect>
          <text x={10 + n * bw + bw / 2} y={H - 6} textAnchor="middle" fontSize="10" fill="var(--muted)" fontFamily="var(--f-mono)">{i.label}</text>
          {i.value > 0 && <text x={10 + n * bw + bw / 2} y={H - 26 - h} textAnchor="middle" fontSize="10" fill="var(--ink)" fontFamily="var(--f-mono)">{i.value}</text>}</g>;
      })}
    </svg>
  );
}

export function Stack({ s }: { s: Extract<Section, { kind: "stack" }> }) {
  const W = 680, H = 240, pad = { l: 58, r: 12, t: 14, b: 28 };
  const tot = (i: Record<string, number | string>) => s.series.reduce((a, x) => a + (Number(i[x.key]) || 0), 0);
  const max = Math.max(1, s.target || 0, ...s.items.map(tot));
  const bw = (W - pad.l - pad.r) / s.items.length;
  const y = (v: number) => H - pad.b - (v / max) * (H - pad.t - pad.b);
  const shades = ["var(--accent)", "color-mix(in srgb,var(--accent) 50%,var(--surface))", "color-mix(in srgb,var(--accent) 20%,var(--surface))"];
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={s.title}>
        {[0, 0.25, 0.5, 0.75, 1].map((f) => <g key={f}><line x1={pad.l} x2={W - pad.r} y1={y(f * max)} y2={y(f * max)} stroke="var(--line)" />
          <text x={pad.l - 6} y={y(f * max) + 4} textAnchor="end" fontSize="10" fill="var(--muted)" fontFamily="var(--f-mono)">{aed(f * max, false)}</text></g>)}
        {s.target ? <g><line x1={pad.l} x2={W - pad.r} y1={y(s.target)} y2={y(s.target)} stroke="var(--neg)" strokeDasharray="6 4" strokeWidth="1.5" />
          <text x={W - pad.r} y={y(s.target) - 4} textAnchor="end" fontSize="10" fill="var(--neg)">Quarterly target {aed(s.target)}</text></g> : null}
        {s.items.map((it, n) => {
          let acc = 0; const x = pad.l + n * bw + bw * 0.2, w = bw * 0.6;
          return (
            <g key={n}>
              {s.series.map((se, si) => { const v = Number(it[se.key]) || 0; const y0 = y(acc), y1 = y(acc + v); acc += v;
                return v > 0 ? <rect key={se.key} x={x} y={y1} width={w} height={y0 - y1} fill={shades[si]} rx="2"><title>{`${it.quarter} ${se.label}: ${aed(v)}`}</title></rect> : null; })}
              <line x1={x - 4} x2={x + w + 4} y1={y(Number(it[s.line]) || 0)} y2={y(Number(it[s.line]) || 0)} stroke="var(--ink)" strokeWidth="2.2"><title>{`${s.line_label}: ${aed(Number(it[s.line]))}`}</title></line>
              <text x={x + w / 2} y={H - 10} textAnchor="middle" fontSize="11" fill="var(--muted)" fontFamily="var(--f-mono)">{String(it.quarter)}</text>
            </g>
          );
        })}
      </svg>
      <div className="chips">{s.series.map((se, i) => <span key={se.key} className="chip"><span className="dot" style={{ background: shades[i] }} />{se.label}</span>)}
        <span className="chip"><span className="dot" style={{ background: "var(--ink)", height: 3 }} />{s.line_label}</span></div>
    </div>
  );
}

/** Renders any report returned by /api/reports/{id}: same layout on screen and in print. */
export default function ReportView({ rep, onOpenReport, bare }: { rep: Report; onOpenReport?: (id: string) => void; bare?: boolean }) {
  const { openOpp } = useApp();
  return (
    <article className="report">
      {!bare && <header className="rep-h">
        <img src="/brand/presight-logo.svg" alt="Presight" className="rep-logo" />
        <div className="rep-t">
          <div className="idc">PRECAST · {rep.audience.toUpperCase()}</div>
          <h2>{rep.title}</h2>
          <div className="hint">{rep.scope} · As of {fd(rep.as_of)}</div>
        </div>
      </header>}
      {rep.sections.map((s, i) => {
        if (s.kind === "text") return <section key={i} className="rep-s"><div className="ph"><h3>{s.title}</h3><EngineBadge engine={s.engine} /></div><p className="rep-text">{s.body}</p></section>;
        if (s.kind === "kpis") return <section key={i} className="rep-s"><div className="kgrid">{s.items.map((k) => <KpiTile key={k.key} k={k} onOpen={onOpenReport} />)}</div></section>;
        if (s.kind === "stack") return <section key={i} className="rep-s"><div className="ph"><h3>{s.title}</h3></div><Stack s={s} /></section>;
        if (s.kind === "bars") return <section key={i} className="rep-s half"><div className="ph"><h3>{s.title}</h3>{s.note && <span className="hint">{s.note}</span>}</div><Bars s={s} /></section>;
        if (s.kind === "columns") return <section key={i} className="rep-s half"><div className="ph"><h3>{s.title}</h3></div><Columns s={s} /></section>;
        return (
          <section key={i} className="rep-s">
            <div className="ph"><h3>{s.title}</h3><span className="hint">{s.rows.length} rows{s.note ? ` · ${s.note}` : ""}</span></div>
            {s.rows.length ? (
              <div className="tw"><table><thead><tr>{s.columns.map((c) => <th key={c.key} className={cls(["aed", "pct", "int", "x", "days"].includes(c.type) && "n")}>{c.label}</th>)}</tr></thead>
                <tbody>{s.rows.map((r, n) => {
                  const oid = typeof r.id === "string" && /^OPP-/.test(r.id) ? r.id : null;
                  return <tr key={n} className={cls(oid && "click")} onClick={() => oid && openOpp(oid)}>
                    {s.columns.map((c) => <td key={c.key} className={cls(["aed", "pct", "int", "x", "days"].includes(c.type) && "n mono", c.key === "id" && "idc",
                      c.type === "pct" && c.key === "delta" && (Number(r[c.key]) < 0 ? "bad" : "ok"))}>{c.type === "pct" && c.key === "delta" && r[c.key] != null ? (Number(r[c.key]) > 0 ? "+" : "") + Math.round(Number(r[c.key]) * 100) + " pts" : cell(r[c.key], c.type)}</td>)}
                  </tr>;
                })}</tbody></table></div>
            ) : <div className="empty">Nothing to report for this selection.</div>}
          </section>
        );
      })}
      {!bare && <footer className="rep-f hint">Generated by Precast from the live register. Win probabilities are model estimates; figures in AED. Confidential.</footer>}
    </article>
  );
}
