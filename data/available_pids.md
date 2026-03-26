# PID disponibili — scansione 2026-03-26

**Adattatore:** ELM327 v2.3
**Tensione:** 11.2V
**Standard:** EOBD (Europe)
**Errori DTC:** nessuno

---

## PID supportati (19)

| Nome | Valore rilevato | Unità |
|---|---|---|
| PIDS_A | 10111110001111101011100000010001 | bitmask |
| PIDS_B | 10000000000000000000000000000000 | bitmask |
| STATUS | — | oggetto stato |
| FUEL_STATUS | Open loop due to engine load OR fuel cut due to deceleration | — |
| ENGINE_LOAD | 0.0 | percent |
| COOLANT_TEMP | 66 | °C |
| SHORT_FUEL_TRIM_1 | 0.0 | percent |
| LONG_FUEL_TRIM_1 | -23.44 | percent |
| INTAKE_PRESSURE | 98 | kPa |
| RPM | 0.0 | rpm |
| SPEED | 0.0 | km/h |
| TIMING_ADVANCE | -5.0 | ° |
| INTAKE_TEMP | 31 | °C |
| THROTTLE_POS | 7.06 | percent |
| O2_SENSORS | — | bitmask sensori |
| O2_B1S1 | 0.06 | V |
| O2_B1S2 | 0.01 | V |
| OBD_COMPLIANCE | EOBD (Europe) | — |
| DISTANCE_W_MIL | 0.0 | km |

---

## PID non disponibili su questo veicolo

| Nome | Note |
|---|---|
| MAF | Massa aria — non presente |
| FUEL_LEVEL | Livello carburante — non presente |
| VIN | Non supportato da obd==0.7.1 |

---

## Note

- RPM e SPEED a 0.0 perché rilevati a motore spento (quadro in ACC)
- LONG_FUEL_TRIM_1 a -23.44% indica una correzione carburante significativa — da monitorare a motore caldo
- DISTANCE_W_MIL = km percorsi con MIL (spia guasto) accesa — attualmente 0
