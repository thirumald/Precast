import maplibregl, { type GeoJSONSource, type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import { feature } from "topojson-client";
import countries110 from "world-atlas/countries-110m.json";
import { api } from "../api";
import { aed, pct } from "../format";
import { Loading, useApp, useData } from "../ui";

type Geo = GeoJSON.FeatureCollection & {
  countries: { country: string; region?: string; count: number; value: number; ev: number; risk: number; competitor_density: number; lat: number; lon: number }[];
};

const css = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || "#888";

/** Offline base map: Natural Earth 110m countries bundled with the app (air-gap friendly).
 *  Set VITE_MAP_STYLE to a self-hosted vector-tile style URL for street-level detail. */
function baseStyle(): StyleSpecification | string {
  const ext = import.meta.env.VITE_MAP_STYLE as string | undefined;
  if (ext) return ext;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const land = feature(countries110 as any, (countries110 as any).objects.countries) as unknown as GeoJSON.FeatureCollection;
  return {
    version: 8,
    sources: { land: { type: "geojson", data: land } },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": css("--sunk") } },
      { id: "land", type: "fill", source: "land", paint: { "fill-color": css("--surface") } },
      { id: "borders", type: "line", source: "land", paint: { "line-color": css("--line"), "line-width": 0.8 } },
    ],
  } as StyleSpecification;
}

