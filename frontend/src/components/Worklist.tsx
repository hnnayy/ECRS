import { useEffect, useState } from "react";
import { api } from "../api";
import type { CompanyList, Filters } from "../types";
import ScoreBar from "./ScoreBar";

const PAGE = 25;
const BAND_ORDER = ["Tinggi", "Sedang", "Rendah", "Belum bisa dinilai"];
const TONE: Record<string, string> = { Tinggi: "critical", Sedang: "serious", Rendah: "good" };

export default function Worklist({ onSelect }: { onSelect: (id: string) => void }) {
  const [filters, setFilters] = useState<Filters | null>(null);
  const [sektor, setSektor] = useState("");
  const [wilayah, setWilayah] = useState("");
  const [band, setBand] = useState("");
  const [flagged, setFlagged] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<CompanyList | null>(null);

  useEffect(() => { api.filters().then(setFilters); }, []);
  useEffect(() => { setOffset(0); }, [sektor, wilayah, band, flagged, q]);
  useEffect(() => {
    api.companies({ sektor, wilayah, band, flagged, q, limit: PAGE, offset }).then(setData);
  }, [sektor, wilayah, band, flagged, q, offset]);

  const select = (label: string, value: string, set: (v: string) => void, options: string[] = []) => (
    <select value={value} onChange={(e) => set(e.target.value)} aria-label={label}>
      <option value="">{label}</option>
      {options.map((o) => <option key={o}>{o}</option>)}
    </select>
  );

  return (
    <section className="panel">
      <div className="toolbar">
        <h2>Worklist prioritas</h2>
        <input placeholder="Cari ID (mis. EMP-0492)" value={q} onChange={(e) => setQ(e.target.value)} />
        {select("Semua sektor", sektor, setSektor, filters?.sektor)}
        {select("Semua wilayah", wilayah, setWilayah, filters?.wilayah)}
        {select("Semua tingkat risiko", band, setBand, BAND_ORDER.filter((b) => filters?.band.includes(b)))}
        <select value={flagged} onChange={(e) => setFlagged(e.target.value)} aria-label="Jenis indikasi">
          <option value="">Semua jenis indikasi</option>
          <option value="A">Jumlah peserta tidak wajar</option>
          <option value="B">Upah dilaporkan rendah</option>
          <option value="C">Setoran iuran kurang</option>
        </select>
      </div>
      <table>
        <thead>
          <tr>
            <th title="Urutan prioritas pemeriksaan; 1 = paling perlu dicek">Peringkat</th><th>Badan usaha</th><th>Sektor · Wilayah</th>
            <th title="Tinggi = paling perlu dicek. Belum bisa dinilai = data belum cukup">Tingkat risiko</th><th title="Skor gabungan 0–1; makin tinggi makin perlu dicek">Skor risiko</th>
            <th title="Jumlah peserta turun tajam tanpa catatan resign (indikasi peserta tidak didaftarkan)">Jumlah peserta</th>
            <th title="Upah yang dilaporkan jauh di bawah perusahaan sejenis (indikasi upah dilaporkan lebih rendah)">Upah dilaporkan</th>
            <th title="Iuran yang disetor kurang dari yang seharusnya, berulang beberapa bulan">Setoran iuran</th>
          </tr>
        </thead>
        <tbody>
          {data?.items.map((c) => (
            <tr key={c.id} onClick={() => onSelect(c.id)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && onSelect(c.id)}>
              <td>{c.rank ?? "–"}</td>
              <td className="mono">{c.id}</td>
              <td>{c.sektor}<div className="muted">{c.wilayah} · {c.skala}</div></td>
              <td><span className={`pill bg-${TONE[c.band] ?? "muted"}`}>{c.band}</span></td>
              <td className="mono">{c.composite_score?.toFixed(2) ?? "–"}</td>
              <td><ScoreBar value={c.scores.A} /></td>
              <td><ScoreBar value={c.scores.B} /></td>
              <td><ScoreBar value={c.scores.C} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small legend">
        <b>Jumlah peserta · Upah dilaporkan · Setoran iuran</b> = tiga jenis indikasi yang diperiksa. Bar makin panjang dan merah = indikasi makin kuat
        (tidak ada bar isi = tidak ada indikasi; "n/a" = data belum cukup). Skor adalah alat prioritas pemeriksaan, bukan vonis.
      </p>
      {data && (
        <div className="pager">
          <span>{data.total} employer</span>
          <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>← Sebelumnya</button>
          <button disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>Berikutnya →</button>
        </div>
      )}
    </section>
  );
}
