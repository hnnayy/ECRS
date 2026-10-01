"""Model terlatih (tingkat 3): regresi logistik ber-regularisasi, murni numpy.

Fitur = keluaran engine berbasis aturan (skor & status modul + metrik penjelas), sehingga
aturan tetap menjadi sumber alasan dan model hanya belajar menimbang dari label pemeriksa.
"""
from __future__ import annotations

import numpy as np

FEATURES: list[tuple[str, str]] = [
    ("sA", "Skor Module A (headcount)"), ("sB", "Skor Module B (peer wage)"), ("sC", "Skor Module C (setoran)"),
    ("fA", "A di-flag"), ("fB", "B di-flag"), ("fC", "C di-flag"),
    ("explained", "Penurunan dijelaskan resign"),
    ("A_drop", "Penurunan headcount terburuk"), ("B_below", "Upah di bawah median cohort"),
    ("C_gap", "Median selisih setoran"), ("C_run", "Kurang setor berturut-turut"),
]
NAMES = [k for k, _ in FEATURES]
LABELS = dict(FEATURES)


def _metrics(c: dict, module: str) -> dict:
    for d in c["explanation"]["drivers"]:
        if d["module"] == module:
            return d.get("metrics") or {}
    return {}


def _clip01(x: float | None) -> float:
    return float(min(max(x or 0.0, 0.0), 1.0))


def featurize(c: dict) -> list[float]:
    s, st = c["scores"], c["status"]
    a, b, cc = _metrics(c, "A"), _metrics(c, "B"), _metrics(c, "C")
    return [
        s["A"] or 0.0, s["B"] or 0.0, s["C"] or 0.0,
        float(st["A"] == "FLAGGED"), float(st["B"] == "FLAGGED"), float(st["C"] == "FLAGGED"),
        float(st["A"] == "EXPLAINED_BY_RESIGN"),
        _clip01(a.get("drop_pct")), _clip01(-(b.get("pct_vs_median") or 0.0)),
        _clip01(cc.get("median_gap_pct")), _clip01((cc.get("longest_run") or 0) / 12),
    ]


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def fit(X: np.ndarray, y: np.ndarray, l2: float = 5.0, iters: int = 50) -> dict:
    """Newton/IRLS dengan ridge dan bobot kelas seimbang. Mengembalikan bobot dalam ruang terstandardisasi."""
    mean, std = X.mean(0), X.std(0)
    std[std < 1e-9] = 1.0
    Z = np.hstack([np.ones((len(X), 1)), (X - mean) / std])
    n_pos, n_neg = y.sum(), len(y) - y.sum()
    sw = np.where(y == 1, len(y) / (2 * n_pos), len(y) / (2 * n_neg))
    reg = np.eye(Z.shape[1]) * l2
    reg[0, 0] = 0.0
    w = np.zeros(Z.shape[1])
    for _ in range(iters):
        p = _sigmoid(Z @ w)
        grad = Z.T @ (sw * (p - y)) + reg @ w
        H = (Z * (sw * p * (1 - p))[:, None]).T @ Z + reg + np.eye(Z.shape[1]) * 1e-6
        step = np.linalg.solve(H, grad)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return {"b": float(w[0]), "w": w[1:].tolist(), "mean": mean.tolist(), "std": std.tolist()}


def predict(model: dict, X: np.ndarray) -> np.ndarray:
    Z = (X - np.array(model["mean"])) / np.array(model["std"])
    return _sigmoid(Z @ np.array(model["w"]) + model["b"])


def contributions(model: dict, x: list[float], top: int = 5) -> list[dict]:
    z = (np.array(x) - np.array(model["mean"])) / np.array(model["std"])
    contrib = z * np.array(model["w"])
    order = np.argsort(-np.abs(contrib))[:top]
    return [{"feature": NAMES[i], "label": LABELS[NAMES[i]], "value": round(float(x[i]), 3),
             "contribution": round(float(contrib[i]), 3)} for i in order if abs(contrib[i]) > 1e-3]


def auc(y: np.ndarray, p: np.ndarray) -> float | None:
    pos, neg = (y == 1), (y == 0)
    if not pos.any() or not neg.any():
        return None
    ranks = np.argsort(np.argsort(p)) + 1.0
    for v in np.unique(p):  # rata-ratakan ranking untuk skor kembar
        m = p == v
        if m.sum() > 1:
            ranks[m] = ranks[m].mean()
    return float((ranks[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * neg.sum()))


def precision_at_k(y: np.ndarray, p: np.ndarray, k: int) -> float:
    return float(y[np.argsort(-p)[:k]].mean())


def cross_validate(X: np.ndarray, y: np.ndarray, baseline: np.ndarray, k: int = 5, seed: int = 0) -> dict:
    """CV stratified. Membandingkan model dengan skor aturan (baseline) pada label yang sama."""
    rng = np.random.default_rng(seed)
    folds = np.zeros(len(y), dtype=int)
    for cls in (0, 1):
        idx = rng.permutation(np.where(y == cls)[0])
        folds[idx] = np.arange(len(idx)) % k
    oof = np.zeros(len(y))
    for f in range(k):
        tr, te = folds != f, folds == f
        oof[te] = predict(fit(X[tr], y[tr]), X[te])
    kk = int(y.sum())
    return {
        "folds": k, "auc_model": auc(y, oof), "auc_rules": auc(y, baseline),
        "p_at_k_model": precision_at_k(y, oof, kk), "p_at_k_rules": precision_at_k(y, baseline, kk), "k": kk,
    }
