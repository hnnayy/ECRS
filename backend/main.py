"""ECRS API — engine, data, dan model berjalan di backend; semua data tersimpan di SQLite."""
import json
import os
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from collections import Counter

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles

from . import model as ml
from . import summary as case_summary

from .database import ROOT, db
from .engine.pipeline import run as run_engine
from .jobs import MODEL_CHECK_S, RESCORE_DEBOUNCE_S, Scheduler
from .store import load_scores, save_scores

# State hasil engine (diisi dari tabel `scores`; diperbarui in-place oleh reload_scores)
DATA: dict = {"meta": {}}
COMPANIES: list[dict] = []
BY_ID: dict[str, dict] = {}
FEATURE_MATRIX: dict[str, list[float]] = {}


def reload_scores() -> None:
    global COMPANIES, BY_ID, FEATURE_MATRIX
    with db() as con:
        meta, companies = load_scores(con)
    by_id = {c["id"]: c for c in companies}
    features = {c["id"]: ml.featurize(c) for c in companies}
    DATA["meta"] = meta
    COMPANIES, BY_ID, FEATURE_MATRIX = companies, by_id, features  # penukaran referensi = atomik untuk pembaca


reload_scores()

AUTO_INCLUDE_SIM = os.environ.get("ECRS_AUTO_TRAIN_SIMULATED") == "1"   # hanya untuk demo; default: label pemeriksa asli saja
RETRAIN_EVERY = int(os.environ.get("ECRS_RETRAIN_EVERY", 10))            # latih ulang tiap +N label hasil akhir baru
PROMOTE_MARGIN = 0.01                                                    # model baru dipakai hanya jika AUC >= AUC aturan - margin
WORK_LOCK = threading.Lock()                                             # rescore & pelatihan tidak boleh bertumpuk

STATE: dict = {
    "scoring": {"dirty_since": None, "running": False, "last_run": None, "last_error": None},
    "model": {"running": False, "last_check": None, "last_action": None, "waiting_for": None, "last_error": None},
}


def mark_dirty() -> None:
    """Tandai data berubah; job latar belakang akan menghitung ulang skor sesaat lagi (debounce)."""
    STATE["scoring"]["dirty_since"] = time.time()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not COMPANIES:
        with db() as con:
            if con.execute("SELECT 1 FROM headcount_timeseries LIMIT 1").fetchone():
                mark_dirty()
    sched = Scheduler(STATE, do_rescore, auto_train_if_due)
    sched.start()
    yield
    sched.stop()


app = FastAPI(title="ECRS Risk API", version="0.2.0", lifespan=lifespan,
              description="Skor risiko kontribusi pemberi kerja (data sintetis, bukan data BPJS asli).")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "null"],
                   allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok", "companies": len(COMPANIES)}


@app.get("/api/meta")
def meta():
    return DATA["meta"]


@app.get("/api/filters")
def filters():
    return {key: sorted({c[key] for c in COMPANIES if c.get(key)}) for key in ("sektor", "wilayah", "skala", "band")}


@app.get("/api/summary")
def summary():
    return {
        "total": len(COMPANIES),
        "by_band": dict(Counter(c["band"] for c in COMPANIES)),
        "by_module_flagged": dict(Counter(m for c in COMPANIES for m in c["modules_flagged"])),
    }


