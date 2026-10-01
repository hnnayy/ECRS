"""Backtest peringatan dini setoran terhadap Module C (dev). Jalankan dari root proyek:  python -m scripts.backtest_forecast

A) Data riil (lonjakan mendadak): berapa bulan lebih awal dibanding Module C, dan berapa employer bersih yang kena alarm palsu.
B) Skenario SUNTIKAN (bukan temuan): 30 employer bersih diberi penurunan setoran BERTAHAP. Mendokumentasikan batas: peringatan dini
   (lonjakan) tidak lebih awal dari Module C pada penurunan bertahap.
"""
import numpy as np
import pandas as pd

from backend.database import db
from backend.engine.forecast import first_alarm_month
from backend.engine.modules import module_c, prepare
from backend.engine.pipeline import COLS, load_raw

con = db()
raw = load_raw(con)
data = prepare(raw, COLS)
rem = data["rem"].copy()
periods = sorted(rem["period"].unique())
gt = raw["ground_truth"].set_index("employer_id").anomaly_type


def first_c_flag(r: pd.DataFrame) -> dict:
    out = {}
    for p in periods[1:]:
        res, _ = module_c(r[r["period"] <= p])
        for eid in res.loc[res["status"] == "FLAGGED", "employer_id"]:
            out.setdefault(eid, p)
    return out


def report(title, ew, cf, target_ids, clean_ids):
    lead = [(cf[e] - ew[e]).n for e in target_ids if e in ew and e in cf]
    print(f"\n== {title} ==")
    print(f"kasus: {len(target_ids)} | terdeteksi peringatan dini: {sum(e in ew for e in target_ids)} | terdeteksi Module C: {sum(e in cf for e in target_ids)}")
    if lead:
        print(f"keunggulan waktu peringatan dini vs Module C (bulan): rata-rata {np.mean(lead):.1f}, min {min(lead)}, maks {max(lead)}")
    print(f"employer bersih kena alarm sepanjang riwayat -> peringatan dini: {sum(e in ew for e in clean_ids)}/{len(clean_ids)} | Module C: {sum(e in cf for e in clean_ids)}/{len(clean_ids)}")


clean = [e for e in gt.index if gt[e] == "CLEAN"]
ew, cf = first_alarm_month(rem, periods), first_c_flag(rem)
report("A) Data riil: anomali setoran (lonjakan mendadak)", ew, cf, [e for e in gt.index if gt[e] == "REMITTANCE_GAP"], clean)

# B) skenario suntikan: penurunan bertahap mulai bulan ke-5, +1,2% per bulan (+ kebisingan asli tetap)
rng = np.random.default_rng(0)
victims = list(rng.choice(clean, 30, replace=False))
rem2 = rem.copy()
for e in victims:
    m = rem2["employer_id"] == e
    k = np.arange(m.sum())
    ramp = np.clip((k - 3) * 0.012, 0, None)                # bulan 5 dst: 1,2%, 2,4%, ...
    rem2.loc[m, "actual"] = rem2.loc[m, "actual"].to_numpy() * (1 - ramp)
ew2, cf2 = first_alarm_month(rem2, periods), first_c_flag(rem2)
others = [e for e in clean if e not in victims]
report("B) Skenario suntikan: penurunan bertahap (batas metode, BUKAN temuan)", ew2, cf2, victims, others)
