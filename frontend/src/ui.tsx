import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { cls, pct, riskTone } from "./format";

/* ---------- app context ---------- */
type AppCtx = { openOpp: (id: string) => void; toast: (m: string) => void; version: number; bump: () => void; lang: "en" | "ar" };
export const App = createContext<AppCtx>({ openOpp: () => {}, toast: () => {}, version: 0, bump: () => {}, lang: "en" });
export const useApp = () => useContext(App);

/* ---------- data hook ---------- */
export function useData<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const { version } = useApp();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const load = useCallback(() => {
    const n = ++seq.current;
    setLoading(true);
    fn().then((d) => { if (n === seq.current) { setData(d); setError(null); } })
      .catch((e: Error) => { if (n === seq.current) setError(e.message); })
      .finally(() => { if (n === seq.current) setLoading(false); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);
  useEffect(load, [load]);
  return { data, error, loading, reload: load, setData };
}

export function Loading({ error, label = "Loading" }: { error?: string | null; label?: string }) {
  if (error) return <div className="notice err"><b>Couldn't load.</b> {error}</div>;
  return <div className="empty"><span className="spin" /> {label}…</div>;
}

/* ---------- small visuals ---------- */
export function Score5({ n }: { n?: number }) {
  const v = Number(n || 0);
  return <span className="score5" aria-label={`${v} of 5`}>{[1, 2, 3, 4, 5].map((i) => <i key={i} className={i <= v ? "f" : ""} />)}</span>;
}

export function Prob({ p, delta }: { p: number; delta?: number }) {
  const tone = riskTone(p);
  return (
    <span className="prob" title={`Win probability ${pct(p, 1)}`}>
      <span className="track"><span className="fill" style={{ width: `${p * 100}%`, background: `var(--${tone})` }} /></span>
      <b>{pct(p)}</b>
      {delta != null && Math.abs(delta) >= 0.02 && (
        <span className={cls("idc", delta > 0 ? "ok" : "bad")}>{delta > 0 ? "▲" : "▼"}{Math.abs(Math.round(delta * 100))}</span>
      )}
    </span>
  );
}

export function Spark({ values, w = 96, h = 26, color }: { values: number[]; w?: number; h?: number; color?: string }) {
  if (!values?.length) return null;
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min || 0.01;
  const xs = values.map((_, i) => (i / Math.max(1, values.length - 1)) * (w - 4) + 2);
  const ys = values.map((v) => h - 3 - ((v - min) / span) * (h - 6));
  const d = xs.map((x, i) => `${i ? "L" : "M"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join("");
  const up = values[values.length - 1] >= values[0];
  const c = color ?? (up ? "var(--pos)" : "var(--neg)");
  return (
    <svg className="spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`Trend from ${pct(values[0])} to ${pct(values[values.length - 1])}`}>
      <path d={d} fill="none" stroke={c} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={xs[xs.length - 1]} cy={ys[ys.length - 1]} r="2.6" fill={c} />
    </svg>
  );
}

export function Chip({ tone, children }: { tone?: string; children: ReactNode }) {
  return <span className={cls("chip", tone)}>{children}</span>;
}

export function OutlookChip({ v }: { v?: string }) {
  if (!v) return <>—</>;
  return <Chip tone={({ Positive: "pos", Neutral: "neu", Negative: "neg" } as Record<string, string>)[v]}>{v}</Chip>;
}

export function Approval({ v }: { v?: string }) {
  const c = /approved|yes|not required/i.test(v || "") ? "ok" : /rejected|^no$/i.test(v || "") ? "bad" : /pending/i.test(v || "") ? "pend" : "";
  return <span className={c}>{v || "—"}</span>;
}

export function Modal({ onClose, children, title }: { onClose: () => void; children: ReactNode; title: string }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="modal" onMouseDown={(e) => e.target === e.currentTarget && onClose()} role="dialog" aria-modal="true" aria-label={title}>
      <div>
        <div className="dh-row"><h3>{title}</h3><button className="x" onClick={onClose} aria-label="Close">×</button></div>
        {children}
      </div>
    </div>
  );
}

export function copy(text: string, toast: (m: string) => void) {
  navigator.clipboard?.writeText(text).then(() => toast("Copied to clipboard"), () => toast("Couldn't copy; select the text instead"));
}

export function EngineBadge({ engine }: { engine?: string }) {
  if (!engine) return null;
  return <Chip tone={engine === "llm" ? "acc" : ""}>{engine === "llm" ? "Local LLM" : "Template engine"}</Chip>;
}

/* nav icons: simple strokes */
export const Icon = ({ d }: { d: string }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>
);
