# Saved ML Models

This directory stores trained ML model files for TerraWatch.

## Training the Soil Ensemble Model

The soil prediction model uses a Random Forest + XGBoost ensemble trained on
data from the [ISRIC SoilGrids](https://soilgrids.org/) API.

### Prerequisites

```bash
pip install scikit-learn joblib httpx numpy xgboost
```

### Train the model

```bash
cd backend/ml
python train_soil_model.py --n-points 5000 --output-dir saved_models
```

Arguments:
- `--n-points`: Number of global grid points to sample (default: 5000)
- `--output-dir`: Where to save the model (default: `saved_models/`)

### Output files

- `soil_ensemble.joblib` — Trained model, scaler, and metadata
- `model_metrics.json` — Cross-validation metrics for each property

### Notes

- Training requires internet access (fetches from ISRIC SoilGrids API).
- ISRIC API has rate limits; training 5000 points may take 30-60 minutes.
- The model is loaded automatically by `backend/app/models/soil_model.py`.
- If no model file exists, the app falls back to analytical estimation.
