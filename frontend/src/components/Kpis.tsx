import type { Summary } from "../types";

const BANDS: [string, string][] = [
  ["Tinggi", "critical"], ["Sedang", "serious"], ["Rendah", "good"], ["Belum bisa dinilai", "muted"],
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
      <div className="card">
        <span className="label">Terindikasi per jenis</span>
        <b className="small">
          Peserta {summary.by_module_flagged.A ?? 0} · Upah {summary.by_module_flagged.B ?? 0} · Setoran {summary.by_module_flagged.C ?? 0}
        </b>
      </div>
    </section>
  );
}
