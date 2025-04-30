def check_oil_return(velocity_m_per_s, orientation="horizontal"):
    """
    Check if the refrigerant velocity is sufficient to ensure oil return.

    Parameters:
    - velocity_m_per_s (float): Calculated velocity in the pipe (m/s)
    - orientation (str): "horizontal" or "vertical"

    Returns:
    - result (dict): {
        "required_velocity_m_per_s": float,
        "is_sufficient": bool,
        "note": str
      }
    """
    if orientation.lower() == "vertical":
        required_velocity = 7.0  # m/s for vertical risers
    else:
        required_velocity = 4.0  # m/s for horizontal runs

    is_sufficient = velocity_m_per_s >= required_velocity
    note = (
        "Velocity sufficient for oil return."
        if is_sufficient
        else f"Velocity too low for oil return — minimum {required_velocity} m/s required."
    )

    return {
        "required_velocity_m_per_s": required_velocity,
        "is_sufficient": is_sufficient,
        "note": note
    }
