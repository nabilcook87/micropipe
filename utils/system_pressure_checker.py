
from dataclasses import dataclass
from typing import Optional
import math

COPPER_WALL_TOL = 0.9
MILD_STEEL_WALL_TOL = 0.875
STAINLESS_WALL_TOL = 0.85
ALUMINIUM_WALL_TOL = 0.9

@dataclass(frozen=True)
class Stress:
    value: float
    unit: str  # "MPa" or "psi"

@dataclass(frozen=True)
class WallThickness:
    mm: float
    inch: float

COPPER_GAUGE_WALL_IN = {
    22: 0.028,
    21: 0.032,
    20: 0.036,
    19: 0.040,
    18: 0.048,
    16: 0.064,
    14: 0.080,
    12: 0.104,
}

def k65_wall_tolerance(od_mm: float, wall_mm_nom: float) -> float:
    if od_mm < 18 and wall_mm_nom < 1:
        return 0.9
    if od_mm < 18 and wall_mm_nom >= 1:
        return 0.87
    if od_mm >= 18 and wall_mm_nom < 1:
        return 0.9
    return 0.85

def steel_pipe_stress_psi(temp_c: float) -> float:
    """
    VB: PipeStress(T°F)
    Polynomial valid above 100°F minimum
    """
    temp_f = max(temp_c * 9.0 / 5.0 + 32.0, 100.0)

    return (
        20500
        - 12.3 * temp_f
        + 0.0021 * temp_f**2
    )

def aluminium_pipe_stress_mpa(temp_c: float) -> float:

    temp_f = temp_c * 9.0 / 5.0 + 32.0

    psi = (
        24000
        - 15.0 * temp_f
        + 0.003 * temp_f**2
    )

    return (psi / 1000.0) * 6.895  # psi → MPa

def k65_yield_strength_mpa(temp_f: float) -> float:
    # VB: T2 = (T - 32) / 1.8
    T2 = (temp_f - 32.0) / 1.8

    A0 = 153.411968466317
    A1 = -0.164870520783605
    A2 = -5.02591973244193e-04
    A3 = 1.14870520783601e-05
    A4 = -3.386048733876e-08

    return A0 + (A1 * T2) + (A2 * T2**2) + (A3 * T2**3) + (A4 * T2**4)

def allowable_stress(
    *,
    pipe_index: int,
    circuit: str,
    copper_calc: Optional[str],
    temp_c: float,
) -> Stress:

    if pipe_index == 1:
        if copper_calc == "BS1306":
            value = 34 if circuit == "Discharge" else 41
        else:  # DKI
            value = 180 if circuit == "Discharge" else 194
        return Stress(value=value, unit="MPa")

    if pipe_index == 6:
        temp_f = max(temp_c * 9.0 / 5.0 + 32.0, 100.0)
        return Stress(
            value=pipe_stress_psi(temp_f),
            unit="psi",
        )

    if pipe_index == 7:
        return Stress(
            value=aluminium_pipe_stress_mpa(temp_c),
            unit="MPa",
        )

    if pipe_index == 8:
        return Stress(
            value=k65_yield_strength_mpa(temp_c) / 1.5,
            unit="MPa",
        )

    if pipe_index in (2, 5):  # steel
        return Stress(value=15000.0, unit="psi")

    if pipe_index in (3, 4):  # stainless
        return Stress(value=70000.0, unit="psi")

    raise ValueError(f"Unsupported pipe index: {pipe_index}")

def calc_wall_thickness(
    *,
    pipe_index: int,
    od_mm: float,
    id_mm: Optional[float] = None,
    gauge: Optional[int] = None,
) -> WallThickness:

    if pipe_index == 1:
        if gauge not in COPPER_GAUGE_WALL_IN:
            raise ValueError("Invalid gauge for EN12735 copper")

        t_in = COPPER_GAUGE_WALL_IN[gauge] * COPPER_WALL_TOL
        t_mm = t_in * 25.4

        return WallThickness(mm=t_mm, inch=t_in)

    if id_mm is None:
        raise ValueError("ID must be provided for non-gauge pipes")

    t_mm = (od_mm - id_mm) / 2.0

    # Apply tolerances
    if pipe_index in (2, 5):  # steel
        t_mm *= MILD_STEEL_WALL_TOL
    elif pipe_index in (3, 4):  # stainless
        t_mm *= STAINLESS_WALL_TOL
    elif pipe_index == 7:  # aluminium
        t_mm *= ALUMINIUM_WALL_TOL
    elif pipe_index == 8:  # K65 copper
        wall_mm_nom = (od_mm - id_mm) / 2.0
        tol = k65_wall_tolerance(od_mm, wall_mm_nom)
        t_mm = wall_mm_nom * tol

    t_in = t_mm / 25.4

    return WallThickness(mm=t_mm, inch=t_in)

