# utils/refrigerant_properties.py

import json
import numpy as np
import os
from scipy.interpolate import CubicSpline
import streamlit as st

class RefrigerantProperties:
    def __init__(self):
        base_path = os.path.dirname(os.path.dirname(__file__))
        data_path = os.path.join(base_path, 'data', 'refrigerant_tables.json')
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
            # st.write("spline:", spline)
            return float(spline(x))
    
    def interpolate_log(self, x_array, y_array, x):
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
        
        pressure_bar = self.interpolate_log(temp_array, pressure_array, temperature_C)
        density_liquid = self.interpolate(temp_array, density_liquid_array, temperature_C)
        density_vapor = self.interpolate_log(temp_array, density_vapor_array, temperature_C)
        enthalpy_liquid = self.interpolate(temp_array, enthalpy_liquid_array, temperature_C)
        enthalpy_vapor = self.interpolate(temp_array, enthalpy_vapor_array, temperature_C)
        enthalpy_super = self.interpolate(temp_array, enthalpy_super_array, temperature_C)

        # st.write("temp_array:", temp_array)
        # st.write("enthalpy_super_array:", enthalpy_super_array)
        # st.write("temperature_C:", temperature_C)
        
        return {
            "pressure_bar": pressure_bar,
            "density_liquid": density_liquid,
            "density_vapor": density_vapor,
            "enthalpy_liquid": enthalpy_liquid,
            "enthalpy_vapor": enthalpy_vapor,
            "enthalpy_super": enthalpy_super
        }
