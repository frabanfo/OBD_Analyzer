# OBD2 connection settings
# Change PORT to match your adapter:
#   - USB/ELM327:  "COM3", "COM4", etc. (check Device Manager on Windows)
#   - Bluetooth:   "COM5", "COM6", etc. (pair first, then check Device Manager)
#   - Auto-detect: leave as None

PORT = None          # None = auto-detect
BAUDRATE = 38400     # 38400 or 115200 depending on adapter
FAST = False         # False = more compatible (try True if it works)
TIMEOUT = 30         # seconds to wait for connection

# Log output
LOG_FILE = "obd_data.csv"
SCAN_INTERVAL = 1.0  # seconds between reads in live mode
