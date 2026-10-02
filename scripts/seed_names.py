"""Isi nama badan usaha (kolom employers.nama) dengan nama acak yang terdengar wajar, per sektor.

    python -m scripts.seed_names            # hanya isi yang masih kosong
    python -m scripts.seed_names --all      # timpa semua nama
Nama bersifat fiktif (data simulasi). Hasil deterministik (seed tetap) dan unik per badan usaha.
"""
import argparse
import random
import sqlite3

from backend.database import DB_PATH

PREFIX = ["Adi", "Bumi", "Cipta", "Duta", "Eka", "Graha", "Harapan", "Indah", "Jaya", "Karya", "Lintas", "Maju", "Nusa",
          "Prima", "Mitra", "Sentosa", "Surya", "Tirta", "Trans", "Utama", "Wahana", "Satya", "Mega", "Cahaya", "Berkah",
          "Sinar", "Global", "Nusantara", "Artha", "Bina", "Tunggal", "Sumber", "Pelita", "Sejahtera", "Karsa", "Dirgantara"]
CORE = {
    "Manufaktur": ["Mesin", "Tekstil", "Baja", "Plastik", "Kemasan", "Logam", "Furnitur", "Kimia", "Garmen", "Otomotif"],
    "Konstruksi": ["Konstruksi", "Beton", "Bangun", "Infrastruktur", "Teknik Sipil", "Properti", "Rekayasa"],
    "Jasa Keuangan": ["Finansial", "Kapital", "Pembiayaan", "Investama", "Dana", "Sekuritas", "Multi Finance"],
    "Perdagangan & Ritel": ["Niaga", "Dagang", "Retail", "Mart", "Distribusi", "Grosir", "Perkasa Trading"],
    "Perkebunan & Agribisnis": ["Agro", "Perkebunan", "Sawit", "Tani", "Lestari Agri", "Kopi", "Karet"],
    "Teknologi & Digital": ["Teknologi", "Digital", "Solusi Data", "Sistem", "Cyber", "Software", "Inovasi"],
}
SUFFIX = ["", "", "", " Indonesia", " Nusantara", " Persada", " Abadi", " Sejahtera", " Mandiri", " Perkasa"]
BADAN = ["PT", "PT", "PT", "PT", "CV"]


def make(rng: random.Random, sektor: str) -> str:
    core = rng.choice(CORE.get(sektor, ["Usaha"]))
    return f"{rng.choice(BADAN)} {rng.choice(PREFIX)} {core}{rng.choice(SUFFIX)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="timpa juga nama yang sudah terisi")
    a = ap.parse_args()
    db = sqlite3.connect(DB_PATH)
    rows = db.execute("SELECT employer_id, nama, sektor FROM employers ORDER BY employer_id").fetchall()
    used = {n for _, n, _ in rows if n and not a.all}
    rng = random.Random(42)
    n_set = 0
    for eid, nama, sektor in rows:
        if nama and not a.all:
            continue
        cand = make(rng, sektor)
        while cand in used:
            cand = f"{make(rng, sektor)}"
            if cand in used:
                cand += f" {rng.randint(2, 99)}"
        used.add(cand)
        db.execute("UPDATE employers SET nama=? WHERE employer_id=?", (cand, eid))
        n_set += 1
    db.commit()
    print(f"{n_set} nama diisi dari {len(rows)} badan usaha")


if __name__ == "__main__":
    main()
