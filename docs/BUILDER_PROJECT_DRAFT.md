# AWS Builder Center project draft

Draft only. The public endpoint and short public demo video are still required before this is ready to submit to the map challenge. Do not paste the local API key into Builder Center.

## Title

Europe Warming & Population Atlas

## Description

Explore annual warming scenarios from EURO-CORDEX alongside GHSL 2020 population across Europe. Compare matched CMIP5 model ensembles for RCP 4.5 and RCP 8.5, then inspect the warming range and population estimate for each climate grid cell.

## Body

### What this map reveals

Climate models describe change across large grid cells, while population data shows where people live. This atlas puts those datasets on the same map so visitors can compare the patterns across Europe, switch between emissions scenarios and future periods, and inspect individual cells.

The map shows conditional model scenarios. It is not a weather forecast, a measure of personal exposure, or a health-risk estimate.

### Data

- **EURO-CORDEX CMIP5:** monthly 2-meter air temperature (`tas`) on the EUR-11 grid, paired between historical, RCP 4.5, and RCP 8.5 runs. The ensemble uses three driving models with the same CLMcom CCLM4-8-17 regional grid: CNRM-CERFACS-CNRM-CM5, ICHEC-EC-EARTH, and MPI-M-MPI-ESM-LR. A fourth catalog pair was excluded because its archive ends during 2099 and does not cover the full late-century period.
- **GHSL GHS-POP 2020:** gridded population counts from the European Commission Joint Research Centre.

Sources: [EURO-CORDEX on the Registry of Open Data on AWS](https://registry.opendata.aws/euro-cordex/) and [GHSL population on the Registry of Open Data on AWS](https://registry.opendata.aws/ghs-pop/).

### Processing and map

For each matched model pair, monthly temperatures are combined into day-weighted annual means. The pipeline calculates future-minus-baseline change against 1981–2000 for 2041–2060 and 2081–2100, then reports the ensemble median and 10th–90th percentile range. It supports each model's native calendar, including 360-day calendars.

GHSL pixel counts are assigned once to the climate cell containing each pixel center. The aggregated in-domain total is checked against the source pixels. The current archive contains 174,688 cells and preserves 1,014,002,935 residents within the climate-grid footprint. Population is context at climate-grid scale, not a precise local count.

The browser app uses React, TypeScript, MapLibre GL JS, and a PMTiles vector archive. Visitors can select RCP 4.5 or RCP 8.5, choose a future period, switch between warming and population layers, and click a cell to see values.

### AWS architecture

Amazon Location Service provides the basemap with a map-only API key restricted by referrer. The source datasets are public objects in Amazon S3. AWS CDK defines S3 and CloudFront hosting for the app and derived archive.

The local map and generated archive have been validated. The archive has **not** yet been uploaded to the CloudFront origin, so a public live-map URL is not available yet.

### Limitations

- RCP 4.5 and RCP 8.5 are conditional CMIP5 scenario pathways, not predictions.
- The ensemble range describes spread among these selected model runs; it is not a confidence interval.
- Annual means do not show heatwaves, daily extremes, urban heat islands, health effects, or future population.
- Population values are aggregated to climate-model cells and should not be interpreted as individual exposure.

### Attribution

EURO-CORDEX monthly CMIP5 2-meter air temperature. GHSL GHS-POP 2020, European Commission Joint Research Centre. Follow the source dataset terms and attribution requirements when redistributing derived data.

## Tags (5 maximum)

Amazon Location Service; Climate Data; Geospatial; Open Data; AWS CDK

## GitHub or GitLab repository

[Europe Warming & Population Atlas on GitHub](https://github.com/ramthaker/europe-warming-population-atlas). The repository contains the app, CDK infrastructure, and reproducible data pipeline; local credentials and the generated archive are excluded.

## Endpoint or live demo

Pending public hosting of the derived PMTiles archive and a correctly configured app build. The local address is `http://localhost:5173/` and is not publicly accessible.

## Demo video

Required for the challenge submission: add a public video link under three minutes showing the live map, scenario and period controls, population layer, and a clicked cell.

## Notebook

None.
