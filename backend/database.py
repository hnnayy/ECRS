"""SQLite: satu-satunya penyimpanan data (master, deret waktu mentah, skor engine, keputusan, model)."""
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("ECRS_DB", ROOT / "backend/ecrs.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS wilayah (nama TEXT PRIMARY KEY, umr_rp REAL);
CREATE TABLE IF NOT EXISTS sektor (nama TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS employers (
    employer_id TEXT PRIMARY KEY, nama TEXT NOT NULL DEFAULT '', sektor TEXT NOT NULL, wilayah TEXT NOT NULL,
    skala TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Aktif', tanggal_registrasi TEXT NOT NULL);

-- data mentah untuk engine (nama tabel & kolom sama dengan CSV Wave 0)
CREATE TABLE IF NOT EXISTS headcount_timeseries (employer_id TEXT, periode TEXT, jumlah_peserta_aktif INTEGER, PRIMARY KEY (employer_id, periode));
CREATE TABLE IF NOT EXISTS payroll_timeseries (employer_id TEXT, periode TEXT, rata2_DPI REAL, PRIMARY KEY (employer_id, periode));
CREATE TABLE IF NOT EXISTS remittance_timeseries (employer_id TEXT, periode TEXT, expected_contribution REAL, actual_remittance REAL, PRIMARY KEY (employer_id, periode));
CREATE TABLE IF NOT EXISTS resign_records (employer_id TEXT, periode TEXT, jumlah_keluar INTEGER, PRIMARY KEY (employer_id, periode));
CREATE TABLE IF NOT EXISTS ground_truth (employer_id TEXT PRIMARY KEY, anomaly_type TEXT, detail TEXT);

-- hasil engine
CREATE TABLE IF NOT EXISTS scores (employer_id TEXT PRIMARY KEY, rank INTEGER, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS score_meta (id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL);

-- feedback loop
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, company_id TEXT NOT NULL, decision TEXT NOT NULL,
    note TEXT NOT NULL, officer TEXT NOT NULL, created_at TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'pemeriksa');
CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, n_labels INTEGER NOT NULL, n_pos INTEGER NOT NULL,
    n_neg INTEGER NOT NULL, uses_simulated INTEGER NOT NULL, metrics TEXT NOT NULL, weights TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 0);
"""


def _migrate_umr_to_rupiah(con: sqlite3.Connection) -> None:
    """DB lama menyimpan UMR dalam juta (umr_jt, angka simulasi). Ubah ke Rupiah; ganti placeholder lama dengan UMP dari config."""
    from .engine.config import UMR_TABLE
    if "umr_jt" not in {r[1] for r in con.execute("PRAGMA table_info(wilayah)")}:
        return
    con.execute("ALTER TABLE wilayah RENAME COLUMN umr_jt TO umr_rp")
    con.execute("UPDATE wilayah SET umr_rp = ROUND(umr_rp * 1000000) WHERE umr_rp IS NOT NULL")
    placeholders = {"DKI Jakarta": 5_400_000, "Jawa Barat": 2_300_000, "Jawa Timur": 2_500_000}
    for nama, val in UMR_TABLE.items():
        con.execute("UPDATE wilayah SET umr_rp = ? WHERE nama = ? AND (umr_rp IS NULL OR umr_rp = ?)", [val, nama, placeholders.get(nama)])
    con.commit()


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=30)  # job latar belakang & request berbagi file DB
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    _migrate_umr_to_rupiah(con)
    if "source" not in {r[1] for r in con.execute("PRAGMA table_info(decisions)")}:
        con.execute("ALTER TABLE decisions ADD COLUMN source TEXT NOT NULL DEFAULT 'pemeriksa'")
    return con
