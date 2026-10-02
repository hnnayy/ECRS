import type { Summary } from "../types";

const BANDS: [string, string, string, string][] = [
  ["Tinggi", "critical", "periksa lebih dulu", "Indikasi kuat; sebaiknya diperiksa lebih dulu."],
  ["Sedang", "serious", "perlu dipantau", "Ada indikasi, tetapi belum sekuat tingkat Tinggi."],
  ["Rendah", "good", "belum ada indikasi", "Belum ada indikasi pada data yang tersedia. Ini bukan jaminan badan usaha patuh."],
  ["Belum bisa dinilai", "muted", "data belum cukup", "Data periode belum cukup (minimal 3 periode). Lengkapi lewat menu Input Data."],
];

const FLAGS: [string, string, string][] = [
  ["A", "Jumlah peserta", "turun tanpa alasan jelas"],
  ["B", "Upah dilaporkan", "di bawah yang seharusnya"],
  ["C", "Setoran iuran", "kurang dari kewajiban"],
];

export default function Kpis({ summary }: { summary: Summary }) {
  return (
    <section className="kpis">
      <div className="card"><span className="label">Total badan usaha</span><b>{summary.total.toLocaleString("id-ID")}</b><span className="hint">yang dipantau sistem</span></div>
      {BANDS.map(([band, tone, caption, tip]) => (
        <div className="card" key={band} title={tip}>
          <span className="label">{band}</span>
          <b className={`tone-${tone}`}>{summary.by_band[band] ?? 0}</b>
          <span className="hint">{caption}</span>
        </div>
      ))}
      <div className="card wide" title="Jumlah badan usaha yang terindikasi pada tiap jenis pemeriksaan.">
        <span className="label">Terindikasi per jenis</span>
        <ul className="flag-list">
          {FLAGS.map(([key, name, hint]) => (
            <li key={key}>
              <b>{summary.by_module_flagged[key] ?? 0}</b>
              <span>{name}<small>{hint}</small></span>
            </li>
          ))}
        </ul>
        <span className="hint">Satu badan usaha bisa terindikasi di lebih dari satu jenis</span>
      </div>
    </section>
  );
}
