"""RUSLE-based soil erosion risk calculator.

Implements the Revised Universal Soil Loss Equation:
A = R × K × LS × C × P

where:
- A: estimated average soil loss (tons/ha/year)
- R: rainfall erosivity factor
- K: soil erodibility factor
- LS: slope length and steepness factor
- C: cover management factor
- P: support practice factor
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ErosionResult:
    """Result of RUSLE erosion calculation."""
    soil_loss_tons_ha_yr: float
    risk_level: str
    R: float
    K: float
    LS: float
    C: float
    P: float


class ErosionModel:
    """RUSLE-based soil erosion risk calculator.

    Computes annual soil loss and classifies erosion risk
    using the Revised Universal Soil Loss Equation.
    """

    RISK_THRESHOLDS = {
        "Very Low": (0, 2),
        "Low": (2, 5),
        "Moderate": (5, 10),
        "High": (10, 20),
        "Very High": (20, 50),
        "Severe": (50, float("inf")),
    }

    def calculate(
        self,
        annual_precip_mm: float,
        sand_pct: float,
        silt_pct: float,
        clay_pct: float,
        organic_carbon_pct: float,
        slope_pct: float,
        slope_length_m: float = 100.0,
        land_cover: str = "cropland",
        ndvi: float = 0.5,
        conservation_practice: str = "none",
    ) -> ErosionResult:
        """Calculate RUSLE soil erosion estimate.

        Args:
            annual_precip_mm: Mean annual precipitation in mm.
            sand_pct: Sand content percentage.
            silt_pct: Silt content percentage.
            clay_pct: Clay content percentage.
            organic_carbon_pct: Organic carbon percentage.
            slope_pct: Slope as percentage (rise/run * 100).
            slope_length_m: Slope length in meters.
            land_cover: Land cover type.
            ndvi: NDVI value (0-1).
            conservation_practice: Conservation practice type.

        Returns:
            ErosionResult with calculated soil loss and risk classification.
        """
        R = self._calculate_r_factor(annual_precip_mm)
        K = self._calculate_k_factor(sand_pct, silt_pct, clay_pct, organic_carbon_pct)
        LS = self._calculate_ls_factor(slope_pct, slope_length_m)
        C = self._calculate_c_factor(land_cover, ndvi)
        P = self._calculate_p_factor(conservation_practice, slope_pct)

        A = R * K * LS * C * P
        A = max(0, round(A, 2))

        risk_level = self._classify_risk(A)

        return ErosionResult(
            soil_loss_tons_ha_yr=A,
            risk_level=risk_level,
            R=round(R, 1),
            K=round(K, 4),
            LS=round(LS, 2),
            C=round(C, 3),
            P=round(P, 2),
        )

    def _calculate_r_factor(self, annual_precip_mm: float) -> float:
        """Calculate rainfall erosivity factor.

        Uses a modified Fournier index approximation.
        R = 0.0483 * P^1.61 (for annual precipitation P in mm)
        """
        if annual_precip_mm <= 0:
            return 0.0
        # Modified Fournier-based approximation
        R = 0.0483 * (annual_precip_mm ** 1.61)
        return max(0, min(R, 20000))

    def _calculate_k_factor(
        self,
        sand_pct: float,
        silt_pct: float,
        clay_pct: float,
        organic_carbon_pct: float,
    ) -> float:
        """Calculate soil erodibility factor.

        Uses the Williams (1995) modified equation:
        K = f_csand * f_cl_si * f_orgc * f_hisand
        """
        organic_matter_pct = organic_carbon_pct * 1.724

        # Factor for high sand content
        f_csand = (
            0.2
            + 0.3
            * math.exp(-0.0256 * sand_pct * (1 - silt_pct / 100))
        )

        # Factor for clay to silt ratio
        cl_si = silt_pct / max(clay_pct + silt_pct, 0.01)
        f_cl_si = (cl_si / (cl_si + math.exp(2.478 - 30.59 * cl_si))) if cl_si < 0.7 else 0.7

        # Factor for organic carbon
        oc = organic_carbon_pct
        f_orgc = 1.0 - (0.25 * oc / (oc + math.exp(3.72 - 2.95 * oc)))

        # Factor for high sand content
        sn = sand_pct / 100
        f_hisand = 1.0 - (0.7 * (1 - sn) / ((1 - sn) + math.exp(-5.51 + 22.9 * (1 - sn))))

        K = f_csand * f_cl_si * f_orgc * f_hisand
        return max(0.0, min(K, 0.8))

    def _calculate_ls_factor(
        self, slope_pct: float, slope_length_m: float
    ) -> float:
        """Calculate slope length and steepness factor.

        Uses the McCool et al. (1987, 1989) equations.
        LS = (slope_length / 22.13)^m * (65.41 * sin²θ + 4.56 * sinθ + 0.065)
        """
        if slope_length_m <= 0:
            slope_length_m = 22.13

        slope_rad = math.atan(slope_pct / 100)
        sin_slope = math.sin(slope_rad)

        # Exponent m based on slope
        if slope_pct < 1:
            m = 0.2
        elif slope_pct < 3:
            m = 0.3
        elif slope_pct < 5:
            m = 0.4
        else:
            m = 0.5

        L = (slope_length_m / 22.13) ** m

        if slope_pct < 9:
            S = 10.8 * sin_slope + 0.03
        else:
            S = 16.8 * sin_slope - 0.50

        LS = L * S
        return max(0.01, min(LS, 100))

    def _calculate_c_factor(self, land_cover: str, ndvi: float = 0.5) -> float:
        """Calculate cover management factor.

        Based on land cover type and NDVI.
        """
        cover_factors = {
            "forest": 0.001,
            "dense_forest": 0.001,
            "grassland": 0.01,
            "shrubland": 0.02,
            "cropland": 0.35,
            "agriculture": 0.35,
            "bare": 1.0,
            "urban": 0.01,
            "water": 0.0,
            "wetland": 0.01,
            "pasture": 0.02,
        }

        base_c = cover_factors.get(land_cover.lower(), 0.15)

        # Adjust based on NDVI (more vegetation = less erosion)
        if ndvi > 0:
            ndvi_adjustment = max(0.1, 1.0 - ndvi * 1.5)
            C = base_c * ndvi_adjustment
        else:
            C = base_c

        return max(0.0, min(C, 1.0))

    def _calculate_p_factor(
        self, practice: str, slope_pct: float = 0
    ) -> float:
        """Calculate support practice factor.

        Based on conservation practice type.
        """
        practice_factors = {
            "none": 1.0,
            "contour_farming": 0.5,
            "strip_cropping": 0.3,
            "terracing": 0.15,
            "grassed_waterways": 0.4,
            "no_till": 0.25,
            "mulching": 0.3,
            "cover_crops": 0.35,
        }

        P = practice_factors.get(practice.lower(), 1.0)

        # Adjust for steep slopes (practices less effective)
        if slope_pct > 25 and P < 1.0:
            P = min(1.0, P * 1.5)

        return P

    def _classify_risk(self, soil_loss: float) -> str:
        """Classify erosion risk level based on soil loss."""
        for level, (low, high) in self.RISK_THRESHOLDS.items():
            if low <= soil_loss < high:
                return level
        return "Severe"


# Singleton
_model_instance: Optional[ErosionModel] = None


def get_erosion_model() -> ErosionModel:
    """Get or create singleton erosion model."""
    global _model_instance
    if _model_instance is None:
        _model_instance = ErosionModel()
    return _model_instance
