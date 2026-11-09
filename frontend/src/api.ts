export type Factor = { key: string; label: string; impact: number; detail: string };
export type Score = {
  id: string; p: number; ev: number; value: number; potential_manual: number; potential_dynamic: number;
  expected_close: string; quarter: string; risk: "low" | "medium" | "high"; factors: Factor[];
  trend?: number[]; delta_14d?: number; p_next?: number; potential_next?: number; direction?: "up" | "down" | "flat";
  open_actions?: number; overdue?: number; blocked?: number;
};
export type Opp = {
  id: string; name: string; country?: string; domain?: string; segment?: string; counterparty?: string; type?: string;
  sponsor?: string; owner?: string; priority?: number; commercial?: number; value?: number; status?: string; outlook?: string;
  rationale?: string; latest?: string; last_engagement?: string; milestone?: string; milestone_date?: string;
  next_action?: string; action_owner?: string; intervention?: string; announce?: string; sensitivity?: string;
  verified?: string; source?: string; lat?: number; lon?: number; site?: string; competitors?: number;
  teams_channel_id?: string; teams_web_url?: string; sharepoint_url?: string;
  score: Score; actions_open: number; actions_blocked: number; escalation: boolean;
};
export type Engagement = { id: string; opp: string; opp_name?: string; date?: string; type?: string; external?: string; internal?: string;
  summary?: string; commitments?: string; follow_up?: string; owner?: string; due?: string; source?: string; link?: string };
export type Action = { id: string; opp: string; opp_name?: string; title?: string; category?: string; owner?: string; due?: string;
  status?: string; priority?: string; blocker?: string; escalate?: string; update_note?: string };
export type Announcement = { id: string; opp: string; opp_name?: string; title?: string; type?: string; target?: string; event?: string;
  lead?: string; readiness?: string; legal?: string; ir?: string; counterparty?: string; disclose?: string; cleared?: boolean };
export type Discussion = { id: string; opp: string; parent?: string; author?: string; body?: string; created?: string; source?: string; web_url?: string };
export type OppDetail = Opp & { actions: Action[]; engagements: Engagement[]; announcements: Announcement[]; discussions: Discussion[]; region?: string };
export type Agg = { key: string; count: number; value: number; ev: number };
export type Quarter = { quarter: string; commit: number; best_case: number; pipeline: number; weighted: number; count: number };
export type Overview = {
  as_of: string;
  kpis: Record<string, number | string>;
  stages: Agg[]; closed: { key: string; count: number; value: number }[]; outlook: Agg[]; domains: Agg[];
  forecast: { quarters: Quarter[] };
  attention: { id: string; name: string; country?: string; status?: string; sponsor?: string; value?: number; p: number; delta?: number;
    priority?: number; reasons: [string, string][]; high: boolean }[];
  timeline: { date: string; title: string; meta: string; kind: string; opp: string }[];
  movers: { id: string; name: string; p: number; delta: number; trend: number[] }[];
  calibration: { global_win_rate: number; domains: { domain: string; won: number; lost: number; win_rate: number }[] };
};
export type AskResult = { answer: string; engine: string; filters: Record<string, unknown>;
  summary: { matched: number; total_value_aed: number; expected_value_aed: number; scope: string };
  rows: Opp[]; citations: { id: string; text: string; opp?: string; opp_name?: string; date?: string; kind?: string }[] };
export type GraphData = { nodes: { id: string; class: string; label: string; [k: string]: unknown }[];
  edges: { source: string; target: string; relation: string }[]; focus?: string | null };
export type M365Status = { configured: boolean; sharepoint: boolean; teams: boolean; teams_posting: boolean; outlook: boolean;
  settings: Record<string, string>; last_sync: Record<string, string | null> };

/* ---------- static edition ----------
 * When the bundle is opened from the static/ folder, window.__PRECAST_SNAPSHOT__ holds every API
 * response captured at build time. Reads are served from it; writes are refused (read-only demo).
 */
type Snap = { built: string; get: Record<string, unknown>; post: Record<string, unknown> };
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const SNAP: Snap | undefined = (globalThis as any).__PRECAST_SNAPSHOT__;
export const STATIC = !!SNAP;
export const snapshotDate = SNAP?.built;

