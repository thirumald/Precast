import { useState } from "react";
import { api } from "../api";
import { aed, DOMAIN_COLOR, pct } from "../format";
import { Loading, useApp, useData } from "../ui";

type Pt = { id: string; name: string; priority: number; potential: number; potential_next: number; p: number; p_next?: number;
  delta?: number; direction?: string; value: number; ev: number; domain?: string };

export default function Matrix() {
  const { openOpp } = useApp();
  const [mode, setMode] = useState<"dynamic" | "manual">("dynamic");
  const [showVec, setShowVec] = useState(true);
  const [hover, setHover] = useState<Pt | null>(null);
  const { data, error } = useData(() => api.get<{ points: Pt[] }>(`/api/matrix?potential=${mode}`), [mode]);
  if (!data) return <Loading error={error} />;
  const W = 820, H = 560, L = 54, B = 44, cw = (W - L - 10) / 5, ch = (H - B - 10) / 5;
  const cx = (c: number) => L + (c - 0.5) * cw, cy = (p: number) => 10 + (5 - p + 0.5) * ch;
  const groups: Record<string, Pt[]> = {};
  data.points.forEach((p) => (groups[`${p.priority}-${p.potential}`] ||= []).push(p));
  const pos: Record<string, [number, number]> = {};
  Object.values(groups).forEach((g) => g.forEach((p, i) => {
    const a = (i / g.length) * Math.PI * 2, r = g.length > 1 ? Math.min(cw, ch) * 0.26 : 0;
    pos[p.id] = [cx(p.potential) + Math.cos(a) * r, cy(p.priority) + Math.sin(a) * r];
  }));
  const maxV = Math.max(...data.points.map((p) => p.value), 1);
  const moving = data.points.filter((p) => p.potential_next !== p.potential);
  return (
    <>
      <div className="filters">
        <div className="seg" role="group" aria-label="Potential basis">
          <button aria-pressed={mode === "dynamic"} onClick={() => setMode("dynamic")}>AI potential (risk-weighted EV)</button>
          <button aria-pressed={mode === "manual"} onClick={() => setMode("manual")}>Manual potential (1–5)</button>
        </div>
        <label className="hint" style={{ display: "flex", gap: 6, alignItems: "center" }}><input type="checkbox" checked={showVec} onChange={(e) => setShowVec(e.target.checked)} /> Predicted movement next week</label>
      </div>
      <section className="grid g-wide">
        <div className="panel">
          <div className="ph"><h2>Priority × commercial potential</h2><span className="hint">Bubble size = face value · ring = win probability · arrows = momentum projection</span></div>
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Executive priority and potential matrix">
            <defs><marker id="mv" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L10,5L0,10z" fill="var(--ink)" /></marker></defs>
            {[1, 2, 3, 4, 5].map((p) => [1, 2, 3, 4, 5].map((c) => {
              const quad = p >= 4 && c >= 4;
              return <rect key={`${p}${c}`} x={L + (c - 1) * cw + 2} y={10 + (5 - p) * ch + 2} width={cw - 4} height={ch - 4} rx="6"
                fill={quad ? "color-mix(in srgb,var(--accent) 10%,var(--sunk))" : "var(--sunk)"} stroke={quad ? "var(--accent)" : "none"} strokeDasharray="5 4" />;
            }))}
            {[1, 2, 3, 4, 5].map((i) => <g key={i}>
              <text x={L - 10} y={cy(i) + 4} textAnchor="end" fontSize="12" fill="var(--muted)" fontFamily="var(--f-mono)">P{i}</text>
              <text x={cx(i)} y={H - B + 18} textAnchor="middle" fontSize="12" fill="var(--muted)" fontFamily="var(--f-mono)">C{i}</text></g>)}
            <text x={L + (W - L) / 2} y={H - 6} textAnchor="middle" fontSize="11" fill="var(--muted)">COMMERCIAL POTENTIAL → (1 = &lt; AED 5m · 5 = AED 250m+)</text>
            <text transform={`translate(14,${H / 2}) rotate(-90)`} textAnchor="middle" fontSize="11" fill="var(--muted)">STRATEGIC PRIORITY →</text>
            {showVec && moving.map((p) => {
              const [x1, y1] = pos[p.id]; const x2 = cx(p.potential_next), y2 = cy(p.priority);
              return <line key={"v" + p.id} x1={x1} y1={y1} x2={x2 + (x1 < x2 ? -12 : 12)} y2={y2} stroke="var(--ink)" strokeWidth="1.6" strokeDasharray="4 3" markerEnd="url(#mv)" opacity=".7" />;
            })}
            {data.points.map((p) => {
              const [x, y] = pos[p.id]; const r = 7 + Math.sqrt(p.value / maxV) * 16;
              const ring = p.p >= 0.6 ? "var(--pos)" : p.p >= 0.3 ? "var(--neu)" : "var(--neg)";
              return (
                <g key={p.id} className="mx-dot" transform={`translate(${x},${y})`} onClick={() => openOpp(p.id)} onMouseEnter={() => setHover(p)} onMouseLeave={() => setHover(null)}>
                  <title>{`${p.name}: p ${pct(p.p)}, ${aed(p.value)}`}</title>
                  <circle r={r} fill={DOMAIN_COLOR[p.domain || ""] || "var(--accent)"} opacity=".85" />
                  <circle r={r + 3} fill="none" stroke={ring} strokeWidth="3" strokeDasharray={`${2 * Math.PI * (r + 3) * p.p} 999`} transform="rotate(-90)" />
                  {showVec && p.direction && p.direction !== "flat" && <text y={4} textAnchor="middle" fontSize="11" fill="#fff" fontWeight="700">{p.direction === "up" ? "▲" : "▼"}</text>}
                </g>
              );
            })}
          </svg>
        </div>
        <div className="panel">
          <div className="ph"><h2>{hover ? hover.name : "Movement next week"}</h2></div>
          {hover ? (
            <div className="kv" style={{ gridTemplateColumns: "1fr 1fr" }}>
              <div><span>Win probability</span>{pct(hover.p)} → {pct(hover.p_next)}</div>
              <div><span>14-day change</span>{hover.delta != null ? `${Math.round(hover.delta * 100)} pts` : "—"}</div>
              <div><span>Value</span>{aed(hover.value)}</div><div><span>Expected value</span>{aed(hover.ev)}</div>
              <div><span>Cell now</span>P{hover.priority} · C{hover.potential}</div><div><span>Projected</span>P{hover.priority} · C{hover.potential_next}</div>
            </div>
          ) : moving.length ? (
            <div className="list">{moving.map((p) => (
              <button key={p.id} className="li" onClick={() => openOpp(p.id)} style={{ gridTemplateColumns: "minmax(0,1fr) auto" }}>
                <div><div className="t">{p.name}</div><div className="m">C{p.potential} → C{p.potential_next} · p {pct(p.p)} → {pct(p.p_next)}</div></div>
                <div className={"r " + (p.potential_next > p.potential ? "ok" : "bad")}>{p.potential_next > p.potential ? "▲" : "▼"}</div>
              </button>))}</div>
          ) : <div className="empty">No opportunity is projected to change cell next week.</div>}
          <p className="hint">Projection = current probability + half the last 14-day change, applied to value and re-banded. It signals momentum; it is not a commitment.</p>
          <div className="chips">{Object.entries(DOMAIN_COLOR).map(([d, c]) => <span className="chip" key={d}><span className="dot" style={{ background: c }} />{d}</span>)}</div>
        </div>
      </section>
    </>
  );
}
