# Requirement — ECRS Risk Radar

> Data yang dipakai sintetis (bukan data BPJS asli). Dokumen ini menjelaskan *apa* yang harus dilakukan sistem; rancangan teknis ada di `design.md`, rencana kerja di `task.md`.

## 1. Latar Belakang & Tujuan
Verifikasi kepatuhan kontribusi pemberi kerja saat ini **reaktif dan manual**, tanpa urutan prioritas. ECRS Risk Radar mengubahnya menjadi **antrian risiko berperingkat yang bisa dijelaskan**, sehingga pemeriksa memulai dari badan usaha yang paling mencurigakan, bukan secara acak.

Tujuan:
1. Mendeteksi indikasi ketidakpatuhan dari data deret waktu bulanan.
2. Memberi alasan yang bisa dibaca pemeriksa untuk setiap skor.
3. Menangkap keputusan pemeriksa sebagai label untuk memperbaiki model secara bertahap.
4. Meminimalkan salah-tuduh (telat bayar biasa, penurunan peserta yang sah).

## 2. Pengguna
| Peran | Kebutuhan |
|---|---|
| Pemeriksa | Melihat antrian prioritas, membaca alasan, memutuskan Terbukti / Tidak terbukti |
| Operator data | Memasukkan data periode (peserta, upah, setoran), mengelola master |
| Developer | Menjalankan rescore/latih model lewat CLI, memantau status read-only |

Tidak ada RBAC/login pada versi ini.

## 3. Kebutuhan Fungsional

### FR-1 Deteksi risiko (engine)
- **FR-1.1 Module A — Volatilitas jumlah peserta**: tandai penurunan peserta tidak wajar (z-score ≥ 2,0, turun ≥ 10%) yang tidak didukung catatan resign.
- **FR-1.2 Module B — Benchmark upah sejenis**: tandai upah yang jauh di bawah median kelompok sejenis (sektor/wilayah/skala; z ≥ 1,5, persisten ≥ 50% periode, kohort ≥ 5).
- **FR-1.3 Module C — Rekonsiliasi setoran**: tandai kurang setor > 2% **dan** > Rp10.000 selama ≥ 2 bulan berturut-turut; kurang bayar yang dilunasi bulan berikutnya tidak dihitung.
- **FR-1.4 Composite**: gabungkan skor modul (rata-rata) menjadi band **Tinggi / Sedang / Rendah / Belum bisa dinilai**. Satu modul dengan skor ≥ 0,8 langsung Tinggi. Data < 2 modul dan tidak ada flag → "Belum bisa dinilai", bukan "Rendah".
- **FR-1.5 Peringatan dini**: kurang setor 1 bulan tidak di-flag, tetapi menampilkan kartu "Peringatan dini setoran".
- **FR-1.6 Pola tidak biasa**: Isolation Forest (tanpa label) sebagai konfirmasi independen, tidak menambah kasus di atas aturan.
- **FR-1.7 Penjelasan**: setiap skor disertai kalimat alasan per modul dan metrik pendukung.

### FR-2 Dashboard & Radar Risiko
- KPI ringkas (jumlah badan usaha, Tinggi, Sedang, dll.).
- Daftar kerja (worklist) berperingkat dengan filter sektor, wilayah, tingkat risiko, jenis indikasi; pagination.
- Visualisasi radar/grafik.

### FR-3 Detail kasus
- Panel detail per badan usaha: skor, alasan, grafik deret waktu (peserta, upah, setoran), kartu pola tidak biasa.
- **Ringkasan kasus**: templat deterministik selalu tersedia; LLM opsional merapikan menjadi satu paragraf. Hasil LLM ditolak dan diganti templat jika memuat angka di luar data, bahasa vonis, ID hilang, terlalu panjang, atau penyedia gagal.
- Tombol salin ringkasan.

### FR-4 Input data
- Form input per periode: ID, periode (YYYY-MM), peserta, keluar, upah, iuran seharusnya, setoran. Upsert bila periode sudah ada.
- Menampilkan riwayat periode terbaru badan usaha.
- Setelah data berubah, skor dihitung ulang otomatis.

### FR-5 Keputusan pemeriksa (feedback loop)
- Pemeriksa memilih Terbukti / Tidak terbukti disertai catatan dan nama pemeriksa.
- Riwayat keputusan dapat dilihat (filter per badan usaha, pagination).

