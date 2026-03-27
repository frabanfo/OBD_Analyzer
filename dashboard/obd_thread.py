"""
obd_thread.py
Thread background che legge dati OBD2 (reali o mock) e li inserisce nel buffer.
"""

import threading
import sys
import os
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from dashboard.data_buffer import DataBuffer
from dashboard.gear_detector import GearDetector
from dashboard.trip_summary import TripSummary


def _calc_braking(speed_history: deque) -> float:
    """Derivata della velocità con smoothing. Negativo = frenata (m/s²)."""
    if len(speed_history) < 2:
        return 0.0
    speeds = list(speed_history)
    # Media mobile per ridurre il rumore
    if len(speeds) >= config.BRAKING_SMOOTH:
        speeds = speeds[-config.BRAKING_SMOOTH:]
    delta_speed = (speeds[-1] - speeds[0]) / len(speeds)
    # Converti da km/h/campione a m/s²
    delta_ms2 = (delta_speed / 3.6) / (config.DISPLAY_INTERVAL_MS / 1000.0)
    return round(delta_ms2, 3)


def _real_reader(buffer: DataBuffer, gear_detector: GearDetector,
                 trip: TripSummary, stop_event: threading.Event):
    """Legge dati dall'adattatore OBD2 con modalità asincrona (più veloce)."""
    import obd
    import datetime as dt_mod

    PIDS = {
        "rpm":             obd.commands.RPM,
        "speed":           obd.commands.SPEED,
        "throttle":        obd.commands.THROTTLE_POS,
        "engine_load":     obd.commands.ENGINE_LOAD,
        "coolant_temp":    obd.commands.COOLANT_TEMP,
        "intake_temp":     obd.commands.INTAKE_TEMP,
        "short_fuel_trim": obd.commands.SHORT_FUEL_TRIM_1,
        "long_fuel_trim":  obd.commands.LONG_FUEL_TRIM_1,
        "intake_pressure": obd.commands.INTAKE_PRESSURE,
    }

    speed_history = deque(maxlen=config.BRAKING_SMOOTH + 2)
    connection = None

    while not stop_event.is_set():
        if connection is None or not connection.is_connected():
            print("[OBD] Connessione in corso...")
            if connection is not None:
                try:
                    connection.stop()
                    connection.close()
                except Exception:
                    pass
            connection = obd.Async(
                portstr=config.PORT,
                baudrate=config.BAUDRATE,
                fast=config.FAST,
                timeout=config.TIMEOUT,
            )
            if not connection.is_connected():
                print("[OBD] Connessione fallita, riprovo in 5s...")
                connection = None
                stop_event.wait(5.0)
                continue
            for cmd in PIDS.values():
                if connection.supports(cmd):
                    connection.watch(cmd)
            connection.start()
            print("[OBD] Connesso (async).")

        # Leggi i valori cached — non blocca la seriale
        record = {"timestamp": dt_mod.datetime.now().isoformat()}
        for key, cmd in PIDS.items():
            if connection.supports(cmd):
                resp = connection.query(cmd)
                val = None if resp.is_null() else resp.value
                if val is not None and hasattr(val, "magnitude"):
                    val = round(val.magnitude, 2)
                record[key] = val
            else:
                record[key] = None

        speed = record.get("speed") or 0.0
        rpm   = record.get("rpm")   or 0.0
        speed_history.append(speed)
        record["braking"] = _calc_braking(speed_history)

        gear_detector.update(rpm, speed)
        record["gear"] = gear_detector.detect(rpm, speed)

        buffer.add(record)
        trip.update(record)
        stop_event.wait(config.DISPLAY_INTERVAL_MS / 1000.0)

    if connection is not None:
        try:
            connection.stop()
            connection.close()
        except Exception:
            pass
    gear_detector.save_profile()


def _mock_reader(buffer: DataBuffer, gear_detector: GearDetector,
                 trip: TripSummary, stop_event: threading.Event):
    """Legge dati dal simulatore mock."""
    from dashboard.mock_obd import MockOBDSource

    source = MockOBDSource()
    speed_history = deque(maxlen=config.BRAKING_SMOOTH + 2)

    for record in source.stream():
        if stop_event.is_set():
            break

        speed = record.get("speed") or 0.0
        rpm = record.get("rpm") or 0.0
        speed_history.append(speed)
        record["braking"] = _calc_braking(speed_history)

        # In mock mode il gear viene già dalla sequenza scripted,
        # ma aggiorniamo il detector per testarlo
        gear_detector.update(rpm, speed)
        if record.get("gear") is None:
            record["gear"] = gear_detector.detect(rpm, speed)

        buffer.add(record)
        trip.update(record)

    gear_detector.save_profile()


def start_reader(buffer: DataBuffer, trip: TripSummary,
                 stop_event: threading.Event) -> threading.Thread:
    """Avvia il thread di lettura (mock o reale) e lo ritorna."""
    gear_detector = GearDetector()
    reader_fn = _mock_reader if config.MOCK_MODE else _real_reader
    t = threading.Thread(
        target=reader_fn,
        args=(buffer, gear_detector, trip, stop_event),
        daemon=True,
        name="obd-reader",
    )
    t.start()
    return t
