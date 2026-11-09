export function aed(v?: number | null, unit = true): string {
  const n = Number(v || 0);
  if (!n) return unit ? "AED 0" : "0";
  const a = Math.abs(n);
  const s = a >= 1e9 ? (n / 1e9).toFixed(2) + "bn" : a >= 1e6 ? (n / 1e6).toFixed(a >= 1e8 ? 0 : 1) + "m" : a >= 1e3 ? Math.round(n / 1e3) + "k" : String(Math.round(n));
  return unit ? "AED " + s : s;
}
export const pct = (p?: number | null, digits = 0) => (p == null ? "—" : (p * 100).toFixed(digits) + "%");
export const pts = (d?: number | null) => (d == null ? "" : (d > 0 ? "+" : d < 0 ? "−" : "±") + Math.abs(Math.round(d * 100)) + " pts");
export const toDate = (s?: string | null) => (s ? new Date(s.length <= 10 ? s + "T00:00:00" : s) : null);
export function fd(s?: string | null, year = true): string {
  const d = toDate(s);
  if (!d || isNaN(+d)) return "—";
  return d.toLocaleDateString("en-GB", year ? { day: "numeric", month: "short", year: "numeric" } : { day: "numeric", month: "short" });
}
export function daysFrom(s?: string | null): number | null {
  const d = toDate(s);
  if (!d) return null;
  const t = new Date(); t.setHours(0, 0, 0, 0);
  return Math.round((+d - +t) / 864e5);
}
export function rel(s?: string | null): string {
  const n = daysFrom(s);
  if (n === null) return "";
  if (n === 0) return "today";
  return n < 0 ? `${-n}d overdue` : `in ${n}d`;
}
export const DOMAIN_COLOR: Record<string, string> = {
  Security: "var(--d1)", Defense: "var(--d2)", Urban: "var(--d3)", Financial: "var(--d4)", Energy: "var(--d5)",
};
export const OUTLOOK_COLOR: Record<string, string> = { Positive: "var(--pos)", Neutral: "var(--neu)", Negative: "var(--neg)" };
export const riskTone = (p: number) => (p >= 0.6 ? "pos" : p >= 0.3 ? "neu" : "neg");
export const cls = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(" ");
