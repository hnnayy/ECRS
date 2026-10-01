import { useEffect, useState } from "react";
import { api } from "../api";
import type { CaseSummary, CompanyDetail, Decision, Series } from "../types";
import { HeadcountChart, PeerWageChart, RemittanceChart } from "./Charts";
import ScoreBar from "./ScoreBar";

const STATUS_LABEL: Record<string, string> = {
  FLAGGED: "Terindikasi", NORMAL: "Wajar", ONE_OFF_GAP: "Sekali kurang setor (wajar)", EXPLAINED_BY_RESIGN: "Dijelaskan catatan resign",
  INSUFFICIENT_DATA: "Data belum cukup", NOT_CANDIDATE: "Bukan kandidat",
};

const MODULE_NAME: Record<string, string> = { A: "Jumlah peserta", B: "Upah dilaporkan", C: "Setoran iuran" };

export const DECISION_LABEL: Record<Decision["decision"], string> = {
  investigasi: "Investigasi lanjut", terbukti: "Terbukti", tidak_terbukti: "Tidak terbukti", tutup: "Tutup",
};

export default function DetailDrawer({ id, onClose }: { id: string; onClose: () => void }) {
  const [c, setC] = useState<CompanyDetail | null>(null);
  const [series, setSeries] = useState<Series | null>(null);
  const [history, setHistory] = useState<Decision[]>([]);
  const [brief, setBrief] = useState<CaseSummary | null>(null);
  const [copied, setCopied] = useState(false);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const decide = async (decision: Decision["decision"]) => {
    setSaving(true); setErr(null);
    try {
      await api.addDecision({ company_id: id, decision, note });
      setNote(""); setHistory(await api.decisions(id));
    } catch (e) { setErr((e as Error).message); } finally { setSaving(false); }
  };

  useEffect(() => {
    setC(null); setSeries(null);
    api.company(id).then(setC);
    api.series(id).then(setSeries);
    api.decisions(id).then(setHistory);
    setBrief(null); setCopied(false);
    let alive = true;  // templat tampil seketika; versi AI (jika dikonfigurasi) menggantikannya
    api.caseSummary(id, false).then((s) => {
      if (!alive) return;
      setBrief(s);
      if (s.llm_configured) api.caseSummary(id, true).then((x) => alive && setBrief(x)).catch(() => undefined);
    }).catch(() => undefined);
    setNote(""); setErr(null);
    return () => { alive = false; };
  }, [id]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={`Detail ${id}`}>
        <button className="close" onClick={onClose} aria-label="Tutup">×</button>
        {!c ? <p>Memuat…</p> : (
          <>
            <h2 className="mono">{c.id}</h2>
            <p className="muted">{c.sektor} · {c.wilayah} · skala {c.skala}</p>
            <p><b>{c.band}</b> · rank {c.rank ?? "–"} · skor {c.composite_score?.toFixed(2) ?? "–"} · coverage {c.coverage}/3</p>
            <p>{c.explanation.summary}</p>
            <p className="recommendation">{c.recommendation}</p>
            {brief && (
              <div className="driver">
                <div className="driver-head">
                  <b>Ringkasan kasus</b>
                  <span className="muted small">{brief.source === "llm" ? `disusun AI (${brief.model})` : "ringkasan otomatis (templat)"}</span>
                </div>
                <p>{brief.text}</p>
                <div className="actions">
                  <button onClick={() => navigator.clipboard?.writeText(brief.text).then(() => setCopied(true)).catch(() => undefined)}>{copied ? "Tersalin ✓" : "Salin"}</button>
                </div>
                {brief.llm_configured && brief.source === "templat" && brief.fallback_reason && (
                  <p className="muted small">Versi AI tidak dipakai: {brief.fallback_reason}.</p>
                )}
              </div>
            )}
            {c.explanation.drivers.map((d) => (
              <div className="driver" key={d.module}>
                <div className="driver-head">
                  <b>{MODULE_NAME[d.module] ?? d.label}</b>
                  <span className={d.flagged ? "flag" : "muted"}>{STATUS_LABEL[d.status] ?? d.status}</span>
                </div>
                <ScoreBar value={d.score} />
                <p>{d.text}</p>
                {series && d.module === "A" && <><HeadcountChart data={series.A} /><p className="muted small">Garis: peserta aktif · batang oranye: resign tercatat</p></>}
                {series && d.module === "B" && <><PeerWageChart data={series.B} /><p className="muted small">Garis biru: upah rata-rata (jt) · area abu: Q1–Q3 peer-group · putus-putus: median</p></>}
                {series && d.module === "C" && <><RemittanceChart data={series.C} /><p className="muted small">Biru: setoran seharusnya · oranye/merah: aktual (jt) · merah = kurang &gt;5%</p></>}
              </div>
            ))}
            {c.extra_signals?.remittance_early_warning?.flagged && (
              <div className="driver">
                <div className="driver-head"><b>Peringatan dini setoran</b><span className="flag">perlu dipantau</span></div>
                <p className="small">{c.extra_signals.remittance_early_warning.text}</p>
                <p className="muted small">Muncul satu bulan lebih awal dari penilaian Setoran iuran. Tidak mengubah tingkat risiko di atas.</p>
              </div>
            )}
            {c.extra_signals?.isolation_forest?.flagged && (
              <div className="driver">
                <div className="driver-head">
                  <b>Pola tidak biasa</b>
                  <span className="mono">lebih janggal dari {Math.round(c.extra_signals.isolation_forest.score * 100)}% badan usaha lain</span>
                </div>
                {c.extra_signals.isolation_forest.reasons.map((r) => <p key={r.feature} className="small">{r.text}</p>)}
                <p className="muted small">Sinyal tambahan dari analisis pola (tanpa label). Tidak mengubah tingkat risiko di atas.</p>
              </div>
            )}
            <div className="driver">
              <b>Keputusan pemeriksa</b>
              <textarea placeholder="Alasan / catatan (min. 3 karakter)" value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
              <div className="actions wrap">
                {(Object.keys(DECISION_LABEL) as Decision["decision"][]).map((k) => (
                  <button key={k} className={k === "terbukti" ? "danger" : ""} disabled={saving || note.trim().length < 3} onClick={() => decide(k)}>{DECISION_LABEL[k]}</button>
                ))}
              </div>
              <p className="muted small">"Terbukti" dan "Tidak terbukti" adalah hasil akhir; keduanya menjadi label untuk melatih model.</p>
              {err && <p className="flag">{err}</p>}
              {history.map((h) => (
                <p key={h.id} className="small"><b>{DECISION_LABEL[h.decision]}</b>{h.source === "simulasi" && " (simulasi)"} · {new Date(h.created_at).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" })} — {h.note}</p>
              ))}
            </div>
            <p className="muted small">Skor adalah alat prioritas pemeriksaan, bukan vonis.</p>
          </>
        )}
      </aside>
    </>
  );
}
