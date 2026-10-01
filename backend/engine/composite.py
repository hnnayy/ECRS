"""Composite scoring, band risiko, dan penjelasan per employer (dari notebook Wave 2)."""
from datetime import datetime, timezone
from dataclasses import asdict

import numpy as np
import pandas as pd

from .config import *  # noqa: F401,F403
from .config import CFG_A, CFG_B, CFG_C, CFG_X, MODULE_LABEL
from .modules import FLAGGED, INSUFFICIENT

BAND_ORDER = {"Tinggi": 0, "Sedang": 1, "Rendah": 2, "Belum bisa dinilai": 3}
BAND_CODE = {"Tinggi": "HIGH", "Sedang": "MEDIUM", "Rendah": "LOW", "Belum bisa dinilai": "INSUFFICIENT"}

def normalize(raw, status, thr, cap):
    """Normalisasi berbasis threshold: 0 -> 0.0, threshold -> 0.5, cap -> 1.0.
    Modul yang tidak FLAGGED dibatasi <= 0.49, yang FLAGGED >= 0.5."""
    raw = pd.Series(raw, dtype=float).clip(lower=0)
    below = 0.5 * raw / thr
    above = 0.5 + 0.5 * (raw - thr) / (cap - thr)
    n = pd.Series(np.where(raw < thr, below, above), index=raw.index).clip(0, 1)
    flagged = pd.Series(status, index=raw.index).eq(FLAGGED)
    n = pd.Series(np.where(flagged, np.maximum(n, 0.5), np.minimum(n, 0.49)), index=raw.index)
    return n.where(raw.notna()).round(3)

NORM_PARAMS = {
    "A": (CFG_A.Z_THRESHOLD, CFG_A.Z_THRESHOLD * CFG_A.CAP_MULT),
    "B": (CFG_B.Z_THRESHOLD, CFG_B.Z_THRESHOLD * CFG_B.CAP_MULT),
    "C": (CFG_C.TOL_PCT, CFG_C.CAP_PCT),
}

def short_text(m, r):
    # kalimat ringkas untuk UI (satu baris per modul)
    if m == "A":
        rs_txt = "tidak ada resign record yang cocok" if r["resign_recorded"] == 0 else f"hanya {int(r['resign_recorded'])} resign tercatat"
        return f"Headcount turun {r['drop_pct']:.0%} ({int(r['hc_before'])}→{int(r['hc_after'])}) pada {r['worst_period']}, {rs_txt}"
    if m == "B":
        return f"Upah {abs(r['pct_vs_median']):.0%} di bawah median cohort {r['cohort_key']}"
    return f"Setoran {r['median_gap_pct']:.0%} di bawah seharusnya selama {int(r['longest_run'])} bulan berturut-turut ({r['run_start']} s/d {r['run_end']})"

METRIC_COLS = {
    "A": ["worst_period", "hc_before", "hc_after", "drop", "drop_pct", "resign_recorded", "z_score", "n_flagged_periods", "n_periods"],
    "B": ["wage_median", "cohort_median_wage", "pct_vs_median", "z_median", "frac_below", "cohort_key", "cohort_level",
          "cohort_size", "umr", "candidate", "n_periods"],
    "C": ["longest_run", "run_start", "run_end", "n_gap_periods", "n_late_paid", "n_periods", "median_gap_pct",
          "cum_shortfall_pct", "total_shortfall"],
}

def composite(results, emp, cfg=CFG_X):
    ids = set()
    for r in results.values():
        if r is not None:
            ids |= set(r["employer_id"])
    base = pd.DataFrame({"employer_id": sorted(ids)})
    if emp is not None:
        base = base.merge(emp[["employer_id", "sektor", "wilayah", "skala"]], on="employer_id", how="left")
    mods = {}
    for m, r in results.items():
        if r is None:
            continue
        thr, cap = NORM_PARAMS[m]
        t = r.copy(); t["norm"] = normalize(t["raw"], t["status"], thr, cap)
        mods[m] = t.set_index("employer_id")
        base[f"status_{m}"] = base["employer_id"].map(t.set_index("employer_id")["status"]).fillna("NO_DATA")
        base[f"score_{m}"] = base["employer_id"].map(t.set_index("employer_id")["norm"])
    sc = [c for c in base.columns if c.startswith("score_")]
    base["coverage"] = base[sc].notna().sum(axis=1)
    base["composite_score"] = (base[sc].mean(axis=1) if cfg.METHOD == "mean" else base[sc].max(axis=1)).round(3)
    base["max_module_score"] = base[sc].max(axis=1)
    base["n_flags"] = sum(base[f"status_{m}"].eq(FLAGGED).astype(int) for m in mods)
    strong = (base["n_flags"] >= 2) | ((base["n_flags"] == 1) & (base["max_module_score"] >= cfg.STRONG_SCORE))
    base["band"] = np.select([base["coverage"] == 0, strong, base["n_flags"] == 1, base["coverage"] < cfg.MIN_COVERAGE],
                             ["Belum bisa dinilai", "Tinggi", "Sedang", "Belum bisa dinilai"], "Rendah")
    base = (base.assign(_o=base["band"].map(BAND_ORDER))
                .sort_values(["_o", "n_flags", "max_module_score", "composite_score"],
                             ascending=[True, False, False, False], na_position="last")
                .drop(columns="_o").reset_index(drop=True))
    base.insert(0, "rank", range(1, len(base) + 1))
    return base, mods

