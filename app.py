import streamlit as st
from utils.network_builder import NetworkBuilder
from utils.pressure_temp_converter import PressureTemperatureConverter
from utils.system_pressure_checker import check_pipe_rating, _pipe_rating_data
import pandas as pd
import io

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
    pipe_sizes = sorted(_pipe_rating_data['Pipe Nominal Size'].unique())
    selected_size = st.selectbox("Select Pipe Nominal Size", pipe_sizes)

    # Filter rows for selected pipe size
    matching_pipes = _pipe_rating_data[_pipe_rating_data['Pipe Nominal Size'] == selected_size]

    if len(matching_pipes) == 0:
        st.warning("No pipe data available for selected size.")
        return

    # Let user choose gauge if multiple gauges exist for this size
    gauges = matching_pipes['Gauge'].unique()
    selected_gauge = st.selectbox("Select Copper Gauge", gauges)

    # Choose temperature for rating lookup (with interpolation step)
    all_temps = [int(col[:-1]) for col in _pipe_rating_data.columns if col.endswith("C") and col[:-1].isdigit()]
    design_temp_C = st.slider("Design Temperature (°C)", min_value=min(all_temps), max_value=max(all_temps), value=50)

    # Get matching row
    pipe_row = matching_pipes[matching_pipes['Gauge'] == selected_gauge].iloc[0]

    # Input design pressure
    design_pressure_bar = st.number_input("Design Pressure (bar)", min_value=0.0, step=0.5, value=10.0)

    # Interpolate pressure rating
    temp_cols = [col for col in pipe_row.index if col.endswith("C") and col[:-1].isdigit()]
    temp_values = [int(col[:-1]) for col in temp_cols]
    rating_values = [pipe_row[col] for col in temp_cols]
    rated_pressure = pd.Series(rating_values, index=temp_values).sort_index().interpolate(method='linear').reindex(range(min(temp_values), max(temp_values)+1)).interpolate().get(design_temp_C, None)

    # Check rating
    is_rated = rated_pressure * 0.9 >= design_pressure_bar if rated_pressure else False

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Pipe Rating Summary")
        st.metric("Rated Pressure @ Temp", f"{rated_pressure:.2f} bar" if rated_pressure else "N/A")
        st.metric("Design Pressure", f"{design_pressure_bar:.2f} bar")

    with col2:
        st.subheader("Result")
        if is_rated:
            st.success("✅ Pipe is rated for this pressure.")
        else:
            st.error("❌ Pipe is NOT rated for this pressure.")

    # Show full data row for transparency
    with st.expander("Show Full Pipe Data"):
        st.dataframe(pipe_row.to_frame().T.style.highlight_max(axis=1))

    # Add a line chart for Rated Pressure vs. Temperature with design pressure overlay
    with st.expander("Rated Pressure vs. Temperature Chart"):
        chart_data = pd.DataFrame({
            "Temperature (C)": range(min(temp_values), max(temp_values)+1),
            "Rated Pressure (bar)": pd.Series(rating_values, index=temp_values).sort_index().interpolate(method='linear').reindex(range(min(temp_values), max(temp_values)+1)).interpolate().values
        })
        chart_data["Design Pressure (bar)"] = design_pressure_bar
        st.line_chart(chart_data.set_index("Temperature (C)"))

    # Add CSV export
    with st.expander("Export Pressure Data"):
        csv = chart_data.to_csv(index=False)
        st.download_button(
            label="Download Pressure Data as CSV",
            data=csv,
            file_name="pressure_rating_vs_temperature.csv",
            mime="text/csv"
        )

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
