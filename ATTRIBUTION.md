# Attributions and third-party data licences

TerraWatch's own source code is released under the MIT licence (see
`LICENSE`). The application uses the following third-party data and software.

## Bundled datasets

### ETOPO1 / ETOPO10 elevation grid

`backend/app/data/static/elevation_grid.npz` is derived from the
ETOPO1 global relief model (NOAA National Centers for Environmental
Information, public domain), resampled to 10 arc-minutes by the
[`g2e/etopo10`](https://github.com/g2e/etopo10) project
(Copyright © 2017 Garrett Euler, MIT licence).

> ETOPO1 Global Relief Model, NOAA National Centers for Environmental
> Information, https://www.ngdc.noaa.gov/mgg/global/

### Köppen-Geiger climate grid

`backend/app/data/static/koppen_grid.npz` stores one Köppen-Geiger class per
0.5° cell. The class assignment is derived from the present-day
Köppen-Geiger maps of **Beck et al. (2018)**, which are licensed under
Creative Commons Attribution 4.0 (CC BY 4.0). The grid was extracted from
the [`koppen-climate-lookup`](https://www.npmjs.com/package/koppen-climate-lookup)
package (ISC licence).

> Beck, H. E., Zimmermann, N. E., McVicar, T. R., Vergopolan, N., Berg, A.,
> & Wood, E. F. (2018). Present and future Köppen-Geiger climate
> classification maps at 1-km resolution. *Scientific Data*, 5, 180214.
> https://doi.org/10.1038/sdata.2018.214

`backend/app/data/static/climate_class_normals.json` contains representative
annual statistics for each class. These values were compiled for this
project from published climate-class ranges and are not a redistribution of
the Beck et al. raster values.

### World boundaries (offline map fallback)

The frontend bundles `world-atlas` country outlines (Natural Earth 1:110m,
public domain; `world-atlas` ISC licence, Copyright © Mike Bostock) so the
map remains usable when the raster tile CDN is unreachable.

## Live data services

| Service | Data | Terms |
|---------|------|-------|
| [Open-Meteo](https://open-meteo.com/) | Forecast, archive, elevation, soil moisture | CC BY 4.0; non-commercial free tier |
| [USGS Earthquake Hazards Program](https://earthquake.usgs.gov/) | Real-time earthquake catalogue | Public domain |
| [ISRIC SoilGrids](https://soilgrids.org/) | Global soil properties | CC BY 4.0 |
| [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) | Active fire detections | NASA open data |

Attribution is displayed in the UI where required, and every API response
records which source produced each value in its `data_quality` block.

## Software

| Project | Licence |
|---------|---------|
| FastAPI, Starlette, Pydantic | MIT |
| SQLAlchemy | MIT |
| httpx | BSD-3-Clause |
| NumPy, scikit-learn | BSD-3-Clause |
| React, React DOM | MIT |
| Leaflet | BSD-2-Clause |
| react-leaflet | MIT |
| Recharts | MIT |
| Tailwind CSS | MIT |
| Vite | MIT |
| Lucide icons | ISC |
