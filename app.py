import streamlit as st
from utils.network_builder import NetworkBuilder
from utils.pressure_temp_converter import PressureTemperatureConverter
from utils.system_pressure_checker import check_pipe_rating, _pipe_rating_data, get_pipe_options
import pandas as pd

st.set_page_config(page_title="Micropipe - Industrial Refrigeration Tool", layout="wide")
st.title("Micropipe - Industrial Refrigeration Pipe Sizing")

# Sidebar for tools and settings
st.sidebar.title("Tools & Utilities")
tool_selection = st.sidebar.radio("Select Tool", [
    "Pipe Network Builder",
    "Pressure ↔ Temperature Converter",
    "Pressure Drop ↔ Temperature Penalty",
    "System Pressure Checker",
    "Oil Return Velocity Checker"
])

def system_pressure_checker_ui():
    st.title("System Pressure Rating Tool")
    st.markdown("""
    This tool checks if a selected pipe size and gauge is rated for your system's design pressure 
    at a specified temperature. Safety factor threshold: **90%** of the rated pressure.
    """)

    st.divider()

    # Pipe sizes from the data
    pipe_sizes = sorted(_pipe_rating_data['Nominal Size (inch)'].dropna().unique())
    selected_size = st.selectbox("Select Pipe Nominal Size", pipe_sizes)

    # Pipe materials
    materials = sorted(_pipe_rating_data['Material'].dropna().unique())
    selected_material = st.selectbox("Select Pipe Material", materials)

    # Filter rows for selected pipe material and size
    matching_pipes = get_pipe_options(selected_material, selected_size)

    if matching_pipes.empty:
        st.warning("No pipe data available for selected material and size.")
        return

    # Optional gauge selection
    if "Gauge" in matching_pipes.columns and matching_pipes["Gauge"].notna().any():
        gauges = sorted(matching_pipes["Gauge"].dropna().unique())
        selected_gauge = st.selectbox("Select Copper Gauge", gauges)
        pipe_row = matching_pipes[matching_pipes["Gauge"] == selected_gauge].iloc[0]
    else:
        pipe_row = matching_pipes.iloc[0]  # fallback for steel

    # Choose temperature for rating lookup
    design_temp_C = st.select_slider("Design Temperature (C)", options=[50, 100, 150], value=50)
    design_temp_col = f"{design_temp_C}C"

    # Input design pressure
    design_pressure_bar = st.number_input("Design Pressure (bar)", min_value=0.0, step=0.5, value=10.0)
    pipe_row["Design Pressure (bar)"] = design_pressure_bar  # Set for rating check

    # Check rating
    is_rated = check_pipe_rating(pipe_row, design_temp_C)
    rated_pressure = pipe_row.get(design_temp_col)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Pipe Rating Summary")
        st.metric("Rated Pressure @ Temp", f"{rated_pressure:.2f} bar" if pd.notna(rated_pressure) else "N/A")
        st.metric("Design Pressure", f"{design_pressure_bar:.2f} bar")

    with col2:
        st.subheader("Result")
        if is_rated:
            st.success("✅ Pipe is rated for this pressure.")
        else:
            st.error("❌ Pipe is NOT rated for this pressure.")

    # Show full data row for transparency
    with st.expander("Show Full Pipe Data"):
        st.dataframe(pipe_row.to_frame().T)

    with st.expander("BS EN 378 Reference Pressures"):
        st.table(pd.DataFrame({
            "Design Temp (C)": [55, 43, 32],
            "Design Pressure (bar)": [24.69, 18.51, 13.90]
        }))

if tool_selection == "Pipe Network Builder":
    builder = NetworkBuilder()
    builder.run()

elif tool_selection == "Pressure ↔ Temperature Converter":
    st.subheader("Saturation Pressure ↔ Temperature Tool")
    converter = PressureTemperatureConverter()

    refrigerant = st.selectbox("Refrigerant", [
        "R404A", "R134a", "R407F", "R744", "R410A",
        "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A"
    ])
    mode = st.radio("Convert:", ["Pressure ➞ Temperature", "Temperature ➞ Pressure"])

    if mode == "Pressure ➞ Temperature":
        pressure_bar = st.number_input("Saturation Pressure (bar)", value=5.0)
        temp_C = converter.pressure_to_temp(refrigerant, pressure_bar)
        st.write(f"**Saturation Temperature:** {temp_C:.2f} °C")
    else:
        temp_C = st.number_input("Saturation Temperature (°C)", value=0.0)
        pressure_bar = converter.temp_to_pressure(refrigerant, temp_C)
        st.write(f"**Saturation Pressure:** {pressure_bar:.2f} bar")

elif tool_selection == "Pressure Drop ↔ Temperature Penalty":
    st.subheader("Pressure Drop ⇄ Temperature Penalty Tool")
    converter = PressureTemperatureConverter()

    refrigerant = st.selectbox("Refrigerant", [
        "R404A", "R134a", "R407F", "R744", "R410A",
        "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A"
    ])
    T_sat = st.number_input("Saturation Temperature (°C)", value=-10.0)
    direction = st.radio("Convert:", ["ΔP ➞ ΔT", "ΔT ➞ ΔP"])

    if direction == "ΔP ➞ ΔT":
        delta_p_kpa = st.number_input("Pressure Drop (kPa)", value=20.0)
        delta_T = converter.pressure_drop_to_temp_penalty(refrigerant, T_sat, delta_p_kpa)
        st.write(f"**Temperature Penalty:** {delta_T:.3f} K")
    else:
        delta_T = st.number_input("Temperature Penalty (K)", value=0.5)
        delta_p_kpa = converter.temp_penalty_to_pressure_drop(refrigerant, T_sat, delta_T)
        st.write(f"**Equivalent Pressure Drop:** {delta_p_kpa:.2f} kPa")

elif tool_selection == "System Pressure Checker":
    system_pressure_checker_ui()

elif tool_selection == "Oil Return Velocity Checker":
    st.subheader("Oil Return Velocity Check (Stub)")
    st.info("This feature checks that refrigerant velocity is sufficient for oil return. UI not yet implemented.")
