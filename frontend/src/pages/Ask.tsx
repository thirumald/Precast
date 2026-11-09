import { useEffect, useRef, useState } from "react";
import { api, type AskResult } from "../api";
import { aed, pct } from "../format";
import { Chip, EngineBadge, useApp } from "../ui";

type Msg = { role: "user" | "assistant"; content: string; res?: AskResult };
const SUGGEST = [
  "What is the revenue impact of blocked security deals in Saudi Arabia?",
  "List all defense opportunities requiring CEO intervention",
  "Which deals are at risk this quarter?",
  "How many opportunities are in negotiation?",
  "ما هي الفرص الدفاعية التي تتطلب تدخل الرئيس التنفيذي؟",
  "ما قيمة خط الأنابيب في الإمارات؟",
];

export default function Ask() {
  const { openOpp } = useApp();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs]);

  async function send(text: string) {
    const t = text.trim();
    if (!t || busy) return;
    const history = msgs.map((m) => ({ role: m.role, content: m.content }));
    setMsgs((m) => [...m, { role: "user", content: t }]);
    setQ(""); setBusy(true);
    try {
      const r = await api.post<AskResult>("/api/ask", { question: t, history });
      setMsgs((m) => [...m, { role: "assistant", content: r.answer, res: r }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", content: "Couldn't answer: " + (e as Error).message }]);
    }
    setBusy(false);
  }
  return (
    <section className="panel" style={{ maxWidth: 980 }}>
      <div className="ph"><h2>Ask Precast</h2><span className="hint">Arabic or English. Figures are computed from the register, never invented by the model.</span></div>
      {!msgs.length && <div className="suggest">{SUGGEST.map((s) => <button key={s} onClick={() => send(s)} dir="auto">{s}</button>)}</div>}
      <div className="chat">
        {msgs.map((m, i) => (
          <div key={i} className={"msg " + (m.role === "user" ? "u" : "a")} dir="auto">
            {m.content}
            {m.res && (
              <div className="meta">
                <div className="chips" style={{ margin: "6px 0" }}>
                  <EngineBadge engine={m.res.engine} />
                  <Chip>{m.res.summary.matched} matched</Chip>
                  <Chip>{aed(m.res.summary.total_value_aed)} face</Chip>
                  <Chip tone="acc">{aed(m.res.summary.expected_value_aed)} expected</Chip>
                  {Object.entries(m.res.filters).filter(([k]) => k !== "metric").map(([k, v]) => <Chip key={k}>{k}: {String(v)}</Chip>)}
                </div>
                {m.res.rows.length > 0 && (
                  <div className="tw"><table><tbody>{m.res.rows.slice(0, 8).map((o) => (
                    <tr key={o.id} className="click" onClick={() => openOpp(o.id)}><td className="idc">{o.id}</td><td>{o.name}</td><td>{o.country}</td><td>{o.status}</td><td className="mono">{pct(o.score.p)}</td><td className="n mono">{aed(o.value, false)}</td></tr>
                  ))}</tbody></table></div>
                )}
                {m.res.citations.length > 0 && <div style={{ marginTop: 6 }}>Sources: {m.res.citations.map((c) => <span key={c.id} className="chip" title={c.text} style={{ marginInlineEnd: 4 }}>{c.kind} {c.id}{c.date ? ` · ${c.date}` : ""}</span>)}</div>}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="msg a"><span className="spin" /> Thinking…</div>}
        <div ref={end} />
      </div>
      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(q); }}>
        <input className="in" dir="auto" placeholder="Ask about the pipeline… / اسأل عن خط الأنابيب…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Question" />
        <button className="btn primary" disabled={busy || !q.trim()}>Ask</button>
        {msgs.length > 0 && <button type="button" className="btn ghost" onClick={() => setMsgs([])}>Clear</button>}
      </form>
    </section>
  );
}
