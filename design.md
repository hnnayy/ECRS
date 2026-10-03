# Design — ECRS Risk Radar

Rancangan teknis untuk kebutuhan di `requirement.md`.

## 1. Arsitektur
```
┌────────────┐  HTTP/JSON   ┌───────────────────────── FastAPI (backend/main.py) ─────────────────────────┐
│ React SPA  │ ───────────▶ │ routes ─▶ SQLite (backend/ecrs.db, WAL)                                       │
│ Vite + TS  │ ◀─────────── │   │                                                                           │
└────────────┘              │   ├─ mark_dirty() ─▶ Scheduler thread (jobs.py)                               │
                            │   │                    ├─ rescore  (debounce) ─▶ engine/pipeline ─▶ scores    │
                            │   │                    └─ model_check (±60s)  ─▶ model.py ─▶ model_versions   │
                            │   └─ summary.py (templat + LLM opsional, dengan guard)                        │
                            └───────────────────────────────────────────────────────────────────────────────┘
```
- Satu proses API; satu thread daemon untuk job latar belakang.
- State job (dirty, last_error, dll.) disimpan di memori dan dibuka via `/api/system/status`.
- Skor dihitung batch ke tabel `scores`, lalu dimuat ke memori (`reload_scores`) untuk melayani request cepat.

## 2. Struktur Kode
| Path | Peran |
|---|---|
| `backend/main.py` | Routes, validasi (Pydantic), orkestrasi rescore/model |
| `backend/database.py` | Skema SQLite + migrasi ringan (UMR juta→Rupiah, kolom `decisions.source`) |
| `backend/engine/config.py` | Dataclass konfigurasi per modul, `UMR_TABLE`, label ground truth |
| `backend/engine/modules.py` | Normalisasi data + Module A, B, C |
| `backend/engine/forecast.py` | Peringatan dini setoran |
| `backend/engine/anomaly.py` | Isolation Forest (pola tidak biasa) |
| `backend/engine/composite.py` | Normalisasi skor, composite, band, teks alasan |
| `backend/engine/evaluation.py` | Recall / alarm palsu terhadap ground truth |
| `backend/engine/pipeline.py` | Alur end-to-end dari DB ke payload skor |
| `backend/model.py` | Regresi logistik (numpy) dari label pemeriksa |
| `backend/summary.py` | Ringkasan kasus: templat + LLM + validator |
| `backend/jobs.py` | `Scheduler` (rescore debounce, cek model) |
| `backend/migrate_csv.py` | Isi DB dari CSV Wave 0 (hanya bila kosong) |
| `scripts/` | `admin.py`, `backtest_forecast.py`, `seed_names.py`, `simulate_feedback.py` |
| `frontend/src/pages/` | Dashboard, InputData, Decisions, MasterEmployers, MasterReference |
| `frontend/src/components/` | Worklist, DetailDrawer, Charts, Kpis, ScoreBar, Pager, Modal, Icon, Logo |

## 3. Model Data (SQLite)
| Tabel | Kolom kunci | Catatan |
|---|---|---|
| `wilayah` | `nama` PK, `umr_rp` | UMR dalam Rupiah |
| `sektor` | `nama` PK | |
| `employers` | `employer_id` PK, nama, sektor, wilayah, skala, status, tanggal_registrasi | Divalidasi ke referensi |
| `headcount_timeseries` | (employer_id, periode) PK, `jumlah_peserta_aktif` | |
| `payroll_timeseries` | (employer_id, periode) PK, `rata2_DPI` | |
| `remittance_timeseries` | (employer_id, periode) PK, `expected_contribution`, `actual_remittance` | |
| `resign_records` | (employer_id, periode) PK, `jumlah_keluar` | |
| `ground_truth` | employer_id PK, anomaly_type, detail | Hanya evaluasi data simulasi |
| `scores` | employer_id PK, `rank`, `payload` JSON | Hasil engine |
| `score_meta` | id=1, payload JSON | Metadata run terakhir |
| `decisions` | id, company_id, decision, note, officer, created_at, `source` | `source` = pemeriksa / simulasi |
| `model_versions` | id, created_at, n_labels, n_pos, n_neg, uses_simulated, metrics, weights, `active` | Satu aktif |

Format periode: `YYYY-MM` (juga menerima `YYYYMM`).

## 4. Engine

### 4.1 Pipeline
`DB → normalisasi (modules.norm_*) → Module A/B/C → forecast & anomaly → composite → (blend model aktif) → scores`

### 4.2 Modul
| Modul | Sinyal | Threshold (`config.py`) |
|---|---|---|
| A | z-score penurunan peserta rolling 6 bulan, dikurangi resign tercatat | Z ≥ 2,0; drop ≥ 10%; min 3 periode |
| B | upah median vs median kohort (sektor+wilayah+skala, fallback level lebih lebar) | Z ≥ 1,5; persist ≥ 0,5; kohort ≥ 5; tanpa pre-filter UMR |
| C | selisih setoran vs seharusnya, run berturut-turut, catch-up diperbolehkan | tol 2% & Rp10.000; run ≥ 2; cap 25% |

