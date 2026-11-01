# Builder Center article draft — HeatReady Atlas

Draft for the Strands climate-resilience challenge. The map, archive, and agent API are live. Add the public demo-video link after recording, and confirm the required workshop completion before submission; do not claim eligibility until it is complete.

## Title

HeatReady Atlas: A Climate Resilience Agent for Community Planning

## Description

HeatReady Atlas pairs European climate scenarios with 2020 population context, then uses a Strands agent to draft a grounded heat-preparedness brief for a selected map cell. It helps community groups turn long-term climate data into practical questions to verify with local services.

## Cover image

Upload [heatready-atlas-article-cover.jpg](images/heatready-atlas-article-cover.jpg) in the Builder Center cover-image field. It is 1200×675 and below the 2 MB upload limit.

## Body

### The challenge

Communities need to plan for hotter summers, but climate projections are often difficult to connect to local planning. A long-term model scenario is not an alert for tomorrow, and a population grid cannot identify people who may need support. HeatReady Atlas makes those boundaries clear while giving community groups a useful next step: a short, data-grounded preparedness brief.

### What the project does

Visitors explore annual-mean warming scenarios across the EURO-CORDEX Europe domain alongside GHSL population counts for 2020. They choose an emissions pathway and period, switch between warming and population, and select a climate-grid cell. The selected values become the evidence for a Strands-powered community planning assistant.

The agent drafts a short brief with the selected cell's modelled warming median and ensemble range, its aggregated population estimate, practical heat-preparedness prompts, and a local fact to verify—such as cooling-venue access, opening hours, or capacity. Those service details are explicitly not inferred from the climate map.

The map is also a reusable location-data pattern: it layers a derived climate-cell dataset and population counts over an Amazon Location Service basemap, then lets visitors compare scenarios and inspect a cell. It makes the dataset, processing method, and interpretation limits available alongside the live map.

### How the agent works

The Python API uses the Strands Agents SDK and Amazon Bedrock. Each request is validated, then a Strands agent is given two read-only tools:

1. `read_selected_map_cell` returns the map cell's exact scenario values, population estimate, source labels, and interpretation limits.
2. `get_community_heat_actions` supplies general community planning prompts grounded in [WHO/Europe heat guidance](https://www.who.int/europe/news-room/fact-sheets/item/keepcool-in-the-heat).

The model must use both tools before writing its response. Its instructions prohibit health-risk scores, diagnoses, live alerts, unsupported claims about local services, and treating the population total as a count of vulnerable people. The prototype does not retain chat messages. It is not a health professional or emergency service.

### Data and method

- [EURO-CORDEX CMIP5 on the Registry of Open Data on AWS](https://registry.opendata.aws/euro-cordex/): monthly 2 m air temperature (`tas`) on the EUR-11 grid. Three matched historical/RCP model pairs cover the full period.
- [GHSL GHS-POP on the Registry of Open Data on AWS](https://registry.opendata.aws/ghs-pop/): gridded residential population for 2020, from the European Commission Joint Research Centre.
- The Python pipeline computes day-weighted annual means and future-minus-baseline changes against 1981–2000 for 2041–2060 and 2081–2100. It reports the ensemble median and 10th–90th percentile range.
- GHSL pixel counts are assigned once to climate cells by pixel center. The data build checks total preservation within the climate-grid footprint.

### AWS and implementation

Amazon Location Service supplies the MapLibre basemap through a map-only API key restricted to the live site's referrer. The React app and PMTiles archive are hosted in Amazon S3 behind CloudFront. A CloudFront `/api/*` route reaches the FastAPI Strands agent on AWS Lambda; the Lambda execution role invokes the EU Amazon Nova Lite profile in Amazon Bedrock after a visitor submits a request. The live app is public and does not require sign-in.

The frontend is React, TypeScript, Vite, MapLibre GL JS, and PMTiles. The data pipeline is Python. The source repository documents setup, attribution, model selection, limitations, and a video script.

### Why this matters

The project makes climate data easier to discuss in a community planning meeting. Instead of presenting a colored cell as a prediction of harm, it shows the scenario, range, population context, and uncertainty, then helps users formulate actionable questions for local authorities. A future deployment could add verified cooling-center inventories, accessible transport data, and official warning feeds—each with dated sources and clear coverage—without pretending those datasets are already present.

### Measuring impact

No community outcome has been measured yet. In a pilot with local partners, we would track the share of planning sessions that leave with (1) a verified local heat-warning source, (2) a checked, accessible cool-space option, and (3) a named owner and review date for the outreach plan. A short before-and-after question could measure whether participants can distinguish long-term scenarios from current heat alerts. These measures require partner consent and a locally designed process; the prototype does not track users or store personal data.

### Limitations

The scenarios represent annual-mean model changes, not heatwave frequency or current conditions. The selected ensemble is small and does not represent a probability distribution. GHSL population is aggregated to climate cells. Local heat vulnerability, services, access, and capacities are not measured by these inputs and need local verification. The agent's output is a planning draft, not clinical advice or an official heat-health action plan.

### Sources and attribution

EURO-CORDEX monthly CMIP5 2 m temperature data; GHSL GHS-POP 2020, European Commission Joint Research Centre; and WHO/Europe, “#KeepCool in the heat” (2026). Follow the datasets' current reuse and attribution terms before redistribution.

## Tags

Climate Resilience; Strands Agents; Amazon Bedrock; Amazon Location Service; Open Data

## Repository

https://github.com/ramthaker/europe-warming-population-atlas

## Endpoint or live demo

https://d1p7fe2ijqxr2z.cloudfront.net

## Demo video

Pending. Use the sub-three-minute recording script in `docs/DEMO.md` and add the public video URL here after upload. The video must show the live map and what visitors can explore.

## Notebook

None.
