"""
live_reader.py
Legge i dati OBD2 in tempo reale e li salva su CSV nella cartella data/.
Premi Ctrl+C per fermare.
"""

import csv
import os
import time
import datetime
import obd
import config
from utils import connect


def build_commands():
    commands = []
    for name in config.LIVE_PIDS:
        cmd = getattr(obd.commands, name, None)
        if cmd is None:
            print(f"[WARN] PID sconosciuto in config.py: '{name}' — ignorato")
        else:
            commands.append(cmd)
    return commands


def filter_supported(connection, commands):
    supported = [cmd for cmd in commands if connection.supports(cmd)]
    unsupported = [cmd.name for cmd in commands if not connection.supports(cmd)]
    if unsupported:
        print(f"[WARN] PID non supportati da questa auto: {', '.join(unsupported)}")
    print(f"[INFO] Lettura di {len(supported)} PID: {', '.join(c.name for c in supported)}\n")
    return supported


def read_loop(connection, commands):
    os.makedirs(config.LOG_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(config.LOG_DIR, f"obd_{timestamp}.csv")

    fieldnames = ["timestamp"] + [cmd.name for cmd in commands]

    with open(log_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        print(f"Logging su '{log_file}' — Ctrl+C per fermare\n")
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

    print(f"Dati salvati in: {log_file}")


def main():
    connection = connect()
    if connection is None:
        return

    commands = build_commands()
    supported = filter_supported(connection, commands)
    if not supported:
        print("[ERRORE] Nessuno dei PID configurati e' supportato. Esegui scan_pids.py prima.")
        connection.close()
        return

    read_loop(connection, supported)
    connection.close()


if __name__ == "__main__":
    main()
