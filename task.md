# Task — ECRS Risk Radar

Legenda: `[x]` selesai (ada di kode), `[~]` sedang dikerjakan (perubahan belum di-commit), `[ ]` belum.
Referensi: kebutuhan di `requirement.md`, rancangan di `design.md`.

## Fase 1 — Engine deteksi
- [x] Konfigurasi threshold per modul (`engine/config.py`) — FR-1
- [x] Normalisasi data & Module A volatilitas peserta — FR-1.1
- [x] Module B benchmark upah kohort — FR-1.2
- [x] Module C rekonsiliasi setoran — FR-1.3
- [x] Composite, band risiko, teks alasan — FR-1.4, FR-1.7
- [x] Peringatan dini setoran (`forecast.py`) — FR-1.5
- [x] Isolation Forest pola tidak biasa (`anomaly.py`) — FR-1.6
- [x] Evaluasi terhadap ground truth (`evaluation.py`)
- [x] Backtest peringatan dini (`scripts/backtest_forecast.py`)

## Fase 2 — Backend & data
- [x] Skema SQLite + migrasi ringan (`database.py`)
- [x] Migrasi CSV Wave 0 (`migrate_csv.py`)
- [x] Seed nama badan usaha (`scripts/seed_names.py`)
- [x] API baca: companies, radar, series, summary, filters, evaluation — FR-2
- [x] API input periode (upsert) — FR-4
- [x] API keputusan pemeriksa — FR-5
- [x] CRUD badan usaha & referensi (wilayah/sektor) — FR-7
- [x] Scheduler rescore debounce + cek model (`jobs.py`) — FR-8
- [x] Model regresi logistik + gate AUC + versi (`model.py`) — FR-6
- [x] Simulasi label & CLI admin (`simulate_feedback.py`, `admin.py`)
- [x] Ringkasan kasus templat + LLM + validator (`summary.py`) — FR-3
- [x] Endpoint status read-only (`/api/system/status`, `/api/model`)

## Fase 3 — Frontend
- [x] Layout, sidebar lipat, routing (`App.tsx`)
- [x] Dashboard: KPI, Worklist, filter, grafik — FR-2
- [x] DetailDrawer: ringkasan, kartu modul, keputusan — FR-3, FR-5
- [x] Halaman Input Data — FR-4
- [x] Halaman Riwayat Keputusan
- [x] Master Badan Usaha & Master Referensi — FR-7
- [~] Komponen `Pager` dan pagination di Worklist, Decisions, InputData, MasterEmployers, MasterReference
- [~] Penyesuaian `api.ts` (limit/offset) & `styles.css`

## Fase 4 — Penyelesaian (belum)
- [ ] Selesaikan & commit perubahan pagination (frontend + `backend/main.py`)
- [ ] Verifikasi manual: tiap halaman dengan data > 1 halaman, filter + pagination tidak saling mereset
- [ ] Verifikasi UMR/UMP ke sumber resmi (`UMR_TABLE`)
- [ ] Tes otomatis backend (pytest): modul A/B/C, composite, normalize, validator summary, gate model
- [ ] Tes API (FastAPI `TestClient`): upsert → dirty → rescore, validasi CRUD, penolakan referensi tidak valid
- [ ] Tes frontend minimal (smoke test render halaman) atau checklist manual terdokumentasi
- [ ] Audit aksesibilitas (kontras, fokus, label form) — NFR-8
- [ ] Pemindaian keamanan DAST (HawkScan) atas API, perbaiki temuan
- [ ] Jalankan skenario demo EMP-0001 end-to-end dan reset (`DEMO.md`) — kriteria penerimaan 2
- [ ] Perbarui `README.md` dan `DEMO.md` bila perilaku berubah (README masih menyebut `.env.example` yang sudah dihapus)

## Fase 5 — Pengembangan lanjut (opsional)
- [ ] Autentikasi + RBAC bila dipakai di luar demo
- [ ] Ganti ground truth simulasi dengan label asli, tuning ulang threshold
- [ ] Evaluasi apakah model terlatih benar-benar mengungguli aturan sebelum dipakai di skor utama
- [ ] Halaman pemantauan job/model (read-only) bila dibutuhkan operator
- [ ] Ekspor daftar kasus (CSV) untuk pemeriksa
- [ ] Penyedia LLM lokal (Ollama) sebagai default untuk data asli
- [ ] Rescore inkremental (hanya badan usaha yang berubah)
- [ ] Migrasi ke database server bila konkurensi meningkat
