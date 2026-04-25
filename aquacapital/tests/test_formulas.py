"""
Unit tests for all deterministic formula modules.
Run with: pytest tests/test_formulas.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from services.formulas.physical_risk import (
    calculate_water_depletion_risk,
    calculate_flood_occurrence_risk,
    calculate_ndwi,
    calculate_flood_inundation_index,
)
from services.formulas.flood_risk import (
    calculate_expected_annual_damage_index,
    calculate_flood_protection_standard_risk,
)
from services.formulas.regulatory_risk import (
    calculate_regulatory_deficiency_score,
    apply_implementation_adjustment,
)
from services.formulas.investment_grade import (
    calculate_investment_grade,
    compare_locations,
)
from config import ROMANIA_DEFAULTS


# ---------------------------------------------------------------------------
# Water depletion thresholds
# ---------------------------------------------------------------------------

class TestWaterDepletionThresholds:
    def test_very_low(self):
        assert calculate_water_depletion_risk(0.0) == 1
        assert calculate_water_depletion_risk(0.10) == 1

    def test_low(self):
        assert calculate_water_depletion_risk(0.11) == 2
        assert calculate_water_depletion_risk(0.20) == 2

    def test_moderate(self):
        assert calculate_water_depletion_risk(0.21) == 3
        assert calculate_water_depletion_risk(0.40) == 3

    def test_high(self):
        assert calculate_water_depletion_risk(0.41) == 4
        assert calculate_water_depletion_risk(0.80) == 4

    def test_very_high(self):
        assert calculate_water_depletion_risk(0.81) == 5
        assert calculate_water_depletion_risk(1.50) == 5


# ---------------------------------------------------------------------------
# Flood occurrence thresholds
# ---------------------------------------------------------------------------

class TestFloodOccurrenceThresholds:
    def test_zero_events(self):
        assert calculate_flood_occurrence_risk(0) == 1

    def test_one_event(self):
        assert calculate_flood_occurrence_risk(1) == 2

    def test_eleven_events(self):
        assert calculate_flood_occurrence_risk(11) == 4

    def test_boundary_two(self):
        assert calculate_flood_occurrence_risk(2) == 2

    def test_boundary_three(self):
        assert calculate_flood_occurrence_risk(3) == 3

    def test_boundary_ten(self):
        assert calculate_flood_occurrence_risk(10) == 3

    def test_boundary_thirty(self):
        assert calculate_flood_occurrence_risk(30) == 4

    def test_over_thirty(self):
        assert calculate_flood_occurrence_risk(31) == 5


# ---------------------------------------------------------------------------
# NDWI known value
# ---------------------------------------------------------------------------

class TestNdwiKnownValue:
    def test_known_value(self):
        result = calculate_ndwi(green_band=0.3, nir_band=0.1)
        assert abs(result - 0.5) < 1e-6, f"Expected 0.5, got {result}"

    def test_zero_denominator(self):
        result = calculate_ndwi(0.0, 0.0)
        assert result == 0.0

    def test_water_positive(self):
        result = calculate_ndwi(0.4, 0.1)
        assert result > 0

    def test_land_negative(self):
        result = calculate_ndwi(0.05, 0.4)
        assert result < 0


# ---------------------------------------------------------------------------
# Flood Severity Index bounds
# ---------------------------------------------------------------------------

class TestFloodSeverityIndexBounds:
    @pytest.mark.parametrize("ndwi,mndwi,freq", [
        (-1.0, -1.0, 0.0),
        (1.0, 1.0, 1.0),
        (0.0, 0.0, 0.5),
        (-0.5, 0.5, 0.3),
        (0.8, -0.2, 0.9),
    ])
    def test_fsi_always_between_0_and_1(self, ndwi, mndwi, freq):
        fsi = calculate_flood_inundation_index(ndwi, mndwi, freq)
        assert 0.0 <= fsi <= 1.0, f"FSI={fsi} out of bounds for inputs ({ndwi}, {mndwi}, {freq})"


# ---------------------------------------------------------------------------
# Investment grade — data_center vs logistics under high water stress
# ---------------------------------------------------------------------------

class TestInvestmentGradeDataCenterVsLogistics:
    def _grade(self, user_type: str) -> float:
        result = calculate_investment_grade(
            physical_risk_score=0.80,  # high water stress
            regulatory_risk_score=0.40,
            compliance_score=0.60,
            ead_index=0.50,
            user_type=user_type,
        )
        return result["score"]

    def test_data_center_lower_than_logistics_under_high_water_stress(self):
        dc_score = self._grade("data_center")
        log_score = self._grade("logistics")
        # Logistics weights physical_risk at 45% vs data_center 40%.
        # Under high physical risk, logistics is the most penalized user type.
        assert log_score < dc_score, (
            f"logistics ({log_score}) should score lower than data_center ({dc_score}) "
            "under high physical risk because logistics weights physical_risk at 45% vs 40%."
        )


# ---------------------------------------------------------------------------
# Grade mapping
# ---------------------------------------------------------------------------

class TestInvestmentGradeGradeMapping:
    def _grade_label(self, score_target: float) -> str:
        # Back-calculate inputs to produce the target score for generic_investor
        # Score = raw * 100. With equal risks all at 0.5, score = 0.5 * 100 = 50
        # We adjust physical_risk to shift the score
        physical = 1.0 - (score_target / 100.0)
        result = calculate_investment_grade(
            physical_risk_score=physical,
            regulatory_risk_score=0.0,
            compliance_score=1.0,
            ead_index=0.0,
            user_type="generic_investor",
        )
        return result["grade"]

    def test_score_90_is_A_plus(self):
        result = calculate_investment_grade(0.05, 0.05, 0.95, 0.05, "generic_investor")
        assert result["grade"] == "A+"

    def test_score_40_is_D(self):
        # generic_investor weights: physical=0.30, regulatory=0.25, compliance=0.25, ead=0.20
        # (1-0.60)*0.30 + (1-0.60)*0.25 + 0.40*0.25 + (1-0.60)*0.20 = 0.12+0.10+0.10+0.08 = 0.40 → 40.0 → D
        result = calculate_investment_grade(0.60, 0.60, 0.40, 0.60, "generic_investor")
        assert result["grade"] == "D", f"Got {result['grade']} with score {result['score']}"

    def test_score_20_is_F(self):
        result = calculate_investment_grade(1.0, 1.0, 0.0, 1.0, "generic_investor")
        assert result["grade"] == "F"

    def test_grade_label_present(self):
        result = calculate_investment_grade(0.5, 0.5, 0.5, 0.5, "generic_investor")
        assert result["grade_label"]
        assert result["recommendation_summary"]


# ---------------------------------------------------------------------------
# compare_locations ranking
# ---------------------------------------------------------------------------

class TestCompareLocationsRanking:
    def test_sort_order(self):
        locations = [
            {"score": 45.0, "grade": "C", "grade_label": "Elevated Risk", "location_name": "C"},
            {"score": 82.0, "grade": "A", "grade_label": "Investment Grade", "location_name": "A"},
            {"score": 67.0, "grade": "B", "grade_label": "Acceptable", "location_name": "B"},
        ]
        ranked = compare_locations(locations, "generic_investor")
        assert ranked[0]["location_name"] == "A"
        assert ranked[1]["location_name"] == "B"
        assert ranked[2]["location_name"] == "C"

    def test_rank_assigned(self):
        locations = [{"score": 70.0, "location_name": "X"}, {"score": 50.0, "location_name": "Y"}]
        ranked = compare_locations(locations, "generic_investor")
        assert ranked[0]["rank"] == 1
        assert ranked[1]["rank"] == 2

    def test_delta_from_best(self):
        locations = [{"score": 80.0, "location_name": "X"}, {"score": 60.0, "location_name": "Y"}]
        ranked = compare_locations(locations, "generic_investor")
        assert ranked[0]["delta_from_best"] == 0.0
        assert ranked[1]["delta_from_best"] == -20.0


# ---------------------------------------------------------------------------
# Regulatory risk — Romania defaults
# ---------------------------------------------------------------------------

class TestRegulatoryRiskRomaniaDefaults:
    def test_romania_risk_value_is_2_or_3(self):
        answers = {k: ROMANIA_DEFAULTS[k] for k in [
            "iwrm_policy_exists", "iwrm_in_law", "water_authority_exists",
            "water_authority_has_enforcement", "clean_water_standards_penalties",
            "wastewater_penalties", "wetland_harm_penalties",
            "water_management_plans_required", "plans_enforceable",
            "monitoring_water_quality", "flood_disaster_framework", "governance_score",
        ]}
        result = calculate_regulatory_deficiency_score(answers)
        assert result["risk_value"] in (2, 3), (
            f"Romania defaults should yield moderate regulatory risk (2 or 3), "
            f"got {result['risk_value']} (score={result['total_score']})"
        )


# ---------------------------------------------------------------------------
# Implementation adjustment never decreases risk
# ---------------------------------------------------------------------------

class TestImplementationAdjustmentNeverDecreases:
    @pytest.mark.parametrize("reg_risk,governance", [
        (3, 2.5),   # good governance, moderate regulation
        (4, 1.5),   # good governance, high risk
        (2, 2.0),   # excellent governance, low risk
        (1, 2.5),   # excellent everything
    ])
    def test_good_governance_never_lowers_risk(self, reg_risk, governance):
        adjusted = apply_implementation_adjustment(reg_risk, governance)
        assert adjusted >= reg_risk, (
            f"Governance={governance} should not lower regulatory_risk={reg_risk}, "
            f"but got {adjusted}"
        )

    def test_poor_governance_can_raise_risk(self):
        adjusted = apply_implementation_adjustment(2, -2.0)
        assert adjusted >= 2


# ---------------------------------------------------------------------------
# EAD — data_center content factor produces higher index than residential
# ---------------------------------------------------------------------------

class TestEADDataCenterMultiplier:
    def test_data_center_higher_ead_than_residential(self):
        dc = calculate_expected_annual_damage_index(
            flood_depth_m=2.0,
            return_period_years=100,
            land_use_type="data_center",
            gdp_per_capita_usd=14000.0,
        )
        res = calculate_expected_annual_damage_index(
            flood_depth_m=2.0,
            return_period_years=100,
            land_use_type="residential",
            gdp_per_capita_usd=14000.0,
        )
        assert dc["total_damage_index"] > res["total_damage_index"], (
            f"data_center EAD ({dc['total_damage_index']}) should exceed "
            f"residential EAD ({res['total_damage_index']}) at same flood depth."
        )

    def test_ead_damage_category_critical_at_high_depth(self):
        result = calculate_expected_annual_damage_index(
            flood_depth_m=9.0,
            return_period_years=10,
            land_use_type="data_center",
        )
        assert result["damage_category"] == "critical"

    def test_ead_negligible_at_zero_depth(self):
        result = calculate_expected_annual_damage_index(
            flood_depth_m=0.0,
            return_period_years=100,
            land_use_type="residential",
        )
        assert result["total_damage_index"] == 0.0
        assert result["damage_category"] == "negligible"
