# utils/oil_return_checker.py

def check_oil_velocity(network_type, velocity_m_s):
    """
    Check if the velocity is sufficient for oil return.
    
    For horizontal sections (Dry Suction, Discharge): minimum 4.0 m/s
    For vertical risers: minimum 7.0 m/s
    
    Returns:
        (bool, str): Tuple of (is_ok, message)
    """
    if network_type in ["Dry Suction", "Discharge"]:
        if velocity_m_s < 4.0:
            return False, "Velocity too low for oil return (horizontal)"
    if network_type == "Vertical Rise":
        if velocity_m_s < 7.0:
            return False, "Velocity too low for oil return (vertical)"
    return True, "OK"
