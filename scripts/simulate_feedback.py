"""Simulasikan keputusan pemeriksa untuk DEMO feedback loop. Jalankan dari root proyek:

    python -m scripts.simulate_feedback            # buat (ganti) label simulasi
    python -m scripts.simulate_feedback --purge    # hapus semua label simulasi

Sama dengan tombol di halaman "Model & Feedback Loop". Label ditandai source='simulasi' dan BUKAN bukti
akurasi: diturunkan dari ground_truth sintetis, hanya untuk employer peringkat teratas.
"""
import argparse

from backend.main import purge_simulated, simulate_labels

ap = argparse.ArgumentParser()
ap.add_argument("--top", type=int, default=150)
ap.add_argument("--noise", type=float, default=0.08)
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--purge", action="store_true")
a = ap.parse_args()
print(f"{purge_simulated()} label simulasi dihapus" if a.purge else simulate_labels(a.top, a.noise, a.seed))