def explain(row, mods):
    # payload penjelasan per employer: kontribusi tiap modul + nilai mentah pendukung
    avail = {m: mods[m].loc[row.employer_id] for m in mods if row.employer_id in mods[m].index
             and pd.notna(mods[m].loc[row.employer_id, "norm"])}
    total = sum(float(r["norm"]) for r in avail.values())
    drivers, notes = [], []
    for m in ["A", "B", "C"]:
        if m not in mods:
            notes.append(f"Module {m} ({MODULE_LABEL[m]}) tidak dijalankan: data tidak tersedia.")
            continue
        if row.employer_id not in mods[m].index:
            notes.append(f"Module {m} ({MODULE_LABEL[m]}): tidak ada data untuk perusahaan ini.")
            continue
        r = mods[m].loc[row.employer_id]
        if r["status"] == INSUFFICIENT:
            notes.append(f"Module {m} ({MODULE_LABEL[m]}): {r['reason']}")
            continue
        drivers.append(dict(
            module=m, label=MODULE_LABEL[m], status=r["status"], flagged=bool(r["status"] == FLAGGED),
            score=float(r["norm"]), contribution_pct=round(100 * float(r["norm"]) / total, 1) if total > 0 else 0.0,
            short_text=short_text(m, r) if r["status"] == FLAGGED else None, text=r["reason"],
            metrics={k: r[k] for k in METRIC_COLS[m] if k in r.index}))
    drivers.sort(key=lambda x: x["score"], reverse=True)
    flagged = [d for d in drivers if d["flagged"]]
    if row.band == "Belum bisa dinilai" and row.coverage == 0:
        summary = "Belum bisa dinilai: data belum cukup di semua modul."
    elif row.band == "Belum bisa dinilai":
        summary = (f"Belum bisa dinilai: hanya {row.coverage} dari {len(mods)} modul punya data cukup "
                   f"(tidak ada indikasi di modul tersebut) — pantau sampai data lengkap.")
    elif flagged:
        summary = f"Prioritas {row.band.lower()} — {len(flagged)} dari {row.coverage} modul menunjukkan indikasi: " + \
                  "; ".join(d["short_text"] for d in flagged) + "."
    else:
        summary = f"Tidak ada indikasi di {row.coverage} modul yang dinilai."
    if 0 < row.coverage < len(mods):
        notes.append(f"Skor gabungan dihitung dari {row.coverage} dari {len(mods)} modul yang tersedia.")
    return dict(summary=summary, drivers=drivers, notes=notes)


# Contoh payload penjelasan untuk perusahaan ranking #1
def _jsonable(o):
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if pd.isna(o) else round(float(o), 4)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, pd.Period):
        return str(o)
    if o is pd.NA or o is pd.NaT:
        return None
    return o


REC = {"Tinggi": "Perlu dicek segera", "Sedang": "Perlu dicek", "Rendah": "Tidak ada indikasi",
       "Belum bisa dinilai": "Belum bisa dinilai — pantau"}

def to_company(r, mods_run):
    return _jsonable(dict(
        id=r.employer_id, rank=r.rank,
        sektor=getattr(r, "sektor", None), wilayah=getattr(r, "wilayah", None), skala=getattr(r, "skala", None),
        composite_score=r.composite_score, max_module_score=r.max_module_score,
        band=r.band, band_code=BAND_CODE[r.band],
        coverage=r.coverage, modules_flagged=[m for m in mods_run if getattr(r, f"status_{m}") == FLAGGED],
        scores={m: getattr(r, f"score_{m}") for m in mods_run},
        status={m: getattr(r, f"status_{m}") for m in mods_run},
        recommendation=REC[r.band], explanation=r.explanation))


def build_payload(comp, mods, data):
    """Payload sama persis dengan output_scores.json lama, tetapi dikembalikan (tidak ditulis ke file)."""
    mods_run = list(mods)
    return {
        "meta": _jsonable(dict(
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            data_source="database", modules_run=mods_run,
            method=f"composite = {CFG_X.METHOD} dari skor modul ternormalisasi (threshold-based, 0.5 = batas flag)",
            config=dict(A=asdict(CFG_A), B=asdict(CFG_B), C=asdict(CFG_C), composite=asdict(CFG_X)),
            remittance_expected_source=data["rem_source"],
            counts=dict(total=len(comp), **comp["band"].value_counts().to_dict()),
            disclaimer="Data simulasi. Daftar ini adalah rekomendasi prioritas pemeriksaan, bukan vonis. "
                       "Keputusan akhir ada di tim pemeriksa BPJS.")),
        "companies": [to_company(r, mods_run) for r in comp.itertuples()],
    }
