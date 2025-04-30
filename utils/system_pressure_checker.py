# utils/system_pressure_checker.py

import pandas as pd

# Load pipe rating data only once
_pipe_rating_data = pd.read_csv("data/pipe_pressure_ratings_full.csv")

# Imperial to metric lookup (approximate mm equivalents)
INCH_TO_MM_MAP = {
    "1/4": 6.35,
    "3/8": 9.53,
    "1/2": 12.7,
    "5/8": 15.88,
    "3/4": 19.05,
    "7/8": 22.23,
    "1-1/8": 28.58,
    "1-3/8": 34.93,
    "1-5/8": 41.28,
    "2-1/8": 53.98,
    "2-5/8": 66.68,
    "3-1/8": 79.38,
    "3-5/8": 92.08,
    "4-1/8": 104.78,
}

def check_pipe_rating(pipe_row, operating_temp_C, design_pressure_bar):
    """
    Check if the pipe's pressure rating at a given temperature is above a safety threshold.
    Safety threshold: 0.9 × rating at design temp.
    """
    design_temp_col = f"{int(round(operating_temp_C))}C"
    available_cols = pipe_row.index

    if design_temp_col not in available_cols:
        design_temp_col = closest_temp_column(available_cols, operating_temp_C)

    try:
        val = pipe_row.get(design_temp_col)
        if pd.isna(val):
            return False
        rating = float(val)
        return rating * 0.9 >= design_pressure_bar
    except Exception:
        return False

def closest_temp_column(columns, target_temp):
    """
    Find the closest available temperature column name like '20C' from a list of strings.
    """
    temps = []
    for col in columns:
        if col.endswith("C") and col[:-1].isdigit():
            temps.append(int(col[:-1]))

    if not temps:
        return "20C"  # fallback

    closest = min(temps, key=lambda x: abs(x - target_temp))
    return f"{closest}C"

def get_pipe_options(material, size_inch):
    """
    Return a filtered DataFrame for a given pipe material and size,
    optionally including gauge if present. EN pipes match by closest mm.
    """
    df = _pipe_rating_data.copy()
    df = df[df["Material"].str.strip().str.lower() == material.strip().lower()]

    if "en" in material.lower():
        target_mm = INCH_TO_MM_MAP.get(size_inch.strip())
        if target_mm is None or "Nominal Size (mm)" not in df.columns:
            return pd.DataFrame()

        df = df.dropna(subset=["Nominal Size (mm)"])
        df["_diff"] = (df["Nominal Size (mm)"] - target_mm).abs()
        closest_mm = df.sort_values("_diff").iloc[0]["Nominal Size (mm)"]
        df = df[df["Nominal Size (mm)"] == closest_mm].drop(columns="_diff")
        return df
    else:
        return df[df["Nominal Size (inch)"].astype(str).str.strip() == str(size_inch).strip()]
