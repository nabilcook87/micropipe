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
    return correction_factors.get(str(pipe_size_inch).strip(), None)


def get_min_duty(refrigerant):
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
    }.get(refrigerant.strip(), 1.0)


def get_massflow_scaling_factor(refrigerant):
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
    }.get(refrigerant.strip(), 1.0)


def check_oil_velocity(pipe_size_inch, refrigerant, evap_capacity_kw, required_oil_duty_pct=100.0):
    """
    Final version mimicking legacy VB software:
    - Applies scaling factor (kW → flow representation)
    - Multiplies by correction factor (pipe size)
    - Compares to min duty threshold
    """
    cf = get_correction_factor(pipe_size_inch)
    if cf is None:
        return False, f"No correction factor for pipe size {pipe_size_inch}"

    scale = get_massflow_scaling_factor(refrigerant)
    min_required = get_min_duty(refrigerant)

    adjusted_kw = evap_capacity_kw * (required_oil_duty_pct / 100.0)
    effective_value = adjusted_kw * scale * cf

    if effective_value >= min_required:
        return True, f"OK: {effective_value:.2f} ≥ {min_required:.2f}"
    else:
        return False, f"Insufficient flow for oil return ({effective_value:.2f} < {min_required:.2f})"
