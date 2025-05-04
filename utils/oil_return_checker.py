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


def get_min_duty(refrigerant):
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


def check_oil_velocity(pipe_size_inch, refrigerant, evap_capacity_kw, required_oil_duty_pct=100.0):
    """
    Checks oil return using legacy Micropipe logic.
    Correct condition: Scaled duty × CF ≥ min required duty
    """
    cf = get_correction_factor(pipe_size_inch)
    if cf is None:
        return False, f"No correction factor for pipe size {pipe_size_inch}"

    min_duty = get_min_duty(refrigerant)
    effective_duty = evap_capacity_kw * (required_oil_duty_pct / 100.0) * cf

    if effective_duty >= min_duty:
        return True, f"OK: {effective_duty:.2f} ≥ {min_duty:.2f}"
    else:
        return False, f"Insufficient flow for oil return ({effective_duty:.2f} < {min_duty:.2f})"
