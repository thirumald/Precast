import { api } from "../api";
import { useData } from "../ui";

export type F = Partial<Record<"domain" | "region" | "country" | "segment" | "sponsor", string>>;
const LABELS: [keyof F, string][] = [["domain", "Domain"], ["region", "Region"], ["country", "Country"], ["segment", "Segment"], ["sponsor", "Executive sponsor"]];

export const qs = (f: F) => {
  const p = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as [string, string][]).toString();
  return p ? "?" + p : "";
};

/** Global management filters shared by the executive dashboard and every report. */
export default function Filters({ value, onChange, keys = ["domain", "region", "country", "segment", "sponsor"] }: {
  value: F; onChange: (f: F) => void; keys?: (keyof F)[];
}) {
  const { data } = useData(() => api.get<Record<string, string[]>>("/api/filters"));
  const any = Object.values(value).some(Boolean);
  return (
    <div className="filters no-print">
      {LABELS.filter(([k]) => keys.includes(k)).map(([k, label]) => (
        <label key={k} className="f">{label}
          <select className="in" value={value[k] || ""} onChange={(e) => onChange({ ...value, [k]: e.target.value || undefined })}>
            <option value="">All</option>{(data?.[k] || []).map((o) => <option key={o}>{o}</option>)}
          </select>
        </label>
      ))}
      {any && <button className="btn ghost sm" onClick={() => onChange({})}>Clear filters</button>}
    </div>
  );
}
