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
    """All non-mass-flow inputs needed to reproduce your MOR + DP + ΔT logic."""

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
    from typing import Callable, Optional
    # Pipe size lookup function
    pipe_row_for_size: Callable[[str, Optional[str]], pd.Series]

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
    """Full thermodynamic & geometric result for a branch."""

    # MOR-related
    MOR_worst: Optional[float]

    # Flow/pressure
    DP_kPa: float
    DT_K: float
    velocity_m_s: float
    density: float
    viscosity_uPa_s: float
    reynolds: float
    post_temp_C: float
    post_press_bar: float
    mass_flow_kg_s: float

    dp_pipe: float
    dp_fit: float
    dp_valve: float
    dp_plf: float

    # Geometry & oil physics (needed by UI and full-flow MOR)
    ID_mm: float
    ID_m: float
    area_m2: float
    density_foroil: float
    oil_density: float
    jg_half: float


@dataclass
class DoubleRiserResult:
    """Balanced double riser calculation."""

    size_small: str
    size_large: str

    M_total: float
    M_small: float
    M_large: float

    DP_kPa: float
    DT_K: float

    # Results for UI
    small_result: PipeResult
    large_result: PipeResult

    dp_pipe: float
    dp_fit: float
    dp_valve: float
    dp_plf: float

# ======================================================================
#  HELPER FUNCTIONS FOR REFRIGERANT DEPENDENCIES
# ======================================================================

def _velocity1_prop_for_refrigerant(refrigerant: str, superheat_K: float) -> float:
    """EXACT match to your get_pipe_results logic."""
    if refrigerant in ["R744", "R744 TC"]:
        return 1.0

    if refrigerant == "R404A":
        return (0.0328330590542629 * superheat_K) - 1.47748765744183 if superheat_K > 45 else 0.0

    if refrigerant == "R134a":
        if superheat_K > 30:
            return (
                -0.000566085879684639 * (superheat_K ** 2) +
                0.075049554857083 * superheat_K -
                1.74200935399632
            )
        return 0.0

    if refrigerant in ["R407F", "R407A", "R410A", "R22", "R502", "R507A", "R448A", "R449A", "R717"]:
        return 1.0

    if refrigerant == "R407C":
        return 0.0

    # default
    if superheat_K > 30:
        return (
            0.0000406422632403154 * (superheat_K ** 2) -
            0.000541007136813307 * superheat_K +
            0.748882946418884
        )
    return 0.769230769230769


def _jg_half_for_refrigerant(refrigerant: str) -> float:
    """EXACT mapping of your VB constants."""
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


# ======================================================================
#  FULL PIPE ENGINE — REFACTORED FOR SMALL-RISER MOR ONLY
# ======================================================================

