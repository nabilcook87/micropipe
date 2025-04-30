import csv
import os

class SystemPressureChecker:
    def __init__(self, data_file="data/pipe_pressure_ratings_full.csv", safety_factor=0.9):
        self.data_file = data_file
        self.safety_factor = safety_factor
        self.pressure_limits = self.load_pressure_limits()

    def load_pressure_limits(self):
        """Load pipe pressure limits from CSV into a lookup dictionary."""
        limits = {}
        if not os.path.exists(self.data_file):
            raise FileNotFoundError(f"Pipe pressure ratings file not found: {self.data_file}")

        with open(self.data_file, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                key = self._make_key(row["Material"], row["Nominal Size (inch)"])
                try:
                    max_pressure_bar = float(row["Max Pressure (bar)"])
                    limits[key] = max_pressure_bar
                except ValueError:
                    continue  # Skip bad data

        return limits

    def _make_key(self, material, size_inch):
        """Helper to normalize key lookup."""
        return f"{material.strip().lower()}::{size_inch.strip()}"

    def check_pressure(self, material, size_inch, system_pressure_bar):
        """
        Returns a dict:
        {
            "pass": True/False,
            "allowed_bar": float,
            "margin_bar": float,
            "notes": str
        }
        """
        key = self._make_key(material, size_inch)
        if key not in self.pressure_limits:
            return {
                "pass": False,
                "allowed_bar": None,
                "margin_bar": None,
                "notes": f"Pipe size '{size_inch}' with material '{material}' not found in pressure ratings database."
            }

        allowed_max = self.pressure_limits[key] * self.safety_factor
        margin = allowed_max - system_pressure_bar
        result = {
            "pass": margin >= 0,
            "allowed_bar": round(allowed_max, 2),
            "margin_bar": round(margin, 2),
            "notes": "OK" if margin >= 0 else f"⚠️ Exceeds max allowed pressure by {abs(margin):.2f} bar"
        }
        return result