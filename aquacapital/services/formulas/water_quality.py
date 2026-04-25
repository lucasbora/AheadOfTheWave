"""
Water quality risk formulas based on WWF Water Risk Filter v3.0, Section 4.
Sources: Jones et al. (2023), Damania et al. (2019).
"""


def calculate_biological_oxygen_demand_risk(bod_mg_per_l: float) -> int:
    """
    DynQual BOD model. Source: Jones et al. (2023), WWF WRF v3.0 B4_4.
    bod_mg_per_l: biological oxygen demand in mg/L.
    Thresholds: <=1=1, 1-5=2, 5-10=3, 10-30=4, >30=5.
    Returns risk value 1-5.
    """
    if bod_mg_per_l <= 1.0:
        return 1
    if bod_mg_per_l <= 5.0:
        return 2
    if bod_mg_per_l <= 10.0:
        return 3
    if bod_mg_per_l <= 30.0:
        return 4
    return 5


def calculate_nitrate_risk(nitrate_mg_per_l: float) -> int:
    """
    World Bank Nitrate-Nitrite Concentration. Source: Damania et al. (2019), WWF WRF v3.0 B4_2.
    nitrate_mg_per_l: nitrate concentration in mg/L.
    Thresholds: <=0.4=1, 0.4-0.8=2, 0.8-1.2=3, 1.2-1.6=4, >1.6=5.
    Returns risk value 1-5.
    """
    if nitrate_mg_per_l <= 0.4:
        return 1
    if nitrate_mg_per_l <= 0.8:
        return 2
    if nitrate_mg_per_l <= 1.2:
        return 3
    if nitrate_mg_per_l <= 1.6:
        return 4
    return 5


def _calculate_salinity_risk(salinity_tds_mg_l: float) -> int:
    """
    DynQual Salinity (TDS). Source: Jones et al. (2023), WWF WRF v3.0 B4_9.
    Thresholds: <=100=1, 100-250=2, 250-525=3, 525-3000=4, >3000=5.
    Returns risk value 1-5.
    """
    if salinity_tds_mg_l <= 100.0:
        return 1
    if salinity_tds_mg_l <= 250.0:
        return 2
    if salinity_tds_mg_l <= 525.0:
        return 3
    if salinity_tds_mg_l <= 3000.0:
        return 4
    return 5


def calculate_water_quality_composite(
    bod_risk: int,
    nitrate_risk: int,
    salinity_tds_mg_l: float,
) -> dict:
    """
    Composite water quality score.
    Salinity from DynQual. Source: Jones et al. (2023), WWF WRF v3.0 B4_9.
    Salinity thresholds: <=100=1, 100-250=2, 250-525=3, 525-3000=4, >3000=5.
    Returns composite risk 1-5 as mean of all three indicators, plus breakdown dict.
    """
    salinity_risk = _calculate_salinity_risk(salinity_tds_mg_l)
    try:
        composite_float = (bod_risk + nitrate_risk + salinity_risk) / 3.0
    except ZeroDivisionError:
        composite_float = 3.0

    composite_risk = round(composite_float)

    return {
        "bod_risk": bod_risk,
        "nitrate_risk": nitrate_risk,
        "salinity_risk": salinity_risk,
        "composite_risk": composite_risk,
        "composite_score": round(composite_float, 3),
        "breakdown": {
            "bod": bod_risk,
            "nitrate": nitrate_risk,
            "salinity": salinity_risk,
        },
    }
