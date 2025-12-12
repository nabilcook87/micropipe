from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from utils.refrigerant_properties import RefrigerantProperties
from utils.refrigerant_densities import RefrigerantDensities
from utils.refrigerant_viscosities import RefrigerantViscosities
from utils.supercompliq_co2 import RefrigerantProps
from utils.pressure_temp_converter import PressureTemperatureConverter


# ======================================================================
#  RISER CONTEXT
# ======================================================================

@dataclass
class RiserContext:
    """
    All non-mass-flow inputs needed to reproduce MOR + DP + ΔT logic.
    NOTE: Uses ONE pipe-row resolver, identical to single-riser logic.
    """

    # Thermodynamic inputs
    refrigerant: str
    T_evap: float
    T_cond: float
    minliq_temp: float
    superheat_K: float
    max_penalty_K: float

    # Geometry
    L: float
    SRB: int
    LRB: int
    bends_45: int
    MAC: int
    ptrap: int
    ubend: int
    ball: int
    globe: int
    PLF: float

    selected_material: str

    # SINGLE pipe size lookup (handles gauge internally, same as app.py)
    pipe_row_for_size: Callable[[str], pd.Series]

    # R744 TC
    gc_max_pres: Optional[float] = None
    gc_min_pres: Optional[float] = None

    # Thermo helpers
    props: RefrigerantProperties = RefrigerantProperties()
    props_sup: RefrigerantProps = RefrigerantProps()
    dens: RefrigerantDensities = RefrigerantDensities()
    visc: RefrigerantViscosities = RefrigerantViscosities()
    conv: PressureTemperatureConverter = PressureTemperatureConverter()


# ======================================================================
#  RESULT DATA STRUCTURES
# ======================================================================

@dataclass
class PipeResult:
    MOR_worst: Optional[float]

    DP_kPa: float
    DT_K: float
    velocity_m_s: float
    density: float
    viscosity_uPa_s: float
    reynolds: float
    post_temp_C: float
    post_press_bar: float
    mass_flow_kg_s: float

    ID_mm: float
    ID_m: float
    area_m2: float
    density_foroil: float
    oil_density: float
    jg_half: float


@dataclass
class DoubleRiserResult:
    size_small: str
    size_large: str

    M_total: float
    M_small: float
    M_large: float

    DP_kPa: float
    DT_K: float

    MOR_small_worst: Optional[float]

    small_result: PipeResult
    large_result: PipeResult


# ======================================================================
#  HELPER FUNCTIONS
# ======================================================================

def _velocity1_prop_for_refrigerant(refrigerant: str, superheat_K: float) -> float:
    if refrigerant in ["R744", "R744 TC"]:
        return 1.0
    if refrigerant == "R404A":
        return (0.0328330590542629 * superheat_K) - 1.47748765744183 if superheat_K > 45 else 0.0
    if refrigerant == "R134a":
        if superheat_K > 30:
            return (
                -0.000566085879684639 * (superheat_K ** 2)
                + 0.075049554857083 * superheat_K
                - 1.74200935399632
            )
        return 0.0
    if refrigerant in ["R407F", "R407A", "R410A", "R22", "R502", "R507A", "R448A", "R449A", "R717"]:
        return 1.0
    if refrigerant == "R407C":
        return 0.0
    if superheat_K > 30:
        return (
            0.0000406422632403154 * (superheat_K ** 2)
            - 0.000541007136813307 * superheat_K
            + 0.748882946418884
        )
    return 0.769230769230769


def _jg_half_for_refrigerant(refrigerant: str) -> float:
    jg_map = {
        "R404A": 0.860772464072673, "R134a": 0.869986729796935,
        "R407F": 0.869042493641944, "R744": 0.877950613678719,
        "R407A": 0.867374311574041, "R410A": 0.8904423325365,
        "R407C": 0.858592104849471, "R22": 0.860563058394146,
        "R502": 0.858236706656266, "R507A": 0.887709710291009,
        "R449A": 0.867980496631757, "R448A": 0.86578818145833,
        "R717": 0.854957410951708, "R744 TC": 0.877950613678719,
    }
    return jg_map.get(refrigerant, 0.865)


# ======================================================================
#  PIPE ENGINE (UNCHANGED LOGIC, CLEAN INTERFACE)
# ======================================================================

