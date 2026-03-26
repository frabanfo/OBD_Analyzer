"""
utils.py
Funzioni condivise tra scan_pids.py e live_reader.py.
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
        print("  - Assicurati che il motore sia acceso o in modalita' ACC")
        return None
    print(f"[OK] Connesso su {connection.port_name()}\n")
    return connection
