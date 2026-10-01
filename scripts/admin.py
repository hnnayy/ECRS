"""Operasi manual untuk DEVELOPER (tidak tersedia di API/UI, karena aplikasi tidak punya RBAC).

    python -m scripts.admin rescore                 # hitung ulang skor sekarang
    python -m scripts.admin train [--simulated]     # latih model sekarang (abaikan syarat +N label)
    python -m scripts.admin activate <id>           # paksa versi model tertentu
    python -m scripts.admin deactivate              # matikan model (kembali ke skor aturan)
Pada operasi normal semua ini berjalan otomatis di backend.
"""
import argparse

from backend import main

ap = argparse.ArgumentParser()
ap.add_argument("cmd", choices=["rescore", "train", "activate", "deactivate"])
ap.add_argument("version", nargs="?", type=int)
ap.add_argument("--simulated", action="store_true")
a = ap.parse_args()

if a.cmd == "rescore":
    main.do_rescore()
    print(main.DATA["meta"]["counts"])
elif a.cmd == "train":
    print(main.train_model_now(a.simulated))
elif a.cmd == "activate":
    main.set_active_version(a.version)
    print(main.ACTIVE["version"])
else:
    main.set_active_version(None)
    print("model dinonaktifkan")
