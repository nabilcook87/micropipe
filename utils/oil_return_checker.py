# utils/oil_return_checker.py

def get_correction_factor(pipe_size_inch):
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


def get_min_kW(refrigerant):
    """
    Minimum required kW for oil return based on refrigerant.
    """
    return {
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
    }.get(refrigerant, 1.0)


def get_massflow_scaling_factor(refrigerant):
    """
    Legacy VB-style multiplier used to convert kW to an equivalent scaled mass flow.
    """
    return {
        "R22": 1.00,
        "R134a": 0.98,
        "R404A": 1.04,
        "R407C": 1.00,
        "R407F": 1.04,
        "R410A": 1.03,
        "R507A": 1.04,
        "R744": 1.20,
        "R448A": 1.04,
        "R449A": 1.04,
        "R32": 1.00,
        "R454A": 1.00
    }.get(refrigerant, 1.0)


def check_oil_velocity(pipe_size_inch, refrigerant, actual_duty_kw):
    """
    Check oil return based on corrected VB logic: (scaled_kW * correction factor) ≥ min_kW

    Parameters:
        pipe_size_inch (str): Pipe nominal size
        refrigerant (str): Refrigerant name
        actual_duty_kw (float): Actual duty in kW

    Returns:
        (bool, str): (is_ok, message)
    """
    cf = get_correction_factor(pipe_size_inch)
    if cf is None:
        return False, f"No correction factor for pipe size {pipe_size_inch}"

    min_kW = get_min_kW(refrigerant)
    multiplier = get_massflow_scaling_factor(refrigerant)

    # Convert duty (kW) to a pseudo-flow using legacy VB scaling
    scaled_duty_product = actual_duty_kw * multiplier * cf

    if scaled_duty_product >= min_kW:
        return True, f"OK: {scaled_duty_product:.2f} ≥ {min_kW:.2f}"
    else:
        return False, f"Insufficient flow for oil return ({scaled_duty_product:.2f} < {min_kW:.2f})"
