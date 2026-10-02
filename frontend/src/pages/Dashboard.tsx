import { useEffect, useState } from "react";
import { api } from "../api";
import type { Summary } from "../types";
import Kpis from "../components/Kpis";
import Worklist from "../components/Worklist";

export default function Dashboard({ onSelect }: { onSelect: (id: string) => void }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.summary().then(setSummary).catch((e: Error) => setError(e.message)); }, []);
  return (
    <>
      <div className="page-head"><h2>Dashboard &amp; Radar Risiko</h2><p>Daftar badan usaha yang sebaiknya diperiksa lebih dulu, diurutkan dari yang paling perlu dicek.</p></div>
      {error && <div className="alert">Data tidak dapat dimuat. Coba muat ulang halaman; jika masih gagal, hubungi tim IT. ({error})</div>}
      {summary && <Kpis summary={summary} />}
      <Worklist onSelect={onSelect} />
    </>
  );
}
