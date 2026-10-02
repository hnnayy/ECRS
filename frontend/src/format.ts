// Format tampilan untuk petugas (bukan format mesin).
const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

/** "2022-01-01" -> "1 Jan 2022" */
export const tanggal = (iso: string | null | undefined) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? "");
  return m ? `${Number(m[3])} ${BULAN[Number(m[2]) - 1]} ${m[1]}` : iso || "–";
};

/** "2025-06" -> "Jun 2025" */
export const bulan = (periode: string) => {
  const m = /^(\d{4})-(\d{2})/.exec(periode);
  return m ? `${BULAN[Number(m[2]) - 1]} ${m[1]}` : periode;
};

/** Skor 0–1 dari engine ditampilkan sebagai 0–100 agar mudah dibaca. */
export const skor100 = (v: number | null | undefined) => (v === null || v === undefined ? "–" : String(Math.round(v * 100)));
