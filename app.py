import streamlit as st
from utils.network_builder import NetworkBuilder
from utils.pressure_temp_converter import PressureTemperatureConverter
from utils.system_pressure_checker import check_pipe_rating  # Stub interface
from utils.save_load_manager import save_project, load_project  # Load logic optional

st.set_page_config(page_title="Micropipe - Industrial Refrigeration Tool", layout="wide")
st.title("Micropipe - Industrial Refrigeration Pipe Sizing")

# Sidebar for tools and settings
st.sidebar.title("Tools & Utilities")
tool_selection = st.sidebar.radio("Select Tool", [
    "Pipe Network Builder",
    "Pressure ↔ Temperature Converter",
    "Pressure Drop ↔ Temperature Penalty",
    "System Pressure Checker",
    "Save / Load Project"
])

# Tool 1: Pipe Network Builder
if tool_selection == "Pipe Network Builder":
    builder = NetworkBuilder()
    builder.run()

# Tool 2: Pressure ↔ Temperature Converter
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

# Tool 3: Pressure Drop ↔ Temperature Penalty
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
        delta_T = converter.delta_p_to_delta_T(refrigerant, T_sat, delta_p_kpa)
        st.write(f"**Temperature Penalty:** {delta_T:.3f} K")

    else:
        delta_T = st.number_input("Temperature Penalty (K)", value=0.5)
        delta_p_kpa = converter.delta_T_to_delta_p(refrigerant, T_sat, delta_T)
        st.write(f"**Equivalent Pressure Drop:** {delta_p_kpa:.2f} kPa")

# Tool 4: System Pressure Checker
elif tool_selection == "System Pressure Checker":
    st.subheader("System Pressure & Pipe Gauge Checker (Beta)")

    refrigerant = st.selectbox("Refrigerant", [
        "R404A", "R134a", "R407F", "R744", "R410A",
        "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A"
    ])
    temp_C = st.number_input("Design Temperature (°C)", value=40.0)
    pipe_material = st.selectbox("Pipe Material", ["Copper", "Steel"])
    pipe_type = st.selectbox("Pipe Type", ["Type A", "Type B", "Type L"])  # Customize as needed
    pipe_size = st.text_input("Nominal Pipe Size (inch)", value="1 1/8")

    try:
        status, pressure_bar, limit = check_pipe_rating(pipe_material, pipe_type, pipe_size, refrigerant, temp_C)
        st.write(f"System Pressure: {pressure_bar:.2f} bar")
        st.write(f"Rating Limit: {limit:.2f} bar")
        if status:
            st.success("✅ OK: System pressure is within limits.")
        else:
            st.error("⚠️ WARNING: Pressure exceeds pipe rating!")
    except Exception as e:
        st.error(f"Error: {e}")

# Tool 5: Save / Load Project
elif tool_selection == "Save / Load Project":
    st.subheader("Save / Load Project")
    st.write("This tool is used internally by the Network Builder. Manual loading support may be added if needed.")
