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


@dataclass
class RiserContext:
    """
    All non-mass-flow inputs needed to reproduce your MOR + DP + ΔT logic.
    """
    refrigerant: str
    T_evap: float          # °C
    T_cond: float          # Max liquid temp °C (or GC out for CO2 TC)
    minliq_temp: float     # Min liquid temp °C
    superheat_K: float
    max_penalty_K: float   # Allowed ΔT penalty

    # Geometry / fittings for THIS riser
    L: float               # Pipe length (m)
    SRB: int
    LRB: int
    bends_45: int
    MAC: int
    ptrap: int
    ubend: int
    ball: int
    globe: int
    PLF: float

    # Pipe material info
    selected_material: str

    # Function to get CSV row for pipe size
    pipe_row_for_size: Callable[[str], pd.Series]

    gc_max_pres: Optional[float] = None  # bar(a) — R744 TC only
    gc_min_pres: Optional[float] = None  # bar(a) — R744 TC only

    # Property helpers (may be shared singletons)
    props: RefrigerantProperties = RefrigerantProperties()
    props_sup: RefrigerantProps = RefrigerantProps()
    dens: RefrigerantDensities = RefrigerantDensities()
    visc: RefrigerantViscosities = RefrigerantViscosities()
    conv: PressureTemperatureConverter = PressureTemperatureConverter()


@dataclass
class PipeResult:
    """
    Result for a single branch (one pipe size, one branch mass flow).
    Includes MOR at max/min liquid conditions and overall best/worst.
    """
    MOR_worst: float
    MOR_best: float
    MOR_maxliq: float
    MOR_minliq: float
    DP_kPa: float
    DT_K: float
    velocity_m_s: float
    density: float
    viscosity_uPa_s: float
    reynolds: float
    post_temp_C: float
    post_press_bar: float
    mass_flow_kg_s: float


@dataclass
class DoubleRiserResult:
    """
    Balanced double-riser solution for a given pair and total mass flow.
    Contains:
      - per-branch split & PD
      - per-branch MOR metrics
      - system-level worst/best MOR (over all 4 cases, S2 logic)
    """
    size_small: str
    size_large: str
    M_total: float
    M_small: float
    M_large: float
    DP_kPa: float
    DT_K: float

    MOR_small_worst: float
    MOR_small_best: float
    MOR_small_maxliq: float
    MOR_small_minliq: float

    MOR_large_worst: float
    MOR_large_best: float
    MOR_large_maxliq: float
    MOR_large_minliq: float

    MOR_system_worst: float
    MOR_system_best: float

    small_result: PipeResult
    large_result: PipeResult


def _velocity1_prop_for_refrigerant(refrigerant: str, superheat_K: float) -> float:
    """
    EXACT same logic as your main block / get_pipe_results.
    """
    if refrigerant == "R744":
        return 1.0
    elif refrigerant == "R744 TC":
        return 1.0
    elif refrigerant == "R404A":
        if superheat_K > 45:
            return (0.0328330590542629 * superheat_K) - 1.47748765744183
        else:
            return 0.0
    elif refrigerant == "R134a":
        if superheat_K > 30:
            return (-0.000566085879684639 * (superheat_K ** 2)) + (0.075049554857083 * superheat_K) - 1.74200935399632
        else:
            return 0.0
    elif refrigerant in ["R407F", "R407A", "R410A", "R22", "R502", "R507A", "R448A", "R449A", "R717"]:
        return 1.0
    elif refrigerant == "R407C":
        return 0.0
    else:
        if superheat_K > 30:
            return (0.0000406422632403154 * (superheat_K ** 2)) - (0.000541007136813307 * superheat_K) + 0.748882946418884
        else:
            return 0.769230769230769


def _jg_half_for_refrigerant(refrigerant: str) -> float:
    """
    EXACT mapping (you already used this compressed dict in get_pipe_results).
    """
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
        "R23": 0.865673418568001, "R508B": 0.864305626845382, "R744 TC": 0.877950613678719,
    }
    return jg_map.get(refrigerant, 0.865)


