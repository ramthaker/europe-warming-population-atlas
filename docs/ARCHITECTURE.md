# HeatReady Atlas architecture

![HeatReady Atlas system architecture](images/architecture.svg)

## Map data path

1. Read monthly `tas` files from the public EURO-CORDEX archive on Amazon S3 and the GHSL 2020 population raster from its AWS-hosted source.
2. The Python pipeline pairs three complete EUR-11 climate-model runs, computes annual-mean anomalies against 1981–2000 for 2041–2060 and 2081–2100, and summarizes the ensemble percentiles.
3. The pipeline aggregates each GHSL pixel count once to a climate cell and checks population-total preservation within the climate grid.
4. The derived cell attributes are packed into a local PMTiles archive. The React app loads that vector data through MapLibre GL JS; Amazon Location Service provides the basemap.
5. AWS CDK defines a private S3 origin and CloudFront distribution for the static app and archive. The Amazon Location API key is restricted to map reads and allowed referrers.

## Agent request path

1. A visitor selects a cell and submits a planning question. The browser sends the cell ID, scenario, period, selected temperature percentiles, 2020 population count, and prompt to the FastAPI service.
2. Pydantic validates values and rejects unsupported IDs, non-finite/out-of-range temperatures, and inconsistent percentile order.
3. The request creates a Strands agent with a per-request, read-only cell evidence tool and a shared WHO-guidance tool. The cell tool is bound to that validated snapshot; it cannot query arbitrary files or run shell commands.
4. Strands invokes the configured Amazon Bedrock model. The response is returned to the browser with its model label and the evidence snapshot.

No conversation store is configured. The prompt should not contain personal or medical details. The agent is instructed to keep long-range scenarios separate from current weather alerts and to defer local services and health decisions to qualified authorities.

## Current state and deployment boundary

- Local map archive: built and present under ignored `data/` files.
- Static site and S3/CloudFront distribution: CDK infrastructure is defined; the updated agent-enabled build and archive are not published.
- Strands API: implemented as a local FastAPI service. It is not deployed and has no public endpoint.
- Bedrock: invoked only when a local user submits a request; model access, region, and charges depend on the user's AWS account.
- Public demo video: the script is in `DEMO.md`; recording and upload remain outstanding.

Before public release, deploy the API behind an HTTPS service endpoint, use an execution role with least-privilege model invocation permissions, configure HTTPS-only CORS for the site, set the production API URL, publish the archive, and verify the full flow. Deployment is intentionally a separate approval step.

## Scale and limits

- 174,688 climate cells in the local archive; PMTiles source contains 4,303 vector tiles at zoom 4–8.
- Three matched climate-model pairs; their spread is not a confidence interval.
- Annual-mean anomalies do not show hot days, heatwaves, urban heat islands, future population, health effects, or personal exposure.
- Population counts are cell aggregates. They are not demographic vulnerability measures.
