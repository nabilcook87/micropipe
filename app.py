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

    # Check rating using corrected call
    is_rated = check_pipe_rating(pipe_row, design_temp_C, design_pressure_bar)
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
    st.subheader("Oil Return Velocity Checker")

    st.markdown("""
    This tool calculates refrigerant velocity in a suction line and checks whether it meets the oil return requirement
    based on pipe size, refrigerant, and duty cycle — using original Micropipe logic.
    """)

    refrigerant = st.selectbox("Refrigerant", [
        "R404A", "R134a", "R407F", "R744", "R410A",
        "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A"
    ])

    pipe_size_inch = st.selectbox("Pipe Size (inch)", [
        "1/4", "3/8", "1/2", "5/8", "3/4", "7/8", "1-1/8", "1-3/8", "1-5/8",
        "2-1/8", "2-5/8", "3-1/8", "3-5/8", "4-1/8"
    ])

    evap_capacity_kw = st.number_input("Evaporator Capacity (kW)", min_value=0.1, value=10.0)
    condensing_temp = st.number_input("Condensing Temperature (°C)", value=40.0)
    evaporating_temp = st.number_input("Evaporating Temperature (°C)", value=-10.0)
    subcooling_K = st.number_input("Subcooling (K)", value=3.0)
    superheat_K = st.number_input("Superheat (K)", value=5.0)
    required_oil_duty_pct = st.number_input("Required Oil Return Duty (%)", min_value=0.0, max_value=100.0, value=100.0, step=5.0)

    from utils.refrigerant_properties import RefrigerantProperties
    from utils.pipe_length_volume_calc import get_pipe_id_mm
    from utils.oil_return_checker import check_oil_velocity

    props = RefrigerantProperties()
    h_vap = props.get_properties(refrigerant, evaporating_temp)["enthalpy_vapor"]
    h_vap_plus = props.get_properties(refrigerant, evaporating_temp + 10)["enthalpy_vapor"]
    Cp_vapor = (h_vap_plus - h_vap) / 10
    h_in = h_vap
    h_out = h_vap + superheat_K * Cp_vapor
    Δh = h_out - h_in

    mass_flow_kg_s = evap_capacity_kw / Δh if Δh > 0 else 0.01

    ID_mm = get_pipe_id_mm(pipe_size_inch)
    if ID_mm:
        ID_m = ID_mm / 1000.0
        area_m2 = 3.1416 * (ID_m / 2) ** 2
        density_vapor = props.get_properties(refrigerant, evaporating_temp)["density_vapor"]
        velocity_m_s = mass_flow_kg_s / (area_m2 * density_vapor)
    else:
        velocity_m_s = None

    is_ok, message = check_oil_velocity(pipe_size_inch, refrigerant, mass_flow_kg_s)

    st.divider()
    st.subheader("Results")

    if velocity_m_s:
        st.metric("Refrigerant Velocity", f"{velocity_m_s:.2f} m/s")

    if is_ok:
        st.success(f"✅ {message}")
    else:
        st.error(f"❌ {message}")