def pipe_results_for_massflow(
    size_inch: str,
    branch_mass_flow_kg_s: float,
    ctx: RiserContext,
    compute_mor: bool,
    gauge: Optional[str] = None,
) -> PipeResult:
    """
    Full DP + ΔT + velocity + oil-return MINIMUM MASS FLOW for THIS pipe.

    compute_mor=False → skip MOR (large riser)
    compute_mor=True  → compute MOR (small riser and also full-flow MOR)
    """

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

    # ------------------------------------------------------------------
    # PIPE GEOMETRY
    # ------------------------------------------------------------------
    row = ctx.pipe_row_for_size(size_inch, gauge)
    ID_mm = float(row["ID_mm"])
    ID_m = ID_mm / 1000
    A = math.pi * (ID_m / 2)**2

    # ------------------------------------------------------------------
    # ENTHALPIES / MASS FLOW SPLITS — EXACTLY YOUR LOGIC
    # ------------------------------------------------------------------

    # CO2 TC
    if ref == "R744 TC":
        if ctx.gc_max_pres is None or ctx.gc_min_pres is None:
            raise ValueError("R744 TC requires discharge pressures.")

        h_in = props_sup.get_enthalpy_sup(ctx.gc_max_pres, T_cond)

        if ctx.gc_min_pres >= 73.8:
            h_inmin = props_sup.get_enthalpy_sup(ctx.gc_min_pres, T_min)
        elif ctx.gc_min_pres <= 72.13:
            h_inmin = props.get_properties("R744", T_min)["enthalpy_liquid2"]
        else:
            raise ValueError("Disallowed CO2 TC region")

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

    # superheat enthalpies
    hdiff_10K = h_10K - h_evap
    h_super = h_evap + hdiff_10K * min(max(SH, 5.0), 30.0) / 10.0
    h_foroil = (h_evap + h_super) / 2

    Δh = h_evap - h_in
    Δh_min = h_evap - h_inmin
    Δh_oil = h_foroil - h_inlet
    Δh_oil_min = h_foroil - h_inletmin

    # Equivalent branch duty Q
    if Δh <= 0:
        Q = 0
        m = max(branch_mass_flow_kg_s, 0.01)
    else:
        m = max(branch_mass_flow_kg_s, 0)
        Q = m * Δh

    m_min = Q / Δh_min if Δh_min > 0 else 0.01
    m_oil = Q / Δh_oil if Δh_oil > 0 else 0.01
    m_oil_min = Q / Δh_oil_min if Δh_oil_min > 0 else 0.01

    # ------------------------------------------------------------------
    # DENSITIES & VELOCITIES (Original)
    # ------------------------------------------------------------------

    if ref == "R744 TC":
        density_super = dens.get_density("R744", T_evap - penalty + 273.15, SH)
        ds2a = dens.get_density("R744", T_evap + 273.15, ((SH + 5) / 2))
        ds2b = dens.get_density("R744", T_evap - penalty + 273.15, ((SH + 5) / 2))
        density_super2 = (ds2a + ds2b) / 2
        density_super_oil = dens.get_density("R744", T_evap + 273.15, min(max(SH, 5), 30))
        density_sat = props.get_properties("R744", T_evap)["density_vapor"]
        density_5K = dens.get_density("R744", T_evap + 273.15, 5)

    else:
        density_super = dens.get_density(ref, T_evap - penalty + 273.15, SH)
        ds2a = dens.get_density(ref, T_evap + 273.15, ((SH + 5) / 2))
        ds2b = dens.get_density(ref, T_evap - penalty + 273.15, ((SH + 5) / 2))
        density_super2 = (ds2a + ds2b) / 2
        density_super_oil = dens.get_density(ref, T_evap + 273.15, min(max(SH, 5), 30))
        density_sat = props.get_properties(ref, T_evap)["density_vapor"]
        density_5K = dens.get_density(ref, T_evap + 273.15, 5)

    density_mix = (density_super + density_5K) / 2
    density_foroil = (density_super_oil + density_sat) / 2

    # velocities
    v1 = m / (A * density_mix) if density_mix > 0 else 0
    v1min = m_min / (A * density_mix) if density_mix > 0 else 0
    v2 = m / (A * density_super2) if density_super2 > 0 else 0
    v2min = m_min / (A * density_super2) if density_super2 > 0 else 0

    w = _velocity1_prop_for_refrigerant(ref, SH)
    v = max(v1*w + v2*(1-w), v1min*w + v2min*(1-w))

    # ----------------------------------------------------------------------
    # OIL DENSITY MODEL
    # ----------------------------------------------------------------------

    if ref in ["R23", "R508B"]:
        oil_sat = (-0.853841209044878 * T_evap) + 999.190772536527
        oil_sup = (-0.853841209044878 *
                   (T_evap + min(max(SH, 5), 30))) + 999.190772536527
    else:
        oil_sat = (
            -0.00356060606060549*(T_evap**2)
            - 0.957878787878808*T_evap
            + 963.595454545455
        )
        oil_sup = (
            -0.00356060606060549*((T_evap + min(max(SH, 5), 30))**2)
            - 0.957878787878808*(T_evap + min(max(SH, 5), 30))
            + 963.595454545455
        )

    oil_density = (oil_sat + oil_sup) / 2

    # ----------------------------------------------------------------------
    # MINIMUM MASS FLOW (THIS is the basis of ALL MOR — full-flow + branch)
    # ----------------------------------------------------------------------

    jg = _jg_half_for_refrigerant(ref)

    MinMassFlux = (jg**2) * (
        (density_foroil * 9.81 * ID_m * (oil_density - density_foroil)) ** 0.5
    )
    MinMassFlow = MinMassFlux * A

    # ----------------------------------------------------------------------
    # MOR calculation (ONLY for small riser)
    # ----------------------------------------------------------------------

    MOR_worst = None

    if compute_mor:

        # MOR_pre at max liquid
        MOR_pre = MinMassFlow / m_oil if m_oil > 0 else float("inf")
        MOR_pre_min = MinMassFlow / m_oil_min if m_oil_min > 0 else float("inf")

        # Temperature corrections — SAME AS YOUR ORIGINAL LOGIC
        if ref in ["R23", "R508B"]:
            MCL = T_cond + 47.03
            MCL_min = T_min + 47.03
            evap_oil_T = T_evap + 46.14
        else:
            MCL = T_cond
            MCL_min = T_min
            evap_oil_T = T_evap

        # Liquid correction factors
        def corr_L(T):
            if ref == "R744":
                return 0.000225755013421421*T - 0.00280879370374927
            if ref == "R744 TC":
                return (0.0000603336117708171 * h_in) - 0.0142318718120024
            if ref in ["R407A", "R449A", "R448A", "R502"]:
                return 0.00000414431651323856*(T**2) + 0.000381908525139781*T - 0.0163450053041212
            if ref == "R507A":
                return 0.000302619054048837*T - 0.00930188913363997
            if ref == "R22":
                return 0.000108153843367715*T - 0.00329248681202757
            if ref == "R407C":
                TT = max(T, -32.0716410083429)
                return 0.00000420322918839302*(TT**2) + 0.000269608915211859*TT - 0.0134546663857195
            if ref == "R410A":
                return 0
            if ref == "R407F":
                TT = max(T, -34.4346433150568)
                return 0.00000347332380289385*(TT**2) + 0.000239205332540693*TT - 0.0121545316131988
            if ref == "R134a":
                return 0.000195224660107459*T - 0.00591757011487048
            if ref == "R404A":
                TT = max(T, -22.031637377024)
                return 0.0000156507169104918*(TT**2) + 0.000689621839324826*TT - 0.0392

            # default
            TT = max(T, -23.6334996273983)
            return 0.00000461020482461793*(TT**2) + 0.000217910548009675*TT - 0.012074621594626

        C1 = corr_L(MCL)
        C1_min = corr_L(MCL_min)

        # Second evap correction
        def corr_e(T):
            if ref in ["R744", "R744 TC"]:
                return (-0.0000176412848988908*(T**2)
                        - 0.00164308248808803*T
                        - 0.0184308798286039)
            if ref == "R407A":
                return -0.000864076433837511*T - 0.0145018190416687
            if ref == "R449A":
                return -0.000835375233693285*T - 0.0138846063856621
            if ref == "R448A":
                return (0.00000171366802431428*(T**2)
                        - 0.000865528727278154*T
                        - 0.0152961902042161)
            if ref == "R502":
                return (0.00000484734071020993*(T**2)
                        - 0.000624822304716683*T
                        - 0.0128725684240106)
            if ref == "R507A":
                return -0.000701333343440148*T - 0.0114900933623056
            if ref == "R22":
                return (0.00000636798209134899*(T**2)
                        - 0.000157783204337396*T
                        - 0.00575251626397381)
            if ref == "R407C":
                return (-0.00000665735727676349*(T**2)
                        - 0.000894860288947537*T
                        - 0.0116054361757929)
            if ref == "R410A":
                return -0.000672268853990701*T - 0.0111802230098585
            if ref == "R407F":
                return (0.00000263731418614519*(T**2)
                        - 0.000683997257738699*T
                        - 0.0126005968942147)
            if ref == "R134a":
                return (-0.00000823045532174214*(T**2)
                        - 0.00108063672211041*T
                        - 0.0217411206961643)
            if ref == "R404A":
                return (0.00000342378568620316*(T**2)
                        - 0.000329572335134041*T
                        - 0.00706087606597149)

            # default
            return -0.000711441807827186*T - 0.0118194116436425

        C2 = corr_e(evap_oil_T)

        # Final MOR (max/min liquid)
        MOR_max = (1 - C1)*(1 - C2)*MOR_pre
        MOR_min = (1 - C1_min)*(1 - C2)*MOR_pre_min

        MOR_worst = max(MOR_max, MOR_min)

    # ----------------------------------------------------------------------
    # Reynolds, friction factor, DP, ΔT — EXACT COPY of page logic
    # ----------------------------------------------------------------------

    # visc
    if ref == "R744 TC":
        vis_sup = visc.get_viscosity("R744", T_evap - penalty + 273.15, SH)
        vs2a = visc.get_viscosity("R744", T_evap + 273.15, ((SH+5)/2))
        vs2b = visc.get_viscosity("R744", T_evap - penalty + 273.15, ((SH+5)/2))
        vis2 = (vs2a + vs2b) / 2
        vis5 = visc.get_viscosity("R744", T_evap + 273.15, 5)
    else:
        vis_sup = visc.get_viscosity(ref, T_evap - penalty + 273.15, SH)
        vs2a = visc.get_viscosity(ref, T_evap + 273.15, ((SH+5)/2))
        vs2b = visc.get_viscosity(ref, T_evap - penalty + 273.15, ((SH+5)/2))
        vis2 = (vs2a + vs2b) / 2
        vis5 = visc.get_viscosity(ref, T_evap + 273.15, 5)

    vis = (vis_sup + vis5)/2
    vis_final = vis*w + vis2*(1-w)

    # Reynolds
    rho_recalc = m / (v*A) if v > 0 else density_mix
    Re = rho_recalc * v * ID_m / (vis_final/1e6) if vis_final > 0 else 0

    # friction factor
    eps = 0.00004572 if ctx.selected_material in ["Steel SCH40","Steel SCH80"] else 0.000001524

    if 0 < Re < 2000:
        f = 64/Re
    else:
        f = 0.02
        for _ in range(50):
            lhs = 1/math.sqrt(f)
            rhs = -2*math.log10((eps/(3.7*ID_m)) + 2.51/(Re*math.sqrt(f)))
            if abs(lhs-rhs) < 1e-5:
                break
            # simple relaxation
            f = ((1/rhs)**2)

    # K-factors
    K_SRB = float(row["SRB"])
    K_LRB = float(row["LRB"])
    K_BALL = float(row["BALL"])
    K_GLOBE = float(row["GLOBE"])

    B_SRB = ctx.SRB + 0.5*ctx.bends_45 + 2*ctx.ubend + 3*ctx.ptrap
    B_LRB = ctx.LRB + ctx.MAC

    q = 0.5*rho_recalc*(v**2)/1000

    dp_pipe = f*(ctx.L/ID_m)*q
    dp_plf = q*ctx.PLF
    dp_fit = q*(K_SRB*B_SRB + K_LRB*B_LRB)
    dp_valve = q*(K_BALL*ctx.ball + K_GLOBE*ctx.globe)

    DP = dp_pipe + dp_fit + dp_valve + dp_plf

    # ΔT from pressure drop
    if ref == "R744 TC":
        Pevap = conv.temp_to_pressure("R744", T_evap)
        P2 = Pevap - DP/100
        T2 = conv.pressure_to_temp("R744", P2)
    else:
        Pevap = conv.temp_to_pressure(ref, T_evap)
        P2 = Pevap - DP/100
        T2 = conv.pressure_to_temp(ref, P2)

    DT = T_evap - T2

    # ----------------------------------------------------------------------
    # RETURN
    # ----------------------------------------------------------------------
    return PipeResult(
        MOR_worst=MOR_worst,
        DP_kPa=DP,
        DT_K=DT,
        velocity_m_s=v,
        density=rho_recalc,
        viscosity_uPa_s=vis_final,
        reynolds=Re,
        post_temp_C=T2,
        post_press_bar=P2,
        mass_flow_kg_s=m,

        dp_pipe=dp_pipe,
        dp_fit=dp_fit,
        dp_valve=dp_valve,
        dp_plf=dp_plf,

        # Geometry & oil fields — NEW
        ID_mm=ID_mm,
        ID_m=ID_m,
        area_m2=A,
        density_foroil=density_foroil,
        oil_density=oil_density,
        jg_half=jg,
    )


