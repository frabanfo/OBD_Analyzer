"""
mock_obd.py
Simulatore di guida realistica per sviluppo senza auto.
Genera dati OBD2 coerenti: accelerazioni, cambiate, frenate, idle.
"""

import time
import math
import random
import datetime

# Rapporti RPM/Speed per marcia — VW Polo V 85cv 2009, cambio 02T
# Formula: k = 60 * rapporto_cambio * rapporto_finale / (3.6 * circonferenza_ruota)
# Dati: finale 3.765, ruota 185/60R14 (~1.81m), rapporti: 3.909 / 2.238 / 1.520 / 1.156 / 0.886
GEAR_RATIOS = [None, 135.0, 77.5, 52.7, 40.1, 30.7]  # indice 1-5, in rpm/(km/h)

# Sequenza di guida scripted: lista di (durata_sec, target_speed, marcia)
DRIVE_SEQUENCE = [
    (5,   0,   None),   # avvio, idle
    (6,   20,  1),      # partenza in 1ª
    (8,   45,  2),      # accelera in 2ª (città)
    (10,  70,  3),      # 3ª extraurbano
    (12,  100, 4),      # 4ª
    (15,  120, 5),      # 5ª autostrada
    (10,  90,  5),      # rilascio gas
    (8,   70,  4),      # uscita autostrada
    (6,   50,  3),
    (5,   30,  2),
    (5,   5,   1),      # frenata urbana decisa
    (4,   0,   None),   # stop semaforo
    (6,   35,  2),      # ripartenza
    (8,   60,  3),
    (5,   30,  2),
    (4,   0,   None),   # fine giro
]


class MockOBDSource:
    """
    Genera record OBD2 finti a cadenza config.SCAN_INTERVAL.
    Chiama stream() per ottenere un generatore infinito.
    """

    def __init__(self):
        self._speed = 0.0
        self._coolant = 30.0   # parte freddo, sale fino a 90°
        self._intake = 20.0
        self._seq_idx = 0
        self._seg_elapsed = 0.0

    def stream(self):
        import config
        while True:
            t0 = time.time()
            record = self._next_frame()
            yield record
            elapsed = time.time() - t0
            sleep_time = config.SCAN_INTERVAL - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _next_frame(self):
        import config

        seg = DRIVE_SEQUENCE[self._seq_idx]
        seg_duration, target_speed, gear = seg

        # Avanza nel segmento
        self._seg_elapsed += config.SCAN_INTERVAL
        if self._seg_elapsed >= seg_duration:
            self._seg_elapsed = 0.0
            self._seq_idx = (self._seq_idx + 1) % len(DRIVE_SEQUENCE)
            seg = DRIVE_SEQUENCE[self._seq_idx]
            seg_duration, target_speed, gear = seg

        # Interpola velocità verso target
        # Frenata più brusca dell'accelerazione
        prev_speed = self._speed
        factor = 0.25 if target_speed < self._speed else 0.10
        self._speed += (target_speed - self._speed) * factor
        self._speed = max(0.0, self._speed)

        # RPM
        if gear and self._speed > 5:
            ratio = GEAR_RATIOS[gear]
            base_rpm = self._speed * ratio
            rpm = base_rpm + random.uniform(-80, 80)
        else:
            rpm = 820 + random.uniform(-30, 30)  # idle
        rpm = max(750.0, rpm)

        # Throttle: positivo quando accelera, ~0 quando frena
        delta_speed = self._speed - prev_speed
        throttle = max(0.0, min(100.0, delta_speed * 15 + random.uniform(-2, 2)))
        if target_speed == 0:
            throttle = 0.0

        # Engine load: correlato con RPM e throttle
        engine_load = min(100.0, max(10.0,
            (rpm / 6000) * 50 + throttle * 0.4 + random.uniform(-3, 3)
        ))

        # Temperature: sale lentamente verso regimi normali
        self._coolant += (90.0 - self._coolant) * 0.002
        self._intake += (35.0 - self._intake) * 0.001
        coolant = self._coolant + random.uniform(-0.5, 0.5)
        intake = self._intake + random.uniform(-0.3, 0.3)

        # Intake pressure (MAP): idle ~35 kPa, WOT ~97 kPa
        # Per un motore NA a gas: MAP cresce con il carico
        map_kpa = 30.0 + engine_load * 0.67 + random.uniform(-2.0, 2.0)
        map_kpa = round(max(25.0, min(102.0, map_kpa)), 1)

        # Fuel trims: piccole oscillazioni
        short_fuel_trim = random.uniform(-3.0, 3.0)
        long_fuel_trim = -23.44 + random.uniform(-1.0, 1.0)  # come la tua auto

        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "rpm": round(rpm, 1),
            "speed": round(self._speed, 1),
            "throttle": round(throttle, 1),
            "engine_load": round(engine_load, 1),
            "coolant_temp": round(coolant, 1),
            "intake_temp": round(intake, 1),
            "intake_pressure": map_kpa,
            "short_fuel_trim": round(short_fuel_trim, 2),
            "long_fuel_trim": round(long_fuel_trim, 2),
            "gear": gear,
        }