export function normKey(path: string): string {
  const [p, q] = path.split("?");
  if (!q) return p;
  const sp = new URLSearchParams(q);
  const items = [...sp.entries()].sort(([a], [b]) => a.localeCompare(b));
  return items.length ? p + "?" + new URLSearchParams(items).toString() : p;
}

/** Map server download links to files shipped in static/downloads. */
export function href(path: string): string | undefined {
  if (!STATIC) return path;
  const [p, q] = path.split("?");
  if (p === "/api/ingest/template") return q?.includes("examples=false") ? "downloads/Precast_Tracker_Template_blank.xlsx" : "downloads/Precast_Tracker_Template.xlsx";
  if (p === "/api/export") return "downloads/Precast_Tracker_Export.xlsx";
  if (p === "/api/ontology.ttl") return "downloads/precast-ontology.ttl";
  if (p === "/api/ontology.jsonld") return "downloads/precast-ontology.jsonld";
  const m = p.match(/^\/api\/reports\/([\w-]+)\.xlsx$/);
  if (m) return q ? undefined : `downloads/reports/Precast_${m[1]}.xlsx`;
  return undefined;
}
export const asset = (p: string) => (STATIC ? p.replace(/^\//, "") : p);
export const READ_ONLY = "This is the static, read-only edition. Run the full Precast app to edit, sync or generate new content.";

function fromSnapshot<T>(method: string, path: string, body?: unknown): T {
  const clone = (v: unknown) => JSON.parse(JSON.stringify(v)) as T;
  if (method === "GET") {
    const k = normKey(path);
    if (k in SNAP!.get) return clone(SNAP!.get[k]);
    if (k.includes("?") && !/[?&](include_closed|quarters|potential|focus|examples)=/.test(k))
      throw new Error("This filter combination isn't included in the static snapshot. Clear one of the filters, or run the full app.");
    throw new Error("Not available in the static edition.");
  }
  if (method === "POST") {
    const b = (body || {}) as Record<string, unknown>;
    const key = path.endsWith("/draft") ? `${path}|${b.kind || "memo"}` : path === "/api/ask" ? `${path}|${String(b.question || "").trim()}`
      : path === "/api/engagements/extract" ? `${path}|${String(b.text || "").trim()}` : path;
    if (key in SNAP!.post) return clone(SNAP!.post[key]);
    if (path === "/api/ask") return clone(localAsk(String(b.question || "")));
  }
  throw new Error(READ_ONLY);
}

/* Offline Ask Precast: a compact port of the server's keyword parser, so any question still gets a computed answer. */
const DOM: [RegExp, string][] = [[/securit|public safety|safe city|cyber|أمن|الأمن|أمنية/, "Security"], [/defen[cs]e|military|border|دفاع|الدفاع|الدفاعية/, "Defense"],
  [/urban|smart city|transport|traffic|حضري|المدن|النقل/, "Urban"], [/financ|bank|مالي|المالية/, "Financial"], [/energy|grid|power|renewable|طاقة|الطاقة/, "Energy"]];
const CTRY: [RegExp, string][] = [[/\bksa\b|saudi|السعودية/, "Saudi Arabia"], [/\buae\b|emirates|الإمارات|الامارات/, "UAE"], [/egypt|مصر/, "Egypt"],
  [/kazakhstan|كازاخستان/, "Kazakhstan"], [/morocco|المغرب/, "Morocco"], [/indonesia|إندونيسيا/, "Indonesia"], [/kenya|كينيا/, "Kenya"],
  [/albania|ألبانيا/, "Albania"], [/azerbaijan|أذربيجان/, "Azerbaijan"], [/uzbekistan|أوزبكستان/, "Uzbekistan"], [/montenegro|الجبل الأسود/, "Montenegro"],
  [/dominican|الدومينيكان/, "Dominican Republic"], [/oman|عمان|عُمان/, "Oman"]];
const STAGES = ["Exploratory", "Active Engagement", "Proposal", "Negotiation", "Agreement", "Execution"];
function localAsk(q: string) {
  const t = q.toLowerCase(), ar = /[\u0600-\u06FF]/.test(q);
  const f: Record<string, unknown> = {};
  for (const [re, v] of DOM) if (re.test(t)) { f.domain = v; break; }
  for (const [re, v] of CTRY) if (re.test(t)) { f.country = v; break; }
  for (const s of STAGES) if (t.includes(s.toLowerCase())) f.stage = s;
  if (/block|stuck|stall|escalat|متعثر|متوقف|تصعيد/.test(t)) f.blocked = true;
  if (/interven|ceo|تدخل/.test(t)) f.intervention = true;
  if (/risk|weak|negative|مخاطر|خطر|سلبي/.test(t)) f.at_risk = true;
  f.metric = /how many|count|عدد/.test(t) ? "count" : /revenue|value|pipeline|impact|aed|قيمة|إيرادات/.test(t) ? "value" : "list";
  const opps = (SNAP!.get["/api/opportunities?include_closed=false"] || []) as Opp[];
  const rows = opps.filter((o) => (!f.domain || o.domain === f.domain) && (!f.country || o.country === f.country) && (!f.stage || o.status === f.stage)
    && (!f.blocked || o.actions_blocked > 0 || o.escalation) && (!f.intervention || o.intervention === "Yes")
    && (!f.at_risk || o.score.p < 0.35 || o.outlook === "Negative")).sort((a, b) => b.score.ev - a.score.ev);
  const total = rows.reduce((s, o) => s + (o.value || 0), 0), ev = rows.reduce((s, o) => s + o.score.ev, 0);
  const fm = (v: number) => (v >= 1e9 ? `AED ${(v / 1e9).toFixed(2)}bn` : `AED ${(v / 1e6).toFixed(1)}m`);
  const scope = [f.blocked && "blocked/escalated", f.at_risk && "at-risk", f.intervention && "needing intervention", f.domain, f.stage, f.country && `in ${f.country}`].filter(Boolean).join(" ") || "all active";
  const answer = !rows.length ? (ar ? "لا توجد فرص مطابقة." : `No opportunities match (${scope}).`)
    : (ar ? `${rows.length} فرصة بقيمة ${fm(total)}، والقيمة المتوقعة المرجحة بالمخاطر ${fm(ev)}.` : `${rows.length} opportunit${rows.length === 1 ? "y" : "ies"} (${scope}) worth ${fm(total)}; risk-weighted expected value ${fm(ev)}.`)
      + "\n\n" + rows.slice(0, 5).map((o) => `- ${o.id} ${o.name} (${o.country}, ${o.status}): ${fm(o.value || 0)}, ${Math.round(o.score.p * 100)}% win probability.`).join("\n");
  return { answer, engine: "template", filters: f, summary: { matched: rows.length, total_value_aed: total, expected_value_aed: ev, scope }, rows: rows.slice(0, 25), citations: [] };
}

const KEY = "precast.apiKey";
export const apiKey = {
  get: () => { try { return localStorage.getItem(KEY) || ""; } catch { return ""; } },
  set: (v: string) => { try { localStorage.setItem(KEY, v); } catch { /* storage unavailable */ } },
};

async function req<T>(method: string, path: string, body?: unknown, form?: FormData): Promise<T> {
  if (SNAP) { await new Promise((r) => setTimeout(r, 30)); return fromSnapshot<T>(method, path, body); }
  const headers: Record<string, string> = {};
  const k = apiKey.get();
  if (k) headers["X-API-Key"] = k;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const r = await fetch(path, { method, headers, body: form ?? (body !== undefined ? JSON.stringify(body) : undefined) });
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* not json */ }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export const api = {
  get: <T,>(p: string) => req<T>("GET", p),
  post: <T,>(p: string, b?: unknown) => req<T>("POST", p, b ?? {}),
  put: <T,>(p: string, b: unknown) => req<T>("PUT", p, b),
  patch: <T,>(p: string, b: unknown) => req<T>("PATCH", p, b),
  del: <T,>(p: string) => req<T>("DELETE", p),
  upload: <T,>(p: string, f: FormData) => req<T>("POST", p, undefined, f),
};
