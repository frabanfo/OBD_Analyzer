"""
gear_detector.py
Stima la marcia inserita dal rapporto RPM/Speed.
Usa clustering via histogram senza dipendenze esterne (solo numpy).
"""

import json
import math
import os

PROFILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "gear_profile.json"
)

MIN_SPEED = 15.0    # km/h — sotto questo valore ignora (troppo rumoroso)
MIN_RPM = 600.0     # rpm — sotto questo valore ignora (folle/frizione)
MIN_SAMPLES = 50    # campioni minimi prima di tentare il clustering
BIN_WIDTH = 4.0     # ampiezza bin dell'histogram (rpm / km/h)
MAX_RATIO = 200.0   # ratio massimo plausibile (taglio outlier)
ASSIGN_TOL = 0.20   # tolleranza del 20% per assegnare una marcia nota


class GearDetector:
    def __init__(self):
        self._samples: list[float] = []
        self._centroids: list[float] = []  # ordinati desc (G1 > G2 > ...)
        self._dirty = False                 # centroidi da ricalcolare
        self._load_profile()

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def update(self, rpm: float, speed: float):
        """Aggiunge un campione per affinare il clustering."""
        if speed < MIN_SPEED or rpm < MIN_RPM:
            return
        ratio = rpm / speed
        if ratio > MAX_RATIO:
            return
        self._samples.append(ratio)
        self._dirty = True
        if len(self._samples) % 20 == 0:
            self._refit()

    def detect(self, rpm: float, speed: float) -> int | None:
        """Ritorna il numero di marcia (1-based) o None se incerto."""
        if speed < MIN_SPEED or rpm < MIN_RPM:
            return None
        ratio = rpm / speed
        if ratio > MAX_RATIO or not self._centroids:
            return None
        closest = min(range(len(self._centroids)),
                      key=lambda i: abs(self._centroids[i] - ratio))
        centroid = self._centroids[closest]
        if abs(ratio - centroid) / centroid > ASSIGN_TOL:
            return None
        return closest + 1  # 1-based

    def save_profile(self):
        if not self._centroids:
            return
        os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
        with open(PROFILE_PATH, "w") as f:
            json.dump({"centroids": self._centroids,
                       "n_gears": len(self._centroids)}, f, indent=2)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _refit(self):
        if len(self._samples) < MIN_SAMPLES:
            return

        # Histogram in pure Python
        n_bins = int(math.ceil(MAX_RATIO / BIN_WIDTH))
        counts = [0] * n_bins
        for v in self._samples:
            idx = int(v / BIN_WIDTH)
            if 0 <= idx < n_bins:
                counts[idx] += 1

        # Trova picchi locali
        peaks = []
        for i in range(1, n_bins - 1):
            if counts[i] > counts[i - 1] and counts[i] > counts[i + 1] and counts[i] > 3:
                center = (i + 0.5) * BIN_WIDTH
                peaks.append(center)

        if peaks:
            self._centroids = sorted(peaks, reverse=True)  # G1 primo
            self._dirty = False

    def _load_profile(self):
        if not os.path.exists(PROFILE_PATH):
            return
        try:
            with open(PROFILE_PATH) as f:
                data = json.load(f)
            self._centroids = data.get("centroids", [])
        except (json.JSONDecodeError, KeyError):
            pass
