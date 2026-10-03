import { useState } from "react";

export const PAGE_SIZES = [10, 25, 50, 0] as const;  // 0 = semua
const label = (n: number) => (n === 0 ? "Semua" : String(n));

/** Ukuran halaman per tabel, diingat di browser (localStorage) agar pilihan petugas tidak hilang saat pindah menu. */
export function usePageSize(key: string, initial = 25): [number, (n: number) => void] {
  const [size, setSizeState] = useState<number>(() => {
    try {
      const raw = localStorage.getItem(`ecrs.pagesize.${key}`);
      const v = raw === null ? NaN : Number(raw);
      return (PAGE_SIZES as readonly number[]).includes(v) ? v : initial;
    } catch { return initial; }
  });
  const setSize = (n: number) => {
    setSizeState(n);
    try { localStorage.setItem(`ecrs.pagesize.${key}`, String(n)); } catch { /* penyimpanan tidak tersedia */ }
  };
  return [size, setSize];
}

/** Ambil satu halaman dari daftar yang sudah dimuat penuh (tabel sisi klien). */
export const pageSlice = <T,>(rows: T[], size: number, offset: number) => (size === 0 ? rows : rows.slice(offset, offset + size));

export default function Pager({ total, size, offset, onSize, onOffset, unit = "data" }: {
  total: number; size: number; offset: number; onSize: (n: number) => void; onOffset: (n: number) => void; unit?: string;
}) {
  const all = size === 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = all ? total : Math.min(offset + size, total);
  return (
    <div className="pager">
      <span>{from}–{to} dari {total} {unit}</span>
      <label className="page-size">Tampilkan
        <select value={size} onChange={(e) => { onSize(Number(e.target.value)); onOffset(0); }} aria-label="Jumlah baris per halaman">
          {PAGE_SIZES.map((n) => <option key={n} value={n}>{label(n)}</option>)}
        </select>
      </label>
      {!all && <>
        <button disabled={offset === 0} onClick={() => onOffset(Math.max(0, offset - size))}>← Sebelumnya</button>
        <button disabled={offset + size >= total} onClick={() => onOffset(offset + size)}>Berikutnya →</button>
      </>}
    </div>
  );
}