def pipe_results_for_massflow(
    size_inch: str,
    branch_mass_flow_kg_s: float,
    ctx: RiserContext,
) -> PipeResult:
    """
    Reproduces your MOR + ΔT + DP + velocity logic for a given pipe size
    and a given *branch* mass flow (not total evaporator duty).

    IMPORTANT:
    - All thermodynamic formulas and refrigerant-specific polynomials are
      kept IDENTICAL to your existing code.
    - The ONLY structural change is that the "load" is inferred from the
      given branch_mass_flow instead of evap_capacity_kw.
    """
    refrigerant = ctx.refrigerant
    T_evap = ctx.T_evap
    T_cond = ctx.T_cond
    minliq_temp = ctx.minliq_temp
    superheat_K = ctx.superheat_K
    max_penalty = ctx.max_penalty_K

    props = ctx.props
    props_sup = ctx.props_sup
    dens = ctx.dens
    visc = ctx.visc
    conv = ctx.conv

    pipe_row = ctx.pipe_row_for_size(size_inch)
    try:
        ID_mm_local = float(pipe_row["ID_mm"])
    except Exception:
        # If for some reason we can't parse, return NaNs
        nan = float("nan")
        return PipeResult(
            MOR_worst=nan,
            MOR_best=nan,
            MOR_maxliq=nan,
            MOR_minliq=nan,
            DP_kPa=nan,
            DT_K=nan,
            velocity_m_s=nan,
            density=nan,
            viscosity_uPa_s=nan,
            reynolds=nan,
            post_temp_C=nan,
            post_press_bar=nan,
            mass_flow_kg_s=branch_mass_flow_kg_s,
        )

    ID_m_local = ID_mm_local / 1000.0
    area_m2_local = math.pi * (ID_m_local / 2.0) ** 2

    # ------------------------------------------------------------------
    # Enthalpies / Δh as in the original code
    # ------------------------------------------------------------------
    if refrigerant == "R744 TC":
        if ctx.gc_max_pres is None or ctx.gc_min_pres is None:
            raise ValueError("R744 TC requires gc_max_pres and gc_min_pres in RiserContext.")

        h_in = props_sup.get_enthalpy_sup(ctx.gc_max_pres, T_cond)
        if ctx.gc_min_pres >= 73.8:
            h_inmin = props_sup.get_enthalpy_sup(ctx.gc_min_pres, minliq_temp)
        elif ctx.gc_min_pres <= 72.13:
            h_inmin = props.get_properties("R744", minliq_temp)["enthalpy_liquid2"]
        else:
            # Was a Streamlit error previously; here we just raise.
            raise ValueError("This pressure range (72.13–73.8 bar) is not allowed for R744 TC.")

        h_inlet = h_in
        h_inletmin = h_inmin
        h_evap = props.get_properties("R744", T_evap)["enthalpy_vapor"]
        h_10K = props.get_properties("R744", T_evap)["enthalpy_super"]
    else:
        h_in = props.get_properties(refrigerant, T_cond)["enthalpy_liquid2"]
        h_inmin = props.get_properties(refrigerant, minliq_temp)["enthalpy_liquid2"]
        h_inlet = props.get_properties(refrigerant, T_cond)["enthalpy_liquid"]
        h_inletmin = props.get_properties(refrigerant, minliq_temp)["enthalpy_liquid"]
        h_evap = props.get_properties(refrigerant, T_evap)["enthalpy_vapor"]
        h_10K = props.get_properties(refrigerant, T_evap)["enthalpy_super"]

    hdiff_10K = h_10K - h_evap
    hdiff_custom = hdiff_10K * min(max(superheat_K, 5.0), 30.0) / 10.0
    h_super = h_evap + hdiff_custom
    h_foroil = (h_evap + h_super) / 2.0

    delta_h = h_evap - h_in
    delta_hmin = h_evap - h_inmin
    delta_h_foroil = h_foroil - h_inlet
    delta_h_foroilmin = h_foroil - h_inletmin

    # ------------------------------------------------------------------
    # Infer "Q" from branch mass flow and delta_h (full-load mapping)
    # ------------------------------------------------------------------
    if delta_h <= 0:
        Q_branch = 0.0
        mass_flow_kg_s = max(branch_mass_flow_kg_s, 0.01)
    else:
        mass_flow_kg_s = max(branch_mass_flow_kg_s, 0.0)
        Q_branch = mass_flow_kg_s * delta_h

    if delta_hmin > 0:
        mass_flow_kg_smin = Q_branch / delta_hmin
    else:
        mass_flow_kg_smin = 0.01

    if delta_h_foroil > 0:
        mass_flow_foroil = Q_branch / delta_h_foroil
    else:
        mass_flow_foroil = 0.01

    if delta_h_foroilmin > 0:
        mass_flow_foroilmin = Q_branch / delta_h_foroilmin
    else:
        mass_flow_foroilmin = 0.01

    # ------------------------------------------------------------------
    # Densities and velocity
    # ------------------------------------------------------------------
    if refrigerant == "R744 TC":
        density_super = dens.get_density("R744", T_evap - max_penalty + 273.15, superheat_K)
        density_super2a = dens.get_density("R744", T_evap + 273.15, ((superheat_K + 5.0) / 2.0))
        density_super2b = dens.get_density("R744", T_evap - max_penalty + 273.15, ((superheat_K + 5.0) / 2.0))
        density_super2 = (density_super2a + density_super2b) / 2.0
        density_super_foroil = dens.get_density("R744", T_evap + 273.15, min(max(superheat_K, 5.0), 30.0))
        density_sat = props.get_properties("R744", T_evap)["density_vapor"]
        density_5K = dens.get_density("R744", T_evap + 273.15, 5.0)
    else:
        density_super = dens.get_density(refrigerant, T_evap - max_penalty + 273.15, superheat_K)
        density_super2a = dens.get_density(refrigerant, T_evap + 273.15, ((superheat_K + 5.0) / 2.0))
        density_super2b = dens.get_density(refrigerant, T_evap - max_penalty + 273.15, ((superheat_K + 5.0) / 2.0))
        density_super2 = (density_super2a + density_super2b) / 2.0
        density_super_foroil = dens.get_density(refrigerant, T_evap + 273.15, min(max(superheat_K, 5.0), 30.0))
        density_sat = props.get_properties(refrigerant, T_evap)["density_vapor"]
        density_5K = dens.get_density(refrigerant, T_evap + 273.15, 5.0)

    density = (density_super + density_5K) / 2.0
    density_foroil = (density_super_foroil + density_sat) / 2.0

    v1 = mass_flow_kg_s / (area_m2_local * density) if density > 0 else 0.0
    v1min = mass_flow_kg_smin / (area_m2_local * density) if density > 0 else 0.0
    v2 = mass_flow_kg_s / (area_m2_local * density_super2) if density_super2 > 0 else 0.0
    v2min = mass_flow_kg_smin / (area_m2_local * density_super2) if density_super2 > 0 else 0.0

    velocity1_prop = _velocity1_prop_for_refrigerant(refrigerant, superheat_K)
    velocity_m_s = (v1 * velocity1_prop) + (v2 * (1.0 - velocity1_prop))
    velocity_m_smin = (v1min * velocity1_prop) + (v2min * (1.0 - velocity1_prop))
    velocity_m_sfinal = max(velocity_m_s, velocity_m_smin)

    # ------------------------------------------------------------------
    # Oil density and MinMassFlux => MOR_pre (maxliq) & MOR_premin (minliq)
    # ------------------------------------------------------------------
    if refrigerant in ["R23", "R508B"]:
        oil_density_sat = (-0.853841209044878 * T_evap) + 999.190772536527
        oil_density_super = (-0.853841209044878 * (T_evap + min(max(superheat_K, 5.0), 30.0))) + 999.190772536527
    else:
        oil_density_sat = (-0.00356060606060549 * (T_evap ** 2)) - (0.957878787878808 * T_evap) + 963.595454545455
        oil_density_super = (-0.00356060606060549 * ((T_evap + min(max(superheat_K, 5.0), 30.0)) ** 2)) - (0.957878787878808 * (T_evap + min(max(superheat_K, 5.0), 30.0))) + 963.595454545455

    oil_density = (oil_density_sat + oil_density_super) / 2.0
    jg_half = _jg_half_for_refrigerant(refrigerant)

    MinMassFlux = (jg_half ** 2) * (
        (density_foroil * 9.81 * ID_m_local * (oil_density - density_foroil)) ** 0.5
    )
    MinMassFlow = MinMassFlux * area_m2_local

    MOR_pre = (MinMassFlow / mass_flow_foroil) * 100.0 if mass_flow_foroil > 0 else float("inf")
    MOR_premin = (MinMassFlow / mass_flow_foroilmin) * 100.0 if mass_flow_foroilmin > 0 else float("inf")

    # ------------------------------------------------------------------
    # Correction factors (identical to main code)
    # ------------------------------------------------------------------
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
    elif refrigerant == "R744 TC":
        MOR_correction = (0.0000603336117708171 * h_in) - 0.0142318718120024
    elif refrigerant in ["R407A", "R449A", "R448A", "R502"]:
        MOR_correction = (
            0.00000414431651323856 * (MOR_correctliq ** 2)
            + 0.000381908525139781 * MOR_correctliq
            - 0.0163450053041212
        )
    elif refrigerant == "R507A":
        MOR_correction = (0.000302619054048837 * MOR_correctliq) - 0.00930188913363997
    elif refrigerant == "R22":
        MOR_correction = (0.000108153843367715 * MOR_correctliq) - 0.00329248681202757
    elif refrigerant == "R407C":
        MOR_correction = (
            0.00000420322918839302 * (max(MOR_correctliq, -32.0716410083429) ** 2)
            + 0.000269608915211859 * max(MOR_correctliq, -32.0716410083429)
            - 0.0134546663857195
        )
    elif refrigerant == "R410A":
        MOR_correction = 0.0
    elif refrigerant == "R407F":
        MOR_correction = (
            0.00000347332380289385 * (max(MOR_correctliq, -34.4346433150568) ** 2)
            + 0.000239205332540693 * max(MOR_correctliq, -34.4346433150568)
            - 0.0121545316131988
        )
    elif refrigerant == "R134a":
        MOR_correction = (0.000195224660107459 * MOR_correctliq) - 0.00591757011487048
    elif refrigerant == "R404A":
        MOR_correction = (
            0.0000156507169104918 * (max(MOR_correctliq, -22.031637377024) ** 2)
            + 0.000689621839324826 * max(MOR_correctliq, -22.031637377024)
            - 0.0392
        )
    else:
        MOR_correction = (
            0.00000461020482461793 * (max(MOR_correctliq, -23.6334996273983) ** 2)
            + 0.000217910548009675 * max(MOR_correctliq, -23.6334996273983)
            - 0.012074621594626
        )

    # Same for min-liquid
    if refrigerant == "R744":
        MOR_correctionmin = (0.000225755013421421 * MOR_correctliqmin) - 0.00280879370374927
    elif refrigerant == "R744 TC":
        MOR_correctionmin = (0.0000603336117708171 * h_inmin) - 0.0142318718120024
    elif refrigerant in ["R407A", "R449A", "R448A", "R502"]:
        MOR_correctionmin = (
            0.00000414431651323856 * (MOR_correctliqmin ** 2)
            + 0.000381908525139781 * MOR_correctliqmin
            - 0.0163450053041212
        )
    elif refrigerant == "R507A":
        MOR_correctionmin = (0.000302619054048837 * MOR_correctliqmin) - 0.00930188913363997
    elif refrigerant == "R22":
        MOR_correctionmin = (0.000108153843367715 * MOR_correctliqmin) - 0.00329248681202757
    elif refrigerant == "R407C":
        MOR_correctionmin = (
            0.00000420322918839302 * (max(MOR_correctliqmin, -32.0716410083429) ** 2)
            + 0.000269608915211859 * max(MOR_correctliqmin, -32.0716410083429)
            - 0.0134546663857195
        )
    elif refrigerant == "R410A":
        MOR_correctionmin = 0.0
    elif refrigerant == "R407F":
        MOR_correctionmin = (
            0.00000347332380289385 * (max(MOR_correctliqmin, -34.4346433150568) ** 2)
            + 0.000239205332540693 * max(MOR_correctliqmin, -34.4346433150568)
            - 0.0121545316131988
        )
    elif refrigerant == "R134a":
        MOR_correctionmin = (0.000195224660107459 * MOR_correctliqmin) - 0.00591757011487048
    elif refrigerant == "R404A":
        MOR_correctionmin = (
            0.0000156507169104918 * (max(MOR_correctliqmin, -22.031637377024) ** 2)
            + 0.000689621839324826 * max(MOR_correctliqmin, -22.031637377024)
            - 0.0392
        )
    else:
        MOR_correctionmin = (
            0.00000461020482461793 * (max(MOR_correctliqmin, -23.6334996273983) ** 2)
            + 0.000217910548009675 * max(MOR_correctliqmin, -23.6334996273983)
            - 0.012074621594626
        )

    # Second correction vs evap temp
    if refrigerant == "R744":
        MOR_correction2 = (
            -0.0000176412848988908 * (evapoil ** 2)
            - 0.00164308248808803 * evapoil
            - 0.0184308798286039
        )
    elif refrigerant == "R744 TC":
        MOR_correction2 = (
            -0.0000176412848988908 * (evapoil ** 2)
            - 0.00164308248808803 * evapoil
            - 0.0184308798286039
        )
    elif refrigerant == "R407A":
        MOR_correction2 = (-0.000864076433837511 * evapoil) - 0.0145018190416687
    elif refrigerant == "R449A":
        MOR_correction2 = (-0.000835375233693285 * evapoil) - 0.0138846063856621
    elif refrigerant == "R448A":
        MOR_correction2 = (
            0.00000171366802431428 * (evapoil ** 2)
            - 0.000865528727278154 * evapoil
            - 0.0152961902042161
        )
    elif refrigerant == "R502":
        MOR_correction2 = (
            0.00000484734071020993 * (evapoil ** 2)
            - 0.000624822304716683 * evapoil
            - 0.0128725684240106
        )
    elif refrigerant == "R507A":
        MOR_correction2 = (-0.000701333343440148 * evapoil) - 0.0114900933623056
    elif refrigerant == "R22":
        MOR_correction2 = (
            0.00000636798209134899 * (evapoil ** 2)
            - 0.000157783204337396 * evapoil
            - 0.00575251626397381
        )
    elif refrigerant == "R407C":
        MOR_correction2 = (
            -0.00000665735727676349 * (evapoil ** 2)
            - 0.000894860288947537 * evapoil
            - 0.0116054361757929
        )
    elif refrigerant == "R410A":
        MOR_correction2 = (-0.000672268853990701 * evapoil) - 0.0111802230098585
    elif refrigerant == "R407F":
        MOR_correction2 = (
            0.00000263731418614519 * (evapoil ** 2)
            - 0.000683997257738699 * evapoil
            - 0.0126005968942147
        )
    elif refrigerant == "R134a":
        MOR_correction2 = (
            -0.00000823045532174214 * (evapoil ** 2)
            - 0.00108063672211041 * evapoil
            - 0.0217411206961643
        )
    elif refrigerant == "R404A":
        MOR_correction2 = (
            0.00000342378568620316 * (evapoil ** 2)
            - 0.000329572335134041 * evapoil
            - 0.00706087606597149
        )
    else:
        MOR_correction2 = (-0.000711441807827186 * evapoil) - 0.0118194116436425

    # ------------------------------------------------------------------
    # Final MOR values (max-liquid & min-liquid) for THIS pipe
    # ------------------------------------------------------------------
    MOR = ""
    MORmin = ""

    if refrigerant in ["R23", "R508B"]:
        if -86 <= T_evap <= -42:
            MOR = (1 - MOR_correction) * (1 - MOR_correction2) * MOR_pre
            MORmin = (1 - MOR_correctionmin) * (1 - MOR_correction2) * MOR_premin
    else:
        if -40 <= T_evap <= 4:
            MOR = (1 - MOR_correction) * (1 - MOR_correction2) * MOR_pre
            MORmin = (1 - MOR_correctionmin) * (1 - MOR_correction2) * MOR_premin

    # Extract numeric values
    if MOR == "" or MORmin == "":
        MOR_maxliq = float("nan")
        MOR_minliq = float("nan")
    else:
        MOR_maxliq = float(MOR)      # MOR at max liquid temp
        MOR_minliq = float(MORmin)   # MOR at min liquid temp

    # Worst and best for THIS pipe and THIS branch mass flow
    MOR_worst = min(MOR_maxliq, MOR_minliq)
    MOR_best = max(MOR_maxliq, MOR_minliq)

    # ------------------------------------------------------------------
    # Density for Reynolds, viscosities, friction factor, PD, ΔT
    # ------------------------------------------------------------------
    if velocity_m_s > 0:
        density_recalc_local = mass_flow_kg_s / (velocity_m_s * area_m2_local)
    else:
        density_recalc_local = density

    # Viscosities
    if refrigerant == "R744 TC":
        viscosity_super = visc.get_viscosity("R744", T_evap - max_penalty + 273.15, superheat_K)
        viscosity_super2a = visc.get_viscosity("R744", T_evap + 273.15, ((superheat_K + 5.0) / 2.0))
        viscosity_super2b = visc.get_viscosity("R744", T_evap - max_penalty + 273.15, ((superheat_K + 5.0) / 2.0))
        viscosity_super2 = (viscosity_super2a + viscosity_super2b) / 2.0
        viscosity_5K = visc.get_viscosity("R744", T_evap + 273.15, 5.0)
    else:
        viscosity_super = visc.get_viscosity(refrigerant, T_evap - max_penalty + 273.15, superheat_K)
        viscosity_super2a = visc.get_viscosity(refrigerant, T_evap + 273.15, ((superheat_K + 5.0) / 2.0))
        viscosity_super2b = visc.get_viscosity(refrigerant, T_evap - max_penalty + 273.15, ((superheat_K + 5.0) / 2.0))
        viscosity_super2 = (viscosity_super2a + viscosity_super2b) / 2.0
        viscosity_5K = visc.get_viscosity(refrigerant, T_evap + 273.15, 5.0)

    viscosity = (viscosity_super + viscosity_5K) / 2.0
    viscosity_final = (viscosity * velocity1_prop) + (viscosity_super2 * (1.0 - velocity1_prop))

    reynolds_local = (
        density_recalc_local * velocity_m_sfinal * ID_m_local / (viscosity_final / 1_000_000.0)
        if viscosity_final > 0 else 0.0
    )

    # friction factor (Colebrook or laminar)
    if ctx.selected_material in ["Steel SCH40", "Steel SCH80"]:
        eps = 0.00004572
    else:
        eps = 0.000001524

    if 0 < reynolds_local < 2000.0:
        f_local = 64.0 / reynolds_local
    else:
        tol = 1e-5
        max_iter = 60
        flo, fhi = 1e-5, 0.1

        def balance(gg: float):
            s = math.sqrt(gg)
            lhs = 1.0 / s
            rhs = -2.0 * math.log10((eps / (3.7 * ID_m_local)) + 2.51 / (reynolds_local * s))
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

    # K-factors from this pipe row
    required_cols = ["SRB", "LRB", "BALL", "GLOBE"]
    for c in required_cols:
        if c not in pipe_row.index:
            nan = float("nan")
            return PipeResult(
                MOR_worst=nan,
                MOR_best=nan,
                MOR_maxliq=nan,
                MOR_minliq=nan,
                DP_kPa=nan,
                DT_K=nan,
                velocity_m_s=velocity_m_sfinal,
                density=density_recalc_local,
                viscosity_uPa_s=viscosity_final,
                reynolds=reynolds_local,
                post_temp_C=nan,
                post_press_bar=nan,
                mass_flow_kg_s=mass_flow_kg_s,
            )

    K_SRB = float(pipe_row["SRB"])
    K_LRB = float(pipe_row["LRB"])
    K_BALL = float(pipe_row["BALL"])
    K_GLOBE = float(pipe_row["GLOBE"])

    # dynamic pressure
    q_kPa_local = 0.5 * density_recalc_local * (velocity_m_sfinal ** 2) / 1000.0

    B_SRB = ctx.SRB + 0.5 * ctx.bends_45 + 2.0 * ctx.ubend + 3.0 * ctx.ptrap
    B_LRB = ctx.LRB + ctx.MAC

    dp_pipe_kPa_local = f_local * (ctx.L / ID_m_local) * q_kPa_local
    dp_plf_kPa_local = q_kPa_local * ctx.PLF
    dp_fittings_kPa_local = q_kPa_local * (K_SRB * B_SRB + K_LRB * B_LRB)
    dp_valves_kPa_local = q_kPa_local * (K_BALL * ctx.ball + K_GLOBE * ctx.globe)
    dp_total_kPa_local = (
        dp_pipe_kPa_local + dp_fittings_kPa_local + dp_valves_kPa_local + dp_plf_kPa_local
    )

    # ΔT mapping via pressure change — same as your page
    if refrigerant == "R744 TC":
        evappres_local = conv.temp_to_pressure("R744", T_evap)
    else:
        evappres_local = conv.temp_to_pressure(refrigerant, T_evap)

    postcirc_local = evappres_local - (dp_total_kPa_local / 100.0)
    if refrigerant == "R744 TC":
        postcirctemp_local = conv.pressure_to_temp("R744", postcirc_local)
    else:
        postcirctemp_local = conv.pressure_to_temp(refrigerant, postcirc_local)

    dt_local = T_evap - postcirctemp_local

    return PipeResult(
        MOR_worst=MOR_worst,
        MOR_best=MOR_best,
        MOR_maxliq=MOR_maxliq,
        MOR_minliq=MOR_minliq,
        DP_kPa=dp_total_kPa_local,
        DT_K=dt_local,
        velocity_m_s=velocity_m_sfinal,
        density=density_recalc_local,
        viscosity_uPa_s=viscosity_final,
        reynolds=reynolds_local,
        post_temp_C=postcirctemp_local,
        post_press_bar=postcirc_local,
        mass_flow_kg_s=mass_flow_kg_s,
    )