### FR-6 Model terlatih otomatis
- Model regresi logistik dilatih dari label pemeriksa tanpa tombol/endpoint admin di UI.
- Syarat latih: ≥ 20 label akhir (≥ 5 per kelas) dan +10 label baru sejak pelatihan terakhir.
- Versi baru diaktifkan hanya bila AUC tidak lebih dari 0,01 di bawah skor aturan; jika tidak ditandai "ditolak".
- Label simulasi hanya untuk demo (`ECRS_AUTO_TRAIN_SIMULATED=1`).

### FR-7 Master data
- **Badan usaha**: CRUD (ID, nama, sektor, wilayah, skala, status, tanggal registrasi), pencarian, pagination; validasi sektor/wilayah terhadap referensi.
- **Referensi**: CRUD wilayah (dengan UMR dalam Rupiah) dan sektor.
- Perubahan master memicu rescore otomatis.

### FR-8 Operasional
- Job latar belakang: rescore (debounce ±10 dtk) dan cek pelatihan model (±60 dtk).
- Endpoint status read-only: `GET /api/system/status`, `GET /api/model`, `GET /api/health`.
- CLI developer: `python -m scripts.admin rescore|train|activate <id>|deactivate`.
- Migrasi sekali dari CSV Wave 0 bila DB kosong (`python -m backend.migrate_csv`).

## 4. Kebutuhan Non-Fungsional
| ID | Kebutuhan |
|---|---|
| NFR-1 | **Explainability**: setiap flag punya alasan yang dapat ditelusuri ke data. |
| NFR-2 | **Minim salah-tuduh**: target alarm palsu rendah; penurunan peserta sah tidak boleh di-flag. |
| NFR-3 | **Bahasa non-vonis**: UI/ringkasan menyebut "terindikasi", bukan menyatakan bersalah. |
| NFR-4 | **Privasi**: data BPJS asli tidak boleh dikirim ke LLM pihak ketiga; gunakan Ollama lokal. Kunci API bersifat pribadi, disimpan di `.env` (tidak di git). |
| NFR-5 | **Ketahanan job**: kegagalan job tidak mematikan thread; error dicatat di status. |
| NFR-6 | **Kinerja**: endpoint daftar mendukung limit/offset; skor dibaca dari tabel hasil, bukan dihitung ulang tiap request. |
| NFR-7 | **Portabilitas**: SQLite satu file (`backend/ecrs.db`), tidak masuk git. |
| NFR-8 | **Aksesibilitas UI**: label ARIA, navigasi keyboard pada sidebar/modal. |
| NFR-9 | **Bahasa**: antarmuka dan pesan dalam Bahasa Indonesia. |

## 5. Target Kinerja (pada data simulasi)
- 1.020 badan usaha; 75 kasus disisipkan (25 per jenis) + 10 penurunan sah.
- Recall gabungan 100% (75/75); alarm palsu ≈ 1,1% (10/920); 0/10 penurunan sah ter-flag.
- Peringatan dini Module C: 25/25 kasus tepat 1 bulan lebih awal, 0/920 alarm palsu.
- Model pembelajar: **belum terbukti** lebih akurat dari aturan — tidak boleh diklaim.
- Tidak ada klaim penghematan rupiah.

## 6. Batasan & Asumsi
- Data sintetis; UMR/UMP 2025 per provinsi perlu dicek ulang ke sumber resmi.
- Tidak ada autentikasi/otorisasi.
- Peringatan dini tidak lebih awal untuk penurunan bertahap.
- Iuran bila kolom "seharusnya" kosong dihitung 5% dari upah, batas upah Rp12.000.000.

## 7. Di Luar Lingkup
RBAC/SSO, integrasi sistem BPJS produksi, notifikasi email/chat, estimasi nilai rupiah yang dipulihkan, halaman pemantauan job di UI.

## 8. Kriteria Penerimaan
1. Dashboard menampilkan antrian terurut dengan filter dan pagination berfungsi.
2. Input periode baru → skor berubah otomatis tanpa aksi manual; skenario demo EMP-0001 (Rendah → Sedang pada bulan ke-2) terpenuhi.
3. Keputusan tersimpan dan tampil di Riwayat Keputusan.
4. Model hanya aktif bila memenuhi syarat AUC; status terbaca via API.
5. Ringkasan LLM yang melanggar pengaman selalu jatuh ke templat.
6. CRUD master menolak sektor/wilayah yang tidak ada dan menolak penghapusan yang merusak referensi.
