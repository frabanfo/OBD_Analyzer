# OBD Analyzer

A real-time vehicle telemetry dashboard for OBD2-equipped cars, built with Python and Dash.
Connects to any ELM327 adapter (USB or Bluetooth) and displays live engine data, trip statistics, and estimated fuel consumption directly in the browser.

---

## Features

- Live dashboard with RPM, speed, throttle, engine load, coolant temperature, and more
- Automatic gear detection based on RPM/speed ratio, learned and refined over time
- Estimated power output (CV) based on intake pressure and engine displacement
- Trip tracking with distance, average speed, fuel consumption (L/100km), and estimated cost
- Trip history saved locally as JSON files
- Mock mode for development and testing without a physical OBD adapter

---

## Requirements

- Python 3.10 or higher
- An ELM327 adapter (USB or Bluetooth paired via Windows Device Manager)
- A vehicle with an OBD2 port (standard on most cars produced after 2001)

Install dependencies:

```
pip install -r requirements.txt
```

---

## Configuration

All settings are in `config.py`. The most relevant ones:

| Parameter | Description |
|---|---|
| `PORT` | COM port of the OBD adapter (e.g. `"COM3"`) |
| `BAUDRATE` | Serial baud rate (`38400` for most BT adapters) |
| `FAST` | Enable fast ELM327 protocol (`True` recommended, `False` if connection issues) |
| `MOCK_MODE` | `True` for simulated data, `False` for real OBD connection |
| `ENGINE_DISPLACEMENT_CC` | Engine displacement in cc, used for power estimation |
| `ENGINE_MAX_CV` | Max power in CV, used as chart reference |
| `TIRE_SIZE` | Mounted tire size, for reference |

---

## Usage

**Start the dashboard:**

```
python dashboard/app.py
```

Open `http://127.0.0.1:8050` in a browser. The dashboard connects to the OBD adapter automatically and begins streaming data.

**Scan supported PIDs (optional, first-time setup):**

```
python scan_pids.py
```

Use this to verify which OBD commands your vehicle supports before configuring `LIVE_PIDS` in `config.py`.

---

## Project Structure

```
OBD_Analyzer/
├── config.py               # All configuration parameters
├── scan_pids.py            # Utility to list supported OBD commands
├── utils.py                # OBD connection helper
├── dashboard/
│   ├── app.py              # Dash application and UI layout
│   ├── obd_thread.py       # Background OBD reader (async mode)
│   ├── data_buffer.py      # Thread-safe ring buffer for live data
│   ├── trip_summary.py     # Trip statistics accumulator
│   ├── gear_detector.py    # Gear estimation via RPM/speed clustering
│   ├── engine.py           # Fuel rate and power estimation
│   └── mock_obd.py         # Simulated OBD data source
└── data/
    ├── gear_profile.json   # Learned gear ratios (auto-generated)
    └── trips/              # Saved trip records (JSON)
```

---

## Bluetooth Setup (Windows)

1. Pair the ELM327 adapter in Windows Bluetooth settings.
2. Open Device Manager and find the COM port under "Standard Serial over Bluetooth link" (typically COM3 or COM4).
3. Set `PORT` in `config.py` to the outgoing port number.
4. Set `MOCK_MODE = False` and start the dashboard.

---

## Vehicle

Tested on a Volkswagen Polo V 1.4 16V (85 CV, 1390cc). Should work with any OBD2-compliant vehicle and ELM327 adapter.
