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

    def get_density(self, refrigerant, evap_temp_K, superheat_K):
        """
        2D log-log interpolation using evap_temp (K) and superheat (K).
        """
        table = self.tables.get(refrigerant)
        if table is None:
            raise ValueError(f"Refrigerant '{refrigerant}' not found.")

        superheat_axis = np.array(table["superheat"], dtype=np.float64)
        # Replace exact 0 with a small value to avoid log(0)
        superheat_axis[superheat_axis == 0] = 0.01

        # Extract and sort evap temp keys (excluding "superheat")
        evap_keys = [k for k in table if k != "superheat"]
        evap_vals = np.array(sorted([float(k) for k in evap_keys]), dtype=np.float64)

        # Build 2D data matrix (rows = evap, cols = superheat)
        data_matrix = np.array([table[k] for k in map(str, evap_vals)], dtype=np.float64)

        # Interpolation in log space
        log_evap_vals = np.log(evap_vals)
        log_superheat = np.log(superheat_axis)
        log_data = np.log(data_matrix)

        # Target point
        log_x = np.log(evap_temp_K)
        log_y = np.log(superheat_K)

        # First interpolate along superheat axis (each row)
        interp_log_z = np.array([
            np.interp(log_y, log_superheat, row)
            for row in log_data
        ])

        # Then interpolate across evaporating temp axis
        final_log_density = np.interp(log_x, log_evap_vals, interp_log_z)

        return float(np.exp(final_log_density))
