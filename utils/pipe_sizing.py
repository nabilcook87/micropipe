from utils.refrigerant_properties import RefrigerantProperties
from utils.pressure_temp_converter import PressureTemperatureConverter
from utils.system_pressure_checker import check_pipe_rating
from utils.oil_return_checker import check_oil_velocity
from utils.pipe_length_volume_calc import PipeLengthVolumeCalculator
from utils.friction_calculations import get_equivalent_length
import math

class PipeSizer:
    def __init__(self):
        self.refrigerant_props = RefrigerantProperties()
        self.temp_converter = PressureTemperatureConverter()
        self.volume_calc = PipeLengthVolumeCalculator()

    def size_pipe(self, refrigerant, pipe_type, T_evap, T_cond, superheat_K, subcool_K,
                  straight_length_m, capacity_kw, fixed_pipe_size=None,
                  vertical_rise_m=0.0, fittings_equivalent_length_m=0.0):

        props_evap = self.refrigerant_props.get_properties(refrigerant, T_evap)
        props_cond = self.refrigerant_props.get_properties(refrigerant, T_cond)

        h_vap_start = props_evap["h_vapor"]
        h_vap_end = self.refrigerant_props.get_properties(refrigerant, T_evap + 10)["h_vapor"]
        Cp = (h_vap_end - h_vap_start) / 10
        h_total = h_vap_start + Cp * superheat_K - props_cond["h_liquid"] + subcool_K * props_cond["Cp_liquid"]

        mass_flow_kg_s = (capacity_kw * 1000) / h_total

        pipe_table = self.refrigerant_props.get_pipe_table()

        if fixed_pipe_size:
            pipe_options = [p for p in pipe_table if p["Nominal Size (inch)"] == fixed_pipe_size]
        else:
            pipe_options = pipe_table

        best_option = None

        for pipe in pipe_options:
            ID_m = pipe["ID_mm"] / 1000
            area_m2 = math.pi * (ID_m / 2) ** 2

            if pipe_type in ["Liquid", "Condenser Drain", "Pumped Refrigerant Liquid"]:
                density = props_cond["density_liquid"]
                viscosity = props_cond["viscosity_liquid"]
            else:
                density = props_evap["density_vapor"]
                viscosity = props_evap["viscosity_vapor"]

            velocity_m_s = mass_flow_kg_s / (density * area_m2)

            total_length_m = straight_length_m + fittings_equivalent_length_m
            friction_factor = 0.02
            pressure_drop_friction = (friction_factor * total_length_m * density * velocity_m_s ** 2) / (2 * ID_m)
            pressure_drop_vertical = density * 9.81 * vertical_rise_m
            pressure_drop_total_pa = pressure_drop_friction + pressure_drop_vertical
            pressure_drop_total_kpa = pressure_drop_total_pa / 1000

            pressure_rating_ok = check_pipe_rating(pipe["Nominal Size (inch)"], pipe["Schedule"], T_cond, pressure_drop_total_kpa)
            oil_ok = check_oil_velocity(pipe_type, velocity_m_s)

            if pressure_rating_ok and oil_ok:
                best_option = pipe
                break

        if not best_option:
            raise ValueError("No suitable pipe found")

        volume_liters = self.volume_calc.internal_volume_liters(best_option["ID_mm"], straight_length_m)

        return {
            "mass_flow_kg_s": mass_flow_kg_s,
            "velocity_m_s": velocity_m_s,
            "pressure_drop_total_kpa": pressure_drop_total_kpa,
            "selected_pipe": best_option,
            "internal_volume_liters": volume_liters
        }
