import { useEffect, useState } from "react";
import { api } from "../api";
import type { CompanyList, Filters } from "../types";
import ScoreBar from "./ScoreBar";
import { skor100 } from "../format";
import Pager, { usePageSize } from "./Pager";

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
  const [size, setSize] = usePageSize("worklist", 25);
  const [data, setData] = useState<CompanyList | null>(null);

  useEffect(() => { api.filters().then(setFilters); }, []);
  useEffect(() => { setOffset(0); }, [sektor, wilayah, band, flagged, q]);
  useEffect(() => {
    api.companies({ sektor, wilayah, band, flagged, q, limit: size === 0 ? 5000 : size, offset }).then(setData);
  }, [sektor, wilayah, band, flagged, q, offset, size]);

  const select = (label: string, value: string, set: (v: string) => void, options: string[] = []) => (
    <select value={value} onChange={(e) => set(e.target.value)} aria-label={label}>
      <option value="">{label}</option>
      {options.map((o) => <option key={o}>{o}</option>)}
    </select>
  );

  return (
    <section className="panel">
      <div className="toolbar">
        <h2>Daftar prioritas pemeriksaan</h2>
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
            <th title="Tinggi = periksa lebih dulu. Rendah = belum ada indikasi (bukan jaminan patuh). Belum bisa dinilai = data periode belum cukup, lengkapi lewat menu Input Data">Tingkat risiko</th><th title="Skor 0–100; makin tinggi makin perlu diperiksa">Skor risiko</th>
            <th title="Jumlah peserta turun tajam tanpa catatan peserta keluar (kemungkinan peserta tidak didaftarkan)">Jumlah peserta</th>
            <th title="Upah yang dilaporkan jauh di bawah badan usaha sejenis (sektor, wilayah, dan skala sama)">Upah dilaporkan</th>
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
              <td className="mono">{skor100(c.composite_score)}</td>
              <td><ScoreBar value={c.scores.A} /></td>
              <td><ScoreBar value={c.scores.B} /></td>
              <td><ScoreBar value={c.scores.C} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small legend">
        <b>Cara membaca:</b> tiga kolom terakhir adalah jenis pemeriksaan. Bar makin panjang dan merah = dugaan makin kuat; bar kosong = tidak ada dugaan;
        "n/a" = data belum cukup. Hasil ini hanya urutan prioritas pemeriksaan, bukan vonis pelanggaran.
      </p>
      {data && <Pager total={data.total} size={size} offset={offset} onSize={setSize} onOffset={setOffset} unit="badan usaha" />}
    </section>
  );
}
