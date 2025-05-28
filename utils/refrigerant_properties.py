# utils/refrigerant_properties.py

import json
import numpy as np
import os

class RefrigerantProperties:
    def __init__(self):
        base_path = os.path.dirname(os.path.dirname(__file__))
        data_path = os.path.join(base_path, 'data', 'refrigerant_tables.json')
        with open(data_path, 'r') as file:
            self.tables = json.load(file)

    def interpolate(self, x_array, y_array, x):
        """Linear interpolation with out-of-bounds protection."""
        if x <= x_array[0]:
            return y_array[0]
        elif x >= x_array[-1]:
            return y_array[-1]
        else:
            return np.interp(x, x_array, y_array)
    
    def interpolate2(self, x_array, y_array, x):
        """Logarithmic interpolation with out-of-bounds protection."""
        if x <= x_array[0]:
            return y_array[0]
        elif x >= x_array[-1]:
            return y_array[-1]
        else:
            log_y_array = np.log(y_array)
            log_y = np.interp(x, x_array, log_y_array)
            return np.exp(log_y)

    def get_properties(self, refrigerant, temperature_C):
        """Return pressure, densities, enthalpies at given temperature."""
        if refrigerant not in self.tables:
            raise ValueError(f"Refrigerant '{refrigerant}' not found in database.")

        data = self.tables[refrigerant]

        temp_array = np.array(data["temperature_C"])
        pressure_array = np.array(data["pressure_bar"])
        density_liquid_array = np.array(data["density_liquid"])
        density_vapor_array = np.array(data["density_vapor"])
        enthalpy_liquid_array = np.array(data["enthalpy_liquid"])
        enthalpy_vapor_array = np.array(data["enthalpy_vapor"])
        enthalpy_super_array = np.array(data["enthalpy_super"])
        
        pressure_bar = self.interpolate2(temp_array, pressure_array, temperature_C)
        density_liquid = self.interpolate2(temp_array, density_liquid_array, temperature_C)
        density_vapor = self.interpolate2(temp_array, density_vapor_array, temperature_C)
        enthalpy_liquid = self.interpolate2(temp_array, enthalpy_liquid_array, temperature_C)
        enthalpy_vapor = self.interpolate2(temp_array, enthalpy_vapor_array, temperature_C)
        enthalpy_super = self.interpolate2(temp_array, enthalpy_super_array, temperature_C)

        return {
            "pressure_bar": pressure_bar,
            "density_liquid": density_liquid,
            "density_vapor": density_vapor,
            "enthalpy_liquid": enthalpy_liquid,
            "enthalpy_vapor": enthalpy_vapor,
            "enthalpy_super": enthalpy_super
        }
