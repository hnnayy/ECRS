"""Job latar belakang: rescore otomatis saat data berubah & pelatihan ulang model saat label baru cukup.

Berjalan sebagai satu thread daemon di dalam proses API. Tidak ada tombol/endpoint untuk memicunya dari UI.
"""
import logging
import os
import threading
import time
from collections.abc import Callable

log = logging.getLogger("ecrs.jobs")

TICK_S = float(os.environ.get("ECRS_TICK_S", 5))
RESCORE_DEBOUNCE_S = float(os.environ.get("ECRS_RESCORE_DEBOUNCE_S", 10))   # tunggu perubahan data "tenang" dulu
MODEL_CHECK_S = float(os.environ.get("ECRS_MODEL_CHECK_S", 60))


class Scheduler:
    def __init__(self, state: dict, rescore: Callable[[], None], model_check: Callable[[], None]):
        self.state, self.rescore, self.model_check = state, rescore, model_check
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="ecrs-jobs", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        last_model = 0.0
        while not self._stop.wait(TICK_S):
            now = time.time()
            sc = self.state["scoring"]
            if sc["dirty_since"] is not None and now - sc["dirty_since"] >= RESCORE_DEBOUNCE_S:
                self._safe(self.rescore, "scoring")
            if now - last_model >= MODEL_CHECK_S:
                last_model = now
                self._safe(self.model_check, "model")

    def _safe(self, fn: Callable[[], None], key: str) -> None:
        try:
            fn()
            self.state[key]["last_error"] = None
        except Exception as e:  # job tidak boleh mematikan thread
            log.exception("job %s gagal", key)
            self.state[key]["last_error"] = f"{type(e).__name__}: {e}"
