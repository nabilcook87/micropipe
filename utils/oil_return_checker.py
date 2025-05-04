# utils/oil_return_checker.py

def get_correction_factor(pipe_size_inch):
    """
    Return correction factor from legacy VB logic based on suction riser size (inch).
    These are extracted from VB's CorrectionFactorData function.
    """
    correction_factors = {
        "1/4": 0.10,
        "3/8": 0.15,
        "1/2": 0.20,
        "5/8": 0.35,
        "3/4": 0.60,
        "7/8": 0.85,
        "1-1/8": 1.40,
        "1-3/8": 2.00,
        "1-5/8": 2.80,
        "2-1/8": 5.30,
        "2-5/8": 8.50,
        "3-1/8": 13.20,
        "3-5/8": 18.50,
        "4-1/8": 24.70
    }
    return correction_factors.get(str(pipe_size_inch), None)


def get_min_duty(refrigerant):
    """
    Return minimum duty for oil return from legacy VB logic based on refrigerant type.
    These values come from DRMinCapacity.
    """
    min_duty_values = {
        "R22": 1.0,
        "R134a": 1.0,
        "R404A": 1.2,
        "R407C": 1.0,
        "R407F": 1.2,
        "R410A": 1.1,
        "R507A": 1.2,
        "R744": 1.5,
        "R448A": 1.2,
        "R449A": 1.2,
        "R32": 1.0,
        "R454A": 1.0
    }
    return min_duty_values.get(refrigerant, 1.0)


def check_oil_velocity(pipe_size_inch, refrigerant, velocity_m_s):
    """
    Check if the oil return condition is satisfied using VB-style logic:
    velocity × correction factor ≥ refrigerant-specific minimum duty.

    Parameters:
        pipe_size_inch (str): Pipe nominal size
        refrigerant (str): Refrigerant name
        velocity_m_s (float): Refrigerant velocity in m/s

    Returns:
        (bool, str): (is_ok, message)
    """
    cf = get_correction_factor(pipe_size_inch)
    if cf is None:
        return False, f"No correction factor for pipe size {pipe_size_inch}"

    min_duty = get_min_duty(refrigerant)

    product = velocity_m_s * cf

    if product >= min_duty:
        return True, f"OK: {product:.2f} ≥ {min_duty:.2f}"
    else:
        return False, f"Insufficient flow for oil return ({product:.2f} < {min_duty:.2f})"
