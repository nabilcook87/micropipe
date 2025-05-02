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
