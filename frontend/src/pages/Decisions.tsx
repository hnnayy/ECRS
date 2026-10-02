import { useEffect, useState } from "react";
import { api } from "../api";
import type { Decision } from "../types";
import { DECISION_LABEL } from "../components/DetailDrawer";

export default function Decisions({ onSelect }: { onSelect: (id: string) => void }) {
  const [rows, setRows] = useState<Decision[] | null>(null);
  useEffect(() => { api.decisions().then(setRows); }, []);
  return (
    <>
      <div className="page-head"><h2>Riwayat Keputusan</h2><p>Catatan semua keputusan pemeriksaan yang pernah dibuat. Klik satu baris untuk membuka detail badan usaha.</p></div>
      <section className="panel">
        <table>
          <thead><tr><th>Tanggal</th><th>Badan usaha</th><th>Keputusan</th><th>Petugas</th><th>Catatan</th></tr></thead>
          <tbody>
            {rows?.map((d) => (
              <tr key={d.id} onClick={() => onSelect(d.company_id)}>
                <td className="mono">{new Date(d.created_at).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" })}</td>
                <td className="mono">{d.company_id}</td>
                <td><span className={`pill ${d.decision === "terbukti" ? "bg-critical" : d.decision === "investigasi" ? "bg-accent" : "bg-muted"}`}>{DECISION_LABEL[d.decision]}</span>{d.source === "simulasi" && <span className="muted"> · simulasi</span>}</td>
                <td>{d.officer}</td>
                <td>{d.note}</td>
              </tr>
            ))}
            {rows?.length === 0 && <tr><td colSpan={5} className="muted">Belum ada keputusan. Buka detail badan usaha di Dashboard untuk mencatat keputusan.</td></tr>}
          </tbody>
        </table>
      </section>
    </>
  );
}
