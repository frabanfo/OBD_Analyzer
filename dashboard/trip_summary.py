"""
trip_summary.py
Accumula statistiche di viaggio in tempo reale, thread-safe.

Rilevamento viaggio:
  START → RPM > 0 dopo essere stato a 0 (accensione motore)
  END   → RPM = 0 (motore spento) oppure idle > IDLE_END_TIMEOUT (parcheggio prolungato)

Durante i semafori (speed=0, RPM~800) il viaggio continua normalmente.
"""

import threading
import time
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from dashboard.engine import estimate_fuel_rate_lh

IDLE_RPM        = 900   # sotto questa soglia = motore al minimo
IDLE_END_TIMEOUT = 300  # secondi di idle continuo = parcheggio, fine viaggio

TRIPS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "trips")


class TripSummary:
    def __init__(self):
        self._lock = threading.Lock()
        self._reset_state()

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def update(self, record: dict):
        rpm   = record.get("rpm")   or 0.0
        speed = record.get("speed") or 0.0
        map_k = record.get("intake_pressure")
        temp  = record.get("intake_temp")
        dt    = config.SCAN_INTERVAL

        with self._lock:
            self._update(rpm, speed, map_k, temp, dt)

    def reset(self):
        with self._lock:
            self._reset_state()

    def get_stats(self) -> dict:
        with self._lock:
            return self._get_stats_unlocked()

    def save_trip(self, fuel_price: float = 1.87) -> bool:
        """Salva il viaggio corrente in data/trips/. Restituisce True se salvato."""
        with self._lock:
            stats = self._get_stats_unlocked()
            if stats["distance_km"] < 0.1:
                return False

            os.makedirs(TRIPS_DIR, exist_ok=True)
            fname = (self._started_at.strftime("%Y-%m-%d_%H-%M-%S") if self._started_at
                     else datetime.now().strftime("%Y-%m-%d_%H-%M-%S")) + ".json"
            fpath = os.path.join(TRIPS_DIR, fname)

            trip_data = {
                "started_at": self._started_at.isoformat() if self._started_at else datetime.now().isoformat(),
                "distance_km": stats["distance_km"],
                "fuel_L":      stats["fuel_L"],
                "l_100km":     stats["l_100km"],
                "avg_speed":   stats["avg_speed"],
                "max_speed":   stats["max_speed"],
                "avg_rpm":     stats["avg_rpm"],
                "elapsed_s":   stats["elapsed_s"],
                "fuel_price":  round(fuel_price, 2),
                "cost":        round(stats["fuel_L"] * fuel_price, 2),
            }

            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(trip_data, f, indent=2)
            return True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _reset_state(self):
        self._state      = "idle"
        self._start_t    = None
        self._started_at = None   # datetime reale inizio viaggio
        self._idle_since = None

        self._dist_km   = 0.0
        self._fuel_L    = 0.0
        self._rpm_sum   = 0.0
        self._speed_sum = 0.0
        self._max_speed = 0.0
        self._n_driving = 0

    def _get_stats_unlocked(self) -> dict:
        dist = self._dist_km
        fuel = self._fuel_L
        n    = self._n_driving

        avg_speed = round(self._speed_sum / n, 1) if n > 0 else 0.0
        avg_rpm   = round(self._rpm_sum   / n, 0) if n > 0 else 0.0
        l_100km   = round(fuel / dist * 100, 1)   if dist > 0.05 else 0.0
        elapsed   = int(time.monotonic() - self._start_t) if self._start_t else 0

        return {
            "distance_km": round(dist, 2),
            "fuel_L":      round(fuel, 3),
            "l_100km":     l_100km,
            "avg_speed":   avg_speed,
            "max_speed":   round(self._max_speed, 1),
            "avg_rpm":     int(avg_rpm),
            "elapsed_s":   elapsed,
            "state":       self._state,
        }

    def _update(self, rpm, speed, map_k, temp, dt):
        now = time.monotonic()
        moving = speed > 3 or rpm > IDLE_RPM

        if rpm == 0:
            # Motore spento → fine viaggio
            if self._state == "driving":
                self._state = "idle"
            self._idle_since = now
            return

        if moving:
            # In guida — avvia viaggio se non era già avviato
            if self._start_t is None:
                self._start_t    = now
                self._started_at = datetime.now()
            self._state      = "driving"
            self._idle_since = None

            self._dist_km   += speed * dt / 3600.0
            self._fuel_L    += estimate_fuel_rate_lh(rpm, map_k, temp) * dt / 3600.0
            self._rpm_sum   += rpm
            self._speed_sum += speed
            self._n_driving += 1
            if speed > self._max_speed:
                self._max_speed = speed
        else:
            # Idle con motore acceso (semaforo, coda...) — accumula carburante
            if self._idle_since is None:
                self._idle_since = now
            elif now - self._idle_since > IDLE_END_TIMEOUT:
                self._state = "idle"  # parcheggio prolungato

            self._fuel_L += estimate_fuel_rate_lh(rpm, map_k, temp) * dt / 3600.0
