"""Module A (registration volatility), B (peer-group wage), C (contribution reconciliation).

Logika dipindah verbatim dari notebook Wave 1/2; hanya I/O notebook yang dibuang.
"""
import numpy as np
import pandas as pd

from .config import *  # noqa: F401,F403
from .config import CFG_A, CFG_B, CFG_C

num = lambda s: pd.to_numeric(s, errors="coerce")

def to_month(s):
    s2 = s.astype(str).str.strip()
    s2 = s2.where(~s2.str.fullmatch(r"\d{6}"), s2.str[:4] + "-" + s2.str[4:])
    return pd.to_datetime(s2, errors="coerce").dt.to_period("M")

def norm_headcount(raw, c):
    H = raw.get("headcount_timeseries")
    if H is None:
        return None
    df = pd.DataFrame({"employer_id": H[c["hc_employer"]].astype(str), "period": to_month(H[c["hc_period"]]),
                       "headcount": num(H[c["hc_count"]])}).dropna()
    return df.groupby(["employer_id", "period"], as_index=False)["headcount"].sum()

def norm_resign(raw, c):
    R = raw.get("resign_records")
    if R is None:
        return None
    df = pd.DataFrame({"employer_id": R[c["rs_employer"]].astype(str), "period": to_month(R[c["rs_period"]])})
    df["n_resign"] = num(R[c["rs_count"]]).fillna(0) if c.get("rs_count") else 1
    return df.dropna(subset=["period"]).groupby(["employer_id", "period"], as_index=False)["n_resign"].sum()

def norm_payroll(raw, c, hc):
    P = raw.get("payroll_timeseries")
    if P is None:
        return None
    df = pd.DataFrame({"employer_id": P[c["pr_employer"]].astype(str), "period": to_month(P[c["pr_period"]])})
    h = num(P[c["pr_headcount"]]) if c.get("pr_headcount") else None
    df["total"], df["avg_w"], df["weight"] = np.nan, np.nan, np.nan
    if c.get("pr_avg_wage"):
        df["avg_w"] = num(P[c["pr_avg_wage"]]); df["weight"] = h if h is not None else 1.0
        df["hc"] = h if h is not None else np.nan
    elif c.get("pr_total_wage"):
        df["total"] = num(P[c["pr_total_wage"]]); df["hc"] = h if h is not None else np.nan
    else:
        df["avg_w"] = num(P[c["pr_single_wage"]]); df["weight"] = 1.0; df["hc"] = 1.0
    df["umr_p"] = num(P[c["pr_umr"]]) if c.get("pr_umr") else np.nan
    df["wx"] = df["avg_w"] * df["weight"]; df["wt"] = df["weight"].where(df["avg_w"].notna())
    df = df.dropna(subset=["period"]); df = df[df["total"].notna() | df["avg_w"].notna()]
    s_ = lambda x: x.sum(min_count=1)
    a = df.groupby(["employer_id", "period"], as_index=False).agg(
        total=("total", s_), hc=("hc", s_), wx=("wx", s_), wt=("wt", s_), umr_p=("umr_p", "median"))
    if a["hc"].isna().any() and hc is not None:
        a = a.merge(hc.rename(columns={"headcount": "hc_ts"}), on=["employer_id", "period"], how="left")
        a["hc"] = a["hc"].fillna(a["hc_ts"]); a = a.drop(columns="hc_ts")
    a["avg_wage"] = np.where(a["total"].notna(), a["total"] / a["hc"], a["wx"] / a["wt"])
    a = a[a["avg_wage"] > 0].drop(columns=["wx", "wt"]).copy()
    a["log_wage"] = np.log(a["avg_wage"])
    return a

def scale_from_headcount(n):
    out = pd.cut(n, [0, 4, 19, 99, np.inf], labels=["mikro", "kecil", "menengah", "besar"]).astype(str)
    return out.replace("nan", "tidak_diketahui")

def norm_master(raw, c, panel):
    E = raw.get("employer_master")
    if E is None:
        return None
    e = pd.DataFrame({"employer_id": E[c["em_employer"]].astype(str),
                      "sektor": E[c["em_sector"]].astype(str).str.strip(),
                      "wilayah": E[c["em_region"]].astype(str).str.strip()})
    if c.get("em_scale"):
        e["skala"] = E[c["em_scale"]].astype(str).str.strip()
    elif panel is not None:
        e["skala"] = scale_from_headcount(e["employer_id"].map(panel.groupby("employer_id")["hc"].median()))
    else:
        e["skala"] = "tidak_diketahui"
    e["umr_m"] = num(E[c["em_umr"]]) if c.get("em_umr") else np.nan
    return e.drop_duplicates("employer_id", keep="last").reset_index(drop=True)

