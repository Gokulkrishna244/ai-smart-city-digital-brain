const API_BASE = window.location.protocol === 'file:' ? 'http://127.0.0.1:5000' : window.location.origin;
const $ = (selector, scope = document) => scope.querySelector(selector);

const elements = {
  result: $('#result'),
  statusBox: $('#statusBox'),
  connectionBadge: $('#connectionBadge'),
  mapFeedStatus: $('#mapFeedStatus'),
  pulseDataSource: $('#pulseDataSource'),
  apiMetric: $('#apiMetric'),
  recommendationList: $('#recommendationList'),
  historyBody: $('#historyTable tbody'),
  metroGrid: $('#metroCitiesGrid'),
  toggleApi: $('#toggleApiButton'),
  themeToggle: $('#themeToggle'),
  alertTicker: $('#alertTicker'),
  sidebar: $('#sidebar'),
  menuButton: $('#menuButton'),
  mobileOverlay: $('#mobileOverlay'),
  toast: $('#toast'),
  mapUpdatedAt: $('#mapUpdatedAt'),
  mapSummary: $('#mapSummary'),
  dataSearchInput: $('#dataSearchInput'),
  dataExplorerSummary: $('#dataExplorerSummary'),
  stateRegistryGrid: $('#stateRegistryGrid'),
  stateRegistryCount: $('#stateRegistryCount'),
  roadRecordCount: $('#roadRecordCount'),
  airRecordCount: $('#airRecordCount'),
  roadDataBody: $('#roadDataTable tbody'),
  airDataBody: $('#airDataTable tbody'),
  airTimeline: $('#airTimeline'),
  dataOutcomeCard: $('#dataOutcomeCard'),
  outcomeHeadline: $('#outcomeHeadline'),
  outcomeAdvice: $('#outcomeAdvice'),
  outcomeRisk: $('#outcomeRisk'),
  outcomeAction: $('#outcomeAction'),
  realtimeSearchInput: $('#realtimeSearchInput'),
  realtimeSearchButton: $('#realtimeSearchButton'),
  realtimeSearchResult: $('#realtimeSearchResult'),
  trafficLiveArea: $('#trafficLiveArea'),
  trafficLiveVehicles: $('#trafficLiveVehicles'),
  trafficLiveLevel: $('#trafficLiveLevel'),
  airLivePm25: $('#airLivePm25'),
  airLiveCo2: $('#airLiveCo2'),
  airLiveQuality: $('#airLiveQuality'),
  energyLiveArea: $('#energyLiveArea'),
  energyLiveUsage: $('#energyLiveUsage'),
  energyLiveLoad: $('#energyLiveLoad'),
  readinessScore: $('#readinessScore'),
  capstoneObjective: $('#capstoneObjective'),
  impactGrid: $('#impactGrid'),
  architectureFlow: $('#architectureFlow'),
  moduleValidationGrid: $('#moduleValidationGrid'),
  capstoneStrengths: $('#capstoneStrengths'),
  exportReportButton: $('#exportReportButton'),
  reportStatus: $('#reportStatus')
};

let overviewChart;
let cityMap;
let cityMarkers = [];
let liveMapMarkers = [];
let liveMapResults = [];
let apiExpanded = true;
let toastTimer;
let dataSearchTimer;
let capstoneReportData;
let apiDataSource;

const fallbackCities = [
  { city: 'Delhi', code: 'DL', zone: 'North Corridor', lat: 28.6139, lng: 77.2090, traffic: 'Severe', pollution: 'Poor', energy: 'High', score: 77, level: 'critical', vehicles: 1640, aqi: 151, load: 84 },
  { city: 'Mumbai', code: 'MB', zone: 'Western Suburbs', lat: 19.0760, lng: 72.8777, traffic: 'Moderate', pollution: 'Moderate', energy: 'High', score: 88, level: 'warning', vehicles: 1240, aqi: 94, load: 81 },
  { city: 'Bengaluru', code: 'BL', zone: 'IT Corridor', lat: 12.9716, lng: 77.5946, traffic: 'High', pollution: 'Moderate', energy: 'Normal', score: 87, level: 'warning', vehicles: 1380, aqi: 86, load: 72 },
  { city: 'Chennai', code: 'CH', zone: 'Coastal Basin', lat: 13.0827, lng: 80.2707, traffic: 'High', pollution: 'Poor', energy: 'High', score: 79, level: 'warning', vehicles: 1320, aqi: 124, load: 80 },
  { city: 'Kolkata', code: 'KL', zone: 'Riverfront Belt', lat: 22.5726, lng: 88.3639, traffic: 'Moderate', pollution: 'Poor', energy: 'Normal', score: 82, level: 'warning', vehicles: 1120, aqi: 132, load: 68 },
  { city: 'Hyderabad', code: 'HY', zone: 'Tech Valley', lat: 17.3850, lng: 78.4867, traffic: 'High', pollution: 'Good', energy: 'Normal', score: 91, level: 'stable', vehicles: 1295, aqi: 58, load: 70 }
];

const fallbackAlerts = [
  { level: 'critical', color: '#ff667d', city: 'Delhi', message: 'Congestion spike near Ring Road. Diversion protocol recommended.', time: '2m' },
  { level: 'warning', color: '#ffb454', city: 'Mumbai', message: 'Coastal air-quality threshold approaching elevated range.', time: '8m' },
  { level: 'info', color: '#4f8cff', city: 'Bengaluru', message: 'Adaptive signal rerouting activated across IT Corridor.', time: '14m' },
  { level: 'stable', color: '#3ddc97', city: 'Chennai', message: 'Grid load balancing completed; reserve capacity restored.', time: '21m' }
];

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
}

function showToast(message, isError = false) {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle('error', isError);
  elements.toast.classList.add('show');
  toastTimer = setTimeout(() => elements.toast.classList.remove('show'), 2800);
}

function renderMetroCities(cities = fallbackCities) {
  elements.metroGrid.innerHTML = cities.map(city => `
    <article class="metro-card ${city.level !== 'stable' || city.score < 80 ? 'alert-card' : ''}">
      <div class="metro-head">
        <div class="metro-title"><span class="city-initial">${escapeHtml(city.code)}</span><div><h4>${escapeHtml(city.city)}</h4><p>${escapeHtml(city.parent_area ? `${city.parent_area} · ${city.parent_city}` : city.parent_city || city.zone)}</p></div></div>
        <strong class="health-score">${escapeHtml(city.score)}%</strong>
      </div>
      <div class="metro-metrics">
        <div><span>Traffic</span><strong>${escapeHtml(city.traffic)}</strong></div>
        <div><span>AQI</span><strong>${escapeHtml(city.aqi ?? city.pollution)}</strong></div>
        <div><span>Load</span><strong>${escapeHtml(city.load ?? city.energy)}%</strong></div>
      </div>
    </article>
  `).join('');
}

function renderAlerts(items = fallbackAlerts) {
  elements.alertTicker.innerHTML = items.map(alert => `
    <article class="alert-item" style="--alert-color:${alert.color}">
      <i></i><div><strong>${escapeHtml(alert.city)} - ${escapeHtml(alert.level)}</strong><p>${escapeHtml(alert.message)}</p></div><time>${escapeHtml(alert.time)}</time>
    </article>
  `).join('');
}

function alertColor(level) {
  return level === 'critical' ? '#ff667d' : level === 'high' || level === 'warning' ? '#ffb454' : level === 'medium' ? '#4f8cff' : '#3ddc97';
}

