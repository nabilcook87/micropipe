
import streamlit as st
from utils.network_builder import NetworkBuilder
from utils.pressure_temp_converter import PressureTemperatureConverter
from utils.system_pressure_checker import check_pipe_rating, _pipe_rating_data, get_pipe_options
import pandas as pd
import math
import bisect
import numpy as np

# Make metric numbers & labels smaller
st.markdown("""
<style>
/* number */
div[data-testid="stMetricValue"] > div {
    font-size: 30px;            /* default is ~36px; pick what you like */
    line-height: 1.2;
}
/* label (e.g., "Refrigerant Velocity") */
div[data-testid="stMetricLabel"] > div {
    font-size: 14px;
}
/* optional: delta arrow/number size */
div[data-testid="stMetricDelta"] svg, 
div[data-testid="stMetricDelta"] > div {
    height: 14px; width: 14px; font-size: 14px;
}
</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="Micropipe - Refrigeration Pipe Sizing", layout="wide")
st.title("MicroPipe")

# Sidebar for tools and settings
st.sidebar.title("Tools & Utilities")
tool_selection = st.sidebar.radio("Select Tool", [
    "Manual Calculation",
    "Oil Return Checker",
    "Pressure ↔ Temperature Converter",
    "Pressure Drop ↔ Temperature Penalty",
    "System Pressure Checker"
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

    # --- helpers ---
    def _nps_inch_to_mm(nps_str: str) -> float:
        # e.g. "1-1/8", '1"', "3/8"
        s = str(nps_str).replace('"', '').strip()
        if not s:
            return float('nan')
        parts = s.split('-')
        tot_in = 0.0
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if '/' in p:
                num, den = p.split('/')
                tot_in += float(num) / float(den)
            else:
                tot_in += float(p)
        return tot_in * 25.4  # mm

    ss = st.session_state

    # 1) Pipe material
    with col2:
        if refrigerant == "R717":
            excluded_materials = ["Copper ACR", "Copper EN12735"]
            pipe_materials = sorted(m for m in pipe_data["Material"].dropna().unique()
                                    if m not in excluded_materials)
        else:
            pipe_materials = sorted(pipe_data["Material"].dropna().unique())

        selected_material = st.selectbox("Pipe Material", pipe_materials, key="material")
    
    # detect material change
    material_changed = ss.get("last_material") is not None and ss.last_material != selected_material
    ss.last_material = selected_material

    # 2) Sizes for selected material (de-duped)
    material_df = pipe_data[pipe_data["Material"] == selected_material].copy()

    sizes_df = (
        material_df[["Nominal Size (inch)", "Nominal Size (mm)"]]
        .dropna(subset=["Nominal Size (inch)"])
        .assign(**{
            "Nominal Size (inch)": lambda d: d["Nominal Size (inch)"].astype(str).str.strip(),
        })
        .drop_duplicates(subset=["Nominal Size (inch)"], keep="first")
    )

    # make sure we have a numeric mm per nominal (fallback: parse the inch string)
    sizes_df["mm_num"] = pd.to_numeric(sizes_df.get("Nominal Size (mm)"), errors="coerce")
    sizes_df.loc[sizes_df["mm_num"].isna(), "mm_num"] = sizes_df.loc[sizes_df["mm_num"].isna(), "Nominal Size (inch)"].apply(_nps_inch_to_mm)

    pipe_sizes = sizes_df["Nominal Size (inch)"].tolist()
    mm_map = dict(zip(sizes_df["Nominal Size (inch)"], sizes_df["mm_num"]))

    # choose default index
    def _closest_index(target_mm: float) -> int:
        mm_list = [mm_map[s] for s in pipe_sizes]
        return min(range(len(mm_list)), key=lambda i: abs(mm_list[i] - target_mm)) if mm_list else 0

    default_index = 0
    if material_changed and "prev_pipe_mm" in ss:
        default_index = _closest_index(ss.prev_pipe_mm)
    elif selected_material == "Copper ACR" and ("1-1/8" in pipe_sizes or '1-1/8"' in pipe_sizes):
        # first load or no previous selection → prefer 1-1/8" for Copper ACR
        want = "1-1/8" if "1-1/8" in pipe_sizes else '1-1/8"'
        default_index = pipe_sizes.index(want)
    elif "selected_size" in ss and ss.selected_size in pipe_sizes:
        # if Streamlit kept the selection, use it
        default_index = pipe_sizes.index(ss.selected_size)

    with col1:
        selected_size = st.selectbox(
            "Nominal Pipe Size (inch)",
            pipe_sizes,
            index=default_index,
            key="selected_size",
        )

    # remember the selected size in mm for next material change
    ss.prev_pipe_mm = float(mm_map.get(selected_size, float("nan")))

    # 3) Gauge (if applicable)
    gauge_options = material_df[material_df["Nominal Size (inch)"].astype(str).str.strip() == selected_size]
    if "Gauge" in gauge_options.columns and gauge_options["Gauge"].notna().any():
        gauges = sorted(gauge_options["Gauge"].dropna().unique())
        with col2:
            selected_gauge = st.selectbox("Copper Gauge", gauges, key="gauge")
        selected_pipe_row = gauge_options[gauge_options["Gauge"] == selected_gauge].iloc[0]
    else:
        selected_pipe_row = gauge_options.iloc[0]

    # Pipe parameters
    pipe_size_inch = selected_pipe_row["Nominal Size (inch)"]
    ID_mm = selected_pipe_row["ID_mm"]

    with col1:
        evap_capacity_kw = st.number_input("Evaporator Capacity (kW)", min_value=0.03, max_value=20000.0, value=10.0, step=1.0)

        # --- Base ranges per refrigerant ---
        if refrigerant in ("R23", "R508B"):
            evap_min, evap_max, evap_default = -100.0, -20.0, -80.0
            maxliq_min, maxliq_max, maxliq_default = -100.0, 10.0, -30.0
            minliq_min, minliq_max, minliq_default = -100.0, 10.0, -40.0
        elif refrigerant == "R744":
            evap_min, evap_max, evap_default = -50.0, 20.0, -10.0
            maxliq_min, maxliq_max, maxliq_default = -50.0, 30.0, 15.0
            minliq_min, minliq_max, minliq_default = -50.0, 30.0, 10.0
        else:
            evap_min, evap_max, evap_default = -50.0, 30.0, -10.0
            maxliq_min, maxliq_max, maxliq_default = -50.0, 60.0, 40.0
            minliq_min, minliq_max, minliq_default = -50.0, 60.0, 20.0

        # --- Init state (widget-backed) ---
        ss = st.session_state
        
        if "last_refrigerant" not in ss or ss.last_refrigerant != refrigerant:
            ss.maxliq_temp   = maxliq_default
            ss.minliq_temp = minliq_default
            ss.evap_temp   = evap_default
            ss.last_refrigerant = refrigerant
        
        ss.setdefault("maxliq_temp",   maxliq_default)
        ss.setdefault("minliq_temp", minliq_default)
        ss.setdefault("evap_temp",   evap_default)

        if "minliq_temp" in ss and "maxliq_temp" in ss:
            ss.minliq_temp = min(ss.maxliq_temp, ss.minliq_temp)

        if "minliq_temp" in ss and "maxliq_temp" in ss and "evap_temp" in ss:
            ss.evap_temp = min(ss.maxliq_temp, ss.minliq_temp, ss.evap_temp)

        # --- Callbacks implementing your downstream clamping logic ---
        def on_change_maxliq():
            # When cond changes: clamp minliq down to cond, then evap down to minliq
            ss.minliq_temp = min(ss.minliq_temp, ss.maxliq_temp)
            ss.evap_temp   = min(ss.evap_temp,   ss.minliq_temp)

        def on_change_minliq():
            # When minliq changes: clamp minliq down to cond, then evap down to minliq
            ss.minliq_temp = min(ss.minliq_temp, ss.maxliq_temp)
            ss.evap_temp   = min(ss.evap_temp,   ss.minliq_temp)

        def on_change_evap():
            # When evap changes: clamp evap down to minliq
            ss.evap_temp   = min(ss.evap_temp,   ss.minliq_temp)

        # --- Inputs with inclusive caps (≤), same order as your code ---
        maxliq_temp = st.number_input(
            "Max Liquid Temperature (°C)",
            min_value=maxliq_min, max_value=maxliq_max,
            value=ss.maxliq_temp, step=1.0, key="maxliq_temp",
            on_change=on_change_maxliq,
        )

        minliq_temp = st.number_input(
            "Min Liquid Temperature (°C)",
            min_value=minliq_min, max_value=min(maxliq_temp, minliq_max),
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
    from utils.refrigerant_viscosities import RefrigerantViscosities
    from utils.pipe_length_volume_calc import get_pipe_id_mm
    from utils.oil_return_checker import check_oil_return

    T_evap = evaporating_temp
    T_cond = maxliq_temp

    props = RefrigerantProperties()
    h_in = props.get_properties(refrigerant, T_cond)["enthalpy_liquid2"]
    #st.write("h_in:", h_in)
    # for velocity
    h_inmin = props.get_properties(refrigerant, minliq_temp)["enthalpy_liquid2"]
    #st.write("h_inmin:", h_inmin)
    h_inlet = props.get_properties(refrigerant, T_cond)["enthalpy_liquid"]
    #st.write("h_inlet:", h_inlet)
    h_inletmin = props.get_properties(refrigerant, minliq_temp)["enthalpy_liquid"]
    #st.write("h_inletmin:", h_inletmin)
    h_evap = props.get_properties(refrigerant, T_evap)["enthalpy_vapor"]
    #st.write("h_evap:", h_evap)
    h_10K = props.get_properties(refrigerant, T_evap)["enthalpy_super"]
    #st.write("h_10K:", h_10K)
    hdiff_10K = h_10K - h_evap
    #st.write("hdiff_10K:", hdiff_10K)
    hdiff_custom = hdiff_10K * min(max(superheat_K, 5), 30) / 10
    #st.write("hdiff_custom:", hdiff_custom)
    h_super = h_evap + hdiff_custom
    #st.write("h_super:", h_super)
    h_foroil = (h_evap + h_super) / 2
    #st.write("h_foroil:", h_foroil)
    
    delta_h = h_evap - h_in
    #st.write("delta_h:", delta_h)
    delta_hmin = h_evap - h_inmin
    #st.write("delta_hmin:", delta_hmin)
    
    delta_h_foroil = h_foroil - h_inlet
    #st.write("delta_h_foroil:", delta_h_foroil)
    delta_h_foroilmin = h_foroil - h_inletmin
    #st.write("delta_h_foroilmin:", delta_h_foroilmin)

    mass_flow_kg_s = evap_capacity_kw / delta_h if delta_h > 0 else 0.01
    #st.write("mass_flow_kg_s:", mass_flow_kg_s)
    mass_flow_kg_smin = evap_capacity_kw / delta_hmin if delta_hmin > 0 else 0.01
    #st.write("mass_flow_kg_smin:", mass_flow_kg_smin)

    mass_flow_foroil = evap_capacity_kw / delta_h_foroil if delta_h_foroil > 0 else 0.01
    #st.write("mass_flow_foroil:", mass_flow_foroil)
    mass_flow_foroilmin = evap_capacity_kw / delta_h_foroilmin if delta_h_foroilmin > 0 else 0.01
    #st.write("mass_flow_foroilmin:", mass_flow_foroilmin)

    # Calculate velocity for transparency
    if ID_mm is not None:
        ID_m = ID_mm / 1000.0
        #st.write("ID_mm:", ID_mm)
        #st.write("ID_m:", ID_m)
        area_m2 = math.pi * (ID_m / 2) ** 2
        #st.write("area_m2:", area_m2)
        density_super = RefrigerantDensities().get_density(refrigerant, T_evap - max_penalty + 273.15, superheat_K)
        #st.write("density_super:", density_super)
        density_super2a = RefrigerantDensities().get_density(refrigerant, T_evap + 273.15, ((superheat_K + 5) / 2))
        #st.write("density_super2a:", density_super2a)
        density_super2b = RefrigerantDensities().get_density(refrigerant, T_evap - max_penalty + 273.15, ((superheat_K + 5) / 2))
        #st.write("density_super2b:", density_super2b)
        density_super2 = (density_super2a + density_super2b) / 2
        #st.write("density_super2:", density_super2)
        density_super_foroil = RefrigerantDensities().get_density(refrigerant, T_evap + 273.15, min(max(superheat_K, 5), 30))
        #st.write("density_super_foroil:", density_super_foroil)
        density_sat = RefrigerantProperties().get_properties(refrigerant, T_evap)["density_vapor"]
        #st.write("density_sat:", density_sat)
        density_5K = RefrigerantDensities().get_density(refrigerant, T_evap + 273.15, 5)
        #st.write("density_5K:", density_5K)
        density = (density_super + density_5K) / 2
        #st.write("density:", density)
        density_foroil = (density_super_foroil + density_sat) / 2
        #st.write("density_foroil:", density_foroil)
        velocity_m_s1 = mass_flow_kg_s / (area_m2 * density)
        #st.write("velocity_m_s1:", velocity_m_s1)
        velocity_m_s1min = mass_flow_kg_smin / (area_m2 * density)
        #st.write("velocity_m_s1min:", velocity_m_s1min)
        velocity_m_s2 = mass_flow_kg_s / (area_m2 * density_super2)
        #st.write("velocity_m_s2:", velocity_m_s2)
        velocity_m_s2min = mass_flow_kg_smin / (area_m2 * density_super2)
        #st.write("velocity_m_s2min:", velocity_m_s2min)
        if refrigerant == "R744": velocity1_prop = 1
        elif refrigerant == "R404A":
            if superheat_K > 45: velocity1_prop = (0.0328330590542629 * superheat_K) - 1.47748765744183
            else: velocity1_prop = 0
        elif refrigerant == "R134a":
            if superheat_K > 30: velocity1_prop = (-0.000566085879684639 * (superheat_K ** 2)) + (0.075049554857083 * superheat_K) - 1.74200935399632
            else: velocity1_prop = 0
        elif refrigerant == "R407F": velocity1_prop = 1
        elif refrigerant == "R407A": velocity1_prop = 1
        elif refrigerant == "R410A": velocity1_prop = 1
        elif refrigerant == "R407C": velocity1_prop = 0
        elif refrigerant == "R22": velocity1_prop = 1
        elif refrigerant == "R502": velocity1_prop = 1
        elif refrigerant == "R507A": velocity1_prop = 1
        elif refrigerant == "R448A": velocity1_prop = 1
        elif refrigerant == "R449A": velocity1_prop = 1
        elif refrigerant == "R717": velocity1_prop = 1
        else:
            if superheat_K > 30: velocity1_prop = (0.0000406422632403154 * (superheat_K ** 2)) - (0.000541007136813307 * superheat_K) + 0.748882946418884
            else: velocity1_prop = 0.769230769230769
        # if refrigerant == "R744": velocity1_prop = (-0.0142814388381874 * max(superheat_K, 5)) + 1.07140719419094
        # else: velocity1_prop = (-0.00280805561137312 * max(superheat_K, 5)) + 1.01404027805687
        #st.write("velocity1_prop:", velocity1_prop)
        velocity_m_s = (velocity_m_s1 * velocity1_prop) + (velocity_m_s2 * (1 - velocity1_prop))
        #st.write("velocity_m_s:", velocity_m_s)
        velocity_m_smin = (velocity_m_s1min * velocity1_prop) + (velocity_m_s2min * (1 - velocity1_prop))
        #st.write("velocity_m_smin:", velocity_m_smin)
        if refrigerant in ["R23", "R508B"]:
            oil_density_sat = (-0.853841209044878 * T_evap) + 999.190772536527
            oil_density_super = (-0.853841209044878 * (T_evap + min(max(superheat_K, 5), 30))) + 999.190772536527
        else:
            oil_density_sat = (-0.00356060606060549 * (T_evap ** 2)) - (0.957878787878808 * T_evap) + 963.595454545455
            oil_density_super = (-0.00356060606060549 * ((T_evap + min(max(superheat_K, 5), 30)) ** 2)) - (0.957878787878808 * (T_evap + min(max(superheat_K, 5), 30))) + 963.595454545455
        #st.write("oil_density_sat:", oil_density_sat)
        #st.write("oil_density_super:", oil_density_super)
        oil_density = (oil_density_sat + oil_density_super) / 2
        #st.write("oil_density:", oil_density)
        
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
        #st.write("jg_half:", jg_half)
        
        MinMassFlux = (jg_half ** 2) * ((density_foroil * 9.81 * ID_m * (oil_density - density_foroil)) ** 0.5)
        #st.write("MinMassFluxy:", MinMassFlux)
        MinMassFlow = MinMassFlux * area_m2
        #st.write("MinMassFlow:", MinMassFlow)
        MOR_pre = (MinMassFlow / mass_flow_foroil) * 100
        #st.write("MOR_pre:", MOR_pre)
        MOR_premin = (MinMassFlow / mass_flow_foroilmin) * 100
        #st.write("MOR_premin:", MOR_premin)

        if refrigerant in ["R23", "R508B"]:
            MOR_correctliq = T_cond + 47.03
        else:
            MOR_correctliq = T_cond
        if refrigerant in ["R23", "R508B"]:
            MOR_correctliqmin = minliq_temp + 47.03
        else:
            MOR_correctliqmin = minliq_temp
        if refrigerant in ["R23", "R508B"]:
            evapoil = T_evap + 46.14
        else:
            evapoil = T_evap
        #st.write("MOR_correctliq:", MOR_correctliq)
        #st.write("evapoil:", evapoil)
        if refrigerant == "R744": MOR_correction = (0.000225755013421421 * MOR_correctliq) - 0.00280879370374927
        elif refrigerant == "R407A": MOR_correction = (0.00000414431651323856 * (MOR_correctliq ** 2)) + (0.000381908525139781 * MOR_correctliq) - 0.0163450053041212
        elif refrigerant == "R449A": MOR_correction = (0.00000414431651323856 * (MOR_correctliq ** 2)) + (0.000381908525139781 * MOR_correctliq) - 0.0163450053041212
        elif refrigerant == "R448A": MOR_correction = (0.00000414431651323856 * (MOR_correctliq ** 2)) + (0.000381908525139781 * MOR_correctliq) - 0.0163450053041212
        elif refrigerant == "R502": MOR_correction = (0.00000414431651323856 * (MOR_correctliq ** 2)) + (0.000381908525139781 * MOR_correctliq) - 0.0163450053041212
        elif refrigerant == "R507A": MOR_correction = (0.000302619054048837 * MOR_correctliq) - 0.00930188913363997
        elif refrigerant == "R22": MOR_correction = (0.000108153843367715 * MOR_correctliq) - 0.00329248681202757
        elif refrigerant == "R407C": MOR_correction = (0.00000420322918839302 * (max(MOR_correctliq, -32.0716410083429) ** 2)) + (0.000269608915211859 * max(MOR_correctliq, -32.0716410083429)) - 0.0134546663857195
        elif refrigerant == "R410A": MOR_correction = 0
        elif refrigerant == "R407F": MOR_correction = (0.00000347332380289385 * (max(MOR_correctliq, -34.4346433150568) ** 2)) + (0.000239205332540693 * max(MOR_correctliq, -34.4346433150568)) - 0.0121545316131988
        elif refrigerant == "R134a": MOR_correction = (0.000195224660107459 * MOR_correctliq) - 0.00591757011487048
        elif refrigerant == "R404A": MOR_correction = (0.0000156507169104918 * (max(MOR_correctliq, -22.031637377024) ** 2)) + (0.000689621839324826 * max(MOR_correctliq, -22.031637377024)) - 0.0392
        else: MOR_correction = (0.00000461020482461793 * (max(MOR_correctliq, -23.6334996273983) ** 2)) + (0.000217910548009675 * max(MOR_correctliq, -23.6334996273983)) - 0.012074621594626
        #st.write("MOR_correction:", MOR_correction)

        if refrigerant == "R744": MOR_correctionmin = (0.000225755013421421 * MOR_correctliqmin) - 0.00280879370374927
        elif refrigerant == "R407A": MOR_correctionmin = (0.00000414431651323856 * (MOR_correctliqmin ** 2)) + (0.000381908525139781 * MOR_correctliqmin) - 0.0163450053041212
        elif refrigerant == "R449A": MOR_correctionmin = (0.00000414431651323856 * (MOR_correctliqmin ** 2)) + (0.000381908525139781 * MOR_correctliqmin) - 0.0163450053041212
        elif refrigerant == "R448A": MOR_correctionmin = (0.00000414431651323856 * (MOR_correctliqmin ** 2)) + (0.000381908525139781 * MOR_correctliqmin) - 0.0163450053041212
        elif refrigerant == "R502": MOR_correctionmin = (0.00000414431651323856 * (MOR_correctliqmin ** 2)) + (0.000381908525139781 * MOR_correctliqmin) - 0.0163450053041212
        elif refrigerant == "R507A": MOR_correctionmin = (0.000302619054048837 * MOR_correctliqmin) - 0.00930188913363997
        elif refrigerant == "R22": MOR_correctionmin = (0.000108153843367715 * MOR_correctliqmin) - 0.00329248681202757
        elif refrigerant == "R407C": MOR_correctionmin = (0.00000420322918839302 * (max(MOR_correctliqmin, -32.0716410083429) ** 2)) + (0.000269608915211859 * max(MOR_correctliqmin, -32.0716410083429)) - 0.0134546663857195
        elif refrigerant == "R410A": MOR_correctionmin = 0
        elif refrigerant == "R407F": MOR_correctionmin = (0.00000347332380289385 * (max(MOR_correctliqmin, -34.4346433150568) ** 2)) + (0.000239205332540693 * max(MOR_correctliqmin, -34.4346433150568)) - 0.0121545316131988
        elif refrigerant == "R134a": MOR_correctionmin = (0.000195224660107459 * MOR_correctliqmin) - 0.00591757011487048
        elif refrigerant == "R404A": MOR_correctionmin = (0.0000156507169104918 * (max(MOR_correctliqmin, -22.031637377024) ** 2)) + (0.000689621839324826 * max(MOR_correctliqmin, -22.031637377024)) - 0.0392
        else: MOR_correctionmin = (0.00000461020482461793 * (max(MOR_correctliqmin, -23.6334996273983) ** 2)) + (0.000217910548009675 * max(MOR_correctliqmin, -23.6334996273983)) - 0.012074621594626
        #st.write("MOR_correctionmin:", MOR_correctionmin)

        if refrigerant == "R744": MOR_correction2 = (-0.0000176412848988908 * (evapoil ** 2)) - (0.00164308248808803 * evapoil) - 0.0184308798286039
        elif refrigerant == "R407A": MOR_correction2 = (-0.000864076433837511 * evapoil) - 0.0145018190416687
        elif refrigerant == "R449A": MOR_correction2 = (-0.000835375233693285 * evapoil) - 0.0138846063856621
        elif refrigerant == "R448A": MOR_correction2 = (0.00000171366802431428 * (evapoil ** 2)) - (0.000865528727278154 * evapoil) - 0.0152961902042161
        elif refrigerant == "R502": MOR_correction2 = (0.00000484734071020993 * (evapoil ** 2)) - (0.000624822304716683 * evapoil) - 0.0128725684240106
        elif refrigerant == "R507A": MOR_correction2 = (-0.000701333343440148 * evapoil) - 0.0114900933623056
        elif refrigerant == "R22": MOR_correction2 = (0.00000636798209134899 * (evapoil ** 2)) - (0.000157783204337396 * evapoil) - 0.00575251626397381
        elif refrigerant == "R407C": MOR_correction2 = (-0.00000665735727676349 * (evapoil ** 2)) - (0.000894860288947537 * evapoil) - 0.0116054361757929
        elif refrigerant == "R410A": MOR_correction2 = (-0.000672268853990701 * evapoil) - 0.0111802230098585
        elif refrigerant == "R407F": MOR_correction2 = (0.00000263731418614519 * (evapoil ** 2)) - (0.000683997257738699 * evapoil) - 0.0126005968942147
        elif refrigerant == "R134a": MOR_correction2 = (-0.00000823045532174214 * (evapoil ** 2)) - (0.00108063672211041 * evapoil) - 0.0217411206961643
        elif refrigerant == "R404A": MOR_correction2 = (0.00000342378568620316 * (evapoil ** 2)) - (0.000329572335134041 * evapoil) - 0.00706087606597149
        else: MOR_correction2 = (-0.000711441807827186 * evapoil) - 0.0118194116436425
        #st.write("MOR_correction2:", MOR_correction2)
        
        if refrigerant in ["R23", "R508B"]:
            if T_evap < -86:
                MOR = ""
                MORmin = ""
                MORfinal = ""
            elif T_evap > -42:
                MOR = ""
                MORmin = ""
                MORfinal = ""
            else:
                MOR = (1 - MOR_correction) * (1 - MOR_correction2) * MOR_pre
                MORmin = (1 - MOR_correctionmin) * (1 - MOR_correction2) * MOR_premin
                MORfinal = max(MOR, MORmin)
        else:    
            if T_evap < -40:
                MOR = ""
                MORmin = ""
                MORfinal = ""
            elif T_evap > 4:
                MOR = ""
                MORmin = ""
                MORfinal = ""
            else:
                MOR = (1 - MOR_correction) * (1 - MOR_correction2) * MOR_pre
                MORmin = (1 - MOR_correctionmin) * (1 - MOR_correction2) * MOR_premin
                MORfinal = max(MOR, MORmin)
        #st.write("MOR:", MOR)
        #st.write("MORmin:", MORmin)
        #st.write("MORfinal:", MORfinal)
        velocity_m_sfinal = max(velocity_m_s, velocity_m_smin)
        #st.write("velocity_m_sfinal:", velocity_m_sfinal)
    else:
        velocity_m_s = None
        velocity_m_smin = None
        velocity_m_sfinal = None

    # Oil return check
    adjusted_duty_kw = evap_capacity_kw * (required_oil_duty_pct / 100.0)
    #st.write("adjusted_duty_kw:", adjusted_duty_kw)

    density_recalc = mass_flow_kg_s / (velocity_m_s * area_m2)
    #st.write("density_recalc:", density_recalc)
    
    if MORfinal == "":
        MinCap = ""
    else:
        MinCap = MORfinal * evap_capacity_kw / 100
    
    st.subheader("Results")
    
    if velocity_m_sfinal:
        col1, col2 = st.columns(2)

        with col1:
            if MORfinal == "":
                st.metric("Minimum Capacity", "")
            else:                
                st.metric("Minimum Capacity", f"{MinCap:.4f}kW")

        with col2:
            if MORfinal == "":
                st.metric("Minimum Oil Return", "")
            else:
                st.metric("Minimum Oil Return", f"{MORfinal:.1f}%")

    if isinstance(MORfinal, (int, float)):
        is_ok, message = (True, "✅ OK") if required_oil_duty_pct >= MORfinal else (False, "❌ Insufficient flow")
    else:
        is_ok, message = (False, "")

    if is_ok:
        st.success(f"{message}")
    else:
        st.error(f"{message}")

elif tool_selection == "Manual Calculation":
    st.subheader("Manual Calculation")
    
    mode = st.radio("", ["Dry Suction", "Liquid", "Discharge", "Drain", "Pumped Liquid", "Wet Suction"], index=1, horizontal=True, label_visibility="collapsed")
    
    if mode == "Dry Suction":
        
        col1, col2, col3, col4 = st.columns(4)
    
        with col1:
            refrigerant = st.selectbox("Refrigerant", [
                "R404A", "R134a", "R407F", "R744", "R410A",
                "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A", "R454C", "R455A", "R407A",
                "R290", "R1270", "R600a", "R717", "R1234ze", "R1234yf", "R12", "R11", "R454B", "R450A", "R513A", "R23", "R508B", "R502"
            ])
    
        # Load pipe data
        pipe_data = pd.read_csv("data/pipe_pressure_ratings_full.csv")
    
        # --- helpers ---
        def _nps_inch_to_mm(nps_str: str) -> float:
            # e.g. "1-1/8", '1"', "3/8"
            s = str(nps_str).replace('"', '').strip()
            if not s:
                return float('nan')
            parts = s.split('-')
            tot_in = 0.0
            for p in parts:
                p = p.strip()
                if not p:
                    continue
                if '/' in p:
                    num, den = p.split('/')
                    tot_in += float(num) / float(den)
                else:
                    tot_in += float(p)
            return tot_in * 25.4  # mm
    
        ss = st.session_state
    
        # 1) Pipe material
        with col2:
            if refrigerant == "R717":
                excluded_materials = ["Copper ACR", "Copper EN12735"]
                pipe_materials = sorted(m for m in pipe_data["Material"].dropna().unique()
                                        if m not in excluded_materials)
            else:
                pipe_materials = sorted(pipe_data["Material"].dropna().unique())
    
            selected_material = st.selectbox("Pipe Material", pipe_materials, key="material")
        
        # detect material change
        material_changed = ss.get("last_material") is not None and ss.last_material != selected_material
        ss.last_material = selected_material
    
        # 2) Sizes for selected material (de-duped)
        material_df = pipe_data[pipe_data["Material"] == selected_material].copy()
    
        sizes_df = (
            material_df[["Nominal Size (inch)", "Nominal Size (mm)"]]
            .dropna(subset=["Nominal Size (inch)"])
            .assign(**{
                "Nominal Size (inch)": lambda d: d["Nominal Size (inch)"].astype(str).str.strip(),
            })
            .drop_duplicates(subset=["Nominal Size (inch)"], keep="first")
        )
    
        # make sure we have a numeric mm per nominal (fallback: parse the inch string)
        sizes_df["mm_num"] = pd.to_numeric(sizes_df.get("Nominal Size (mm)"), errors="coerce")
        sizes_df.loc[sizes_df["mm_num"].isna(), "mm_num"] = sizes_df.loc[sizes_df["mm_num"].isna(), "Nominal Size (inch)"].apply(_nps_inch_to_mm)
    
        pipe_sizes = sizes_df["Nominal Size (inch)"].tolist()
        mm_map = dict(zip(sizes_df["Nominal Size (inch)"], sizes_df["mm_num"]))
    
        # choose default index
        def _closest_index(target_mm: float) -> int:
            mm_list = [mm_map[s] for s in pipe_sizes]
            return min(range(len(mm_list)), key=lambda i: abs(mm_list[i] - target_mm)) if mm_list else 0

        # --- Handle deferred pipe selection (from "Select Optimal Pipe Size" button) ---
        if "_next_selected_size" in st.session_state:
            new_val = st.session_state["_next_selected_size"]
            # ✅ directly set the selectbox value itself
            st.session_state["selected_size"] = new_val
            # clean up the temporary flag
            del st.session_state["_next_selected_size"]

        default_index = 0
        override_val = st.session_state.get("selected_size_override")
        if override_val and override_val in pipe_sizes:
            default_index = pipe_sizes.index(override_val)
        elif material_changed and "prev_pipe_mm" in ss:
            default_index = _closest_index(ss.prev_pipe_mm)
        elif selected_material == "Copper ACR" and ("1-1/8" in pipe_sizes or '1-1/8"' in pipe_sizes):
            want = "1-1/8" if "1-1/8" in pipe_sizes else '1-1/8"'
            default_index = pipe_sizes.index(want)
        elif "selected_size" in ss and ss.selected_size in pipe_sizes:
            default_index = pipe_sizes.index(ss.selected_size)
        
        with col1:
            selected_size = st.selectbox(
                "Nominal Pipe Size (inch)",
                pipe_sizes,
                index=default_index,
                key="selected_size",
            )

        ss.prev_pipe_mm = float(mm_map.get(selected_size, float("nan")))
        
        # remember the selected size in mm for next material change
        ss.prev_pipe_mm = float(mm_map.get(selected_size, float("nan")))
    
        # 3) Gauge (if applicable)
        gauge_options = material_df[material_df["Nominal Size (inch)"].astype(str).str.strip() == selected_size]
        if "Gauge" in gauge_options.columns and gauge_options["Gauge"].notna().any():
            gauges = sorted(gauge_options["Gauge"].dropna().unique())
            with col2:
                selected_gauge = st.selectbox("Copper Gauge", gauges, key="gauge")
            selected_pipe_row = gauge_options[gauge_options["Gauge"] == selected_gauge].iloc[0]
        else:
            selected_pipe_row = gauge_options.iloc[0]
    
        # Pipe parameters
        pipe_size_inch = selected_pipe_row["Nominal Size (inch)"]
        ID_mm = selected_pipe_row["ID_mm"]
    
        with col1:
            evap_capacity_kw = st.number_input("Evaporator Capacity (kW)", min_value=0.03, max_value=20000.0, value=10.0, step=1.0)
    
            # --- Base ranges per refrigerant ---
            if refrigerant in ("R23", "R508B"):
                evap_min, evap_max, evap_default = -100.0, -20.0, -80.0
                maxliq_min, maxliq_max, maxliq_default = -100.0, 10.0, -30.0
                minliq_min, minliq_max, minliq_default = -100.0, 10.0, -40.0
            elif refrigerant == "R744":
                evap_min, evap_max, evap_default = -50.0, 20.0, -10.0
                maxliq_min, maxliq_max, maxliq_default = -50.0, 30.0, 15.0
                minliq_min, minliq_max, minliq_default = -50.0, 30.0, 10.0
            else:
                evap_min, evap_max, evap_default = -50.0, 30.0, -10.0
                maxliq_min, maxliq_max, maxliq_default = -50.0, 60.0, 40.0
                minliq_min, minliq_max, minliq_default = -50.0, 60.0, 20.0
    
            # --- Init state (widget-backed) ---
            ss = st.session_state
    
            if "last_refrigerant" not in ss or ss.last_refrigerant != refrigerant:
                ss.maxliq_temp   = maxliq_default
                ss.minliq_temp = minliq_default
                ss.evap_temp   = evap_default
                ss.last_refrigerant = refrigerant
            
            ss.setdefault("maxliq_temp",   maxliq_default)
            ss.setdefault("minliq_temp", minliq_default)
            ss.setdefault("evap_temp",   evap_default)

            if "minliq_temp" in ss and "maxliq_temp" in ss:
                ss.minliq_temp = min(ss.maxliq_temp, ss.minliq_temp)

            if "minliq_temp" in ss and "maxliq_temp" in ss and "evap_temp" in ss:
                ss.evap_temp = min(ss.maxliq_temp, ss.minliq_temp, ss.evap_temp)
    
            # --- Callbacks implementing your downstream clamping logic ---
            def on_change_maxliq():
                # When cond changes: clamp minliq down to cond, then evap down to minliq
                ss.minliq_temp = min(ss.minliq_temp, ss.maxliq_temp)
                ss.evap_temp   = min(ss.evap_temp,   ss.minliq_temp)
    
            def on_change_minliq():
                # When minliq changes: clamp minliq down to cond, then evap down to minliq
                ss.minliq_temp = min(ss.minliq_temp, ss.maxliq_temp)
                ss.evap_temp   = min(ss.evap_temp,   ss.minliq_temp)
    
            def on_change_evap():
                # When evap changes: clamp evap down to minliq
                ss.evap_temp   = min(ss.evap_temp,   ss.minliq_temp)
    
            # --- Inputs with inclusive caps (≤), same order as your code ---
            maxliq_temp = st.number_input(
                "Max Liquid Temperature (°C)",
                min_value=maxliq_min, max_value=maxliq_max,
                value=ss.maxliq_temp, step=1.0, key="maxliq_temp",
                on_change=on_change_maxliq,
            )
    
            minliq_temp = st.number_input(
                "Min Liquid Temperature (°C)",
                min_value=minliq_min, max_value=min(maxliq_temp, minliq_max),
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
    
        with col3:
            L = st.number_input("Pipe Length (m)", min_value=0.1, max_value=300.0, value=10.0, step=1.0)
            LRB = st.number_input("Long Radius Bends", min_value=0, max_value=50, value=0, step=1)
            SRB = st.number_input("Short Radius Bends", min_value=0, max_value=50, value=0, step=1)
            _45 = st.number_input("45° Bends", min_value=0, max_value=50, value=0, step=1)
            MAC = st.number_input("Machine Bends", min_value=0, max_value=50, value=0, step=1)
    
        with col4:
            ptrap = st.number_input("P Traps", min_value=0, max_value=10, value=0, step=1)
            ubend = st.number_input("U Bends", min_value=0, max_value=10, value=0, step=1)
            ball = st.number_input("Ball Valves", min_value=0, max_value=20, value=0, step=1)
            globe = st.number_input("Globe Valves", min_value=0, max_value=20, value=0, step=1)
            PLF = st.number_input("Pressure Loss Factors", min_value=0.0, max_value=20.0, value=0.0, step=0.1)
        
        from utils.refrigerant_properties import RefrigerantProperties
        from utils.refrigerant_densities import RefrigerantDensities
        from utils.refrigerant_viscosities import RefrigerantViscosities
        from utils.pipe_length_volume_calc import get_pipe_id_mm
        from utils.oil_return_checker import check_oil_return
    
        T_evap = evaporating_temp
        T_cond = maxliq_temp
    
        props = RefrigerantProperties()
        h_in = props.get_properties(refrigerant, T_cond)["enthalpy_liquid2"]
        #st.write("h_in:", h_in)
        # for velocity
        h_inmin = props.get_properties(refrigerant, minliq_temp)["enthalpy_liquid2"]
        #st.write("h_inmin:", h_inmin)
        h_inlet = props.get_properties(refrigerant, T_cond)["enthalpy_liquid"]
        #st.write("h_inlet:", h_inlet)
        h_inletmin = props.get_properties(refrigerant, minliq_temp)["enthalpy_liquid"]
        #st.write("h_inletmin:", h_inletmin)
        h_evap = props.get_properties(refrigerant, T_evap)["enthalpy_vapor"]
        #st.write("h_evap:", h_evap)
        h_10K = props.get_properties(refrigerant, T_evap)["enthalpy_super"]
        #st.write("h_10K:", h_10K)
        hdiff_10K = h_10K - h_evap
        #st.write("hdiff_10K:", hdiff_10K)
        hdiff_custom = hdiff_10K * min(max(superheat_K, 5), 30) / 10
        #st.write("hdiff_custom:", hdiff_custom)
        h_super = h_evap + hdiff_custom
        #st.write("h_super:", h_super)
        h_foroil = (h_evap + h_super) / 2
        #st.write("h_foroil:", h_foroil)
        
        delta_h = h_evap - h_in
        #st.write("delta_h:", delta_h)
        delta_hmin = h_evap - h_inmin
        #st.write("delta_hmin:", delta_hmin)
        
        delta_h_foroil = h_foroil - h_inlet
        #st.write("delta_h_foroil:", delta_h_foroil)
        delta_h_foroilmin = h_foroil - h_inletmin
        #st.write("delta_h_foroilmin:", delta_h_foroilmin)
    
        mass_flow_kg_s = evap_capacity_kw / delta_h if delta_h > 0 else 0.01
        #st.write("mass_flow_kg_s:", mass_flow_kg_s)
        mass_flow_kg_smin = evap_capacity_kw / delta_hmin if delta_hmin > 0 else 0.01
        #st.write("mass_flow_kg_smin:", mass_flow_kg_smin)
    
        mass_flow_foroil = evap_capacity_kw / delta_h_foroil if delta_h_foroil > 0 else 0.01
        #st.write("mass_flow_foroil:", mass_flow_foroil)
        mass_flow_foroilmin = evap_capacity_kw / delta_h_foroilmin if delta_h_foroilmin > 0 else 0.01
        #st.write("mass_flow_foroilmin:", mass_flow_foroilmin)
    
        # Calculate velocity for transparency
        if ID_mm is not None:
            ID_m = ID_mm / 1000.0
            #st.write("ID_mm:", ID_mm)
            #st.write("ID_m:", ID_m)
            area_m2 = math.pi * (ID_m / 2) ** 2
            #st.write("area_m2:", area_m2)
            density_super = RefrigerantDensities().get_density(refrigerant, T_evap - max_penalty + 273.15, superheat_K)
            #st.write("density_super:", density_super)
            density_super2a = RefrigerantDensities().get_density(refrigerant, T_evap + 273.15, ((superheat_K + 5) / 2))
            #st.write("density_super2a:", density_super2a)
            density_super2b = RefrigerantDensities().get_density(refrigerant, T_evap - max_penalty + 273.15, ((superheat_K + 5) / 2))
            #st.write("density_super2b:", density_super2b)
            density_super2 = (density_super2a + density_super2b) / 2
            #st.write("density_super2:", density_super2)
            density_super_foroil = RefrigerantDensities().get_density(refrigerant, T_evap + 273.15, min(max(superheat_K, 5), 30))
            #st.write("density_super_foroil:", density_super_foroil)
            density_sat = RefrigerantProperties().get_properties(refrigerant, T_evap)["density_vapor"]
            #st.write("density_sat:", density_sat)
            density_5K = RefrigerantDensities().get_density(refrigerant, T_evap + 273.15, 5)
            #st.write("density_5K:", density_5K)
            density = (density_super + density_5K) / 2
            #st.write("density:", density)
            density_foroil = (density_super_foroil + density_sat) / 2
            #st.write("density_foroil:", density_foroil)
            velocity_m_s1 = mass_flow_kg_s / (area_m2 * density)
            #st.write("velocity_m_s1:", velocity_m_s1)
            velocity_m_s1min = mass_flow_kg_smin / (area_m2 * density)
            #st.write("velocity_m_s1min:", velocity_m_s1min)
            velocity_m_s2 = mass_flow_kg_s / (area_m2 * density_super2)
            #st.write("velocity_m_s2:", velocity_m_s2)
            velocity_m_s2min = mass_flow_kg_smin / (area_m2 * density_super2)
            #st.write("velocity_m_s2min:", velocity_m_s2min)
            if refrigerant == "R744": velocity1_prop = 1
            elif refrigerant == "R404A":
                if superheat_K > 45: velocity1_prop = (0.0328330590542629 * superheat_K) - 1.47748765744183
                else: velocity1_prop = 0
            elif refrigerant == "R134a":
                if superheat_K > 30: velocity1_prop = (-0.000566085879684639 * (superheat_K ** 2)) + (0.075049554857083 * superheat_K) - 1.74200935399632
                else: velocity1_prop = 0
            elif refrigerant == "R407F": velocity1_prop = 1
            elif refrigerant == "R407A": velocity1_prop = 1
            elif refrigerant == "R410A": velocity1_prop = 1
            elif refrigerant == "R407C": velocity1_prop = 0
            elif refrigerant == "R22": velocity1_prop = 1
            elif refrigerant == "R502": velocity1_prop = 1
            elif refrigerant == "R507A": velocity1_prop = 1
            elif refrigerant == "R448A": velocity1_prop = 1
            elif refrigerant == "R449A": velocity1_prop = 1
            elif refrigerant == "R717": velocity1_prop = 1
            else:
                if superheat_K > 30: velocity1_prop = (0.0000406422632403154 * (superheat_K ** 2)) - (0.000541007136813307 * superheat_K) + 0.748882946418884
                else: velocity1_prop = 0.769230769230769
            # if refrigerant == "R744": velocity1_prop = (-0.0142814388381874 * max(superheat_K, 5)) + 1.07140719419094
            # else: velocity1_prop = (-0.00280805561137312 * max(superheat_K, 5)) + 1.01404027805687
            #st.write("velocity1_prop:", velocity1_prop)
            velocity_m_s = (velocity_m_s1 * velocity1_prop) + (velocity_m_s2 * (1 - velocity1_prop))
            #st.write("velocity_m_s:", velocity_m_s)
            velocity_m_smin = (velocity_m_s1min * velocity1_prop) + (velocity_m_s2min * (1 - velocity1_prop))
            #st.write("velocity_m_smin:", velocity_m_smin)
            if refrigerant in ["R23", "R508B"]:
                oil_density_sat = (-0.853841209044878 * T_evap) + 999.190772536527
                oil_density_super = (-0.853841209044878 * (T_evap + min(max(superheat_K, 5), 30))) + 999.190772536527
            else:
                oil_density_sat = (-0.00356060606060549 * (T_evap ** 2)) - (0.957878787878808 * T_evap) + 963.595454545455
                oil_density_super = (-0.00356060606060549 * ((T_evap + min(max(superheat_K, 5), 30)) ** 2)) - (0.957878787878808 * (T_evap + min(max(superheat_K, 5), 30))) + 963.595454545455
            #st.write("oil_density_sat:", oil_density_sat)
            #st.write("oil_density_super:", oil_density_super)
            oil_density = (oil_density_sat + oil_density_super) / 2
            #st.write("oil_density:", oil_density)
            
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
            #st.write("jg_half:", jg_half)
            
            MinMassFlux = (jg_half ** 2) * ((density_foroil * 9.81 * ID_m * (oil_density - density_foroil)) ** 0.5)
            #st.write("MinMassFluxy:", MinMassFlux)
            MinMassFlow = MinMassFlux * area_m2
            #st.write("MinMassFlow:", MinMassFlow)
            MOR_pre = (MinMassFlow / mass_flow_foroil) * 100
            #st.write("MOR_pre:", MOR_pre)
            MOR_premin = (MinMassFlow / mass_flow_foroilmin) * 100
            #st.write("MOR_premin:", MOR_premin)
    
            if refrigerant in ["R23", "R508B"]:
                MOR_correctliq = T_cond + 47.03
            else:
                MOR_correctliq = T_cond
            if refrigerant in ["R23", "R508B"]:
                MOR_correctliqmin = minliq_temp + 47.03
            else:
                MOR_correctliqmin = minliq_temp
            if refrigerant in ["R23", "R508B"]:
                evapoil = T_evap + 46.14
            else:
                evapoil = T_evap
            #st.write("MOR_correctliq:", MOR_correctliq)
            #st.write("evapoil:", evapoil)
            if refrigerant == "R744": MOR_correction = (0.000225755013421421 * MOR_correctliq) - 0.00280879370374927
            elif refrigerant == "R407A": MOR_correction = (0.00000414431651323856 * (MOR_correctliq ** 2)) + (0.000381908525139781 * MOR_correctliq) - 0.0163450053041212
            elif refrigerant == "R449A": MOR_correction = (0.00000414431651323856 * (MOR_correctliq ** 2)) + (0.000381908525139781 * MOR_correctliq) - 0.0163450053041212
            elif refrigerant == "R448A": MOR_correction = (0.00000414431651323856 * (MOR_correctliq ** 2)) + (0.000381908525139781 * MOR_correctliq) - 0.0163450053041212
            elif refrigerant == "R502": MOR_correction = (0.00000414431651323856 * (MOR_correctliq ** 2)) + (0.000381908525139781 * MOR_correctliq) - 0.0163450053041212
            elif refrigerant == "R507A": MOR_correction = (0.000302619054048837 * MOR_correctliq) - 0.00930188913363997
            elif refrigerant == "R22": MOR_correction = (0.000108153843367715 * MOR_correctliq) - 0.00329248681202757
            elif refrigerant == "R407C": MOR_correction = (0.00000420322918839302 * (max(MOR_correctliq, -32.0716410083429) ** 2)) + (0.000269608915211859 * max(MOR_correctliq, -32.0716410083429)) - 0.0134546663857195
            elif refrigerant == "R410A": MOR_correction = 0
            elif refrigerant == "R407F": MOR_correction = (0.00000347332380289385 * (max(MOR_correctliq, -34.4346433150568) ** 2)) + (0.000239205332540693 * max(MOR_correctliq, -34.4346433150568)) - 0.0121545316131988
            elif refrigerant == "R134a": MOR_correction = (0.000195224660107459 * MOR_correctliq) - 0.00591757011487048
            elif refrigerant == "R404A": MOR_correction = (0.0000156507169104918 * (max(MOR_correctliq, -22.031637377024) ** 2)) + (0.000689621839324826 * max(MOR_correctliq, -22.031637377024)) - 0.0392
            else: MOR_correction = (0.00000461020482461793 * (max(MOR_correctliq, -23.6334996273983) ** 2)) + (0.000217910548009675 * max(MOR_correctliq, -23.6334996273983)) - 0.012074621594626
            #st.write("MOR_correction:", MOR_correction)
    
            if refrigerant == "R744": MOR_correctionmin = (0.000225755013421421 * MOR_correctliqmin) - 0.00280879370374927
            elif refrigerant == "R407A": MOR_correctionmin = (0.00000414431651323856 * (MOR_correctliqmin ** 2)) + (0.000381908525139781 * MOR_correctliqmin) - 0.0163450053041212
            elif refrigerant == "R449A": MOR_correctionmin = (0.00000414431651323856 * (MOR_correctliqmin ** 2)) + (0.000381908525139781 * MOR_correctliqmin) - 0.0163450053041212
            elif refrigerant == "R448A": MOR_correctionmin = (0.00000414431651323856 * (MOR_correctliqmin ** 2)) + (0.000381908525139781 * MOR_correctliqmin) - 0.0163450053041212
            elif refrigerant == "R502": MOR_correctionmin = (0.00000414431651323856 * (MOR_correctliqmin ** 2)) + (0.000381908525139781 * MOR_correctliqmin) - 0.0163450053041212
            elif refrigerant == "R507A": MOR_correctionmin = (0.000302619054048837 * MOR_correctliqmin) - 0.00930188913363997
            elif refrigerant == "R22": MOR_correctionmin = (0.000108153843367715 * MOR_correctliqmin) - 0.00329248681202757
            elif refrigerant == "R407C": MOR_correctionmin = (0.00000420322918839302 * (max(MOR_correctliqmin, -32.0716410083429) ** 2)) + (0.000269608915211859 * max(MOR_correctliqmin, -32.0716410083429)) - 0.0134546663857195
            elif refrigerant == "R410A": MOR_correctionmin = 0
            elif refrigerant == "R407F": MOR_correctionmin = (0.00000347332380289385 * (max(MOR_correctliqmin, -34.4346433150568) ** 2)) + (0.000239205332540693 * max(MOR_correctliqmin, -34.4346433150568)) - 0.0121545316131988
            elif refrigerant == "R134a": MOR_correctionmin = (0.000195224660107459 * MOR_correctliqmin) - 0.00591757011487048
            elif refrigerant == "R404A": MOR_correctionmin = (0.0000156507169104918 * (max(MOR_correctliqmin, -22.031637377024) ** 2)) + (0.000689621839324826 * max(MOR_correctliqmin, -22.031637377024)) - 0.0392
            else: MOR_correctionmin = (0.00000461020482461793 * (max(MOR_correctliqmin, -23.6334996273983) ** 2)) + (0.000217910548009675 * max(MOR_correctliqmin, -23.6334996273983)) - 0.012074621594626
            #st.write("MOR_correctionmin:", MOR_correctionmin)
    
            if refrigerant == "R744": MOR_correction2 = (-0.0000176412848988908 * (evapoil ** 2)) - (0.00164308248808803 * evapoil) - 0.0184308798286039
            elif refrigerant == "R407A": MOR_correction2 = (-0.000864076433837511 * evapoil) - 0.0145018190416687
            elif refrigerant == "R449A": MOR_correction2 = (-0.000835375233693285 * evapoil) - 0.0138846063856621
            elif refrigerant == "R448A": MOR_correction2 = (0.00000171366802431428 * (evapoil ** 2)) - (0.000865528727278154 * evapoil) - 0.0152961902042161
            elif refrigerant == "R502": MOR_correction2 = (0.00000484734071020993 * (evapoil ** 2)) - (0.000624822304716683 * evapoil) - 0.0128725684240106
            elif refrigerant == "R507A": MOR_correction2 = (-0.000701333343440148 * evapoil) - 0.0114900933623056
            elif refrigerant == "R22": MOR_correction2 = (0.00000636798209134899 * (evapoil ** 2)) - (0.000157783204337396 * evapoil) - 0.00575251626397381
            elif refrigerant == "R407C": MOR_correction2 = (-0.00000665735727676349 * (evapoil ** 2)) - (0.000894860288947537 * evapoil) - 0.0116054361757929
            elif refrigerant == "R410A": MOR_correction2 = (-0.000672268853990701 * evapoil) - 0.0111802230098585
            elif refrigerant == "R407F": MOR_correction2 = (0.00000263731418614519 * (evapoil ** 2)) - (0.000683997257738699 * evapoil) - 0.0126005968942147
            elif refrigerant == "R134a": MOR_correction2 = (-0.00000823045532174214 * (evapoil ** 2)) - (0.00108063672211041 * evapoil) - 0.0217411206961643
            elif refrigerant == "R404A": MOR_correction2 = (0.00000342378568620316 * (evapoil ** 2)) - (0.000329572335134041 * evapoil) - 0.00706087606597149
            else: MOR_correction2 = (-0.000711441807827186 * evapoil) - 0.0118194116436425
            #st.write("MOR_correction2:", MOR_correction2)
            
            if refrigerant in ["R23", "R508B"]:
                if T_evap < -86:
                    MOR = ""
                    MORmin = ""
                    MORfinal = ""
                elif T_evap > -42:
                    MOR = ""
                    MORmin = ""
                    MORfinal = ""
                else:
                    MOR = (1 - MOR_correction) * (1 - MOR_correction2) * MOR_pre
                    MORmin = (1 - MOR_correctionmin) * (1 - MOR_correction2) * MOR_premin
                    MORfinal = max(MOR, MORmin)
            else:    
                if T_evap < -40:
                    MOR = ""
                    MORmin = ""
                    MORfinal = ""
                elif T_evap > 4:
                    MOR = ""
                    MORmin = ""
                    MORfinal = ""
                else:
                    MOR = (1 - MOR_correction) * (1 - MOR_correction2) * MOR_pre
                    MORmin = (1 - MOR_correctionmin) * (1 - MOR_correction2) * MOR_premin
                    MORfinal = max(MOR, MORmin)
            #st.write("MOR:", MOR)
            #st.write("MORmin:", MORmin)
            #st.write("MORfinal:", MORfinal)
            velocity_m_sfinal = max(velocity_m_s, velocity_m_smin)
            #st.write("velocity_m_sfinal:", velocity_m_sfinal)
        else:
            velocity_m_s = None
            velocity_m_smin = None
            velocity_m_sfinal = None
    
        # Oil return check
        adjusted_duty_kw = evap_capacity_kw * (required_oil_duty_pct / 100.0)
        #st.write("adjusted_duty_kw:", adjusted_duty_kw)
    
        density_recalc = mass_flow_kg_s / (velocity_m_s * area_m2)
        #st.write("density_recalc:", density_recalc)
    
        viscosity_super = RefrigerantViscosities().get_viscosity(refrigerant, T_evap - max_penalty + 273.15, superheat_K)
        #st.write("viscosity_super:", viscosity_super)
        viscosity_super2a = RefrigerantViscosities().get_viscosity(refrigerant, T_evap + 273.15, ((superheat_K + 5) / 2))
        #st.write("viscosity_super2a:", viscosity_super2a)
        viscosity_super2b = RefrigerantViscosities().get_viscosity(refrigerant, T_evap - max_penalty + 273.15, ((superheat_K + 5) / 2))
        #st.write("viscosity_super2b:", viscosity_super2b)
        viscosity_super2 = (viscosity_super2a + viscosity_super2b) / 2
        #st.write("viscosity_super2:", viscosity_super2)
        viscosity_sat = RefrigerantViscosities().get_viscosity(refrigerant, T_evap + 273.15, 0)
        #st.write("viscosity_sat:", viscosity_sat)
        viscosity_5K = RefrigerantViscosities().get_viscosity(refrigerant, T_evap + 273.15, 5)
        #st.write("viscosity_5K:", viscosity_5K)
        viscosity = (viscosity_super + viscosity_5K) / 2
        #st.write("viscosity:", viscosity)
        viscosity_final = (viscosity * velocity1_prop) + (viscosity_super2 * (1 - velocity1_prop))
        #st.write("viscosity_final:", viscosity_final)
    
        # density for reynolds and col2 display needs density_super2 factoring in!
        reynolds = (density_recalc * velocity_m_sfinal * ID_m) / (viscosity_final / 1000000)
        #st.write("reynolds:", reynolds)
    
        if selected_material in ["Steel SCH40", "Steel SCH80"]:
            eps = 0.00004572 #0.00015
        else:
            eps = 0.000001524 #0.000005
        
        tol = 1e-5
        max_iter = 60
        
        if reynolds < 2000.0:
            f = 64.0 / reynolds
        else:
            flo, fhi = 1e-5, 0.1
            def balance(gg):
                s = math.sqrt(gg)
                lhs = 1.0 / s
                rhs = -2.0 * math.log10((eps / (3.7 * ID_m)) + 2.51 / (reynolds * s))
                return lhs, rhs
    
            f = 0.5 * (flo + fhi)
            for _ in range(max_iter):
                f = 0.5 * (flo + fhi)
                lhs, rhs = balance(f)
                if abs(1.0 - lhs/rhs) < tol:
                    break
                # decide side using sign of (lhs - rhs)
                if (lhs - rhs) > 0.0:
                    flo = f
                else:
                    fhi = f
        
        # dynamic (velocity) pressure, kPa
        q_kPa = 0.5 * density_recalc * (velocity_m_sfinal ** 2) / 1000.0
    
        # 1) straight pipe only
        dp_pipe_kPa = f * (L / ID_m) * q_kPa
        
        dp_plf_kPa = q_kPa * PLF
    
        required_cols = ["SRB", "LRB", "BALL", "GLOBE"]
        missing = [c for c in required_cols if c not in selected_pipe_row.index]
        if missing:
            st.error(f"CSV missing required K columns: {missing}")
            st.stop()
    
        # Convert to floats and check NaNs
        try:
            K_SRB  = float(selected_pipe_row["SRB"])
            K_LRB  = float(selected_pipe_row["LRB"])
            K_BALL = float(selected_pipe_row["BALL"])
            K_GLOBE= float(selected_pipe_row["GLOBE"])
        except Exception as e:
            st.error(f"Failed to parse K-factors as numbers: {e}")
            st.stop()
    
        if any(pd.isna([K_SRB, K_LRB, K_BALL, K_GLOBE])):
            st.error("One or more K-factors are NaN in the CSV row.")
            st.stop()
        
        B_SRB = SRB + 0.5 * _45 + 2.0 * ubend + 3.0 * ptrap
        B_LRB = LRB + MAC
    
        dp_fittings_kPa = q_kPa * (
        K_SRB   * B_SRB +
        K_LRB   * B_LRB
        )

        dp_valves_kPa = q_kPa * (
        K_BALL  * ball +
        K_GLOBE * globe
        )
        
        dp_total_kPa = dp_pipe_kPa + dp_fittings_kPa + dp_valves_kPa + dp_plf_kPa

        converter = PressureTemperatureConverter()
        evappres = converter.temp_to_pressure(refrigerant, T_evap)

        postcirc = evappres - (dp_total_kPa / 100)
        
        postcirctemp = converter.pressure_to_temp(refrigerant, postcirc)

        dt = T_evap - postcirctemp
        #st.write("dt:", dt)

        maxmass = max(mass_flow_kg_s, mass_flow_kg_smin)

        volflow = maxmass / density_recalc

        if MORfinal == "":
            MinCap = ""
        else:
            MinCap = MORfinal * evap_capacity_kw / 100
        
        def _pipe_row_for_size(size_inch: str):
            """Return the CSV row for a given nominal size, respecting the selected gauge if present."""
            rows = material_df[material_df["Nominal Size (inch)"].astype(str).str.strip() == str(size_inch)]
            if "Gauge" in rows.columns and rows["Gauge"].notna().any():
                # If the UI has a selected_gauge, use it; otherwise take the first available for that size
                if "selected_gauge" in st.session_state:
                    g = st.session_state["selected_gauge"]
                    rows_g = rows[rows["Gauge"] == g]
                    if not rows_g.empty:
                        return rows_g.iloc[0]
                return rows.iloc[0]
            return rows.iloc[0]
        
        
        def get_pipe_results(size_inch):
            """
            Reproduce MORfinal and dt for a given pipe size (exact same logic path as your main block).
            Returns (MORfinal_value or NaN, dt_value) as floats.
            """
            # ---- Pipe geometry for this size ----
            pipe_row = _pipe_row_for_size(size_inch)
            try:
                ID_mm_local = float(pipe_row["ID_mm"])
            except Exception:
                return float("nan"), float("nan")
        
            ID_m_local = ID_mm_local / 1000.0
            area_m2_local = math.pi * (ID_m_local / 2) ** 2
        
            # ---- Densities (same as page) ----
            dens = RefrigerantDensities()
            props = RefrigerantProperties()
        
            density_super = dens.get_density(refrigerant, T_evap - max_penalty + 273.15, superheat_K)
            density_super2a = dens.get_density(refrigerant, T_evap + 273.15, ((superheat_K + 5) / 2))
            density_super2b = dens.get_density(refrigerant, T_evap - max_penalty + 273.15, ((superheat_K + 5) / 2))
            density_super2 = (density_super2a + density_super2b) / 2
            density_super_foroil = dens.get_density(refrigerant, T_evap + 273.15, min(max(superheat_K, 5), 30))
            density_sat = props.get_properties(refrigerant, T_evap)["density_vapor"]
            density_5K = dens.get_density(refrigerant, T_evap + 273.15, 5)
            density = (density_super + density_5K) / 2
            density_foroil = (density_super_foroil + density_sat) / 2
        
            # ---- Mass flows (reuse from page; they’re size-independent) ----
            # These should already be defined in your main code before calling the button:
            # mass_flow_kg_s, mass_flow_kg_smin, mass_flow_foroil, mass_flow_foroilmin
            # If not, we recompute them here exactly as you did:
            try:
                _ = mass_flow_kg_s  # noqa: F401
            except NameError:
                h_in = props.get_properties(refrigerant, T_cond)["enthalpy_liquid2"]
                h_inmin = props.get_properties(refrigerant, minliq_temp)["enthalpy_liquid2"]
                h_evap = props.get_properties(refrigerant, T_evap)["enthalpy_vapor"]
                h_10K = props.get_properties(refrigerant, T_evap)["enthalpy_super"]
                hdiff_10K = h_10K - h_evap
                hdiff_custom = hdiff_10K * min(max(superheat_K, 5), 30) / 10
                h_super = h_evap + hdiff_custom
                h_inlet = props.get_properties(refrigerant, T_cond)["enthalpy_liquid"]
                h_inletmin = props.get_properties(refrigerant, minliq_temp)["enthalpy_liquid"]
        
                delta_h = h_evap - h_in
                delta_hmin = h_evap - h_inmin
                h_foroil = (h_evap + h_super) / 2
                delta_h_foroil = h_foroil - h_inlet
                delta_h_foroilmin = h_foroil - h_inletmin
        
                mass_flow_kg_s = evap_capacity_kw / delta_h if delta_h > 0 else 0.01
                mass_flow_kg_smin = evap_capacity_kw / delta_hmin if delta_hmin > 0 else 0.01
                mass_flow_foroil = evap_capacity_kw / delta_h_foroil if delta_h_foroil > 0 else 0.01
                mass_flow_foroilmin = evap_capacity_kw / delta_h_foroilmin if delta_h_foroilmin > 0 else 0.01
        
            # ---- Velocities (same mixing and refrigerant-dependent velocity1_prop) ----
            v1 = mass_flow_kg_s / (area_m2_local * density)
            v1min = mass_flow_kg_smin / (area_m2_local * density)
            v2 = mass_flow_kg_s / (area_m2_local * density_super2)
            v2min = mass_flow_kg_smin / (area_m2_local * density_super2)
        
            if refrigerant == "R744":
                velocity1_prop = 1
            elif refrigerant == "R404A":
                velocity1_prop = (0.0328330590542629 * superheat_K) - 1.47748765744183 if superheat_K > 45 else 0
            elif refrigerant == "R134a":
                velocity1_prop = (-0.000566085879684639 * (superheat_K ** 2)) + (0.075049554857083 * superheat_K) - 1.74200935399632 if superheat_K > 30 else 0
            elif refrigerant in ["R407F", "R407A", "R410A", "R22", "R502", "R507A", "R448A", "R449A", "R717"]:
                velocity1_prop = 1
            elif refrigerant == "R407C":
                velocity1_prop = 0
            else:
                velocity1_prop = (0.0000406422632403154 * (superheat_K ** 2)) - (0.000541007136813307 * superheat_K) + 0.748882946418884 if superheat_K > 30 else 0.769230769230769
        
            velocity_m_s = (v1 * velocity1_prop) + (v2 * (1 - velocity1_prop))
            velocity_m_smin = (v1min * velocity1_prop) + (v2min * (1 - velocity1_prop))
            velocity_m_sfinal = max(velocity_m_s, velocity_m_smin)
        
            # ---- Oil density (same branches) ----
            if refrigerant in ["R23", "R508B"]:
                oil_density_sat = (-0.853841209044878 * T_evap) + 999.190772536527
                oil_density_super = (-0.853841209044878 * (T_evap + min(max(superheat_K, 5), 30))) + 999.190772536527
            else:
                oil_density_sat = (-0.00356060606060549 * (T_evap ** 2)) - (0.957878787878808 * T_evap) + 963.595454545455
                oil_density_super = (-0.00356060606060549 * ((T_evap + min(max(superheat_K, 5), 30)) ** 2)) - (0.957878787878808 * (T_evap + min(max(superheat_K, 5), 30))) + 963.595454545455
            oil_density = (oil_density_sat + oil_density_super) / 2
        
            # ---- jg_half (per refrigerant) ----
            jg_map = {
                "R404A": 0.860772464072673, "R134a": 0.869986729796935, "R407F": 0.869042493641944,
                "R744": 0.877950613678719, "R407A": 0.867374311574041, "R410A": 0.8904423325365,
                "R407C": 0.858592104849471, "R22": 0.860563058394146, "R502": 0.858236706656266,
                "R507A": 0.887709710291009, "R449A": 0.867980496631757, "R448A": 0.86578818145833,
                "R717": 0.854957410951708, "R290": 0.844975139695726, "R1270": 0.849089717732815,
                "R600a": 0.84339338979887, "R1234ze": 0.867821375349728, "R1234yf": 0.860767472602571,
                "R12": 0.8735441986466, "R11": 0.864493203834913, "R454B": 0.869102255850291,
                "R450A": 0.865387140496035, "R513A": 0.861251244627232, "R454A": 0.868161104592492,
                "R455A": 0.865687329727713, "R454C": 0.866423016875524, "R32": 0.875213309852597,
                "R23": 0.865673418568001, "R508B": 0.864305626845382,
            }
            jg_half = jg_map.get(refrigerant, 0.865)
        
            # ---- MOR (same as page) ----
            MinMassFlux = (jg_half ** 2) * ((density_foroil * 9.81 * ID_m_local * (oil_density - density_foroil)) ** 0.5)
            MinMassFlow = MinMassFlux * area_m2_local
            MOR_pre = (MinMassFlow / mass_flow_foroil) * 100
            MOR_premin = (MinMassFlow / mass_flow_foroilmin) * 100
        
            # Special corrections
            if refrigerant in ["R23", "R508B"]:
                MOR_correctliq = T_cond + 47.03
                MOR_correctliqmin = minliq_temp + 47.03
                evapoil = T_evap + 46.14
            else:
                MOR_correctliq = T_cond
                MOR_correctliqmin = minliq_temp
                evapoil = T_evap
        
            # First correction vs liquid temp
            if refrigerant == "R744":
                MOR_correction = (0.000225755013421421 * MOR_correctliq) - 0.00280879370374927
            elif refrigerant in ["R407A", "R449A", "R448A", "R502"]:
                MOR_correction = (0.00000414431651323856 * (MOR_correctliq ** 2)) + (0.000381908525139781 * MOR_correctliq) - 0.0163450053041212
            elif refrigerant == "R507A":
                MOR_correction = (0.000302619054048837 * MOR_correctliq) - 0.00930188913363997
            elif refrigerant == "R22":
                MOR_correction = (0.000108153843367715 * MOR_correctliq) - 0.00329248681202757
            elif refrigerant == "R407C":
                MOR_correction = (0.00000420322918839302 * (max(MOR_correctliq, -32.0716410083429) ** 2)) + (0.000269608915211859 * max(MOR_correctliq, -32.0716410083429)) - 0.0134546663857195
            elif refrigerant == "R410A":
                MOR_correction = 0
            elif refrigerant == "R407F":
                MOR_correction = (0.00000347332380289385 * (max(MOR_correctliq, -34.4346433150568) ** 2)) + (0.000239205332540693 * max(MOR_correctliq, -34.4346433150568)) - 0.0121545316131988
            elif refrigerant == "R134a":
                MOR_correction = (0.000195224660107459 * MOR_correctliq) - 0.00591757011487048
            elif refrigerant == "R404A":
                MOR_correction = (0.0000156507169104918 * (max(MOR_correctliq, -22.031637377024) ** 2)) + (0.000689621839324826 * max(MOR_correctliq, -22.031637377024)) - 0.0392
            else:
                MOR_correction = (0.00000461020482461793 * (max(MOR_correctliq, -23.6334996273983) ** 2)) + (0.000217910548009675 * max(MOR_correctliq, -23.6334996273983)) - 0.012074621594626
        
            if refrigerant == "R744":
                MOR_correctionmin = (0.000225755013421421 * MOR_correctliqmin) - 0.00280879370374927
            elif refrigerant in ["R407A", "R449A", "R448A", "R502"]:
                MOR_correctionmin = (0.00000414431651323856 * (MOR_correctliqmin ** 2)) + (0.000381908525139781 * MOR_correctliqmin) - 0.0163450053041212
            elif refrigerant == "R507A":
                MOR_correctionmin = (0.000302619054048837 * MOR_correctliqmin) - 0.00930188913363997
            elif refrigerant == "R22":
                MOR_correctionmin = (0.000108153843367715 * MOR_correctliqmin) - 0.00329248681202757
            elif refrigerant == "R407C":
                MOR_correctionmin = (0.00000420322918839302 * (max(MOR_correctliqmin, -32.0716410083429) ** 2)) + (0.000269608915211859 * max(MOR_correctliqmin, -32.0716410083429)) - 0.0134546663857195
            elif refrigerant == "R410A":
                MOR_correctionmin = 0
            elif refrigerant == "R407F":
                MOR_correctionmin = (0.00000347332380289385 * (max(MOR_correctliqmin, -34.4346433150568) ** 2)) + (0.000239205332540693 * max(MOR_correctliqmin, -34.4346433150568)) - 0.0121545316131988
            elif refrigerant == "R134a":
                MOR_correctionmin = (0.000195224660107459 * MOR_correctliqmin) - 0.00591757011487048
            elif refrigerant == "R404A":
                MOR_correctionmin = (0.0000156507169104918 * (max(MOR_correctliqmin, -22.031637377024) ** 2)) + (0.000689621839324826 * max(MOR_correctliqmin, -22.031637377024)) - 0.0392
            else:
                MOR_correctionmin = (0.00000461020482461793 * (max(MOR_correctliqmin, -23.6334996273983) ** 2)) + (0.000217910548009675 * max(MOR_correctliqmin, -23.6334996273983)) - 0.012074621594626
        
            # Second correction vs evap temp
            if refrigerant == "R744":
                MOR_correction2 = (-0.0000176412848988908 * (evapoil ** 2)) - (0.00164308248808803 * evapoil) - 0.0184308798286039
            elif refrigerant == "R407A":
                MOR_correction2 = (-0.000864076433837511 * evapoil) - 0.0145018190416687
            elif refrigerant == "R449A":
                MOR_correction2 = (-0.000835375233693285 * evapoil) - 0.0138846063856621
            elif refrigerant == "R448A":
                MOR_correction2 = (0.00000171366802431428 * (evapoil ** 2)) - (0.000865528727278154 * evapoil) - 0.0152961902042161
            elif refrigerant == "R502":
                MOR_correction2 = (0.00000484734071020993 * (evapoil ** 2)) - (0.000624822304716683 * evapoil) - 0.0128725684240106
            elif refrigerant == "R507A":
                MOR_correction2 = (-0.000701333343440148 * evapoil) - 0.0114900933623056
            elif refrigerant == "R22":
                MOR_correction2 = (0.00000636798209134899 * (evapoil ** 2)) - (0.000157783204337396 * evapoil) - 0.00575251626397381
            elif refrigerant == "R407C":
                MOR_correction2 = (-0.00000665735727676349 * (evapoil ** 2)) - (0.000894860288947537 * evapoil) - 0.0116054361757929
            elif refrigerant == "R410A":
                MOR_correction2 = (-0.000672268853990701 * evapoil) - 0.0111802230098585
            elif refrigerant == "R407F":
                MOR_correction2 = (0.00000263731418614519 * (evapoil ** 2)) - (0.000683997257738699 * evapoil) - 0.0126005968942147
            elif refrigerant == "R134a":
                MOR_correction2 = (-0.00000823045532174214 * (evapoil ** 2)) - (0.00108063672211041 * evapoil) - 0.0217411206961643
            elif refrigerant == "R404A":
                MOR_correction2 = (0.00000342378568620316 * (evapoil ** 2)) - (0.000329572335134041 * evapoil) - 0.00706087606597149
            else:
                MOR_correction2 = (-0.000711441807827186 * evapoil) - 0.0118194116436425
        
            # Compose MOR / bounds
            MOR, MORmin, MORfinal_local = "", "", ""
            if refrigerant in ["R23", "R508B"]:
                if -86 <= T_evap <= -42:
                    MOR = (1 - MOR_correction) * (1 - MOR_correction2) * MOR_pre
                    MORmin = (1 - MOR_correctionmin) * (1 - MOR_correction2) * MOR_premin
                    MORfinal_local = max(MOR, MORmin)
            else:
                if -40 <= T_evap <= 4:
                    MOR = (1 - MOR_correction) * (1 - MOR_correction2) * MOR_pre
                    MORmin = (1 - MOR_correctionmin) * (1 - MOR_correction2) * MOR_premin
                    MORfinal_local = max(MOR, MORmin)
        
            # ---- density/viscosity for Reynolds (same path) ----
            # use the same density_recalc definition (note: uses velocity_m_s, not final)
            if velocity_m_s > 0:
                density_recalc_local = mass_flow_kg_s / (velocity_m_s * area_m2_local)
            else:
                density_recalc_local = density  # fallback
        
            visc = RefrigerantViscosities()
            viscosity_super = visc.get_viscosity(refrigerant, T_evap - max_penalty + 273.15, superheat_K)
            viscosity_super2a = visc.get_viscosity(refrigerant, T_evap + 273.15, ((superheat_K + 5) / 2))
            viscosity_super2b = visc.get_viscosity(refrigerant, T_evap - max_penalty + 273.15, ((superheat_K + 5) / 2))
            viscosity_super2 = (viscosity_super2a + viscosity_super2b) / 2
            viscosity_5K = visc.get_viscosity(refrigerant, T_evap + 273.15, 5)
            viscosity = (viscosity_super + viscosity_5K) / 2
            viscosity_final = (viscosity * velocity1_prop) + (viscosity_super2 * (1 - velocity1_prop))
        
            reynolds_local = (density_recalc_local * velocity_m_sfinal * ID_m_local) / (viscosity_final / 1_000_000)
        
            # ---- friction factor (same eps/material logic) ----
            eps = 0.00004572 if selected_material in ["Steel SCH40", "Steel SCH80"] else 0.000001524
        
            if reynolds_local < 2000.0:
                f_local = 64.0 / max(reynolds_local, 1e-9)
            else:
                tol = 1e-5
                max_iter = 60
                flo, fhi = 1e-5, 0.1
        
                def balance(gg):
                    s = math.sqrt(gg)
                    lhs = 1.0 / s
                    rhs = -2.0 * math.log10((eps / (3.7 * ID_m_local)) + 2.51 / (reynolds_local * s))
                    return lhs, rhs
        
                for _ in range(max_iter):
                    f_try = 0.5 * (flo + fhi)
                    lhs, rhs = balance(f_try)
                    if abs(1.0 - lhs / rhs) < tol:
                        f_local = f_try
                        break
                    if (lhs - rhs) > 0.0:
                        flo = f_try
                    else:
                        fhi = f_try
                else:
                    f_local = 0.5 * (flo + fhi)
        
            # ---- pressure drops & ΔT (use this pipe's K-factors) ----
            required_cols = ["SRB", "LRB", "BALL", "GLOBE"]
            for c in required_cols:
                if c not in pipe_row.index:
                    return float("nan"), float("nan")
        
            K_SRB = float(pipe_row["SRB"])
            K_LRB = float(pipe_row["LRB"])
            K_BALL = float(pipe_row["BALL"])
            K_GLOBE = float(pipe_row["GLOBE"])
        
            q_kPa_local = 0.5 * density_recalc_local * (velocity_m_sfinal ** 2) / 1000.0
        
            B_SRB = SRB + 0.5 * _45 + 2.0 * ubend + 3.0 * ptrap
            B_LRB = LRB + MAC
        
            dp_pipe_kPa_local = f_local * (L / ID_m_local) * q_kPa_local
            dp_plf_kPa_local = q_kPa_local * PLF
            dp_fittings_kPa_local = q_kPa_local * (K_SRB * B_SRB + K_LRB * B_LRB)
            dp_valves_kPa_local = q_kPa_local * (K_BALL * ball + K_GLOBE * globe)
            dp_total_kPa_local = dp_pipe_kPa_local + dp_fittings_kPa_local + dp_valves_kPa_local + dp_plf_kPa_local
        
            converter = PressureTemperatureConverter()
            evappres_local = converter.temp_to_pressure(refrigerant, T_evap)
            postcirc_local = evappres_local - (dp_total_kPa_local / 100)
            postcirctemp_local = converter.pressure_to_temp(refrigerant, postcirc_local)
            dt_local = T_evap - postcirctemp_local
        
            # ---- Numeric return (handle blank MOR) ----
            if MORfinal_local == "":
                mor_num = float("nan")
            else:
                mor_num = float(MORfinal_local)
        
            return mor_num, float(dt_local)
        
        if st.button("Auto-select"):
            results, errors = [], []
        
            # --- Run the calculations ---
            for ps in pipe_sizes:
                try:
                    MOR_i, dt_i = get_pipe_results(ps)
                    if math.isfinite(MOR_i) and math.isfinite(dt_i):
                        results.append({"size": ps, "MORfinal": MOR_i, "dt": dt_i})
                    else:
                        errors.append((ps, "Non-numeric MOR or ΔT"))
                except Exception as e:
                    errors.append((ps, str(e)))
        
            # --- Handle results ---
            if not results:
                with st.expander("⚠️ Pipe selection debug details", expanded=True):
                    for ps, msg in errors:
                        st.write(f"❌ {ps}: {msg}")
                st.error("No valid pipe size results. Check inputs and CSV rows.")
        
            else:
                valid = [r for r in results if (r["MORfinal"] <= required_oil_duty_pct) and (r["dt"] <= max_penalty)]
        
                if valid:
                    best = min(valid, key=lambda x: mm_map[x["size"]])
                    st.session_state["_next_selected_size"] = best["size"]
        
                    st.success(
                        f"✅ Selected optimal pipe size: **{best['size']}**  \n"
                        f"MOR: {best['MORfinal']:.1f}% | ΔT: {best['dt']:.2f} K"
                    )
        
                    # ✅ Trigger a rerun AFTER displaying success
                    st.rerun()
        
                else:
                    st.error(
                        "❌ No pipe meets both limits simultaneously.  \n"
                        "➡ Please relax one or more input limits."
                    )
        
        st.subheader("Results")
    
        if velocity_m_sfinal:
            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
            with col1:
                st.metric("Refrigerant Velocity", f"{velocity_m_sfinal:.2f}m/s")
    
            with col2:
                st.metric("Suction Density", f"{density_recalc:.2f}kg/m³")
    
            with col3:
                if MORfinal == "":
                    st.metric("MOR (%)", "")
                else:
                    st.metric("MOR (%)", f"{MORfinal:.1f}%")
    
            with col4:
                st.metric("Pressure Drop", f"{dp_total_kPa:.2f}kPa")
    
            with col5:
                st.metric("Temp Penalty", f"{dt:.2f}K")

            with col6:
                st.metric("SST", f"{postcirctemp:.2f}°C")

            with col7:
                st.metric("Evaporating Pressure", f"{evappres:.2f}bar(a)")

            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
            with col1:
                st.metric("Mass Flow Rate", f"{maxmass:.5f}kg/s")
    
            with col2:
                st.metric("Volumetric Flow Rate", f"{volflow:.5f}m³/s")
    
            with col3:
                if MORfinal == "":
                    st.metric("Minimum Capacity", "")
                else:
                    st.metric("Minimum Capacity", f"{MinCap:.4f}kW")
    
            with col4:
                st.metric("Pipe PD", f"{dp_pipe_kPa:.2f}kPa")
    
            with col5:
                st.metric("Fittings PD", f"{dp_fittings_kPa:.2f}kPa")

            with col6:
                st.metric("Valves PD", f"{dp_valves_kPa:.2f}kPa")

            with col7:
                st.metric("Velocity Pressure PD", f"{dp_plf_kPa:.2f}kPa")
    
        if isinstance(MORfinal, (int, float)):
            is_ok, message = (True, "✅ OK") if required_oil_duty_pct >= MORfinal else (False, "❌ Insufficient flow")
        else:
            is_ok, message = (False, "")
    
        if is_ok:
            st.success(f"{message}")
        else:
            st.error(f"{message}")
    
    if mode == "Liquid":
        
        col1, col2, col3, col4 = st.columns(4)
    
        with col1:
            refrigerant = st.selectbox("Refrigerant", [
                "R404A", "R134a", "R407F", "R744", "R410A",
                "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A", "R454C", "R455A", "R407A",
                "R290", "R1270", "R600a", "R717", "R1234ze", "R1234yf", "R12", "R11", "R454B", "R450A", "R513A", "R23", "R508B", "R502"
            ])
    
        # Load pipe data
        pipe_data = pd.read_csv("data/pipe_pressure_ratings_full.csv")
    
        # --- helpers ---
        def _nps_inch_to_mm(nps_str: str) -> float:
            # e.g. "1-1/8", '1"', "3/8"
            s = str(nps_str).replace('"', '').strip()
            if not s:
                return float('nan')
            parts = s.split('-')
            tot_in = 0.0
            for p in parts:
                p = p.strip()
                if not p:
                    continue
                if '/' in p:
                    num, den = p.split('/')
                    tot_in += float(num) / float(den)
                else:
                    tot_in += float(p)
            return tot_in * 25.4  # mm
    
        ss = st.session_state
    
        # 1) Pipe material
        with col2:
            if refrigerant == "R717":
                excluded_materials = ["Copper ACR", "Copper EN12735"]
                pipe_materials = sorted(m for m in pipe_data["Material"].dropna().unique()
                                        if m not in excluded_materials)
            else:
                pipe_materials = sorted(pipe_data["Material"].dropna().unique())
    
            selected_material = st.selectbox("Pipe Material", pipe_materials, key="material")
        
        # detect material change
        material_changed = ss.get("last_material") is not None and ss.last_material != selected_material
        ss.last_material = selected_material
    
        # 2) Sizes for selected material (de-duped)
        material_df = pipe_data[pipe_data["Material"] == selected_material].copy()
    
        sizes_df = (
            material_df[["Nominal Size (inch)", "Nominal Size (mm)"]]
            .dropna(subset=["Nominal Size (inch)"])
            .assign(**{
                "Nominal Size (inch)": lambda d: d["Nominal Size (inch)"].astype(str).str.strip(),
            })
            .drop_duplicates(subset=["Nominal Size (inch)"], keep="first")
        )
    
        # make sure we have a numeric mm per nominal (fallback: parse the inch string)
        sizes_df["mm_num"] = pd.to_numeric(sizes_df.get("Nominal Size (mm)"), errors="coerce")
        sizes_df.loc[sizes_df["mm_num"].isna(), "mm_num"] = sizes_df.loc[sizes_df["mm_num"].isna(), "Nominal Size (inch)"].apply(_nps_inch_to_mm)
    
        pipe_sizes = sizes_df["Nominal Size (inch)"].tolist()
        mm_map = dict(zip(sizes_df["Nominal Size (inch)"], sizes_df["mm_num"]))
    
        # choose default index
        def _closest_index(target_mm: float) -> int:
            mm_list = [mm_map[s] for s in pipe_sizes]
            return min(range(len(mm_list)), key=lambda i: abs(mm_list[i] - target_mm)) if mm_list else 0
    
        # --- consume any deferred selection from the button ---
        if "_next_selected_size" in st.session_state:
            new_val = st.session_state.pop("_next_selected_size")
            # only accept if the option exists for the current material
            if new_val in pipe_sizes:
                # force the widget to pick this value on next render
                st.session_state["selected_size"] = new_val
                # optional: keep a one-shot override flag so we can clean up later
                st.session_state["_selected_size_just_set"] = True
        
        default_index = 0
        if material_changed and "prev_pipe_mm" in ss:
            default_index = _closest_index(ss.prev_pipe_mm)
        elif selected_material == "Copper ACR" and ("1/2" in pipe_sizes or '1/2"' in pipe_sizes):
            # first load or no previous selection → prefer 1-1/8" for Copper ACR
            want = "1/2" if "1/2" in pipe_sizes else '1/2"'
            default_index = pipe_sizes.index(want)
        elif "selected_size" in ss and ss.selected_size in pipe_sizes:
            # if Streamlit kept the selection, use it
            default_index = pipe_sizes.index(ss.selected_size)
        
        with col1:
            selected_size = st.selectbox(
                "Nominal Pipe Size (inch)",
                pipe_sizes,
                index=default_index,
                key="selected_size",
            )
    
        # remove the one-shot flag so future reruns don't keep forcing it
        if st.session_state.get("_selected_size_just_set"):
            del st.session_state["_selected_size_just_set"]
        
        # remember the selected size in mm for next material change
        ss.prev_pipe_mm = float(mm_map.get(selected_size, float("nan")))
    
        # 3) Gauge (if applicable)
        gauge_options = material_df[material_df["Nominal Size (inch)"].astype(str).str.strip() == selected_size]
        if "Gauge" in gauge_options.columns and gauge_options["Gauge"].notna().any():
            gauges = sorted(gauge_options["Gauge"].dropna().unique())
            with col2:
                selected_gauge = st.selectbox("Copper Gauge", gauges, key="gauge")
            selected_pipe_row = gauge_options[gauge_options["Gauge"] == selected_gauge].iloc[0]
        else:
            selected_pipe_row = gauge_options.iloc[0]
    
        # Pipe parameters
        pipe_size_inch = selected_pipe_row["Nominal Size (inch)"]
        ID_mm = selected_pipe_row["ID_mm"]
    
        with col1:
            
            evap_capacity_kw = st.number_input("Evaporator Capacity (kW)", min_value=0.03, max_value=20000.0, value=10.0, step=1.0)
            
            # --- Base ranges per refrigerant ---
            if refrigerant in ("R23", "R508B"):
                evap_min, evap_max, evap_default = -100.0, -20.0, -80.0
                cond_min, cond_max, cond_default = -100.0, 10.0, -30.0
                maxliq_min, maxliq_max, maxliq_default = -100.0, 10.0, -40.0
            elif refrigerant == "R744":
                evap_min, evap_max, evap_default = -50.0, 20.0, -10.0
                cond_min, cond_max, cond_default = -23.0, 30.0, 15.0
                maxliq_min, maxliq_max, maxliq_default = -50.0, 30.0, 10.0
            else:
                evap_min, evap_max, evap_default = -50.0, 30.0, -10.0
                cond_min, cond_max, cond_default = -23.0, 60.0, 43.0
                maxliq_min, maxliq_max, maxliq_default = -50.0, 60.0, 40.0
    
            # --- Init state (widget-backed) ---
            ss = st.session_state
    
            if "last_refrigerant" not in ss or ss.last_refrigerant != refrigerant:
                ss.cond_temp   = cond_default
                ss.maxliq_temp = maxliq_default
                ss.evap_temp   = evap_default
                ss.last_refrigerant = refrigerant
            
            ss.setdefault("cond_temp",   cond_default)
            ss.setdefault("maxliq_temp", maxliq_default)
            ss.setdefault("evap_temp",   evap_default)

            if "maxliq_temp" in ss and "cond_temp" in ss and "evap_temp" in ss:
                ss.cond_temp = min(max(ss.cond_temp, ss.maxliq_temp, ss.evap_temp), cond_max)
    
            if "cond_temp" in ss and "maxliq_temp" in ss and "evap_temp" in ss:
                ss.evap_temp = min(ss.maxliq_temp, ss.cond_temp, ss.evap_temp)
            
            # --- Callbacks implementing your downstream clamping logic ---
            def on_change_cond():
                # When cond changes: clamp maxliq down to cond, then evap down to maxliq
                ss.maxliq_temp = min(ss.maxliq_temp, ss.cond_temp)
                ss.evap_temp   = min(ss.evap_temp,   ss.maxliq_temp)
    
            def on_change_maxliq():
                # When maxliq changes: clamp maxliq down to cond, then evap down to maxliq
                ss.maxliq_temp = min(ss.maxliq_temp, ss.cond_temp)
                ss.evap_temp   = min(ss.evap_temp,   ss.maxliq_temp)
    
            def on_change_evap():
                # When evap changes: clamp evap down to maxliq
                ss.evap_temp   = min(ss.evap_temp,   ss.maxliq_temp)
    
            # --- Inputs with inclusive caps (≤), same order as your code ---
            condensing_temp = st.number_input(
                "Condensing Temperature (°C)",
                min_value=cond_min, max_value=cond_max,
                value=ss.cond_temp, step=1.0, key="cond_temp",
                on_change=on_change_cond,
            )
    
            maxliq_temp = st.number_input(
                "Liquid Temperature (°C)",
                min_value=maxliq_min, max_value=min(condensing_temp, maxliq_max),
                value=ss.maxliq_temp, step=1.0, key="maxliq_temp",
                on_change=on_change_maxliq,
            )

        with col2:
            
            evaporating_temp = st.number_input(
                "Evaporating Temperature (°C)",
                min_value=evap_min, max_value=min(maxliq_temp, evap_max),
                value=ss.evap_temp, step=1.0, key="evap_temp",
                on_change=on_change_evap,
            )
    
        with col2:
            risem = st.number_input("Liquid Line Rise (m)", min_value=0.0, max_value=30.0, value=0.0, step=1.0)
            max_penalty = st.number_input("Max Penalty (K)", min_value=0.0, max_value=6.0, value=1.0, step=0.1)
    
        with col3:
            L = st.number_input("Pipe Length (m)", min_value=0.1, max_value=300.0, value=10.0, step=1.0)
            LRB = st.number_input("Long Radius Bends", min_value=0, max_value=50, value=0, step=1)
            SRB = st.number_input("Short Radius Bends", min_value=0, max_value=50, value=0, step=1)
            _45 = st.number_input("45° Bends", min_value=0, max_value=50, value=0, step=1)
            MAC = st.number_input("Machine Bends", min_value=0, max_value=50, value=0, step=1)
    
        with col4:
            ptrap = st.number_input("P Traps", min_value=0, max_value=10, value=0, step=1)
            ubend = st.number_input("U Bends", min_value=0, max_value=10, value=0, step=1)
            ball = st.number_input("Ball Valves", min_value=0, max_value=20, value=0, step=1)
            globe = st.number_input("Globe Valves", min_value=0, max_value=20, value=0, step=1)
            PLF = st.number_input("Pressure Loss Factors", min_value=0.0, max_value=20.0, value=0.0, step=0.1)
        
        from utils.refrigerant_properties import RefrigerantProperties
        from utils.refrigerant_densities import RefrigerantDensities
        from utils.refrigerant_viscosities import RefrigerantViscosities
        from utils.pipe_length_volume_calc import get_pipe_id_mm
    
        T_evap = evaporating_temp
        T_liq = maxliq_temp
        T_cond = condensing_temp
    
        props = RefrigerantProperties()
        
        h_in = props.get_properties(refrigerant, T_liq)["enthalpy_liquid2"]

        h_evap = props.get_properties(refrigerant, T_evap)["enthalpy_vapor"]
        
        delta_h = h_evap - h_in

        mass_flow_kg_s = evap_capacity_kw / delta_h if delta_h > 0 else 0.01
    
        if ID_mm is not None:
            ID_m = ID_mm / 1000.0

            area_m2 = math.pi * (ID_m / 2) ** 2

            density = RefrigerantProperties().get_properties(refrigerant, T_liq)["density_liquid2"]

            velocity_m_s = mass_flow_kg_s / (area_m2 * density)

        else:
            velocity_m_s = None

        viscosity = RefrigerantProperties().get_properties(refrigerant, T_liq)["viscosity_liquid"]
    
        reynolds = (density * velocity_m_s * ID_m) / (viscosity / 1000000)
    
        if selected_material in ["Steel SCH40", "Steel SCH80"]:
            eps = 0.00004572 #0.00015
        else:
            eps = 0.000001524 #0.000005
        
        tol = 1e-5
        max_iter = 60
        
        if reynolds < 2000.0:
            f = 64.0 / reynolds
        else:
            flo, fhi = 1e-5, 0.1
            def balance(gg):
                s = math.sqrt(gg)
                lhs = 1.0 / s
                rhs = -2.0 * math.log10((eps / (3.7 * ID_m)) + 2.51 / (reynolds * s))
                return lhs, rhs
    
            f = 0.5 * (flo + fhi)
            for _ in range(max_iter):
                f = 0.5 * (flo + fhi)
                lhs, rhs = balance(f)
                if abs(1.0 - lhs/rhs) < tol:
                    break
                # decide side using sign of (lhs - rhs)
                if (lhs - rhs) > 0.0:
                    flo = f
                else:
                    fhi = f
        
        # dynamic (velocity) pressure, kPa
        q_kPa = 0.5 * density * (velocity_m_s ** 2) / 1000.0
    
        # 1) straight pipe only
        dp_pipe_kPa = f * (L / ID_m) * q_kPa
        
        dp_plf_kPa = q_kPa * PLF
    
        required_cols = ["SRB", "LRB", "BALL", "GLOBE"]
        missing = [c for c in required_cols if c not in selected_pipe_row.index]
        if missing:
            st.error(f"CSV missing required K columns: {missing}")
            st.stop()
    
        # Convert to floats and check NaNs
        try:
            K_SRB  = float(selected_pipe_row["SRB"])
            K_LRB  = float(selected_pipe_row["LRB"])
            K_BALL = float(selected_pipe_row["BALL"])
            K_GLOBE= float(selected_pipe_row["GLOBE"])
        except Exception as e:
            st.error(f"Failed to parse K-factors as numbers: {e}")
            st.stop()
    
        if any(pd.isna([K_SRB, K_LRB, K_BALL, K_GLOBE])):
            st.error("One or more K-factors are NaN in the CSV row.")
            st.stop()
        
        B_SRB = SRB + 0.5 * _45 + 2.0 * ubend + 3.0 * ptrap
        B_LRB = LRB + MAC
    
        dp_fittings_kPa = q_kPa * (
        K_SRB   * B_SRB +
        K_LRB   * B_LRB
        )

        dp_valves_kPa = q_kPa * (
        K_BALL  * ball +
        K_GLOBE * globe
        )
        
        dp_total_kPa = dp_pipe_kPa + dp_fittings_kPa + dp_valves_kPa + dp_plf_kPa
        
        converter = PressureTemperatureConverter()
        condpres = converter.temp_to_pressure(refrigerant, T_cond)
        postcirc = condpres - (dp_total_kPa / 100)
        postcirctemp = converter.pressure_to_temp(refrigerant, postcirc)
        
        dt = T_cond - postcirctemp

        head = 9.80665 * risem * density / 1000
        
        dp_withhead = dp_total_kPa + head

        postall = condpres - (dp_withhead / 100)
        postalltemp = converter.pressure_to_temp(refrigerant, postall)
        
        tall = T_cond - postalltemp

        exsub = T_cond - T_liq

        addsub = max(tall - exsub, 0)

        evappres = converter.temp_to_pressure(refrigerant, T_evap)

        volflow = mass_flow_kg_s / density

        compratio = condpres / evappres

        def _pipe_row_for_size(size_inch: str):
            """Return the CSV row for a given nominal size, respecting selected gauge if present."""
            rows = material_df[material_df["Nominal Size (inch)"].astype(str).str.strip() == str(size_inch)]
            if rows.empty:
                return None
            if "Gauge" in rows.columns and rows["Gauge"].notna().any():
                if "gauge" in st.session_state:
                    g = st.session_state["gauge"]
                    rows_g = rows[rows["Gauge"] == g]
                    if not rows_g.empty:
                        return rows_g.iloc[0]
                return rows.iloc[0]
            return rows.iloc[0]
        
        def get_liquid_dt_for_size(size_inch: str) -> float:
            """
            Compute ΔT (dt) for a given pipe size using the SAME logic as your main Liquid calc
            (without static head — use 'dt', not 'tall').
            Returns float('nan') on any failure.
            """
            try:
                pipe_row = _pipe_row_for_size(size_inch)
                if pipe_row is None:
                    return float("nan")
        
                ID_mm_local = float(pipe_row["ID_mm"])
                ID_m_local = ID_mm_local / 1000.0
                area_m2_local = math.pi * (ID_m_local / 2) ** 2
        
                # Properties at liquid temperature (size-independent)
                density_liq = RefrigerantProperties().get_properties(refrigerant, T_liq)["density_liquid2"]
                visc_liq = RefrigerantProperties().get_properties(refrigerant, T_liq)["viscosity_liquid"]
        
                # Mass flow already computed outside (size-independent)
                v_local = mass_flow_kg_s / (area_m2_local * density_liq)
        
                # Reynolds
                Re = (density_liq * v_local * ID_m_local) / (visc_liq / 1_000_000)
        
                # Roughness by material
                eps = 0.00004572 if selected_material in ["Steel SCH40", "Steel SCH80"] else 0.000001524
        
                # Friction factor (laminar vs Colebrook)
                if Re < 2000.0 and Re > 0:
                    f_local = 64.0 / Re
                else:
                    flo, fhi = 1e-5, 0.1
                    tol, max_iter = 1e-5, 60
        
                    def bal(gg):
                        s = math.sqrt(gg)
                        lhs = 1.0 / s
                        rhs = -2.0 * math.log10((eps / (3.7 * ID_m_local)) + (2.51 / (Re * s)))
                        return lhs, rhs
        
                    f_local = 0.5 * (flo + fhi)
                    for _ in range(max_iter):
                        f_try = 0.5 * (flo + fhi)
                        lhs, rhs = bal(f_try)
                        if abs(1.0 - lhs / rhs) < tol:
                            f_local = f_try
                            break
                        if (lhs - rhs) > 0.0:
                            flo = f_try
                        else:
                            fhi = f_try
                    else:
                        f_local = 0.5 * (flo + fhi)
        
                # Dynamic pressure (kPa)
                q_kPa_local = 0.5 * density_liq * (v_local ** 2) / 1000.0
        
                # K-factors for this size
                for c in ["SRB", "LRB", "BALL", "GLOBE"]:
                    if c not in pipe_row.index or pd.isna(pipe_row[c]):
                        return float("nan")
                K_SRB   = float(pipe_row["SRB"])
                K_LRB   = float(pipe_row["LRB"])
                K_BALL  = float(pipe_row["BALL"])
                K_GLOBE = float(pipe_row["GLOBE"])
        
                # Bend/valve counts
                B_SRB = SRB + 0.5 * _45 + 2.0 * ubend + 3.0 * ptrap
                B_LRB = LRB + MAC
        
                # Pressure drops (kPa)
                dp_pipe_kPa_local    = f_local * (L / ID_m_local) * q_kPa_local
                dp_plf_kPa_local     = q_kPa_local * PLF
                dp_fittings_kPa_local= q_kPa_local * (K_SRB * B_SRB + K_LRB * B_LRB)
                dp_valves_kPa_local  = q_kPa_local * (K_BALL * ball    + K_GLOBE * globe)
        
                dp_total_kPa_local = dp_pipe_kPa_local + dp_fittings_kPa_local + dp_valves_kPa_local + dp_plf_kPa_local
        
                # Convert DP to post-circ temperature and get ΔT
                conv = PressureTemperatureConverter()
                condpres_local = conv.temp_to_pressure(refrigerant, T_cond)
                postcirc_local = condpres_local - (dp_total_kPa_local / 100.0)  # kPa -> bar: /100
                postcirctemp_local = conv.pressure_to_temp(refrigerant, postcirc_local)
                dt_local = T_cond - postcirctemp_local
        
                return float(dt_local)
            except Exception:
                return float("nan")
        
        if st.button("Auto-select"):
            results, errors = [], []
        
            for ps in pipe_sizes:
                dt_i = get_liquid_dt_for_size(ps)
                if math.isfinite(dt_i):
                    results.append({"size": ps, "dt": dt_i})
                else:
                    errors.append((ps, "Non-numeric ΔT"))
        
            if not results:
                with st.expander("⚠️ Liquid selection debug details", expanded=True):
                    for ps, msg in errors:
                        st.write(f"❌ {ps}: {msg}")
                st.error("No valid pipe size results. Check inputs and CSV rows.")
            else:
                # Keep sizes that satisfy the dt limit, pick the smallest OD (mm)
                valid = [r for r in results if r["dt"] <= max_penalty]
        
                if valid:
                    best = min(valid, key=lambda x: mm_map[x["size"]])
                    st.session_state["_next_selected_size"] = best["size"]
                    st.success(
                        f"✅ Selected liquid pipe size: **{best['size']}**  \n"
                        f"ΔT: {best['dt']:.3f} K (limit {max_penalty:.3f} K)"
                    )
                    st.rerun()
                else:
                    best_dt = min(r["dt"] for r in results if math.isfinite(r["dt"]))
                    st.error(
                        "❌ No pipe meets the ΔT limit.  \n"
                        f"Best achievable ΔT = {best_dt:.3f} K (must be ≤ {max_penalty:.3f} K)  \n"
                        "➡ Relax the Max Penalty or choose a different material/length/fittings."
                    )
        
        st.subheader("Results")
    
        if velocity_m_s:
            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
            with col1:
                st.metric("Refrigerant Velocity", f"{velocity_m_s:.2f}m/s")
    
            with col2:
                st.metric("Liquid Density", f"{density:.1f}kg/m³")
    
            with col3:
                st.metric("Pressure Drop", f"{dp_total_kPa:.2f}kPa")
    
            with col4:
                st.metric("Temp Penalty", f"{dt:.2f}K")

            with col5:
                st.metric("Additional Subcooling Required", f"{addsub:.2f}K")

            with col6:
                st.metric("Evaporating Pressure", f"{evappres:.2f}bar(a)")

            with col7:
                st.metric("Condensing Pressure", f"{condpres:.2f}bar(a)")

            # correcting default values between cond, max liq, and min liq between liquid calcs and dry suction calcs
            
            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
            with col1:
                st.metric("Mass Flow Rate", f"{mass_flow_kg_s:.5f}kg/s")
    
            with col2:
                st.metric("Volumetric Flow Rate", f"{volflow:.5f}m³/s")
    
            with col3:
                st.metric("Pipe PD", f"{dp_pipe_kPa:.2f}kPa")
    
            with col4:
                st.metric("Fittings PD", f"{dp_fittings_kPa:.2f}kPa")

            with col5:
                st.metric("Valves PD", f"{dp_valves_kPa:.2f}kPa")

            with col6:
                st.metric("Velocity Pressure PD", f"{dp_plf_kPa:.2f}kPa")

            with col7:
                st.metric("Compression Ratio", f"{compratio:.2f}")

    if mode == "Discharge":

        from utils.refrigerant_properties import RefrigerantProperties
        from utils.refrigerant_densities import RefrigerantDensities
        from utils.refrigerant_viscosities import RefrigerantViscosities
        from utils.pipe_length_volume_calc import get_pipe_id_mm
        from utils.refrigerant_entropies import RefrigerantEntropies
        from utils.refrigerant_enthalpies import RefrigerantEnthalpies

        col1, col2, col3, col4 = st.columns(4)
    
        with col1:
            refrigerant = st.selectbox("Refrigerant", [
                "R404A", "R134a", "R407F", "R744", "R410A",
                "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A", "R454C", "R455A", "R407A",
                "R290", "R1270", "R600a", "R717", "R1234ze", "R1234yf", "R12", "R11", "R454B", "R450A", "R513A", "R23", "R508B", "R502"
            ])
        
        # Load pipe data
        pipe_data = pd.read_csv("data/pipe_pressure_ratings_full.csv")
    
        # --- helpers ---
        def _nps_inch_to_mm(nps_str: str) -> float:
            # e.g. "1-1/8", '1"', "3/8"
            s = str(nps_str).replace('"', '').strip()
            if not s:
                return float('nan')
            parts = s.split('-')
            tot_in = 0.0
            for p in parts:
                p = p.strip()
                if not p:
                    continue
                if '/' in p:
                    num, den = p.split('/')
                    tot_in += float(num) / float(den)
                else:
                    tot_in += float(p)
            return tot_in * 25.4  # mm
    
        ss = st.session_state
    
        # 1) Pipe material
        with col2:
            if refrigerant == "R717":
                excluded_materials = ["Copper ACR", "Copper EN12735"]
                pipe_materials = sorted(m for m in pipe_data["Material"].dropna().unique()
                                        if m not in excluded_materials)
            else:
                pipe_materials = sorted(pipe_data["Material"].dropna().unique())
    
            selected_material = st.selectbox("Pipe Material", pipe_materials, key="material")
        
        # detect material change
        material_changed = ss.get("last_material") is not None and ss.last_material != selected_material
        ss.last_material = selected_material
    
        # 2) Sizes for selected material (de-duped)
        material_df = pipe_data[pipe_data["Material"] == selected_material].copy()
    
        sizes_df = (
            material_df[["Nominal Size (inch)", "Nominal Size (mm)"]]
            .dropna(subset=["Nominal Size (inch)"])
            .assign(**{
                "Nominal Size (inch)": lambda d: d["Nominal Size (inch)"].astype(str).str.strip(),
            })
            .drop_duplicates(subset=["Nominal Size (inch)"], keep="first")
        )
    
        # make sure we have a numeric mm per nominal (fallback: parse the inch string)
        sizes_df["mm_num"] = pd.to_numeric(sizes_df.get("Nominal Size (mm)"), errors="coerce")
        sizes_df.loc[sizes_df["mm_num"].isna(), "mm_num"] = sizes_df.loc[sizes_df["mm_num"].isna(), "Nominal Size (inch)"].apply(_nps_inch_to_mm)
    
        pipe_sizes = sizes_df["Nominal Size (inch)"].tolist()
        mm_map = dict(zip(sizes_df["Nominal Size (inch)"], sizes_df["mm_num"]))
    
        # choose default index
        def _closest_index(target_mm: float) -> int:
            mm_list = [mm_map[s] for s in pipe_sizes]
            return min(range(len(mm_list)), key=lambda i: abs(mm_list[i] - target_mm)) if mm_list else 0
    
        # --- consume any deferred selection from the button ---
        if "_next_selected_size" in st.session_state:
            new_val = st.session_state.pop("_next_selected_size")
            if new_val in pipe_sizes:
                st.session_state["selected_size"] = new_val
                st.session_state["_selected_size_just_set"] = True
        
        default_index = 0
        if material_changed and "prev_pipe_mm" in ss:
            default_index = _closest_index(ss.prev_pipe_mm)
        elif selected_material == "Copper ACR" and ("5/8" in pipe_sizes or '5/8"' in pipe_sizes):
            # first load or no previous selection → prefer 1-1/8" for Copper ACR
            want = "5/8" if "5/8" in pipe_sizes else '5/8"'
            default_index = pipe_sizes.index(want)
        elif "selected_size" in ss and ss.selected_size in pipe_sizes:
            # if Streamlit kept the selection, use it
            default_index = pipe_sizes.index(ss.selected_size)
    
        with col1:
            selected_size = st.selectbox(
                "Nominal Pipe Size (inch)",
                pipe_sizes,
                index=default_index,
                key="selected_size",
            )
    
        if st.session_state.get("_selected_size_just_set"):
            del st.session_state["_selected_size_just_set"]
        
        # remember the selected size in mm for next material change
        ss.prev_pipe_mm = float(mm_map.get(selected_size, float("nan")))
    
        # 3) Gauge (if applicable)
        gauge_options = material_df[material_df["Nominal Size (inch)"].astype(str).str.strip() == selected_size]
        if "Gauge" in gauge_options.columns and gauge_options["Gauge"].notna().any():
            gauges = sorted(gauge_options["Gauge"].dropna().unique())
            with col2:
                selected_gauge = st.selectbox("Copper Gauge", gauges, key="gauge")
            selected_pipe_row = gauge_options[gauge_options["Gauge"] == selected_gauge].iloc[0]
        else:
            selected_pipe_row = gauge_options.iloc[0]
    
        # Pipe parameters
        pipe_size_inch = selected_pipe_row["Nominal Size (inch)"]
        ID_mm = selected_pipe_row["ID_mm"]

        with col1:
            
            evap_capacity_kw = st.number_input("Evaporator Capacity (kW)", min_value=0.03, max_value=20000.0, value=10.0, step=1.0)
            
            # --- Base ranges per refrigerant ---
            if refrigerant in ("R23", "R508B"):
                evap_min, evap_max, evap_default = -100.0, -20.0, -80.0
                cond_min, cond_max, cond_default = -100.0, 10.0, -30.0
                maxliq_min, maxliq_max, maxliq_default = -100.0, 10.0, -40.0
            elif refrigerant == "R744":
                evap_min, evap_max, evap_default = -50.0, 20.0, -10.0
                cond_min, cond_max, cond_default = -23.0, 30.0, 15.0
                maxliq_min, maxliq_max, maxliq_default = -50.0, 30.0, 10.0
            else:
                evap_min, evap_max, evap_default = -50.0, 30.0, -10.0
                cond_min, cond_max, cond_default = -23.0, 60.0, 43.0
                maxliq_min, maxliq_max, maxliq_default = -50.0, 60.0, 40.0
    
            # --- Init state (widget-backed) ---
            ss = st.session_state
    
            if "last_refrigerant" not in ss or ss.last_refrigerant != refrigerant:
                ss.cond_temp   = cond_default
                ss.maxliq_temp = maxliq_default
                ss.evap_temp   = evap_default
                ss.last_refrigerant = refrigerant
            
            ss.setdefault("cond_temp",   cond_default)
            ss.setdefault("maxliq_temp", maxliq_default)
            ss.setdefault("evap_temp",   evap_default)

            if "maxliq_temp" in ss and "cond_temp" in ss and "evap_temp" in ss:
                ss.cond_temp = min(max(ss.cond_temp, ss.maxliq_temp, ss.evap_temp), cond_max)
    
            if "cond_temp" in ss and "maxliq_temp" in ss and "evap_temp" in ss:
                ss.evap_temp = min(ss.maxliq_temp, ss.cond_temp, ss.evap_temp)
            
            # --- Callbacks implementing your downstream clamping logic ---
            def on_change_cond():
                # When cond changes: clamp maxliq down to cond, then evap down to maxliq
                ss.maxliq_temp = min(ss.maxliq_temp, ss.cond_temp)
                ss.evap_temp   = min(ss.evap_temp,   ss.maxliq_temp)
    
            def on_change_maxliq():
                # When maxliq changes: clamp maxliq down to cond, then evap down to maxliq
                ss.maxliq_temp = min(ss.maxliq_temp, ss.cond_temp)
                ss.evap_temp   = min(ss.evap_temp,   ss.maxliq_temp)
    
            def on_change_evap():
                # When evap changes: clamp evap down to maxliq
                ss.evap_temp   = min(ss.evap_temp,   ss.maxliq_temp)
    
            # --- Inputs with inclusive caps (≤), same order as your code ---
            condensing_temp = st.number_input(
                "Condensing Temperature (°C)",
                min_value=cond_min, max_value=cond_max,
                value=ss.cond_temp, step=1.0, key="cond_temp",
                on_change=on_change_cond,
            )
    
            maxliq_temp = st.number_input(
                "Liquid Temperature (°C)",
                min_value=maxliq_min, max_value=min(condensing_temp, maxliq_max),
                value=ss.maxliq_temp, step=1.0, key="maxliq_temp",
                on_change=on_change_maxliq,
            )

            evaporating_temp = st.number_input(
                "Evaporating Temperature (°C)",
                min_value=evap_min, max_value=min(maxliq_temp, evap_max),
                value=ss.evap_temp, step=1.0, key="evap_temp",
                on_change=on_change_evap,
            )
        
        with col2:
            isen = st.number_input("Isentropic Efficiency (%)", min_value=50.0, max_value=90.0, value=75.0, step=5.0)
            superheat_K = st.number_input("Superheat (K)", min_value=0.0, max_value=60.0, value=5.0, step=1.0)
            max_penalty = st.number_input("Max Penalty (K)", min_value=0.0, max_value=6.0, value=1.0, step=0.1)
    
        with col3:
            L = st.number_input("Pipe Length (m)", min_value=0.1, max_value=300.0, value=10.0, step=1.0)
            LRB = st.number_input("Long Radius Bends", min_value=0, max_value=50, value=0, step=1)
            SRB = st.number_input("Short Radius Bends", min_value=0, max_value=50, value=0, step=1)
            _45 = st.number_input("45° Bends", min_value=0, max_value=50, value=0, step=1)
            MAC = st.number_input("Machine Bends", min_value=0, max_value=50, value=0, step=1)
    
        with col4:
            ptrap = st.number_input("P Traps", min_value=0, max_value=10, value=0, step=1)
            ubend = st.number_input("U Bends", min_value=0, max_value=10, value=0, step=1)
            ball = st.number_input("Ball Valves", min_value=0, max_value=20, value=0, step=1)
            globe = st.number_input("Globe Valves", min_value=0, max_value=20, value=0, step=1)
            PLF = st.number_input("Pressure Loss Factors", min_value=0.0, max_value=20.0, value=0.0, step=0.1)

        T_evap = evaporating_temp
        T_liq = maxliq_temp
        T_cond = condensing_temp
    
        props = RefrigerantProperties()
        
        h_in = props.get_properties(refrigerant, T_liq)["enthalpy_liquid2"]

        h_evap = props.get_properties(refrigerant, T_evap)["enthalpy_vapor"]
        
        delta_h = h_evap - h_in

        mass_flow_kg_s = evap_capacity_kw / delta_h if delta_h > 0 else 0.01
    
        if ID_mm is not None:
            ID_m = ID_mm / 1000.0

            area_m2 = math.pi * (ID_m / 2) ** 2

            suc_ent = RefrigerantEntropies().get_entropy(refrigerant, T_evap + 273.15, superheat_K)
            
            isen_sup = RefrigerantEntropies().get_superheat_from_entropy(refrigerant, T_cond + 273.15, suc_ent)

            isen_enth = RefrigerantEnthalpies().get_enthalpy(refrigerant, T_cond + 273.15, isen_sup)

            suc_enth = RefrigerantEnthalpies().get_enthalpy(refrigerant, T_evap + 273.15, superheat_K)

            isen_change = isen_enth - suc_enth

            enth_change = isen_change / (isen / 100)

            dis_enth = suc_enth + enth_change

            dis_sup = RefrigerantEnthalpies().get_superheat_from_enthalpy(refrigerant, T_cond + 273.15, dis_enth)

            dis_t = T_cond + dis_sup

            dis_dens = RefrigerantDensities().get_density(refrigerant, T_cond + 273.15, dis_sup)

            dis_visc = RefrigerantViscosities().get_viscosity(refrigerant, T_cond + 273.15, dis_sup)

            velocity_m_s = mass_flow_kg_s / (area_m2 * dis_dens)
            
        else:
            velocity_m_s = None

        reynolds = (dis_dens * velocity_m_s * ID_m) / (dis_visc / 1000000)

        if selected_material in ["Steel SCH40", "Steel SCH80"]:
            eps = 0.00004572 #0.00015
        else:
            eps = 0.000001524 #0.000005
        
        tol = 1e-5
        max_iter = 60
        
        if reynolds < 2000.0:
            f = 64.0 / reynolds
        else:
            flo, fhi = 1e-5, 0.1
            def balance(gg):
                s = math.sqrt(gg)
                lhs = 1.0 / s
                rhs = -2.0 * math.log10((eps / (3.7 * ID_m)) + 2.51 / (reynolds * s))
                return lhs, rhs
    
            f = 0.5 * (flo + fhi)
            for _ in range(max_iter):
                f = 0.5 * (flo + fhi)
                lhs, rhs = balance(f)
                if abs(1.0 - lhs/rhs) < tol:
                    break
                # decide side using sign of (lhs - rhs)
                if (lhs - rhs) > 0.0:
                    flo = f
                else:
                    fhi = f

        q_kPa = 0.5 * dis_dens * (velocity_m_s ** 2) / 1000.0

        dp_pipe_kPa = f * (L / ID_m) * q_kPa
        
        dp_plf_kPa = q_kPa * PLF
    
        required_cols = ["SRB", "LRB", "BALL", "GLOBE"]
        missing = [c for c in required_cols if c not in selected_pipe_row.index]
        if missing:
            st.error(f"CSV missing required K columns: {missing}")
            st.stop()
    
        # Convert to floats and check NaNs
        try:
            K_SRB  = float(selected_pipe_row["SRB"])
            K_LRB  = float(selected_pipe_row["LRB"])
            K_BALL = float(selected_pipe_row["BALL"])
            K_GLOBE= float(selected_pipe_row["GLOBE"])
        except Exception as e:
            st.error(f"Failed to parse K-factors as numbers: {e}")
            st.stop()
    
        if any(pd.isna([K_SRB, K_LRB, K_BALL, K_GLOBE])):
            st.error("One or more K-factors are NaN in the CSV row.")
            st.stop()
        
        B_SRB = SRB + 0.5 * _45 + 2.0 * ubend + 3.0 * ptrap
        B_LRB = LRB + MAC
    
        dp_fittings_kPa = q_kPa * (
        K_SRB   * B_SRB +
        K_LRB   * B_LRB
        )

        dp_valves_kPa = q_kPa * (
        K_BALL  * ball +
        K_GLOBE * globe
        )
        
        dp_total_kPa = dp_pipe_kPa + dp_fittings_kPa + dp_valves_kPa + dp_plf_kPa

        converter = PressureTemperatureConverter()
        condpres = converter.temp_to_pressure(refrigerant, T_cond)
        postcirc = condpres - (dp_total_kPa / 100)
        postcirctemp = converter.pressure_to_temp(refrigerant, postcirc)
        
        dt = T_cond - postcirctemp

        evappres = converter.temp_to_pressure(refrigerant, T_evap)

        volflow = mass_flow_kg_s / dis_dens

        compratio = condpres / evappres
        
        def _pipe_row_for_size(size_inch: str):
            rows = material_df[material_df["Nominal Size (inch)"].astype(str).str.strip() == str(size_inch)]
            if rows.empty:
                return None
            if "Gauge" in rows.columns and rows["Gauge"].notna().any():
                if "gauge" in st.session_state:
                    g = st.session_state["gauge"]
                    rows_g = rows[rows["Gauge"] == g]
                    if not rows_g.empty:
                        return rows_g.iloc[0]
                return rows.iloc[0]
            return rows.iloc[0]

        def get_discharge_dt_for_size(size_inch: str) -> float:
            """
            Compute ΔT (dt) for a given discharge pipe size using the SAME method as the main block:
            1) Isentropic chain → discharge superheat, enthalpy, temperature
            2) Discharge density/viscosity at (T_cond, dis_sup)
            3) Velocity/Reynolds → friction factor (Colebrook or laminar)
            4) q_kPa → dp's (pipe + fittings + valves + PLF)
            5) Convert dp to post-circ temperature → dt = T_cond - postcirc_temp
            Returns NaN on failure.
            """
            try:
                pipe_row = _pipe_row_for_size(size_inch)
                if pipe_row is None:
                    return float("nan")
        
                # Geometry
                ID_mm_local = float(pipe_row["ID_mm"])
                ID_m_local  = ID_mm_local / 1000.0
                area_m2     = math.pi * (ID_m_local / 2) ** 2
        
                # 1) Isentropic chain – size independent, but we recompute to be safe
                suc_ent    = RefrigerantEntropies().get_entropy(refrigerant, T_evap + 273.15, superheat_K)
                isen_sup   = RefrigerantEntropies().get_superheat_from_entropy(refrigerant, T_cond + 273.15, suc_ent)
                isen_enth  = RefrigerantEnthalpies().get_enthalpy(refrigerant, T_cond + 273.15, isen_sup)
                suc_enth   = RefrigerantEnthalpies().get_enthalpy(refrigerant, T_evap + 273.15, superheat_K)
                isen_change = isen_enth - suc_enth
                enth_change = isen_change / (isen / 100.0)
                dis_enth    = suc_enth + enth_change
                dis_sup     = RefrigerantEnthalpies().get_superheat_from_enthalpy(refrigerant, T_cond + 273.15, dis_enth)
        
                # Discharge properties at (T_cond, dis_sup)
                dis_dens = RefrigerantDensities().get_density(refrigerant, T_cond + 273.15, dis_sup)
                dis_visc = RefrigerantViscosities().get_viscosity(refrigerant, T_cond + 273.15, dis_sup)
        
                # Mass flow is size-independent (already computed in main code)
                v = mass_flow_kg_s / (area_m2 * dis_dens)
        
                # 2) Reynolds
                Re = (dis_dens * v * ID_m_local) / (dis_visc / 1_000_000)
        
                # 3) Roughness and friction factor
                eps = 0.00004572 if selected_material in ["Steel SCH40", "Steel SCH80"] else 0.000001524
                if Re < 2000.0 and Re > 0:
                    f_local = 64.0 / Re
                else:
                    flo, fhi = 1e-5, 0.1
                    tol, max_iter = 1e-5, 60
                    def balance(gg):
                        s = math.sqrt(gg)
                        lhs = 1.0 / s
                        rhs = -2.0 * math.log10((eps / (3.7 * ID_m_local)) + 2.51 / (Re * s))
                        return lhs, rhs
                    f_local = 0.5 * (flo + fhi)
                    for _ in range(max_iter):
                        f_try = 0.5 * (flo + fhi)
                        lhs, rhs = balance(f_try)
                        if abs(1.0 - lhs / rhs) < tol:
                            f_local = f_try
                            break
                        if (lhs - rhs) > 0.0:
                            flo = f_try
                        else:
                            fhi = f_try
                    else:
                        f_local = 0.5 * (flo + fhi)
        
                # 4) Dynamic pressure and K-based losses
                q_kPa = 0.5 * dis_dens * (v ** 2) / 1000.0
        
                for c in ["SRB", "LRB", "BALL", "GLOBE"]:
                    if c not in pipe_row.index or pd.isna(pipe_row[c]):
                        return float("nan")
                K_SRB   = float(pipe_row["SRB"])
                K_LRB   = float(pipe_row["LRB"])
                K_BALL  = float(pipe_row["BALL"])
                K_GLOBE = float(pipe_row["GLOBE"])
        
                B_SRB = SRB + 0.5 * _45 + 2.0 * ubend + 3.0 * ptrap
                B_LRB = LRB + MAC
        
                dp_pipe_kPa = f_local * (L / ID_m_local) * q_kPa
                dp_plf_kPa  = q_kPa * PLF
                dp_fit_kPa  = q_kPa * (K_SRB * B_SRB + K_LRB * B_LRB)
                dp_val_kPa  = q_kPa * (K_BALL * ball + K_GLOBE * globe)
        
                dp_total_kPa_local = dp_pipe_kPa + dp_fit_kPa + dp_val_kPa + dp_plf_kPa
        
                # 5) Convert Δp → ΔT at condenser side
                conv = PressureTemperatureConverter()
                condpres_local   = conv.temp_to_pressure(refrigerant, T_cond)
                postcirc_local   = condpres_local - (dp_total_kPa_local / 100.0)  # kPa→bar
                postcirctemp_loc = conv.pressure_to_temp(refrigerant, postcirc_local)
                dt_local         = T_cond - postcirctemp_loc
        
                return float(dt_local)
        
            except Exception:
                return float("nan")
        
        if st.button("Auto-select"):
            results, errors = [], []
            for ps in pipe_sizes:
                dt_i = get_discharge_dt_for_size(ps)
                if math.isfinite(dt_i):
                    results.append({"size": ps, "dt": dt_i})
                else:
                    errors.append((ps, "Non-numeric ΔT"))
        
            if not results:
                with st.expander("⚠️ Discharge selection debug details", expanded=True):
                    for ps, msg in errors:
                        st.write(f"❌ {ps}: {msg}")
                st.error("No valid pipe size results. Check inputs and CSV rows.")
            else:
                valid = [r for r in results if r["dt"] <= max_penalty]
                if valid:
                    best = min(valid, key=lambda x: mm_map[x["size"]])  # smallest OD that passes
                    st.session_state["_next_selected_size"] = best["size"]
                    st.success(
                        f"✅ Selected discharge pipe size: **{best['size']}**  \n"
                        f"ΔT: {best['dt']:.3f} K (limit {max_penalty:.3f} K)"
                    )
                    st.rerun()
                else:
                    best_dt = min(r["dt"] for r in results if math.isfinite(r["dt"]))
                    st.error(
                        "❌ No pipe meets the ΔT limit.  \n"
                        f"Best achievable ΔT = {best_dt:.3f} K (must be ≤ {max_penalty:.3f} K)  \n"
                        "➡ Relax the Max Penalty or change material/length/fittings."
                    )
        
        st.subheader("Results")
    
        if velocity_m_s:
            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
            with col1:
                st.metric("Refrigerant Velocity", f"{velocity_m_s:.2f}m/s")
    
            with col2:
                st.metric("Discharge Density", f"{dis_dens:.2f}kg/m³")
    
            with col3:
                st.metric("Pressure Drop", f"{dp_total_kPa:.2f}kPa")
    
            with col4:
                st.metric("Temp Penalty", f"{dt:.2f}K")

            with col5:
                st.metric("Discharge Temperature", f"{dis_t:.2f}°C")

            with col6:
                st.metric("Evaporating Pressure", f"{evappres:.2f}bar(a)")

            with col7:
                st.metric("Condensing Pressure", f"{condpres:.2f}bar(a)")
            
            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
            with col1:
                st.metric("Mass Flow Rate", f"{mass_flow_kg_s:.5f}kg/s")
    
            with col2:
                st.metric("Volumetric Flow Rate", f"{volflow:.5f}m³/s")
    
            with col3:
                st.metric("Pipe PD", f"{dp_pipe_kPa:.2f}kPa")
    
            with col4:
                st.metric("Fittings PD", f"{dp_fittings_kPa:.2f}kPa")

            with col5:
                st.metric("Valves PD", f"{dp_valves_kPa:.2f}kPa")

            with col6:
                st.metric("Velocity Pressure PD", f"{dp_plf_kPa:.2f}kPa")

            with col7:
                st.metric("Compression Ratio", f"{compratio:.2f}")

    if mode == "Drain":

        from utils.refrigerant_properties import RefrigerantProperties
        from utils.refrigerant_densities import RefrigerantDensities
        from utils.refrigerant_viscosities import RefrigerantViscosities
        from utils.pipe_length_volume_calc import get_pipe_id_mm
        from utils.refrigerant_entropies import RefrigerantEntropies
        from utils.refrigerant_enthalpies import RefrigerantEnthalpies

        col1, col2, col3, col4 = st.columns(4)
    
        with col1:
            refrigerant = st.selectbox("Refrigerant", [
                "R404A", "R134a", "R407F", "R744", "R410A",
                "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A", "R454C", "R455A", "R407A",
                "R290", "R1270", "R600a", "R717", "R1234ze", "R1234yf", "R12", "R11", "R454B", "R450A", "R513A", "R23", "R508B", "R502"
            ], disabled=True)
        
        # Load pipe data
        pipe_data = pd.read_csv("data/pipe_pressure_ratings_full.csv")
    
        # --- helpers ---
        def _nps_inch_to_mm(nps_str: str) -> float:
            # e.g. "1-1/8", '1"', "3/8"
            s = str(nps_str).replace('"', '').strip()
            if not s:
                return float('nan')
            parts = s.split('-')
            tot_in = 0.0
            for p in parts:
                p = p.strip()
                if not p:
                    continue
                if '/' in p:
                    num, den = p.split('/')
                    tot_in += float(num) / float(den)
                else:
                    tot_in += float(p)
            return tot_in * 25.4  # mm
    
        ss = st.session_state
    
        # 1) Pipe material
        with col2:
            if refrigerant == "R717":
                excluded_materials = ["Copper ACR", "Copper EN12735"]
                pipe_materials = sorted(m for m in pipe_data["Material"].dropna().unique()
                                        if m not in excluded_materials)
            else:
                pipe_materials = sorted(pipe_data["Material"].dropna().unique())
    
            selected_material = st.selectbox("Pipe Material", pipe_materials, key="material", disabled=True)
        
        # detect material change
        material_changed = ss.get("last_material") is not None and ss.last_material != selected_material
        ss.last_material = selected_material
    
        # 2) Sizes for selected material (de-duped)
        material_df = pipe_data[pipe_data["Material"] == selected_material].copy()
    
        sizes_df = (
            material_df[["Nominal Size (inch)", "Nominal Size (mm)"]]
            .dropna(subset=["Nominal Size (inch)"])
            .assign(**{
                "Nominal Size (inch)": lambda d: d["Nominal Size (inch)"].astype(str).str.strip(),
            })
            .drop_duplicates(subset=["Nominal Size (inch)"], keep="first")
        )
    
        # make sure we have a numeric mm per nominal (fallback: parse the inch string)
        sizes_df["mm_num"] = pd.to_numeric(sizes_df.get("Nominal Size (mm)"), errors="coerce")
        sizes_df.loc[sizes_df["mm_num"].isna(), "mm_num"] = sizes_df.loc[sizes_df["mm_num"].isna(), "Nominal Size (inch)"].apply(_nps_inch_to_mm)
    
        pipe_sizes = sizes_df["Nominal Size (inch)"].tolist()
        mm_map = dict(zip(sizes_df["Nominal Size (inch)"], sizes_df["mm_num"]))
    
        # choose default index
        def _closest_index(target_mm: float) -> int:
            mm_list = [mm_map[s] for s in pipe_sizes]
            return min(range(len(mm_list)), key=lambda i: abs(mm_list[i] - target_mm)) if mm_list else 0

        default_index = 0
        if material_changed and "prev_pipe_mm" in ss:
            default_index = _closest_index(ss.prev_pipe_mm)
        elif "selected_size" in ss and ss.selected_size in pipe_sizes:
            default_index = pipe_sizes.index(ss.selected_size)
        
        # Apply auto-selected value if present
        if "auto_selected_main" in ss and ss.auto_selected_main in pipe_sizes:
            default_index = pipe_sizes.index(ss.auto_selected_main)
            del ss.auto_selected_main
        
        with col1:

            # --- Before main pipe selectbox ---
            if "auto_selected_main" in st.session_state and st.session_state.auto_selected_main in pipe_sizes:
                default_index = pipe_sizes.index(st.session_state.auto_selected_main)
                del st.session_state.auto_selected_main  # clear after use

            selected_size = st.selectbox(
                "Main Pipe Size (inch)",
                pipe_sizes,
                index=default_index,
                key="selected_size",
            )
    
        # remember the selected size in mm for next material change
        ss.prev_pipe_mm = float(mm_map.get(selected_size, float("nan")))
    
        # 3) Gauge (if applicable)
        gauge_options = material_df[material_df["Nominal Size (inch)"].astype(str).str.strip() == selected_size]
        if "Gauge" in gauge_options.columns and gauge_options["Gauge"].notna().any():
            gauges = sorted(gauge_options["Gauge"].dropna().unique())
            with col2:
                selected_gauge = st.selectbox("Main Copper Gauge", gauges, key="gauge")
            selected_pipe_row = gauge_options[gauge_options["Gauge"] == selected_gauge].iloc[0]
        else:
            selected_pipe_row = gauge_options.iloc[0]
    
        # Pipe parameters
        pipe_size_inch = selected_pipe_row["Nominal Size (inch)"]
        ID_mm = selected_pipe_row["ID_mm"]

        # --- helpers (reuse or keep separate if you want clarity) ---
        def _nps_inch_to_mm_2(nps_str: str) -> float:
            s = str(nps_str).replace('"', '').strip()
            if not s:
                return float('nan')
            parts = s.split('-')
            tot_in = 0.0
            for p in parts:
                p = p.strip()
                if not p:
                    continue
                if '/' in p:
                    num, den = p.split('/')
                    tot_in += float(num) / float(den)
                else:
                    tot_in += float(p)
            return tot_in * 25.4  # mm

        ss = st.session_state

        # 1️⃣ Use same pipe material from main pipe
        selected_material_2 = ss.get("last_material", None)
        if not selected_material_2:
            st.warning("⚠️ Please select a pipe material in the main input first.")
            st.stop()

        # 2️⃣ Filter data for that material only
        material_df_2 = pipe_data[pipe_data["Material"] == selected_material_2].copy()

        sizes_df_2 = (
            material_df_2[["Nominal Size (inch)", "Nominal Size (mm)"]]
            .dropna(subset=["Nominal Size (inch)"])
            .assign(**{
                "Nominal Size (inch)": lambda d: d["Nominal Size (inch)"].astype(str).str.strip(),
            })
            .drop_duplicates(subset=["Nominal Size (inch)"], keep="first")
        )

        # Convert inch → mm if needed
        sizes_df_2["mm_num"] = pd.to_numeric(sizes_df_2.get("Nominal Size (mm)"), errors="coerce")
        sizes_df_2.loc[sizes_df_2["mm_num"].isna(), "mm_num"] = sizes_df_2.loc[
            sizes_df_2["mm_num"].isna(), "Nominal Size (inch)"
        ].apply(_nps_inch_to_mm_2)

        pipe_sizes_2 = sizes_df_2["Nominal Size (inch)"].tolist()
        mm_map_2 = dict(zip(sizes_df_2["Nominal Size (inch)"], sizes_df_2["mm_num"]))

        # 3️⃣ Choose default index
        def _closest_index_2(target_mm: float) -> int:
            mm_list = [mm_map_2[s] for s in pipe_sizes_2]
            return min(range(len(mm_list)), key=lambda i: abs(mm_list[i] - target_mm)) if mm_list else 0

        default_index_2 = 0
        if "prev_pipe_mm_2" in ss:
            default_index_2 = _closest_index_2(ss.prev_pipe_mm_2)
        elif "selected_size_2" in ss and ss.selected_size_2 in pipe_sizes_2:
            default_index_2 = pipe_sizes_2.index(ss.selected_size_2)
        
        # Apply auto-selected value if present
        if "auto_selected_branch" in ss and ss.auto_selected_branch in pipe_sizes_2:
            default_index_2 = pipe_sizes_2.index(ss.auto_selected_branch)
            del ss.auto_selected_branch

        # 4️⃣ Size selector
        with col1:

            # --- Before branch pipe selectbox ---
            if "auto_selected_branch" in st.session_state and st.session_state.auto_selected_branch in pipe_sizes_2:
                default_index_2 = pipe_sizes_2.index(st.session_state.auto_selected_branch)
                del st.session_state.auto_selected_branch  # clear after use

            selected_size_2 = st.selectbox(
                "Branch Pipe Size (inch)",
                pipe_sizes_2,
                index=default_index_2,
                key="selected_size_2",
            )

        ss.prev_pipe_mm_2 = float(mm_map_2.get(selected_size_2, float("nan")))

        # 5️⃣ Gauge selector (if applicable)
        gauge_options_2 = material_df_2[
            material_df_2["Nominal Size (inch)"].astype(str).str.strip() == selected_size_2
        ]

        if "Gauge" in gauge_options_2.columns and gauge_options_2["Gauge"].notna().any():
            gauges_2 = sorted(gauge_options_2["Gauge"].dropna().unique())
            with col2:
                selected_gauge_2 = st.selectbox("Branch Copper Gauge", gauges_2, key="gauge_2")
            selected_pipe_row_2 = gauge_options_2[gauge_options_2["Gauge"] == selected_gauge_2].iloc[0]
        else:
            selected_pipe_row_2 = gauge_options_2.iloc[0]

        # 6️⃣ Output parameters for secondary pipe
        pipe_size_inch_2 = selected_pipe_row_2["Nominal Size (inch)"]
        ID_mm_2 = selected_pipe_row_2["ID_mm"]
        
        # --- Rule: Main pipe must be >= Branch pipe ---
        invalid_pipe_selection = False
        if ID_mm < ID_mm_2:
            st.error(
                f"🚫 Invalid selection: The main pipe ({selected_size} – {ID_mm:.2f} mm ID) "
                f"is smaller than the branch pipe ({selected_size_2} – {ID_mm_2:.2f} mm ID). "
                "Please choose a larger main pipe or a smaller branch pipe."
            )
            invalid_pipe_selection = True
        
        with col3:
            
            evap_capacity_kw = st.number_input("Evaporator Capacity (kW)", min_value=0.03, max_value=20000.0, value=10.0, step=1.0)
            no_branch = st.number_input("No. of Branches", min_value=2, max_value=10, value=2, step=1)
            
            # --- Base ranges per refrigerant ---
            if refrigerant in ("R23", "R508B"):
                evap_min, evap_max, evap_default = -100.0, -20.0, -80.0
                cond_min, cond_max, cond_default = -100.0, 10.0, -30.0
                maxliq_min, maxliq_max, maxliq_default = -100.0, 10.0, -40.0
            elif refrigerant == "R744":
                evap_min, evap_max, evap_default = -50.0, 20.0, -10.0
                cond_min, cond_max, cond_default = -23.0, 30.0, 15.0
                maxliq_min, maxliq_max, maxliq_default = -50.0, 30.0, 10.0
            else:
                evap_min, evap_max, evap_default = -50.0, 30.0, -10.0
                cond_min, cond_max, cond_default = -23.0, 60.0, 43.0
                maxliq_min, maxliq_max, maxliq_default = -50.0, 60.0, 40.0
    
            # --- Init state (widget-backed) ---
            ss = st.session_state
    
            if "last_refrigerant" not in ss or ss.last_refrigerant != refrigerant:
                ss.cond_temp   = cond_default
                ss.maxliq_temp = maxliq_default
                ss.evap_temp   = evap_default
                ss.last_refrigerant = refrigerant
            
            ss.setdefault("cond_temp",   cond_default)
            ss.setdefault("maxliq_temp", maxliq_default)
            ss.setdefault("evap_temp",   evap_default)

            if "maxliq_temp" in ss and "cond_temp" in ss and "evap_temp" in ss:
                ss.cond_temp = min(max(ss.cond_temp, ss.maxliq_temp, ss.evap_temp), cond_max)
    
            if "cond_temp" in ss and "maxliq_temp" in ss and "evap_temp" in ss:
                ss.evap_temp = min(ss.maxliq_temp, ss.cond_temp, ss.evap_temp)
            
            # --- Callbacks implementing your downstream clamping logic ---
            def on_change_cond():
                # When cond changes: clamp maxliq down to cond, then evap down to maxliq
                ss.maxliq_temp = min(ss.maxliq_temp, ss.cond_temp)
                ss.evap_temp   = min(ss.evap_temp,   ss.maxliq_temp)
    
            def on_change_maxliq():
                # When maxliq changes: clamp maxliq down to cond, then evap down to maxliq
                ss.maxliq_temp = min(ss.maxliq_temp, ss.cond_temp)
                ss.evap_temp   = min(ss.evap_temp,   ss.maxliq_temp)
    
            def on_change_evap():
                # When evap changes: clamp evap down to maxliq
                ss.evap_temp   = min(ss.evap_temp,   ss.maxliq_temp)
    
        with col4:
            
            # --- Inputs with inclusive caps (≤), same order as your code ---
            condensing_temp = st.number_input(
                "Condensing Temperature (°C)",
                min_value=cond_min, max_value=cond_max,
                value=ss.cond_temp, step=1.0, key="cond_temp",
                on_change=on_change_cond,
                disabled=True,
            )
    
            maxliq_temp = st.number_input(
                "Liquid Temperature (°C)",
                min_value=maxliq_min, max_value=min(condensing_temp, maxliq_max),
                value=ss.maxliq_temp, step=1.0, key="maxliq_temp",
                on_change=on_change_maxliq,
                disabled=True,
            )

            evaporating_temp = st.number_input(
                "Evaporating Temperature (°C)",
                min_value=evap_min, max_value=min(maxliq_temp, evap_max),
                value=ss.evap_temp, step=1.0, key="evap_temp",
                on_change=on_change_evap,
                disabled=True,
            )

        if not invalid_pipe_selection:
        
            T_evap = evaporating_temp
            T_liq = maxliq_temp
            T_cond = condensing_temp
        
            props = RefrigerantProperties()
    
            h_in = props.get_properties(refrigerant, T_liq)["enthalpy_liquid2"]
    
            h_evap = props.get_properties(refrigerant, T_evap)["enthalpy_vapor"]
            
            delta_h = h_evap - h_in
    
            mass_flow_kg_s = evap_capacity_kw / delta_h if delta_h > 0 else 0.01
    
            if ID_mm is not None:
                ID_m = ID_mm / 1000.0
    
                area_m2 = math.pi * (ID_m / 2) ** 2
    
                density1 = RefrigerantProperties().get_properties(refrigerant, T_liq)["density_liquid2"]
    
                density2 = RefrigerantProperties().get_properties(refrigerant, T_cond)["density_liquid"]
    
                density = min(density1, density2)
    
                velocity_m_s = mass_flow_kg_s / (area_m2 * density)
    
            else:
                velocity_m_s = None
    
            mf_branch = mass_flow_kg_s / no_branch
    
            ID_m_2 = ID_mm_2 / 1000.0
    
            area_m2_2 = math.pi * (ID_m_2 / 2) ** 2
    
            vel_branch = mf_branch / (area_m2_2 * density)
    
            # --- Automatic pipe size selection button ---
            if st.button("Auto-select"):
                target_velocity = 0.55  # m/s
            
                # Compute main pipe size
                best_main = None
                for size in pipe_sizes:
                    ID_main_mm = material_df.loc[
                        material_df["Nominal Size (inch)"].astype(str).str.strip() == size, "ID_mm"
                    ].iloc[0]
                    ID_main_m = ID_main_mm / 1000.0
                    area_main = math.pi * (ID_main_m / 2) ** 2
                    vel_main = mass_flow_kg_s / (area_main * density)
                    if vel_main <= target_velocity:
                        best_main = size
                        break
            
                # Compute branch pipe size
                best_branch = None
                for size in pipe_sizes_2:
                    ID_branch_mm = material_df_2.loc[
                        material_df_2["Nominal Size (inch)"].astype(str).str.strip() == size, "ID_mm"
                    ].iloc[0]
                    ID_branch_m = ID_branch_mm / 1000.0
                    area_branch = math.pi * (ID_branch_m / 2) ** 2
                    vel_branch_calc = mf_branch / (area_branch * density)
                    if vel_branch_calc <= target_velocity:
                        best_branch = size
                        break
            
                # ✅ Store in temp state (safe names that are not bound to widgets)
                if best_main:
                    st.session_state["auto_selected_main"] = best_main
                    st.success(f"✅ Main pipe set to {best_main} (velocity ≤ {target_velocity} m/s)")
                else:
                    st.warning("⚠️ No main pipe found with velocity ≤ 0.55 m/s")
            
                if best_branch:
                    st.session_state["auto_selected_branch"] = best_branch
                    st.success(f"✅ Branch pipe set to {best_branch} (velocity ≤ {target_velocity} m/s)")
                else:
                    st.warning("⚠️ No branch pipe found with velocity ≤ 0.55 m/s")
            
                st.rerun()
    
            st.subheader("Results")
    
            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
            
            with col1:
    
                st.metric("Main Velocity", f"{velocity_m_s:.2f}m/s")
    
            with col2:
    
                st.metric("Branch Velocity", f"{vel_branch:.2f}m/s")
    
            with col3:
                st.empty()
            with col4:
                st.empty()
            with col5:
                st.empty()
            with col6:
                st.empty()
            with col7:
                st.empty()

        else:
            st.warning("Pipe size validation failed — calculations skipped.")

    if mode == "Wet Suction":

        def find_pipe_diameter(PD, Vis, Den, MassF, choice, surface_roughness):
        
            import math
        
            VEA = MassF / Den
            RenoEA = Vis
        
            # Hi2 / Lo2 bounds
            Hi2 = 0.3048
            Lo2 = 0.0003048
        
            for _ in range(200):
                PipeDia = (Hi2 + Lo2) / 2.0
                PipeArea = math.pi * (PipeDia * 0.5) ** 2
        
                Vel = VEA / PipeArea
                VP = 0.5 * Den * Vel**2
                Reno = Den * PipeDia * Vel / RenoEA
        
                # Friction factor
                if Reno < 2000:
                    FF = 64.0 / Reno
                else:
                    # Colebrook bisection exactly like VB
                    Hi = 0.1
                    Lo = 0.00001
                    FF = None
                    for _ in range(60):
                        FF_try = (Hi + Lo) / 2.0
                        LHS = 1.0 / math.sqrt(FF_try)
                        RHS = -2 * (math.log10((surface_roughness / (PipeDia * 3.7)) +
                                               (2.51 / (Reno * math.sqrt(FF_try)))))
                        if LHS > RHS:
                            Lo = FF_try
                        else:
                            Hi = FF_try
                    FF = (Hi + Lo) / 2.0
        
                # Pipe pressure drop
                PPD = FF * 30.48 / PipeDia * VP
        
                if PPD > PD:
                    Lo2 = PipeDia
                else:
                    Hi2 = PipeDia
        
                if abs(1 - (PPD / PD)) < 0.00001:
                    break
        
            return PipeDia

        col1, col2, col3, col4 = st.columns(4)
    
        with col1:
            refrigerant = st.selectbox("Refrigerant", [
                "R404A", "R134a", "R407F", "R744", "R410A",
                "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A", "R454C", "R455A", "R407A",
                "R290", "R1270", "R600a", "R717", "R1234ze", "R1234yf", "R12", "R11", "R454B", "R450A", "R513A", "R23", "R508B", "R502"
            ])
    
        # Load pipe data
        pipe_data = pd.read_csv("data/pipe_pressure_ratings_full.csv")
    
        # --- helpers ---
        def _nps_inch_to_mm(nps_str: str) -> float:
            # e.g. "1-1/8", '1"', "3/8"
            s = str(nps_str).replace('"', '').strip()
            if not s:
                return float('nan')
            parts = s.split('-')
            tot_in = 0.0
            for p in parts:
                p = p.strip()
                if not p:
                    continue
                if '/' in p:
                    num, den = p.split('/')
                    tot_in += float(num) / float(den)
                else:
                    tot_in += float(p)
            return tot_in * 25.4  # mm
    
        ss = st.session_state
    
        # 1) Pipe material
        with col2:
            if refrigerant == "R717":
                excluded_materials = ["Copper ACR", "Copper EN12735"]
                pipe_materials = sorted(m for m in pipe_data["Material"].dropna().unique()
                                        if m not in excluded_materials)
            else:
                pipe_materials = sorted(pipe_data["Material"].dropna().unique())
    
            selected_material = st.selectbox("Pipe Material", pipe_materials, key="material")
        
        # detect material change
        material_changed = ss.get("last_material") is not None and ss.last_material != selected_material
        ss.last_material = selected_material
    
        # 2) Sizes for selected material (de-duped)
        material_df = pipe_data[pipe_data["Material"] == selected_material].copy()
    
        sizes_df = (
            material_df[["Nominal Size (inch)", "Nominal Size (mm)"]]
            .dropna(subset=["Nominal Size (inch)"])
            .assign(**{
                "Nominal Size (inch)": lambda d: d["Nominal Size (inch)"].astype(str).str.strip(),
            })
            .drop_duplicates(subset=["Nominal Size (inch)"], keep="first")
        )
    
        # make sure we have a numeric mm per nominal (fallback: parse the inch string)
        sizes_df["mm_num"] = pd.to_numeric(sizes_df.get("Nominal Size (mm)"), errors="coerce")
        sizes_df.loc[sizes_df["mm_num"].isna(), "mm_num"] = sizes_df.loc[sizes_df["mm_num"].isna(), "Nominal Size (inch)"].apply(_nps_inch_to_mm)
    
        pipe_sizes = sizes_df["Nominal Size (inch)"].tolist()
        mm_map = dict(zip(sizes_df["Nominal Size (inch)"], sizes_df["mm_num"]))

        def _pipe_row_for_size(size_inch: str):
            rows = material_df[material_df["Nominal Size (inch)"].astype(str).str.strip() == str(size_inch)]
            if rows.empty:
                return None
            if "Gauge" in rows.columns and rows["Gauge"].notna().any():
                if "gauge" in st.session_state:
                    g = st.session_state["gauge"]
                    match = rows[rows["Gauge"] == g]
                    if not match.empty:
                        return match.iloc[0]
                return rows.iloc[0]
            return rows.iloc[0]
    
        # choose default index
        def _closest_index(target_mm: float) -> int:
            mm_list = [mm_map[s] for s in pipe_sizes]
            return min(range(len(mm_list)), key=lambda i: abs(mm_list[i] - target_mm)) if mm_list else 0
    
        # --- consume any deferred selection from Auto-select button ---
        if "_next_selected_size" in st.session_state:
            new_val = st.session_state.pop("_next_selected_size")
            if new_val in pipe_sizes:
                st.session_state["selected_size"] = new_val
                st.session_state["_selected_size_just_set"] = True
        
        default_index = 0
        if material_changed and "prev_pipe_mm" in ss:
            default_index = _closest_index(ss.prev_pipe_mm)
        elif selected_material == "Copper ACR" and ("7/8" in pipe_sizes or '7/8"' in pipe_sizes):
            # first load or no previous selection → prefer 1-1/8" for Copper ACR
            want = "7/8" if "7/8" in pipe_sizes else '7/8"'
            default_index = pipe_sizes.index(want)
        elif "selected_size" in ss and ss.selected_size in pipe_sizes:
            # if Streamlit kept the selection, use it
            default_index = pipe_sizes.index(ss.selected_size)
        
        with col1:
            selected_size = st.selectbox(
                "Nominal Pipe Size (inch)",
                pipe_sizes,
                index=default_index,
                key="selected_size",
            )

        # --- clean up one-shot flag ---
        if st.session_state.get("_selected_size_just_set"):
            del st.session_state["_selected_size_just_set"]
    
        # remember the selected size in mm for next material change
        ss.prev_pipe_mm = float(mm_map.get(selected_size, float("nan")))
    
        # 3) Gauge (if applicable)
        gauge_options = material_df[material_df["Nominal Size (inch)"].astype(str).str.strip() == selected_size]
        if "Gauge" in gauge_options.columns and gauge_options["Gauge"].notna().any():
            gauges = sorted(gauge_options["Gauge"].dropna().unique())
            with col2:
                selected_gauge = st.selectbox("Copper Gauge", gauges, key="gauge")
            selected_pipe_row = gauge_options[gauge_options["Gauge"] == selected_gauge].iloc[0]
        else:
            selected_pipe_row = gauge_options.iloc[0]
    
        # Pipe parameters
        pipe_size_inch = selected_pipe_row["Nominal Size (inch)"]
        ID_mm = selected_pipe_row["ID_mm"]
    
        with col1:
            
            evap_capacity_kw = st.number_input("Evaporator Capacity (kW)", min_value=0.03, max_value=20000.0, value=10.0, step=1.0)
            
            # --- Base ranges per refrigerant ---
            if refrigerant in ("R23", "R508B"):
                evap_min, evap_max, evap_default = -100.0, -20.0, -80.0
            elif refrigerant == "R744":
                evap_min, evap_max, evap_default = -50.0, 20.0, -10.0
            else:
                evap_min, evap_max, evap_default = -50.0, 30.0, -10.0
    
            # --- Init state (widget-backed) ---
            ss = st.session_state
    
            if "last_refrigerant" not in ss or ss.last_refrigerant != refrigerant:
                ss.evap_temp   = evap_default
                ss.last_refrigerant = refrigerant
        
            ss.setdefault("evap_temp",   evap_default)

            liq_oq = st.number_input("Liquid Overfeed Quantity (%)", min_value=0.0, max_value=2000.0, value=100.0, step=25.0)

        with col2:
            
            evaporating_temp = st.number_input(
                "Evaporating Temperature (°C)",
                min_value=evap_min, max_value=evap_max,
                value=ss.evap_temp, step=1.0, key="evap_temp",
            )
    
        with col2:
            WetSucPenaltyFactor = st.number_input("Max Liquid Hold-Up Penalty Bias", min_value=1.0, max_value=3.0, value=1.5, step=0.1)
            max_penalty = st.number_input("Max Penalty (K)", min_value=0.0, max_value=6.0, value=1.0, step=0.1)
    
        with col3:
            L = st.number_input("Pipe Length (m)", min_value=0.1, max_value=300.0, value=10.0, step=1.0)
            LRB = st.number_input("Long Radius Bends", min_value=0, max_value=50, value=0, step=1)
            SRB = st.number_input("Short Radius Bends", min_value=0, max_value=50, value=0, step=1)
            _45 = st.number_input("45° Bends", min_value=0, max_value=50, value=0, step=1)
            MAC = st.number_input("Machine Bends", min_value=0, max_value=50, value=0, step=1)
    
        with col4:
            ptrap = st.number_input("P Traps", min_value=0, max_value=10, value=0, step=1)
            ubend = st.number_input("U Bends", min_value=0, max_value=10, value=0, step=1)
            ball = st.number_input("Ball Valves", min_value=0, max_value=20, value=0, step=1)
            globe = st.number_input("Globe Valves", min_value=0, max_value=20, value=0, step=1)
            PLF = st.number_input("Pressure Loss Factors", min_value=0.0, max_value=20.0, value=0.0, step=0.1)
        
        from utils.refrigerant_properties import RefrigerantProperties
        from utils.refrigerant_densities import RefrigerantDensities
        from utils.refrigerant_viscosities import RefrigerantViscosities
        from utils.pipe_length_volume_calc import get_pipe_id_mm
    
        D_int = ID_mm / 1000
        A_total = math.pi * (D_int / 2)**2
        
        T_evap = evaporating_temp
    
        props = RefrigerantProperties()

        h_in = props.get_properties(refrigerant, T_evap)["enthalpy_liquid"]
        h_out = props.get_properties(refrigerant, T_evap)["enthalpy_vapor"]
        deltah = h_out - h_in

        base_massflow = evap_capacity_kw / deltah
        BMR_massflow = 293.07107017224996 / deltah
        overfeed_ratio = 1 + liq_oq / 100
        m_g = base_massflow                # vapour mass
        m_l = base_massflow * (overfeed_ratio - 1)   # liquid mass
        m_gplusl = m_g + m_l

        d_liq1 = props.get_properties(refrigerant, T_evap)["density_liquid"]
        d_vap1 = props.get_properties(refrigerant, T_evap)["density_vapor"]

        v_liq1 = props.get_properties(refrigerant, T_evap)["viscosity_liquid"] / 1000000
        v_vap1 = RefrigerantViscosities().get_viscosity(refrigerant, T_evap + 273.15, 0) / 1000000

        d_liq2 = props.get_properties(refrigerant, T_evap - max_penalty)["density_liquid"]
        d_vap2 = props.get_properties(refrigerant, T_evap - max_penalty)["density_vapor"]

        v_liq2 = props.get_properties(refrigerant, T_evap - max_penalty)["viscosity_liquid"] / 1000000
        v_vap2 = RefrigerantViscosities().get_viscosity(refrigerant, T_evap + 273.15 - max_penalty, 0) / 1000000

        d_liq = (d_liq1 + d_liq2) / 2
        d_vap = (d_vap1 + d_vap2) / 2
        v_liq = (v_liq1 + v_liq2) / 2
        v_vap = (v_vap1 + v_vap2) / 2

        Q_g = m_g / d_vap
        Q_l = m_l / d_liq if liq_oq > 0 else 0

        if liq_oq <= 0 or overfeed_ratio <= 1:
            # Dry suction – behave like your old code's dry branch
            liquid_ratio = 0.0
            A_gas = A_total
            gas_velocity = Q_g / A_gas if A_gas > 0 else 0.0
            D_h = D_int
        else:
            # --- VB6 Wet Suction Logic (faithful) ---
            
            # Determine surface roughness exactly like VB
            if selected_material in ["Steel SCH40", "Steel SCH80"]:
                surface_roughness = 0.00004572
            else:
                surface_roughness = 0.000001524
            
            # Mass flow terms for VB
            D = BMR_massflow   # VB scaling
            
            # VB-equivalent diameters for gas and liquid
            A_diam = find_pipe_diameter(689.476, v_vap, d_vap, D, 1, surface_roughness)
            B_diam = find_pipe_diameter(689.476, v_liq, d_liq, D * (overfeed_ratio - 1), 2, surface_roughness)
            
            # Convert diameters to areas (VB logic)
            A_area = math.pi * (A_diam / 2)**2
            B_area = math.pi * (B_diam / 2)**2
            C_area = A_area + B_area
            
            # VB liquid ratio
            liquid_ratio = B_area / C_area if C_area > 0 else 0
            
            # --- Geometry (VB strata model) ---
            Radius = D_int / 2
            TotalArea = math.pi * Radius**2
            LiqArea = TotalArea * liquid_ratio
            SucArea = TotalArea - LiqArea  # gas area
            
            # Solve Angle exactly like VB
            DegCon = 57.2957795130824
            Angle = (LiqArea / (Radius**2 * 0.5)) * DegCon
            
            # Chord / Arc / Perimeter (VB)
            Chord = math.sin((Angle / DegCon) / 2) * Radius * 2
            Arc = ((360 - Angle) * math.pi) / (360 / (Radius * 2))
            Perimeter = Chord + Arc
            
            # Hydraulic diameter
            if Perimeter > 0:
                D_h = 4 * TotalArea / Perimeter
            else:
                D_h = D_int  # dry fallback
            
            # Gas velocity using VB suction area
            A_gas = SucArea
            gas_velocity = Q_g / A_gas if A_gas > 0 else 0
    
        if v_vap > 0:
            Re = d_vap * gas_velocity * D_h / v_vap
        else:
            Re = 0
    
        if selected_material in ["Steel SCH40", "Steel SCH80"]:
            eps = 0.00004572
        else:
            eps = 0.000001524
    
        if Re <= 0:
            f = 0
        elif Re < 2000:
            f = 64 / Re
        else:
            rel = eps / D_h
            f = 0.02
            for _ in range(60):
                rhs = -2.0 * math.log10((rel / 3.7) + (2.51 / (Re * math.sqrt(f))))
                f_new = 1.0 / (rhs * rhs)
                if abs(f_new - f) / f < 1e-5:
                    f = f_new
                    break
                f = f_new
    
        dyn = 0.5 * d_vap * gas_velocity**2 / 1000
    
        dp_pipe = f * (L / D_h) * dyn
        dp_plf = dyn * PLF
    
        K_SRB = float(selected_pipe_row["SRB"])
        K_LRB = float(selected_pipe_row["LRB"])
        K_BALL = float(selected_pipe_row["BALL"])
        K_GLOBE = float(selected_pipe_row["GLOBE"])
    
        B_SRB = SRB + 0.5 * _45 + 2 * ubend + 3 * ptrap
        B_LRB = LRB + MAC
    
        dp_fittings = dyn * (K_SRB * B_SRB + K_LRB * B_LRB)
        dp_valves = dyn * (K_BALL * ball + K_GLOBE * globe)
        
        if refrigerant == "R404A": C_ref = 0.77
        elif refrigerant == "R502": C_ref = 0.76
        elif refrigerant == "R717": C_ref = 0.64
        elif refrigerant == "R134a": C_ref = 0.71
        else: C_ref = 0.73
    
        WetSucFactor = 1 + (WetSucPenaltyFactor - 1) * (liquid_ratio / C_ref)
        if WetSucFactor < 1:
            WetSucFactor = 1
    
        dp_pipe_ws = dp_pipe * WetSucFactor
        dp_fittings_ws = dp_fittings * WetSucFactor
        dp_valves_ws = dp_valves * WetSucFactor
        dp_plf_ws = dp_plf * WetSucFactor
    
        dp_total_ws = dp_pipe_ws + dp_fittings_ws + dp_valves_ws + dp_plf_ws
        
        converter = PressureTemperatureConverter()
        evappres = converter.temp_to_pressure(refrigerant, T_evap)

        postcirc = evappres - (dp_total_ws / 100)
        
        postcirctemp = converter.pressure_to_temp(refrigerant, postcirc)

        dt = T_evap - postcirctemp

        def get_wet_suction_dt_for_size(size_inch: str) -> float:
            """Compute ΔT for a given Wet Suction pipe size using identical logic to the main block."""
            try:
                pipe_row = _pipe_row_for_size(size_inch)
                if pipe_row is None:
                    return float("nan")
        
                # Geometry
                ID_mm_local = float(pipe_row["ID_mm"])
                D_int = ID_mm_local / 1000
                A_total = math.pi * (D_int / 2) ** 2
        
                # --- identical property setup ---
                T_evap_local = T_evap
                props = RefrigerantProperties()
                h_in = props.get_properties(refrigerant, T_evap_local)["enthalpy_liquid"]
                h_out = props.get_properties(refrigerant, T_evap_local)["enthalpy_vapor"]
                deltah = h_out - h_in
                base_massflow = evap_capacity_kw / deltah
                BMR_massflow = 293.07107017224996 / deltah
                overfeed_ratio = 1 + liq_oq / 100
                m_g = base_massflow
                m_l = base_massflow * (overfeed_ratio - 1)
                m_gplusl = m_g + m_l
        
                d_liq1 = props.get_properties(refrigerant, T_evap_local)["density_liquid"]
                d_vap1 = props.get_properties(refrigerant, T_evap_local)["density_vapor"]
                v_liq1 = props.get_properties(refrigerant, T_evap_local)["viscosity_liquid"] / 1_000_000
                v_vap1 = RefrigerantViscosities().get_viscosity(refrigerant, T_evap_local + 273.15, 0) / 1_000_000
                d_liq2 = props.get_properties(refrigerant, T_evap_local - max_penalty)["density_liquid"]
                d_vap2 = props.get_properties(refrigerant, T_evap_local - max_penalty)["density_vapor"]
                v_liq2 = props.get_properties(refrigerant, T_evap_local - max_penalty)["viscosity_liquid"] / 1_000_000
                v_vap2 = RefrigerantViscosities().get_viscosity(refrigerant, T_evap_local + 273.15 - max_penalty, 0) / 1_000_000
        
                d_liq = (d_liq1 + d_liq2) / 2
                d_vap = (d_vap1 + d_vap2) / 2
                v_liq = (v_liq1 + v_liq2) / 2
                v_vap = (v_vap1 + v_vap2) / 2
        
                Q_g = m_g / d_vap
                Q_l = m_l / d_liq if liq_oq > 0 else 0
        
                # --- identical wet suction geometry logic ---
                if liq_oq <= 0 or overfeed_ratio <= 1:
                    liquid_ratio = 0.0
                    A_gas = A_total
                    gas_velocity = Q_g / A_gas if A_gas > 0 else 0.0
                    D_h = D_int
                else:
                    # surface roughness
                    surface_roughness = 0.00004572 if selected_material in ["Steel SCH40", "Steel SCH80"] else 0.000001524
        
                    D = BMR_massflow
                    A_diam = find_pipe_diameter(689.476, v_vap, d_vap, D, 1, surface_roughness)
                    B_diam = find_pipe_diameter(689.476, v_liq, d_liq, D * (overfeed_ratio - 1), 2, surface_roughness)
                    A_area = math.pi * (A_diam / 2) ** 2
                    B_area = math.pi * (B_diam / 2) ** 2
                    C_area = A_area + B_area
                    liquid_ratio = B_area / C_area if C_area > 0 else 0
                    Radius = D_int / 2
                    TotalArea = math.pi * Radius**2
                    LiqArea = TotalArea * liquid_ratio
                    SucArea = TotalArea - LiqArea
                    DegCon = 57.2957795130824
                    Angle = (LiqArea / (Radius**2 * 0.5)) * DegCon
                    Chord = math.sin((Angle / DegCon) / 2) * Radius * 2
                    Arc = ((360 - Angle) * math.pi) / (360 / (Radius * 2))
                    Perimeter = Chord + Arc
                    D_h = 4 * TotalArea / Perimeter if Perimeter > 0 else D_int
                    A_gas = SucArea
                    gas_velocity = Q_g / A_gas if A_gas > 0 else 0
        
                # --- identical friction and dp chain ---
                Re = d_vap * gas_velocity * D_h / v_vap if v_vap > 0 else 0
                eps = 0.00004572 if selected_material in ["Steel SCH40", "Steel SCH80"] else 0.000001524
        
                if Re <= 0:
                    f = 0
                elif Re < 2000:
                    f = 64 / Re
                else:
                    rel = eps / D_h
                    f = 0.02
                    for _ in range(60):
                        rhs = -2.0 * math.log10((rel / 3.7) + (2.51 / (Re * math.sqrt(f))))
                        f_new = 1.0 / (rhs * rhs)
                        if abs(f_new - f) / f < 1e-5:
                            f = f_new
                            break
                        f = f_new
        
                dyn = 0.5 * d_vap * gas_velocity**2 / 1000
                dp_pipe = f * (L / D_h) * dyn
                dp_plf = dyn * PLF
                K_SRB = float(pipe_row["SRB"])
                K_LRB = float(pipe_row["LRB"])
                K_BALL = float(pipe_row["BALL"])
                K_GLOBE = float(pipe_row["GLOBE"])
                B_SRB = SRB + 0.5 * _45 + 2 * ubend + 3 * ptrap
                B_LRB = LRB + MAC
                dp_fittings = dyn * (K_SRB * B_SRB + K_LRB * B_LRB)
                dp_valves = dyn * (K_BALL * ball + K_GLOBE * globe)
        
                # --- identical wet suction correction ---
                if refrigerant == "R404A": C_ref = 0.77
                elif refrigerant == "R502": C_ref = 0.76
                elif refrigerant == "R717": C_ref = 0.64
                elif refrigerant == "R134a": C_ref = 0.71
                else: C_ref = 0.73
        
                WetSucFactor = 1 + (WetSucPenaltyFactor - 1) * (liquid_ratio / C_ref)
                if WetSucFactor < 1:
                    WetSucFactor = 1
        
                dp_total_ws = (dp_pipe + dp_fittings + dp_valves + dp_plf) * WetSucFactor
        
                conv = PressureTemperatureConverter()
                evappres = conv.temp_to_pressure(refrigerant, T_evap_local)
                postcirc = evappres - (dp_total_ws / 100)
                postcirctemp = conv.pressure_to_temp(refrigerant, postcirc)
                dt_local = T_evap_local - postcirctemp
        
                return float(dt_local)
        
            except Exception:
                return float("nan")

        if st.button("Auto-select"):
            results, errors = [], []
            for ps in pipe_sizes:
                dt_i = get_wet_suction_dt_for_size(ps)
                if math.isfinite(dt_i):
                    results.append({"size": ps, "dt": dt_i})
                else:
                    errors.append((ps, "failed or non-numeric ΔT"))
        
            if not results:
                with st.expander("⚠️ Debug Details", expanded=True):
                    for ps, msg in errors:
                        st.write(f"❌ {ps}: {msg}")
                st.error("No valid results for any pipe size — check CSV or inputs.")
            else:
                valid = [r for r in results if r["dt"] <= max_penalty]
                if valid:
                    best = min(valid, key=lambda x: mm_map[x["size"]])  # smallest ID that passes
                    st.session_state["_next_selected_size"] = best["size"]
                    st.success(
                        f"✅ Auto-selected pipe: **{best['size']}**  \n"
                        f"ΔT = {best['dt']:.3f} K ≤ {max_penalty:.3f} K"
                    )
                    st.rerun()
                else:
                    best_dt = min(r["dt"] for r in results if math.isfinite(r["dt"]))
                    st.error(
                        f"❌ No pipe meets ΔT ≤ {max_penalty:.3f} K.  \n"
                        f"Best achievable ΔT = {best_dt:.3f} K."
                    )
        
        st.subheader("Results")
    
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
        with col1:
            st.metric("Refrigerant Velocity", f"{gas_velocity:.2f}m/s")
    
        with col2:
            st.metric("Vapour Density", f"{d_vap:.2f}kg/m³")
    
        with col3:
            st.metric("Vapour Volumetric Flow", f"{Q_g:.5f}m³/s")
    
        with col4:
            st.metric("Pressure Drop", f"{dp_total_ws:.2f}kPa")

        with col5:
            st.metric("Temp Penalty", f"{dt:.2f}K")

        with col6:
            st.metric("Saturated Temperature", f"{postcirctemp:.2f}°C")

        with col7:
            st.metric("Evaporating Pressure", f"{evappres:.2f}bar(a)")
            
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
        with col1:
            st.metric("Mass Flow Rate", f"{m_gplusl:.5f}kg/s")
    
        with col2:
            st.metric("Liquid Density", f"{d_liq:.1f}kg/m³")
    
        with col3:
            st.metric("Liquid Volumetric Flow", f"{Q_l:.5f}m³/s")
    
        with col4:
            st.metric("Pipe PD", f"{dp_pipe_ws:.2f}kPa")

        with col5:
            st.metric("Fittings PD", f"{dp_fittings_ws:.2f}kPa")

        with col6:
            st.metric("Valves PD", f"{dp_valves_ws:.2f}kPa")

        with col7:
            st.metric("Velocity Pressure PD", f"{dp_plf_ws:.2f}kPa")

    if mode == "Pumped Liquid":
        
        col1, col2, col3, col4 = st.columns(4)
    
        with col1:
            refrigerant = st.selectbox("Refrigerant", [
                "R404A", "R134a", "R407F", "R744", "R410A",
                "R407C", "R507A", "R448A", "R449A", "R22", "R32", "R454A", "R454C", "R455A", "R407A",
                "R290", "R1270", "R600a", "R717", "R1234ze", "R1234yf", "R12", "R11", "R454B", "R450A", "R513A", "R23", "R508B", "R502"
            ])
    
        # Load pipe data
        pipe_data = pd.read_csv("data/pipe_pressure_ratings_full.csv")
    
        # --- helpers ---
        def _nps_inch_to_mm(nps_str: str) -> float:
            # e.g. "1-1/8", '1"', "3/8"
            s = str(nps_str).replace('"', '').strip()
            if not s:
                return float('nan')
            parts = s.split('-')
            tot_in = 0.0
            for p in parts:
                p = p.strip()
                if not p:
                    continue
                if '/' in p:
                    num, den = p.split('/')
                    tot_in += float(num) / float(den)
                else:
                    tot_in += float(p)
            return tot_in * 25.4  # mm
    
        ss = st.session_state
    
        # 1) Pipe material
        with col2:
            if refrigerant == "R717":
                excluded_materials = ["Copper ACR", "Copper EN12735"]
                pipe_materials = sorted(m for m in pipe_data["Material"].dropna().unique()
                                        if m not in excluded_materials)
            else:
                pipe_materials = sorted(pipe_data["Material"].dropna().unique())
    
            selected_material = st.selectbox("Pipe Material", pipe_materials, key="material")
        
        # detect material change
        material_changed = ss.get("last_material") is not None and ss.last_material != selected_material
        ss.last_material = selected_material
    
        # 2) Sizes for selected material (de-duped)
        material_df = pipe_data[pipe_data["Material"] == selected_material].copy()
    
        sizes_df = (
            material_df[["Nominal Size (inch)", "Nominal Size (mm)"]]
            .dropna(subset=["Nominal Size (inch)"])
            .assign(**{
                "Nominal Size (inch)": lambda d: d["Nominal Size (inch)"].astype(str).str.strip(),
            })
            .drop_duplicates(subset=["Nominal Size (inch)"], keep="first")
        )
    
        # make sure we have a numeric mm per nominal (fallback: parse the inch string)
        sizes_df["mm_num"] = pd.to_numeric(sizes_df.get("Nominal Size (mm)"), errors="coerce")
        sizes_df.loc[sizes_df["mm_num"].isna(), "mm_num"] = sizes_df.loc[sizes_df["mm_num"].isna(), "Nominal Size (inch)"].apply(_nps_inch_to_mm)
    
        pipe_sizes = sizes_df["Nominal Size (inch)"].tolist()
        mm_map = dict(zip(sizes_df["Nominal Size (inch)"], sizes_df["mm_num"]))
    
        # choose default index
        def _closest_index(target_mm: float) -> int:
            mm_list = [mm_map[s] for s in pipe_sizes]
            return min(range(len(mm_list)), key=lambda i: abs(mm_list[i] - target_mm)) if mm_list else 0
        
        default_index = 0
        if material_changed and "prev_pipe_mm" in ss:
            default_index = _closest_index(ss.prev_pipe_mm)
        elif selected_material == "Copper ACR" and ("1/2" in pipe_sizes or '1/2"' in pipe_sizes):
            # first load or no previous selection → prefer 1-1/8" for Copper ACR
            want = "1/2" if "1/2" in pipe_sizes else '1/2"'
            default_index = pipe_sizes.index(want)
        elif "selected_size" in ss and ss.selected_size in pipe_sizes:
            # if Streamlit kept the selection, use it
            default_index = pipe_sizes.index(ss.selected_size)
        
        with col1:
            selected_size = st.selectbox(
                "Nominal Pipe Size (inch)",
                pipe_sizes,
                index=default_index,
                key="selected_size",
            )
        
        # remember the selected size in mm for next material change
        ss.prev_pipe_mm = float(mm_map.get(selected_size, float("nan")))
    
        # 3) Gauge (if applicable)
        gauge_options = material_df[material_df["Nominal Size (inch)"].astype(str).str.strip() == selected_size]
        if "Gauge" in gauge_options.columns and gauge_options["Gauge"].notna().any():
            gauges = sorted(gauge_options["Gauge"].dropna().unique())
            with col2:
                selected_gauge = st.selectbox("Copper Gauge", gauges, key="gauge")
            selected_pipe_row = gauge_options[gauge_options["Gauge"] == selected_gauge].iloc[0]
        else:
            selected_pipe_row = gauge_options.iloc[0]
    
        # Pipe parameters
        pipe_size_inch = selected_pipe_row["Nominal Size (inch)"]
        ID_mm = selected_pipe_row["ID_mm"]
    
        with col1:
            
            evap_capacity_kw = st.number_input("Evaporator Capacity (kW)", min_value=0.03, max_value=20000.0, value=10.0, step=1.0)
            
            # --- Base ranges per refrigerant ---
            if refrigerant in ("R23", "R508B"):
                evap_min, evap_max, evap_default = -100.0, -20.0, -80.0
            elif refrigerant == "R744":
                evap_min, evap_max, evap_default = -50.0, 20.0, -10.0
            else:
                evap_min, evap_max, evap_default = -50.0, 30.0, -10.0
    
            # --- Init state (widget-backed) ---
            ss = st.session_state
    
            if "last_refrigerant" not in ss or ss.last_refrigerant != refrigerant:
                ss.evap_temp   = evap_default
                ss.last_refrigerant = refrigerant
        
            ss.setdefault("evap_temp",   evap_default)

            liq_oq = st.number_input("Liquid Overfeed Quantity (%)", min_value=0.0, max_value=2000.0, value=100.0, step=25.0)

        with col2:
            
            evaporating_temp = st.number_input(
                "Pumped Liquid Temperature (°C)",
                min_value=evap_min, max_value=evap_max,
                value=ss.evap_temp, step=1.0, key="evap_temp",
            )
    
        with col2:
            risem = st.number_input("Liquid Lift (m)", min_value=0.0, max_value=30.0, value=0.0, step=1.0)
            max_ppd = st.number_input("Max Pressure Drop (bar)", min_value=0.01, max_value=2.0, value=0.5, step=0.1)
    
        with col3:
            L = st.number_input("Pipe Length (m)", min_value=0.1, max_value=300.0, value=10.0, step=1.0)
            LRB = st.number_input("Long Radius Bends", min_value=0, max_value=50, value=0, step=1)
            SRB = st.number_input("Short Radius Bends", min_value=0, max_value=50, value=0, step=1)
            _45 = st.number_input("45° Bends", min_value=0, max_value=50, value=0, step=1)
            MAC = st.number_input("Machine Bends", min_value=0, max_value=50, value=0, step=1)
    
        with col4:
            ptrap = st.number_input("P Traps", min_value=0, max_value=10, value=0, step=1)
            ubend = st.number_input("U Bends", min_value=0, max_value=10, value=0, step=1)
            ball = st.number_input("Ball Valves", min_value=0, max_value=20, value=0, step=1)
            globe = st.number_input("Globe Valves", min_value=0, max_value=20, value=0, step=1)
            PLF = st.number_input("Pressure Loss Factors", min_value=0.0, max_value=20.0, value=0.0, step=0.1)
        
        from utils.refrigerant_properties import RefrigerantProperties
        from utils.refrigerant_densities import RefrigerantDensities
        from utils.refrigerant_viscosities import RefrigerantViscosities
        from utils.pipe_length_volume_calc import get_pipe_id_mm
    
        T_evap = evaporating_temp
    
        props = RefrigerantProperties()

        h_in = props.get_properties(refrigerant, T_evap)["enthalpy_liquid"]
        h_out = props.get_properties(refrigerant, T_evap)["enthalpy_vapor"]
        deltah = h_out - h_in

        mass_flow_kg_s = (evap_capacity_kw / delta_h) * (1 + (liq_oq / 100)) if delta_h > 0 else 0.01
    
        if ID_mm is not None:
            ID_m = ID_mm / 1000.0

            area_m2 = math.pi * (ID_m / 2) ** 2

            density = RefrigerantProperties().get_properties(refrigerant, T_evap)["density_liquid"]

            velocity_m_s = mass_flow_kg_s / (area_m2 * density)

        else:
            velocity_m_s = None

        viscosity = RefrigerantProperties().get_properties(refrigerant, T_liq)["viscosity_liquid"]
    
        reynolds = (density * velocity_m_s * ID_m) / (viscosity / 1000000)
    
        if selected_material in ["Steel SCH40", "Steel SCH80"]:
            eps = 0.00004572 #0.00015
        else:
            eps = 0.000001524 #0.000005
        
        tol = 1e-5
        max_iter = 60
        
        if reynolds < 2000.0:
            f = 64.0 / reynolds
        else:
            flo, fhi = 1e-5, 0.1
            def balance(gg):
                s = math.sqrt(gg)
                lhs = 1.0 / s
                rhs = -2.0 * math.log10((eps / (3.7 * ID_m)) + 2.51 / (reynolds * s))
                return lhs, rhs
    
            f = 0.5 * (flo + fhi)
            for _ in range(max_iter):
                f = 0.5 * (flo + fhi)
                lhs, rhs = balance(f)
                if abs(1.0 - lhs/rhs) < tol:
                    break
                # decide side using sign of (lhs - rhs)
                if (lhs - rhs) > 0.0:
                    flo = f
                else:
                    fhi = f
        
        # dynamic (velocity) pressure, kPa
        q_kPa = 0.5 * density * (velocity_m_s ** 2) / 1000.0
    
        # 1) straight pipe only
        dp_pipe_kPa = f * (L / ID_m) * q_kPa
        
        dp_plf_kPa = q_kPa * PLF
    
        required_cols = ["SRB", "LRB", "BALL", "GLOBE"]
        missing = [c for c in required_cols if c not in selected_pipe_row.index]
        if missing:
            st.error(f"CSV missing required K columns: {missing}")
            st.stop()
    
        # Convert to floats and check NaNs
        try:
            K_SRB  = float(selected_pipe_row["SRB"])
            K_LRB  = float(selected_pipe_row["LRB"])
            K_BALL = float(selected_pipe_row["BALL"])
            K_GLOBE= float(selected_pipe_row["GLOBE"])
        except Exception as e:
            st.error(f"Failed to parse K-factors as numbers: {e}")
            st.stop()
    
        if any(pd.isna([K_SRB, K_LRB, K_BALL, K_GLOBE])):
            st.error("One or more K-factors are NaN in the CSV row.")
            st.stop()
        
        B_SRB = SRB + 0.5 * _45 + 2.0 * ubend + 3.0 * ptrap
        B_LRB = LRB + MAC
    
        dp_fittings_kPa = q_kPa * (
        K_SRB   * B_SRB +
        K_LRB   * B_LRB
        )

        dp_valves_kPa = q_kPa * (
        K_BALL  * ball +
        K_GLOBE * globe
        )
        
        dp_total_kPa = dp_pipe_kPa + dp_fittings_kPa + dp_valves_kPa + dp_plf_kPa
        
        converter = PressureTemperatureConverter()
        condpres = converter.temp_to_pressure(refrigerant, T_cond)
        postcirc = condpres - (dp_total_kPa / 100)
        postcirctemp = converter.pressure_to_temp(refrigerant, postcirc)
        
        dt = T_cond - postcirctemp

        head = 9.80665 * risem * density / 1000
        
        dp_withhead = dp_total_kPa + head

        postall = condpres - (dp_withhead / 100)
        postalltemp = converter.pressure_to_temp(refrigerant, postall)
        
        tall = T_cond - postalltemp

        exsub = T_cond - T_liq

        addsub = max(tall - exsub, 0)

        evappres = converter.temp_to_pressure(refrigerant, T_evap)

        volflow = mass_flow_kg_s / density

        compratio = condpres / evappres
        
        st.subheader("Results")
    
        if velocity_m_s:
            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
            with col1:
                st.metric("Refrigerant Velocity", f"{velocity_m_s:.2f}m/s")
    
            with col2:
                st.metric("Liquid Density", f"{density:.1f}kg/m³")
    
            with col3:
                st.metric("Pressure Drop", f"{dp_total_kPa:.2f}kPa")
    
            with col4:
                st.metric("Temp Penalty", f"{dt:.2f}K")

            with col5:
                st.metric("Additional Subcooling Required", f"{addsub:.2f}K")

            with col6:
                st.metric("Evaporating Pressure", f"{evappres:.2f}bar(a)")

            with col7:
                st.metric("Condensing Pressure", f"{condpres:.2f}bar(a)")

            # correcting default values between cond, max liq, and min liq between liquid calcs and dry suction calcs
            
            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
            with col1:
                st.metric("Mass Flow Rate", f"{mass_flow_kg_s:.5f}kg/s")
    
            with col2:
                st.metric("Volumetric Flow Rate", f"{volflow:.5f}m³/s")
    
            with col3:
                st.metric("Pipe PD", f"{dp_pipe_kPa:.2f}kPa")
    
            with col4:
                st.metric("Fittings PD", f"{dp_fittings_kPa:.2f}kPa")

            with col5:
                st.metric("Valves PD", f"{dp_valves_kPa:.2f}kPa")

            with col6:
                st.metric("Velocity Pressure PD", f"{dp_plf_kPa:.2f}kPa")

            with col7:
                st.metric("Compression Ratio", f"{compratio:.2f}")
