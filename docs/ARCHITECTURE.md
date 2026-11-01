# HeatReady Atlas architecture

![HeatReady Atlas system architecture](images/architecture.svg)

## Map data path

1. Read monthly `tas` files from the public EURO-CORDEX archive on Amazon S3 and the GHSL 2020 population raster from its AWS-hosted source.
2. The Python pipeline pairs three complete EUR-11 climate-model runs, computes annual-mean anomalies against 1981–2000 for 2041–2060 and 2081–2100, and summarizes the ensemble percentiles.
3. The pipeline aggregates each GHSL pixel count once to a climate cell and checks population-total preservation within the climate grid.
4. The derived cell attributes are packed into a local PMTiles archive. The React app loads that vector data through MapLibre GL JS; Amazon Location Service provides the basemap.
5. AWS CDK deploys the static app and PMTiles archive to S3 behind CloudFront. The Amazon Location API key is restricted to map reads and the live site's referrer.

## Agent request path

1. A visitor selects a cell and submits a planning question. The browser sends the cell ID, scenario, period, selected temperature percentiles, 2020 population count, and prompt to the FastAPI service.
2. Pydantic validates values and rejects unsupported IDs, non-finite/out-of-range temperatures, and inconsistent percentile order.
3. The request creates a Strands agent with a per-request, read-only cell evidence tool and a shared WHO-guidance tool. The cell tool is bound to that validated snapshot; it cannot query arbitrary files or run shell commands.
4. Strands invokes the configured Amazon Bedrock model. The response is returned to the browser with its model label and the evidence snapshot.

No conversation store is configured. The prompt should not contain personal or medical details. The agent is instructed to keep long-range scenarios separate from current weather alerts and to defer local services and health decisions to qualified authorities.

## Live deployment

- Live app: https://d1p7fe2ijqxr2z.cloudfront.net
- Static app and PMTiles: S3 private origin behind CloudFront. The archive is available at `/climate-cells.pmtiles`.
- Strands API: Python FastAPI runs in Lambda and is reached through the same CloudFront site at `/api/brief`; `/api/health` reports service readiness.
- Bedrock: the Lambda execution role invokes the EU Amazon Nova Lite inference profile only after a visitor submits a brief request. Inference may incur AWS charges.
- Public demo video: the script is in `DEMO.md`; recording and upload remain outstanding.

The CloudFront API behavior forwards requests to a Lambda Function URL protected with CloudFront Origin Access Control. The browser uses the same origin, so no public function URL or separate API key is exposed.

## Scale and limits

- 174,688 climate cells in the local archive; PMTiles source contains 4,303 vector tiles at zoom 4–8.
- Three matched climate-model pairs; their spread is not a confidence interval.
- Annual-mean anomalies do not show hot days, heatwaves, urban heat islands, future population, health effects, or personal exposure.
- Population counts are cell aggregates. They are not demographic vulnerability measures.
