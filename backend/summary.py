"""Ringkasan kasus per badan usaha.

Dasar = ringkasan TEMPLAT deterministik (selalu tersedia, angkanya pasti benar). Jika LLM dikonfigurasi, LLM hanya diminta
MERAPIKAN templat itu menjadi paragraf yang lebih luwes; hasilnya DITOLAK (dan dipakai templat) bila:
memuat angka yang tidak ada di templat, memakai bahasa vonis, tidak menyebut ID, terlalu panjang, atau penyedia gagal/dibatasi.
Penyedia memakai format API kompatibel-OpenAI (Gemini, Groq, OpenRouter, GitHub Models, Ollama): atur lewat .env.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from collections import deque

from .database import ROOT


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def cfg() -> dict:
    return {
        "base_url": os.environ.get("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
        "model": os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite"),
        "api_key": os.environ.get("LLM_API_KEY", ""),
        "timeout": float(os.environ.get("LLM_TIMEOUT_S", 25)),
        "max_per_min": int(os.environ.get("LLM_MAX_PER_MIN", 8)),
    }


def llm_configured() -> bool:
    c = cfg()
    return bool(c["base_url"] and c["model"] and (c["api_key"] or "localhost" in c["base_url"] or "127.0.0.1" in c["base_url"]))


# ---------------------------------------------------------------- templat
NEXT_STEP = {
    "A": lambda m: f"minta catatan mutasi/resign dan data kepesertaan sekitar {m.get('worst_period', 'periode terkait')}",
    "B": lambda m: "bandingkan upah yang dilaporkan dengan bukti upah (mis. data pajak atau slip) dan dengan perusahaan sejenis",
    "C": lambda m: f"minta bukti setoran iuran untuk {m['run_start']} s/d {m['run_end']}" if m.get("run_start") and m.get("run_end")
                   else "minta bukti setoran iuran periode yang kurang",
}
NAME = {"A": "jumlah peserta", "B": "upah yang dilaporkan", "C": "setoran iuran"}


def template_summary(c: dict, total: int) -> str:
    head = f"{c['id']} ({c['sektor']}, {c['wilayah']}, skala {c['skala'].lower()}) berada pada tingkat risiko {c['band'].lower()}"
    head += f", peringkat {c['rank']} dari {total}." if c.get("rank") else "."
    drivers = c["explanation"]["drivers"]
    flagged = [d for d in drivers if d["flagged"]]
    parts = [head]
    if flagged:
        parts.append("Indikasi: " + " ".join(d["text"].rstrip(".") + "." for d in flagged))
        steps = [NEXT_STEP[d["module"]](d.get("metrics") or {}) for d in flagged]
        parts.append("Langkah pemeriksaan yang disarankan: " + "; ".join(steps) + ".")
    elif c["band"] == "Belum bisa dinilai":
        parts.append("Data belum cukup untuk menilai badan usaha ini; pantau sampai data lengkap.")
    else:
        parts.append(f"Tidak ada indikasi pada {c['coverage']} jenis pemeriksaan ({', '.join(NAME[d['module']] for d in drivers)}).")
    pola = (c.get("extra_signals") or {}).get("isolation_forest") or {}
    if pola.get("flagged") and pola.get("reasons"):
        parts.append("Pola tidak biasa: " + "; ".join(r["text"] for r in pola["reasons"]) + ".")
    ew = (c.get("extra_signals") or {}).get("remittance_early_warning") or {}
    if ew.get("flagged"):
        parts.append("Peringatan dini setoran: " + ew["text"])
    parts.append("Skor ini alat prioritas pemeriksaan, bukan vonis.")
    return " ".join(parts)


# ---------------------------------------------------------------- LLM + validasi
NUM = re.compile(r"\d+(?:[.,]\d+)*")
BANNED = ("terbukti", "menggelapkan", "penipuan", "pelaku", "korupsi", "curang", "bersalah")
MAX_CHARS = 1200

SYSTEM = ("Kamu membantu tim pemeriksa kepatuhan iuran. Tulis ulang ringkasan kasus berikut menjadi SATU paragraf bahasa Indonesia "
          "yang jelas dan ringkas (maksimal 110 kata), tanpa markdown dan tanpa daftar. Gunakan HANYA fakta yang ada di teks; "
          "jangan menambah angka, nama, atau kesimpulan. Jangan menuduh atau memvonis; ini hanya prioritas pemeriksaan. "
          "Pertahankan ID badan usaha dan seluruh angka persis seperti aslinya.")


def validate_llm(text: str, template: str, company_id: str) -> str | None:
    """Kembalikan alasan penolakan, atau None jika lolos."""
    t = (text or "").strip()
    if not t:
        return "jawaban kosong"
    if len(t) > MAX_CHARS:
        return "terlalu panjang"
    if company_id not in t:
        return "ID badan usaha hilang"
    if any(w in t.lower() for w in BANNED):
        return "memakai bahasa vonis"
    extra = set(NUM.findall(t)) - set(NUM.findall(template))
    if extra:
        return f"memuat angka yang tidak ada di data ({', '.join(sorted(extra)[:3])})"
    return None


_calls: deque[float] = deque()
_lock = threading.Lock()


def _rate_ok(limit: int) -> bool:
    now = time.time()
    with _lock:
        while _calls and now - _calls[0] > 60:
            _calls.popleft()
        if len(_calls) >= limit:
            return False
        _calls.append(now)
        return True


def call_llm(user_text: str) -> str:
    c = cfg()
    body = json.dumps({"model": c["model"], "temperature": 0.2, "max_tokens": 1024,
                       "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_text}]}).encode()
    headers = {"Content-Type": "application/json"}
    if c["api_key"]:
        headers["Authorization"] = f"Bearer {c['api_key']}"
    req = urllib.request.Request(c["base_url"].rstrip("/") + "/chat/completions", data=body, headers=headers, method="POST")
    for attempt in range(2):  # penyedia gratis kadang 503 sesaat: coba ulang sekali
        try:
            with urllib.request.urlopen(req, timeout=c["timeout"]) as r:
                return json.load(r)["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code != 503 or attempt == 1:
                raise
            time.sleep(2)
    raise RuntimeError("tidak tercapai")


# cache: berhasil -> berlaku sampai skor dihitung ulang; gagal -> 60 detik (jangan menghabiskan kuota gratis)
_cache: dict[tuple, tuple[float, dict]] = {}


def build(c: dict, total: int, generated_at: str | None, use_llm: bool = True) -> dict:
    template = template_summary(c, total)
    out = {"text": template, "source": "templat", "model": None, "fallback_reason": None, "llm_configured": llm_configured()}
    if not use_llm or not out["llm_configured"]:
        return out
    key = (c["id"], generated_at, cfg()["model"])
    hit = _cache.get(key)
    if hit and (hit[1]["source"] == "llm" or time.time() - hit[0] < 60):
        return hit[1]
    result = dict(out)
    try:
        if not _rate_ok(cfg()["max_per_min"]):
            result["fallback_reason"] = "batas permintaan per menit tercapai"
        else:
            text = call_llm(template)
            why = validate_llm(text, template, c["id"])
            if why:
                result["fallback_reason"] = f"jawaban AI ditolak: {why}"
            else:
                result.update(text=text.strip(), source="llm", model=cfg()["model"])
    except urllib.error.HTTPError as e:
        result["fallback_reason"] = {401: "kunci penyedia ditolak", 403: "kunci penyedia ditolak", 429: "kuota gratis penyedia habis/dibatasi", 503: "model penyedia sedang padat"}.get(
            e.code, f"penyedia mengembalikan error {e.code}")
    except (urllib.error.URLError, TimeoutError):
        result["fallback_reason"] = "penyedia tidak dapat dihubungi"
    except Exception as e:  # format respons tak terduga, dll.
        result["fallback_reason"] = f"error: {type(e).__name__}"
    _cache[key] = (time.time(), result)
    return result
