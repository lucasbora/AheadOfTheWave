"""
Physical risk formulas based on WWF Water Risk Filter v3.0 and WRI Aqueduct.
All thresholds and indicator codes are sourced directly from the methodology documents.
"""


def calculate_water_depletion_risk(depletion_ratio: float) -> int:
    """
    WaterGAP Water Depletion. Source: Brauman et al. (2016), WWF WRF v3.0 B1_1.
    Returns risk value 1-5 (1=Very Low, 5=Very High).
    Thresholds: <=0.1=1, <=0.2=2, <=0.4=3, <=0.8=4, >0.8=5.
    """
    if depletion_ratio <= 0.1:
        return 1
    if depletion_ratio <= 0.2:
        return 2
    if depletion_ratio <= 0.4:
        return 3
    if depletion_ratio <= 0.8:
        return 4
    return 5


def calculate_baseline_water_stress_risk(
    annual_depletion_pct: float,
    dry_year_months: int,
    seasonal_months: int,
) -> int:
    """
    WRI Aqueduct 4.0 Baseline Water Stress. Source: Kuzma et al. (2023), WWF WRF v3.0 B1_2.
    annual_depletion_pct: percentage of annual depletion.
    dry_year_months: number of years (out of 30) with at least one monthly depletion >75%.
    seasonal_months: whether monthly depletion >75% occurs every year (>0 = yes).
    Thresholds: <=5%=1, 5-25%=2, 25-75% dry_year<3=3, 25-75% seasonal>0=4, >75%=5.
    Returns risk value 1-5.
    """
    if annual_depletion_pct <= 5.0:
        return 1
    if annual_depletion_pct <= 25.0:
        return 2
    if annual_depletion_pct > 75.0:
        return 5
    # 25-75% range — distinguish by dry year frequency
    if seasonal_months > 0:
        return 4
    if dry_year_months >= 3:
        return 3
    return 3


def calculate_groundwater_risk(groundwater_change_mm: float) -> int:
    """
    Global Land Water Storage (GLWS). Source: Gerdener (2024), WWF WRF v3.0 B1_4.
    groundwater_change_mm: change in groundwater level (negative = decline).
    Thresholds: >=5=1, -5 to +5=2, -5.01 to -50=3, -50.01 to -100=4, <-100=5.
    Returns risk value 1-5.
    """
    if groundwater_change_mm >= 5.0:
        return 1
    if groundwater_change_mm >= -5.0:
        return 2
    if groundwater_change_mm >= -50.0:
        return 3
    if groundwater_change_mm >= -100.0:
        return 4
    return 5


def calculate_longterm_drought_risk(spei_dry_proportion_10yr: float) -> int:
    """
    SPEI-12 Long-term drought. Source: Vicente-Serrano et al. (2010), Copernicus GDO,
    WWF WRF v3.0 B2_1.
    spei_dry_proportion_10yr: proportion of dry events (SPEI <= -1) in 10-year period.
    Thresholds: 0=1, 0-0.15=2, 0.15-0.3=3, 0.3-0.6=4, >0.6=5.
    Returns risk value 1-5.
    """
    if spei_dry_proportion_10yr == 0.0:
        return 1
    if spei_dry_proportion_10yr <= 0.15:
        return 2
    if spei_dry_proportion_10yr <= 0.30:
        return 3
    if spei_dry_proportion_10yr <= 0.60:
        return 4
    return 5


def calculate_shortterm_drought_risk(spei_dry_proportion_3yr: float) -> int:
    """
    SPEI-12 Short-term drought. Source: Vicente-Serrano et al. (2010), Copernicus GDO,
    WWF WRF v3.0 B2_2.
    spei_dry_proportion_3yr: proportion of dry events (SPEI <= -1) in 3-year period.
    Same thresholds as long-term.
    Returns risk value 1-5.
    """
    if spei_dry_proportion_3yr == 0.0:
        return 1
    if spei_dry_proportion_3yr <= 0.15:
        return 2
    if spei_dry_proportion_3yr <= 0.30:
        return 3
    if spei_dry_proportion_3yr <= 0.60:
        return 4
    return 5


def calculate_flood_occurrence_risk(flood_events_count: int) -> int:
    """
    Dartmouth Flood Observatory. Source: Brakenridge (2020), WWF WRF v3.0 B3_1.
    flood_events_count: number of flood events since 1985.
    Thresholds: 0=1, 1-2=2, 3-10=3, 10-30=4, >30=5.
    Returns risk value 1-5.
    """
    if flood_events_count == 0:
        return 1
    if flood_events_count <= 2:
        return 2
    if flood_events_count <= 10:
        return 3
    if flood_events_count <= 30:
        return 4
    return 5


def calculate_flood_hazard_risk(avg_flood_depth_m: float) -> int:
    """
    JRC Global River Flood Hazard Maps 100-year return period.
    Source: Dottori et al. (2016), WWF WRF v3.0 B3_2.
    avg_flood_depth_m: median flood depth (m) within 100-year flood extent.
    Thresholds (quantiles): <=1.27=1, 1.27-2.47=2, 2.47-4.28=3, 4.28-7.65=4, >7.65=5.
    Returns risk value 1-5.
    """
    if avg_flood_depth_m <= 1.27:
        return 1
    if avg_flood_depth_m <= 2.47:
        return 2
    if avg_flood_depth_m <= 4.28:
        return 3
    if avg_flood_depth_m <= 7.65:
        return 4
    return 5


def calculate_ndwi(green_band: float, nir_band: float) -> float:
    """
    Normalized Difference Water Index. Source: McFeeters (1996).
    Formula: (Green - NIR) / (Green + NIR).
    Inputs must be between 0 and 1. Returns value between -1 and 1.
    Positive values indicate water presence; negative indicate dry land.
    """
    try:
        return (green_band - nir_band) / (green_band + nir_band)
    except ZeroDivisionError:
        return 0.0


def calculate_mndwi(green_band: float, swir_band: float) -> float:
    """
    Modified NDWI. Source: Xu (2006).
    Formula: (Green - SWIR) / (Green + SWIR).
    Better than NDWI for urban water body detection.
    Inputs must be between 0 and 1. Returns value between -1 and 1.
    """
    try:
        return (green_band - swir_band) / (green_band + swir_band)
    except ZeroDivisionError:
        return 0.0


def calculate_flood_inundation_index(
    ndwi: float,
    mndwi: float,
    flood_frequency: float,
) -> float:
    """
    Composite Flood Severity Index (FSI).
    Normalizes NDWI and MNDWI from [-1,1] to [0,1] using (val + 1) / 2.
    Formula: FSI = 0.35 * norm_ndwi + 0.35 * norm_mndwi + 0.30 * flood_frequency.
    flood_frequency: fraction of time (0-1) area shows water presence historically.
    Returns FSI between 0 and 1. Higher = more flood risk.
    """
    norm_ndwi = (ndwi + 1.0) / 2.0
    norm_mndwi = (mndwi + 1.0) / 2.0
    fsi = 0.35 * norm_ndwi + 0.35 * norm_mndwi + 0.30 * flood_frequency
    return max(0.0, min(1.0, fsi))
