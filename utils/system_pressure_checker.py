# utils/system_pressure_checker.py

import pandas as pd

# Load pipe rating data only once
_pipe_rating_data = pd.read_csv("data/pipe_pressure_ratings_full.csv")

def check_pipe_rating(pipe_row, operating_temp_C):
    """
    Check if the pipe's pressure rating at a given temperature is above a safety threshold.
    Safety threshold: 0.9 × rating at design temp.
    """
    design_temp_col = f"{int(round(operating_temp_C))}C"
    available_cols = _pipe_rating_data.columns

    # Fallback if the exact temp column is not available
    if design_temp_col not in available_cols:
        design_temp_col = closest_temp_column(available_cols, operating_temp_C)

    try:
        rating = float(pipe_row[design_temp_col])
        return rating * 0.9 >= pipe_row["Design Pressure (bar)"]
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
    optionally including gauge if present.
    """
    df = _pipe_rating_data.copy()
    df = df[df["Material"].str.strip().str.lower() == material.strip().lower()]
    df = df[df["Nominal Size (inch)"].astype(str).str.strip() == str(size_inch).strip()]
    return df
