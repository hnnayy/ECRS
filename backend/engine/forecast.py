"""Peringatan dini setoran iuran: sinyal TAMBAHAN yang lebih awal 1 bulan dari Module C untuk LONJAKAN kurang setor.

Module C sengaja menunggu kurang setor >= 2 bulan berturut-turut (agar telat bayar wajar tidak dituduh). Peringatan dini mengisi
jeda itu: selisih bulan terakhir >= 5% DAN >= 4 simpangan baku di atas riwayat 6 bulan sebelumnya milik badan usaha itu sendiri.
Ambang 5% ditetapkan dari kebisingan data bersih (selisih bersih maksimal ±3,9%), bukan dari kasus curang.

Hasil backtest (scripts/backtest_forecast.py): pada lonjakan mendadak, 25/25 kasus terdeteksi tepat 1 bulan lebih awal dari Module C,
0/920 alarm palsu. Pada penurunan BERTAHAP komponen tren yang sempat dicoba tidak lebih awal dari Module C, sehingga dibuang.
"""
import numpy as np
import pandas as pd

WINDOW = 6
MIN_HISTORY = 4
JUMP_MIN, JUMP_Z = 0.05, 4.0
STD_FLOOR = 0.01
COLUMNS = ["employer_id", "ew_flag", "ew_last_gap", "ew_text"]


def gap_series(rem: pd.DataFrame) -> pd.DataFrame:
    d = rem.sort_values(["employer_id", "period"]).copy()
    d["gap"] = ((d["expected"] - d["actual"]) / d["expected"]).where(d["expected"] > 0)
    return d.dropna(subset=["gap"])


def assess(gaps: np.ndarray) -> dict | None:
    """gaps: selisih setoran (proporsi) berurutan sampai bulan terakhir. None bila riwayat kurang."""
    if len(gaps) < MIN_HISTORY + 1:
        return None
    last, hist = gaps[-1], gaps[-1 - WINDOW:-1]
    mu, sd = hist.mean(), max(hist.std(ddof=1) if len(hist) > 1 else 0.0, STD_FLOOR)
    z = (last - mu) / sd
    return {"last_gap": float(last), "z": float(z), "jump": bool(last >= JUMP_MIN and z >= JUMP_Z)}


def run_early_warning(rem: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for eid, g in gap_series(rem).groupby("employer_id", sort=False):
        a = assess(g["gap"].to_numpy())
        if a is None:
            continue
        text = (f"Selisih setoran bulan terakhir {a['last_gap']:.0%}, jauh di atas kebiasaan badan usaha ini. "
                f"Module C baru mengibarkan bendera jika berlanjut bulan depan.") if a["jump"] else None
        rows.append({"employer_id": eid, "ew_flag": a["jump"], "ew_last_gap": a["last_gap"], "ew_text": text})
    return pd.DataFrame(rows, columns=COLUMNS)


def first_alarm_month(rem: pd.DataFrame, upto_periods: list) -> dict:
    """Backtest: untuk tiap bulan t, jalankan penilaian hanya dengan data <= t; kembalikan bulan alarm pertama per employer."""
    first: dict = {}
    for p in upto_periods:
        res = run_early_warning(rem[rem["period"] <= p])
        for eid in res.loc[res["ew_flag"], "employer_id"]:
            first.setdefault(eid, p)
    return first
