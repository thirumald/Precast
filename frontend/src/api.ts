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

const KEY = "precast.apiKey";
export const apiKey = {
  get: () => { try { return localStorage.getItem(KEY) || ""; } catch { return ""; } },
  set: (v: string) => { try { localStorage.setItem(KEY, v); } catch { /* storage unavailable */ } },
};

async function req<T>(method: string, path: string, body?: unknown, form?: FormData): Promise<T> {
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