# ======================================================================
#  DOUBLE RISER BALANCING — FINAL VERSION (VB IDENTICAL)
# ======================================================================

def balance_double_riser(
    size_small: str,
    size_large: str,
    M_total_kg_s: float,
    ctx: RiserContext,
    gauge_small: Optional[str] = None,
    gauge_large: Optional[str] = None,
    tol_kPa: float = 0.001,
    max_iter: int = 100,
) -> DoubleRiserResult:

    if M_total_kg_s <= 0:
        raise ValueError("Total mass flow must be > 0.")

    lo = 0.000001*M_total_kg_s
    hi = 0.999999*M_total_kg_s

    res_s = None
    res_l = None

    for _ in range(max_iter):
        M_small = 0.5*(lo+hi)
        M_large = M_total_kg_s - M_small

        res_s = pipe_results_for_massflow(size_small, M_small, ctx, compute_mor=True,  gauge=gauge_small)
        res_l = pipe_results_for_massflow(size_large, M_large, ctx, compute_mor=False, gauge=gauge_large)

        diff = res_s.DP_kPa - res_l.DP_kPa

        if abs(diff) <= tol_kPa:
            break

        if diff > 0:
            hi = M_small
        else:
            lo = M_small

    if res_s is None or res_l is None:
        raise RuntimeError("Double riser balance failed.")

    return DoubleRiserResult(
        size_small=size_small,
        size_large=size_large,
        M_total=M_total_kg_s,
        M_small=res_s.mass_flow_kg_s,
        M_large=res_l.mass_flow_kg_s,
        DP_kPa=(res_s.DP_kPa + res_l.DP_kPa)/2,
        DT_K=(res_s.DT_K + res_l.DT_K)/2,
        small_result=res_s,
        large_result=res_l,
        dp_pipe=(res_s.dp_pipe + res_l.dp_pipe)/2,
        dp_fit=(res_s.dp_fit + res_l.dp_fit)/2,
        dp_valve=(res_s.dp_valve + res_l.dp_valve)/2,
        dp_plf=(res_s.dp_plf + res_l.dp_plf)/2,
    )


