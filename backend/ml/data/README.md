# Training Data

This directory is for storing downloaded training data (optional).

## Data Sources

### ISRIC SoilGrids v2.0
- URL: https://rest.isric.org/soilgrids/v2.0
- Coverage: Global, 250m resolution
- Properties: pH, SOC, nitrogen, sand, silt, clay, CEC, bulk density
- License: CC-BY 4.0

The `train_soil_model.py` script fetches data directly from the API.
No pre-downloaded data files are required.

### WorldClim 2.1 (for climate features)
- URL: https://www.worldclim.org/data/worldclim21.html
- Coverage: Global bioclimatic variables
- Used for feature enrichment during training
