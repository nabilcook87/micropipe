# utils/oil_return_checker.py

import math
from utils.refrigerant_properties import RefrigerantProperties
from utils.pipe_length_volume_calc import get_pipe_id_mm

def check_oil_velocity(pipe_size_inch, refrigerant, mass_flow_kg_s, required_oil_duty_pct):
    """
    Check if velocity is sufficient for oil return based on legacy VB logic.

    Parameters:
        pipe_size_inch (str): Nominal pipe size (e.g. "7/8")
        refrigerant (str): Refrigerant name
        mass_flow_kg_s (float): Refrigerant mass flow rate [kg/s]
        required_oil_duty_pct (float): Required oil return duty as percent (0–100)

    Returns:
        (bool, str): Tuple of (is_ok, message)
    """
    try:
        # Get pipe ID
        ID_mm = get_pipe_id_mm(pipe_size_inch)
        if ID_mm is None:
            return False, f"Unknown pipe size: {pipe_size_inch}"
        
        ID_m = ID_mm / 1000
        area_m2 = math.pi * (ID_m / 2) ** 2

        if area_m2 <= 0:
            return False, "Invalid pipe area"

        # Get density of saturated vapor
        props = RefrigerantProperties().get_properties(refrigerant, -10)  # Assume evap temp -10°C
        density = props.get("density_vapor", 5.0) or 5.0  # fallback default

        # Velocity (m/s)
        velocity = mass_flow_kg_s / (area_m2 * density)

        # Required minimum velocity (from VB logic)
        velocity_min = 0.15 * required_oil_duty_pct + 2.0

        if velocity < velocity_min:
            return False, f"Velocity too low for oil return ({velocity:.2f} m/s < {velocity_min:.2f} m/s)"
        else:
            return True, f"Velocity OK ({velocity:.2f} m/s ≥ {velocity_min:.2f} m/s)"

    except Exception as e:
        return False, f"Error: {e}"