def calc_mwp(
    *,
    pipe_index: int,
    stress: Stress,
    wall: WallThickness,
    od_mm: float,
    id_mm: float | None,
    mwp_temp_c: float,
    copper_calc: Optional[str],
) -> float:
    PSI_TO_BAR = 0.0689476

    # Helpers
    def _od_in() -> float:
        return od_mm / 25.4

    def _nom_wall_in() -> float:
        if id_mm is None:
            raise ValueError("This pipe type requires id_mm.")
        return (_od_in() - (id_mm / 25.4)) / 2.0

    if pipe_index == 6:
        wall_in = _nom_wall_in() * COPPER_WALL_TOL

        temp_f = mwp_temp_c * 9.0 / 5.0 + 32.0
        if temp_f < 100.0:
            temp_f = 100.0

        stress_psi = pipe_stress_psi(temp_f)

        mwp_psi = (2.0 * stress_psi * wall_in) / (_od_in() - 0.8 * wall_in)
        return mwp_psi * PSI_TO_BAR

    if pipe_index in (2, 5):
        deduction = 0.025 if od_mm <= 61 else 0.065

        wall_in_nom = _nom_wall_in()
        wall_eff = (wall_in_nom * MILD_STEEL_WALL_TOL) - deduction

        mwp_psi = (2.0 * 15000.0 * wall_eff) / _od_in()
        return mwp_psi * PSI_TO_BAR

    if pipe_index in (3, 4):
        wall_in_nom = _nom_wall_in()
        mwp_psi = ((wall_in_nom * 2.0 * 70000.0 * STAINLESS_WALL_TOL) / _od_in()) / 4.0 * 0.7
        return mwp_psi * PSI_TO_BAR

    if pipe_index == 8:
        temp_f = mwp_temp_c * 9.0 / 5.0 + 32.0
        ys_mpa = k65_yield_strength_mpa(temp_f)
    
        wall_mm = wall.mm  # already tol-adjusted
        od = od_mm
    
        presscalc = 1 if (copper_calc == "BS1306") else 2
    
        if presscalc == 1:
            return (20.0 * ys_mpa * wall_mm) / ((od - wall_mm) * 1.5)
        else:
            return ((20.0 * ys_mpa * wall_mm) / (od - wall_mm)) * 1.5

    if stress.unit == "MPa":
        mwp_bar = (20.0 * stress.value * wall.mm) / (od_mm - wall.mm)
    elif stress.unit == "psi":
        mwp_psi = (20.0 * stress.value * wall.inch) / (_od_in() - wall.inch)
        mwp_bar = mwp_psi * PSI_TO_BAR
    else:
        raise ValueError(f"Unsupported stress unit: {stress.unit}")

    if copper_calc == "DKI" and pipe_index == 1:
        mwp_bar /= 3.5

    return mwp_bar

from utils.refrigerant_properties import RefrigerantProperties

def calc_design_pressure_bar_g(
    *,
    refrigerant: str,
    design_temp_c: float,
    circuit: str,
    r744_tc_pressure_bar_g: float | None = None,
) -> float:

    # CO₂ transcritical override
    if refrigerant.upper() in ("R744", "CO2"):
        if r744_tc_pressure_bar_g is None:
            raise ValueError("R744 transcritical design pressure must be provided")
        return r744_tc_pressure_bar_g

    props = RefrigerantProperties()
    data = props.get_properties(refrigerant, design_temp_c)

    # VB logic:
    # Liquid / Pumped → bubble point
    # Suction / Discharge → dew point
    if circuit in ("Liquid", "Pumped"):
        p_abs = data["pressure_bar2"]   # bubble
    else:
        p_abs = data["pressure_bar"]    # dew

    # Convert abs → gauge
    return p_abs - 1.0

def calc_pressure_limits(
    *,
    design_pressure_bar_g: float,
) -> dict[str, float]:

    return {
        "design": design_pressure_bar_g,
        "leak_test": design_pressure_bar_g,
        "pressure_test": 1.3 * design_pressure_bar_g,
        "relief_setting": design_pressure_bar_g,
        "rated_discharge": 1.1 * design_pressure_bar_g,
    }

def system_pressure_check(
    *,
    refrigerant: str,
    design_temp_c: float,
    mwp_temp_c: float,        # ← NEW
    circuit: str,
    pipe_index: int,
    od_mm: float,
    id_mm: float | None = None,
    gauge: int | None = None,
    copper_calc: str | None = None,
    r744_tc_pressure_bar_g: float | None = None,
) -> dict:

    design_pressure = calc_design_pressure_bar_g(
        refrigerant=refrigerant,
        design_temp_c=design_temp_c,
        circuit=circuit,
        r744_tc_pressure_bar_g=r744_tc_pressure_bar_g,
    )

    pressure_limits = calc_pressure_limits(
        design_pressure_bar_g=design_pressure
    )

    stress = allowable_stress(
        pipe_index=pipe_index,
        circuit=circuit,
        copper_calc=copper_calc,
        temp_c=design_temp_c,
    )

    wall = calc_wall_thickness(
        pipe_index=pipe_index,
        od_mm=od_mm,
        id_mm=id_mm,
        gauge=gauge,
    )

    mwp = calc_mwp(
        pipe_index=pipe_index,
        stress=stress,
        wall=wall,
        od_mm=od_mm,
        id_mm=id_mm,
        mwp_temp_c=mwp_temp_c,   # ← pass separately
        copper_calc=copper_calc,
    )

    passes = mwp >= design_pressure

    return {
        "design_pressure_bar_g": design_pressure,
        "pressure_limits_bar": pressure_limits,
        "allowable_stress": stress,
        "wall_thickness": wall,
        "mwp_bar": mwp,
        "pass": passes,
        "margin_bar": mwp - design_pressure,
    }

def pipe_stress_psi(temp_f: float) -> float:
    T2 = temp_f
    A0 = 37600.0274576506
    A1 = -878.367490116384
    A2 = 9.83034307114902
    A3 = -5.78667251130062E-02
    A4 = 1.87333522081964E-04
    A5 = -3.14666979085113E-07
    A6 = 2.13333541253137E-10
    return A0 + (A1 * T2) + (A2 * T2**2) + (A3 * T2**3) + (A4 * T2**4) + (A5 * T2**5) + (A6 * T2**6)
