# HeatReady Atlas demo script

**Target length:** 2 minutes 40 seconds (must stay under 3 minutes)

**Format:** screen recording with voiceover; show the live map and a real agent response.

**Current status:** script ready; video recording and public upload remain to be done.

## Before recording

- Run the app and local API using the README instructions. Confirm the climate archive and Amazon Location basemap load.
- Confirm AWS profile `pulse-personal`, region `eu-central-1`, Bedrock model access, and `STRANDS_MODEL_ID` are configured. A real brief request invokes Bedrock and may incur charges.
- Select a cell with a nonzero population estimate. Keep personal or account information out of the recording.
- Close terminals, secret files, AWS consoles, browser developer tools, and unrelated tabs. Use a clean browser window with the map already loaded.
- Capture at 1920×1080 if available. Keep the UI and selected-cell detail readable; zoom the page to 90–100%.

## Script and shot list

### 0:00–0:18 — The question

**On screen:** Start with the Europe map, warming layer, RCP 4.5 and 2041–2060 selected.

**Voiceover:** “A long-term climate scenario cannot tell a neighborhood when the next heatwave will happen. But it can help communities ask what they should prepare for. HeatReady Atlas puts modelled warming beside where people live, then uses a Strands agent to turn one map cell into a planning brief.”

### 0:18–0:45 — Explore the evidence

**On screen:** Drag the scenario slider to RCP 8.5, then switch to 2081–2100. Pan or zoom to a region, turn on the population layer, and click a cell.

**Voiceover:** “The map compares two CMIP5 pathways and two future periods against 1981 to 2000. Each cell reports the ensemble median and the 10th-to-90th percentile range. The population layer uses 2020 GHSL counts aggregated to the same climate grid.”

### 0:45–1:07 — Explain the limits

**On screen:** Pause on the selected-cell card and point to the warming range and population estimate.

**Voiceover:** “This is annual-mean change from three matched EURO-CORDEX model pairs. It is not a daily heat forecast, and the population number does not identify vulnerable people or measure personal exposure.”

### 1:07–1:45 — Ask the Strands agent

**On screen:** Scroll to the community planning panel. Leave the suggested question or enter: “What should our community verify before summer, and what are practical first steps?” Click **Draft a brief**. Show the working status, then the response and its grounding line.

**Voiceover:** “I’m asking what the community should verify before summer. The Strands agent calls two tools: one returns the exact selected-cell values and their limits; the other provides general WHO Europe heat-preparedness guidance. Bedrock uses those tool results to draft practical next steps and flag a local fact to verify, like cooling-venue access and capacity.”

### 1:45–2:15 — Show what makes it useful

**On screen:** Scroll through the brief. Highlight a practical action and the local verification item. Briefly show the source link and limitations note.

**Voiceover:** “The answer is deliberately a planning prompt, not a claim that a particular service exists. A community can take the verification item to local health, social-care, and emergency-planning teams, then use official heat warnings when conditions change.”

### 2:15–2:40 — How it is built and where to reuse it

**On screen:** Show the architecture diagram or README section; finish on the GitHub repository URL and, once available, the public live URL.

**Voiceover:** “The map combines public EURO-CORDEX and GHSL data, a Python processing pipeline, PMTiles, MapLibre, and an Amazon Location basemap. The agent is built with the Strands Agents SDK and Amazon Bedrock. The repository includes the processing method, tool code, and limitations so another community can adapt the pattern.”

## Recording and upload checklist

1. Record the complete map and agent flow in one take if possible. Trim pauses, but keep the genuine agent request and response visible.
2. Keep the finished video below 3 minutes and make it publicly viewable without sign-in.
3. Upload to YouTube, Vimeo, or another public video host and add the public link to the Builder Center **demo** field.
4. Add the live app URL only after the static site, PMTiles archive, and API are deployed and verified. Do not put AWS credentials or `.env.local` values in the video, article, or repository.
5. Confirm the required Strands workshop is complete during the hackathon window before submitting; code alone does not establish workshop eligibility.
