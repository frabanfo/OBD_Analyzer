# OBD2 connection settings
# Change PORT to match your adapter:
#   - USB/ELM327:  "COM3", "COM4", etc. (check Device Manager on Windows)
#   - Bluetooth:   "COM5", "COM6", etc. (pair first, then check Device Manager)
#   - Auto-detect: leave as None

PORT = "COM3"        # COM3 = outgoing BT (se non funziona prova COM4)
BAUDRATE = 38400     # 38400 or 115200 depending on adapter
FAST = True          # True = più veloce, False = più compatibile
TIMEOUT = 30         # seconds to wait for connection

# Log output
LOG_DIR = "data"     # cartella dove vengono salvati i CSV
SCAN_INTERVAL = 1.0  # seconds between reads in live mode

# Mock mode (sviluppo senza auto)
MOCK_MODE = False    # True = dati simulati, False = connessione OBD reale

# Motore (usato per stima potenza)
ENGINE_DISPLACEMENT_CC = 1390   # cilindrata in cc (Polo V 1.4 16V = 1390)
ENGINE_MAX_CV = 85               # solo per riferimento visivo sul grafico

# Gomme
TIRE_SIZE = "195/55 R15"        # taglia montata — solo riferimento

# Dashboard
DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8050
DISPLAY_INTERVAL_MS = 500   # ms refresh UI (indipendente dalla lettura OBD)
BUFFER_SIZE = 300    # punti dati massimi nel buffer (5 min a 1Hz)
GRAPH_WINDOW = 120   # secondi visibili nel grafico
BRAKING_SMOOTH = 5   # punti per smoothing derivata velocità

# PID da leggere in modalita' live (nomi dei comandi obd.commands.*)
# Scopri quali supporta la tua auto eseguendo scan_pids.py
LIVE_PIDS = [
    "RPM",
    "SPEED",
    "ENGINE_LOAD",
    "COOLANT_TEMP",
    "INTAKE_TEMP",
    "INTAKE_PRESSURE",
    "THROTTLE_POS",
    "TIMING_ADVANCE",
    "O2_B1S1",
    "O2_B1S2",
    "SHORT_FUEL_TRIM_1",
    "LONG_FUEL_TRIM_1",
    "DISTANCE_W_MIL",
]
