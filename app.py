import streamlit as st
from utils.network_builder import NetworkBuilder
from utils.pressure_temp_converter import PressureTemperatureConverter
from utils.system_pressure_checker import check_pipe_rating, _pipe_rating_data, get_pipe_options
import pandas as pd
import math

st.set_page_config(page_title="Micropipe - Refrigeration Pipe Sizing", layout="wide")
st.title("MicroPipe")

# Sidebar for tools and settings
st.sidebar.title("Tools & Utilities")
tool_selection = st.sidebar.radio("Select Tool", [
    "Pipe Network Builder",
    "Pressure ↔ Temperature Converter",
    "Pressure Drop ↔ Temperature Penalty",
    "System Pressure Checker",
    "Oil Return Velocity Checker"
])
st.sidebar.text("")
st.sidebar.text("")
st.sidebar.text("")
st.sidebar.text("")
st.sidebar.text("")
st.sidebar.text("")
st.sidebar.text("")
st.sidebar.text("")
st.sidebar.image("assets/logo.png", use_container_width=True)

def system_pressure_checker_ui():
    st.subheader("System Pressure Rating Tool")

    # Load pipe data
    pipe_data = pd.read_csv("data/pipe_pressure_ratings_full.csv")

    # 1. Select Pipe Material
    pipe_materials = sorted(pipe_data["Material"].dropna().unique())
    selected_material = st.selectbox("Pipe Material", pipe_materials)

    # 2. Filter pipe sizes for selected material
    material_df = pipe_data[pipe_data["Material"] == selected_material]
    pipe_sizes = sorted(material_df["Nominal Size (inch)"].dropna().astype(str).unique())
    selected_size = st.selectbox("Nominal Pipe Size (inch)", pipe_sizes)

    # 3. Gauge (if applicable)
    gauge_options = material_df[material_df["Nominal Size (inch)"].astype(str) == selected_size]
    if "Gauge" in gauge_options.columns and gauge_options["Gauge"].notna().any():
        gauges = sorted(gauge_options["Gauge"].dropna().unique())
        selected_gauge = st.selectbox("Copper Gauge", gauges)
        selected_pipe_row = gauge_options[gauge_options["Gauge"] == selected_gauge].iloc[0]
    else:
        selected_pipe_row = gauge_options.iloc[0]

    design_temp_C = st.select_slider("Design Temperature (C)", options=[50, 100, 150], value=50)
    design_temp_col = f"{design_temp_C}C"
    design_pressure_bar = st.number_input("Design Pressure (bar)", min_value=0.0, step=0.5, value=10.0)

    is_rated = check_pipe_rating(selected_pipe_row, design_temp_C, design_pressure_bar)
    rated_pressure = selected_pipe_row.get(design_temp_col)

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

    with st.expander("Show Full Pipe Data"):
        st.dataframe(selected_pipe_row.to_frame().T)

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
        "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A", "R454C", "R455A", "R407A"
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
        "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A", "R454C", "R455A", "R407A"
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

    refrigerant = st.selectbox("Refrigerant", [
        "R404A", "R134a", "R407F", "R744", "R410A",
        "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A", "R454C", "R455A", "R407A"
    ])

    # Load pipe data
    pipe_data = pd.read_csv("data/pipe_pressure_ratings_full.csv")

    # 1. Select Pipe Material
    pipe_materials = sorted(pipe_data["Material"].dropna().unique())
    selected_material = st.selectbox("Pipe Material", pipe_materials)

    # 2. Filter pipe sizes for selected material
    material_df = pipe_data[pipe_data["Material"] == selected_material]
    pipe_sizes = sorted(material_df["Nominal Size (inch)"].dropna().astype(str).unique())
    selected_size = st.selectbox("Nominal Pipe Size (inch)", pipe_sizes)

    # 3. Gauge (if applicable)
    gauge_options = material_df[material_df["Nominal Size (inch)"].astype(str) == selected_size]
    if "Gauge" in gauge_options.columns and gauge_options["Gauge"].notna().any():
        gauges = sorted(gauge_options["Gauge"].dropna().unique())
        selected_gauge = st.selectbox("Copper Gauge", gauges)
        selected_pipe_row = gauge_options[gauge_options["Gauge"] == selected_gauge].iloc[0]
    else:
        selected_pipe_row = gauge_options.iloc[0]

    # Pipe parameters
    pipe_size_inch = selected_pipe_row["Nominal Size (inch)"]
    ID_mm = selected_pipe_row["ID_mm"]

    evap_capacity_kw = st.number_input("Evaporator Capacity (kW)", min_value=0.1, value=10.0)
    evaporating_temp = st.number_input("Evaporating Temperature (°C)", value=-10)
    condensing_temp = st.number_input("Condensing Temperature (°C)", value=40.0)
    subcooling_K = st.number_input("Subcooling (K)", value=3.0)
    superheat_K = st.number_input("Superheat (K)", value=5.0)
    required_oil_duty_pct = st.number_input("Required Oil Return Duty (%)", min_value=0.0, max_value=100.0, value=100.0, step=5.0)

    from utils.refrigerant_properties import RefrigerantProperties
    from utils.refrigerant_densities import RefrigerantDensities
    from utils.pipe_length_volume_calc import get_pipe_id_mm
    from utils.oil_return_checker import check_oil_return

    T_evap = evaporating_temp
    T_cond = condensing_temp

    props = RefrigerantProperties()
    h_inlet = props.get_properties(refrigerant, T_cond - subcooling_K)["enthalpy_liquid"]
    h_evap = props.get_properties(refrigerant, T_evap)["enthalpy_vapor"]
    h_10K = props.get_properties(refrigerant, T_evap)["enthalpy_super"]
    hdiff_10K = h_10K - h_evap
    hdiff_custom = hdiff_10K * min(superheat_K, 30) / 10
    h_super = h_evap + hdiff_custom
    h_foroil = (h_evap + h_super) / 2
    
    delta_h = h_evap - h_inlet
    delta_h_foroil = h_foroil - h_inlet
    mass_flow_kg_s = evap_capacity_kw / delta_h if delta_h > 0 else 0.01
    mass_flow_foroil = evap_capacity_kw / delta_h_foroil if delta_h_foroil > 0 else 0.01

    adjusted_mass_flow_kg_s = mass_flow_kg_s * (required_oil_duty_pct / 100.0)

    # Calculate velocity for transparency
    if ID_mm is not None:
        ID_m = ID_mm / 1000.0
        area_m2 = 3.1416 * (ID_m / 2) ** 2
        density_super = RefrigerantDensities().get_density(refrigerant, T_evap + 273.15, superheat_K)
        density_sat = RefrigerantProperties().get_properties(refrigerant, T_evap)["density_vapor"]
        density = (density_super + density_sat) / 2
        velocity_m_s = adjusted_mass_flow_kg_s / (area_m2 * density)
        oil_density_sat = (-0.00356060606060549 * (T_evap ** 2)) - (0.957878787878808 * T_evap) + 963.595454545455
        oil_density_super = (-0.00356060606060549 * ((T_evap + min(superheat_K, 30)) ** 2)) - (0.957878787878808 * (T_evap + min(superheat_K, 30))) + 963.595454545455
        oil_density = (oil_density_sat + oil_density_super) / 2
        MinMassFlux = (0.895 ** 2) * ((density * 9.81 * ID_m * (oil_density - density)) ** 0.5)
        MinMassFlow = MinMassFlux * area_m2
        MOR = (MinMassFlow / mass_flow_foroil) * 100
    else:
        velocity_m_s = None

    # Oil return check
    adjusted_duty_kw = evap_capacity_kw * (required_oil_duty_pct / 100.0)
    is_ok, message, min_oil_return = check_oil_return(
        pipe_size_inch=pipe_size_inch,
        refrigerant=refrigerant,
        evap_capacity_kw=evap_capacity_kw,
        duty_pct=required_oil_duty_pct,
        evap_temp=evaporating_temp,
        cond_temp=condensing_temp,
        superheat=superheat_K,
        subcool=subcooling_K
    )
    
    st.divider()
    st.subheader("Results")

    if velocity_m_s:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Refrigerant Velocity", f"{velocity_m_s:.2f} m/s")

        with col2:
            st.metric("Minimum Oil Return (%)", f"{min_oil_return:.1f} %")

        with col3:
            st.metric("Suction Density", f"{density_super:.2f} kg/m3")

        with col4:
            st.metric("MOR (%)", f"{MOR:.1f} %")
    
    if is_ok:
        st.success(f"✅ {message}")
    else:
        st.error(f"❌ {message}")