def norm_remittance(raw, c, panel, hc, cfg=CFG_C):
    RM = raw.get("remittance_timeseries")
    if RM is None:
        return None, None
    df = pd.DataFrame({"employer_id": RM[c["rm_employer"]].astype(str), "period": to_month(RM[c["rm_period"]]),
                       "actual": num(RM[c["rm_actual"]])})
    if c.get("rm_expected"):
        df["expected"] = num(RM[c["rm_expected"]]); source = f"kolom '{c['rm_expected']}'"
        df = df.dropna(subset=["period"]).groupby(["employer_id", "period"], as_index=False)[["expected", "actual"]].sum()
    else:
        # hitung dari upah yang dilaporkan sendiri (payroll) x jumlah karyawan x tarif
        df = df.dropna(subset=["period"]).groupby(["employer_id", "period"], as_index=False)["actual"].sum()
        base = panel[["employer_id", "period", "avg_wage", "hc"]].copy()
        if hc is not None:
            base = base.merge(hc, on=["employer_id", "period"], how="left")
            base["hc"] = base["hc"].fillna(base["headcount"])
        base["expected"] = np.minimum(base["avg_wage"], cfg.WAGE_CAP) * base["hc"] * cfg.CONTRIB_RATE
        df = df.merge(base[["employer_id", "period", "expected"]], on=["employer_id", "period"], how="left")
        source = f"dihitung: min(upah, {cfg.WAGE_CAP:,.0f}) × jumlah karyawan × {cfg.CONTRIB_RATE:.0%}"
    return df.dropna(subset=["expected", "actual"]), source

def prepare(raw, c):
    hc = norm_headcount(raw, c)
    rs = norm_resign(raw, c)
    panel = norm_payroll(raw, c, hc)
    emp = norm_master(raw, c, panel)
    rem, rem_source = norm_remittance(raw, c, panel, hc)
    return dict(hc=hc, rs=rs, panel=panel, emp=emp, rem=rem, rem_source=rem_source)


FLAGGED, NORMAL, EXPLAINED, NOT_CAND, INSUFFICIENT = \
    "FLAGGED", "NORMAL", "EXPLAINED_BY_RESIGN", "NOT_CANDIDATE", "INSUFFICIENT_DATA"
rp = lambda x: ("Rp" + f"{x:,.0f}".replace(",", ".")) if pd.notna(x) else "-"

