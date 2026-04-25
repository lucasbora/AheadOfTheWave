from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    CDSE_USER: str = ""
    CDSE_PASSWORD: str = ""
    ANTHROPIC_API_KEY: str = ""
    ROMANIA_GOVERNANCE_SCORE: float = 0.3
    DEFAULT_COUNTRY: str = "RO"
    # Finland / CASSINI
    KAJAANI_LAT: float = 64.2245
    KAJAANI_LON: float = 27.7177
    FINLAND_LUMI_VALIDATION_THRESHOLD: float = 0.90

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

ROMANIA_DEFAULTS: dict = {
    "depletion_ratio": 0.35,
    "annual_depletion_pct": 30.0,
    "dry_year_months": 5,
    "seasonal_months": 3,
    "groundwater_change_mm": -25.0,
    "spei_dry_proportion_10yr": 0.25,
    "spei_dry_proportion_3yr": 0.20,
    "flood_events_count": 8,
    "avg_flood_depth_m": 3.5,
    "bod_mg_per_l": 3.0,
    "nitrate_mg_per_l": 0.6,
    "salinity_tds_mg_l": 180.0,
    "protection_return_period": 100,
    "governance_score": 0.3,
    "iwrm_policy_exists": True,
    "iwrm_in_law": True,
    "water_authority_exists": True,
    "water_authority_has_enforcement": True,
    "clean_water_standards_penalties": True,
    "wastewater_penalties": True,
    "wetland_harm_penalties": True,
    "water_management_plans_required": True,
    "plans_enforceable": False,
    "monitoring_water_quality": True,
    "flood_disaster_framework": True,
}
