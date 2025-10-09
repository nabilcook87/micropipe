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
    from utils.refrigerant_viscosities import RefrigerantViscosities
    from utils.pipe_length_volume_calc import get_pipe_id_mm
    from utils.oil_return_checker import check_oil_return

    T_evap = evaporating_temp
    T_cond = condensing_temp

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
        area_m2 = 3.1416 * (ID_m / 2) ** 2
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

        if refrigerant == "R744": MOR_correctionmin = (0.000225755013421421 * minliq_temp) - 0.00280879370374927
        elif refrigerant == "R407A": MOR_correctionmin = (0.00000414431651323856 * (minliq_temp ** 2)) + (0.000381908525139781 * minliq_temp) - 0.0163450053041212
        elif refrigerant == "R449A": MOR_correctionmin = (0.00000414431651323856 * (minliq_temp ** 2)) + (0.000381908525139781 * minliq_temp) - 0.0163450053041212
        elif refrigerant == "R448A": MOR_correctionmin = (0.00000414431651323856 * (minliq_temp ** 2)) + (0.000381908525139781 * minliq_temp) - 0.0163450053041212
        elif refrigerant == "R502": MOR_correctionmin = (0.00000414431651323856 * (minliq_temp ** 2)) + (0.000381908525139781 * minliq_temp) - 0.0163450053041212
        elif refrigerant == "R507A": MOR_correctionmin = (0.000302619054048837 * minliq_temp) - 0.00930188913363997
        elif refrigerant == "R22": MOR_correctionmin = (0.000108153843367715 * minliq_temp) - 0.00329248681202757
        elif refrigerant == "R407C": MOR_correctionmin = (0.00000420322918839302 * (max(minliq_temp, -32.0716410083429) ** 2)) + (0.000269608915211859 * max(minliq_temp, -32.0716410083429)) - 0.0134546663857195
        elif refrigerant == "R410A": MOR_correctionmin = 0
        elif refrigerant == "R407F": MOR_correctionmin = (0.00000347332380289385 * (max(minliq_temp, -34.4346433150568) ** 2)) + (0.000239205332540693 * max(minliq_temp, -34.4346433150568)) - 0.0121545316131988
        elif refrigerant == "R134a": MOR_correctionmin = (0.000195224660107459 * minliq_temp) - 0.00591757011487048
        elif refrigerant == "R404A": MOR_correctionmin = (0.0000156507169104918 * (max(minliq_temp, -22.031637377024) ** 2)) + (0.000689621839324826 * max(minliq_temp, -22.031637377024)) - 0.0392
        else: MOR_correctionmin = (0.00000461020482461793 * (max(minliq_temp, -23.6334996273983) ** 2)) + (0.000217910548009675 * max(minliq_temp, -23.6334996273983)) - 0.012074621594626
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
    
    st.subheader("Results")

    MinCap = MORfinal * evap_capacity_kw / 100
    
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

    mode = st.radio("", ["Dry Suction", "Liquid", "Discharge", "Pumped Liquid", "Wet Suction"], index=1, horizontal=True, label_visibility="collapsed")
    
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
        T_cond = condensing_temp
    
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
            area_m2 = 3.1416 * (ID_m / 2) ** 2
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
    
            if refrigerant == "R744": MOR_correctionmin = (0.000225755013421421 * minliq_temp) - 0.00280879370374927
            elif refrigerant == "R407A": MOR_correctionmin = (0.00000414431651323856 * (minliq_temp ** 2)) + (0.000381908525139781 * minliq_temp) - 0.0163450053041212
            elif refrigerant == "R449A": MOR_correctionmin = (0.00000414431651323856 * (minliq_temp ** 2)) + (0.000381908525139781 * minliq_temp) - 0.0163450053041212
            elif refrigerant == "R448A": MOR_correctionmin = (0.00000414431651323856 * (minliq_temp ** 2)) + (0.000381908525139781 * minliq_temp) - 0.0163450053041212
            elif refrigerant == "R502": MOR_correctionmin = (0.00000414431651323856 * (minliq_temp ** 2)) + (0.000381908525139781 * minliq_temp) - 0.0163450053041212
            elif refrigerant == "R507A": MOR_correctionmin = (0.000302619054048837 * minliq_temp) - 0.00930188913363997
            elif refrigerant == "R22": MOR_correctionmin = (0.000108153843367715 * minliq_temp) - 0.00329248681202757
            elif refrigerant == "R407C": MOR_correctionmin = (0.00000420322918839302 * (max(minliq_temp, -32.0716410083429) ** 2)) + (0.000269608915211859 * max(minliq_temp, -32.0716410083429)) - 0.0134546663857195
            elif refrigerant == "R410A": MOR_correctionmin = 0
            elif refrigerant == "R407F": MOR_correctionmin = (0.00000347332380289385 * (max(minliq_temp, -34.4346433150568) ** 2)) + (0.000239205332540693 * max(minliq_temp, -34.4346433150568)) - 0.0121545316131988
            elif refrigerant == "R134a": MOR_correctionmin = (0.000195224660107459 * minliq_temp) - 0.00591757011487048
            elif refrigerant == "R404A": MOR_correctionmin = (0.0000156507169104918 * (max(minliq_temp, -22.031637377024) ** 2)) + (0.000689621839324826 * max(minliq_temp, -22.031637377024)) - 0.0392
            else: MOR_correctionmin = (0.00000461020482461793 * (max(minliq_temp, -23.6334996273983) ** 2)) + (0.000217910548009675 * max(minliq_temp, -23.6334996273983)) - 0.012074621594626
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
            eps = 0.00015
        else:
            eps = 0.000005
        
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

        MinCap = MORfinal * evap_capacity_kw / 100
        
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
                cond_min, cond_max, cond_default = -100.0, 10.0, -30.0
                minliq_min, minliq_max, minliq_default = -100.0, 10.0, -40.0
            elif refrigerant == "R744":
                evap_min, evap_max, evap_default = -50.0, 20.0, -10.0
                cond_min, cond_max, cond_default = -23.0, 30.0, 15.0
                minliq_min, minliq_max, minliq_default = -50.0, 30.0, 10.0
            else:
                evap_min, evap_max, evap_default = -50.0, 30.0, -10.0
                cond_min, cond_max, cond_default = -23.0, 60.0, 43.0
                minliq_min, minliq_max, minliq_default = -50.0, 60.0, 40.0
    
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
                "Condensing Temperature (°C)",
                min_value=cond_min, max_value=cond_max,
                value=ss.cond_temp, step=1.0, key="cond_temp",
                on_change=on_change_cond,
            )
    
            minliq_temp = st.number_input(
                "Liquid Temperature (°C)",
                min_value=minliq_min, max_value=min(condensing_temp, minliq_max),
                value=ss.minliq_temp, step=1.0, key="minliq_temp",
                on_change=on_change_minliq,
            )

        with col2:
            
            evaporating_temp = st.number_input(
                "Evaporating Temperature (°C)",
                min_value=evap_min, max_value=min(minliq_temp, evap_max),
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
        T_liq = minliq_temp
        T_cond = condensing_temp
    
        props = RefrigerantProperties()
        
        h_in = props.get_properties(refrigerant, T_liq)["enthalpy_liquid2"]

        h_evap = props.get_properties(refrigerant, T_evap)["enthalpy_vapor"]
        
        delta_h = h_evap - h_in

        mass_flow_kg_s = evap_capacity_kw / delta_h if delta_h > 0 else 0.01
    
        if ID_mm is not None:
            ID_m = ID_mm / 1000.0

            area_m2 = 3.1416 * (ID_m / 2) ** 2

            density = RefrigerantProperties().get_properties(refrigerant, T_liq)["density_liquid2"]

            velocity_m_s = mass_flow_kg_s / (area_m2 * density)

        else:
            velocity_m_s = None

        viscosity = RefrigerantProperties().get_properties(refrigerant, T_liq)["viscosity_liquid"]
    
        reynolds = (density * velocity_m_s * ID_m) / (viscosity / 1000000)
    
        if selected_material in ["Steel SCH40", "Steel SCH80"]:
            eps = 0.00015
        else:
            eps = 0.000005
        
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
