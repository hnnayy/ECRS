import { useState } from "react";
import { api } from "../api";
import type { CompanyDetail, PeriodInput, PeriodRow } from "../types";
import { bulan, skor100 } from "../format";

const EMPTY = { periode: "", jumlah_peserta_aktif: "", jumlah_keluar: "0", rata2_DPI: "", expected_contribution: "", actual_remittance: "" };
type Form = typeof EMPTY;
const rp = (v: number | null) => (v === null ? "–" : v.toLocaleString("id-ID", { maximumFractionDigits: 0 }));

export default function InputData({ onSelect }: { onSelect: (id: string) => void }) {
  const [id, setId] = useState("");
  const [rows, setRows] = useState<PeriodRow[] | null>(null);
  const [form, setForm] = useState<Form>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [result, setResult] = useState<CompanyDetail | null>(null);

  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });
  const valid = id.trim() !== "" && form.periode !== "" && Object.values(form).every((v) => v !== "");

  const loadEmployer = async () => {
    setMsg(null); setResult(null);
    try { setRows(await api.timeseries(id.trim())); } catch (e) { setMsg({ kind: "err", text: (e as Error).message }); }
  };
  const payload = (): PeriodInput => ({
    employer_id: id.trim(), periode: form.periode, jumlah_peserta_aktif: Number(form.jumlah_peserta_aktif), jumlah_keluar: Number(form.jumlah_keluar),
    rata2_DPI: Number(form.rata2_DPI), expected_contribution: Number(form.expected_contribution), actual_remittance: Number(form.actual_remittance),
  });

  const submit = async () => {
    setBusy(true); setMsg(null); setResult(null);
    try {
      const before = (await api.status()).scoring.last_run;
      await api.savePeriod(payload());
      setRows(await api.timeseries(id.trim()));
      setMsg({ kind: "ok", text: "Periode tersimpan. Skor dihitung ulang otomatis. hasilnya akan muncul di bawah (biasanya beberapa detik)…" });
      for (let i = 0; i < 45; i++) {  // tunggu job latar belakang (maks ±90 dtk)
        await new Promise((r) => setTimeout(r, 2000));
        const s = (await api.status()).scoring;
        if (s.last_run !== before && !s.running && !s.pending) {
          try { setResult(await api.company(id.trim())); setMsg({ kind: "ok", text: "Skor sudah diperbarui." }); }
          catch { setMsg({ kind: "ok", text: "Skor diperbarui, tetapi badan usaha ini belum bisa dinilai karena sistem butuh minimal 3 periode data." }); }
          return;
        }
      }
      setMsg({ kind: "ok", text: "Periode tersimpan. Penghitungan skor masih berjalan; cek Dashboard beberapa saat lagi." });
    } catch (e) { setMsg({ kind: "err", text: (e as Error).message }); } finally { setBusy(false); }
  };

  const num = (label: string, k: keyof Form, hint: string, help: string) => (
    <label>{label}<input type="number" min="0" value={form[k]} onChange={set(k)} placeholder={hint} /><small className="help">{help}</small></label>
  );

  return (
    <>
      <div className="page-head">
        <h2>Input Data Payroll &amp; Setoran</h2>
        <p>Catat data bulanan satu badan usaha. Setelah disimpan, sistem otomatis menghitung ulang tingkat risikonya. Semua angka ditulis tanpa titik atau koma.</p>
      </div>
      {msg && <div className={`alert ${msg.kind === "ok" ? "info" : ""}`}>{msg.text}</div>}
      <section className="panel">
        <div className="toolbar">
          <input placeholder="ID badan usaha (mis. EMP-0492)" value={id} onChange={(e) => setId(e.target.value)} onKeyDown={(e) => e.key === "Enter" && loadEmployer()} />
          <button onClick={loadEmployer} disabled={!id.trim()}>Lihat riwayat</button>
        </div>
        <div className="form-grid">
          <label>Bulan data<input type="month" value={form.periode} onChange={set("periode")} /><small className="help">Bulan yang datanya dicatat</small></label>
          {num("Peserta aktif", "jumlah_peserta_aktif", "cth. 320", "Jumlah peserta yang aktif pada bulan itu")}
          {num("Peserta keluar (resign tercatat)", "jumlah_keluar", "cth. 2", "Peserta yang keluar dan tercatat resmi pada bulan itu; isi 0 jika tidak ada")}
          {num("Rata-rata upah dilaporkan (Rp)", "rata2_DPI", "cth. 4900000", "Rata-rata upah per peserta yang dilaporkan badan usaha, per bulan")}
          {num("Iuran seharusnya (Rp)", "expected_contribution", "cth. 12200000", "Total iuran yang wajib disetor bulan itu, sesuai upah dan tarif")}
          {num("Iuran disetor (Rp)", "actual_remittance", "cth. 12200000", "Total iuran yang benar-benar dibayarkan bulan itu")}
        </div>
        <p className="muted small">Pembanding (badan usaha sejenis dengan sektor, wilayah, dan skala sama) dipilih otomatis, tidak perlu diisi. Sistem baru bisa menilai setelah ada minimal 3 bulan data.</p>
        <div className="actions">
          <button className="primary" onClick={submit} disabled={!valid || busy}>{busy ? "Menunggu skor…" : "Simpan periode"}</button>
        </div>
      </section>

      {result && (
        <section className="panel" style={{ marginTop: 16 }}>
          <h3>Hasil penilaian · <span className="mono">{result.id}</span></h3>
          <p><span className={`pill bg-${result.band === "Tinggi" ? "critical" : result.band === "Sedang" ? "serious" : result.band === "Rendah" ? "good" : "muted"}`}>{result.band}</span>
            {" "}peringkat {result.rank ?? "–"} · skor {skor100(result.composite_score)}/100 · dinilai dari {result.coverage} dari 3 jenis pemeriksaan</p>
          <p>{result.explanation.summary}</p>
          <button onClick={() => onSelect(result.id)}>Lihat detail lengkap</button>
        </section>
      )}

      {rows && (
        <section className="panel" style={{ marginTop: 16 }}>
          <h3>Riwayat data · {id.trim()}</h3>
          {rows.length === 0 ? <p className="muted">Belum ada data periode untuk badan usaha ini.</p> : (
            <table>
              <thead><tr><th>Periode</th><th>Peserta</th><th>Keluar</th><th>Upah rata-rata (Rp)</th><th>Iuran seharusnya (Rp)</th><th>Iuran disetor (Rp)</th></tr></thead>
              <tbody>{rows.map((r) => (
                <tr key={r.periode}><td>{bulan(r.periode)}</td><td>{r.jumlah_peserta_aktif}</td><td>{r.jumlah_keluar}</td>
                  <td>{rp(r.rata2_DPI)}</td><td>{rp(r.expected_contribution)}</td><td>{rp(r.actual_remittance)}</td></tr>
              ))}</tbody>
            </table>
          )}
        </section>
      )}
    </>
  );
}
