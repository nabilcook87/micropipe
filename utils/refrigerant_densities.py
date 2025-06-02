# utils/refrigerant_densities.py

import json
import numpy as np
import os

class RefrigerantDensities:
    def __init__(self):
        base_path = os.path.dirname(os.path.dirname(__file__))
        data_path = os.path.join(base_path, 'data', 'refrigerant_densities.json')
        with open(data_path, 'r') as file:
            self.tables = json.load(file)

    def interpolate_ln(self, x_array, y_array, x):
        x_array = np.array(x_array)
        y_array = np.array(y_array)

        # Prevent log(0) or log(negative)
        if x <= 0 or np.any(x_array <= 0) or np.any(y_array <= 0):
            return float("nan")

        log_x = np.log(x_array)
        log_y = np.log(y_array)
        log_x_val = np.log(x)
        log_y_val = np.interp(log_x_val, log_x, log_y)
        return np.exp(log_y_val)

    def get_density(self, refrigerant, evap_temp, superheat):
        """
        Perform 2D ln-ln interpolation using evap_temp (K) and superheat (K)
        """
        table = self.tables.get(refrigerant)
        if table is None:
            raise ValueError(f"Refrigerant '{refrigerant}' not found.")

        superheats = table["superheat"]

        # Filter and sort only temperature keys
        evap_keys = [k for k in table if k != "superheat"]
        evap_temps = sorted([float(k) for k in evap_keys])

        # Match floating point keys reliably
        matrix = []
        for t in evap_temps:
            key = next((k for k in evap_keys if abs(float(k) - t) < 0.001), None)
            if key is None:
                raise KeyError(f"Temperature {t} K not found in table keys.")
            matrix.append(table[key])
        matrix = np.array(matrix)

        # Interpolate across superheat (x-direction)
        interp_vals = [self.interpolate_ln(superheats, row, superheat) for row in matrix]

        # Interpolate across evap temp (y-direction)
        return self.interpolate_ln(evap_temps, interp_vals, evap_temp)