export default function MapView() {
  const { openOpp } = useApp();
  const { data, error } = useData(() => api.get<Geo>("/api/geo"));
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [layers, setLayers] = useState({ clusters: true, risk: true, competitors: false, closed: false });
  const [sel, setSel] = useState<Geo["countries"][0] | null>(null);

  useEffect(() => {
    if (!data || !box.current) return;
    const m = new maplibregl.Map({ container: box.current, style: baseStyle(), center: [45, 28], zoom: 2.1, attributionControl: { compact: true } });
    map.current = m;
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.on("load", () => {
      const pts = { ...data, features: data.features } as GeoJSON.FeatureCollection;
      m.addSource("opps", { type: "geojson", data: pts, cluster: true, clusterRadius: 38, clusterMaxZoom: 6,
        clusterProperties: { value: ["+", ["get", "value"]], ev: ["+", ["get", "ev"]] } });
      m.addSource("opps-flat", { type: "geojson", data: pts });
      m.addSource("countries", { type: "geojson", data: { type: "FeatureCollection", features: data.countries.map((c) => ({
        type: "Feature", geometry: { type: "Point", coordinates: [c.lon, c.lat] }, properties: c })) } });
      const acc = css("--accent"), neg = css("--neg"), neu = css("--neu"), pos = css("--pos");
      m.addLayer({ id: "risk-heat", type: "heatmap", source: "opps-flat", filter: ["==", ["get", "active"], true], maxzoom: 9,
        paint: { "heatmap-weight": ["interpolate", ["linear"], ["get", "at_risk_value"], 0, 0, 3e8, 1],
          "heatmap-intensity": 1.1, "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 1, 28, 6, 60],
          "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"], 0, "rgba(0,0,0,0)", 0.25, "rgba(224,184,76,.35)", 0.6, "rgba(240,122,112,.55)", 1, "rgba(179,38,30,.75)"],
          "heatmap-opacity": 0.85 } });
      m.addLayer({ id: "competitors", type: "circle", source: "countries", layout: { visibility: "none" },
        paint: { "circle-radius": ["interpolate", ["linear"], ["get", "competitor_density"], 0, 6, 4, 34], "circle-color": "rgba(59,76,184,.18)",
          "circle-stroke-color": "rgba(59,76,184,.7)", "circle-stroke-width": 1.5 } });
      m.addLayer({ id: "clusters", type: "circle", source: "opps", filter: ["has", "point_count"],
        paint: { "circle-color": acc, "circle-opacity": 0.88, "circle-stroke-color": "#fff", "circle-stroke-width": 2,
          "circle-radius": ["interpolate", ["linear"], ["get", "value"], 1e7, 16, 1e9, 34] } });
      m.addLayer({ id: "points", type: "circle", source: "opps", filter: ["all", ["!", ["has", "point_count"]], ["==", ["get", "active"], true]],
        paint: { "circle-radius": ["interpolate", ["linear"], ["get", "value"], 5e6, 6, 4e8, 22],
          "circle-color": ["case", [">=", ["get", "p"], 0.6], pos, [">=", ["get", "p"], 0.3], neu, neg],
          "circle-opacity": 0.85, "circle-stroke-color": "#fff", "circle-stroke-width": 1.6 } });
      m.addLayer({ id: "closed", type: "circle", source: "opps-flat", layout: { visibility: "none" }, filter: ["==", ["get", "active"], false],
        paint: { "circle-radius": 5, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": css("--muted"), "circle-stroke-width": 1.5 } });
      m.on("click", "clusters", async (e) => {
        const f = e.features?.[0]; if (!f) return;
        const src = m.getSource("opps") as GeoJSONSource;
        const z = await src.getClusterExpansionZoom(f.properties.cluster_id);
        m.easeTo({ center: (f.geometry as GeoJSON.Point).coordinates as [number, number], zoom: z });
      });
      const popup = new maplibregl.Popup({ closeButton: false, offset: 12 });
      m.on("mouseenter", "points", (e) => {
        m.getCanvas().style.cursor = "pointer";
        const p = e.features?.[0]?.properties as Record<string, unknown>;
        popup.setLngLat((e.features![0].geometry as GeoJSON.Point).coordinates as [number, number])
          .setHTML(`<b>${String(p.name)}</b><br><span style="color:var(--muted)">${String(p.site || p.country)}</span><br>${aed(Number(p.value))} · p ${pct(Number(p.p))} · EV ${aed(Number(p.ev))}`).addTo(m);
      });
      m.on("mouseleave", "points", () => { m.getCanvas().style.cursor = ""; popup.remove(); });
      m.on("click", "points", (e) => openOpp(String(e.features?.[0]?.properties?.id)));
      m.on("mouseenter", "clusters", (e) => {
        m.getCanvas().style.cursor = "pointer";
        const p = e.features?.[0]?.properties as Record<string, number>;
        popup.setLngLat((e.features![0].geometry as GeoJSON.Point).coordinates as [number, number])
          .setHTML(`<b>${p.point_count} opportunities</b><br>${aed(p.value)} face · ${aed(p.ev)} expected`).addTo(m);
      });
      m.on("mouseleave", "clusters", () => { m.getCanvas().style.cursor = ""; popup.remove(); });
    });
    return () => { m.remove(); map.current = null; };
  }, [data, openOpp]);

  useEffect(() => {
    const m = map.current; if (!m) return;
    const apply = () => {
      const vis = (id: string, on: boolean) => m.getLayer(id) && m.setLayoutProperty(id, "visibility", on ? "visible" : "none");
      vis("risk-heat", layers.risk); vis("competitors", layers.competitors); vis("closed", layers.closed);
      vis("clusters", layers.clusters);
      const src = m.getSource("opps") as GeoJSONSource | undefined;
      if (src && data) src.setClusterOptions?.({ cluster: layers.clusters, clusterRadius: 38, clusterMaxZoom: 6 });
    };
    if (m.isStyleLoaded()) apply(); else m.once("load", apply);
  }, [layers, data]);

  if (!data) return <Loading error={error} />;
  const toggle = (k: keyof typeof layers) => setLayers((l) => ({ ...l, [k]: !l[k] }));
  return (
    <>
      <div className="filters">
        <div className="seg" role="group" aria-label="Map layers">
          <button aria-pressed={layers.clusters} onClick={() => toggle("clusters")}>Spatial clustering</button>
          <button aria-pressed={layers.risk} onClick={() => toggle("risk")}>AI risk overlay (value at risk)</button>
          <button aria-pressed={layers.competitors} onClick={() => toggle("competitors")}>Competitor density</button>
          <button aria-pressed={layers.closed} onClick={() => toggle("closed")}>Closed / on hold</button>
        </div>
      </div>
      <section className="grid g-wide">
        <div className="map">
          <div ref={box} style={{ position: "absolute", inset: 0 }} />
          <div className="map-legend">
            <b>Win probability</b>
            <span><span className="dot" style={{ background: "var(--pos)", borderRadius: 9 }} /> ≥ 60%  <span className="dot" style={{ background: "var(--neu)", borderRadius: 9 }} /> 30–60%  <span className="dot" style={{ background: "var(--neg)", borderRadius: 9 }} /> &lt; 30%</span>
            <span className="hint">Size = value · heat = value × (1 − p)</span>
          </div>
        </div>
        <div className="panel">
          <div className="ph"><h2>Regional exposure</h2><span className="hint">Active pipeline by country</span></div>
          <div className="tw"><table><thead><tr><th>Country</th><th className="n">Deals</th><th className="n">Value</th><th className="n">Risk</th><th className="n">Comp.</th></tr></thead>
            <tbody>{data.countries.map((c) => (
              <tr key={c.country} className="click" onClick={() => { setSel(c); map.current?.flyTo({ center: [c.lon, c.lat], zoom: 4.5 }); }}>
                <td>{c.country}<div className="idc">{c.region}</div></td><td className="n mono">{c.count}</td><td className="n mono">{aed(c.value, false)}</td>
                <td className={"n mono " + (c.risk > 0.6 ? "bad" : c.risk > 0.35 ? "pend" : "ok")}>{pct(c.risk)}</td><td className="n mono">{c.competitor_density}</td>
              </tr>))}</tbody></table></div>
          {sel && <p className="hint">{sel.country}: {aed(sel.ev)} expected of {aed(sel.value)}; {pct(sel.risk)} of value at risk; {sel.competitor_density} competitors per deal on average.</p>}
          <p className="hint">The base map ships with the app and needs no internet access. For street-level or 3D deployment views, point <span className="mono">VITE_MAP_STYLE</span> at a self-hosted tile server.</p>
        </div>
      </section>
    </>
  );
}
