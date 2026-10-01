# Skrip demo ECRS Risk Radar (±5 menit)

Siapkan: backend (`uvicorn backend.main:app`) dan frontend (`npm run dev`) jalan, buka `http://localhost:5173`.
Semua data adalah **simulasi**: 1.020 badan usaha, 75 kasus anomali yang disisipkan (25 per jenis) + 10 kasus penurunan sah sebagai uji salah-tuduh.

## 1. Masalah (30 dtk)
Verifikasi kepatuhan pemberi kerja saat ini reaktif dan manual. Tidak ada urutan prioritas. Kami ubah jadi antrian berperingkat yang bisa dijelaskan.

## 2. Dashboard (45 dtk) — menu *Dashboard & Radar Risiko*
- Tunjuk KPI: 1.020 badan usaha, **74 Tinggi + 11 Sedang** (±8%): pemeriksa mulai dari sini, bukan acak.
- Filter **Tingkat risiko = Tinggi**, lalu **Jenis indikasi = Jumlah peserta tidak wajar**.
- Kolom *Jumlah peserta / Upah dilaporkan / Setoran iuran* = tiga jenis indikasi (bar merah = kuat).

## 3. Satu kasus sampai tuntas (90 dtk) — klik **EMP-0492**
- **Ringkasan kasus** (disusun AI dari fakta, dengan pengaman angka; ada tombol Salin).
- Kartu *Jumlah peserta*: grafik turun 506 → 261 pada 2025-06, hanya 1 resign tercatat.
- Kartu **Pola tidak biasa**: analisis tanpa label (Isolation Forest) setuju kasus ini janggal.
- Tulis catatan lalu klik **Terbukti / Tidak terbukti**: itu menjadi label untuk pelatihan model otomatis di latar belakang.

## 4. Peringatan dini, satu bulan lebih awal (90 dtk) — menu *Input Data Payroll & Setoran*
Badan usaha **EMP-0001** (Manufaktur, DKI Jakarta, kecil) saat ini wajar.
1. Isi ID `EMP-0001`, periode `2026-01`, peserta `53`, keluar `0`, upah `4831900`, seharusnya `10244000`, disetor `9014720` (kurang 12%). Klik **Simpan periode**.
2. Tunggu beberapa detik: skor dihitung ulang otomatis. Buka detailnya: tingkat risiko masih *Rendah*, Setoran iuran "Sekali kurang setor (wajar)", tetapi muncul kartu **Peringatan dini setoran**.
3. Ulangi untuk `2026-02` dengan angka yang sama: kini tingkat risiko naik jadi **Sedang** dan Setoran iuran *Terindikasi*.
Pesan: sistem menunggu 2 bulan sebelum menuduh (hindari salah-tuduh telat bayar), tetapi memberi tahu pemeriksa sejak bulan pertama.

## 5. Master data (30 dtk)
*Master Referensi UMR & Sektor*: tambah/ubah wilayah; skor ikut dihitung ulang otomatis.

## Angka yang boleh disebut (semuanya pada data simulasi)
- Recall gabungan **100%** (75/75 kasus), alarm palsu 10 dari 920 badan usaha bersih (**1,1%**); 0 dari 10 kasus penurunan sah yang salah di-flag.
- Peringatan dini: **25/25 kasus tepat 1 bulan lebih awal** dari Module C, **0/920** alarm palsu. Untuk penurunan bertahap metode ini tidak lebih awal (batas yang kami catat).
- Isolation Forest (tanpa label): AUC 0,997 sebagai konfirmasi independen, **tidak menambah kasus** di atas aturan.
- Model pembelajar dari label pemeriksa: mekanismenya jalan otomatis; **belum terbukti lebih akurat** dari aturan. Jangan diklaim.
- Tidak ada angka penghematan rupiah: belum ada dasar datanya.

## Reset setelah demo
```bash
sqlite3 backend/ecrs.db "DELETE FROM headcount_timeseries WHERE employer_id='EMP-0001' AND periode>='2026-01'; \
 DELETE FROM payroll_timeseries WHERE employer_id='EMP-0001' AND periode>='2026-01'; \
 DELETE FROM remittance_timeseries WHERE employer_id='EMP-0001' AND periode>='2026-01'; \
 DELETE FROM resign_records WHERE employer_id='EMP-0001' AND periode>='2026-01';"
source .venv/bin/activate && python -m scripts.admin rescore && touch backend/main.py
```