function renderLiveAlerts(cities) {
  const liveAlerts = cities
    .slice()
    .sort((a, b) => a.score - b.score)
    .slice(0, 4)
    .map(city => ({
      level: city.level,
      color: alertColor(city.level),
      city: city.city,
      message: `${city.traffic} traffic, AQI ${city.aqi}, and ${city.load}% energy load across ${city.zone}.`,
      time: 'dataset'
    }));
  renderAlerts(liveAlerts);
}

function initCityMap() {
  const mapElement = $('#realCityMap');
  if (!mapElement) return;
  if (typeof L === 'undefined') {
    mapElement.innerHTML = '<div class="map-fallback">Map tiles unavailable. Connect to the internet to load OpenStreetMap.</div>';
    return;
  }
  cityMap = L.map(mapElement, { zoomControl: true, scrollWheelZoom: true }).setView([21.2, 78.9], 5);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(cityMap);
  renderCityMap(fallbackCities);
  setTimeout(() => cityMap.invalidateSize(), 250);
}

function markerClass(city) {
  const levelClass = city.level === 'critical' ? 'critical' : city.level === 'warning' ? 'warning' : '';
  return `city-marker ${levelClass} ${city.place_type || 'city'}`;
}

function renderCityMap(cities) {
  if (!cityMap || typeof L === 'undefined') return;
  cityMarkers.forEach(marker => marker.remove());
  cityMarkers = cities.map(city => {
    const marker = L.marker([city.lat, city.lng], {
      icon: L.divIcon({
        className: '',
        html: `<span class="${markerClass(city)}"></span>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9]
      })
    }).addTo(cityMap);
    marker.bindPopup(`
      <div class="map-popup">
        <strong>${escapeHtml(city.display_name || city.city)}</strong>
        <span>Level <b>${escapeHtml((city.place_type || 'city').replace('_', ' '))}</b></span>
        <span>Traffic <b>${escapeHtml(city.traffic)}</b></span>
        <span>AQI <b>${escapeHtml(city.aqi)}</b></span>
        <span>Energy load <b>${escapeHtml(city.load)}%</b></span>
        <span>Health <b>${escapeHtml(city.score)}%</b></span>
      </div>
    `);
    return marker;
  });
  const bounds = L.latLngBounds(cities.map(city => [city.lat, city.lng]));
  cityMap.fitBounds(bounds, { padding: [34, 34], maxZoom: 5 });
}

function updateLiveSummary(data) {
  const updated = data?.updated_at ? new Date(data.updated_at) : new Date();
  const totals = data?.totals || {};
  elements.mapUpdatedAt.textContent = `Updated ${updated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  const areaLabel = totals.areas !== undefined ? `${totals.parent_cities} cities + ${totals.areas} areas + ${totals.streets || 0} streets` : `${totals.cities ?? fallbackCities.length} places`;
  elements.mapSummary.textContent = `${areaLabel} - ${totals.critical ?? 1} critical - ${totals.warnings ?? 4} warnings - ${totals.avg_health ?? 84}% avg health`;
}

function updateOperationalMetrics(values = {}) {
  Object.entries(values).forEach(([id, value]) => {
    const node = document.getElementById(id);
    if (node && value !== null && value !== undefined && Number.isFinite(Number(value))) {
      node.textContent = Number(value).toLocaleString(undefined, { maximumFractionDigits: id === 'networkHealth' ? 1 : 0 });
      if (id === 'activeIncidents') {
        const countLabel = `${Number(value).toLocaleString()} open`;
        $('#alertCount').textContent = countLabel;
        $('#navAlertCount').textContent = Number(value).toLocaleString();
      }
    }
  });
}

async function loadLiveData(quiet = false) {
  const data = await fetchApi('/live-data', {}, { quiet: true });
  if (!data?.cities?.length) {
    renderMetroCities(fallbackCities);
    renderCityMap(fallbackCities);
    renderAlerts();
    elements.mapUpdatedAt.textContent = 'Backend unavailable';
    elements.mapSummary.textContent = 'Local demo fallback - not connected to a city feed';
    elements.mapFeedStatus.textContent = 'Demo fallback';
    elements.pulseDataSource.textContent = 'Demo fallback';
    if (!quiet) showToast('Showing local demo values; no city feed is connected.', true);
    return;
  }
  renderMetroCities(data.cities);
  renderCityMap(data.cities);
  updateLiveSummary(data);
  updateOperationalMetrics({ networkHealth: data.totals.avg_health, connectedZones: data.totals.cities });
  const sourceLabel = data.data_source === 'simulated_dataset' ? 'Simulated dataset' : 'Connected data';
  elements.mapFeedStatus.textContent = sourceLabel;
  elements.pulseDataSource.textContent = sourceLabel;
}

async function loadIncidents() {
  const data = await fetchApi('/incidents?status=open', {}, { quiet: true });
  const incidents = data?.incidents || [];
  if (!incidents.length) return;
  renderAlerts(incidents.slice(0, 6).map(item => ({
    level: item.severity,
    color: alertColor(item.severity),
    city: `${item.city} · ${item.category}`,
    message: item.explanation,
    time: new Date(item.updated_at || item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  })));
  updateOperationalMetrics({ activeIncidents: incidents.length });
  const emergencyGrid = document.getElementById('emergencyGrid');
  if (emergencyGrid) emergencyGrid.innerHTML = incidents.slice(0, 10).map((item, index) => `
    <article class="emergency-item"><header><h4>#${item.id} · ${escapeHtml(item.city)}</h4><span class="quality-pill ${qualityClass(item.severity)}">${escapeHtml(item.severity)}</span></header>
    <p>${escapeHtml(item.explanation)}</p><p>Status: <strong>${escapeHtml(item.status)}</strong> · Team: ${escapeHtml(item.assigned_team || 'Unassigned')} · ETA: ${escapeHtml(item.response_eta || '--')} min</p>
    <div class="emergency-actions"><select data-team-for="${item.id}"><option>Traffic Response ${index % 4 + 1}</option><option>Fire & Rescue ${index % 3 + 1}</option><option>Environmental Unit ${index % 2 + 1}</option></select><button type="button" data-assign-incident="${item.id}">Assign team</button><button type="button" data-incident-status="acknowledged" data-incident-id="${item.id}">Acknowledge</button><button type="button" data-incident-status="resolved" data-incident-id="${item.id}">Resolve</button></div></article>
  `).join('');
  const critical = incidents.find(item => item.severity === 'critical');
  if (critical && 'Notification' in window && Notification.permission === 'granted') {
    const notificationKey = `urbanos-critical-${critical.id}-${critical.updated_at}`;
    if (!sessionStorage.getItem(notificationKey)) {
      new Notification(`Critical incident · ${critical.city}`, { body: critical.explanation, tag: `incident-${critical.id}` });
      sessionStorage.setItem(notificationKey, 'shown');
    }
  }
}

async function loadAdvancedIntelligence() {
  const data = await fetchApi('/intelligence', {}, { quiet: true });
  if (!data) return;
  const forecasts = data.predictions || [];
  const operations = data.operations || {};
  const first = forecasts[0] || {};
  const setText = (id, value) => { const node = document.getElementById(id); if (node) node.textContent = value; };
  setText('trafficForecast', `${first.city || 'City'} · ${first.traffic || '--'}`);
  setText('pollutionForecast', `${first.city || 'City'} · ${first.pollution || '--'}`);
  setText('waterForecast', `${operations.water_watch_zones || 0} watch zones`);
  setText('energyForecast', `${operations.energy_peak_zones || 0} peak zones`);
  setText('responseTeams', `${operations.response_teams_ready || 0} teams ready`);
  setText('parkingSpaces', `${Number(operations.parking_available || 0).toLocaleString()} spaces`);
  const modules = data.modules || {};
  setText('trafficModuleDetail', `${modules.traffic?.congestion_zones || 0} congestion zones · ${Number(modules.traffic?.vehicle_density || 0).toLocaleString()} vehicles · ${modules.traffic?.alternate_routes || 0} alternate routes`);
  setText('airModuleDetail', `Avg AQI ${modules.air?.avg_aqi || '--'} · PM2.5 ${modules.air?.pm25_estimate || '--'} · ${modules.air?.hotspots || 0} hotspots`);
  setText('waterModuleDetail', `Tank ${modules.water?.tank_level || '--'}% · ${modules.water?.possible_leaks || 0} possible leaks · ${modules.water?.watch_zones || 0} watch zones`);
  setText('energyModuleDetail', `${modules.energy?.demand_mw || '--'} MW · ${modules.energy?.peak_zones || 0} peak zones · ${modules.energy?.load_forecast || '--'} forecast`);
  setText('parkingModuleDetail', `${modules.parking?.occupancy || '--'}% occupancy · ${Number(modules.parking?.entries_today || 0).toLocaleString()} vehicle entries`);
  setText('disasterModuleDetail', `${modules.disaster?.flood_watch || 0} flood watches · ${modules.disaster?.weather_risk || '--'} weather risk · ${modules.disaster?.teams_ready || 0} teams`);
  const grid = document.getElementById('forecastGrid');
  if (grid) grid.innerHTML = forecasts.map(item => `
    <article class="forecast-card"><header><h4>${escapeHtml(item.city)}</h4><span>${escapeHtml(item.confidence)}%</span></header>
    <p>Traffic: <strong>${escapeHtml(item.traffic)}</strong></p><p>Air: <strong>${escapeHtml(item.pollution)}</strong></p>
    <p>Water: <strong>${escapeHtml(item.water_demand)}</strong> · ${item.anomaly ? 'Anomaly watch' : 'Normal pattern'}</p>
    <div class="confidence-track"><i style="width:${Math.min(100, Number(item.confidence) || 0)}%"></i></div></article>
  `).join('');
  const anomalyGrid = document.getElementById('anomalyGrid');
  if (anomalyGrid) anomalyGrid.innerHTML = (data.anomalies || []).map(item => `<article class="anomaly-item"><header><h4>${escapeHtml(item.city)} · ${escapeHtml(item.domain)}</h4><span>${escapeHtml(item.severity)}</span></header><p><strong>Evidence:</strong> ${escapeHtml(item.evidence)}</p><p><strong>Recommendation:</strong> ${escapeHtml(item.recommendation)}</p></article>`).join('') || '<p>No anomalies detected.</p>';
  const rankingTable = document.getElementById('rankingTable');
  if (rankingTable) rankingTable.innerHTML = (data.rankings || []).slice(0, 10).map((item, index) => `<div class="ranking-row"><b>${index + 1}</b><span>${escapeHtml(item.city)}</span><strong>${escapeHtml(item.overall)}</strong></div>`).join('');
  if (grid) grid.innerHTML = forecasts.map(item => `<article class="forecast-card"><header><h4>${escapeHtml(item.city)}</h4><span>${escapeHtml(item.confidence)}%</span></header><p>1h traffic: <strong>${escapeHtml(item.traffic_1h)}</strong></p><p>6h AQI: <strong>${escapeHtml(item.aqi_6h?.join(' → '))}</strong></p><p>Energy ${escapeHtml(item.energy_forecast_mw)} MW · Water ${escapeHtml(item.water_forecast_kl)} kL</p><p>Accuracy: ${item.historical_accuracy?.traffic == null ? 'Not validated' : escapeHtml(item.historical_accuracy.traffic)}</p><div class="confidence-track"><i style="width:${Math.min(100, Number(item.confidence) || 0)}%"></i></div></article>`).join('');
}

async function loadPlatform() {
  const data = await fetchApi('/platform', {}, { quiet: true });
  if (!data) return;
  const setText = (id, value) => { const node = document.getElementById(id); if (node) node.textContent = value; };
  const waste = data.waste || {}, transport = data.transport || {}, roads = data.roads || {}, safety = data.public_safety || {}, noise = data.noise || {}, sustainability = data.sustainability || {};
  setText('wasteHeadline', `${waste.collection_efficiency || '--'}% efficient`); setText('wasteDetail', `${waste.bins_full || 0} full bins · ${waste.routes_active || 0} active routes · ${waste.recycling_rate || 0}% recycling`);
  setText('transportHeadline', `${transport.on_time_percent || '--'}% on time`); setText('transportDetail', `${transport.buses_active || 0} buses · ${Number(transport.passengers_today || 0).toLocaleString()} passengers · ${transport.delayed_routes || 0} delays`);
  setText('roadsHeadline', `${roads.good_percent || '--'}% good condition`); setText('roadsDetail', `${roads.potholes_open || 0} potholes · ${roads.repair_km || 0} km repair · ${roads.signals_online || 0}% signals online`);
  setText('safetyHeadline', `${safety.average_response_min || '--'} min response`); setText('safetyDetail', `${safety.patrol_units || 0} patrols · ${safety.camera_uptime || 0}% camera uptime · ${safety.safe_zones || 0} safe zones`);
  const flood = (data.flood_prediction || [])[0] || {}; setText('floodHeadline', `${flood.risk || '--'}% risk`); setText('floodDetail', `${flood.city || 'City'} · ${flood.rainfall_mm || 0} mm rain · ${flood.drainage_status || '--'} drainage · ${flood.confidence || '--'}% confidence`);
  setText('noiseHeadline', `${noise.average_db || '--'} dB average`); setText('noiseDetail', `${noise.hotspots || 0} hotspots · ${noise.night_violations || 0} night violations · ${noise.quiet_zones || 0} quiet zones`);
  const root = document.getElementById('rootCauseGrid'); if (root) root.innerHTML = (data.root_causes || []).map(item => `<article class="root-cause-item"><h4>${escapeHtml(item.city)} · ${escapeHtml(item.issue)}</h4><p><strong>Likely causes:</strong> ${escapeHtml(item.probable_causes.join(', '))}</p><p><strong>Evidence:</strong> ${escapeHtml(item.evidence)} · ${escapeHtml(item.confidence)}% confidence</p></article>`).join('');
  const recommendations = document.getElementById('agentRecommendations'); if (recommendations) recommendations.innerHTML = (data.recommendations || []).map((item, index) => `<article class="agent-item"><h4>Priority ${index + 1}</h4><p>${escapeHtml(item)}</p></article>`).join('');
  const alerts = document.getElementById('citizenAlertList'); if (alerts) alerts.innerHTML = (data.citizen_alerts || []).map(item => `<article class="citizen-alert"><strong>${escapeHtml(item.title)} · ${escapeHtml(item.location)}</strong><p>${escapeHtml(item.message)}</p></article>`).join('');
  const services = document.getElementById('publicServiceGrid'); if (services) services.innerHTML = (data.public_services || []).map(item => `<div class="service-item">${escapeHtml(item)}</div>`).join('');
  const maintenance = document.getElementById('maintenanceGrid'); if (maintenance) maintenance.innerHTML = (data.maintenance || []).map(item => `<article class="maintenance-item ${String(item.failure_risk).toLowerCase()}"><div><h4>${escapeHtml(item.asset)} · ${escapeHtml(item.location)}</h4><p>${escapeHtml(item.next_action)}</p></div><strong>${escapeHtml(item.health)}% · ${escapeHtml(item.failure_risk)}</strong></article>`).join('');
  setText('sustainabilityScore', sustainability.score || '--'); const sustainable = document.getElementById('sustainabilityMetrics'); if (sustainable) sustainable.innerHTML = [['Renewable', `${sustainability.renewable_percent}%`], ['Green cover', `${sustainability.green_cover_percent}%`], ['Emissions', `${sustainability.emissions_change}%`], ['Water reuse', `${sustainability.water_reuse_percent}%`]].map(([label,value]) => `<div><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`).join('');
  renderGrievances(data.grievances || []);
}

function renderGrievances(items) {
  const list = document.getElementById('grievanceList'); if (!list) return;
  list.innerHTML = items.map(item => `<article class="grievance-item"><header><h4>#${item.id} · ${escapeHtml(item.category)} · ${escapeHtml(item.location)}</h4><span>${escapeHtml(item.status)}</span></header><p>${escapeHtml(item.description)}</p><p>${escapeHtml(item.priority)} priority · ${escapeHtml(item.created_at)}</p></article>`).join('') || '<p>No grievances submitted yet.</p>';
}

async function submitGrievance(event) {
  event.preventDefault(); const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
  const data = await fetchApi('/grievances', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const status = document.getElementById('grievanceStatus');
  if (data) { if (status) status.innerHTML = `<strong>Grievance #${data.id}</strong> submitted with ${escapeHtml(data.priority)} priority.`; event.currentTarget.reset(); loadPlatform(); showToast('Citizen grievance submitted.'); }
}

function setupTwinCityScene() {
  const scene = document.getElementById('twinCityScene'); if (!scene) return;
  let dragging = false, startX = 0, rotation = 0;
  scene.addEventListener('pointerdown', event => { dragging = true; startX = event.clientX; scene.setPointerCapture(event.pointerId); });
  scene.addEventListener('pointermove', event => { if (!dragging) return; rotation += (event.clientX - startX) * .08; startX = event.clientX; scene.querySelectorAll('i, .twin-ground, .twin-road').forEach(node => node.style.filter = `hue-rotate(${rotation}deg)`); });
  scene.addEventListener('pointerup', () => { dragging = false; });
}

async function submitAssistant(event) {
  event.preventDefault();
  const question = new FormData(event.currentTarget).get('question');
  const messages = document.getElementById('assistantMessages');
  messages.innerHTML = `<p><strong>Operator:</strong> ${escapeHtml(question)}</p><p>Analyzing dataset-derived city conditions...</p>`;
  const data = await fetchApi('/assistant', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) });
  if (data) {
    messages.innerHTML = `<p><strong>Operator:</strong> ${escapeHtml(question)}</p><p><strong>UrbanOS (${escapeHtml(data.confidence)}%):</strong> ${escapeHtml(data.answer)}</p><p>${escapeHtml(data.disclaimer)}</p>`;
    const evidence = document.getElementById('assistantEvidence');
    if (evidence) evidence.innerHTML = (data.evidence || []).map(item => `<div><span>${escapeHtml(item.metric)}</span><strong>${escapeHtml(item.value)}</strong><span>${escapeHtml(item.source)}</span></div>`).join('');
    if (data.map_place && cityMap && typeof L !== 'undefined') {
      const place = data.map_place;
      liveMapMarkers.forEach(marker => marker.remove());
      const marker = L.marker([place.lat, place.lng], {
        icon: L.divIcon({ className: '', html: '<span class="live-search-marker"></span>', iconSize: [22, 22], iconAnchor: [11, 11] })
      }).addTo(cityMap);
      marker.bindPopup(`<div class="map-popup"><strong>${escapeHtml(place.name)}</strong><span>${escapeHtml(place.display_name)}</span><span>Source <b>OpenStreetMap</b></span></div>`).openPopup();
      liveMapMarkers = [marker];
      cityMap.setView([place.lat, place.lng], 15);
    }
  }
}

async function submitTwin(event) {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
  Object.keys(payload).forEach(key => payload[key] = Number(payload[key]));
  const data = await fetchApi('/digital-twin', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const box = document.getElementById('twinResult');
  if (data && box) box.innerHTML = `<strong>Simulated impact:</strong> congestion ${escapeHtml(data.congestion_delta)}%, AQI ${escapeHtml(data.aqi_delta)}, energy ${escapeHtml(data.energy_delta)}%. ${escapeHtml(data.recommendation)}`;
  const comparison = document.getElementById('twinComparison');
  if (data && comparison) comparison.innerHTML = Object.keys(data.before || {}).map(key => `<div><span>${escapeHtml(key.replace('_', ' '))}</span><strong>${escapeHtml(data.before[key])} → ${escapeHtml(data.after[key])}</strong></div>`).join('');
}

function updateClock() {
  const now = new Date();
  $('#liveTime').textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  $('#liveDate').textContent = now.toLocaleDateString([], { month: 'short', day: 'numeric' });
  const hour = now.getHours();
  $('#timeGreeting').textContent = hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening';
}

function setApiStatus(online, dataSource) {
  if (dataSource) apiDataSource = dataSource;
  elements.statusBox.textContent = online ? '200 OK - Backend connected' : 'Connection unavailable';
  elements.apiMetric.textContent = online ? 'Backend online' : 'Backend offline';
  const statusDot = elements.apiMetric.previousElementSibling;
  statusDot?.classList.toggle('green', online);
  statusDot?.classList.toggle('amber', !online);
  $('#sidebarSystemStatus').textContent = online ? 'Operational' : 'Offline';
  $('#sidebarStatusDot').classList.toggle('green', online);
  $('#sidebarStatusDot').classList.toggle('amber', !online);
  const badgeLabel = online
    ? apiDataSource === 'simulated_dataset' ? 'API connected - demo data' : 'API connected'
    : 'Backend offline - demo fallback';
  elements.connectionBadge.lastChild.textContent = ` ${badgeLabel}`;
  elements.connectionBadge.classList.toggle('offline', !online);
  if (!online) {
    ['networkHealth', 'connectedZones', 'activeIncidents', 'aiDecisions'].forEach(id => {
      const node = document.getElementById(id);
      if (node) node.textContent = '--';
    });
    $('#alertCount').textContent = '-- open';
    $('#navAlertCount').textContent = '--';
  }
}

async function fetchApi(endpoint, options = {}, { quiet = false } = {}) {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, options);
    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json') ? await response.json() : { message: await response.text() };
    if (!response.ok) throw new Error(data.message || `Request failed (${response.status})`);
    elements.result.textContent = JSON.stringify(data, null, 2);
    setApiStatus(true, data?.data_source);
    return data;
  } catch (error) {
    elements.result.textContent = `Connection error\n${error.message}\n\nStart the backend with: python Backend/app.py`;
    if (endpoint === '/health' || error instanceof TypeError) setApiStatus(false);
    if (!quiet) showToast('Backend unavailable - start the Flask server to use live models.', true);
    return null;
  }
}

async function handlePrediction(event, endpoint, resultBoxId) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = $('button[type="submit"]', form);
  const box = document.getElementById(resultBoxId);
  const payload = Object.fromEntries(new FormData(form).entries());
  Object.keys(payload).forEach(key => {
    if (payload[key] !== '' && !Number.isNaN(Number(payload[key]))) payload[key] = Number(payload[key]);
  });

  const moduleName = endpoint.split('/').pop();
  const buttonLabels = { traffic: 'Analyze traffic', pollution: 'Analyze air quality', energy: 'Analyze energy' };
  button.disabled = true;
  button.innerHTML = 'Running prediction...';
  box.textContent = 'Applying the trained model to the submitted values...';
  box.classList.remove('success');
  const data = await fetchApi(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  button.disabled = false;
  button.innerHTML = `${buttonLabels[moduleName] || 'Run prediction'} <span>-&gt;</span>`;
  if (data) {
    const moduleText = data.module === 'pollution' ? 'Air quality' : data.module === 'energy' ? 'Energy demand' : 'Traffic flow';
    const urgent = ['High', 'Critical', 'Dangerous', 'Poor', 'Severe'];
    const watch = ['Medium', 'Moderate', 'Normal'];
    const validated = data.validation?.status === 'validated';
    const actionText = !validated
      ? 'Demo prediction only; not suitable for operational decisions.'
      : urgent.includes(data.prediction)
        ? 'Priority response recommended.'
        : watch.includes(data.prediction)
          ? 'Monitor closely and keep normal controls active.'
          : 'Stable condition; continue routine monitoring.';
    const validationText = validated
      ? `5-fold macro F1: ${data.validation.macro_f1_mean}`
      : `Trained on ${data.training_rows} CSV rows. ${data.validation?.message || 'Validation unavailable.'}`;
    box.innerHTML = `<span>${escapeHtml(moduleText)} outcome · ${escapeHtml(data.confidence ?? '--')}% model confidence</span><strong>${escapeHtml(data.prediction)}</strong><small>${escapeHtml(actionText)}</small><small>${escapeHtml(validationText)}</small>`;
    box.classList.add('success');
    showToast(`${data.module} model completed: ${data.prediction}`);
    loadHistory(true);
    loadLiveData(true);
    loadInsights(false);
  } else {
    box.textContent = 'Model unavailable - check the backend connection.';
  }
}

function chartColors() {
  const light = document.body.classList.contains('light-mode');
  return { text: light ? '#667a90' : '#8295a9', grid: light ? 'rgba(30,55,80,.08)' : 'rgba(144,174,204,.1)' };
}

function renderChart(data) {
  const canvas = $('#overviewChart');
  if (!canvas || typeof Chart === 'undefined') return;
  overviewChart?.destroy();
  const colors = chartColors();
  overviewChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: Object.keys(data),
      datasets: [{ data: Object.values(data), backgroundColor: ['rgba(79,140,255,.75)', 'rgba(61,220,151,.75)', 'rgba(255,180,84,.78)'], borderColor: ['#4f8cff', '#3ddc97', '#ffb454'], borderWidth: 1, borderRadius: 7, borderSkipped: false, barPercentage: .55 }]
    },
    options: {
      maintainAspectRatio: false,
      responsive: true,
      animation: { duration: 800, easing: 'easeOutQuart' },
      plugins: { legend: { display: false }, tooltip: { backgroundColor: '#091525', padding: 10, titleFont: { family: 'DM Sans' }, bodyFont: { family: 'DM Sans' } } },
      scales: {
        y: { beginAtZero: true, border: { display: false }, ticks: { color: colors.text, font: { size: 9 }, precision: 0 }, grid: { color: colors.grid } },
        x: { border: { display: false }, ticks: { color: colors.text, font: { size: 9, weight: 600 } }, grid: { display: false } }
      }
    }
  });
}

async function loadHistory(quiet = false) {
  const data = await fetchApi('/predictions', {}, { quiet });
  if (!data) {
    elements.historyBody.innerHTML = '<tr><td colspan="4">No live history - backend is offline.</td></tr>';
    return;
  }
  if (!data.length) {
    elements.historyBody.innerHTML = '<tr><td colspan="4">No predictions recorded yet.</td></tr>';
    return;
  }
  elements.historyBody.innerHTML = data.map(item => `
    <tr><td><span class="module-pill">${escapeHtml(item.module)}</span></td><td>${escapeHtml(item.city_area)}</td><td>${escapeHtml(item.prediction)}</td><td>${escapeHtml(item.created_at)}</td></tr>
  `).join('');
}

function qualityClass(value) {
  const quality = String(value || '').toLowerCase();
  if (quality.includes('danger')) return 'danger';
  if (quality.includes('poor')) return 'poor';
  if (quality.includes('moderate')) return 'moderate';
  return 'good';
}

function renderRoadRows(rows = []) {
  elements.roadRecordCount.textContent = `${rows.length} rows`;
  if (!rows.length) {
    elements.roadDataBody.innerHTML = '<tr><td colspan="6">No road records match this search.</td></tr>';
    return;
  }
  elements.roadDataBody.innerHTML = rows.map(row => `
    <tr>
      <td>${escapeHtml(row.location)}</td>
      <td>${escapeHtml(row.time_label)}</td>
      <td>${escapeHtml(row.road_type)}</td>
      <td>${escapeHtml(row.weather)}</td>
      <td>${escapeHtml(row.vehicle_count)}</td>
      <td><span class="quality-pill ${qualityClass(row.traffic_level)}">${escapeHtml(row.traffic_level)}</span></td>
    </tr>
  `).join('');
}

function renderAirRows(rows = []) {
  elements.airRecordCount.textContent = `${rows.length} rows`;
  if (!rows.length) {
    elements.airDataBody.innerHTML = '<tr><td colspan="6">No air records match this search.</td></tr>';
    return;
  }
  elements.airDataBody.innerHTML = rows.map(row => `
    <tr>
      <td>${escapeHtml(row.location)}</td>
      <td>${escapeHtml(row.time_label)}</td>
      <td>${escapeHtml(row.pm25)}</td>
      <td>${escapeHtml(row.co2)}</td>
      <td>${escapeHtml(row.humidity)}%</td>
      <td><span class="quality-pill ${qualityClass(row.quality)}">${escapeHtml(row.simple_quality || row.quality)}</span></td>
    </tr>
  `).join('');
}

function renderAirTimeline(rows = []) {
  if (!rows.length) {
    elements.airTimeline.innerHTML = '<div class="timeline-empty">No hourly air data available.</div>';
    return;
  }
  elements.airTimeline.innerHTML = rows.map(row => `
    <div class="timeline-hour ${qualityClass(row.quality)}" title="${escapeHtml(row.location)} ${escapeHtml(row.quality)} PM2.5 ${escapeHtml(row.pm25)}">
      <strong>${escapeHtml(row.time_label)}</strong>
      <span>${escapeHtml(row.quality)}</span>
      <small>PM2.5 ${escapeHtml(row.pm25)}</small>
    </div>
  `).join('');
}

function renderOutcome(outcome = {}) {
  const severity = outcome.severity || 'moderate';
  elements.dataOutcomeCard.className = `outcome-card ${severity}`;
  elements.outcomeHeadline.textContent = outcome.headline || 'No matching data outcome found';
  elements.outcomeAdvice.textContent = outcome.health_advice || 'Try a different location, time, or air-quality value.';
  elements.outcomeRisk.textContent = outcome.risk_index ?? '--';
  elements.outcomeAction.textContent = outcome.action || 'No action can be calculated from the current data.';
}

function setFormValue(formId, name, value) {
  const input = document.querySelector(`#${formId} [name="${name}"]`);
  if (input && value !== undefined && value !== null && value !== '') input.value = value;
}

function syncOperationsFromData(data = {}) {
  const road = data.roads?.[0];
  const air = data.air?.[0];
  const outcome = data.outcome || {};
  const hour = Number(String(road?.time ?? air?.time ?? new Date().getHours()).replace(/\D/g, '')) || new Date().getHours();

  if (road) {
    setFormValue('trafficForm', 'location', road.location);
    setFormValue('trafficForm', 'time', road.time);
    setFormValue('trafficForm', 'vehicle_count', road.vehicle_count);
    setFormValue('trafficForm', 'weather', road.weather);
    setFormValue('trafficForm', 'road_type', road.road_type);
    elements.trafficLiveArea.textContent = road.location;
    elements.trafficLiveVehicles.textContent = road.vehicle_count;
    elements.trafficLiveLevel.textContent = road.traffic_level;
  } else if (outcome.location) {
    setFormValue('trafficForm', 'location', outcome.location);
    setFormValue('trafficForm', 'time', hour);
    elements.trafficLiveArea.textContent = outcome.location;
    elements.trafficLiveLevel.textContent = outcome.traffic_level || 'Live';
  }

  if (air) {
    setFormValue('pollutionForm', 'co2', Math.round(Number(air.co2)));
    setFormValue('pollutionForm', 'pm25', Math.round(Number(air.pm25)));
    setFormValue('pollutionForm', 'temperature', Math.round(Number(air.temperature)));
    setFormValue('pollutionForm', 'humidity', Math.round(Number(air.humidity)));
    setFormValue('pollutionForm', 'traffic_level', air.traffic_level);
    elements.airLivePm25.textContent = Math.round(Number(air.pm25));
    elements.airLiveCo2.textContent = Math.round(Number(air.co2));
    elements.airLiveQuality.textContent = air.simple_quality || air.quality;
  }

  setFormValue('energyForm', 'area', outcome.location || road?.location || 'Mumbai');
  setFormValue('energyForm', 'population', road?.vehicle_count ? Math.max(3500, Number(road.vehicle_count) * 70) : 9000);
  setFormValue('energyForm', 'temperature', air?.temperature ? Math.round(Number(air.temperature)) : 34);
  setFormValue('energyForm', 'time', hour);
  const numericRisk = Number(outcome.risk_index);
  setFormValue('energyForm', 'previous_usage', Number.isFinite(numericRisk) ? Math.max(60, Math.round(numericRisk * 1.35)) : 110);
  elements.energyLiveArea.textContent = outcome.location || road?.location || 'Mumbai';
  elements.energyLiveUsage.textContent = document.querySelector('#energyForm [name="previous_usage"]')?.value || '110';
  elements.energyLiveLoad.textContent = outcome.severity === 'critical' ? 'Critical' : outcome.severity === 'warning' ? 'High' : 'Normal';
}

function renderCityRecords(data) {
  renderRoadRows(data?.roads || []);
  renderAirRows(data?.air || []);
  renderAirTimeline(data?.air_timeline || []);
  renderOutcome(data?.outcome || {});
  syncOperationsFromData(data || {});
  const totals = data?.totals || {};
  elements.dataExplorerSummary.innerHTML = `
    <span>Roads shown <strong>${totals.matched_roads ?? 0}</strong> of ${totals.roads ?? 0}</span>
    <span>Air records shown <strong>${totals.matched_air ?? 0}</strong> of ${totals.air ?? 0}</span>
    <span>Coverage <strong>${totals.states ?? 0}</strong> states + <strong>${totals.union_territories ?? 0}</strong> UTs</span>
    <span>National cities <strong>${totals.national_cities ?? 0}</strong></span>
    <span>Type state, city, area, traffic, air quality, PM2.5, CO2, or time</span>
  `;
}

function renderStateCityRegistry(data) {
  const regions = data?.regions || [];
  if (!elements.stateRegistryGrid || !elements.stateRegistryCount) return;
  if (!regions.length) {
    elements.stateRegistryCount.textContent = '0 cities';
    elements.stateRegistryGrid.innerHTML = '<div class="registry-empty">State and city data is not available.</div>';
    return;
  }

  elements.stateRegistryCount.textContent = `${data.states || 0} states + ${data.union_territories || 0} UTs | ${data.cities || 0} cities`;
  elements.stateRegistryGrid.innerHTML = regions.map(region => {
    const cities = region.cities || [];
    const cityButtons = cities.map(city => `
      <button class="city-chip" type="button" data-city="${escapeHtml(city)}" data-region="${escapeHtml(region.state)}">
        ${escapeHtml(city)}
      </button>
    `).join('');
    return `
      <article class="registry-card">
        <div class="registry-card-head">
          <div>
            <span>${escapeHtml(region.type)}</span>
            <h4>${escapeHtml(region.state)}</h4>
          </div>
          <strong>${cities.length}</strong>
        </div>
        <p>Capital: <b>${escapeHtml(region.capital)}</b></p>
        <div class="city-chip-list">${cityButtons}</div>
      </article>
    `;
  }).join('');
}

async function loadStateCityRegistry() {
  const data = await fetchApi('/state-city-data', {}, { quiet: true });
  if (!data) {
    if (elements.stateRegistryCount) elements.stateRegistryCount.textContent = 'Offline';
    if (elements.stateRegistryGrid) elements.stateRegistryGrid.innerHTML = '<div class="registry-empty">Backend offline - state and city registry cannot be loaded.</div>';
    return;
  }
  renderStateCityRegistry(data);
}

function renderCapstoneSummary(data) {
  capstoneReportData = data;
  if (!data) return;
  const coverage = data.coverage || {};
  const datasets = data.datasets || {};
  const validation = data.validation || {};
  const modules = data.modules || [];

  const validationLabel = validation.model_validation_status === 'validated' ? 'Models validated' : 'More training data needed';
  if (elements.readinessScore) elements.readinessScore.textContent = validationLabel;
  if (elements.capstoneObjective) elements.capstoneObjective.textContent = data.objective || 'Dataset-driven smart city decision-support prototype.';
  if (elements.impactGrid) {
    elements.impactGrid.innerHTML = [
      ['States', coverage.states],
      ['Union territories', coverage.union_territories],
      ['Cities covered', coverage.cities],
      ['Road records', coverage.road_records],
      ['Air records', coverage.air_records],
      ['Generated map points', coverage.live_city_points],
    ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? '--')}</strong></div>`).join('');
  }
  if (elements.architectureFlow) {
    elements.architectureFlow.innerHTML = (data.architecture || []).map((step, index) => `
      <div class="architecture-step">
        <span>${String(index + 1).padStart(2, '0')}</span>
        <strong>${escapeHtml(step)}</strong>
      </div>
    `).join('');
  }
  if (elements.moduleValidationGrid) {
    elements.moduleValidationGrid.innerHTML = modules.map(module => {
      const validation = module.validation || {};
      const validationText = validation.status === 'validated'
        ? `5-fold macro F1: ${validation.macro_f1_mean} +/- ${validation.macro_f1_std}`
        : validation.message || 'Validation unavailable.';
      return `
        <article class="module-validation-card">
          <span>${escapeHtml(module.model)}</span>
          <h4>${escapeHtml(module.name)}</h4>
          <p><b>Input:</b> ${escapeHtml(module.input)}</p>
          <p><b>Output:</b> ${escapeHtml(module.output)}</p>
          <p><b>Training:</b> ${escapeHtml(module.training_rows)} CSV rows</p>
          <p><b>Validation:</b> ${escapeHtml(validationText)}</p>
        </article>
      `;
    }).join('');
  }
  if (elements.capstoneStrengths) {
    const datasetLine = `Datasets include ${datasets.traffic_rows || 0} traffic, ${datasets.pollution_rows || 0} pollution, and ${datasets.energy_rows || 0} energy training rows, extended with ${datasets.national_generated_records || 0} national city records.`;
    elements.capstoneStrengths.innerHTML = [datasetLine, ...(validation.strengths || [])].map(item => `<li>${escapeHtml(item)}</li>`).join('');
  }
}

async function loadCapstoneSummary() {
  const data = await fetchApi('/capstone-summary', {}, { quiet: true });
  if (!data) {
    if (elements.reportStatus) elements.reportStatus.textContent = 'Backend offline - capstone summary cannot be loaded.';
    return;
  }
  renderCapstoneSummary(data);
}

function exportCapstoneReport() {
  if (!capstoneReportData) {
    showToast('Capstone summary is still loading.', true);
    return;
  }
  const coverage = capstoneReportData.coverage || {};
  const validation = capstoneReportData.validation || {};
  const lines = [
    capstoneReportData.title,
    `Generated: ${capstoneReportData.generated_at}`,
    '',
    'Objective',
    capstoneReportData.objective,
    '',
    'Coverage',
    `States: ${coverage.states}`,
    `Union Territories: ${coverage.union_territories}`,
    `Cities: ${coverage.cities}`,
    `Road Records: ${coverage.road_records}`,
    `Air Records: ${coverage.air_records}`,
    '',
    'AI Modules',
    ...(capstoneReportData.modules || []).map(module => `${module.name}: ${module.model} | ${module.output}`),
    '',
    'Architecture',
    ...(capstoneReportData.architecture || []).map((step, index) => `${index + 1}. ${step}`),
    '',
    'Validation Strengths',
    ...(validation.strengths || []).map(item => `- ${item}`),
    '',
    `Model validation status: ${validation.model_validation_status || 'not assessed'}`,
  ];
  const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'AI-Smart-City-Capstone-Summary.txt';
  link.click();
  URL.revokeObjectURL(url);
  if (elements.reportStatus) elements.reportStatus.textContent = 'Project summary exported successfully.';
  showToast('Capstone summary exported.');
}

async function loadCityRecords(query = '') {
  const endpoint = `/city-records${query ? `?q=${encodeURIComponent(query)}` : ''}`;
  const data = await fetchApi(endpoint, {}, { quiet: true });
  if (!data) {
    elements.dataExplorerSummary.innerHTML = '<span>Backend offline - road and air data cannot be loaded.</span>';
    renderRoadRows([]);
    renderAirRows([]);
    renderAirTimeline([]);
    return;
  }
  renderCityRecords(data);
  return data;
}

async function runRealtimeSearch(query) {
  const search = String(query || '').trim();
  if (elements.dataSearchInput) elements.dataSearchInput.value = search;
  if (elements.realtimeSearchInput) elements.realtimeSearchInput.value = search;
  elements.realtimeSearchResult.textContent = search ? `Searching live city data for "${search}"...` : 'Loading current city outcome...';
  const [data, mapData] = await Promise.all([loadCityRecords(search), searchLiveMap(search)]);
  if (!data) {
    elements.realtimeSearchResult.textContent = 'Live search unavailable - backend is offline.';
    return;
  }
  if (!mapData?.results?.length) {
    const outcome = data.outcome || {};
    elements.realtimeSearchResult.innerHTML = `Dataset result: <strong>${escapeHtml(outcome.headline || 'No outcome found')}</strong>`;
    document.getElementById('data-explorer')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } else {
    document.getElementById('city-pulse')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

async function searchLiveMap(query) {
  const search = String(query || '').trim();
  const scope = document.getElementById('mapSearchScope')?.value || 'india';
  if (search.length < 2) return null;
  if (elements.realtimeSearchResult) elements.realtimeSearchResult.textContent = `Searching OpenStreetMap for "${search}"...`;
  const data = await fetchApi(`/map-search?q=${encodeURIComponent(search)}&scope=${encodeURIComponent(scope)}`, {}, { quiet: true });
  if (!data) {
    if (elements.realtimeSearchResult) elements.realtimeSearchResult.textContent = 'Live map search is unavailable; bundled locality results are still shown below.';
    return null;
  }
  liveMapResults = data.results || [];
  liveMapMarkers.forEach(marker => marker.remove());
  liveMapMarkers = [];
  if (!liveMapResults.length) {
    if (elements.realtimeSearchResult) elements.realtimeSearchResult.textContent = `OpenStreetMap found no Indian place matching "${search}".`;
    return data;
  }
  if (cityMap && typeof L !== 'undefined') {
    liveMapMarkers = liveMapResults.map((place, index) => {
      const marker = L.marker([place.lat, place.lng], {
        icon: L.divIcon({ className: '', html: '<span class="live-search-marker"></span>', iconSize: [22, 22], iconAnchor: [11, 11] })
      }).addTo(cityMap);
      marker.bindPopup(`<div class="map-popup"><strong>${escapeHtml(place.name)}</strong><span>${escapeHtml(place.display_name)}</span><span>District <b>${escapeHtml(place.district || place.administrative_scope || 'Not tagged')}</b></span><span>Taluk <b>${escapeHtml(place.taluk || 'Not tagged')}</b></span><span>Source <b>OpenStreetMap</b></span><span>Metrics <b>Demo only</b></span></div>`);
      if (index === 0) marker.openPopup();
      return marker;
    });
    cityMap.fitBounds(L.latLngBounds(liveMapResults.map(place => [place.lat, place.lng])), { padding: [45, 45], maxZoom: 15 });
  }
  if (elements.realtimeSearchResult) {
    elements.realtimeSearchResult.innerHTML = `<strong>Live map matches</strong><div class="map-search-results">${liveMapResults.slice(0, 6).map((place, index) => `
      <button type="button" data-map-result="${index}"><b>${escapeHtml(place.name)} · ${escapeHtml(place.administrative_scope || 'India')}</b><span>${escapeHtml(place.display_name)}</span><span>${escapeHtml(place.district || 'District not tagged')} · ${escapeHtml(place.taluk || 'Taluk not tagged')}</span></button>
    `).join('')}</div><small>${escapeHtml(data.attribution || 'OpenStreetMap contributors')} · Scope: ${escapeHtml(scope.replaceAll('_', ' '))}. Geographic result only; operational metrics remain dataset-derived demo values.</small>`;
  }
  return data;
}

async function loadInsights(showMessage = false) {
  const data = await fetchApi('/stats', {}, { quiet: !showMessage });
  if (!data) {
    renderChart({ Traffic: 18, Pollution: 14, Energy: 21 });
    elements.recommendationList.innerHTML = '<li>Connect the backend to receive live AI recommendations.</li><li>Monitor priority corridors during predicted peak demand.</li><li>Review sensor health before dispatching field resources.</li>';
    return;
  }
  const chartData = {
    Traffic: Object.values(data.charts?.traffic_levels || {}).reduce((sum, value) => sum + value, 0),
    Pollution: Object.values(data.charts?.pollution_levels || {}).reduce((sum, value) => sum + value, 0),
    Energy: Object.values(data.charts?.energy_levels || {}).reduce((sum, value) => sum + value, 0)
  };
  renderChart(chartData);
  elements.recommendationList.innerHTML = (data.recommendations || []).map(item => `<li>${escapeHtml(item)}</li>`).join('');
  updateOperationalMetrics({ networkHealth: data.operational?.network_health, connectedZones: data.operational?.connected_zones, activeIncidents: data.operational?.active_incidents, aiDecisions: data.operational?.ai_decisions });
  if (showMessage) showToast('City intelligence refreshed.');
}

async function updateIncident(incidentId, payload) {
  const data = await fetchApi(`/incidents/${incidentId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (data) { showToast(`Incident #${incidentId} updated to ${data.status}.`); loadIncidents(); loadInsights(false); }
}

function startVoiceInput() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) { showToast('Voice input is not supported by this browser.', true); return; }
  const recognition = new SpeechRecognition();
  recognition.lang = 'en-IN'; recognition.interimResults = false;
  recognition.onresult = event => { const input = document.querySelector('#assistantForm [name="question"]'); if (input) input.value = event.results[0][0].transcript; };
  recognition.onerror = () => showToast('Voice input could not be captured.', true);
  recognition.start(); showToast('Listening for your question...');
}

function toggleTheme() {
  document.body.classList.toggle('light-mode');
  const light = document.body.classList.contains('light-mode');
  elements.themeToggle.textContent = light ? 'LT' : 'DK';
  elements.themeToggle.setAttribute('aria-label', light ? 'Switch to dark theme' : 'Switch to light theme');
  localStorage.setItem('urbanos-theme', light ? 'light' : 'dark');
  if (overviewChart) loadInsights(false);
}

function toggleSidebar(force) {
  const open = typeof force === 'boolean' ? force : !elements.sidebar.classList.contains('open');
  elements.sidebar.classList.toggle('open', open);
  elements.mobileOverlay.classList.toggle('show', open);
  elements.menuButton.setAttribute('aria-expanded', String(open));
}

function setupNavigation() {
  document.querySelectorAll('.nav-link').forEach(link => link.addEventListener('click', event => {
    document.querySelectorAll('.nav-link').forEach(item => item.classList.remove('active'));
    link.classList.add('active');
    toggleSidebar(false);
    const targetMap = { '#prediction-engine': '.forecast-panel', '#anomaly-detection': '#anomalyGrid', '#performance-ranking': '#rankingTable' };
    const target = document.querySelector(link.getAttribute('href')) || document.querySelector(targetMap[link.getAttribute('href')]);
    if (target) { event.preventDefault(); history.replaceState(null, '', link.getAttribute('href')); setTimeout(() => target.scrollIntoView({ behavior: 'smooth', block: 'start' }), 30); }
  }));
}

elements.toggleApi.addEventListener('click', () => {
  apiExpanded = !apiExpanded;
  elements.result.hidden = !apiExpanded;
  elements.toggleApi.textContent = apiExpanded ? 'Collapse' : 'Expand';
});
elements.themeToggle.addEventListener('click', toggleTheme);
elements.menuButton.addEventListener('click', () => toggleSidebar());
elements.mobileOverlay.addEventListener('click', () => toggleSidebar(false));
$('#healthButton').addEventListener('click', async () => {
  const data = await fetchApi('/health');
  if ('Notification' in window && Notification.permission === 'default') await Notification.requestPermission();
  if (data) showToast('Diagnostics complete - all backend services operational.');
});
$('#statsButton').addEventListener('click', () => {
  loadInsights(true);
  loadLiveData(true);
  loadCityRecords(elements.dataSearchInput?.value || '');
  loadStateCityRegistry();
  loadCapstoneSummary();
});
$('#trafficForm').addEventListener('submit', event => handlePrediction(event, '/predict/traffic', 'trafficResult'));
$('#pollutionForm').addEventListener('submit', event => handlePrediction(event, '/predict/pollution', 'pollutionResult'));
$('#energyForm').addEventListener('submit', event => handlePrediction(event, '/predict/energy', 'energyResult'));
elements.dataSearchInput?.addEventListener('input', event => {
  clearTimeout(dataSearchTimer);
  dataSearchTimer = setTimeout(() => {
    const search = event.target.value.trim();
    if (elements.realtimeSearchInput) elements.realtimeSearchInput.value = search;
    loadCityRecords(search);
  }, 180);
});
elements.realtimeSearchButton?.addEventListener('click', () => runRealtimeSearch(elements.realtimeSearchInput?.value || ''));
elements.realtimeSearchInput?.addEventListener('keydown', event => {
  if (event.key === 'Enter') {
    event.preventDefault();
    runRealtimeSearch(event.currentTarget.value);
  }
});
elements.realtimeSearchResult?.addEventListener('click', event => {
  const button = event.target.closest('[data-map-result]');
  if (!button || !cityMap) return;
  const place = liveMapResults[Number(button.dataset.mapResult)];
  if (!place) return;
  cityMap.setView([place.lat, place.lng], 16);
  liveMapMarkers[Number(button.dataset.mapResult)]?.openPopup();
  document.getElementById('city-pulse')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
});
elements.stateRegistryGrid?.addEventListener('click', event => {
  const button = event.target.closest('.city-chip');
  if (!button) return;
  runRealtimeSearch(button.dataset.city || button.dataset.region || '');
});
elements.exportReportButton?.addEventListener('click', exportCapstoneReport);
document.getElementById('assistantForm')?.addEventListener('submit', submitAssistant);
document.getElementById('twinForm')?.addEventListener('submit', submitTwin);
document.getElementById('grievanceForm')?.addEventListener('submit', submitGrievance);
document.getElementById('voiceInputButton')?.addEventListener('click', startVoiceInput);
document.querySelector('.suggested-questions')?.addEventListener('click', event => {
  const button = event.target.closest('[data-question]'); if (!button) return;
  const input = document.querySelector('#assistantForm [name="question"]'); if (input) input.value = button.dataset.question;
});
document.getElementById('downloadForensicButton')?.addEventListener('click', () => { window.location.href = `${API_BASE}/reports/incidents.pdf`; });
document.getElementById('emergencyGrid')?.addEventListener('click', event => {
  const assign = event.target.closest('[data-assign-incident]');
  const statusButton = event.target.closest('[data-incident-status]');
  if (assign) { const id = assign.dataset.assignIncident; const team = document.querySelector(`[data-team-for="${id}"]`)?.value; updateIncident(id, { assigned_team: team, response_eta: 8 + Number(id) % 12, status: 'acknowledged' }); }
  if (statusButton) updateIncident(statusButton.dataset.incidentId, { status: statusButton.dataset.incidentStatus });
});

window.addEventListener('DOMContentLoaded', () => {
  if (localStorage.getItem('urbanos-theme') === 'light') document.body.classList.add('light-mode');
  elements.themeToggle.textContent = document.body.classList.contains('light-mode') ? 'LT' : 'DK';
  renderMetroCities();
  renderAlerts();
  initCityMap();
  updateClock();
  setupNavigation();
  setInterval(updateClock, 30000);
  setInterval(() => { loadLiveData(true); loadIncidents(); loadAdvancedIntelligence(); loadPlatform(); }, 30000);
  fetchApi('/health', {}, { quiet: true });
  loadLiveData(true);
  loadCityRecords();
  loadStateCityRegistry();
  loadCapstoneSummary();
  loadInsights(false);
  loadHistory(true);
  loadIncidents();
  loadAdvancedIntelligence();
  loadPlatform();
  setupTwinCityScene();
});
