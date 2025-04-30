# utils/pipe_sizing.py

from utils.refrigerant_properties import get_refrigerant_properties
from utils.pipe_length_volume_calc import calculate_internal_area
from utils.friction_calculations import calculate_friction_pressure_drop, fittings_equivalent_length_m
from utils.oil_return_checker import check_oil_return_velocity

def calculate_mass_flow(evap_capacity_kw, refrigerant, evap_temp, superheat_K, cond_temp, subcooling_K):
    # Get enthalpy of subcooled liquid (condenser outlet)
    t_subcooled = cond_temp - subcooling_K
    props_liquid = get_refrigerant_properties(refrigerant, t_subcooled)
    h_liquid_subcooled = props_liquid["enthalpy_liquid"]

    # Saturated vapor enthalpy at evaporating temp
    props_evap = get_refrigerant_properties(refrigerant, evap_temp)
    h_vapor_sat = props_evap["enthalpy_vapor"]

    # Estimate Cp from 10K rise (VB logic)
    props_evap_10K = get_refrigerant_properties(refrigerant, evap_temp + 10)
    h_vapor_plus10 = props_evap_10K["enthalpy_vapor"]
    cp_vapor = (h_vapor_plus10 - h_vapor_sat) / 10

    # Superheat enthalpy contribution
    delta_h_superheat = cp_vapor * superheat_K

    # Total delta h = superheat + latent (based on subcooled liquid)
    delta_h_total = (h_vapor_sat + delta_h_superheat) - h_liquid_subcooled

    if delta_h_total <= 0:
        raise ValueError("Calculated Δh is non-positive — check temperature inputs.")

    m_dot = evap_capacity_kw / delta_h_total  # kg/s

    return m_dot, delta_h_total


def size_pipe(m_dot, refrigerant, pipe_type, length_m, fittings_list, vertical_rise_m, fixed_pipe_size=None):
    pipe_options = fittings_equivalent_length_m(material="Copper ACR")  # or EN, Steel...

    selected_pipe = None
    for pipe in pipe_options:
        internal_diameter = pipe["ID_mm"] / 1000  # m
        area = calculate_internal_area(internal_diameter)

        velocity = m_dot / (area * pipe["density_kg_per_m3"])

        if fixed_pipe_size:
            if pipe["Nominal Size (inch)"] == fixed_pipe_size:
                selected_pipe = pipe
                break
        else:
            if 3 < velocity < 15:
                selected_pipe = pipe
                break

    if not selected_pipe:
        raise Exception("No suitable pipe found.")

    pressure_drop = calculate_friction_pressure_drop(
        m_dot, selected_pipe["ID_mm"] / 1000, length_m, fittings_list
    )

    oil_ok = check_oil_return_velocity(velocity, pipe_type, vertical_rise_m)

    return {
        "selected_pipe": selected_pipe,
        "velocity_m_s": velocity,
        "pressure_drop_kPa": pressure_drop,
        "mass_flow_kg_s": m_dot,
        "oil_return_ok": oil_ok,
    }