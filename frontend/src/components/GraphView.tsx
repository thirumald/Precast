import { useEffect, useMemo, useRef, useState } from "react";
import type { GraphData } from "../api";
import { pct } from "../format";

export const CLASS_COLOR: Record<string, string> = {
  Opportunity: "var(--accent)", Counterparty: "var(--d2)", Country: "var(--d3)", Region: "#8A6A12", Site: "#B5651D",
  Domain: "var(--d4)", Stage: "#56666F", Outlook: "#56666F", ExecutiveSponsor: "var(--d5)", ExecutionalOwner: "var(--d5)",
  Person: "var(--d5)", Engagement: "#3B82A0", Action: "var(--neg)", Announcement: "#C2410C", Approval: "#9A7B1C",
  Prediction: "var(--pos)", ScoreFactor: "#6B7C85",
};

// In the portfolio view, label only the hub classes; others show on hover to keep the graph legible.
const ALWAYS_LABEL = new Set(["Opportunity", "Country", "Region", "Domain", "ExecutiveSponsor"]);

type N = { id: string; class: string; label: string; x: number; y: number; vx: number; vy: number; fixed?: boolean; r: number; meta: Record<string, unknown> };

/** Force-directed knowledge-graph view. Dependency-free; nodes can be dragged; click calls onSelect. */
export default function GraphView({ data, height = 620, onSelect }: { data: GraphData; height?: number; onSelect?: (id: string, cls: string) => void }) {
  const W = 1000, H = height;
  const ref = useRef<SVGSVGElement>(null);
  const [tick, setTick] = useState(0);
  const [hover, setHover] = useState<string | null>(null);

  const sim = useMemo(() => {
    const deg: Record<string, number> = {};
    data.edges.forEach((e) => { deg[e.source] = (deg[e.source] || 0) + 1; deg[e.target] = (deg[e.target] || 0) + 1; });
    const nodes: N[] = data.nodes.map((n, i) => {
      const a = (i / data.nodes.length) * Math.PI * 2;
      const isFocus = n.id === data.focus;
      return { id: n.id, class: n.class, label: n.label, meta: n, x: W / 2 + Math.cos(a) * (isFocus ? 0 : 260), y: H / 2 + Math.sin(a) * (isFocus ? 0 : 220),
               vx: 0, vy: 0, fixed: isFocus, r: n.class === "Opportunity" ? 9 + Math.min(10, Math.sqrt(Number(n.value || 0) / 1e7)) : 5 + Math.min(8, (deg[n.id] || 1) * 0.9) };
    });
    const idx = new Map(nodes.map((n) => [n.id, n]));
    const links = data.edges.map((e) => ({ s: idx.get(e.source)!, t: idx.get(e.target)!, rel: e.relation })).filter((l) => l.s && l.t);
    const step = (alpha: number) => {
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j];
          let dx = b.x - a.x, dy = b.y - a.y;
          let d2 = dx * dx + dy * dy;
          if (d2 < 1) { dx = Math.random(); dy = Math.random(); d2 = 1; }
          const f = (1600 * alpha) / d2;
          const d = Math.sqrt(d2);
          a.vx -= (dx / d) * f; a.vy -= (dy / d) * f; b.vx += (dx / d) * f; b.vy += (dy / d) * f;
        }
      }
      for (const l of links) {
        const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const target = l.s.class === "Opportunity" && l.t.class === "Opportunity" ? 160 : 90;
        const f = ((d - target) / d) * 0.06 * alpha;
        l.s.vx += dx * f; l.s.vy += dy * f; l.t.vx -= dx * f; l.t.vy -= dy * f;
      }
      for (const n of nodes) {
        n.vx += (W / 2 - n.x) * 0.004 * alpha; n.vy += (H / 2 - n.y) * 0.004 * alpha;
        if (n.fixed) { n.vx = 0; n.vy = 0; continue; }
        n.vx *= 0.6; n.vy *= 0.6;
        n.x = Math.max(20, Math.min(W - 20, n.x + n.vx)); n.y = Math.max(20, Math.min(H - 20, n.y + n.vy));
      }
    };
    for (let k = 0; k < 260; k++) step(1 - k / 300);
    return { nodes, links, step };
  }, [data, H]);

  useEffect(() => {
    let raf = 0, k = 0;
    const loop = () => { sim.step(0.15); setTick((t) => t + 1); if (++k < 40) raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [sim]);

  const drag = useRef<N | null>(null);
  const toSvg = (e: React.PointerEvent) => {
    const r = ref.current!.getBoundingClientRect();
    return { x: ((e.clientX - r.left) / r.width) * W, y: ((e.clientY - r.top) / r.height) * H };
  };
  const neighbours = useMemo(() => {
    if (!hover) return null;
    const s = new Set([hover]);
    sim.links.forEach((l) => { if (l.s.id === hover) s.add(l.t.id); if (l.t.id === hover) s.add(l.s.id); });
    return s;
  }, [hover, sim, tick]);

  return (
    <svg ref={ref} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Knowledge graph"
      onPointerMove={(e) => { if (drag.current) { const p = toSvg(e); drag.current.x = p.x; drag.current.y = p.y; sim.step(0.05); setTick((t) => t + 1); } }}
      onPointerUp={() => { drag.current = null; }} onPointerLeave={() => { drag.current = null; }}>
      <defs><marker id="arr" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="var(--muted)" /></marker></defs>
      {sim.links.map((l, i) => {
        const dim = neighbours && !(neighbours.has(l.s.id) && neighbours.has(l.t.id));
        const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
        const x2 = l.t.x - (dx / d) * (l.t.r + 2), y2 = l.t.y - (dy / d) * (l.t.r + 2);
        return (
          <g key={i} opacity={dim ? 0.12 : 0.75}>
            <line x1={l.s.x} y1={l.s.y} x2={x2} y2={y2} stroke="var(--muted)" strokeWidth="1" markerEnd="url(#arr)" />
            {(data.focus || neighbours) && !dim && <text className="edge-l" x={(l.s.x + l.t.x) / 2} y={(l.s.y + l.t.y) / 2 - 3} textAnchor="middle">{l.rel}</text>}
          </g>
        );
      })}
      {sim.nodes.map((n) => {
        const dim = neighbours && !neighbours.has(n.id);
        const p = n.meta.p as number | undefined;
        return (
          <g key={n.id} className="mx-dot" opacity={dim ? 0.2 : 1} transform={`translate(${n.x},${n.y})`}
            onPointerDown={(e) => { (e.target as Element).setPointerCapture?.(e.pointerId); drag.current = n; }}
            onPointerEnter={() => setHover(n.id)} onPointerLeave={() => setHover(null)}
            onClick={() => onSelect?.(n.id, n.class)}>
            <title>{`${n.class}: ${n.label}${p != null ? ` · p=${pct(p)}` : ""}`}</title>
            <circle r={n.r} fill={CLASS_COLOR[n.class] || "var(--muted)"} stroke="var(--surface)" strokeWidth="2" />
            {n.class === "Opportunity" && p != null && (
              <circle r={n.r + 3} fill="none" stroke={p >= 0.6 ? "var(--pos)" : p >= 0.3 ? "var(--neu)" : "var(--neg)"} strokeWidth="2.5"
                strokeDasharray={`${2 * Math.PI * (n.r + 3) * p} 999`} transform="rotate(-90)" />
            )}
            {(data.focus || ALWAYS_LABEL.has(n.class) || neighbours?.has(n.id)) && <text x={n.r + 5} y={4}>{n.label.length > 34 ? n.label.slice(0, 32) + "…" : n.label}</text>}
          </g>
        );
      })}
    </svg>
  );
}
