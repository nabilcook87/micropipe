# utils/pipe_sizing.py

from utils.refrigerant_properties import RefrigerantProperties
from utils.friction_calculations import get_equivalent_length
from utils.system_pressure_checker import check_pipe_rating
from utils.oil_return_checker import check_oil_velocity

import math

class PipeSizer:
    def __init__(self):
        self.refrigerant_props = RefrigerantProperties()
        self.pipe_table = self.load_pipe_table()

    def load_pipe_table(self):
        import pandas as pd
        return pd.read_csv("data/pipe_pressure_ratings_full.csv")

    def size_pipe(self, refrigerant, pipe_type, T_evap, T_cond, superheat, subcooling,
                  length_m, capacity_kw, fixed_pipe_size, vertical_rise_m, fittings_equiv_length_m):
        props = self.refrigerant_props.get_properties(refrigerant, T_evap)

        # Use subcooling and superheat logic
        h_vap_base = self.refrigerant_props.get_properties(refrigerant, T_evap)["h_vapor"]
        h_vap_plus10 = self.refrigerant_props.get_properties(refrigerant, T_evap + 10)["h_vapor"]
        cp_vapor = (h_vap_plus10 - h_vap_base) / 10
        delta_h_superheat = cp_vapor * superheat

        h_liquid_subcooled = self.refrigerant_props.get_properties(refrigerant, T_cond - subcooling)["h_liquid"]

        delta_h_total = h_vap_base + delta_h_superheat - h_liquid_subcooled  # kJ/kg
        m_dot = (capacity_kw * 1000) / (delta_h_total * 1000)  # kg/s

        pipe_options = []

        for _, row in self.pipe_table.iterrows():
            if fixed_pipe_size and row["Nominal Size (inch)"] != fixed_pipe_size:
                continue

            ID_m = row["ID_mm"] / 1000.0
            area = math.pi * (ID_m / 2) ** 2
            velocity = m_dot / (props["density_vapor"] * area) if pipe_type in ["Dry Suction", "Discharge"] else m_dot / (props["density_liquid"] * area)

            # Darcy friction factor approx (fully turbulent, smooth pipe): f ≈ 0.3164 / Re^0.25 — we simplify
            equiv_length = length_m + fittings_equiv_length_m
            reynolds = (props["density_vapor"] * velocity * ID_m) / props["viscosity"] if pipe_type in ["Dry Suction", "Discharge"] else (props["density_liquid"] * velocity * ID_m) / props["viscosity"]

            friction_factor = 0.3164 / (reynolds ** 0.25)
            pressure_drop = (friction_factor * equiv_length / ID_m) * 0.5 * props["density_vapor"] * velocity ** 2 / 1000  # in kPa

            # Static head loss/gain
            g = 9.81
            delta_p_static = props["density_vapor"] * g * vertical_rise_m / 1000 if pipe_type in ["Dry Suction", "Discharge"] else props["density_liquid"] * g * vertical_rise_m / 1000
            total_delta_p = pressure_drop + delta_p_static

            # Check pressure rating
            pressure_ok = check_pipe_rating(row, T_cond)

            # Check oil velocity
            oil_ok = check_oil_velocity(pipe_type, velocity)

            pipe_options.append({
                "Nominal Size (inch)": row["Nominal Size (inch)"],
                "ID_mm": row["ID_mm"],
                "velocity_m_s": velocity,
                "pressure_drop_total_kpa": total_delta_p,
                "reynolds": reynolds,
                "oil_velocity_ok": oil_ok,
                "pressure_rating_ok": pressure_ok
            })

        if not pipe_options:
            raise ValueError("No suitable pipe sizes found.")

        # Choose smallest pipe that satisfies velocity and pressure constraints
        for option in pipe_options:
            if option["oil_velocity_ok"] and option["pressure_rating_ok"]:
                return {
                    "selected_pipe": {
                        "Nominal Size (inch)": option["Nominal Size (inch)"],
                        "ID_mm": option["ID_mm"]
                    },
                    "velocity_m_s": option["velocity_m_s"],
                    "pressure_drop_total_kpa": option["pressure_drop_total_kpa"]
                }

        raise ValueError("No pipe size meets oil velocity and pressure rating requirements.")
