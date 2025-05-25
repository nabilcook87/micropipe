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
        data = self.refrigerant_props.tables[refrigerant]
        temps = np.array(data["temperature_C"])
        pressures_kPa = np.array(data["pressure_bar"]) * 100

        if not (temps[0] <= sat_temp_C <= temps[-1]):
            return 0.0

        dp_dT_array = np.empty_like(temps, dtype=float)
        dp_dT_array[:-1] = np.diff(pressures_kPa) / np.diff(temps)
        dp_dT_array[-1] = dp_dT_array[-2]  # Extend final slope

        dp_dT = np.interp(sat_temp_C, temps, dp_dT_array)

        if abs(dp_dT) < 1e-6:
            return 0.0

        return pressure_drop_kPa / dp_dT

    def temp_penalty_to_pressure_drop(self, refrigerant, sat_temp_C, temp_penalty_K):
        data = self.refrigerant_props.tables[refrigerant]
        temps = np.array(data["temperature_C"])
        pressures_kPa = np.array(data["pressure_bar"]) * 100

        if not (temps[0] <= sat_temp_C <= temps[-1]):
            return 0.0

        dp_dT_array = np.empty_like(temps, dtype=float)
        dp_dT_array[:-1] = np.diff(pressures_kPa) / np.diff(temps)
        dp_dT_array[-1] = dp_dT_array[-2]  # Extend final slope

        dp_dT = np.interp(sat_temp_C, temps, dp_dT_array)

        if abs(dp_dT) < 1e-6:
            return 0.0

        return temp_penalty_K * dp_dT
