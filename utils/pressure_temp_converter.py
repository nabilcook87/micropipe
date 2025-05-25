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
        pressures_Pa = np.array(data["pressure_bar"]) * 1e5  # Convert to Pascals

        if not (temps[0] <= sat_temp_C <= temps[-1]):
            return 0.0

        # Compute log slopes
        lnP = np.log(pressures_Pa)
        dlnP_dT = np.diff(lnP) / np.diff(temps)
        slope_temps = temps[:-1]

        slope = np.interp(sat_temp_C, slope_temps, dlnP_dT)

        if abs(slope) < 1e-12:
            return 0.0

        delta_lnP = pressure_drop_kPa * 1e3 / np.interp(sat_temp_C, temps, pressures_Pa)
        delta_T = delta_lnP / slope

        return delta_T

    def temp_penalty_to_pressure_drop(self, refrigerant, sat_temp_C, temp_penalty_K):
        data = self.refrigerant_props.tables[refrigerant]
        temps = np.array(data["temperature_C"])
        pressures_Pa = np.array(data["pressure_bar"]) * 1e5  # Pascals

        if not (temps[0] <= sat_temp_C <= temps[-1]):
            return 0.0

        lnP = np.log(pressures_Pa)
        dlnP_dT = np.diff(lnP) / np.diff(temps)
        slope_temps = temps[:-1]

        slope = np.interp(sat_temp_C, slope_temps, dlnP_dT)

        if abs(slope) < 1e-12:
            return 0.0

        P = np.interp(sat_temp_C, temps, pressures_Pa)
        delta_lnP = slope * temp_penalty_K
        delta_P = P * (np.exp(delta_lnP) - 1)

        return delta_P / 1e3  # back to kPa