### 4.3 Normalisasi & Composite
- `normalize`: 0→0, threshold→0,5, cap→1,0. Modul FLAGGED ≥ 0,5; non-flag ≤ 0,49.
- Composite `mean`; band Tinggi bila ≥ 2 modul flag atau 1 modul skor ≥ 0,8; Sedang bila 1 flag lemah; Rendah bila tidak ada; `INSUFFICIENT` bila coverage < 2 modul tanpa flag.
- Status modul: `FLAGGED`, `INSUFFICIENT`, lainnya normal.

### 4.4 Peringatan dini
Kurang setor 1 bulan → tidak mengubah band, tetapi menambah kartu peringatan. Bulan ke-2 berturut-turut → Module C FLAGGED.

### 4.5 Model terlatih
- Fitur: skor/metrik modul. Algoritma: regresi logistik numpy.
- Pelatihan dipicu `auto_train_if_due` bila label cukup (≥ 20, ≥ 5 per kelas, +10 baru).
- Gate: aktifkan hanya bila `AUC_model ≥ AUC_aturan − 0,01`; selain itu tersimpan sebagai versi "ditolak".
- Label simulasi dikecualikan kecuali `ECRS_AUTO_TRAIN_SIMULATED=1`.

## 5. API
| Method | Path | Fungsi |
|---|---|---|
| GET | `/api/health`, `/api/meta`, `/api/filters`, `/api/summary` | Status, metadata, opsi filter, KPI |
| GET | `/api/companies`, `/api/companies/{id}` | Daftar berfilter (sektor, wilayah, band, …) & detail |
| GET | `/api/radar` | Data radar (limit ≤ 2000) |
| GET | `/api/companies/{id}/series` | Deret waktu untuk grafik |
| GET | `/api/companies/{id}/case-summary?llm=` | Ringkasan kasus |
| GET/POST | `/api/timeseries[/{id}]` | Riwayat & upsert periode |
| GET/POST | `/api/decisions` | Riwayat & simpan keputusan |
| GET/POST/PUT/DELETE | `/api/employers[/{id}]` | CRUD badan usaha (q, limit, offset) |
| GET + CRUD | `/api/reference`, rute `wilayah`/`sektor` | Referensi |
| GET | `/api/evaluation` | Metrik terhadap ground truth |
| GET | `/api/model`, `/api/system/status` | Status model & job (read-only) |

Mutasi data (timeseries, employers, referensi) memanggil `mark_dirty()`; rescore berjalan di job setelah debounce.

## 6. Ringkasan Kasus (`summary.py`)
1. Bangun templat deterministik dari payload skor.
2. Jika LLM dikonfigurasi (`.env`, API kompatibel-OpenAI), minta penyusunan ulang menjadi satu paragraf.
3. **Validator** menolak hasil LLM bila: ada angka di luar data, bahasa vonis, ID hilang, terlalu panjang, atau error/kuota.
4. Jika ditolak → kembalikan templat.

## 7. Frontend
- React + Vite + TypeScript, routing dengan `react-router` (`NavLink`).
- Sidebar dapat dilipat; item: Dashboard & Radar Risiko, Input Data Payroll & Setoran, Riwayat Keputusan, Master Data Badan Usaha, Master Referensi UMR & Sektor.
- `api.ts` membungkus fetch; `types.ts` mendefinisikan tipe payload.
- `Pager` komponen pagination bersama (Worklist, Decisions, InputData, MasterEmployers, MasterReference).
- `DetailDrawer` memuat ringkasan, kartu per modul, grafik (`Charts`), form keputusan.
- Gaya tunggal di `styles.css`.

## 8. Konfigurasi Lingkungan
| Variabel | Default | Fungsi |
|---|---|---|
| `ECRS_DB` | `backend/ecrs.db` | Lokasi DB |
| `ECRS_TICK_S` | 5 | Interval loop scheduler |
| `ECRS_RESCORE_DEBOUNCE_S` | 10 | Jeda tenang sebelum rescore |
| `ECRS_MODEL_CHECK_S` | 60 | Interval cek pelatihan |
| `ECRS_RETRAIN_EVERY` | 10 | Label baru per pelatihan ulang |
| `ECRS_AUTO_TRAIN_SIMULATED` | off | Sertakan label simulasi (demo) |
| `.env` LLM | — | Penyedia, kunci, model untuk ringkasan |

## 9. Keputusan Desain & Trade-off
| Keputusan | Alasan | Konsekuensi |
|---|---|---|
| Aturan transparan sebagai inti, model belajar sebagai tambahan | Bisa dijelaskan; label awal sedikit | Model belum terbukti lebih baik |
| Rescore batch + debounce | Banyak input beruntun tidak memicu hitung berulang | Skor tertunda beberapa detik |
| Tanpa tombol admin | Tidak ada RBAC | Operasi latih/rescore via CLI developer |
| SQLite WAL | Sederhana, satu file | Tidak untuk konkurensi tinggi |
| Flag setoran butuh 2 bulan | Hindari salah-tuduh telat bayar | Peringatan dini sebagai penutup celah |
| LLM dengan guard + fallback templat | Cegah halusinasi angka | Sebagian output LLM terbuang |

## 10. Risiko
- UMR/UMP hasil seed perlu verifikasi sumber resmi.
- Pergeseran distribusi data asli vs sintetis → threshold perlu dituning ulang.
- Data BPJS asli ke LLM eksternal → wajib model lokal.
- Race job vs request pada SQLite → timeout 30 dtk dan WAL.