def module_a(hc, rs, cfg=CFG_A):
    df = hc.merge(rs, on=["employer_id", "period"], how="left") if rs is not None else hc.assign(n_resign=0)
    df["n_resign"] = df["n_resign"].fillna(0)
    df = df.sort_values(["employer_id", "period"]).reset_index(drop=True)
    g = df.groupby("employer_id", sort=False)
    df["n_periods"] = g["period"].transform("count")
    df["prev_hc"] = g["headcount"].shift(1)
    df["delta"] = df["headcount"] - df["prev_hc"]
    drop = (-df["delta"]).clip(lower=0)
    df["explained"] = np.minimum(df["n_resign"], drop)
    df["delta_adj"] = df["delta"] + df["explained"]
    grp = df.groupby("employer_id", sort=False)["delta_adj"]
    W = cfg.ROLLING_WINDOW
    df["mean_delta"] = grp.transform(lambda s: s.shift(1).rolling(W, min_periods=1).mean())
    std_hist = grp.transform(lambda s: s.shift(1).rolling(W, min_periods=2).std())
    df["std_delta"] = np.maximum(std_hist.fillna(0), np.maximum(cfg.STD_FLOOR_ABS, cfg.STD_FLOOR_REL * df["prev_hc"]))
    df["z_raw"] = (df["delta"] - df["mean_delta"]) / df["std_delta"]
    df["z"] = (df["delta_adj"] - df["mean_delta"]) / df["std_delta"]
    df["drop_pct"] = drop / df["prev_hc"]
    df["unexplained_pct"] = (-df["delta_adj"]).clip(lower=0) / df["prev_hc"]
    base = df["mean_delta"].notna() & (df["n_periods"] >= cfg.MIN_PERIODS)
    df["flag_raw"] = base & (df["z_raw"] < -cfg.Z_THRESHOLD) & (df["drop_pct"] >= cfg.MIN_DROP_PCT)
    df["flag"] = base & (df["z"] < -cfg.Z_THRESHOLD) & (df["unexplained_pct"] >= cfg.MIN_DROP_PCT)
    df["suppressed"] = df["flag_raw"] & ~df["flag"]
    df["severity"] = np.where(base & (df["unexplained_pct"] >= cfg.MIN_DROP_PCT), (-df["z"]).clip(lower=0), 0.0)

    rows = []
    for eid, d in df.groupby("employer_id", sort=False):
        n_p = int(d["n_periods"].iloc[0])
        r = dict(employer_id=eid, n_periods=n_p)
        if n_p < cfg.MIN_PERIODS:
            rows.append({**r, "status": INSUFFICIENT, "raw": np.nan}); continue
        w = d.dropna(subset=["z"]).sort_values(["flag", "severity", "z"], ascending=[False, False, True]).iloc[0]
        if d["flag"].any():
            st = FLAGGED
        elif d["suppressed"].any():
            st = EXPLAINED; w = d[d["suppressed"]].sort_values("z_raw").iloc[0]
        else:
            st = NORMAL
        rows.append({**r, "status": st, "raw": float(d["severity"].max()),
                     "n_flagged_periods": int(d["flag"].sum()), "worst_period": str(w["period"]),
                     "hc_before": w["prev_hc"], "hc_after": w["headcount"], "drop": max(-w["delta"], 0),
                     "drop_pct": w["drop_pct"], "resign_recorded": w["n_resign"], "z_score": float(w["z"])})
    out = pd.DataFrame(rows)

    def reason(r):
        if r.status == INSUFFICIENT:
            return f"Riwayat jumlah karyawan baru {r.n_periods} bulan (< {cfg.MIN_PERIODS}); belum bisa dinilai."
        if r.status == FLAGGED:
            rs_txt = (f"hanya {int(r.resign_recorded)} orang tercatat resign" if r.resign_recorded > 0
                      else "tidak ada catatan resign yang cocok")
            return (f"Jumlah karyawan turun {r.drop_pct:.0%} ({int(r.hc_before)}→{int(r.hc_after)} orang) pada "
                    f"{r.worst_period}, {rs_txt}.")
        if r.status == EXPLAINED:
            return (f"Jumlah karyawan turun {int(r.drop)} orang pada {r.worst_period}, sesuai catatan resign resmi "
                    f"({int(r.resign_recorded)} orang) — wajar.")
        return "Pergerakan jumlah karyawan dalam batas wajar."
    out["reason"] = [reason(r) for r in out.itertuples()]
    return out, df


COHORT_LEVELS = [("L0", ["sektor", "wilayah", "skala"]), ("L1", ["sektor", "wilayah"]),
                 ("L2", ["sektor", "skala"]), ("L3", ["sektor"]), ("L4", [])]
LEVEL_NOTE = {"L0": "", "L1": " (skala direlaksasi)", "L2": " (wilayah direlaksasi)",
              "L3": " (hanya sektor)", "L4": " (semua employer)"}

def assign_cohorts(emp, cfg):
    e = emp.copy(); e["cohort_level"] = None; e["cohort_size"] = np.nan
    for lvl, keys in COHORT_LEVELS:
        size = e.groupby(keys)["employer_id"].transform("nunique") if keys else pd.Series(len(e), index=e.index)
        m = e["cohort_level"].isna() & (size >= cfg.MIN_COHORT_SIZE)
        e.loc[m, "cohort_level"] = lvl; e.loc[m, "cohort_size"] = size[m]
    m = e["cohort_level"].isna(); e.loc[m, "cohort_level"] = "L4"; e.loc[m, "cohort_size"] = len(e)
    kd = dict(COHORT_LEVELS)
    e["cohort_key"] = [", ".join(f"{k} {r[k]}" for k in kd[l]) or "semua perusahaan"
                       for l, (_, r) in zip(e["cohort_level"], e.iterrows())]
    return e

