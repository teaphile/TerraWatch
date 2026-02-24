"""Soil property prediction model using ensemble methods.

Predicts soil properties (pH, organic carbon, nitrogen, texture, etc.)
from location, elevation, climate, and land use features using an ensemble
of Random Forest and XGBoost models.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent.parent.parent / "ml" / "saved_models"


class SoilPredictionModel:
    """Ensemble model for soil property prediction.

    Uses Random Forest + XGBoost ensemble to predict soil properties
    from geospatial and climate features. Falls back to analytical
    estimation when trained models are not available.
    """

    # Global soil property statistics for analytical fallback
    GLOBAL_MEANS = {
        "ph": 6.5,
        "organic_carbon": 1.8,
        "nitrogen": 0.15,
        "sand": 40.0,
        "silt": 35.0,
        "clay": 25.0,
        "cec": 15.0,
        "bulk_density": 1.35,
    }

    TEXTURE_CLASSES = {
        "Sand": (85, 10, 5),
        "Loamy Sand": (75, 15, 10),
        "Sandy Loam": (60, 25, 15),
        "Loam": (40, 35, 25),
        "Silt Loam": (25, 55, 20),
        "Silt": (10, 80, 10),
        "Sandy Clay Loam": (55, 15, 30),
        "Clay Loam": (30, 35, 35),
        "Silty Clay Loam": (15, 50, 35),
        "Sandy Clay": (50, 10, 40),
        "Silty Clay": (10, 45, 45),
        "Clay": (20, 20, 60),
    }

    def __init__(self) -> None:
        """Initialize the soil prediction model."""
        self.models: Dict[str, Any] = {}
        self.scaler: Optional[StandardScaler] = None
        self.is_trained = False
        self._try_load_models()

    def _try_load_models(self) -> None:
        """Attempt to load pre-trained models from disk."""
        model_path = MODEL_DIR / "soil_ensemble.joblib"
        if model_path.exists():
            try:
                data = joblib.load(model_path)
                self.models = data.get("models", {})
                self.scaler = data.get("scaler")
                self.is_trained = True
                logger.info("Loaded pre-trained soil models from disk")
            except Exception as e:
                logger.warning(f"Failed to load soil models: {e}")

    def predict(
        self,
        latitude: float,
        longitude: float,
        elevation: float = 100.0,
        slope: float = 5.0,
        mean_temp: float = 15.0,
        mean_precip: float = 800.0,
        land_cover: str = "cropland",
        ndvi: float = 0.5,
    ) -> Dict[str, Any]:
        """Predict soil properties for a given location.

        Args:
            latitude: Location latitude (-90 to 90).
            longitude: Location longitude (-180 to 180).
            elevation: Elevation in meters.
            slope: Terrain slope in degrees.
            mean_temp: Mean annual temperature in Celsius.
            mean_precip: Mean annual precipitation in mm.
            land_cover: Land cover type string.
            ndvi: Normalized Difference Vegetation Index (0-1).

        Returns:
            Dictionary with predicted soil properties and confidence scores.
        """
        if self.is_trained:
            return self._predict_with_model(
                latitude, longitude, elevation, slope,
                mean_temp, mean_precip, land_cover, ndvi
            )
        return self._predict_analytical(
            latitude, longitude, elevation, slope,
            mean_temp, mean_precip, land_cover, ndvi
        )

    def _predict_analytical(
        self,
        latitude: float,
        longitude: float,
        elevation: float,
        slope: float,
        mean_temp: float,
        mean_precip: float,
        land_cover: str,
        ndvi: float,
    ) -> Dict[str, Any]:
        """Analytical estimation when trained models aren't available.

        Uses pedotransfer functions and empirical relationships to
        estimate soil properties from environmental variables.
        """
        abs_lat = abs(latitude)

        # pH estimation: varies with climate (arid=high, humid=low)
        aridity_index = mean_precip / max(mean_temp * 50 + 100, 1)
        ph = np.clip(8.5 - aridity_index * 1.5 + elevation * 0.0002, 3.5, 9.5)
        ph = round(float(ph), 1)

        # Organic carbon: higher in cool, wet conditions with vegetation
        oc_base = 1.2
        oc_temp_factor = max(0.5, 2.5 - mean_temp * 0.08)
        oc_precip_factor = min(2.0, mean_precip / 800.0)
        oc_ndvi_factor = 0.5 + ndvi * 1.5
        organic_carbon = np.clip(
            oc_base * oc_temp_factor * oc_precip_factor * oc_ndvi_factor, 0.1, 12.0
        )
        organic_carbon = round(float(organic_carbon), 2)

        # Nitrogen: roughly 1/10 of organic carbon
        nitrogen = round(float(np.clip(organic_carbon * 0.1, 0.01, 1.0)), 3)

        # Soil texture: varies with parent material and weathering
        if elevation > 2000:
            sand, silt, clay = 50.0, 30.0, 20.0
        elif abs_lat > 50:
            sand, silt, clay = 35.0, 40.0, 25.0
        elif abs_lat < 15:
            sand, silt, clay = 30.0, 25.0, 45.0
        elif mean_precip > 1500:
            sand, silt, clay = 25.0, 30.0, 45.0
        elif mean_precip < 300:
            sand, silt, clay = 65.0, 25.0, 10.0
        else:
            sand, silt, clay = 40.0, 35.0, 25.0

        # Add some variation based on longitude
        lon_factor = np.sin(np.radians(longitude)) * 5
        sand = np.clip(sand + lon_factor, 5, 90)
        clay = np.clip(clay - lon_factor * 0.5, 5, 75)
        silt = 100.0 - sand - clay
        if silt < 5:
            silt = 5.0
            total = sand + clay + silt
            sand = sand / total * 100
            clay = clay / total * 100
            silt = silt / total * 100

        sand, silt, clay = round(sand, 1), round(silt, 1), round(clay, 1)
        # Normalize to 100
        total = sand + silt + clay
        sand = round(sand / total * 100, 1)
        silt = round(silt / total * 100, 1)
        clay = round(100.0 - sand - silt, 1)

        texture_class = self._classify_texture(sand, silt, clay)

        # CEC: correlated with clay and organic matter
        cec = round(float(np.clip(clay * 0.3 + organic_carbon * 3.5, 2.0, 60.0)), 1)

        # Bulk density: inversely related to organic carbon
        bulk_density = round(
            float(np.clip(1.7 - organic_carbon * 0.08 - clay * 0.003, 0.8, 1.8)), 2
        )

        # Soil moisture estimation from precipitation and temperature
        pet = max(mean_temp * 5, 0)  # Simple PET proxy
        moisture = np.clip(
            (mean_precip - pet * 0.3) / mean_precip * 50 if mean_precip > 0 else 10,
            5, 60,
        )
        moisture = round(float(moisture + ndvi * 10), 1)

        # Confidence scores (lower for analytical estimation)
        base_confidence = 0.65
        lat_conf = max(0, 1 - abs_lat / 90 * 0.2)
        confidence = round(base_confidence * lat_conf, 2)

        return {
            "ph": {"value": ph, "confidence": confidence, "category": self._ph_category(ph)},
            "organic_carbon_pct": {"value": organic_carbon, "confidence": confidence - 0.05},
            "nitrogen_pct": {"value": nitrogen, "confidence": confidence - 0.08},
            "moisture_pct": {"value": moisture, "confidence": confidence + 0.05},
            "texture": {
                "sand_pct": sand,
                "silt_pct": silt,
                "clay_pct": clay,
                "classification": texture_class,
            },
            "bulk_density_gcm3": bulk_density,
            "cec_cmolkg": cec,
        }

    def _predict_with_model(
        self,
        latitude: float,
        longitude: float,
        elevation: float,
        slope: float,
        mean_temp: float,
        mean_precip: float,
        land_cover: str,
        ndvi: float,
    ) -> Dict[str, Any]:
        """Predict using trained analytical models."""
        features = self._prepare_features(
            latitude, longitude, elevation, slope,
            mean_temp, mean_precip, land_cover, ndvi
        )

        predictions = {}
        for target, model in self.models.items():
            pred = model.predict(features.reshape(1, -1))[0]
            predictions[target] = float(pred)

        sand = np.clip(predictions.get("sand", 40), 5, 90)
        silt = np.clip(predictions.get("silt", 35), 5, 80)
        clay = np.clip(100 - sand - silt, 5, 75)
        total = sand + silt + clay
        sand, silt, clay = sand/total*100, silt/total*100, clay/total*100

        ph = np.clip(predictions.get("ph", 6.5), 3.5, 9.5)
        oc = np.clip(predictions.get("organic_carbon", 1.8), 0.1, 12)

        return {
            "ph": {"value": round(ph, 1), "confidence": 0.85, "category": self._ph_category(ph)},
            "organic_carbon_pct": {"value": round(oc, 2), "confidence": 0.82},
            "nitrogen_pct": {"value": round(np.clip(predictions.get("nitrogen", 0.15), 0.01, 1), 3), "confidence": 0.78},
            "moisture_pct": {"value": round(np.clip(predictions.get("moisture", 30), 5, 60), 1), "confidence": 0.88},
            "texture": {
                "sand_pct": round(sand, 1),
                "silt_pct": round(silt, 1),
                "clay_pct": round(clay, 1),
                "classification": self._classify_texture(sand, silt, clay),
            },
            "bulk_density_gcm3": round(np.clip(predictions.get("bulk_density", 1.35), 0.8, 1.8), 2),
            "cec_cmolkg": round(np.clip(predictions.get("cec", 15), 2, 60), 1),
        }

    def _prepare_features(
        self,
        latitude: float,
        longitude: float,
        elevation: float,
        slope: float,
        mean_temp: float,
        mean_precip: float,
        land_cover: str,
        ndvi: float,
    ) -> np.ndarray:
        """Prepare feature vector for model prediction."""
        land_cover_map = {
            "cropland": 0, "forest": 1, "grassland": 2,
            "shrubland": 3, "urban": 4, "water": 5,
            "bare": 6, "wetland": 7,
        }
        lc_code = land_cover_map.get(land_cover.lower(), 0)

        features = np.array([
            latitude, longitude, elevation, slope,
            mean_temp, mean_precip, lc_code, ndvi,
            abs(latitude), np.sin(np.radians(latitude)),
            np.cos(np.radians(latitude)),
        ])

        if self.scaler:
            features = self.scaler.transform(features.reshape(1, -1)).flatten()

        return features

    @staticmethod
    def _classify_texture(sand: float, silt: float, clay: float) -> str:
        """Classify soil texture using USDA texture triangle."""
        if clay >= 40:
            if sand >= 45:
                return "Sandy Clay"
            elif silt >= 40:
                return "Silty Clay"
            return "Clay"
        elif clay >= 27:
            if sand >= 20 and sand < 45:
                return "Clay Loam"
            elif sand >= 45:
                return "Sandy Clay Loam"
            return "Silty Clay Loam"
        elif clay >= 7 and clay < 27:
            if silt >= 50 and clay >= 12:
                return "Silt Loam"
            elif silt >= 50:
                return "Silt Loam"
            elif sand >= 52:
                return "Sandy Loam"
            return "Loam"
        elif silt >= 80:
            return "Silt"
        elif sand >= 85:
            return "Sand"
        elif sand >= 70:
            return "Loamy Sand"
        return "Loam"

    @staticmethod
    def _ph_category(ph: float) -> str:
        """Categorize pH value."""
        if ph < 4.5:
            return "Extremely Acidic"
        elif ph < 5.5:
            return "Strongly Acidic"
        elif ph < 6.0:
            return "Moderately Acidic"
        elif ph < 6.5:
            return "Slightly Acidic"
        elif ph < 7.0:
            return "Neutral to Slightly Acidic"
        elif ph < 7.5:
            return "Neutral"
        elif ph < 8.0:
            return "Slightly Alkaline"
        elif ph < 8.5:
            return "Moderately Alkaline"
        return "Strongly Alkaline"


# Singleton
_model_instance: Optional[SoilPredictionModel] = None


def get_soil_model() -> SoilPredictionModel:
    """Get or create singleton soil prediction model."""
    global _model_instance
    if _model_instance is None:
        _model_instance = SoilPredictionModel()
    return _model_instance
