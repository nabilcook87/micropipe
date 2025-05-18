# /utils/pressure_temp_converter.py

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
        Convert pressure drop (kPa) to temperature penalty (K) using real table interpolation of dp/dT.
        """
        data = self.refrigerant_props.tables[refrigerant]
        temps = data["temperature_C"]
        pressures_bar = data["pressure_bar"]
        pressures_kPa = [p * 100 for p in pressures_bar]

        for i in range(len(temps) - 1):
            T1, T2 = temps[i], temps[i + 1]
            if T1 <= sat_temp_C <= T2:
                P1, P2 = pressures_kPa[i], pressures_kPa[i + 1]
                # Interpolated slope
                dp_dT = (P2 - P1) / (T2 - T1)
                return pressure_drop_kPa / dp_dT

        # Outside range — clamp to edges
        return 0.0

    def temp_penalty_to_pressure_drop(self, refrigerant, sat_temp_C, temp_penalty_K):
        """
        Convert temperature penalty (K) to pressure drop (kPa) using real table interpolation of dp/dT.
        """
        data = self.refrigerant_props.tables[refrigerant]
        temps = data["temperature_C"]
        pressures_bar = data["pressure_bar"]
        pressures_kPa = [p * 100 for p in pressures_bar]

        for i in range(len(temps) - 1):
            T1, T2 = temps[i], temps[i + 1]
            if T1 <= sat_temp_C <= T2:
                P1, P2 = pressures_kPa[i], pressures_kPa[i + 1]
                # Interpolated slope
                dp_dT = (P2 - P1) / (T2 - T1)
                return temp_penalty_K * dp_dT

        return 0.0