def module_b(panel, emp, cfg=CFG_B):
    emp = emp[emp["employer_id"].isin(panel["employer_id"])]
    p = panel.merge(emp, on="employer_id", how="inner")
    p["umr"] = p["umr_p"].fillna(p["umr_m"])
    has_umr = p["umr"].notna().any()
    emp_c = assign_cohorts(emp, cfg)
    p = p.merge(emp_c[["employer_id", "cohort_level", "cohort_size", "cohort_key"]], on="employer_id")
    parts = []
    for lvl, keys in COHORT_LEVELS:
        sub = p[p["cohort_level"] == lvl]
        if sub.empty:
            continue
        gk = keys + ["period"]
        st = (p.groupby(gk)["log_wage"].agg(c_median="median", c_q1=lambda s: s.quantile(.25),
                                            c_q3=lambda s: s.quantile(.75), c_n="count").reset_index())
        parts.append(sub.merge(st, on=gk, how="left"))
    d = pd.concat(parts, ignore_index=True)
    d["c_iqr"] = np.maximum(d["c_q3"] - d["c_q1"], cfg.IQR_FLOOR)
    d["z"] = np.where(d["c_n"] >= cfg.MIN_COHORT_SIZE, (d["log_wage"] - d["c_median"]) / d["c_iqr"], np.nan)
    d["pct_vs_median"] = np.exp(d["log_wage"] - d["c_median"]) - 1
    d["cohort_median_wage"] = np.exp(d["c_median"])
    d["below"] = (d["z"] < -cfg.Z_THRESHOLD).where(d["z"].notna())

    e = d.groupby("employer_id").agg(
        n_periods=("period", "nunique"), n_valid=("z", "count"), n_below=("below", "sum"), z_median=("z", "median"),
        pct_vs_median=("pct_vs_median", "median"), wage_median=("avg_wage", "median"),
        cohort_median_wage=("cohort_median_wage", "median"), umr=("umr", "median"),
        cohort_key=("cohort_key", "first"), cohort_level=("cohort_level", "first"),
        cohort_size=("cohort_size", "first")).reset_index()
    e["frac_below"] = e["n_below"] / e["n_valid"].replace(0, np.nan)
    if has_umr and cfg.UMR_PREFILTER_MULT is not None:
        e["candidate"] = e["umr"].isna() | (e["wage_median"] <= cfg.UMR_PREFILTER_MULT * e["umr"])
    else:
        e["candidate"] = True
    enough = e["n_periods"] >= cfg.MIN_PERIODS
    flag = enough & e["candidate"] & (e["z_median"] < -cfg.Z_THRESHOLD) & (e["frac_below"] >= cfg.MIN_PERSIST)
    e["status"] = np.select([~enough, ~e["candidate"], flag], [INSUFFICIENT, NOT_CAND, FLAGGED], NORMAL)
    e["raw"] = np.where(e["status"].isin([FLAGGED, NORMAL]), (-e["z_median"]).clip(lower=0).fillna(0), 0.0)
    e.loc[e["status"] == INSUFFICIENT, "raw"] = np.nan

    def reason(r):
        cohort = f"{r.cohort_key}{LEVEL_NOTE[r.cohort_level]}, {int(r.cohort_size)} perusahaan"
        if r.status == INSUFFICIENT:
            return f"Data upah baru {r.n_periods} bulan (< {cfg.MIN_PERIODS}); belum bisa dinilai."
        if r.status == NOT_CAND:
            return f"Upah rata-rata {rp(r.wage_median)}/orang di atas {cfg.UMR_PREFILTER_MULT}× UMR; tidak masuk kandidat."
        if r.status == FLAGGED:
            umr = (" Upah juga di bawah UMR, tetapi itu sendiri bukan dasar flag (urusan Disnaker)."
                   if pd.notna(r.umr) and r.wage_median < r.umr else "")
            return (f"Upah dilaporkan {rp(r.wage_median)}/orang, {abs(r.pct_vs_median):.0%} di bawah nilai tengah perusahaan "
                    f"sejenis ({rp(r.cohort_median_wage)}; {cohort}), konsisten di {int(r.n_below)}/{int(r.n_valid)} bulan.{umr}")
        arah = "di bawah" if r.pct_vs_median < 0 else "di atas"
        return f"Upah sejalan dengan perusahaan sejenis ({abs(r.pct_vs_median):.0%} {arah} nilai tengah; {cohort})."
    e["reason"] = [reason(r) for r in e.itertuples()]
    return e, d


rp = lambda x: ("Rp" + f"{x:,.0f}".replace(",", ".")) if pd.notna(x) else "-"

ONE_OFF = "ONE_OFF_GAP"

