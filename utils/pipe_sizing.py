# utils/pipe_sizing.py

from utils.refrigerant_properties import RefrigerantProperties
from utils.friction_calculations import get_equivalent_length
from utils.pipe_length_volume_calc import calculate_pipe_volume_liters
from utils.system_pressure_checker import is_pressure_within_rating
from utils.oil_return_checker import check_oil_return_velocity
import math

class PipeSizer:
    def __init__(self):
        self.refrigerant_props = RefrigerantProperties()
        self.pipes = self._load_pipe_table()

    def _load_pipe_table(self):
        import pandas as pd
        import os
        pipe_data_path = os.path.join("data", "pipe_pressure_ratings_full.csv")
        return pd.read_csv(pipe_data_path).to_dict("records")

    def size_pipe(self, refrigerant, pipe_type, T_evap, T_cond, superheat_K, subcooling_K,
                  length_m, capacity_kw, fixed_size, vertical_rise_m, fittings_equiv_length_m):
        
        props_evap = self.refrigerant_props.get_properties(refrigerant, T_evap)
        props_evap_superheat = self.refrigerant_props.get_properties(refrigerant, T_evap + superheat_K)
        props_cond = self.refrigerant_props.get_properties(refrigerant, T_cond)
        props_cond_subcool = self.refrigerant_props.get_properties(refrigerant, T_cond - subcooling_K)

        if pipe_type in ["Dry Suction", "Discharge"]:
            delta_h = (props_evap_superheat["h_vapor"] - props_evap["h_vapor"])
            delta_h += props_evap_superheat["Cp_vapor"] * superheat_K
            rho = props_evap["density_vapor"]
        else:
            delta_h = props_cond["h_liquid"] - props_cond_subcool["h_liquid"]
            rho = props_cond_subcool["density_liquid"]

        mass_flow_kg_s = capacity_kw * 1000 / delta_h  # Q = m * Δh

        candidate_pipes = []
        for pipe in self.pipes:
            if fixed_size and pipe["Nominal Size (inch)"] != fixed_size:
                continue

            ID_m = pipe["ID_mm"] / 1000
            area_m2 = math.pi * (ID_m / 2) ** 2
            velocity = mass_flow_kg_s / (rho * area_m2)

            friction_factor = 0.02  # Assume turbulent for now
            equiv_length = length_m + fittings_equiv_length_m
            pressure_drop_pa_per_m = friction_factor * (length_m + fittings_equiv_length_m) * (rho * velocity**2) / (2 * ID_m)
            pressure_drop_total_pa = pressure_drop_pa_per_m + rho * 9.81 * vertical_rise_m
            pressure_drop_kpa = pressure_drop_total_pa / 1000

            oil_ok = check_oil_return_velocity(pipe_type, velocity, vertical_rise_m)

            rating_ok = is_pressure_within_rating(
                pipe["Nominal Size (inch)"],
                pipe["Schedule"],
                pipe_type,
                T_cond
            )

            candidate_pipes.append({
                "pipe": pipe,
                "velocity_m_s": velocity,
                "pressure_drop_total_kpa": pressure_drop_kpa,
                "oil_ok": oil_ok,
                "rating_ok": rating_ok
            })

        valid = [c for c in candidate_pipes if c["oil_ok"] and c["rating_ok"]]
        if not valid:
            raise ValueError("No valid pipe size found that meets oil return and pressure rating requirements.")

        best = min(valid, key=lambda x: x["velocity_m_s"])
        return {
            "selected_pipe": best["pipe"],
            "velocity_m_s": best["velocity_m_s"],
            "pressure_drop_total_kpa": best["pressure_drop_total_kpa"],
            "mass_flow_kg_s": mass_flow_kg_s
        }
