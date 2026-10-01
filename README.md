# ECRS Risk Radar

Engine deteksi risiko kontribusi pemberi kerja (Module A/B/C + composite + model terlatih) berjalan **di backend**.
Semua data (master, deret waktu mentah, skor, keputusan pemeriksa, versi model) tersimpan di `backend/ecrs.db` (SQLite).
Data yang dipakai sintetis, bukan data BPJS asli.

```
backend/
  engine/      aturan A/B/C, composite, penjelasan, evaluasi   (dipindah dari notebook)
  model.py     model terlatih (regresi logistik, numpy) dari label pemeriksa
  main.py      API FastAPI
  database.py  skema SQLite
  migrate_csv.py  migrasi SEKALI dari CSV Wave 0 (hanya jika DB masih kosong)
frontend/      React + Vite + TypeScript
```

## Menjalankan
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload            # API di :8000 (Swagger: /docs)

cd frontend && npm install && npm run dev      # UI di :5173
```

## Mengisi database dari nol
`backend/ecrs.db` tidak masuk git. Jika DB kosong, muat CSV Wave 0 (enam file: `employer_master`, `headcount_timeseries`,
`payroll_timeseries`, `remittance_timeseries`, `resign_records`, `ground_truth`):
```bash
python -m backend.migrate_csv <folder_csv>
```
Setelah itu CSV tidak dibutuhkan lagi. Data baru masuk lewat halaman **Input Data** (atau `POST /api/timeseries`), lalu `POST /api/rescore`.

## Otomatis di latar belakang (tanpa admin)
Aplikasi tidak punya RBAC, jadi tidak ada tombol/endpoint untuk melatih model atau menghitung ulang skor. Job di backend (`backend/jobs.py`):
- **Rescore**: beberapa detik setelah data periode / master berubah, engine dijalankan ulang otomatis.
- **Latih model**: tiap ±60 dtk dicek; jika ada ≥20 label hasil akhir pemeriksa (≥5 per kelas) dan +10 label baru sejak pelatihan terakhir, model dilatih ulang. Versi baru dipakai hanya jika AUC-nya tidak lebih dari 0,01 di bawah skor aturan (jika tidak, ditandai "ditolak").
- Tidak ada halaman pemantauan di UI; status hanya-baca tersedia di `GET /api/system/status` dan `GET /api/model`.

Untuk developer: `python -m scripts.admin rescore|train|activate <id>|deactivate`; demo dengan label simulasi:
`python -m scripts.simulate_feedback` lalu jalankan API dengan `ECRS_AUTO_TRAIN_SIMULATED=1`.
Pengaturan: `ECRS_RESCORE_DEBOUNCE_S`, `ECRS_MODEL_CHECK_S`, `ECRS_RETRAIN_EVERY`.

## Ringkasan kasus (templat + LLM opsional)
Panel detail employer menampilkan "Ringkasan kasus": **templat deterministik** yang selalu tersedia. Jika `.env` diisi
(salin dari `.env.example`; kunci PRIBADI dari penyedia gratis, mis. Gemini AI Studio), LLM merapikan templat itu menjadi satu paragraf.
Hasil LLM **ditolak dan diganti templat** bila memuat angka di luar data, bahasa vonis, ID hilang, terlalu panjang, atau penyedia
gagal/kuota habis (`backend/summary.py`). Format API kompatibel-OpenAI, jadi bisa Gemini, Groq, OpenRouter, GitHub Models, atau Ollama lokal.
Catatan: tier gratis Gemini memakai konten untuk memperbaiki produk Google, jangan kirim data BPJS asli; untuk itu pakai Ollama lokal.
