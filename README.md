# Europe's Warming and People Map

![Editorial map illustration of Europe with a subtle climate grid and warming gradient](docs/images/europe-warming-population-cover.jpg)

An interactive map for comparing EURO-CORDEX annual mean temperature scenarios with 2020 population distribution across the full EURO-CORDEX Europe domain.

The map is an exploration tool. It shows model scenarios, not a weather forecast or a health-risk assessment.

## Data and method

- **EURO-CORDEX CMIP5:** monthly 2 m air temperature (`tas`) from historical, RCP4.5, and RCP8.5 model runs. The build pipeline pairs each future run with its matching historical run, calculates future-minus-baseline annual mean anomalies, and summarizes matched models with the median and 10th/90th percentiles.
- The initial ensemble selects three EUR-11 pairs on the same CLMcom CCLM4-8-17 regional grid: CNRM-CERFACS-CNRM-CM5, ICHEC-EC-EARTH, and MPI-M-MPI-ESM-LR. The MOHC-HadGEM2-ES archive ends during 2099, so it is omitted to keep the same complete ensemble across all periods. The pipeline respects each run's native calendar, including 360-day calendars.
- **GHSL GHS-POP:** 2020 gridded residential population. Pixel-center assignment allocates each raster count once to a climate cell and verifies the total within the climate-grid footprint.
- Baseline: 1981–2000. Future windows: 2041–2060 and 2081–2100.
- Source datasets are public objects in AWS S3. CDK defines private S3 and CloudFront delivery for the app and archive; the generated archive is local and has not been uploaded to the public distribution.

Source attribution: EURO-CORDEX monthly CMIP5 2 m air temperature, accessed 2026-10-31; GHSL GHS-POP 2020 layer, European Commission Joint Research Centre, accessed 2026-10-31. The [GHSL registry](https://registry.opendata.aws/ghs-pop/) lists CC BY 4.0. Follow the [EURO-CORDEX registry](https://registry.opendata.aws/euro-cordex/) data-use terms and cite the source dataset as required before redistribution.

## Project structure

- `web/` — React, TypeScript, Vite, MapLibre GL JS interface.
- `pipeline/` — climate/population processing and PMTiles generation.
- `infra/` — AWS CDK TypeScript app for S3, CloudFront, Amazon Location map, and restricted public map key.
- `data/` — generated files (ignored by Git).
- `docs/DEMO.md` — under-three-minute recording outline.
- `docs/images/` — Builder Center cover art and high-level architecture diagram.

## High-level architecture

![Architecture: public S3 datasets flow through the Python pipeline into PMTiles and the MapLibre app; Amazon Location Service supplies the basemap, with S3 and CloudFront as the CDK delivery path](docs/images/architecture.svg)

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the data flow and the current publication status.

## Run the web app

1. Install Node.js 20 or later.
2. Copy `web/.env.example` to `web/.env.local` and set `VITE_LOCATION_API_KEY` to the Amazon Location API key. This is a browser-visible key, not a secret. Restrict it to the deployed site referrer and map actions.
3. Put the generated `climate-cells.pmtiles` at `web/public/climate-cells.pmtiles`.
4. Run:

   ```powershell
   cd web
   npm install
   npm run dev
   ```

The app can also load the archive from `VITE_DATA_URL` if it is hosted elsewhere.

## Build the data archive

See [`pipeline/README.md`](pipeline/README.md) for the expected input catalog and command. The pipeline is deliberately manifest-driven: record the exact EURO-CORDEX model runs and population raster used in `pipeline/data-manifest.json` so results can be reproduced.

## Deploy to AWS

The CDK stack deploys in `eu-central-1` by default. It creates a private S3 origin, CloudFront distribution, Amazon Location map, and a browser API key restricted to the CloudFront domain. Build the initial app with an empty key and deploy infrastructure first. Retrieve the generated browser key with `aws location describe-key --key-name europe-climate-explorer-web --query Key --output text`, then put it in `web/.env.local`, rebuild, and redeploy the stack so the built site contains the key. The value is intentionally browser-visible and referrer-restricted.

```powershell
cd infra
npm install
npx cdk synth
npx cdk diff
npx cdk deploy
```

Set `SITE_DOMAIN` only if using a custom domain; otherwise the generated CloudFront domain is used. After deployment, upload the PMTiles archive separately so large data files do not pass through the CDK asset deployment Lambda:

```powershell
aws s3 cp ..\data\climate-cells.pmtiles s3://<ContentBucketName>/climate-cells.pmtiles
```

The site and archive are then served from the same CloudFront origin. Verify AWS account, region, and permissions before deployment.

## Interpretation limits

- CMIP5 RCP4.5 and RCP8.5 are conditional scenario pathways, not probability-ranked predictions.
- A model ensemble range describes spread among selected runs; it is not a confidence interval.
- The annual mean does not represent heat waves, daily extremes, urban heat islands, health impacts, or future population.
- Population values are aggregated to climate cells and should not be read as precise local counts.

## Demo and submission

Follow [`docs/DEMO.md`](docs/DEMO.md) to record a public demo under three minutes. The video and live URL are not created by this repository scaffold.
