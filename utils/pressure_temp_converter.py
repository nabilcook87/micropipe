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
        Accurate dp/dT using central difference on interpolated pressure data.
        """
        eps = 0.01  # Small step in °C

        temps = np.array(self.refrigerant_props.tables[refrigerant]["temperature_C"])
        pressures = np.array(self.refrigerant_props.tables[refrigerant]["pressure_bar"]) * 100  # bar to kPa

        # Use numpy interpolation directly
        p_low = np.interp(sat_temp_C - eps, temps, pressures)
        p_high = np.interp(sat_temp_C + eps, temps, pressures)

        dp_dT = (p_high - p_low) / (2 * eps)

        if dp_dT == 0:
            return 0.0

        return pressure_drop_kPa / dp_dT

    def temp_penalty_to_pressure_drop(self, refrigerant, sat_temp_C, temp_penalty_K):
        """
        Accurate dp/dT using central difference on interpolated pressure data.
        """
        eps = 0.01

        temps = np.array(self.refrigerant_props.tables[refrigerant]["temperature_C"])
        pressures = np.array(self.refrigerant_props.tables[refrigerant]["pressure_bar"]) * 100  # bar to kPa

        p_low = np.interp(sat_temp_C - eps, temps, pressures)
        p_high = np.interp(sat_temp_C + eps, temps, pressures)

        dp_dT = (p_high - p_low) / (2 * eps)

        return temp_penalty_K * dp_dT
