"""Evaluasi engine terhadap ground truth sintetis (precision/recall per modul, precision@K)."""
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

from .config import NEGATIVE_LABELS, POSITIVE_LABELS
from .modules import FLAGGED, INSUFFICIENT

def build_truth(G):
    if G is None or G.empty:
        return None
    lab = G["anomaly_type"].astype(str).str.upper().str.strip()
    t = pd.DataFrame({"employer_id": G["employer_id"].astype(str), "label": lab})
    for m, pats in POSITIVE_LABELS.items():
        t[f"is_{m}"] = lab.str.contains("|".join(pats), na=False)
    t["is_any"] = ~lab.isin(NEGATIVE_LABELS)
    return t.groupby("employer_id", as_index=False).agg(
        label=("label", lambda s: ",".join(sorted(set(s)))), **{k: (k, "any") for k in ["is_A", "is_B", "is_C", "is_any"]})

def prf(pred, actual):
    tp, fp = int((pred & actual).sum()), int((pred & ~actual).sum())
    fn, tn = int((~pred & actual).sum()), int((~pred & ~actual).sum())
    return dict(tp=tp, fp=fp, fn=fn, tn=tn,
                precision=round(tp / (tp + fp), 3) if tp + fp else np.nan,
                recall=round(tp / (tp + fn), 3) if tp + fn else np.nan,
                fpr=round(fp / (fp + tn), 3) if fp + tn else np.nan)

def evaluate(comp, truth):
    m = comp.merge(truth, on="employer_id", how="left")
    for c in ["is_A", "is_B", "is_C", "is_any"]:
        m[c] = m[c].fillna(False).astype(bool)
    rows = []
    for mod in ["A", "B", "C"]:
        if f"status_{mod}" not in m:
            continue
        ev = m[~m[f"status_{mod}"].isin([INSUFFICIENT, "NO_DATA"])]
        rows.append(dict(level=f"Module {mod}", **prf(ev[f"status_{mod}"].eq(FLAGGED), ev[f"is_{mod}"])))
    ev = m[m["band"] != "Belum bisa dinilai"]
    rows.append(dict(level="Composite (band Tinggi/Sedang)", **prf(ev["band"].isin(["Tinggi", "Sedang"]), ev["is_any"])))
    n_pos = int(m["is_any"].sum())
    at_k = {f"precision@{k}": round(float(m.head(k)["is_any"].mean()), 3) for k in (10, 25, 50, n_pos) if 0 < k <= len(m)}
    return pd.DataFrame(rows), at_k, m
