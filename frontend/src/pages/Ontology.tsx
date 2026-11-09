import { useMemo, useState } from "react";
import { api, type GraphData, type Opp, href } from "../api";
import GraphView, { CLASS_COLOR } from "../components/GraphView";
import { Loading, useApp, useData } from "../ui";

type Onto = {
  namespace: string; version: string;
  classes: Record<string, { label: { en: string; ar: string }; parent: string | null; comment: string }>;
  relations: Record<string, { domain: string; range: string; label: { en: string; ar: string }; transitive?: boolean }>;
  properties: Record<string, { class: string; type: string; required: boolean; comment: string }>;
  vocabularies: Record<string, Record<string, { ar: string; syn?: string[] }>>;
};

export default function Ontology() {
  const { openOpp } = useApp();
  const onto = useData(() => api.get<Onto>("/api/ontology"));
  const opps = useData(() => api.get<Opp[]>("/api/opportunities?include_closed=false"));
  const [focus, setFocus] = useState("");
  const [view, setView] = useState<"instance" | "schema">("instance");
  const graph = useData(() => api.get<GraphData>(`/api/graph${focus ? `?focus=${focus}` : ""}`), [focus]);
  const schemaGraph = useMemo<GraphData | null>(() => {
    if (!onto.data) return null;
    const nodes = Object.entries(onto.data.classes).map(([id, c]) => ({ id, class: id in CLASS_COLOR ? id : "Stage", label: `${c.label.en} · ${c.label.ar}` }));
    const edges = Object.entries(onto.data.relations).map(([r, m]) => ({ source: m.domain, target: m.range, relation: r }));
    Object.entries(onto.data.classes).forEach(([id, c]) => c.parent && edges.push({ source: id, target: c.parent, relation: "subClassOf" }));
    return { nodes, edges, focus: "Opportunity" };
  }, [onto.data]);
  if (!onto.data) return <Loading error={onto.error} />;
  const o = onto.data;
  return (
    <>
      <div className="filters">
        <div className="seg" role="group" aria-label="Graph view">
          <button aria-pressed={view === "instance"} onClick={() => setView("instance")}>Knowledge graph (data)</button>
          <button aria-pressed={view === "schema"} onClick={() => setView("schema")}>Ontology schema</button>
        </div>
        {view === "instance" && (
          <label className="f">Focus<select className="in" value={focus} onChange={(e) => setFocus(e.target.value)}>
            <option value="">Whole active portfolio</option>{(opps.data || []).map((x) => <option key={x.id} value={x.id}>{x.id} · {x.name}</option>)}</select></label>
        )}
        <span style={{ flex: 1 }} />
        <a className="btn" href={href("/api/ontology.ttl")} download>Download OWL (Turtle)</a>
        <a className="btn" href={href("/api/ontology.jsonld")} download>Download JSON-LD</a>
      </div>
      <section className="panel">
        <div className="ph"><h2>{view === "schema" ? "Precast ontology v" + o.version : focus ? `Neighbourhood of ${focus}` : "Portfolio knowledge graph"}</h2>
          <span className="hint">Drag nodes; hover to highlight relations{view === "instance" ? "; click an opportunity to open it" : ""}</span></div>
        <div className="graph">
          {view === "schema" ? (schemaGraph && <GraphView data={schemaGraph} />) : graph.data ? (
            <GraphView data={graph.data} onSelect={(id, c) => { if (c === "Opportunity") openOpp(id); }} />
          ) : <Loading error={graph.error} />}
        </div>
        <div className="chips">{Object.entries(CLASS_COLOR).map(([c, col]) => <span key={c} className="chip"><span className="dot" style={{ background: col, borderRadius: 9 }} />{c}</span>)}</div>
      </section>
      <section className="grid g2">
        <div className="panel">
          <div className="ph"><h2>Relations</h2><span className="hint mono">{o.namespace}</span></div>
          <div className="tw"><table><thead><tr><th>Relation</th><th>Domain → Range</th><th>Arabic</th></tr></thead><tbody>
            {Object.entries(o.relations).map(([r, m]) => <tr key={r}><td className="mono">pc:{r}{m.transitive ? " (transitive)" : ""}</td><td>{m.domain} → {m.range}</td><td dir="rtl">{m.label.ar}</td></tr>)}
          </tbody></table></div>
        </div>
        <div className="panel">
          <div className="ph"><h2>Controlled vocabularies</h2><span className="hint">Used to validate imports and parse questions</span></div>
          <div className="tw"><table><thead><tr><th>Scheme</th><th>Terms (English · Arabic)</th></tr></thead><tbody>
            {Object.entries(o.vocabularies).map(([s, terms]) => (
              <tr key={s}><td className="mono">{s}</td><td>{Object.entries(terms).map(([t, m]) => <span key={t} className="chip" style={{ margin: 2 }} title={(m.syn || []).join(", ")}>{t} · {m.ar}</span>)}</td></tr>))}
          </tbody></table></div>
        </div>
      </section>
      <section className="panel">
        <div className="ph"><h2>Data properties</h2></div>
        <div className="tw"><table><thead><tr><th>Property</th><th>Class</th><th>Type</th><th>Required</th><th>Description</th></tr></thead><tbody>
          {Object.entries(o.properties).map(([p, m]) => <tr key={p}><td className="mono">pc:{p}</td><td>{m.class}</td><td className="mono">{m.type}</td><td>{m.required ? "Yes" : ""}</td><td>{m.comment}</td></tr>)}
        </tbody></table></div>
      </section>
    </>
  );
}
