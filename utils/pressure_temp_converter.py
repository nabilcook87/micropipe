# /utils/pressure_temp_converter.py

import numpy as np
from utils.refrigerant_properties import RefrigerantProperties

class PressureTemperatureConverter:
    def __init__(self):
        self.refrigerant_props = RefrigerantProperties()

    def pressure_to_temp(self, refrigerant, target_pressure_bar):
        """
        Find saturation temperature for a given pressure using interpolation.
        """
        data = self.refrigerant_props.tables[refrigerant]
        pressures = data["pressure_bar"]
        temperatures = data["temperature_C"]

        for i in range(len(pressures) - 1):
            if pressures[i] <= target_pressure_bar <= pressures[i + 1]:
                # Linear interpolation
                x1, x2 = pressures[i], pressures[i + 1]
                y1, y2 = temperatures[i], temperatures[i + 1]
                slope = (y2 - y1) / (x2 - x1)
                return y1 + slope * (target_pressure_bar - x1)

        # Outside range — clamp to min or max
        if target_pressure_bar < pressures[0]:
            return temperatures[0]
        else:
            return temperatures[-1]

    def temp_to_pressure(self, refrigerant, temperature_C):
        """
        Find saturation pressure for a given temperature.
        """
        return self.refrigerant_props.get_properties(refrigerant, temperature_C)["pressure_bar"]

    def pressure_drop_to_temp_penalty(self, refrigerant, sat_temp_C, pressure_drop_kPa):
        """
        Convert pressure drop to temperature penalty using dp/dT from coarse table data.
        """
        data = self.refrigerant_props.tables[refrigerant]
        temps = np.array(data["temperature_C"])
        pressures_kPa = np.array(data["pressure_bar"]) * 100

        # Interpolate pressure at T - 5 and T + 5 to compute a slope over a wider window
        t_low = max(sat_temp_C - 5, -50)
        t_high = min(sat_temp_C + 5, 60)

        if t_low < temps[0] or t_high > temps[-1]:
            return 0.0  # Outside bounds

        p_low = np.interp(t_low, temps, pressures_kPa)
        p_high = np.interp(t_high, temps, pressures_kPa)

        dp_dT = (p_high - p_low) / (10.0)

        if dp_dT == 0:
            return 0.0

        return pressure_drop_kPa / dp_dT

    def temp_penalty_to_pressure_drop(self, refrigerant, sat_temp_C, temp_penalty_K):
        """
        Convert temperature penalty to pressure drop using dp/dT from coarse table data.
        """
        data = self.refrigerant_props.tables[refrigerant]
        temps = np.array(data["temperature_C"])
        pressures_kPa = np.array(data["pressure_bar"]) * 100

        t_low = max(sat_temp_C - 5, -50)
        t_high = min(sat_temp_C + 5, 60)

        if t_low < temps[0] or t_high > temps[-1]:
            return 0.0

        p_low = np.interp(t_low, temps, pressures_kPa)
        p_high = np.interp(t_high, temps, pressures_kPa)

        dp_dT = (p_high - p_low) / (10.0)

        return temp_penalty_K * dp_dT
