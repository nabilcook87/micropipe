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
    return correction_factors.get(pipe_size_inch.strip())

def get_base_min_duty(refrigerant):
    base_min_duties = {
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
    return base_min_duties.get(refrigerant.strip(), 1.0)

def get_scaling_factor(refrigerant):
    scaling_factors = {
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
    }
    return scaling_factors.get(refrigerant.strip(), 1.0)

def check_oil_return(pipe_size_inch, refrigerant, evap_capacity_kw, duty_percentage=100.0):
    cf = get_correction_factor(pipe_size_inch)
    if cf is None:
        return False, f"No correction factor for pipe size {pipe_size_inch}"

    base_min_duty = get_base_min_duty(refrigerant)
    scaling_factor = get_scaling_factor(refrigerant)

    effective_flow = evap_capacity_kw * (duty_percentage / 100.0) * scaling_factor
    min_required_flow = base_min_duty * cf

    if effective_flow >= min_required_flow:
        return True, f"OK: {effective_flow:.2f} ≥ {min_required_flow:.2f}"
    else:
        return False, f"Insufficient flow for oil return ({effective_flow:.2f} < {min_required_flow:.2f})"
