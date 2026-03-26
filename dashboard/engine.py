"""
engine.py
Stima di potenza e consumo carburante via speed density.
Condiviso tra dashboard (grafici) e trip_summary (accumulo viaggio).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

VE           = 0.80    # efficienza volumetrica media (WOT ~0.92, carico parziale ~0.70-0.80)
LHV_J_KG     = 43e6   # potere calorifico inferiore benzina (J/kg)
ETA_THERMAL  = 0.34   # rendimento termico
STOICH_AFR   = 14.7   # rapporto stechiometrico aria/carburante
FUEL_DENSITY = 0.74   # kg/L (benzina)
R_AIR        = 287.0  # J/(kg·K)


def _air_mass_s(rpm: float, map_kpa: float, intake_temp_c: float) -> float:
    """Portata massica aria aspirata (kg/s)."""
    T_K = (intake_temp_c or 25.0) + 273.15
    rho  = (map_kpa * 1000.0) / (R_AIR * T_K)
    return rho * (config.ENGINE_DISPLACEMENT_CC * 1e-6) * (rpm / 120.0) * VE


def estimate_power_cv(rpm: float, map_kpa: float, intake_temp_c: float) -> float:
    """Potenza istantanea stimata in CV."""
    if rpm <= 200 or not map_kpa:
        return 0.0
    fuel_s = _air_mass_s(rpm, map_kpa, intake_temp_c) / STOICH_AFR
    return round(max(0.0, fuel_s * LHV_J_KG * ETA_THERMAL / 1000.0 / 0.7355), 1)


def estimate_fuel_rate_lh(rpm: float, map_kpa: float, intake_temp_c: float) -> float:
    """Consumo istantaneo in L/h."""
    if rpm <= 200 or not map_kpa:
        return 0.0
    fuel_s = _air_mass_s(rpm, map_kpa, intake_temp_c) / STOICH_AFR
    return round(fuel_s / FUEL_DENSITY * 3600.0, 3)
