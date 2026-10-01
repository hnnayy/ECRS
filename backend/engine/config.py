"""Konfigurasi engine (threshold hasil tuning Wave 1, dipindah dari notebook Wave 2)."""
from dataclasses import dataclass

# ---- UMP 2025 per provinsi (CEK ULANG ke sumber resmi) -----------------------
# Nilai AWAL master UMR (dipakai untuk mengisi tabel `wilayah` saat migrasi). Engine membaca UMR dari master di database,
# bukan dari tabel ini. CEK ULANG ke sumber resmi.
UMR_TABLE = {
    "DKI Jakarta": 5_396_761, "Jawa Barat": 2_191_238, "Jawa Tengah": 2_169_349,
    "Jawa Timur": 2_305_985, "DI Yogyakarta": 2_264_080, "Banten": 2_905_119,
    "Bali": 2_996_560, "Sumatera Utara": 2_992_559, "Sumatera Barat": 2_994_193,
    "Sumatera Selatan": 3_681_570, "Riau": 3_508_776, "Kepulauan Riau": 3_623_653,
    "Kalimantan Timur": 3_579_313, "Sulawesi Selatan": 3_657_527, "Papua": 4_285_848,
}

@dataclass(frozen=True)
class ConfigA:                     # Registration volatility
    Z_THRESHOLD: float = 2.0
    ROLLING_WINDOW: int = 6
    MIN_PERIODS: int = 3
    MIN_DROP_PCT: float = 0.10
    STD_FLOOR_ABS: float = 1.0
    STD_FLOOR_REL: float = 0.02
    CAP_MULT: float = 3.0          # skor mentah >= Z_THRESHOLD*CAP_MULT -> norm 1.0

@dataclass(frozen=True)
class ConfigB:                     # Peer-group wage benchmarking
    Z_THRESHOLD: float = 1.5
    MIN_PERSIST: float = 0.5
    MIN_COHORT_SIZE: int = 5
    MIN_PERIODS: int = 3
    # Pre-filter UMR dimatikan: dengan 1.5x UMR, under-reporting di sektor bergaji tinggi (keuangan, teknologi)
    # tidak pernah jadi kandidat meski 30-40% di bawah cohort (6/25 kasus terlewat). UMR tetap dipakai sebagai konteks alasan.
    UMR_PREFILTER_MULT: float | None = None
    IQR_FLOOR: float = 0.05
    CAP_MULT: float = 3.0

@dataclass(frozen=True)
class ConfigC:                     # Contribution reconciliation
    TOL_PCT: float = 0.02          # selisih <= 2% dari iuran seharusnya dianggap pembulatan
    TOL_ABS: float = 10_000        # selisih <= Rp10.000 diabaikan (harus lewat KEDUANYA baru dihitung)
    MIN_CONSECUTIVE: int = 2       # flag hanya kalau kurang setor >= 2 bulan BERTURUT-TURUT
    ALLOW_CATCHUP: bool = True     # kurang bulan ini tapi dilunasi bulan depan = telat wajar, tidak dihitung
    MIN_PERIODS: int = 2           # < 2 bulan data setoran -> INSUFFICIENT_DATA
    CAP_PCT: float = 0.25          # kekurangan >= 25% -> skor ternormalisasi 1.0
    # dipakai HANYA kalau remittance tidak punya kolom "iuran seharusnya":
    CONTRIB_RATE: float = 0.05     # iuran BPJS Kesehatan PPU 5% (4% pemberi kerja + 1% pekerja)
    WAGE_CAP: float = 12_000_000   # batas atas upah perhitungan iuran

@dataclass(frozen=True)
class ConfigComposite:
    METHOD: str = "mean"           # "mean" (equal-weight, sesuai checklist) atau "max"
    STRONG_SCORE: float = 0.8      # 1 modul flag dengan skor >= ini -> band Tinggi
    MIN_COVERAGE: int = 2          # < 2 modul punya data cukup & tidak ada flag -> 'Belum bisa dinilai', bukan 'Rendah'

CFG_A, CFG_B, CFG_C, CFG_X = ConfigA(), ConfigB(), ConfigC(), ConfigComposite()

# Label ground truth per modul (dicek "mengandung", tidak case-sensitive)
POSITIVE_LABELS = {
    "A": ["PDUK", "HIDDEN", "HEADCOUNT", "EMPLOYEE", "KARYAWAN", "SEMBUNYI"],
    "B": ["WAGE", "UPAH", "GAJI", "SALARY", "DPI", "UNDERPAY"],
    "C": ["REMITTANCE", "SETOR", "IURAN", "CONTRIBUTION"],
}
# Bukan kasus curang. CLEAN_MUTASI_SAH = penurunan peserta yang SAH (resign cocok): uji true-negative, tidak boleh di-flag.
# COLD_START = badan usaha baru: harus "belum bisa dinilai". (Notebook asli hanya mendaftar CLEAN sehingga keduanya salah dihitung sebagai kasus.)
NEGATIVE_LABELS = ["CLEAN", "NONE", "NORMAL", "-", "NAN", "CLEAN_MUTASI_SAH", "COLD_START"]

MODULE_LABEL = {"A": "Sembunyiin karyawan", "B": "Lapor gaji lebih rendah", "C": "Setoran iuran tidak sesuai"}