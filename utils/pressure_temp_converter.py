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

    def _dp_dT(self, temps, pressures_kPa, sat_temp_C):
        # Ensure inputs are sorted
        temps = np.array(temps)
        pressures_kPa = np.array(pressures_kPa)

        # Find the index where sat_temp_C would be inserted
        idx = np.searchsorted(temps, sat_temp_C)

        # Choose two nearest temperatures to form a valid slope
        if idx == 0:
            # sat_temp_C is below the range, use first two points
            t1, t2 = temps[0], temps[1]
        elif idx >= len(temps):
            # sat_temp_C is above the range, use last two points
            t1, t2 = temps[-2], temps[-1]
        else:
            # sat_temp_C is within range, pick closest neighbors
            t1, t2 = temps[idx - 1], temps[idx]

        p1 = np.interp(t1, temps, pressures_kPa)
        p2 = np.interp(t2, temps, pressures_kPa)

        if t2 == t1:
            return 0.0

        return (p2 - p1) / (t2 - t1)

    def pressure_drop_to_temp_penalty(self, refrigerant, sat_temp_C, pressure_drop_kPa):
        data = self.refrigerant_props.tables[refrigerant]
        temps = np.array(data["temperature_C"])
        pressures_kPa = np.array(data["pressure_bar"]) * 100

        dp_dT = self._dp_dT(temps, pressures_kPa, sat_temp_C)
        return pressure_drop_kPa / dp_dT if dp_dT != 0 else 0.0

    def temp_penalty_to_pressure_drop(self, refrigerant, sat_temp_C, temp_penalty_K):
        data = self.refrigerant_props.tables[refrigerant]
        temps = np.array(data["temperature_C"])
        pressures_kPa = np.array(data["pressure_bar"]) * 100

        dp_dT = self._dp_dT(temps, pressures_kPa, sat_temp_C)
        return temp_penalty_K * dp_dT
