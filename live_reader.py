"""
live_reader.py
Legge i dati OBD2 in tempo reale e li salva su CSV.
Premi Ctrl+C per fermare.
"""

import csv
import time
import datetime
import obd
import config

# PID da leggere in modalità live — modifica in base a quello che supporta la tua auto
# (scoprilo eseguendo prima scan_pids.py)
LIVE_COMMANDS = [
    obd.commands.RPM,
    obd.commands.SPEED,
    obd.commands.COOLANT_TEMP,
    obd.commands.INTAKE_TEMP,
    obd.commands.THROTTLE_POS,
    obd.commands.ENGINE_LOAD,
    obd.commands.FUEL_LEVEL,
    obd.commands.MAF,
    obd.commands.O2_B1S1,
    obd.commands.SHORT_FUEL_TRIM_1,
    obd.commands.LONG_FUEL_TRIM_1,
]


def connect():
    print(f"Connessione OBD2...")
    connection = obd.OBD(
        portstr=config.PORT,
        baudrate=config.BAUDRATE,
        fast=config.FAST,
        timeout=config.TIMEOUT,
    )
    if not connection.is_connected():
        print("[ERRORE] Impossibile connettersi. Controlla config.py e l'adattatore.")
        return None
    print(f"[OK] Connesso su {connection.port_name()}\n")
    return connection


def filter_supported(connection, commands):
    supported = [cmd for cmd in commands if connection.supports(cmd)]
    unsupported = [cmd.name for cmd in commands if not connection.supports(cmd)]
    if unsupported:
        print(f"[WARN] PID non supportati da questa auto: {', '.join(unsupported)}")
    print(f"[INFO] Lettura di {len(supported)} PID: {', '.join(c.name for c in supported)}\n")
    return supported


def read_loop(connection, commands):
    fieldnames = ["timestamp"] + [cmd.name for cmd in commands]

    with open(config.LOG_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        print(f"Logging su '{config.LOG_FILE}' — Ctrl+C per fermare\n")
        print("  " + "  |  ".join(f"{cmd.name:<20}" for cmd in commands))
        print("-" * (22 * len(commands)))

        try:
            while True:
                row = {"timestamp": datetime.datetime.now().isoformat()}
                display = []

                for cmd in commands:
                    response = connection.query(cmd)
                    if response.is_null():
                        row[cmd.name] = ""
                        display.append(f"{'N/A':<20}")
                    else:
                        val = response.value
                        if hasattr(val, "magnitude"):
                            val = round(val.magnitude, 2)
                        row[cmd.name] = val
                        display.append(f"{str(val):<20}")

                writer.writerow(row)
                f.flush()
                print("  " + "  |  ".join(display), end="\r")
                time.sleep(config.SCAN_INTERVAL)

        except KeyboardInterrupt:
            print("\n\n[STOP] Lettura interrotta dall'utente.")


def main():
    connection = connect()
    if connection is None:
        return

    supported = filter_supported(connection, LIVE_COMMANDS)
    if not supported:
        print("[ERRORE] Nessuno dei PID configurati è supportato. Esegui scan_pids.py prima.")
        connection.close()
        return

    read_loop(connection, supported)
    connection.close()
    print(f"Dati salvati in: {config.LOG_FILE}")


if __name__ == "__main__":
    main()