@app.get("/api/companies")
def companies(sektor: str | None = None, wilayah: str | None = None, band: str | None = None,
              q: str | None = Query(None, description="cari id employer"),
              flagged: str | None = Query(None, pattern="^[ABC]$", description="hanya yang di-flag modul ini"),
              sort: str = Query("rule", pattern="^(rule|learned)$"),
              limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    rows = [c for c in COMPANIES
            if (not sektor or c["sektor"] == sektor) and (not wilayah or c["wilayah"] == wilayah)
            and (not band or c["band"] == band) and (not flagged or flagged in c["modules_flagged"]) and (not q or q.lower() in c["id"].lower())]
    if sort == "learned" and ACTIVE["model"]:
        rows.sort(key=lambda c: -ACTIVE["scores"].get(c["id"], 0.0))
    else:
        rows.sort(key=lambda c: (c["rank"] is None, c["rank"]))
    slim = [{k: c[k] for k in ("id", "rank", "sektor", "wilayah", "skala", "composite_score", "band",
                               "band_code", "coverage", "modules_flagged", "scores", "recommendation")}
            | {"summary": c["explanation"]["summary"], "learned_score": ACTIVE["scores"].get(c["id"])}
            for c in rows[offset:offset + limit]]
    return {"total": len(rows), "limit": limit, "offset": offset, "items": slim, "model_active": ACTIVE["model"] is not None}


@app.get("/api/companies/{company_id}")
def company(company_id: str):
    if company_id not in BY_ID:
        raise HTTPException(404, f"{company_id} tidak ditemukan")
    learned = None
    if ACTIVE["model"]:
        learned = {"score": ACTIVE["scores"][company_id], "version": ACTIVE["version"]["id"],
                   "contributions": ml.contributions(ACTIVE["model"], FEATURE_MATRIX[company_id])}
    return BY_ID[company_id] | {"learned": learned}


# ---------- deret waktu, radar (prototype HTML), & input data ----------
N_HC, N_RECON, N_WAGE = 6, 4, 6
BAND_MAP = {"Tinggi": "critical", "Sedang": "serious", "Rendah": "good"}


def _q(con: sqlite3.Connection, sql: str, *params) -> pd.DataFrame:
    return pd.read_sql_query(sql, con, params=params)


def _pts(v):
    return 0 if v is None else round(v * 100)


def to_radar(c: dict, hc: list, wage: float, rem: pd.DataFrame | None, peers: pd.Series) -> dict:
    cid, status = c["id"], c["status"]
    drivers = {d["module"]: d for d in c["explanation"]["drivers"]}
    insufficient = c["band"] == "Belum bisa dinilai"
    out = {
        "id": cid, "name": f"Employer {cid}", "sektor": c["sektor"], "wilayah": c["wilayah"], "skala": c["skala"],
        "status": "Aktif", "api": True, "rank": c["rank"],
        "B": _pts(c["scores"]["B"]), "C": _pts(c["scores"]["C"]),
        "composite": None if insufficient else round(c["composite_score"] * 100, 1),
        "riskBand": "insufficient" if insufficient else BAND_MAP.get(c["band"], "good"),
        "insufficient": insufficient, "headcount": hc, "resignMatch": status["A"] != "FLAGGED",
        "wageOwn": round(wage, 2), "peerMin": round(float(peers.min()), 2), "peerMedian": round(float(peers.median()), 2),
        "peerMax": round(float(peers.max()), 2),
        "reconPeriods": [] if rem is None else rem.periode.str[-2:].tolist(),
        "expected": [] if rem is None else (rem.expected_contribution / 1e6).round(1).tolist(),
        "actual": [] if rem is None else (rem.actual_remittance / 1e6).round(1).tolist(),
        "summary": c["explanation"]["summary"],
    }
    if not insufficient:
        out["A"] = _pts(c["scores"]["A"])
    note = (drivers.get("A") or {}).get("text")
    if note and (insufficient or status["A"] in ("FLAGGED", "EXPLAINED_BY_RESIGN")):
        out["noteOverride"] = note
    return out


@app.get("/api/radar")
def radar(limit: int = Query(150, ge=1, le=2000)):
    """Employer berperingkat teratas dalam bentuk yang dipakai dashboard HTML (prototype lama)."""
    rows = sorted(COMPANIES, key=lambda c: (c["rank"] is None, c["rank"]))[:limit]
    ids = [c["id"] for c in rows]
    ph = ",".join("?" * len(ids))
    with db() as con:
        hc = _q(con, f"SELECT * FROM headcount_timeseries WHERE employer_id IN ({ph}) ORDER BY periode", *ids)
        rem = _q(con, f"SELECT * FROM remittance_timeseries WHERE employer_id IN ({ph}) ORDER BY periode", *ids)
        pay = _q(con, "SELECT p.employer_id, p.periode, p.rata2_DPI, e.sektor, e.wilayah, e.skala FROM payroll_timeseries p "
                      "JOIN employers e ON e.employer_id = p.employer_id ORDER BY p.periode")
    wage = pay.groupby("employer_id").rata2_DPI.apply(lambda x: x.tail(N_WAGE).mean() / 1e6)
    cohort = pay.drop_duplicates("employer_id").set_index("employer_id")[["sektor", "wilayah", "skala"]].apply(tuple, axis=1)
    peers_by = wage.groupby(cohort.reindex(wage.index)).apply(list).to_dict()
    hc_by = {k: g.jumlah_peserta_aktif.tail(N_HC).tolist() for k, g in hc.groupby("employer_id")}
    rem_by = {k: g.tail(N_RECON) for k, g in rem.groupby("employer_id")}
    out = []
    for c in rows:
        w = float(wage.get(c["id"], 0))
        peers = pd.Series(peers_by.get((c["sektor"], c["wilayah"], c["skala"]), [w]))
        out.append(to_radar(c, hc_by.get(c["id"], []), w, rem_by.get(c["id"]), peers))
    return {"meta": DATA["meta"], "total": len(COMPANIES), "companies": out}


@app.get("/api/companies/{company_id}/case-summary")
def case_summary_endpoint(company_id: str, llm: bool = True):
    """Ringkasan kasus: templat instan (llm=false) atau dirapikan LLM bila dikonfigurasi (llm=true)."""
    c = BY_ID.get(company_id)
    if not c:
        raise HTTPException(404, f"{company_id} tidak ditemukan")
    return case_summary.build(c, len(COMPANIES), DATA["meta"].get("generated_at"), use_llm=llm)


@app.get("/api/companies/{company_id}/series")
def series(company_id: str):
    """Deret waktu per periode untuk grafik modul A, B, dan C."""
    c = BY_ID.get(company_id)
    if not c:
        raise HTTPException(404, f"{company_id} tidak ditemukan")
    with db() as con:
        hc = _q(con, "SELECT periode, jumlah_peserta_aktif AS headcount FROM headcount_timeseries WHERE employer_id = ? ORDER BY periode", company_id)
        resign = _q(con, "SELECT periode, jumlah_keluar FROM resign_records WHERE employer_id = ?", company_id).set_index("periode").jumlah_keluar
        pay = _q(con, "SELECT periode, rata2_DPI FROM payroll_timeseries WHERE employer_id = ? ORDER BY periode", company_id)
        rem = _q(con, "SELECT * FROM remittance_timeseries WHERE employer_id = ? ORDER BY periode", company_id)
        cohort = _q(con, "SELECT p.periode, p.rata2_DPI FROM payroll_timeseries p JOIN employers e ON e.employer_id = p.employer_id "
                         "WHERE e.sektor = ? AND e.wilayah = ? AND e.skala = ?", c["sektor"], c["wilayah"], c["skala"])
    cs = cohort.groupby("periode").rata2_DPI.quantile([0.25, 0.5, 0.75]).unstack()
    jt = lambda x: round(float(x) / 1e6, 3)
    at = lambda p, q: jt(cs.loc[p, q]) if p in cs.index else None
    return {
        "A": [{"periode": r.periode, "headcount": int(r.headcount), "resign": int(resign.get(r.periode, 0))} for r in hc.itertuples()],
        "B": [{"periode": r.periode, "own": jt(r.rata2_DPI), "q1": at(r.periode, 0.25), "median": at(r.periode, 0.5),
               "q3": at(r.periode, 0.75)} for r in pay.itertuples()],
        "C": [{"periode": r.periode, "expected": jt(r.expected_contribution), "actual": jt(r.actual_remittance)} for r in rem.itertuples()],
    }


class PeriodIn(BaseModel):
    employer_id: str
    periode: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    jumlah_peserta_aktif: int = Field(ge=0)
    jumlah_keluar: int = Field(default=0, ge=0)
    rata2_DPI: float = Field(gt=0, description="rata-rata upah dilaporkan per peserta (Rp)")
    expected_contribution: float = Field(ge=0, description="iuran seharusnya (Rp)")
    actual_remittance: float = Field(ge=0, description="iuran yang disetor (Rp)")


@app.get("/api/timeseries/{employer_id}")
def get_timeseries(employer_id: str, limit: int = Query(12, ge=1, le=60)):
    with db() as con:
        df = _q(con, """SELECT h.periode, h.jumlah_peserta_aktif, COALESCE(r.jumlah_keluar, 0) AS jumlah_keluar, p.rata2_DPI,
                        m.expected_contribution, m.actual_remittance FROM headcount_timeseries h
                        LEFT JOIN resign_records r USING (employer_id, periode) LEFT JOIN payroll_timeseries p USING (employer_id, periode)
                        LEFT JOIN remittance_timeseries m USING (employer_id, periode)
                        WHERE h.employer_id = ? ORDER BY h.periode DESC LIMIT ?""", employer_id, limit)
    return df.astype(object).where(df.notna(), None).to_dict("records")


@app.post("/api/timeseries", status_code=201)
def upsert_period(d: PeriodIn):
    """Catat/ubah data satu periode. Skor dihitung ulang otomatis oleh job latar belakang."""
    with db() as con:
        if not con.execute("SELECT 1 FROM employers WHERE employer_id = ?", [d.employer_id]).fetchone():
            raise HTTPException(404, f"{d.employer_id} tidak ada di master badan usaha")
        con.execute("INSERT OR REPLACE INTO headcount_timeseries VALUES (?,?,?)", [d.employer_id, d.periode, d.jumlah_peserta_aktif])
        con.execute("INSERT OR REPLACE INTO resign_records VALUES (?,?,?)", [d.employer_id, d.periode, d.jumlah_keluar])
        con.execute("INSERT OR REPLACE INTO payroll_timeseries VALUES (?,?,?)", [d.employer_id, d.periode, d.rata2_DPI])
        con.execute("INSERT OR REPLACE INTO remittance_timeseries VALUES (?,?,?,?)",
                    [d.employer_id, d.periode, d.expected_contribution, d.actual_remittance])
    mark_dirty()
    return d


def do_rescore() -> None:
    """Jalankan ulang engine (Module A/B/C + composite) atas seluruh data di database. Dipanggil job latar belakang / CLI."""
    with WORK_LOCK:
        sc = STATE["scoring"]
        sc["dirty_since"], sc["running"] = None, True  # perubahan yang masuk saat proses berjalan akan menandai dirty lagi
        try:
            with db() as con:
                save_scores(con, run_engine(con))
            reload_scores()
            _load_active()
            sc["last_run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        except ValueError as e:  # belum ada data; bukan error sistem
            sc["last_error"] = str(e)
        finally:
            sc["running"] = False


@app.get("/api/evaluation")
def evaluation():
    """Evaluasi engine vs ground truth sintetis (recall/FPR per modul, precision@K)."""
    ev = DATA["meta"].get("evaluation")
    if not ev:
        raise HTTPException(404, "ground truth tidak tersedia")
    return ev


# ---------- keputusan investigasi (SQLite) ----------

class DecisionIn(BaseModel):
    company_id: str
    decision: str = Field(pattern="^(investigasi|tutup|terbukti|tidak_terbukti)$")
    note: str = Field(min_length=3, max_length=500)


@app.get("/api/decisions")
def list_decisions(company_id: str | None = None, limit: int = Query(200, ge=1, le=1000)):
    with db() as con:
        q = "SELECT * FROM decisions" + (" WHERE company_id = ?" if company_id else "") + " ORDER BY id DESC LIMIT ?"
        args = ([company_id] if company_id else []) + [limit]
        return [dict(r) for r in con.execute(q, args)]


@app.post("/api/decisions", status_code=201)
def add_decision(d: DecisionIn):
    if d.company_id not in BY_ID:
        raise HTTPException(404, f"{d.company_id} tidak ditemukan")
    row = (d.company_id, d.decision, d.note.strip(), "Supervisor Anti-Fraud", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    with db() as con:
        cur = con.execute("INSERT INTO decisions (company_id, decision, note, officer, created_at) VALUES (?,?,?,?,?)", row)
        return dict(con.execute("SELECT * FROM decisions WHERE id = ?", [cur.lastrowid]).fetchone())


# ---------- master data (CRUD, SQLite) ----------
SKALA = ("Kecil", "Menengah", "Besar")


class EmployerIn(BaseModel):
    nama: str = Field(default="", max_length=120)
    sektor: str
    wilayah: str
    skala: str = Field(pattern="^(Kecil|Menengah|Besar)$")
    status: str = Field(default="Aktif", pattern="^(Aktif|Non-aktif)$")
    tanggal_registrasi: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class NameIn(BaseModel):
    nama: str = Field(min_length=2, max_length=80)
    umr_rp: float | None = Field(default=None, ge=0, le=100_000_000, description="UMR dalam Rupiah")


def _check_refs(con: sqlite3.Connection, e: EmployerIn) -> None:
    if not con.execute("SELECT 1 FROM sektor WHERE nama = ?", [e.sektor]).fetchone():
        raise HTTPException(422, f"sektor '{e.sektor}' tidak ada di master")
    if not con.execute("SELECT 1 FROM wilayah WHERE nama = ?", [e.wilayah]).fetchone():
        raise HTTPException(422, f"wilayah '{e.wilayah}' tidak ada di master")


@app.get("/api/employers")
def employers(q: str | None = None, limit: int = Query(25, ge=1, le=500), offset: int = Query(0, ge=0)):
    like = f"%{q or ''}%"
    with db() as con:
        where = "WHERE employer_id LIKE ? OR nama LIKE ?"
        total = con.execute(f"SELECT COUNT(*) FROM employers {where}", [like, like]).fetchone()[0]
        rows = con.execute(f"SELECT * FROM employers {where} ORDER BY employer_id LIMIT ? OFFSET ?", [like, like, limit, offset])
        return {"total": total, "items": [dict(r) | {"scored": r["employer_id"] in BY_ID} for r in rows]}


@app.post("/api/employers", status_code=201)
def create_employer(e: EmployerIn):
    with db() as con:
        _check_refs(con, e)
        n = con.execute("SELECT MAX(CAST(SUBSTR(employer_id, 5) AS INTEGER)) FROM employers").fetchone()[0] or 0
        eid = f"EMP-{n + 1:04d}"
        con.execute("INSERT INTO employers VALUES (?,?,?,?,?,?,?)",
                    [eid, e.nama.strip(), e.sektor, e.wilayah, e.skala, e.status, e.tanggal_registrasi])
        mark_dirty()
        return dict(con.execute("SELECT * FROM employers WHERE employer_id = ?", [eid]).fetchone()) | {"scored": False}


@app.put("/api/employers/{employer_id}")
def update_employer(employer_id: str, e: EmployerIn):
    with db() as con:
        _check_refs(con, e)
        cur = con.execute("UPDATE employers SET nama=?, sektor=?, wilayah=?, skala=?, status=?, tanggal_registrasi=? WHERE employer_id=?",
                          [e.nama.strip(), e.sektor, e.wilayah, e.skala, e.status, e.tanggal_registrasi, employer_id])
        if not cur.rowcount:
            raise HTTPException(404, f"{employer_id} tidak ditemukan")
        mark_dirty()
        return dict(con.execute("SELECT * FROM employers WHERE employer_id = ?", [employer_id]).fetchone()) | {"scored": employer_id in BY_ID}


@app.delete("/api/employers/{employer_id}", status_code=204)
def delete_employer(employer_id: str):
    if employer_id in BY_ID:
        raise HTTPException(409, "Employer ini punya skor di batch Wave 2. Ubah statusnya menjadi Non-aktif, jangan dihapus.")
    with db() as con:
        if not con.execute("DELETE FROM employers WHERE employer_id = ?", [employer_id]).rowcount:
            raise HTTPException(404, f"{employer_id} tidak ditemukan")
        mark_dirty()


@app.get("/api/reference")
def reference():
    with db() as con:
        wil = con.execute("""SELECT w.nama, w.umr_rp, COUNT(e.employer_id) AS employer FROM wilayah w
                             LEFT JOIN employers e ON e.wilayah = w.nama GROUP BY w.nama ORDER BY w.nama""")
        sek = con.execute("""SELECT s.nama, COUNT(e.employer_id) AS employer FROM sektor s
                             LEFT JOIN employers e ON e.sektor = s.nama GROUP BY s.nama ORDER BY s.nama""")
        return {"wilayah": [dict(r) for r in wil], "sektor": [dict(r) for r in sek],
                "skala": list(SKALA)}


def _ref_routes(table: str, has_umr: bool) -> None:
    col = "wilayah" if table == "wilayah" else "sektor"

    def create(b: NameIn):
        with db() as con:
            try:
                if has_umr:
                    con.execute("INSERT INTO wilayah VALUES (?,?)", [b.nama.strip(), b.umr_rp])
                else:
                    con.execute("INSERT INTO sektor VALUES (?)", [b.nama.strip()])
            except sqlite3.IntegrityError:
                raise HTTPException(409, f"'{b.nama}' sudah ada")
        return {"nama": b.nama.strip(), "umr_rp": b.umr_rp if has_umr else None, "employer": 0}

    def update(nama: str, b: NameIn):
        new = b.nama.strip()
        with db() as con:
            if new != nama and con.execute(f"SELECT 1 FROM {table} WHERE nama = ?", [new]).fetchone():
                raise HTTPException(409, f"'{new}' sudah ada")
            sql = "UPDATE wilayah SET nama=?, umr_rp=? WHERE nama=?" if has_umr else "UPDATE sektor SET nama=? WHERE nama=?"
            args = [new, b.umr_rp, nama] if has_umr else [new, nama]
            if not con.execute(sql, args).rowcount:
                raise HTTPException(404, f"'{nama}' tidak ditemukan")
            con.execute(f"UPDATE employers SET {col} = ? WHERE {col} = ?", [new, nama])
            mark_dirty()
        return {"nama": new, "umr_rp": b.umr_rp if has_umr else None}

    def delete(nama: str):
        with db() as con:
            n = con.execute(f"SELECT COUNT(*) FROM employers WHERE {col} = ?", [nama]).fetchone()[0]
            if n:
                raise HTTPException(409, f"Masih dipakai {n} employer; pindahkan atau ubah dulu.")
            if not con.execute(f"DELETE FROM {table} WHERE nama = ?", [nama]).rowcount:
                raise HTTPException(404, f"'{nama}' tidak ditemukan")

    app.post(f"/api/{table}", status_code=201)(create)
    app.put(f"/api/{table}/{{nama}}")(update)
    app.delete(f"/api/{table}/{{nama}}", status_code=204)(delete)


_ref_routes("wilayah", True)
_ref_routes("sektor", False)


# ---------- feedback loop & model terlatih (tingkat 3) ----------
MIN_LABELS, MIN_PER_CLASS = 20, 5
ACTIVE: dict = {"version": None, "model": None, "scores": {}}


def _labels(con: sqlite3.Connection, include_simulated: bool) -> list[sqlite3.Row]:
    """Label = keputusan hasil akhir terbaru per employer (terbukti=1, tidak_terbukti=0)."""
    src = "" if include_simulated else "AND source != 'simulasi'"
    return con.execute(f"""SELECT d.company_id, d.decision, d.source FROM decisions d JOIN (
        SELECT company_id, MAX(id) AS mid FROM decisions WHERE decision IN ('terbukti','tidak_terbukti') {src}
        GROUP BY company_id) m ON d.id = m.mid""").fetchall()


def _label_counts(con: sqlite3.Connection) -> dict:
    out = {}
    for name, inc in (("pemeriksa", False), ("dengan_simulasi", True)):
        rows = _labels(con, inc)
        pos = sum(r["decision"] == "terbukti" for r in rows)
        out[name] = {"total": len(rows), "terbukti": pos, "tidak_terbukti": len(rows) - pos}
    return out


def _activate(row: sqlite3.Row | None) -> None:
    if row is None or not FEATURE_MATRIX:
        ACTIVE.update(version=_version_dict(row) if row else None, model=json.loads(row["weights"]) if row else None, scores={})
        return
    model = json.loads(row["weights"])
    ids = list(FEATURE_MATRIX)
    probs = ml.predict(model, np.array([FEATURE_MATRIX[i] for i in ids]))
    ACTIVE.update(version=_version_dict(row), model=model, scores={i: round(float(p), 4) for i, p in zip(ids, probs)})


def _version_dict(r: sqlite3.Row) -> dict:
    return {"id": r["id"], "created_at": r["created_at"], "n_labels": r["n_labels"], "n_pos": r["n_pos"], "n_neg": r["n_neg"],
            "uses_simulated": bool(r["uses_simulated"]), "active": bool(r["active"]), "metrics": json.loads(r["metrics"])}


def _load_active() -> None:
    with db() as con:
        _activate(con.execute("SELECT * FROM model_versions WHERE active = 1 ORDER BY id DESC LIMIT 1").fetchone())


_load_active()


SIM_POSITIVE = {"REMITTANCE_GAP", "UNDER_REPORTING_WAGE", "PDUK"}


def simulate_labels(top: int = 150, noise: float = 0.08, seed: int = 7) -> dict:
    """Label DEMO: turunan ground_truth sintetis, hanya untuk employer peringkat teratas (meniru bias seleksi)."""
    import random
    with db() as con:
        truth = _q(con, "SELECT employer_id, anomaly_type FROM ground_truth").set_index("employer_id").anomaly_type
    rng = random.Random(seed)
    reviewed = sorted((c for c in BY_ID.values() if c["rank"] is not None), key=lambda c: c["rank"])[:top]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pos = 0
    with db() as con:
        con.execute("DELETE FROM decisions WHERE source = 'simulasi'")
        for c in reviewed:
            fraud = truth.get(c["id"]) in SIM_POSITIVE
            if rng.random() < noise:
                fraud = not fraud
            pos += fraud
            con.execute("INSERT INTO decisions (company_id, decision, note, officer, created_at, source) VALUES (?,?,?,?,?,'simulasi')",
                        [c["id"], "terbukti" if fraud else "tidak_terbukti", "Label simulasi (demo)", "Simulasi", now])
    return {"total": len(reviewed), "terbukti": pos, "tidak_terbukti": len(reviewed) - pos}


def purge_simulated() -> int:
    with db() as con:
        return con.execute("DELETE FROM decisions WHERE source = 'simulasi'").rowcount


@app.get("/api/model")
def model_info():
    with db() as con:
        versions = [_version_dict(r) for r in con.execute("SELECT * FROM model_versions ORDER BY id DESC LIMIT 20")]
        weights = None
        if ACTIVE["model"]:
            m = ACTIVE["model"]
            weights = sorted(({"feature": n, "label": ml.LABELS[n], "weight": round(w, 3)} for n, w in zip(ml.NAMES, m["w"])),
                             key=lambda x: -abs(x["weight"]))
        return {"labels": _label_counts(con), "min_labels": MIN_LABELS, "min_per_class": MIN_PER_CLASS,
                "active": ACTIVE["version"], "weights": weights, "versions": versions}


def train_model_now(include_simulated: bool = False) -> dict:
    """Latih model dari label hasil akhir. Versi baru hanya DIPAKAI jika tidak lebih buruk dari skor aturan (champion/challenger)."""
    with WORK_LOCK, db() as con:
        rows = [r for r in _labels(con, include_simulated) if r["company_id"] in BY_ID]
        y = np.array([1.0 if r["decision"] == "terbukti" else 0.0 for r in rows])
        n_pos, n_neg = int(y.sum()), int(len(y) - y.sum())
        if len(y) < MIN_LABELS or min(n_pos, n_neg) < MIN_PER_CLASS:
            raise ValueError(f"Label belum cukup: {len(y)} label ({n_pos} terbukti, {n_neg} tidak terbukti)")
        X = np.array([FEATURE_MATRIX[r["company_id"]] for r in rows])
        baseline = np.array([BY_ID[r["company_id"]]["composite_score"] or 0.0 for r in rows])
        metrics = ml.cross_validate(X, y, baseline, k=min(5, n_pos, n_neg))
        promoted = metrics["auc_model"] is not None and metrics["auc_rules"] is not None \
            and metrics["auc_model"] >= metrics["auc_rules"] - PROMOTE_MARGIN
        metrics["promoted"] = bool(promoted)
        model = ml.fit(X, y)
        if promoted:
            con.execute("UPDATE model_versions SET active = 0")
        cur = con.execute("INSERT INTO model_versions (created_at, n_labels, n_pos, n_neg, uses_simulated, metrics, weights, active) "
                          "VALUES (?,?,?,?,?,?,?,?)", [datetime.now(timezone.utc).isoformat(timespec="seconds"), len(y), n_pos, n_neg,
                                                       int(any(r["source"] == "simulasi" for r in rows)), json.dumps(metrics),
                                                       json.dumps(model), int(promoted)])
        row = con.execute("SELECT * FROM model_versions WHERE id = ?", [cur.lastrowid]).fetchone()
        if promoted:
            _activate(row)
        return _version_dict(row)


def auto_train_if_due() -> None:
    """Dipanggil job berkala: latih ulang bila label hasil akhir cukup dan sudah ada +RETRAIN_EVERY label baru."""
    ms = STATE["model"]
    ms["last_check"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db() as con:
        rows = [r for r in _labels(con, AUTO_INCLUDE_SIM) if r["company_id"] in BY_ID]
        last = con.execute("SELECT n_labels FROM model_versions WHERE uses_simulated = ? ORDER BY id DESC LIMIT 1", [int(AUTO_INCLUDE_SIM)]).fetchone()
    n, pos = len(rows), sum(r["decision"] == "terbukti" for r in rows)
    neg = n - pos
    if n < MIN_LABELS or min(pos, neg) < MIN_PER_CLASS:
        ms["waiting_for"] = f"label hasil akhir: {n}/{MIN_LABELS} (terbukti {pos}, tidak terbukti {neg}; min. {MIN_PER_CLASS} per kelas)"
        return
    if last and n - last["n_labels"] < RETRAIN_EVERY:
        ms["waiting_for"] = f"{RETRAIN_EVERY - (n - last['n_labels'])} label baru lagi untuk pelatihan ulang"
        return
    ms["running"] = True
    try:
        v = train_model_now(AUTO_INCLUDE_SIM)
        ms["last_action"] = f"{v['created_at']}: v{v['id']} dilatih dari {v['n_labels']} label — " + \
            ("dipakai" if v["metrics"].get("promoted") else "ditolak (lebih buruk dari skor aturan)")
        ms["waiting_for"] = None
    finally:
        ms["running"] = False


def set_active_version(version_id: int | None) -> None:
    """Hanya untuk CLI developer (scripts.admin)."""
    with db() as con:
        if version_id is None:
            con.execute("UPDATE model_versions SET active = 0")
            _activate(None)
            return
        row = con.execute("SELECT * FROM model_versions WHERE id = ?", [version_id]).fetchone()
        if not row:
            raise ValueError("versi model tidak ditemukan")
        con.execute("UPDATE model_versions SET active = (id = ?)", [version_id])
        _activate(con.execute("SELECT * FROM model_versions WHERE id = ?", [version_id]).fetchone())


@app.get("/api/system/status")
def system_status():
    """Status job otomatis (skor & model) — hanya-baca, untuk ditampilkan di UI."""
    sc = STATE["scoring"]
    return {
        "now": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scoring": {"pending": sc["dirty_since"] is not None, "running": sc["running"], "last_run": sc["last_run"] or DATA["meta"].get("generated_at"),
                    "last_error": sc["last_error"], "debounce_s": RESCORE_DEBOUNCE_S},
        "model": {**STATE["model"], "check_every_s": MODEL_CHECK_S, "retrain_every_labels": RETRAIN_EVERY,
                  "min_labels": MIN_LABELS, "min_per_class": MIN_PER_CLASS, "includes_simulated": AUTO_INCLUDE_SIM},
    }


@app.get("/")
def index():
    return RedirectResponse("/app/ecrs_risk_radar.html")


if (ROOT / "dashboard").is_dir():  # prototype HTML lama (opsional)
    app.mount("/app", StaticFiles(directory=ROOT / "dashboard", html=True), name="dashboard")