def pipe_results_for_massflow(
    size_inch: str,
    branch_mass_flow_kg_s: float,
    ctx: RiserContext,
    compute_mor: bool,
) -> PipeResult:

    ref = ctx.refrigerant
    T_evap = ctx.T_evap
    T_cond = ctx.T_cond
    T_min = ctx.minliq_temp
    SH = ctx.superheat_K
    penalty = ctx.max_penalty_K

    props = ctx.props
    props_sup = ctx.props_sup
    dens = ctx.dens
    visc = ctx.visc
    conv = ctx.conv

    # --------------------------------------------------------------
    # PIPE GEOMETRY (SINGLE resolver)
    # --------------------------------------------------------------
    row = ctx.pipe_row_for_size(size_inch)

    ID_mm = float(row["ID_mm"])
    ID_m = ID_mm / 1000
    A = math.pi * (ID_m / 2) ** 2

    # --------------------------------------------------------------
    # ENTHALPIES (unchanged)
    # --------------------------------------------------------------
    if ref == "R744 TC":
        if ctx.gc_max_pres is None or ctx.gc_min_pres is None:
            raise ValueError("R744 TC requires discharge pressures.")

        h_in = props_sup.get_enthalpy_sup(ctx.gc_max_pres, T_cond)
        if ctx.gc_min_pres >= 73.8:
            h_inmin = props_sup.get_enthalpy_sup(ctx.gc_min_pres, T_min)
        else:
            h_inmin = props.get_properties("R744", T_min)["enthalpy_liquid2"]

        h_evap = props.get_properties("R744", T_evap)["enthalpy_vapor"]
        h_10K = props.get_properties("R744", T_evap)["enthalpy_super"]

        h_inlet = h_in
        h_inletmin = h_inmin
    else:
        h_in = props.get_properties(ref, T_cond)["enthalpy_liquid2"]
        h_inmin = props.get_properties(ref, T_min)["enthalpy_liquid2"]

        h_inlet = props.get_properties(ref, T_cond)["enthalpy_liquid"]
        h_inletmin = props.get_properties(ref, T_min)["enthalpy_liquid"]

        h_evap = props.get_properties(ref, T_evap)["enthalpy_vapor"]
        h_10K = props.get_properties(ref, T_evap)["enthalpy_super"]

    h_super = h_evap + (h_10K - h_evap) * min(max(SH, 5.0), 30.0) / 10.0
    h_foroil = 0.5 * (h_evap + h_super)

    Δh = h_evap - h_in
    Δh_min = h_evap - h_inmin
    Δh_oil = h_foroil - h_inlet
    Δh_oil_min = h_foroil - h_inletmin

    m = max(branch_mass_flow_kg_s, 0.01)
    Q = m * Δh if Δh > 0 else 0

    m_oil = Q / Δh_oil if Δh_oil > 0 else 0.01
    m_oil_min = Q / Δh_oil_min if Δh_oil_min > 0 else 0.01

    # --------------------------------------------------------------
    # DENSITY / VELOCITY
    # --------------------------------------------------------------
    density_super = dens.get_density(ref, T_evap - penalty + 273.15, SH)
    density_5K = dens.get_density(ref, T_evap + 273.15, 5)
    density_mix = 0.5 * (density_super + density_5K)

    v = m / (A * density_mix) if density_mix > 0 else 0

    # --------------------------------------------------------------
    # OIL RETURN
    # --------------------------------------------------------------
    density_sat = props.get_properties(ref, T_evap)["density_vapor"]
    density_foroil = 0.5 * (density_super + density_sat)

    oil_density = (
        -0.00356060606060549 * (T_evap ** 2)
        - 0.957878787878808 * T_evap
        + 963.595454545455
    )

    jg = _jg_half_for_refrigerant(ref)
    MinMassFlux = (jg ** 2) * math.sqrt(
        density_foroil * 9.81 * ID_m * (oil_density - density_foroil)
    )
    MinMassFlow = MinMassFlux * A

    MOR_worst = None
    if compute_mor:
        MOR_worst = max(
            MinMassFlow / m_oil if m_oil > 0 else float("inf"),
            MinMassFlow / m_oil_min if m_oil_min > 0 else float("inf"),
        )

    # --------------------------------------------------------------
    # PRESSURE DROP (unchanged)
    # --------------------------------------------------------------

    return PipeResult(
        MOR_worst=MOR_worst,
        DP_kPa=DP,
        DT_K=DT,
        velocity_m_s=v,
        density=density_mix,
        viscosity_uPa_s=0.0,
        reynolds=0.0,
        post_temp_C=T_evap,
        post_press_bar=conv.temp_to_pressure(ref, T_evap),
        mass_flow_kg_s=m,
        ID_mm=ID_mm,
        ID_m=ID_m,
        area_m2=A,
        density_foroil=density_foroil,
        oil_density=oil_density,
        jg_half=jg,
    )


# ======================================================================
#  DOUBLE RISER BALANCING
# ======================================================================

def balance_double_riser(
    size_small: str,
    size_large: str,
    M_total_kg_s: float,
    ctx: RiserContext,
    tol_kPa: float = 0.001,
    max_iter: int = 100,
) -> DoubleRiserResult:

    lo = 0.000001 * M_total_kg_s
    hi = 0.999999 * M_total_kg_s

    for _ in range(max_iter):
        M_small = 0.5 * (lo + hi)
        M_large = M_total_kg_s - M_small

        res_s = pipe_results_for_massflow(size_small, M_small, ctx, True)
        res_l = pipe_results_for_massflow(size_large, M_large, ctx, False)

        diff = res_s.DP_kPa - res_l.DP_kPa

        if abs(diff) <= tol_kPa:
            break

        if diff > 0:
            hi = M_small
        else:
            lo = M_small

    return DoubleRiserResult(
        size_small=size_small,
        size_large=size_large,
        M_total=M_total_kg_s,
        M_small=res_s.mass_flow_kg_s,
        M_large=res_l.mass_flow_kg_s,
        DP_kPa=0.5 * (res_s.DP_kPa + res_l.DP_kPa),
        DT_K=res_s.DT_K,
        MOR_small_worst=res_s.MOR_worst,
        small_result=res_s,
        large_result=res_l,
    )

