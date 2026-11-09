import { useEffect, useState } from "react";
import { api } from "../api";
import { copy, EngineBadge, Loading, Modal, useApp } from "../ui";

type Draft = { draft: string; engine: string; banner?: string; cleared?: boolean; status?: string };

/** Generates an AI draft, lets the user edit it, copy it, or hand it to Outlook as a draft. */
export default function DraftModal({ title, path, body, onClose, outlookOpp }: {
  title: string; path: string; body: Record<string, unknown>; onClose: () => void; outlookOpp?: string;
}) {
  const { toast } = useApp();
  const [d, setD] = useState<Draft | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [lang, setLang] = useState<string>((body.lang as string) || "en");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setD(null); setErr(null);
    api.post<Draft>(path, { ...body, lang }).then((r) => { setD(r); setText(r.draft); }).catch((e: Error) => setErr(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, lang]);

  async function toOutlook() {
    if (!outlookOpp) return;
    setBusy(true);
    const lines = text.split("\n");
    const subj = (lines.find((l) => /^subject:/i.test(l)) || `Re: ${title}`).replace(/^subject:\s*/i, "");
    try {
      const r = await api.post<{ web_url?: string }>(`/api/opportunities/${outlookOpp}/outlook/draft`,
        { subject: subj, body: lines.filter((l) => !/^subject:/i.test(l)).join("\n").trim(), to: [] });
      toast("Saved to Outlook Drafts");
      if (r.web_url) window.open(r.web_url, "_blank", "noopener");
    } catch (e) { toast((e as Error).message); }
    setBusy(false);
  }

  return (
    <Modal title={title} onClose={onClose}>
      <div className="filters">
        <div className="seg" role="group" aria-label="Language">
          <button aria-pressed={lang === "en"} onClick={() => setLang("en")}>English</button>
          <button aria-pressed={lang === "ar"} onClick={() => setLang("ar")}>العربية</button>
        </div>
        {d && <EngineBadge engine={d.engine} />}
        {d?.status && <span className="hint">{d.status}: review before sending</span>}
      </div>
      {d?.banner && <div className={"banner " + (d.cleared ? "pos" : "neg")}>{d.banner}</div>}
      {!d ? <Loading error={err} label="Drafting" /> : (
        <textarea className="in" rows={20} value={text} onChange={(e) => setText(e.target.value)} dir={lang === "ar" ? "rtl" : "ltr"} />
      )}
      <div className="filters">
        <button className="btn primary" disabled={!d} onClick={() => copy(text, toast)}>Copy</button>
        {outlookOpp && <button className="btn" disabled={!d || busy} onClick={toOutlook}>Save to Outlook Drafts</button>}
        <button className="btn ghost" onClick={() => { setLang((l) => l); setD(null); api.post<Draft>(path, { ...body, lang }).then((r) => { setD(r); setText(r.draft); }).catch((e: Error) => setErr(e.message)); }}>Regenerate</button>
      </div>
    </Modal>
  );
}
