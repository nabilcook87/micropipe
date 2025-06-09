# utils/refrigerant_densities.py

import json
import numpy as np
import os
from scipy.interpolate import CubicSpline

class RefrigerantDensities:
    def __init__(self):
        base_path = os.path.dirname(os.path.dirname(__file__))
        data_path = os.path.join(base_path, 'data', 'oil_densities.json')
        with open(data_path, 'r') as file:
            self.tables = json.load(file)

    def interpolate(self, x_array, y_array, x):
        """Cubic spline interpolation with out-of-bounds protection."""
        if x <= x_array[0]:
            return y_array[0]
        elif x >= x_array[-1]:
            return y_array[-1]
        else:
            spline = CubicSpline(x_array, y_array, extrapolate=False)
            return float(spline(x))

    def get_oil_density(self, refrigerant, temperature_C):
        if refrigerant not in self.tables:
            raise ValueError(f"Refrigerant '{refrigerant}' not found in database.")

        data = self.tables[refrigerant]

        temp_array = np.array(data["temperature_C"])
        oildensity_array = np.array(data["oil_density"])
        
        oil_density = self.interpolate(temp_array, oildensity_array, temperature_C)

        return oil_density