def balance_double_riser(
    size_small: str,
    size_large: str,
    M_total_kg_s: float,
    ctx: RiserContext,
    tol_kPa: float = 0.01,
    max_iter: int = 50,
) -> DoubleRiserResult:
    """
    Solve for the mass flow split between SMALL and LARGE riser branches such that:

        DP_small(M_small) = DP_large(M_total - M_small)

    at FULL LOAD, using your full MOR/DP/ΔT engine.

    System-level MOR is computed with S2 logic:
      MOR_system_worst = min( all four MOR_max/min from both branches )
      MOR_system_best  = max( all four MOR_max/min from both branches )
    """

    if M_total_kg_s <= 0:
        raise ValueError("M_total_kg_s must be > 0 for double-riser balancing.")

    # Bisection bounds for small-riser branch flow
    lo = 0.01 * M_total_kg_s
    hi = 0.99 * M_total_kg_s

    res_small: Optional[PipeResult] = None
    res_large: Optional[PipeResult] = None

    for _ in range(max_iter):
        M_small = 0.5 * (lo + hi)
        M_large = M_total_kg_s - M_small

        # Evaluate each branch with EXACT same engine
        res_small = pipe_results_for_massflow(size_small, M_small, ctx)
        res_large = pipe_results_for_massflow(size_large, M_large, ctx)

        # Compare pressure drops
        diff = res_small.DP_kPa - res_large.DP_kPa

        if abs(diff) <= tol_kPa:
            # Balanced enough
            break

        # Bisection direction
        if diff > 0:
            # Small riser has higher PD => decrease M_small
            hi = M_small
        else:
            # Small riser has lower PD => increase M_small
            lo = M_small

    if res_small is None or res_large is None:
        raise RuntimeError("Double-riser balancing failed to converge.")

    M_small_final = res_small.mass_flow_kg_s
    M_large_final = res_large.mass_flow_kg_s

    DP_final = (res_small.DP_kPa + res_large.DP_kPa) / 2.0  # should be ~equal
    DT_final = res_small.DT_K  # penalty from balanced PD (branches share same circuit)

    # ------------------------------------------------------------------
    # System-level MOR (S2 logic): min & max over all 4 cases:
    #   small.maxliq, small.minliq, large.maxliq, large.minliq
    # ------------------------------------------------------------------
    vals = []
    for v in [
        res_small.MOR_maxliq,
        res_small.MOR_minliq,
        res_large.MOR_maxliq,
        res_large.MOR_minliq,
    ]:
        if isinstance(v, (int, float)) and math.isfinite(v):
            vals.append(v)

    if vals:
        MOR_system_worst = min(vals)
        MOR_system_best = max(vals)
    else:
        MOR_system_worst = float("nan")
        MOR_system_best = float("nan")

    return DoubleRiserResult(
        size_small=size_small,
        size_large=size_large,
        M_total=M_total_kg_s,
        M_small=M_small_final,
        M_large=M_large_final,
        DP_kPa=DP_final,
        DT_K=DT_final,

        MOR_small_worst=res_small.MOR_worst,
        MOR_small_best=res_small.MOR_best,
        MOR_small_maxliq=res_small.MOR_maxliq,
        MOR_small_minliq=res_small.MOR_minliq,

        MOR_large_worst=res_large.MOR_worst,
        MOR_large_best=res_large.MOR_best,
        MOR_large_maxliq=res_large.MOR_maxliq,
        MOR_large_minliq=res_large.MOR_minliq,

        MOR_system_worst=MOR_system_worst,
        MOR_system_best=MOR_system_best,

        small_result=res_small,
        large_result=res_large,
    )
