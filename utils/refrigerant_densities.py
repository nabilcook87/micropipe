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
        """1D log-log interpolation"""
        x_array = np.array(x_array)
        y_array = np.array(y_array)
        log_x = np.log(x_array)
        log_y = np.log(y_array)
        log_x_val = np.log(x)
        log_y_val = np.interp(log_x_val, log_x, log_y)
        return np.exp(log_y_val)

    def get_density(self, refrigerant, evap_temp, superheat):
        """
        Perform 2D ln-ln interpolation using evaporating temperature (rows)
        and superheat (columns) for a given refrigerant.
        """
        table = self.tables.get(refrigerant)
        if table is None:
            raise ValueError(f"Refrigerant '{refrigerant}' not found in the data.")

        # Extract available values
        superheats = table["superheat"]
        evap_temps = sorted([float(k) for k in table.keys() if k != "superheat"])
        matrix = np.array([table[str(temp)] for temp in evap_temps])

        # Interpolate along superheat (x-direction) at each evap temp (y-values)
        interp_vals = []
        for row in matrix:
            val = self.interpolate_ln(superheats, row, superheat)
            interp_vals.append(val)

        # Interpolate final value along evap temp (y-direction)
        result = self.interpolate_ln(evap_temps, interp_vals, evap_temp)
        return result