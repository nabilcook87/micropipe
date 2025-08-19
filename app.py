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
    "Oil Return Checker"
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
        "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A", "R454C", "R455A", "R407A",
        "R290", "R1270", "R600a", "R717", "R1234ze", "R1234yf", "R12", "R11", "R454B", "R450A", "R513A", "R23", "R508B", "R502"
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
        "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A", "R454C", "R455A", "R407A",
        "R290", "R1270", "R600a", "R717", "R1234ze", "R1234yf", "R12", "R11", "R454B", "R450A", "R513A", "R23", "R508B", "R502"
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

elif tool_selection == "Oil Return Checker":
    st.subheader("Oil Return Checker")

    col1, col2 = st.columns(2)

    with col1:
        refrigerant = st.selectbox("Refrigerant", [
            "R404A", "R134a", "R407F", "R744", "R410A",
            "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A", "R454C", "R455A", "R407A",
            "R290", "R1270", "R600a", "R717", "R1234ze", "R1234yf", "R12", "R11", "R454B", "R450A", "R513A", "R23", "R508B", "R502"
        ])

    # Load pipe data
    pipe_data = pd.read_csv("data/pipe_pressure_ratings_full.csv")

     # 1. Select Pipe Material
    with col2:
        pipe_materials = sorted(pipe_data["Material"].dropna().unique())
        selected_material = st.selectbox("Pipe Material", pipe_materials)

    # 2. Filter pipe sizes for selected material
    material_df = pipe_data[pipe_data["Material"] == selected_material]
    pipe_sizes = sorted(material_df["Nominal Size (inch)"].dropna().astype(str).unique())
    
    with col1:
        selected_size = st.selectbox("Nominal Pipe Size (inch)", pipe_sizes)

    # 3. Gauge (if applicable)
    gauge_options = material_df[material_df["Nominal Size (inch)"].astype(str) == selected_size]
    if "Gauge" in gauge_options.columns and gauge_options["Gauge"].notna().any():
        gauges = sorted(gauge_options["Gauge"].dropna().unique())
        with col2:    
            selected_gauge = st.selectbox("Copper Gauge", gauges)
        selected_pipe_row = gauge_options[gauge_options["Gauge"] == selected_gauge].iloc[0]
    else:
        selected_pipe_row = gauge_options.iloc[0]

    # Pipe parameters
    pipe_size_inch = selected_pipe_row["Nominal Size (inch)"]
    ID_mm = selected_pipe_row["ID_mm"]

    with col1:
        evap_capacity_kw = st.number_input("Evaporator Capacity (kW)", min_value=0.03, max_value=20000.0, value=10.0, step=1.0)
        # if refrigerant == "R23": evaporating_temp = st.number_input("Evaporating Temperature (°C)", min_value=-100.0, max_value=-30.0, value=-80.0, step=1.0)
        # elif refrigerant == "R508B": evaporating_temp = st.number_input("Evaporating Temperature (°C)", min_value=-100.0, max_value=-30.0, value=-80.0, step=1.0)
        # elif refrigerant == "R744": evaporating_temp = st.number_input("Evaporating Temperature (°C)", min_value=-50.0, max_value=20.0, value=-10.0, step=1.0)
        # else: evaporating_temp = st.number_input("Evaporating Temperature (°C)", min_value=-50.0, max_value=30.0, value=-10.0, step=1.0)
        # if refrigerant == "R23": condensing_temp = st.number_input("Max Liquid Temperature (°C)", min_value=max(-100.0, evaporating_temp), max_value=10.0, value=-30.0, step=1.0)
        # elif refrigerant == "R508B": condensing_temp = st.number_input("Max Liquid Temperature (°C)", min_value=max(-100.0, evaporating_temp), max_value=10.0, value=-30.0, step=1.0)
        # elif refrigerant == "R744": condensing_temp = st.number_input("Max Liquid Temperature (°C)", min_value=max(-50.0, evaporating_temp), max_value=30.0, value=20.0, step=1.0)
        # else: condensing_temp = st.number_input("Max Liquid Temperature (°C)", min_value=max(-50.0, evaporating_temp), max_value=60.0, value=40.0, step=1.0)
        # if refrigerant == "R23": minliq_temp = st.number_input("Min Liquid Temperature (°C)", min_value=max(-100.0, evaporating_temp), max_value=min(10.0, condensing_temp), value=condensing_temp, step=1.0)
        # elif refrigerant == "R508B": minliq_temp = st.number_input("Min Liquid Temperature (°C)", min_value=max(-100.0, evaporating_temp), max_value=min(10.0, condensing_temp), value=condensing_temp, step=1.0)
        # elif refrigerant == "R744": minliq_temp = st.number_input("Min Liquid Temperature (°C)", min_value=max(-50.0, evaporating_temp), max_value=min(30.0, condensing_temp), value=condensing_temp, step=1.0)
        # else: minliq_temp = st.number_input("Min Liquid Temperature (°C)", min_value=max(-50.0, evaporating_temp), max_value=min(60.0, condensing_temp), value=condensing_temp, step=1.0)

        # --- Base ranges per refrigerant ---
        if refrigerant in ("R23", "R508B"):
            evap_min, evap_max, evap_default = -100.0, -20.0, -80.0
            cond_min, cond_max, cond_default = -100.0, 10.0, -30.0
            minliq_min, minliq_max, minliq_default = -100.0, 10.0, -40.0
        elif refrigerant == "R744":
            evap_min, evap_max, evap_default = -50.0, 20.0, -10.0
            cond_min, cond_max, cond_default = -50.0, 30.0, 15.0
            minliq_min, minliq_max, minliq_default = -50.0, 30.0, 10.0
        else:
            evap_min, evap_max, evap_default = -50.0, 30.0, -10.0
            cond_min, cond_max, cond_default = -50.0, 60.0, 40.0
            minliq_min, minliq_max, minliq_default = -50.0, 60.0, 20.0

        # --- Init state (widget-backed) ---
        ss = st.session_state

        if "last_refrigerant" not in ss or ss.last_refrigerant != refrigerant:
            ss.cond_temp   = cond_default
            ss.minliq_temp = minliq_default
            ss.evap_temp   = evap_default
            ss.last_refrigerant = refrigerant
        
        ss.setdefault("cond_temp",   cond_default)
        ss.setdefault("minliq_temp", minliq_default)
        ss.setdefault("evap_temp",   evap_default)

        # --- Callbacks implementing your downstream clamping logic ---
        def on_change_cond():
            # When cond changes: clamp minliq down to cond, then evap down to minliq
            ss.minliq_temp = min(ss.minliq_temp, ss.cond_temp)
            ss.evap_temp   = min(ss.evap_temp,   ss.minliq_temp)

        def on_change_minliq():
            # When minliq changes: clamp minliq down to cond, then evap down to minliq
            ss.minliq_temp = min(ss.minliq_temp, ss.cond_temp)
            ss.evap_temp   = min(ss.evap_temp,   ss.minliq_temp)

        def on_change_evap():
            # When evap changes: clamp evap down to minliq
            ss.evap_temp   = min(ss.evap_temp,   ss.minliq_temp)

        # --- Inputs with inclusive caps (≤), same order as your code ---
        condensing_temp = st.number_input(
            "Max Liquid Temperature (°C)",
            min_value=cond_min, max_value=cond_max,
            value=ss.cond_temp, step=1.0, key="cond_temp",
            on_change=on_change_cond,
        )

        minliq_temp = st.number_input(
            "Min Liquid Temperature (°C)",
            min_value=minliq_min, max_value=min(condensing_temp, minliq_max),
            value=ss.minliq_temp, step=1.0, key="minliq_temp",
            on_change=on_change_minliq,
        )

        evaporating_temp = st.number_input(
            "Evaporating Temperature (°C)",
            min_value=evap_min, max_value=min(minliq_temp, evap_max),
            value=ss.evap_temp, step=1.0, key="evap_temp",
            on_change=on_change_evap,
        )

    with col2:
        superheat_K = st.number_input("Superheat (K)", min_value=0.0, max_value=60.0, value=5.0, step=1.0)
        max_penalty = st.number_input("Max Penalty (K)", min_value=0.0, max_value=6.0, value=1.0, step=0.1)
        required_oil_duty_pct = st.number_input("Required Oil Return Duty (%)", min_value=0.0, max_value=100.0, value=100.0, step=5.0)

    from utils.refrigerant_properties import RefrigerantProperties
    from utils.refrigerant_densities import RefrigerantDensities
    from utils.pipe_length_volume_calc import get_pipe_id_mm
    from utils.oil_return_checker import check_oil_return

    T_evap = evaporating_temp
    T_cond = condensing_temp

    props = RefrigerantProperties()
    h_in = props.get_properties(refrigerant, T_cond)["enthalpy_liquid2"]
    # for velocity
    h_inlet = props.get_properties(refrigerant, T_cond)["enthalpy_liquid"]
    # st.write("h_inlet:", h_inlet)
    h_evap = props.get_properties(refrigerant, T_evap)["enthalpy_vapor"]
    # st.write("h_evap:", h_evap)
    h_10K = props.get_properties(refrigerant, T_evap)["enthalpy_super"]
    # st.write("h_10K:", h_10K)
    hdiff_10K = h_10K - h_evap
    # st.write("hdiff_10K:", hdiff_10K)
    hdiff_custom = hdiff_10K * min(max(superheat_K, 5), 30) / 10
    # st.write("hdiff_custom:", hdiff_custom)
    h_super = h_evap + hdiff_custom
    # st.write("h_super:", h_super)
    h_foroil = (h_evap + h_super) / 2
    # st.write("h_foroil:", h_foroil)
    
    delta_h = h_evap - h_in
    # st.write("delta_h:", delta_h) for velocity
    delta_h_foroil = h_foroil - h_inlet
    # st.write("delta_h_foroil:", delta_h_foroil)
    mass_flow_kg_s = evap_capacity_kw / delta_h if delta_h > 0 else 0.01
    # st.write("mass_flow_kg_s:", mass_flow_kg_s)
    mass_flow_foroil = evap_capacity_kw / delta_h_foroil if delta_h_foroil > 0 else 0.01
    # st.write("mass_flow_foroil:", mass_flow_foroil)

    adjusted_mass_flow_kg_s = mass_flow_kg_s * (required_oil_duty_pct / 100.0)
    # st.write("adjusted_mass_flow_kg_s:", adjusted_mass_flow_kg_s)

    # Calculate velocity for transparency
    if ID_mm is not None:
        ID_m = ID_mm / 1000.0
        # st.write("ID_mm:", ID_mm)
        # st.write("ID_m:", ID_m)
        area_m2 = 3.1416 * (ID_m / 2) ** 2
        # st.write("area_m2:", area_m2)
        density_super = RefrigerantDensities().get_density(refrigerant, T_evap - max_penalty + 273.15, superheat_K + max_penalty)
        # st.write("density_super:", density_super)
        density_super2a = RefrigerantDensities().get_density(refrigerant, T_evap + 273.15, ((superheat_K + 5) / 2))
        # st.write("density_super2a:", density_super2a)
        density_super2b = RefrigerantDensities().get_density(refrigerant, T_evap - max_penalty + 273.15, ((superheat_K + max_penalty + 5) / 2))
        # st.write("density_super2b:", density_super2b)
        density_super2 = (density_super2a + density_super2b) / 2
        # st.write("density_super2:", density_super2)
        density_super_foroil = RefrigerantDensities().get_density(refrigerant, T_evap + 273.15, min(max(superheat_K, 5), 30))
        # st.write("density_super_foroil:", density_super_foroil)
        density_sat = RefrigerantProperties().get_properties(refrigerant, T_evap)["density_vapor"]
        # st.write("density_sat:", density_sat)
        density_5K = RefrigerantDensities().get_density(refrigerant, T_evap + 273.15, 5)
        # st.write("density_5K:", density_5K)
        density = (density_super + density_5K) / 2
        # st.write("density:", density)
        density_foroil = (density_super_foroil + density_sat) / 2
        # st.write("density_foroil:", density_foroil)
        velocity_m_s1 = adjusted_mass_flow_kg_s / (area_m2 * density)
        st.write("velocity_m_s1:", velocity_m_s1)
        velocity_m_s2 = adjusted_mass_flow_kg_s / (area_m2 * density_super2)
        st.write("velocity_m_s2:", velocity_m_s2)
        if refrigerant == "R744": velocity1_prop = 0
        elif refrigerant == "R404A":
            if superheat_K > 45: velocity1_prop = (0.0328330590542629 * superheat_K) - 1.47748765744183
            else: velocity1_prop = 0
        elif refrigerant == "R134a":
            if superheat_K > 30: velocity1_prop = (-0.000566085879684639 * (superheat_K ** 2)) + (0.075049554857083 * superheat_K) - 1.74200935399632
            else: velocity1_prop = 0
        elif refrigerant == "R407F": velocity1_prop = 1
        elif refrigerant == "R717": velocity1_prop = 1
        else: velocity1_prop = 0
        # if refrigerant == "R744": velocity1_prop = (-0.0142814388381874 * max(superheat_K, 5)) + 1.07140719419094
        # else: velocity1_prop = (-0.00280805561137312 * max(superheat_K, 5)) + 1.01404027805687
        # st.write("velocity1_prop:", velocity1_prop)
        velocity_m_s = (velocity_m_s1 * velocity1_prop) + (velocity_m_s2 * (1 - velocity1_prop))
        # st.write("velocity_m_s:", velocity_m_s)
        oil_density_sat = (-0.00356060606060549 * (T_evap ** 2)) - (0.957878787878808 * T_evap) + 963.595454545455
        # st.write("oil_density_sat:", oil_density_sat)
        oil_density_super = (-0.00356060606060549 * ((T_evap + min(max(superheat_K, 5), 30)) ** 2)) - (0.957878787878808 * (T_evap + min(max(superheat_K, 5), 30))) + 963.595454545455
        # st.write("oil_density_super:", oil_density_super)
        oil_density = (oil_density_sat + oil_density_super) / 2
        # st.write("oil_density:", oil_density)
        
        if refrigerant == "R404A": jg_half = 0.860772464072673
        elif refrigerant == "R134a": jg_half = 0.869986729796935
        elif refrigerant == "R407F": jg_half = 0.869042493641944
        elif refrigerant == "R744": jg_half = 0.877950613678719
        elif refrigerant == "R407A": jg_half = 0.867374311574041
        elif refrigerant == "R410A": jg_half = 0.8904423325365
        elif refrigerant == "R407C": jg_half = 0.858592104849471
        elif refrigerant == "R22": jg_half = 0.860563058394146
        elif refrigerant == "R502": jg_half = 0.858236706656266
        elif refrigerant == "R507A": jg_half = 0.887709710291009
        elif refrigerant == "R449A": jg_half = 0.867980496631757
        elif refrigerant == "R448A": jg_half = 0.86578818145833
        elif refrigerant == "R717": jg_half = 0.854957410951708
        elif refrigerant == "R290": jg_half = 0.844975139695726
        elif refrigerant == "R1270": jg_half = 0.849089717732815
        elif refrigerant == "R600a": jg_half = 0.84339338979887
        elif refrigerant == "R1234ze": jg_half = 0.867821375349728
        elif refrigerant == "R1234yf": jg_half = 0.860767472602571
        elif refrigerant == "R12": jg_half = 0.8735441986466
        elif refrigerant == "R11": jg_half = 0.864493203834913
        elif refrigerant == "R454B": jg_half = 0.869102255850291
        elif refrigerant == "R450A": jg_half = 0.865387140496035
        elif refrigerant == "R513A": jg_half = 0.861251244627232
        elif refrigerant == "R454A": jg_half = 0.868161104592492
        elif refrigerant == "R455A": jg_half = 0.865687329727713
        elif refrigerant == "R454C": jg_half = 0.866423016875524
        elif refrigerant == "R32": jg_half = 0.875213309852597
        elif refrigerant == "R23": jg_half = 0.865673418568001
        elif refrigerant == "R508B": jg_half = 0.864305626845382
        # st.write("jg_half:", jg_half)
        
        MinMassFlux = (jg_half ** 2) * ((density_foroil * 9.81 * ID_m * (oil_density - density_foroil)) ** 0.5)
        # st.write("MinMassFluxy:", MinMassFlux)
        MinMassFlow = MinMassFlux * area_m2
        # st.write("MinMassFlow:", MinMassFlow)
        MOR_pre = (MinMassFlow / mass_flow_foroil) * 100
        # st.write("MOR_pre:", MOR_pre)
        
        MOR_correctliq = T_cond
        # st.write("MOR_correctliq:", MOR_correctliq)
        if refrigerant == "R744": MOR_correction = (0.000225755013421421 * MOR_correctliq) - 0.00280879370374927
        elif refrigerant == "R407A": MOR_correction = (0.00000414431651323856 * (MOR_correctliq ** 2)) + (0.000381908525139781 * MOR_correctliq) - 0.0163450053041212
        elif refrigerant == "R449A": MOR_correction = (0.00000414431651323856 * (MOR_correctliq ** 2)) + (0.000381908525139781 * MOR_correctliq) - 0.0163450053041212
        elif refrigerant == "R448A": MOR_correction = (0.00000414431651323856 * (MOR_correctliq ** 2)) + (0.000381908525139781 * MOR_correctliq) - 0.0163450053041212
        elif refrigerant == "R502": MOR_correction = (0.00000414431651323856 * (MOR_correctliq ** 2)) + (0.000381908525139781 * MOR_correctliq) - 0.0163450053041212
        elif refrigerant == "R507A": MOR_correction = (0.000302619054048837 * MOR_correctliq) - 0.00930188913363997
        elif refrigerant == "R22": MOR_correction = (0.000108153843367715 * MOR_correctliq) - 0.00329248681202757
        elif refrigerant == "R407C": MOR_correction = (0.00000420322918839302 * (MOR_correctliq ** 2)) + (0.000269608915211859 * MOR_correctliq) - 0.0134546663857195
        elif refrigerant == "R410A": MOR_correction = 0
        elif refrigerant == "R407F": MOR_correction = (0.00000347332380289385 * (MOR_correctliq ** 2)) + (0.000239205332540693 * MOR_correctliq) - 0.0121545316131988
        elif refrigerant == "R134a": MOR_correction = (0.000195224660107459 * MOR_correctliq) - 0.00591757011487048
        elif refrigerant == "R404A": MOR_correction = (0.0000156507169104918 * (MOR_correctliq ** 2)) + (0.000689621839324826 * MOR_correctliq) - 0.0392
        else: MOR_correction = (0.00000461020482461793 * (MOR_correctliq ** 2)) + (0.000217910548009675 * MOR_correctliq) - 0.012074621594626
        # st.write("MOR_correction:", MOR_correction)

        if refrigerant == "R744": MOR_correction2 = (-0.0000176412848988908 * (T_evap ** 2)) - (0.00164308248808803 * T_evap) - 0.0184308798286039
        elif refrigerant == "R407A": MOR_correction2 = (-0.000864076433837511 * T_evap) - 0.0145018190416687
        elif refrigerant == "R449A": MOR_correction2 = (-0.000835375233693285 * T_evap) - 0.0138846063856621
        elif refrigerant == "R448A": MOR_correction2 = (0.00000171366802431428 * (T_evap ** 2)) - (0.000865528727278154 * T_evap) - 0.0152961902042161
        elif refrigerant == "R502": MOR_correction2 = (0.00000484734071020993 * (T_evap ** 2)) - (0.000624822304716683 * T_evap) - 0.0128725684240106
        elif refrigerant == "R507A": MOR_correction2 = (-0.000701333343440148 * T_evap) - 0.0114900933623056
        elif refrigerant == "R22": MOR_correction2 = (0.00000636798209134899 * (T_evap ** 2)) - (0.000157783204337396 * T_evap) - 0.00575251626397381
        elif refrigerant == "R407C": MOR_correction2 = (-0.00000665735727676349 * (T_evap ** 2)) - (0.000894860288947537 * T_evap) - 0.0116054361757929
        elif refrigerant == "R410A": MOR_correction2 = (-0.000672268853990701 * T_evap) - 0.0111802230098585
        elif refrigerant == "R407F": MOR_correction2 = (0.00000263731418614519 * (T_evap ** 2)) - (0.000683997257738699 * T_evap) - 0.0126005968942147
        elif refrigerant == "R134a": MOR_correction2 = (-0.00000823045532174214 * (T_evap ** 2)) - (0.00108063672211041 * T_evap) - 0.0217411206961643
        elif refrigerant == "R404A": MOR_correction2 = (0.00000342378568620316 * (T_evap ** 2)) - (0.000329572335134041 * T_evap) - 0.00706087606597149
        else: MOR_correction2 = (-0.000711441807827186 * T_evap) - 0.0118194116436425
        # st.write("MOR_correction2:", MOR_correction2)
        
        if T_evap < -40: MOR = ""
        elif T_evap > 4: MOR = ""
        else: MOR = (1 - MOR_correction) * (1 - MOR_correction2) * MOR_pre
        # st.write("MOR:", MOR)
    else:
        velocity_m_s = None

    # Oil return check
    adjusted_duty_kw = evap_capacity_kw * (required_oil_duty_pct / 100.0)
    # st.write("adjusted_duty_kw:", adjusted_duty_kw)

    reynolds = (density * velocity_m_s * ID_m) / 1
    
    st.subheader("Results")

    if velocity_m_s:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Refrigerant Velocity", f"{velocity_m_s:.2f} m/s")

        with col2:
            st.metric("Suction Density", f"{density:.2f} kg/m3")

        with col3:
            if MOR == "":
                st.metric("MOR (%)", "")
            else:
                st.metric("MOR (%)", f"{MOR:.1f} %")

        with col4:
            st.metric("Re", f"{reynolds:.1f}")

    if isinstance(MOR, (int, float)):
        is_ok, message = (True, "✅ OK") if required_oil_duty_pct >= MOR else (False, "❌ Insufficient flow")
    else:
        is_ok, message = (False, "")

    if is_ok:
        st.success(f"{message}")
    else:
        st.error(f"{message}")