def module_c(rem, cfg=None):
    """rem: employer_id, period, expected, actual  ->  (tabel per employer, detail per periode)"""
    cfg = cfg or CFG_C
    d = rem.sort_values(["employer_id", "period"]).reset_index(drop=True).copy()
    d["gap"] = d["expected"] - d["actual"]                        # selisih = seharusnya - disetor
    d["gap_pct"] = np.where(d["expected"] > 0, d["gap"] / d["expected"], np.nan)
    d["over_tol"] = (d["gap"] > cfg.TOL_ABS) & (d["gap_pct"] > cfg.TOL_PCT)   # tolerance band
    d["pidx"] = d["period"].dt.year * 12 + d["period"].dt.month
    g = d.groupby("employer_id", sort=False)
    nxt_is_next_month = (g["pidx"].shift(-1) - d["pidx"]) == 1
    nxt_surplus = -g["gap"].shift(-1)                              # kelebihan bayar bulan berikutnya
    d["late_paid"] = (cfg.ALLOW_CATCHUP & d["over_tol"] & nxt_is_next_month
                      & (nxt_surplus >= d["gap"] * (1 - cfg.TOL_PCT)))
    d["is_gap"] = d["over_tol"] & ~d["late_paid"]

    # panjang run berturut-turut
    run_len = np.zeros(len(d), dtype=int)
    prev_e, prev_idx, prev_gap, cur = None, None, False, 0
    for i, (e, p, gp) in enumerate(zip(d["employer_id"], d["pidx"], d["is_gap"])):
        if gp:
            cur = cur + 1 if (e == prev_e and prev_gap and p == prev_idx + 1) else 1
        else:
            cur = 0
        run_len[i] = cur
        prev_e, prev_idx, prev_gap = e, p, gp
    d["run_len"] = run_len

    rows = []
    for eid, x in d.groupby("employer_id", sort=False):
        n_p, gaps = len(x), x[x["is_gap"]]
        longest = int(x["run_len"].max())
        r = dict(employer_id=eid, n_periods=n_p, n_gap_periods=len(gaps), longest_run=longest,
                 n_late_paid=int(x["late_paid"].sum()),
                 total_expected=float(x["expected"].sum()), total_actual=float(x["actual"].sum()),
                 total_shortfall=float(gaps["gap"].sum()),
                 median_gap_pct=float(gaps["gap_pct"].median()) if len(gaps) else 0.0,
                 run_start=None, run_end=None, first_gap_period=str(gaps["period"].min()) if len(gaps) else None)
        r["cum_shortfall_pct"] = r["total_shortfall"] / r["total_expected"] if r["total_expected"] > 0 else np.nan
        if longest > 0:
            end_i = x["run_len"].idxmax()
            r["run_end"] = str(x.loc[end_i, "period"])
            r["run_start"] = str(x.loc[end_i - longest + 1, "period"])
        if n_p < cfg.MIN_PERIODS:
            r.update(status=INSUFFICIENT, raw=np.nan)
        elif longest >= cfg.MIN_CONSECUTIVE:
            r.update(status=FLAGGED, raw=r["median_gap_pct"])
        elif len(gaps):
            r.update(status=ONE_OFF, raw=float(gaps["gap_pct"].max()))
        else:
            r.update(status=NORMAL, raw=0.0)
        rows.append(r)
    e = pd.DataFrame(rows)

    def reason(r):
        late = (f" {r.n_late_paid} kali telat setor tapi dilunasi bulan berikutnya (dianggap wajar)."
                if r.n_late_paid else "")
        if r.status == INSUFFICIENT:
            return f"Data setoran baru {r.n_periods} bulan; belum bisa dinilai."
        if r.status == FLAGGED:
            extra = (f" Ada {r.n_gap_periods - r.longest_run} bulan lain yang juga kurang setor."
                     if r.n_gap_periods > r.longest_run else "")
            return (f"Setoran iuran rata-rata {r.median_gap_pct:.0%} di bawah yang seharusnya selama "
                    f"{r.longest_run} bulan berturut-turut ({r.run_start} s/d {r.run_end}); "
                    f"total kekurangan {rp(r.total_shortfall)}.{extra}{late}")
        if r.status == ONE_OFF:
            return (f"Kurang setor pada {r.first_gap_period}, tetapi tidak berulang berturut-turut — "
                    f"dianggap wajar.{late}")
        return (f"Setoran sesuai dengan yang seharusnya (selisih dalam toleransi "
                f"{cfg.TOL_PCT:.0%} / {rp(cfg.TOL_ABS)}).{late}")
    e["reason"] = [reason(r) for r in e.itertuples()]
    return e, d
