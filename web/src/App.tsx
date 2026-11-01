import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import maplibregl, { Map, MapMouseEvent } from 'maplibre-gl';
import { Protocol } from 'pmtiles';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { ClimateCellProperties, Period, Scenario } from './types';

const apiKey = import.meta.env.VITE_LOCATION_API_KEY as string | undefined;
const region = (import.meta.env.VITE_AWS_REGION as string | undefined) || 'eu-central-1';
const mapName = (import.meta.env.VITE_LOCATION_MAP_NAME as string | undefined) || 'europe-climate-explorer-map';
const dataUrl = (import.meta.env.VITE_DATA_URL as string | undefined) || `${window.location.origin}/climate-cells.pmtiles`;
const sourceLayer = 'climate_cells';

const labels: Record<Scenario, string> = { rcp45: 'RCP 4.5', rcp85: 'RCP 8.5' };
const periods: Record<Period, string> = { mid: '2041–2060', late: '2081–2100' };

function App() {
  const [scenario, setScenario] = useState<Scenario>('rcp45');
  const [period, setPeriod] = useState<Period>('mid');
  const [showPopulation, setShowPopulation] = useState(false);
  const [selected, setSelected] = useState<ClimateCellProperties | null>(null);
  const [mapStatus, setMapStatus] = useState('Loading map…');
  const [hasClimateData, setHasClimateData] = useState(false);
  const [agentQuestion, setAgentQuestion] = useState('Draft a short heat-preparedness brief for a local community group.');
  const [agentBrief, setAgentBrief] = useState('');
  const [agentStatus, setAgentStatus] = useState('Select a map cell to ground a community planning brief in its climate and population data.');
  const [agentBusy, setAgentBusy] = useState(false);
  const mapRef = useRef<Map | null>(null);
  const selectedLayerRef = useRef(showPopulation);

  useEffect(() => {
    if (!apiKey) {
      setMapStatus('Add VITE_LOCATION_API_KEY to web/.env.local to load the basemap.');
      return;
    }

    const protocol = new Protocol();
    maplibregl.addProtocol('pmtiles', protocol.tile);
    let isDisposed = false;
    let basemapReady = false;
    let archiveRetryTimer: number | undefined;
    const map = new maplibregl.Map({
      container: 'map',
      style: `https://maps.geo.${region}.amazonaws.com/maps/v0/maps/${mapName}/style-descriptor?key=${apiKey}`,
      center: [15, 53],
      zoom: 4,
      minZoom: 4,
      maxZoom: 8,
      attributionControl: false,
    });
    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'top-right');
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
    const retryArchiveCheck = () => {
      if (!isDisposed) {
        archiveRetryTimer = window.setTimeout(() => void attachClimateLayer(), 5000);
      }
    };
    const attachClimateLayer = async () => {
      if (isDisposed || map.getSource('climate')) return;
      try {
        const archiveResponse = await fetch(dataUrl, { method: 'HEAD' });
        const contentType = archiveResponse.headers.get('content-type')?.toLowerCase() ?? '';
        if (!archiveResponse.ok || contentType.includes('text/html')) {
          setMapStatus('Basemap ready · climate archive missing');
          retryArchiveCheck();
          return;
        }
      } catch {
        setMapStatus('Basemap ready · climate archive unavailable');
        retryArchiveCheck();
        return;
      }

      try {
        map.addSource('climate', {
          type: 'vector',
          url: `pmtiles://${dataUrl}`,
          promoteId: 'cell_id',
        });
        const firstLabelLayer = map.getStyle().layers?.find((layer) => layer.type === 'symbol')?.id;
        map.addLayer({
          id: 'climate-fill',
          type: 'fill',
          source: 'climate',
          'source-layer': sourceLayer,
          paint: {
            'fill-color': ['interpolate', ['linear'], ['get', 'warming_rcp45_mid_p50'], 0, '#fff1c7', 1, '#f4b66c', 2, '#df754b', 3, '#a83d3f', 5, '#592b53'],
            'fill-opacity': ['interpolate', ['linear'], ['zoom'], 4, 0.44, 6, 0.56, 8, 0.66],
            'fill-outline-color': ['interpolate', ['linear'], ['zoom'], 4, 'rgba(255,255,255,0)', 6, 'rgba(255,255,255,0.12)', 8, 'rgba(255,255,255,0.28)'],
          },
        }, firstLabelLayer);
        map.addLayer({
          id: 'population-fill',
          type: 'fill',
          source: 'climate',
          'source-layer': sourceLayer,
          layout: { visibility: 'none' },
          paint: {
            'fill-color': ['interpolate', ['linear'], ['get', 'population_2020'], 0, '#f4f2eb', 100, '#b7c7b4', 500, '#507e6f', 2000, '#174f4a'],
            'fill-opacity': ['interpolate', ['linear'], ['zoom'], 4, 0.42, 6, 0.54, 8, 0.64],
            'fill-outline-color': ['interpolate', ['linear'], ['zoom'], 4, 'rgba(255,255,255,0)', 6, 'rgba(255,255,255,0.12)', 8, 'rgba(255,255,255,0.28)'],
          },
        }, firstLabelLayer);
        map.addLayer({
          id: 'selected-cell-outline',
          type: 'line',
          source: 'climate',
          'source-layer': sourceLayer,
          paint: { 'line-color': '#122d32', 'line-width': 2.5 },
          filter: ['==', ['get', 'cell_id'], ''],
        }, firstLabelLayer);
      } catch (error) {
        for (const layerId of ['selected-cell-outline', 'population-fill', 'climate-fill']) {
          if (map.getLayer(layerId)) map.removeLayer(layerId);
        }
        if (map.getSource('climate')) map.removeSource('climate');
        console.error('Could not add climate archive layers.', error);
        setMapStatus('Basemap ready · climate layer could not be added');
        retryArchiveCheck();
        return;
      }
      setHasClimateData(true);
      setMapStatus('Climate layer ready');
    };
    map.on('load', () => {
      basemapReady = true;
      setMapStatus('Basemap ready · loading climate archive');
      void attachClimateLayer();
    });

    map.on('click', (event: MapMouseEvent) => {
      const layerId = selectedLayerRef.current ? 'population-fill' : 'climate-fill';
      if (!map.getLayer(layerId)) return;
      const feature = map.queryRenderedFeatures(event.point, { layers: [layerId] })[0];
      setSelected((feature?.properties as ClimateCellProperties | undefined) ?? null);
    });
    map.on('error', (event) => {
      console.error('Map resource error.', event.error);
      if (!basemapReady) setMapStatus('Amazon Location basemap failed · check the map key and network');
      else if (map.getSource('climate')) setMapStatus('A map resource failed to load · check the network');
    });

    return () => {
      isDisposed = true;
      if (archiveRetryTimer !== undefined) window.clearTimeout(archiveRetryTimer);
      map.remove();
      mapRef.current = null;
      maplibregl.removeProtocol('pmtiles');
    };
  }, []);

  const metricKeys = useMemo(() => {
    const prefix = `warming_${scenario}_${period}`;
    return { low: `${prefix}_p10`, median: `${prefix}_p50`, high: `${prefix}_p90` } as const;
  }, [scenario, period]);

  useEffect(() => {
    selectedLayerRef.current = showPopulation;
    const map = mapRef.current;
    if (!map || !map.getLayer('climate-fill')) return;
    map.setLayoutProperty('population-fill', 'visibility', showPopulation ? 'visible' : 'none');
    map.setLayoutProperty('climate-fill', 'visibility', showPopulation ? 'none' : 'visible');
    setSelected(null);
  }, [showPopulation]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer('climate-fill')) return;
    map.setPaintProperty('climate-fill', 'fill-color', [
      'interpolate', ['linear'], ['get', metricKeys.median],
      0, '#fff1c7', 1, '#f4b66c', 2, '#df754b', 3, '#a83d3f', 5, '#592b53',
    ]);
    setSelected(null);
  }, [metricKeys]);

  const range = selected
    ? [selected[metricKeys.low], selected[metricKeys.high]].map(Number)
    : null;
  const median = selected ? Number(selected[metricKeys.median]) : null;
  const population = selected ? Number(selected.population_2020) : null;

  async function askResilienceAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !agentQuestion.trim() || agentBusy) return;
    setAgentBusy(true);
    setAgentBrief('');
    setAgentStatus('The Strands agent is checking the selected cell and its community guidance…');
    try {
      const requestBody = JSON.stringify({
        question: agentQuestion.trim(),
        cell: {
          cell_id: String(selected.cell_id),
          scenario,
          period,
          p10_c: Number(selected[metricKeys.low]),
          median_c: Number(selected[metricKeys.median]),
          p90_c: Number(selected[metricKeys.high]),
          population_2020: Math.round(Number(selected.population_2020)),
        },
      });
      const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(requestBody));
      const payloadHash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
      const response = await fetch(`${import.meta.env.VITE_AGENT_API_URL || ''}/api/brief`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-amz-content-sha256': payloadHash },
        body: requestBody,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'The agent could not create a brief.');
      setAgentBrief(result.brief);
      setAgentStatus(`Grounded in cell ${selected.cell_id} · ${labels[scenario]} · ${periods[period]} · model ${result.model_id}`);
    } catch (error) {
      setAgentStatus(error instanceof Error ? error.message : 'Could not reach the local Strands service.');
    } finally {
      setAgentBusy(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="HeatReady Atlas home"><span className="brand-mark">H</span><span>HEATREADY <b>/ EUROPE ATLAS</b></span></a>
        <div className="topbar-note"><span className="live-dot" /> CLIMATE RESILIENCE <span className="topbar-divider">·</span> STRANDS AGENT</div>
      </header>

      <section className="intro" id="top">
        <div className="eyebrow"><span>01</span><i /> A EUROPEAN CLIMATE RESILIENCE ATLAS</div>
        <h1>See the warming.<br /><em>Plan for people.</em></h1>
        <p className="intro-copy">Explore long-run climate scenarios alongside where people live, then ask a Strands agent for a grounded community preparedness brief.</p>
      </section>

      <section className="workspace" aria-label="Interactive climate map">
        <aside className="control-panel">
          <div className="panel-kicker">SCENARIO SETTINGS</div>
          <div className="slider-group">
            <div className="slider-heading">
              <label htmlFor="scenario">Emissions pathway</label>
              <output>{scenario === 'rcp45' ? 'RCP 4.5' : 'RCP 8.5'}</output>
            </div>
            <input
              className="choice-slider"
              id="scenario"
              type="range"
              min="0"
              max="1"
              step="1"
              value={scenario === 'rcp45' ? 0 : 1}
              aria-valuetext={scenario === 'rcp45' ? 'RCP 4.5, intermediate emissions' : 'RCP 8.5, high emissions'}
              onChange={(event) => setScenario(event.target.value === '0' ? 'rcp45' : 'rcp85')}
            />
            <div className="slider-endpoints"><span className={scenario === 'rcp45' ? 'selected' : ''}>Intermediate</span><span className={scenario === 'rcp85' ? 'selected' : ''}>High emissions</span></div>
          </div>
          <div className="slider-group period-slider-group">
            <div className="slider-heading">
              <label htmlFor="period">Future period</label>
              <output>{period === 'mid' ? 'Mid-century' : 'Late-century'}</output>
            </div>
            <input
              className="choice-slider"
              id="period"
              type="range"
              min="0"
              max="1"
              step="1"
              value={period === 'mid' ? 0 : 1}
              aria-valuetext={period === 'mid' ? '2041 to 2060, mid-century' : '2081 to 2100, late-century'}
              onChange={(event) => setPeriod(event.target.value === '0' ? 'mid' : 'late')}
            />
            <div className="slider-endpoints"><span className={period === 'mid' ? 'selected' : ''}>2041–2060</span><span className={period === 'late' ? 'selected' : ''}>2081–2100</span></div>
          </div>
          <div className="baseline-note"><span>REFERENCE PERIOD</span><strong>1981–2000</strong></div>

          <div className="rule" />
          <div className="panel-kicker">MAP LAYER</div>
          <button className={`layer-option ${!showPopulation ? 'active' : ''}`} onClick={() => setShowPopulation(false)}>
            <span className="layer-swatch warming-swatch" /><span><strong>Projected warming</strong><small>Annual mean temperature change</small></span><span className="radio-dot" />
          </button>
          <button className={`layer-option ${showPopulation ? 'active' : ''}`} onClick={() => setShowPopulation(true)}>
            <span className="layer-swatch people-swatch" /><span><strong>People living here</strong><small>GHSL population · 2020</small></span><span className="radio-dot" />
          </button>

          <div className="legend-block">
            <div className="legend-title">{showPopulation ? 'POPULATION PER CLIMATE CELL' : 'MODELLED CHANGE · °C'}</div>
            <div className={`legend-gradient ${showPopulation ? 'population-gradient' : ''}`} />
            <div className="legend-values">{showPopulation ? <><span>LOWER</span><span>HIGHER</span></> : <><span>0°</span><span>1°</span><span>2°</span><span>3°+</span></>}</div>
          </div>

          <div className="panel-footnote">Each cell shows the model ensemble median. Select a cell to see the model range and population estimate.</div>
        </aside>

        <div className="map-wrap">
          <div id="map" role="application" aria-label="Map of projected European warming and population" />
          <div className="map-status">{mapStatus}</div>
          <div className="map-caption"><span className="caption-index">FIG. 01</span><span>{labels[scenario]} <i>·</i> {periods[period]} <i>·</i> {showPopulation ? 'Population by climate cell' : 'Temperature anomaly'}</span></div>
          <div className="detail-card">
            {selected ? <>
              <div className="detail-head"><span>SELECTED GRID CELL</span><button onClick={() => setSelected(null)} aria-label="Close cell details">×</button></div>
              <div className="detail-value">{median !== null && Number.isFinite(median) ? `${median >= 0 ? '+' : ''}${median.toFixed(1)}°` : '—'}<small> median change</small></div>
              <div className="detail-row"><span>Ensemble range</span><strong>{range?.every(Number.isFinite) ? `${range[0].toFixed(1)}° to ${range[1].toFixed(1)}°` : 'No data'}</strong></div>
              <div className="detail-row"><span>Population · 2020</span><strong>{population !== null && Number.isFinite(population) ? Math.round(population).toLocaleString() : 'No data'}</strong></div>
              <div className="detail-cell">Cell {selected.cell_id}</div>
            </> : <>
              <div className="detail-head"><span>{hasClimateData ? 'HOW TO EXPLORE' : 'CLIMATE DATA'}</span></div>
              <p>{hasClimateData
                ? 'Choose a pathway and future period, then click a grid cell to inspect its warming range and population.'
                : 'The basemap stays visible while the climate archive is checked. Model cells will appear as soon as it is ready.'}</p>
            </>}
          </div>
        </div>
      </section>

      <section className="agent-section" aria-labelledby="agent-heading">
        <div className="agent-heading-row">
          <div>
            <div className="eyebrow agent-eyebrow"><span>02</span><i /> CLIMATE RESILIENCE · STRANDS AGENT</div>
            <h2 id="agent-heading">Turn a map cell into a <em>community plan.</em></h2>
            <p className="agent-intro">Ask for practical heat-preparedness planning. The agent checks the selected cell values and a small, cited set of WHO community guidance before drafting.</p>
          </div>
          <div className="agent-badge"><span className="agent-spark">✳</span><span>GROUNDED<br />TWO-TOOL AGENT</span></div>
        </div>
        <form className="agent-form" onSubmit={askResilienceAgent}>
          <label htmlFor="agent-question">What should the community plan for?</label>
          <div className="agent-input-row">
            <input id="agent-question" value={agentQuestion} maxLength={700} onChange={(event) => setAgentQuestion(event.target.value)} placeholder="e.g. What should we verify before summer?" />
            <button type="submit" disabled={!selected || agentBusy || agentQuestion.trim().length < 8}>{agentBusy ? 'Working…' : 'Draft a brief'} <span>↗</span></button>
          </div>
          <div className="agent-status" role="status">{agentStatus}</div>
        </form>
        {agentBrief && <article className="agent-response"><div className="agent-response-label">COMMUNITY PREPAREDNESS BRIEF</div><p>{agentBrief}</p></article>}
        <div className="agent-boundary">Planning support only. EURO-CORDEX annual-mean scenarios are not current heat alerts or health-risk estimates. Confirm local warnings, services, venue accessibility, and capacity with local authorities.</div>
      </section>

      <section className="context-row">
        <div className="context-label">HOW TO READ THIS MAP</div>
        <p>These are conditional climate model scenarios, not predictions. The shaded range represents the 10th–90th percentile across matched model runs. Population is aggregated to the climate grid; it is context for comparison, not a measure of individual exposure or risk.</p>
        <a href="https://registry.opendata.aws/euro-cordex/" target="_blank" rel="noreferrer">DATA & METHODS <span>↗</span></a>
      </section>

      <footer className="footer"><span>EURO-CORDEX · CMIP5 RCP SCENARIOS</span><span>GHSL GHS-POP · 2020</span><span>BASELINE 1981–2000</span></footer>
    </main>
  );
}

export default App;
