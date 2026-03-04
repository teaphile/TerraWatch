#!/usr/bin/env python3
"""Train soil property prediction model from ISRIC SoilGrids data.

Downloads training data from ISRIC SoilGrids API for a representative
global grid and trains a Random Forest + XGBoost ensemble for each
target soil property.

Usage:
    python train_soil_model.py [--n-points 5000] [--output-dir saved_models]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

# Try importing XGBoost (optional, falls back to extra Random Forests)
try:
    from xgboost import XGBRegressor
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    print("⚠️  XGBoost not installed — using Random Forest only ensemble")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

ISRIC_BASE = "https://rest.isric.org/soilgrids/v2.0/properties/query"

# Target properties and their ISRIC column names / units
TARGET_PROPS = {
    "ph": {"isric_name": "phh2o", "unit_conversion": 0.1, "description": "pH (H2O)"},
    "organic_carbon": {"isric_name": "soc", "unit_conversion": 0.01, "description": "SOC (dg/kg → %)"},
    "nitrogen": {"isric_name": "nitrogen", "unit_conversion": 0.001, "description": "Total N (cg/kg → %)"},
    "sand": {"isric_name": "sand", "unit_conversion": 0.1, "description": "Sand (g/kg → %)"},
    "silt": {"isric_name": "silt", "unit_conversion": 0.1, "description": "Silt (g/kg → %)"},
    "clay": {"isric_name": "clay", "unit_conversion": 0.1, "description": "Clay (g/kg → %)"},
    "cec": {"isric_name": "cec", "unit_conversion": 0.1, "description": "CEC (mmol/kg → cmol/kg)"},
    "bulk_density": {"isric_name": "bdod", "unit_conversion": 0.01, "description": "Bulk density (cg/cm³ → g/cm³)"},
}


def generate_global_grid(n_points: int = 5000) -> List[Tuple[float, float]]:
    """Generate a roughly uniform global grid of lat/lon points on land.

    Uses a simplified land mask to avoid ocean points.
    """
    import random
    random.seed(42)

    points = []
    attempts = 0
    max_attempts = n_points * 10

    while len(points) < n_points and attempts < max_attempts:
        lat = random.uniform(-60, 70)
        lon = random.uniform(-180, 180)
        attempts += 1

        # Simple land mask check
        if _is_land(lat, lon):
            points.append((round(lat, 2), round(lon, 2)))

    logger.info(f"Generated {len(points)} land grid points from {attempts} attempts")
    return points


def _is_land(lat: float, lon: float) -> bool:
    """Simple land mask check using continental bounding boxes."""
    # North America
    if 15 <= lat <= 70 and -130 <= lon <= -60:
        return True
    # South America
    if -55 <= lat <= 15 and -80 <= lon <= -35:
        return True
    # Europe
    if 35 <= lat <= 70 and -10 <= lon <= 40:
        return True
    # Africa
    if -35 <= lat <= 37 and -20 <= lon <= 55:
        return True
    # Asia
    if 5 <= lat <= 75 and 40 <= lon <= 180:
        return True
    # Australia
    if -45 <= lat <= -10 and 110 <= lon <= 155:
        return True
    return False


async def fetch_isric_point(
    client: httpx.AsyncClient, lat: float, lon: float
) -> Optional[Dict[str, float]]:
    """Fetch soil properties from ISRIC SoilGrids for a single point."""
    try:
        resp = await client.get(
            ISRIC_BASE,
            params={
                "lon": lon,
                "lat": lat,
                "property": list({p["isric_name"] for p in TARGET_PROPS.values()}),
                "depth": "0-5cm",
                "value": "mean",
            },
            timeout=30.0,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        properties = data.get("properties", {})
        layers = properties.get("layers", [])

        result = {}
        for layer in layers:
            name = layer.get("name", "")
            depths = layer.get("depths", [])
            if depths:
                values = depths[0].get("values", {})
                mean_val = values.get("mean")
                if mean_val is not None:
                    result[name] = mean_val

        return result if len(result) >= 4 else None

    except Exception as e:
        logger.debug(f"ISRIC fetch failed for ({lat}, {lon}): {e}")
        return None


async def collect_training_data(
    points: List[Tuple[float, float]], batch_size: int = 5
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """Collect training data from ISRIC for all grid points.

    Returns:
        features: (N, 11) array of location/climate features
        targets: dict mapping property name → (N,) array of values
    """
    import asyncio

    features_list = []
    targets_dict = {name: [] for name in TARGET_PROPS}
    successful = 0

    async with httpx.AsyncClient() as client:
        for batch_start in range(0, len(points), batch_size):
            batch = points[batch_start:batch_start + batch_size]

            tasks = [fetch_isric_point(client, lat, lon) for lat, lon in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (lat, lon), result in zip(batch, results):
                if isinstance(result, Exception) or result is None:
                    continue

                # Build feature vector
                features_list.append(_build_features(lat, lon, result))

                # Convert ISRIC values to standard units
                for prop_name, prop_info in TARGET_PROPS.items():
                    isric_name = prop_info["isric_name"]
                    raw = result.get(isric_name)
                    if raw is not None:
                        targets_dict[prop_name].append(raw * prop_info["unit_conversion"])
                    else:
                        targets_dict[prop_name].append(np.nan)

                successful += 1

            if batch_start % 100 == 0:
                logger.info(f"Progress: {batch_start}/{len(points)} points, {successful} successful")

            # Rate limiting for ISRIC API
            await asyncio.sleep(0.5)

    features = np.array(features_list)
    targets = {k: np.array(v) for k, v in targets_dict.items()}

    logger.info(f"Collected {successful} training samples with {features.shape[1]} features")
    return features, targets


def _build_features(lat: float, lon: float, isric_data: dict = None) -> List[float]:
    """Build feature vector matching SoilPredictionModel._prepare_features()."""
    abs_lat = abs(lat)

    # Estimate climate from latitude (simplified for training)
    mean_temp = 27.0 - abs_lat * 0.55
    if abs_lat < 15:
        mean_precip = 1800
    elif abs_lat < 30:
        mean_precip = 600
    elif abs_lat < 50:
        mean_precip = 800
    else:
        mean_precip = 500

    elevation = 500  # Placeholder
    slope = 5.0
    lc_code = 0  # cropland default
    ndvi = 0.5

    return [
        lat, lon, elevation, slope,
        mean_temp, mean_precip, lc_code, ndvi,
        abs_lat, np.sin(np.radians(lat)),
        np.cos(np.radians(lat)),
    ]


def train_ensemble(
    X: np.ndarray, y: np.ndarray, property_name: str
) -> Tuple[Any, Dict[str, float]]:
    """Train an ensemble model for a single soil property.

    Returns:
        (model, metrics_dict)
    """
    # Remove NaN target rows
    mask = ~np.isnan(y)
    X_clean = X[mask]
    y_clean = y[mask]

    if len(y_clean) < 50:
        logger.warning(f"Insufficient data for {property_name}: {len(y_clean)} samples")
        return None, {}

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_clean)

    # Train Random Forest
    rf = RandomForestRegressor(
        n_estimators=200, max_depth=15, min_samples_split=5,
        random_state=42, n_jobs=-1,
    )

    if HAS_XGBOOST:
        xgb = XGBRegressor(
            n_estimators=200, max_depth=8, learning_rate=0.1,
            random_state=42, n_jobs=-1, verbosity=0,
        )
        # Cross-validate both
        rf_scores = cross_val_score(rf, X_scaled, y_clean, cv=5, scoring="r2")
        xgb_scores = cross_val_score(xgb, X_scaled, y_clean, cv=5, scoring="r2")

        # Train on full data
        rf.fit(X_scaled, y_clean)
        xgb.fit(X_scaled, y_clean)

        # Simple average ensemble
        rf_pred = rf.predict(X_scaled)
        xgb_pred = xgb.predict(X_scaled)
        ensemble_pred = (rf_pred + xgb_pred) / 2
    else:
        rf_scores = cross_val_score(rf, X_scaled, y_clean, cv=5, scoring="r2")
        rf.fit(X_scaled, y_clean)
        ensemble_pred = rf.predict(X_scaled)
        xgb_scores = rf_scores
        xgb = None

    metrics = {
        "n_samples": len(y_clean),
        "r2_cv_rf": round(float(np.mean(rf_scores)), 4),
        "r2_cv_xgb": round(float(np.mean(xgb_scores)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_clean, ensemble_pred))), 4),
        "mae": round(float(mean_absolute_error(y_clean, ensemble_pred)), 4),
        "r2_train": round(float(r2_score(y_clean, ensemble_pred)), 4),
    }

    logger.info(f"  {property_name}: R²(CV)={metrics['r2_cv_rf']:.3f} (RF), "
                f"RMSE={metrics['rmse']:.3f}, MAE={metrics['mae']:.3f}")

    return {"rf": rf, "xgb": xgb, "scaler": scaler}, metrics


async def main(n_points: int, output_dir: str) -> None:
    """Main training pipeline."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"=== TerraWatch Soil Model Training ===")
    logger.info(f"Target: {n_points} training points")
    logger.info(f"Output: {output_path}")

    # 1. Generate grid
    logger.info("Generating global land grid...")
    points = generate_global_grid(n_points)

    # 2. Fetch data from ISRIC
    logger.info("Fetching soil data from ISRIC SoilGrids...")
    features, targets = await collect_training_data(points)

    if len(features) < 100:
        logger.error(f"Only {len(features)} valid samples collected. Need at least 100.")
        logger.info("ISRIC API may be rate-limited or unavailable. Try again later.")
        sys.exit(1)

    # 3. Train models
    logger.info(f"Training ensemble models on {len(features)} samples...")
    models = {}
    all_metrics = {}

    # Fit one shared scaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features)

    for prop_name in TARGET_PROPS:
        logger.info(f"Training: {prop_name}")
        model_data, metrics = train_ensemble(features, targets[prop_name], prop_name)
        if model_data:
            models[prop_name] = model_data["rf"]  # Store RF as primary
            all_metrics[prop_name] = metrics

    # 4. Save model
    model_file = output_path / "soil_ensemble.joblib"
    save_data = {
        "models": models,
        "scaler": scaler,
        "feature_names": [
            "latitude", "longitude", "elevation", "slope",
            "mean_temp", "mean_precip", "land_cover_code", "ndvi",
            "abs_latitude", "sin_latitude", "cos_latitude",
        ],
        "target_properties": list(TARGET_PROPS.keys()),
        "n_training_samples": len(features),
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    joblib.dump(save_data, model_file)
    logger.info(f"Saved model to {model_file}")

    # 5. Save metrics
    metrics_file = output_path / "model_metrics.json"
    with open(metrics_file, "w") as f:
        json.dump(all_metrics, f, indent=2)
    logger.info(f"Saved metrics to {metrics_file}")

    # Summary
    logger.info("\n=== Training Summary ===")
    for prop, m in all_metrics.items():
        logger.info(f"  {prop:20s} | R²(CV)={m['r2_cv_rf']:.3f} | RMSE={m['rmse']:.3f} | n={m['n_samples']}")
    logger.info("Training complete!")


if __name__ == "__main__":
    import asyncio

    parser = argparse.ArgumentParser(description="Train TerraWatch soil prediction model")
    parser.add_argument("--n-points", type=int, default=5000, help="Number of global grid training points")
    parser.add_argument("--output-dir", type=str, default="saved_models", help="Output directory for model files")
    args = parser.parse_args()

    asyncio.run(main(args.n_points, args.output_dir))
