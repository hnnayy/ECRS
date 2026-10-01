import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import Modal from "../components/Modal";
import type { Employer, EmployerInput, Reference } from "../types";

const EMPTY: EmployerInput = { nama: "", sektor: "", wilayah: "", skala: "Kecil", status: "Aktif", tanggal_registrasi: new Date().toISOString().slice(0, 10) };

export default function MasterEmployers({ onSelect }: { onSelect: (id: string) => void }) {
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{ total: number; items: Employer[] } | null>(null);
  const [ref, setRef] = useState<Reference | null>(null);
  const [editing, setEditing] = useState<{ id: string | null; form: EmployerInput } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => api.employers(q, offset).then(setData), [q, offset]);
  useEffect(() => { setOffset(0); }, [q]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.reference().then(setRef); }, []);

  const openNew = () => { setErr(null); setEditing({ id: null, form: { ...EMPTY, sektor: ref?.sektor[0]?.nama ?? "", wilayah: ref?.wilayah[0]?.nama ?? "" } }); };
  const openEdit = (e: Employer) => {
    setErr(null);
    setEditing({ id: e.employer_id, form: { nama: e.nama, sektor: e.sektor, wilayah: e.wilayah, skala: e.skala, status: e.status, tanggal_registrasi: e.tanggal_registrasi } });
  };
  const save = async () => {
    if (!editing) return;
    try {
      await (editing.id ? api.updateEmployer(editing.id, editing.form) : api.createEmployer(editing.form));
      setEditing(null); await load();
    } catch (e) { setErr((e as Error).message); }
  };
  const remove = async (e: Employer) => {
    if (!window.confirm(`Hapus ${e.employer_id}?`)) return;
    try { await api.deleteEmployer(e.employer_id); await load(); } catch (x) { window.alert((x as Error).message); }
  };
  const set = (k: keyof EmployerInput) => (ev: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setEditing((cur) => cur && { ...cur, form: { ...cur.form, [k]: ev.target.value } });

  return (
    <>
      <div className="page-head"><h2>Master Data Badan Usaha</h2><p>Daftar badan usaha yang dipantau. Employer yang sudah diskor engine tidak bisa dihapus, hanya di-nonaktifkan.</p></div>
      <section className="panel">
        <div className="toolbar">
          <input placeholder="Cari ID atau nama…" value={q} onChange={(e) => setQ(e.target.value)} />
          <span className="muted">{data?.total ?? 0} badan usaha</span>
          <button className="primary" style={{ marginLeft: "auto" }} onClick={openNew} disabled={!ref}>+ Tambah badan usaha</button>
        </div>
        <table>
          <thead><tr><th>ID</th><th>Nama</th><th>Sektor</th><th>Wilayah</th><th>Skala</th><th>Status</th><th>Terdaftar</th><th /></tr></thead>
          <tbody>
            {data?.items.map((e) => (
              <tr key={e.employer_id}>
                <td className="mono">{e.scored ? <a onClick={() => onSelect(e.employer_id)}>{e.employer_id}</a> : e.employer_id}</td>
                <td>{e.nama || <span className="muted">–</span>}</td><td>{e.sektor}</td><td>{e.wilayah}</td><td>{e.skala}</td>
                <td><span className={`pill ${e.status === "Aktif" ? "bg-good" : "bg-muted"}`}>{e.status}</span></td>
                <td>{e.tanggal_registrasi}</td>
                <td className="row-actions">
                  <button onClick={() => openEdit(e)}>Ubah</button>
                  <button className="danger" onClick={() => remove(e)} disabled={e.scored} title={e.scored ? "Sudah diskor engine — nonaktifkan saja" : ""}>Hapus</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && (
          <div className="pager">
            <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>← Sebelumnya</button>
            <button disabled={offset + 25 >= data.total} onClick={() => setOffset(offset + 25)}>Berikutnya →</button>
          </div>
        )}
      </section>

      {editing && ref && (
        <Modal title={editing.id ? `Ubah ${editing.id}` : "Tambah badan usaha"} onClose={() => setEditing(null)}>
          <div className="form-grid">
            <label>Nama<input value={editing.form.nama} onChange={set("nama")} placeholder="PT …" /></label>
            <label>Sektor<select value={editing.form.sektor} onChange={set("sektor")}>{ref.sektor.map((s) => <option key={s.nama}>{s.nama}</option>)}</select></label>
            <label>Wilayah<select value={editing.form.wilayah} onChange={set("wilayah")}>{ref.wilayah.map((w) => <option key={w.nama}>{w.nama}</option>)}</select></label>
            <label>Skala<select value={editing.form.skala} onChange={set("skala")}>{ref.skala.map((s) => <option key={s}>{s}</option>)}</select></label>
            <label>Status<select value={editing.form.status} onChange={set("status")}><option>Aktif</option><option>Non-aktif</option></select></label>
            <label>Tanggal registrasi<input type="date" value={editing.form.tanggal_registrasi} onChange={set("tanggal_registrasi")} /></label>
          </div>
          {err && <p className="flag">{err}</p>}
          <div className="actions"><button className="primary" onClick={save}>Simpan</button><button onClick={() => setEditing(null)}>Batal</button></div>
        </Modal>
      )}
    </>
  );
}
