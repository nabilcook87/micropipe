# utils/pipe_length_volume_calc.py

import math
import pandas as pd

def calculate_pipe_volume_liters(diameter_mm, length_m):
    """
    Calculate internal volume of a cylindrical pipe in liters.

    Parameters:
        diameter_mm (float): Internal diameter in millimeters
        length_m (float): Length of the pipe in meters

    Returns:
        float: Volume in liters
    """
    diameter_m = diameter_mm / 1000.0
    radius_m = diameter_m / 2
    area_m2 = math.pi * radius_m ** 2
    volume_m3 = area_m2 * length_m
    return volume_m3 * 1000  # Convert to liters

def get_pipe_id_mm(nominal_size_inch):
    """
    Return the internal diameter (ID) in mm for a given nominal pipe size (inch)
    using the pipe pressure ratings table.
    
    Parameters:
        nominal_size_inch (str or float): Nominal pipe size as string (e.g., "1-1/8") or float
    
    Returns:
        float or None: ID in mm, or None if not found
    """
    try:
        df = pd.read_csv("data/pipe_pressure_ratings_full.csv")
        match = df[df["Nominal Size (inch)"].astype(str).str.strip() == str(nominal_size_inch).strip()]
        if not match.empty and "ID_mm" in match.columns:
            return match.iloc[0]["ID_mm"]
    except Exception:
        pass
    return None
