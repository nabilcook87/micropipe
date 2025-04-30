# utils/pipe_length_volume_calc.py

import math

class PipeLengthVolumeCalculator:
    def __init__(self):
        pass

    def internal_volume_liters(self, diameter_mm, length_m):
        """Calculate internal volume of pipe (liters) given diameter and length."""
        diameter_m = diameter_mm / 1000
        area_m2 = math.pi * (diameter_m / 2) ** 2
        volume_m3 = area_m2 * length_m
        return volume_m3 * 1000  # Convert to liters

    def refrigerant_mass_kg(self, volume_liters, density_kg_m3):
        """Calculate mass of refrigerant inside the volume."""
        volume_m3 = volume_liters / 1000
        mass_kg = volume_m3 * density_kg_m3
        return mass_kg