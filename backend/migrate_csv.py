"""Migrasi SEKALI: muat CSV Wave 0 ke SQLite, lalu jalankan engine.

    python -m backend.migrate_csv <folder_csv> [--reset]

Setelah ini CSV tidak dibutuhkan lagi: semua data mentah tinggal di backend/ecrs.db.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from .database import DB_PATH, db
from .engine.pipeline import run
from .store import save_scores

TABLES = ["headcount_timeseries", "payroll_timeseries", "remittance_timeseries", "resign_records", "ground_truth"]
from .engine.config import UMR_TABLE


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--reset", action="store_true", help="hapus data mentah & master yang ada sebelum memuat")
    a = ap.parse_args()
    con = db()
    if a.reset:
        for t in TABLES + ["employers", "wilayah", "sektor", "scores", "score_meta"]:
            con.execute(f"DELETE FROM {t}")
    for t in TABLES:
        df = pd.read_csv(a.folder / f"{t}.csv")
        if t == "ground_truth":
            df = df[["employer_id", "anomaly_type", "detail"]]
        cols = ",".join(df.columns)
        con.executemany(f"INSERT OR REPLACE INTO {t} ({cols}) VALUES ({','.join('?' * len(df.columns))})", df.itertuples(index=False, name=None))
        print(f"{t}: {len(df)} baris")
    m = pd.read_csv(a.folder / "employer_master.csv").rename(columns={"sektor_usaha": "sektor"})
    con.executemany("INSERT OR IGNORE INTO wilayah VALUES (?,?)", [(w, UMR_TABLE.get(w)) for w in sorted(m.wilayah.unique())])
    con.executemany("INSERT OR IGNORE INTO sektor VALUES (?)", [(s,) for s in sorted(m.sektor.unique())])
    con.executemany("INSERT OR IGNORE INTO employers VALUES (?,?,?,?,?,?,?)",
                    [(r.employer_id, "", r.sektor, r.wilayah, r.skala, "Aktif", r.tanggal_registrasi) for r in m.itertuples()])
    print(f"employers: {len(m)} baris")
    con.commit()
    payload = run(con)
    save_scores(con, payload)
    con.commit()
    print(f"engine dijalankan: {len(payload['companies'])} employer -> {DB_PATH}")


if __name__ == "__main__":
    main()
