"""Jalankan engine end-to-end dari database: data mentah -> Module A/B/C -> composite -> payload skor."""
import pandas as pd

from .anomaly import evaluate_if, run_isolation_forest
from .composite import build_payload, composite, explain
from .evaluation import build_truth, evaluate
from .forecast import run_early_warning
from .modules import module_a, module_b, module_c, prepare

# Skema tetap (menggantikan auto-detect kolom di notebook)
COLS = dict(
    hc_employer="employer_id", hc_period="periode", hc_count="jumlah_peserta_aktif",
    rs_employer="employer_id", rs_period="periode", rs_count="jumlah_keluar",
    pr_employer="employer_id", pr_period="periode", pr_umr=None, pr_avg_wage="rata2_DPI",
    pr_total_wage=None, pr_single_wage=None, pr_headcount=None,
    em_employer="employer_id", em_sector="sektor_usaha", em_region="wilayah", em_umr="umr", em_scale="skala",
    rm_employer="employer_id", rm_period="periode", rm_expected="expected_contribution", rm_actual="actual_remittance",
)


def load_raw(con) -> dict:
    q = lambda sql: pd.read_sql_query(sql, con)
    raw = {name: q(f"SELECT * FROM {name}") for name in
           ("headcount_timeseries", "resign_records", "payroll_timeseries", "remittance_timeseries")}
    raw["employer_master"] = q("SELECT e.employer_id, e.sektor AS sektor_usaha, e.wilayah, e.skala, w.umr_rp AS umr FROM employers e "
                               "LEFT JOIN wilayah w ON w.nama = e.wilayah WHERE e.status = 'Aktif'")
    raw["ground_truth"] = q("SELECT employer_id, anomaly_type, detail FROM ground_truth")
    return raw


def run(con) -> dict:
    """Mengembalikan payload {meta, companies} — bentuk sama dengan output_scores.json."""
    raw = load_raw(con)
    if raw["headcount_timeseries"].empty:
        raise ValueError("Belum ada data deret waktu. Jalankan: python -m backend.migrate_csv <folder_csv>")
    data = prepare(raw, COLS)
    res_a, _ = module_a(data["hc"], data["rs"])
    res_b, _ = module_b(data["panel"], data["emp"])
    res_c, _ = module_c(data["rem"])
    comp, mods = composite({"A": res_a, "B": res_b, "C": res_c}, data["emp"])
    comp["explanation"] = [explain(r, mods) for r in comp.itertuples()]
    payload = build_payload(comp, mods, data)
    iff = run_isolation_forest(data)                       # sinyal tambahan: TIDAK mengubah composite / band
    by_id = iff.set_index("employer_id")
    ew = run_early_warning(data["rem"]).set_index("employer_id")
    for c in payload["companies"]:
        c["extra_signals"] = {}
        if c["id"] in by_id.index:
            r = by_id.loc[c["id"]]
            c["extra_signals"]["isolation_forest"] = {"score": float(r["if_score"]), "flagged": bool(r["if_flag"]), "reasons": r["reasons"]}
        if c["id"] in ew.index and ew.loc[c["id"], "ew_flag"] and c["status"].get("C") != "FLAGGED":  # bila C sudah flag, tak perlu peringatan dini
            c["extra_signals"]["remittance_early_warning"] = {"flagged": True, "last_gap": round(float(ew.loc[c["id"], "ew_last_gap"]), 4), "text": ew.loc[c["id"], "ew_text"]}
    truth = build_truth(raw["ground_truth"])
    if truth is not None:
        table, at_k, merged = evaluate(comp, truth)
        payload["meta"]["evaluation"] = {"table": table.where(table.notna(), None).to_dict("records"), "precision_at_k": at_k,
                                         "isolation_forest": evaluate_if(iff, merged)}
    return payload
