# utils/oil_return_checker.py

def check_oil_velocity(network_type, velocity_m_s, is_riser=False):
    """
    Check if the velocity is sufficient for oil return.

    For horizontal suction/discharge: minimum 4.0 m/s
    For vertical risers (suction/discharge): minimum 7.0 m/s
    For other types: no strict minimum

    Returns:
        (bool, str): Tuple of (is_ok, message)
    """
    if network_type in ["Dry Suction", "Discharge"]:
        if is_riser and velocity_m_s < 7.0:
            return False, "Velocity too low for oil return (vertical riser)"
        elif not is_riser and velocity_m_s < 4.0:
            return False, "Velocity too low for oil return (horizontal)"
    return True, "OK"
