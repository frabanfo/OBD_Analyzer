"""
scan_pids.py
Scansiona tutti i PID OBD2 supportati dalla tua auto e mostra i valori disponibili.
Esegui questo script per capire cosa riesce a leggere il tuo adattatore.
"""

import obd
import config


def connect():
    print(f"Connessione OBD2... (porta: {config.PORT or 'auto-detect'})")
    connection = obd.OBD(
        portstr=config.PORT,
        baudrate=config.BAUDRATE,
        fast=config.FAST,
        timeout=config.TIMEOUT,
    )
    if not connection.is_connected():
        print("\n[ERRORE] Impossibile connettersi all'adattatore OBD2.")
        print("  - Verifica che l'adattatore sia inserito nella porta OBD2")
        print("  - Controlla il numero di porta COM in config.py")
        print("  - Assicurati che il motore sia acceso o in modalità ACC")
        return None
    print(f"[OK] Connesso su {connection.port_name()}\n")
    return connection


def scan_supported_pids(connection):
    """Interroga tutti i comandi supportati e restituisce quelli con risposta valida."""
    print("=" * 60)
    print("PID SUPPORTATI DALLA TUA AUTO")
    print("=" * 60)

    supported = []
    unsupported = []

    for cmd in obd.commands[1]:  # Mode 01 = dati in tempo reale
        if connection.supports(cmd):
            response = connection.query(cmd)
            if not response.is_null():
                supported.append((cmd, response))
            else:
                unsupported.append(cmd)

    print(f"\nTotale PID trovati: {len(supported)}\n")

    for cmd, response in supported:
        value = response.value
        unit = ""
        if hasattr(value, "magnitude"):
            unit = f" {value.units}"
            value = round(value.magnitude, 2)
        print(f"  {cmd.name:<35} {str(value):<20}{unit}")

    if unsupported:
        print(f"\nPID dichiarati supportati ma senza risposta: {len(unsupported)}")
        for cmd in unsupported:
            print(f"  - {cmd.name}")

    return supported


def scan_dtc(connection):
    """Legge i Diagnostic Trouble Codes (errori memorizzati)."""
    print("\n" + "=" * 60)
    print("DIAGNOSTIC TROUBLE CODES (DTC)")
    print("=" * 60)

    response = connection.query(obd.commands.GET_DTC)
    if response.is_null() or not response.value:
        print("  Nessun errore memorizzato.")
    else:
        print(f"  {len(response.value)} codice/i trovato/i:")
        for code, description in response.value:
            print(f"  [{code}] {description}")


def print_vehicle_info(connection):
    """Legge informazioni generali sul veicolo."""
    print("\n" + "=" * 60)
    print("INFORMAZIONI VEICOLO")
    print("=" * 60)

    info_commands = [
        obd.commands.VIN,
        obd.commands.ELM_VERSION,
        obd.commands.ELM_VOLTAGE,
        obd.commands.FUEL_TYPE,
        obd.commands.OBD_COMPLIANCE,
    ]

    for cmd in info_commands:
        if connection.supports(cmd):
            response = connection.query(cmd)
            if not response.is_null():
                print(f"  {cmd.name:<30} {response.value}")


def main():
    connection = connect()
    if connection is None:
        return

    print_vehicle_info(connection)
    supported = scan_supported_pids(connection)
    scan_dtc(connection)

    print("\n" + "=" * 60)
    print("Scansione completata.")
    print(f"Usa live_reader.py per leggere i dati in tempo reale.")
    print("=" * 60)

    connection.close()


if __name__ == "__main__":
    main()
