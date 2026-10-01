"""Isolation Forest: sinyal TAMBAHAN 'pola tidak biasa' (tanpa label, tidak mengubah composite / tingkat risiko).

Fitur dihitung dari data mentah (bukan dari keluaran aturan), agar menangkap kejanggalan yang tidak diprediksi
aturan A/B/C. Skor = peringkat persentil (0–1) terhadap seluruh badan usaha yang datanya cukup.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score

MIN_PERIODS = 3
FLAG_TOP_FRAC = 0.05          # 5% teratas ditandai (tetap, tidak disetel dari ground truth)
N_REASONS = 3

FEATURES = {
    "hc_max_drop": "penurunan peserta tak terjelaskan terbesar dalam sebulan",
    "hc_vol": "naik-turun jumlah peserta (di luar resign) antar bulan",
    "unexplained_drop": "peserta hilang yang tidak dijelaskan catatan resign",
    "resign_rate": "rasio peserta keluar per bulan",
    "wage_rel": "upah dibanding perusahaan sejenis",
    "wage_vol": "naik-turun upah antar bulan",
    "gap_mean": "rata-rata kurang setor",
    "gap_max": "kurang setor terbesar dalam sebulan",
    "gap_vol": "naik-turun selisih setoran",
    "gap_months": "porsi bulan dengan kurang setor",
}
PCT_FEATURES = {"hc_max_drop", "hc_vol", "unexplained_drop", "resign_rate", "gap_mean", "gap_max", "gap_vol", "gap_months", "wage_vol"}


def build_features(data: dict) -> pd.DataFrame:
    hc = data["hc"].sort_values(["employer_id", "period"]).copy()
    hc["prev"] = hc.groupby("employer_id")["headcount"].shift(1)
    hc = hc.merge(data["rs"], on=["employer_id", "period"], how="left") if data["rs"] is not None else hc.assign(n_resign=0)
    hc["n_resign"] = hc["n_resign"].fillna(0)
    hc["drop"] = (hc["prev"] - hc["headcount"]).clip(lower=0)
    hc["unexpl"] = (hc["drop"] - hc["n_resign"]).clip(lower=0)
    # penurunan yang dijelaskan catatan resign tidak dihitung janggal (sama seperti logika Module A)
    hc["drop_pct"] = hc["unexpl"] / hc["prev"]
    hc["chg"] = (hc["headcount"] - hc["prev"] + np.minimum(hc["n_resign"], hc["drop"])) / hc["prev"]
    hc["resign_pct"] = hc["n_resign"] / hc["headcount"]
    g = hc.groupby("employer_id")
    f = pd.DataFrame({
        "n_periods": g["period"].count(),
        "hc_max_drop": g["drop_pct"].max(), "hc_vol": g["chg"].std(),
        "unexplained_drop": g["unexpl"].sum() / g["headcount"].mean(), "resign_rate": g["resign_pct"].mean(),
    })

    p = data["panel"].merge(data["emp"][["employer_id", "sektor", "wilayah", "skala"]], on="employer_id")
    med = p.groupby(["sektor", "wilayah", "skala", "period"])["log_wage"].transform("median")
    p = p.assign(rel=p["log_wage"] - med).sort_values(["employer_id", "period"])
    p["dlog"] = p.groupby("employer_id")["log_wage"].diff()
    gp = p.groupby("employer_id")
    f["wage_rel"], f["wage_vol"] = gp["rel"].mean(), gp["dlog"].std()

    r = data["rem"].copy()
    r["gap"] = ((r["expected"] - r["actual"]) / r["expected"]).where(r["expected"] > 0)
    gr = r.groupby("employer_id")
    f["gap_mean"], f["gap_max"], f["gap_vol"] = gr["gap"].mean(), gr["gap"].max(), gr["gap"].std()
    f["gap_months"] = r.assign(o=(r["gap"] > 0.02)).groupby("employer_id")["o"].mean()
    return f


def _reasons(row: pd.Series, med: pd.Series, mad: pd.Series) -> list[dict]:
    z = (row - med) / mad
    out = []
    for feat in z.abs().sort_values(ascending=False).index[:N_REASONS]:
        v, m = row[feat], med[feat]
        fmt = (lambda x: f"{x:.0%}") if feat in PCT_FEATURES else (lambda x: f"{x:+.0%}")
        out.append({"feature": feat, "label": FEATURES[feat], "value": round(float(v), 4), "z": round(float(z[feat]), 1),
                    "text": f"{FEATURES[feat].capitalize()}: {fmt(v)} (umumnya {fmt(m)})"})
    return out


def run_isolation_forest(data: dict, seed: int = 0) -> pd.DataFrame:
    """Kembalikan employer_id, if_score (0–1, persentil), if_flag, reasons. Data kurang -> skor NaN."""
    f = build_features(data)
    ok = f[(f["n_periods"] >= MIN_PERIODS)].drop(columns="n_periods").dropna()
    model = IsolationForest(n_estimators=300, contamination="auto", random_state=seed).fit(ok.values)
    raw = -model.score_samples(ok.values)                      # makin besar = makin janggal
    score = pd.Series(raw, index=ok.index).rank(pct=True)
    med = ok.median()
    mad = (ok - med).abs().median().replace(0, np.nan).fillna(ok.std().replace(0, 1)) * 1.4826
    flagged = score >= (1 - FLAG_TOP_FRAC)
    out = pd.DataFrame({"employer_id": ok.index, "if_score": score.values.round(3), "if_flag": flagged.values})
    out["reasons"] = [_reasons(ok.loc[e], med, mad) if fl else [] for e, fl in zip(out["employer_id"], out["if_flag"])]
    return out


def evaluate_if(iff: pd.DataFrame, m: pd.DataFrame) -> dict:
    """m = hasil merge composite x ground truth (kolom is_any, band). Menjawab: apakah IF menambah nilai di atas aturan?"""
    d = m.merge(iff[["employer_id", "if_score", "if_flag"]], on="employer_id", how="left")
    d = d[d["if_score"].notna()]
    y = d["is_any"].astype(bool)
    rules = d["band"].isin(["Tinggi", "Sedang"])
    flag = d["if_flag"].astype(bool)
    tp, fp = int((flag & y).sum()), int((flag & ~y).sum())
    missed = y & ~rules                                         # kasus nyata yang dilewatkan aturan
    union = rules | flag
    return {
        "n_dinilai": int(len(d)), "n_kasus": int(y.sum()), "flag_top_persen": FLAG_TOP_FRAC,
        "auc": round(float(roc_auc_score(y, d["if_score"])), 3),
        "flag": {"ditandai": int(flag.sum()), "tp": tp, "fp": fp, "recall": round(tp / max(int(y.sum()), 1), 3),
                 "precision": round(tp / max(int(flag.sum()), 1), 3)},
        "kasus_terlewat_aturan": {"jumlah": int(missed.sum()), "ditangkap_if": int((missed & flag).sum())},
        "tambahan_di_luar_aturan": {"ditandai_if_bukan_aturan": int((flag & ~rules).sum()),
                                    "di_antaranya_kasus_nyata": int((flag & ~rules & y).sum())},
        "aturan_atau_if": {"recall": round(float((union & y).sum() / max(int(y.sum()), 1)), 3),
                           "fp": int((union & ~y).sum()), "fpr": round(float((union & ~y).sum() / max(int((~y).sum()), 1)), 4)},
        "aturan_saja": {"recall": round(float((rules & y).sum() / max(int(y.sum()), 1)), 3),
                        "fp": int((rules & ~y).sum()), "fpr": round(float((rules & ~y).sum() / max(int((~y).sum()), 1)), 4)},
    }
