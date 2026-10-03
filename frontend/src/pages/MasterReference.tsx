import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import Modal from "../components/Modal";
import type { Reference } from "../types";
import Pager, { pageSlice, usePageSize } from "../components/Pager";

type Kind = "wilayah" | "sektor";
type Edit = { kind: Kind; old: string | null; nama: string; umr: string };

export default function MasterReference() {
  const [ref, setRef] = useState<Reference | null>(null);
  const [edit, setEdit] = useState<Edit | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [wSize, setWSize] = usePageSize("ref-wilayah", 10);
  const [wOff, setWOff] = useState(0);
  const [sSize, setSSize] = usePageSize("ref-sektor", 10);
  const [sOff, setSOff] = useState(0);
  const load = useCallback(() => api.reference().then(setRef), []);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (!edit) return;
    const body = { nama: edit.nama, ...(edit.kind === "wilayah" ? { umr_rp: edit.umr === "" ? null : Number(edit.umr) } : {}) };
    try {
      await (edit.old === null ? api.createRef(edit.kind, body) : api.updateRef(edit.kind, edit.old, body));
      setEdit(null); setErr(null); await load();
    } catch (e) { setErr((e as Error).message); }
  };
  const remove = async (kind: Kind, nama: string) => {
    if (!window.confirm(`Hapus ${kind} "${nama}"?`)) return;
    try { await api.deleteRef(kind, nama); await load(); } catch (e) { window.alert((e as Error).message); }
  };
  const open = (e: Edit) => { setErr(null); setEdit(e); };

  return (
    <>
      <div className="page-head"><h2>Master Referensi UMR &amp; Sektor</h2><p>Daftar wilayah (beserta UMR-nya) dan sektor yang dipakai sistem untuk membandingkan badan usaha. Perubahan UMR membuat skor dihitung ulang otomatis.</p></div>
      <div className="two-col">
        <section className="panel">
          <div className="toolbar"><h3>Wilayah</h3><button className="primary" style={{ marginLeft: "auto" }} onClick={() => open({ kind: "wilayah", old: null, nama: "", umr: "" })}>+ Tambah</button></div>
          <table>
            <thead><tr><th>Wilayah</th><th>Jumlah badan usaha</th><th>UMR (Rp)</th><th /></tr></thead>
            <tbody>{ref && pageSlice(ref.wilayah, wSize, wOff).map((w) => (
              <tr key={w.nama}><td>{w.nama}</td><td>{w.employer}</td><td>{w.umr_rp === null ? "–" : w.umr_rp.toLocaleString("id-ID")}</td>
                <td className="row-actions">
                  <button onClick={() => open({ kind: "wilayah", old: w.nama, nama: w.nama, umr: w.umr_rp === null ? "" : String(w.umr_rp) })}>Ubah</button>
                  <button className="danger" onClick={() => remove("wilayah", w.nama)}>Hapus</button></td></tr>
            ))}</tbody>
          </table>
          {ref && <Pager total={ref.wilayah.length} size={wSize} offset={wOff} onSize={setWSize} onOffset={setWOff} unit="wilayah" />}
        </section>
        <section className="panel">
          <div className="toolbar"><h3>Sektor</h3><button className="primary" style={{ marginLeft: "auto" }} onClick={() => open({ kind: "sektor", old: null, nama: "", umr: "" })}>+ Tambah</button></div>
          <table>
            <thead><tr><th>Sektor</th><th>Jumlah badan usaha</th><th /></tr></thead>
            <tbody>{ref && pageSlice(ref.sektor, sSize, sOff).map((s) => (
              <tr key={s.nama}><td>{s.nama}</td><td>{s.employer}</td>
                <td className="row-actions">
                  <button onClick={() => open({ kind: "sektor", old: s.nama, nama: s.nama, umr: "" })}>Ubah</button>
                  <button className="danger" onClick={() => remove("sektor", s.nama)}>Hapus</button></td></tr>
            ))}</tbody>
          </table>
          {ref && <Pager total={ref.sektor.length} size={sSize} offset={sOff} onSize={setSSize} onOffset={setSOff} unit="sektor" />}
        </section>
      </div>

      {edit && (
        <Modal title={`${edit.old === null ? "Tambah" : "Ubah"} ${edit.kind}`} onClose={() => setEdit(null)}>
          <div className="form-grid">
            <label>Nama<input value={edit.nama} onChange={(e) => setEdit({ ...edit, nama: e.target.value })} /></label>
            {edit.kind === "wilayah" && (
              <label>UMR (Rp per bulan)<input type="number" step="1" min="0" placeholder="cth. 5396761" value={edit.umr} onChange={(e) => setEdit({ ...edit, umr: e.target.value })} /></label>
            )}
          </div>
          {err && <p className="flag">{err}</p>}
          <div className="actions"><button className="primary" onClick={save} disabled={edit.nama.trim().length < 2}>Simpan</button><button onClick={() => setEdit(null)}>Batal</button></div>
        </Modal>
      )}
    </>
  );
}
