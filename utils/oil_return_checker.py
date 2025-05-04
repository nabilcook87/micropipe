from utils.refrigerant_properties import RefrigerantProperties

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

def get_base_min_flow(refrigerant):
    base_min_flows = {
        "R22": 0.010,     # in kg/s
        "R134a": 0.010,
        "R404A": 0.012,
        "R407C": 0.010,
        "R407F": 0.012,
        "R410A": 0.011,
        "R507A": 0.012,
        "R744": 0.015,
        "R448A": 0.012,
        "R449A": 0.012,
        "R32": 0.010,
        "R454A": 0.010
    }
    return base_min_flows.get(refrigerant.strip(), 0.010)

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

def check_oil_return(pipe_size_inch, refrigerant, evap_capacity_kw, evap_temp, cond_temp, superheat, subcool, duty_percentage=100.0):
    props = RefrigerantProperties()

    h_inlet = props.get_properties(refrigerant, cond_temp - subcool)["enthalpy_liquid"]
    h_evap = props.get_properties(refrigerant, evap_temp)["enthalpy_vapor"]
    h_evap_plus10 = props.get_properties(refrigerant, evap_temp + 10)["enthalpy_vapor"]
    cp_vap = (h_evap_plus10 - h_evap) / 10
    h_exit = h_evap + superheat * cp_vap

    delta_h = h_exit - h_inlet  # in kJ/kg
    if delta_h <= 0:
        return False, "Invalid enthalpy difference (Δh <= 0)"

    mass_flow_kg_s = evap_capacity_kw / delta_h
    scaled_flow = mass_flow_kg_s * get_scaling_factor(refrigerant) * (duty_percentage / 100.0)

    base_min = get_base_min_flow(refrigerant)
    cf = get_correction_factor(pipe_size_inch)
    if cf is None:
        return False, f"No correction factor for pipe size '{pipe_size_inch}'"

    min_required_flow = base_min * cf

    if scaled_flow >= min_required_flow:
        return True, f"OK: {scaled_flow:.3f} kg/s ≥ {min_required_flow:.3f} kg/s"
    else:
        return False, f"Insufficient flow ({scaled_flow:.3f} < {min_required_flow:.3f} kg/s)"
