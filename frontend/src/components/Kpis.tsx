import type { Summary } from "../types";

const BANDS: [string, string][] = [
  ["Tinggi", "critical"], ["Sedang", "serious"], ["Rendah", "good"], ["Belum bisa dinilai", "muted"],
];

const FLAGS: [string, string, string][] = [
  ["A", "Jumlah peserta", "turun tanpa alasan jelas"],
  ["B", "Upah dilaporkan", "di bawah yang seharusnya"],
  ["C", "Setoran iuran", "kurang dari kewajiban"],
];

export default function Kpis({ summary }: { summary: Summary }) {
  return (
    <section className="kpis">
      <div className="card"><span className="label">Total employer</span><b>{summary.total.toLocaleString("id-ID")}</b></div>
      {BANDS.map(([band, tone]) => (
        <div className="card" key={band}>
          <span className="label">{band}</span>
          <b className={`tone-${tone}`}>{summary.by_band[band] ?? 0}</b>
        </div>
      ))}
      <div className="card wide" title="Jumlah badan usaha yang ditandai mencurigakan oleh tiap jenis pemeriksaan. Satu badan usaha dihitung sekali per jenis.">
        <span className="label">Terindikasi per jenis</span>
        <ul className="flag-list">
          {FLAGS.map(([key, name, hint]) => (
            <li key={key}>
              <b>{summary.by_module_flagged[key] ?? 0}</b>
              <span>{name}<small>{hint}</small></span>
            </li>
          ))}
        </ul>
        <span className="hint">badan usaha yang perlu diperiksa</span>
      </div>
    </section>
  );
}
