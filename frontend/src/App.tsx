import { useCallback, useEffect, useState } from "react";
import { api, asset, STATIC, snapshotDate } from "./api";
import OppDrawer from "./components/OppDrawer";
import { LangCtx, useT, type Lang } from "./i18n";
import Announcements from "./pages/Announcements";
import Ask from "./pages/Ask";
import Data from "./pages/Data";
import Engagements from "./pages/Engagements";
import Executive from "./pages/Executive";
import Forecast from "./pages/Forecast";
import Interventions from "./pages/Interventions";
import MapView from "./pages/MapView";
import Matrix from "./pages/Matrix";
import Ontology from "./pages/Ontology";
import Overview from "./pages/Overview";
import Register from "./pages/Register";
import Reports from "./pages/Reports";
import { App as Ctx, Icon } from "./ui";

const ROUTES = [
  { id: "executive", label: "Executive Dashboard", el: Executive, icon: "M12 3v4M12 17v4M3 12h4M17 12h4M12 12m-5 0a5 5 0 1 0 10 0a5 5 0 1 0-10 0" },
  { id: "reports", label: "Reports", el: Reports, icon: "M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M8 13h8M8 17h5" },
  { sep: true },
  { id: "overview", label: "Pipeline Overview", el: Overview, icon: "M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z" },
  { id: "forecast", label: "Forecast & Scoring", el: Forecast, icon: "M3 3v18h18M7 15l4-4 3 3 6-7" },
  { id: "matrix", label: "Executive Matrix", el: Matrix, icon: "M4 4h16v16H4zM4 12h16M12 4v16" },
  { id: "map", label: "Geospatial", el: MapView, icon: "M12 21s-7-6.2-7-11a7 7 0 1 1 14 0c0 4.8-7 11-7 11zM12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z" },
  { id: "interventions", label: "Interventions", el: Interventions, icon: "M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" },
  { id: "announcements", label: "Announcements", el: Announcements, icon: "M3 11l18-8v18L3 13zM7 12v6a2 2 0 0 0 4 0v-4" },
  { id: "engagements", label: "Engagement Log", el: Engagements, icon: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" },
  { id: "register", label: "Register", el: Register, icon: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" },
  { sep: true },
  { id: "ask", label: "Ask Precast", el: Ask, icon: "M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z" },
  { id: "ontology", label: "Ontology & Graph", el: Ontology, icon: "M5 6a2 2 0 1 0 0-.01M19 6a2 2 0 1 0 0-.01M12 19a2 2 0 1 0 0-.01M7 6h10M6 8l5 9M18 8l-5 9" },
  { id: "data", label: "Data & Integrations", el: Data, icon: "M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3zM4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" },
] as const;

// Static pages set these before loading the bundle: the page's use case and, optionally, an opportunity to open.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const BOOT = globalThis as any;
if (BOOT.__PRECAST_ROUTE__ && !location.hash) history.replaceState(null, "", "#/" + BOOT.__PRECAST_ROUTE__);

type Route = Extract<(typeof ROUTES)[number], { id: string }>;
const routeOf = () => (ROUTES.find((r) => "id" in r && new RegExp(`^#/${r.id}($|[/?])`).test(location.hash)) as Route | undefined) ?? (ROUTES[0] as Route);

function Logo() {
  return (
    <svg width="34" height="34" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#0A6E7C" />
      <path d="M7 23c4-9 10-13 18-14" stroke="#fff" strokeWidth="2.6" fill="none" strokeLinecap="round" />
      <path d="M7 23c4-9 10-13 18-14" stroke="#9FE3EA" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeDasharray="2 4" transform="translate(0 4)" opacity=".6" />
      <circle cx="25" cy="9" r="3" fill="#fff" />
    </svg>
  );
}

function Shell() {
  const t = useT();
  const [route, setRoute] = useState<Route>(routeOf);
  const [opp, setOpp] = useState<string | null>(BOOT.__PRECAST_OPEN_OPP__ ?? null);
  const [toastMsg, setToast] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [llm, setLlm] = useState<{ available: boolean; model?: string } | null>(null);
  const [lang, setLang] = useState<Lang>(() => { try { return (localStorage.getItem("precast.lang") as Lang) || "en"; } catch { return "en"; } });
  const [theme, setTheme] = useState<string>(() => { try { return localStorage.getItem("precast.theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"); } catch { return "light"; } });

  useEffect(() => { const h = () => setRoute(routeOf()); window.addEventListener("hashchange", h); return () => window.removeEventListener("hashchange", h); }, []);
  useEffect(() => { document.documentElement.dataset.theme = theme; try { localStorage.setItem("precast.theme", theme); } catch { /* ignore */ } }, [theme]);
  useEffect(() => { document.documentElement.dir = lang === "ar" ? "rtl" : "ltr"; document.documentElement.lang = lang; try { localStorage.setItem("precast.lang", lang); } catch { /* ignore */ } }, [lang]);
  useEffect(() => { api.get<{ llm: { available: boolean; model?: string } }>("/api/health").then((h) => setLlm(h.llm)).catch(() => setLlm(null)); }, [version]);
  useEffect(() => { if (!toastMsg) return; const id = setTimeout(() => setToast(null), 4200); return () => clearTimeout(id); }, [toastMsg]);

  const openOpp = useCallback((id: string) => setOpp(id), []);
  const toast = useCallback((m: string) => setToast(m), []);
  const bump = useCallback(() => setVersion((v) => v + 1), []);
  const Page = route.el;

  return (
    <LangCtx.Provider value={lang}>
      <Ctx.Provider value={{ openOpp, toast, version, bump, lang }}>
        <div className="shell">
          <nav className="side" aria-label="Main">
            <div className="brand">
              <img className="pl" src={asset("/brand/presight-logo-white.svg")} alt="Presight" />
              <div className="prod"><Logo /><div><b>Precast</b><small>{t("Strategic Intelligence Hub")}</small></div></div>
            </div>
            <div className="nav">
              {ROUTES.map((r, i) => "sep" in r ? <div key={i} className="sep" /> : (
                <a key={r.id} href={"#/" + r.id} className={route.id === r.id ? "on" : ""} aria-current={route.id === r.id ? "page" : undefined}>
                  <Icon d={r.icon} />{t(r.label)}
                </a>
              ))}
            </div>
            <div className="side-foot">
              <span className={"engine" + (llm?.available ? " on" : "")}><i />{llm?.available ? `LLM · ${llm.model}` : "LLM offline · template mode"}</span>
              <span>Sovereign deployment · data stays on-premises</span>
              <span>Precast v1.1 · Presight</span>
            </div>
          </nav>
          <main>
            <header className="top">
              <div><h1>{t(route.label)}</h1><div className="tag">{t("Predict. Forecast. Precast.")}</div></div>
              <span className="grow" />
              {STATIC && <span className="static-tag" title="Data captured when this static edition was built; editing and integrations need the full app.">Static snapshot · {snapshotDate} · read-only</span>}
              <a className="btn" href="#/ask">✦ {t("Ask")}</a>
              <div className="seg" role="group" aria-label="Language">
                <button aria-pressed={lang === "en"} onClick={() => setLang("en")}>EN</button>
                <button aria-pressed={lang === "ar"} onClick={() => setLang("ar")}>عربي</button>
              </div>
              <button className="btn ghost" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Toggle dark mode">{theme === "dark" ? "☀" : "☾"}</button>
            </header>
            <div className="page"><Page key={route.id} /></div>
          </main>
        </div>
        {opp && <OppDrawer id={opp} onClose={() => setOpp(null)} />}
        {toastMsg && <div className="toast" role="status">{toastMsg}</div>}
      </Ctx.Provider>
    </LangCtx.Provider>
  );
}

export default Shell;
