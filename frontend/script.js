const ui = {
    text: document.getElementById('activityText'), analyze: document.getElementById('analyzeButton'),
    example: document.getElementById('exampleButton'), error: document.getElementById('errorMessage'),
    questionPanel: document.getElementById('questionPanel'), questionPrompt: document.getElementById('questionPrompt'),
    questionContext: document.getElementById('questionContext'), questionInput: document.getElementById('questionInput'),
    evidenceTools: document.getElementById('evidenceTools'), answer: document.getElementById('answerButton'),
    results: document.getElementById('results'), authStatus: document.getElementById('authStatus'),
};

const ACTIVITY_LABELS = [
    'Auto Rickshaw', 'Bike', 'Bus', 'Car', 'Petrol Car', 'Diesel Car', 'Hybrid Car',
    'Electric Car', 'Domestic Flight', 'International Flight', 'Metro', 'Motorcycle',
    'Scooter', 'Taxi', 'Train', 'Walking', 'Vegetarian Meal', 'Chicken Meal',
    'Beef Meal', 'Fish Meal', 'Lamb Meal', 'Pork Meal', 'Electricity',
];
let currentSession = null;
let currentQuestion = null;
let currentData = null;
let capabilities = {};
let authToken = localStorage.getItem('carbonAuthToken');
let signedInUser = null;
let mapsConfig = {available: false};
let googleMapsPromise = null;
let lastRouteRequest = null;
const placeSessionToken = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;

function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function showError(message) {
    ui.error.textContent = message || '';
    ui.error.hidden = !message;
}

function setBusy(busy, label = 'Working…') {
    ui.analyze.disabled = busy;
    ui.answer.disabled = busy;
    if (busy) {
        ui.analyze.dataset.label ||= ui.analyze.textContent;
        ui.analyze.textContent = label;
    } else if (ui.analyze.dataset.label) {
        ui.analyze.textContent = ui.analyze.dataset.label;
    }
}

async function api(path, {method = 'GET', body, form} = {}) {
    const headers = {};
    if (authToken) headers.Authorization = `Bearer ${authToken}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {
        method, headers, body: form || (body !== undefined ? JSON.stringify(body) : undefined),
    });
    if (response.status === 204) return null;
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    return data;
}

async function analyzeText() {
    const text = ui.text.value.trim();
    if (!text) return showError('Describe at least one activity first.');
    showError(''); setBusy(true, 'Reading activity log…');
    try { render(await api('/api/analyze', {method: 'POST', body: {text}})); }
    catch (error) { showError(error.message); }
    finally { setBusy(false); }
}

function render(data) {
    currentData = data; currentSession = data.session_id; currentQuestion = data.question;
    renderQuestion(data.question); renderResult(data);
    if (data.route_evidence) renderRouteEvidence(data.route_evidence);
}

function renderQuestion(question) {
    ui.questionPanel.hidden = !question;
    ui.questionInput.replaceChildren(); ui.evidenceTools.replaceChildren();
    if (!question) return;
    ui.questionPrompt.textContent = question.prompt;
    const metrics = question.utility_metrics;
    const metricText = metrics?.expected_range_reduction_kg == null ? '' :
        ` Expected range reduction: ${metrics.expected_range_reduction_kg} kg.`;
    ui.questionContext.textContent = `From “${question.source_text}” · ${question.reason}${metricText}`;
    if (question.input_type === 'choice') {
        const grid = element('div', 'choice-grid');
        question.options.forEach((option, index) => {
            const label = element('label', 'choice');
            const input = document.createElement('input');
            input.type = 'radio'; input.name = 'clarification'; input.value = option.value;
            if (index === 0) input.checked = true;
            label.append(input, element('span', '', option.label)); grid.append(label);
        });
        ui.questionInput.append(grid);
    } else {
        const wrap = element('label', 'number-field');
        const input = document.createElement('input');
        input.type = 'number'; input.min = '0.001'; input.step = 'any'; input.id = 'clarificationNumber';
        input.placeholder = `Enter ${question.unit}`;
        wrap.append(input, element('span', '', question.unit));
        const evidence = element('div', 'evidence-fields');
        const source = document.createElement('select'); source.id = 'evidenceSource';
        [['user-confirmed', 'My estimate'], ['measured', 'Measured value'],
         ['bill-or-meter', 'Bill or meter'], ['route-service', 'Routing service']].forEach(([value, label]) => {
            const option = document.createElement('option'); option.value = value; option.textContent = label; source.append(option);
        });
        const reference = document.createElement('input'); reference.id = 'evidenceReference';
        reference.placeholder = 'Optional evidence note or reference';
        evidence.append(source, reference);
        if (question.field === 'distance_km') {
            renderRouteTool();
            const fallback = element('details', 'manual-distance-fallback');
            fallback.append(element('summary', '', 'Cannot use Maps? Enter distance manually instead'), wrap, evidence);
            ui.evidenceTools.append(fallback);
        } else {
            ui.questionInput.append(wrap, evidence);
        }
        if (question.field === 'electricity_kwh') renderBillTool();
    }
    ui.questionPanel.scrollIntoView({behavior: 'smooth', block: 'center'});
}

function renderRouteTool() {
    const box = element('div', 'provider-tool');
    box.append(element('strong', '', capabilities.routing?.google_routes ?
        'Get distance automatically from Google Maps' :
        'Automatic Google distance needs GOOGLE_MAPS_API_KEY'));
    const provider = document.createElement('select'); provider.id = 'routeProvider';
    if (capabilities.routing?.google_routes) {
        const option = document.createElement('option'); option.value = 'google'; option.textContent = 'Google Routes (addresses or coordinates)'; provider.append(option);
    }
    const osrm = document.createElement('option'); osrm.value = 'osrm'; osrm.textContent = 'OSRM (latitude, longitude)'; provider.append(osrm);
    const activity = currentData?.extracted_activities?.find(item => item.event_id === currentQuestion.event_id);
    const routeHints = activity?.attributes || {};
    const googleAvailable = Boolean(capabilities.routing?.google_routes);
    const origin = document.createElement('input'); origin.id = 'routeOrigin';
    origin.placeholder = googleAvailable ? 'Origin address' : 'Origin: latitude, longitude';
    origin.value = googleAvailable ? (routeHints.route_origin || '') : '';
    const destination = document.createElement('input'); destination.id = 'routeDestination';
    destination.placeholder = googleAvailable ? 'Destination address' : 'Destination: latitude, longitude';
    destination.value = googleAvailable ? (routeHints.route_destination || '') : '';
    const originSuggestions = document.createElement('datalist'); originSuggestions.id = 'routeOriginSuggestions';
    const destinationSuggestions = document.createElement('datalist'); destinationSuggestions.id = 'routeDestinationSuggestions';
    if (googleAvailable) {
        origin.setAttribute('list', originSuggestions.id);
        destination.setAttribute('list', destinationSuggestions.id);
    }
    const locate = element('button', 'secondary-button locate-button', 'Use my current location');
    locate.type = 'button'; locate.addEventListener('click', () => useCurrentLocation(origin));
    const consentLabel = element('label', 'consent');
    const consent = document.createElement('input'); consent.type = 'checkbox'; consent.id = 'routeConsent';
    consentLabel.append(consent, element('span', '', 'I consent to sending these locations to the selected routing provider.'));
    const button = element('button', 'secondary-button', 'Verify route'); button.type = 'button';
    button.addEventListener('click', verifyRoute);
    box.append(provider, origin, destination, locate, originSuggestions, destinationSuggestions,
        consentLabel, button,
        element('p', 'provider-note', capabilities.routing?.privacy_notice || 'Location consent is required.'));
    ui.evidenceTools.append(box);
    provider.addEventListener('change', () => {
        const addresses = provider.value === 'google';
        origin.placeholder = addresses ? 'Origin address' : 'Origin: latitude, longitude';
        destination.placeholder = addresses ? 'Destination address' : 'Destination: latitude, longitude';
        if (!addresses && routeHints.route_origin) origin.value = '';
        if (!addresses && routeHints.route_destination) destination.value = '';
    });
    [origin, destination].forEach(input => input.addEventListener('input', () => {
        delete input.dataset.latitude; delete input.dataset.longitude;
    }));
    if (googleAvailable) {
        bindPlaceSuggestions(origin, originSuggestions, consent);
        bindPlaceSuggestions(destination, destinationSuggestions, consent);
    }
}

function bindPlaceSuggestions(input, datalist, consent) {
    let timer;
    input.addEventListener('input', () => {
        clearTimeout(timer);
        if (!consent.checked || input.value.trim().length < 2) return;
        timer = setTimeout(async () => {
            try {
                const result = await api('/api/places/autocomplete', {method: 'POST', body: {
                    query: input.value.trim(), session_token: placeSessionToken,
                    consent_external_processing: true,
                }});
                datalist.replaceChildren(...result.suggestions.map(item => {
                    const option = document.createElement('option'); option.value = item.text;
                    option.dataset.placeId = item.place_id; return option;
                }));
            } catch (error) { showError(error.message); }
        }, 300);
    });
}

function routeLocation(input, provider) {
    if (input.dataset.latitude && input.dataset.longitude) {
        return {latitude: Number(input.dataset.latitude), longitude: Number(input.dataset.longitude)};
    }
    if (provider === 'google') {
        if (!input.value.trim()) throw new Error('Both route locations are required.');
        return input.value.trim();
    }
    const parts = input.value.split(',').map(Number);
    if (parts.length !== 2 || parts.some(Number.isNaN)) throw new Error('OSRM locations must use latitude, longitude.');
    return {latitude: parts[0], longitude: parts[1]};
}

function useCurrentLocation(originInput) {
    if (!navigator.geolocation) return showError('This browser does not provide location access.');
    showError('');
    navigator.geolocation.getCurrentPosition(position => {
        const {latitude, longitude} = position.coords;
        originInput.dataset.latitude = latitude;
        originInput.dataset.longitude = longitude;
        originInput.value = `Current location (${latitude.toFixed(5)}, ${longitude.toFixed(5)})`;
    }, error => showError(`Location was not available: ${error.message}`), {
        enableHighAccuracy: true, timeout: 10000, maximumAge: 60000,
    });
}

async function verifyRoute() {
    try {
        const provider = document.getElementById('routeProvider').value;
        const activity = currentData?.extracted_activities?.find(item => item.event_id === currentQuestion.event_id);
        const routeMode = {
            bus: 'transit', train: 'transit', metro: 'transit', bike: 'cycling',
            bicycle: 'cycling', walking: 'walking', walk: 'walking',
            motorcycle: 'two_wheeler', motorbike: 'two_wheeler', scooter: 'two_wheeler',
        }[activity?.attributes?.route_mode] || 'driving';
        const payload = {
            session_id: currentSession, event_id: currentQuestion.event_id, provider,
            origin: routeLocation(document.getElementById('routeOrigin'), provider),
            destination: routeLocation(document.getElementById('routeDestination'), provider),
            mode: routeMode,
            consent_external_processing: document.getElementById('routeConsent').checked,
        };
        lastRouteRequest = payload;
        render(await api('/api/evidence/route', {method: 'POST', body: payload}));
    } catch (error) { showError(error.message); }
}

function googleMapsUrl(origin, destination, mode = 'driving') {
    const locationText = value => typeof value === 'string' ? value : `${value.latitude},${value.longitude}`;
    const parameters = new URLSearchParams({
        api: '1', origin: locationText(origin), destination: locationText(destination),
        travelmode: mode === 'two_wheeler' ? 'driving' : mode,
    });
    return `https://www.google.com/maps/dir/?${parameters}`;
}

async function selectRouteAlternative(index) {
    if (!lastRouteRequest) return;
    try {
        render(await api('/api/evidence/route', {
            method: 'POST', body: {...lastRouteRequest, route_index: index},
        }));
    } catch (error) { showError(error.message); }
}

function renderRouteEvidence(route) {
    const panel = document.getElementById('routePreviewPanel');
    panel.hidden = false;
    document.getElementById('routePreviewTitle').textContent = `${route.distance_km.toFixed(3)} km via ${route.provider}`;
    document.getElementById('routePreviewSummary').textContent =
        `Provider distance: ${route.distance_km.toFixed(3)} km${route.duration ? ` · duration ${route.duration}` : ''}.`;
    const link = document.getElementById('openGoogleMaps');
    if (lastRouteRequest) link.href = googleMapsUrl(lastRouteRequest.origin, lastRouteRequest.destination, lastRouteRequest.mode);
    link.hidden = !lastRouteRequest;

    const alternatives = document.getElementById('routeAlternatives');
    alternatives.replaceChildren();
    (route.alternatives || []).forEach((item, index) => {
        const button = element('button', index === route.selected_index ? 'route-choice selected' : 'route-choice',
            `Route ${index + 1}: ${item.distance_km.toFixed(3)} km${item.duration ? ` · ${item.duration}` : ''}`);
        button.type = 'button'; button.disabled = index === route.selected_index;
        button.addEventListener('click', () => selectRouteAlternative(index));
        alternatives.append(button);
    });
    if (route.encoded_polyline && mapsConfig.available) showGoogleRoute(route.encoded_polyline);
}

function loadGoogleMaps() {
    if (window.google?.maps) return Promise.resolve(window.google.maps);
    if (!mapsConfig.available) return Promise.reject(new Error('Embedded Google Map is not configured.'));
    if (!googleMapsPromise) googleMapsPromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(mapsConfig.browser_key)}&v=weekly&libraries=geometry`;
        script.async = true; script.onload = () => resolve(window.google.maps);
        script.onerror = () => reject(new Error('Google Maps could not be loaded.'));
        document.head.append(script);
    });
    return googleMapsPromise;
}

async function showGoogleRoute(encodedPolyline) {
    try {
        const maps = await loadGoogleMaps();
        const path = maps.geometry.encoding.decodePath(encodedPolyline);
        const mapElement = document.getElementById('routeMap'); mapElement.hidden = false;
        const map = new maps.Map(mapElement, {mapTypeControl: false, streetViewControl: false});
        new maps.Polyline({path, map, strokeColor: '#126849', strokeOpacity: 0.95, strokeWeight: 6});
        const bounds = new maps.LatLngBounds(); path.forEach(point => bounds.extend(point)); map.fitBounds(bounds, 40);
    } catch (error) { showError(error.message); }
}

function renderBillTool() {
    const box = element('div', 'provider-tool');
    box.append(element('strong', '', 'Read an electricity bill or meter image locally'));
    const input = document.createElement('input'); input.type = 'file'; input.id = 'billFile'; input.accept = 'image/*';
    const button = element('button', 'secondary-button', 'Extract kWh'); button.type = 'button';
    button.disabled = !capabilities.bill_ocr?.available; button.addEventListener('click', extractBill);
    box.append(input, button, element('p', 'provider-note', capabilities.bill_ocr?.available ?
        'The image is processed locally and is not retained.' : 'Python OCR support is installed; install the Tesseract 5 executable to enable image reading.'));
    ui.evidenceTools.append(box);
}

async function extractBill() {
    const file = document.getElementById('billFile').files[0];
    if (!file) return showError('Choose a bill or meter image first.');
    const form = new FormData(); form.append('bill', file); form.append('session_id', currentSession);
    form.append('event_id', currentQuestion.event_id);
    try {
        const result = await api('/api/evidence/bill', {method: 'POST', form});
        if (result.recommended_kwh == null) throw new Error('OCR could not find a kWh value. Review the image and enter it manually.');
        document.getElementById('clarificationNumber').value = result.recommended_kwh;
        document.getElementById('evidenceSource').value = 'bill-or-meter';
        document.getElementById('evidenceReference').value = `OCR ${result.sha256.slice(0, 12)}; confidence ${result.confidence}`;
        showError(result.review_required ? 'OCR found a value. Review it before applying.' : '');
    } catch (error) { showError(error.message); }
}

async function submitAnswer() {
    if (!currentQuestion || !currentSession) return;
    const selected = document.querySelector('input[name="clarification"]:checked');
    const numeric = document.getElementById('clarificationNumber');
    const value = selected ? selected.value : numeric?.value;
    if (!value) return showError('Provide an answer to continue.');
    const answer = numeric ? {value, source_type: document.getElementById('evidenceSource').value,
        reference: document.getElementById('evidenceReference').value || null} : value;
    showError(''); setBusy(true);
    try { render(await api('/api/clarify', {method: 'POST', body: {
        session_id: currentSession, question_id: currentQuestion.question_id, answer,
    }})); } catch (error) { showError(error.message); } finally { setBusy(false); }
}

function renderResult(data) {
    ui.results.hidden = false;
    document.getElementById('totalCO2').textContent = Number(data.total_co2_kg).toFixed(2);
    document.getElementById('totalRange').textContent = `${data.total_co2_range_kg.low.toFixed(2)}–${data.total_co2_range_kg.high.toFixed(2)} kg`;
    document.getElementById('benchmarkMsg').textContent = data.benchmark.message;
    const badge = document.getElementById('confidenceBadge'); badge.textContent = data.confidence.replaceAll('-', ' ');
    document.getElementById('saveButton').disabled = data.status !== 'complete' || !signedInUser;
    document.getElementById('saveStatus').textContent = !signedInUser ? 'Sign in to save encrypted history.' :
        (data.status === 'complete' ? '' : 'Resolve the current question before saving.');
    renderCategoryChart(data.breakdown);

    const list = document.getElementById('breakdownList'); list.replaceChildren();
    document.getElementById('activityCount').textContent = `${data.breakdown.length} calculated`;
    data.breakdown.forEach(item => list.append(activityCard(item)));
    data.unresolved_activities.forEach(item => {
        const card = element('article', 'activity-card unresolved');
        card.append(element('strong', '', `${item.activity} · awaiting ${item.reason.replace('-', ' ')}`),
                    element('p', '', item.source_text || 'A required input is missing.')); list.append(card);
    });
    if (!data.breakdown.length && !data.unresolved_activities.length) {
        list.append(element('p', 'empty', 'No supported activity was recognized. Include an activity and quantity, such as “travelled 12 km by bus”.'));
    }
    renderRecommendations(data.recommendations);
    const audit = document.getElementById('auditContent'); audit.replaceChildren(
        element('p', '', data.method.equation), element('p', '', data.method.uncertainty),
        element('p', 'warning', 'Illustrative factors remain for categories without an authoritative source. Check each factor record before publication.'),
        element('code', '', `${data.audit_graph.nodes.length} evidence nodes · ${data.audit_graph.edges.length} trace links · factor version ${data.method.factor_version}`),
    );
}

function activityCard(item) {
    const card = element('article', 'activity-card');
    const top = element('div', 'activity-top'); const title = element('div');
    title.append(element('strong', '', item.activity), element('p', '', `From “${item.source_text}”`));
    const value = element('div', 'activity-value'); value.append(element('strong', '', `${item.co2_kg.toFixed(2)} kg`),
        element('span', '', `${item.co2_range_kg.low.toFixed(2)}–${item.co2_range_kg.high.toFixed(2)}`));
    top.append(title, value); const meta = element('div', 'meta-row');
    [item.category, item.quantity_source.replaceAll('-', ' '), item.confidence.replaceAll('-', ' '),
     `${item.factor_candidates.length} factor candidate${item.factor_candidates.length === 1 ? '' : 's'}`]
        .forEach(text => meta.append(element('span', 'mini-badge', text)));
    card.append(top, meta, correctionEditor(item)); return card;
}

function correctionEditor(item) {
    const details = element('details', 'correction-editor');
    details.append(element('summary', '', signedInUser ? 'Correct this extraction' : 'Sign in to teach corrections'));
    const controls = element('div', 'correction-controls'); const select = document.createElement('select');
    ACTIVITY_LABELS.forEach(label => { const option = document.createElement('option'); option.value = label;
        option.textContent = label; option.selected = label === item.label; select.append(option); });
    const quantity = document.createElement('input'); quantity.type = 'number'; quantity.step = 'any'; quantity.value = item.quantity;
    const button = element('button', 'secondary-button', 'Save correction'); button.disabled = !signedInUser;
    button.addEventListener('click', async () => {
        try { render(await api('/api/corrections', {method: 'POST', body: {
            session_id: currentSession, event_id: item.event_id, label: select.value,
            quantity: quantity.value, unit: item.unit,
        }})); } catch (error) { showError(error.message); }
    });
    controls.append(select, quantity, button); details.append(controls); return details;
}

function renderRecommendations(items) {
    const panel = document.getElementById('recommendationPanel'); const list = document.getElementById('recommendationList');
    list.replaceChildren(); panel.hidden = !items.length;
    items.forEach(item => { const row = element('div', 'recommendation'); row.append(element('p', '', item.message),
        element('strong', '', `≈ ${item.estimated_saving_kg.toFixed(2)} kg lower`),
        element('span', 'mini-badge', item.decision_status.replace('-', ' '))); list.append(row); });
}

function renderCategoryChart(breakdown) {
    const chart = document.getElementById('categoryChart'); chart.replaceChildren();
    const totals = breakdown.reduce((acc, item) => ({...acc, [item.category]: (acc[item.category] || 0) + item.co2_kg}), {});
    renderBars(chart, Object.entries(totals).map(([label, value]) => ({label, value})));
}

function renderBars(container, rows) {
    const maximum = Math.max(...rows.map(row => row.value), 0.001);
    rows.sort((a, b) => b.value - a.value).forEach(rowData => {
        const row = element('div', 'chart-row'); row.append(element('span', '', rowData.label));
        const track = element('div', 'chart-track'); const fill = element('div', 'chart-fill');
        fill.style.width = `${(rowData.value / maximum) * 100}%`; track.append(fill);
        row.append(track, element('strong', '', `${rowData.value.toFixed(2)} kg`)); container.append(row);
    });
    if (!rows.length) container.append(element('p', 'empty', 'Calculated values will appear here.'));
}

async function authenticate(mode) {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    try {
        const result = await api(`/api/auth/${mode}`, {method: 'POST', body: {username, password}});
        authToken = result.token; localStorage.setItem('carbonAuthToken', authToken); signedInUser = result.user;
        document.getElementById('password').value = ''; updateAuthUi(); await Promise.all([loadJournal(), loadDashboard()]);
        if (currentData) renderResult(currentData);
    } catch (error) { showError(error.message); }
}

async function restoreAuth() {
    if (!authToken) return updateAuthUi();
    try { signedInUser = (await api('/api/auth/me')).user; }
    catch { authToken = null; localStorage.removeItem('carbonAuthToken'); }
    updateAuthUi();
}

function updateAuthUi() {
    document.getElementById('authForm').hidden = Boolean(signedInUser);
    document.getElementById('logoutButton').hidden = !signedInUser;
    ui.authStatus.textContent = signedInUser ? `Signed in locally as ${signedInUser.username}. Journal records are encrypted.` :
        'Sign in to save encrypted history and corrections.';
}

async function logout() {
    try { await api('/api/auth/logout', {method: 'POST'}); } catch {}
    authToken = null; signedInUser = null; localStorage.removeItem('carbonAuthToken'); updateAuthUi();
    await loadJournal(); await loadDashboard(); if (currentData) renderResult(currentData);
}

async function saveCurrentResult() {
    if (!currentData || currentData.status !== 'complete' || !signedInUser) return;
    const button = document.getElementById('saveButton'); button.disabled = true;
    try { await api('/api/journal', {method: 'POST', body: {session_id: currentSession}});
        document.getElementById('saveStatus').textContent = 'Saved to encrypted local journal.';
        await Promise.all([loadJournal(), loadDashboard()]);
    } catch (error) { showError(error.message); button.disabled = false; }
}

async function loadJournal() {
    const list = document.getElementById('journalList'); list.replaceChildren();
    if (!signedInUser) { document.getElementById('journalCount').textContent = 'Private';
        list.append(element('p', 'empty', 'Sign in to view encrypted journal entries.')); return; }
    try {
        const data = await api('/api/journal?limit=30'); document.getElementById('journalCount').textContent = `${data.count} entr${data.count === 1 ? 'y' : 'ies'}`;
        data.entries.forEach(entry => {
            const row = element('article', 'journal-entry'); const copy = element('div');
            copy.append(element('strong', '', entry.entry_date), element('p', '', entry.original_text));
            const value = element('div', 'journal-value'); value.append(element('strong', '', `${entry.total_co2_kg.toFixed(2)} kg`),
                element('span', '', `${entry.total_co2_range_kg.low.toFixed(2)}–${entry.total_co2_range_kg.high.toFixed(2)}`));
            const remove = element('button', 'icon-button', 'Delete'); remove.addEventListener('click', async () => {
                if (!window.confirm('Delete this local journal entry?')) return;
                try { await api(`/api/journal/${entry.entry_id}`, {method: 'DELETE'}); await Promise.all([loadJournal(), loadDashboard()]); }
                catch (error) { showError(error.message); }
            }); row.append(copy, value, remove); list.append(row);
        });
        if (!data.entries.length) list.append(element('p', 'empty', 'No saved estimates yet.'));
    } catch (error) { list.append(element('p', 'error', error.message)); }
}

async function loadDashboard() {
    const chart = document.getElementById('trendChart'); const forecast = document.getElementById('forecastOutput');
    chart.replaceChildren(); forecast.hidden = true;
    if (!signedInUser) { chart.append(element('p', 'empty', 'Sign in and save estimates to build trends.')); return; }
    const month = document.getElementById('dashboardMonth').value;
    try {
        const data = await api(`/api/dashboard?month=${encodeURIComponent(month)}`);
        renderBars(chart, data.daily.map(day => ({label: day.date.slice(8), value: day.co2_kg})));
        document.getElementById('goalValue').value = data.goal?.target_kg || '';
        document.getElementById('goalProgress').textContent = data.goal ? `${data.total_co2_kg.toFixed(2)} kg recorded · ${data.goal_progress_percent}% of goal` : `${data.total_co2_kg.toFixed(2)} kg recorded`;
        if (data.forecast.status === 'ready') { const first = data.forecast.points[0]; forecast.hidden = false;
            forecast.textContent = `${data.forecast.method}: next-day estimate ${first.point_kg.toFixed(2)} kg (${first.low_kg.toFixed(2)}–${first.high_kg.toFixed(2)}). ${data.forecast.interpretation}`; }
    } catch (error) { chart.append(element('p', 'error', error.message)); }
}

async function saveGoal() {
    if (!signedInUser) return showError('Sign in before saving a private goal.');
    const month = document.getElementById('dashboardMonth').value;
    try { await api(`/api/goals/${month}`, {method: 'PUT', body: {target_kg: document.getElementById('goalValue').value}}); await loadDashboard(); }
    catch (error) { showError(error.message); }
}

function exportAudit() {
    if (!currentData) return;
    const blob = new Blob([JSON.stringify(currentData, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob); const link = document.createElement('a');
    link.href = url; link.download = `carbon-audit-${new Date().toISOString().slice(0, 10)}.json`; link.click();
    URL.revokeObjectURL(url);
}

async function initialize() {
    document.getElementById('dashboardMonth').value = new Date().toISOString().slice(0, 7);
    try {
        [capabilities, mapsConfig] = await Promise.all([api('/api/capabilities'), api('/api/maps/config')]);
    } catch (error) { showError(error.message); }
    await restoreAuth(); await Promise.all([loadJournal(), loadDashboard()]);
}

ui.analyze.addEventListener('click', analyzeText); ui.answer.addEventListener('click', submitAnswer);
ui.example.addEventListener('click', () => { ui.text.value = 'I drove my car 25 km to college, ate a vegetarian lunch, and used 4 kWh of electricity.'; ui.text.focus(); });
document.getElementById('saveButton').addEventListener('click', saveCurrentResult);
document.getElementById('exportButton').addEventListener('click', exportAudit);
document.getElementById('loginButton').addEventListener('click', () => authenticate('login'));
document.getElementById('registerButton').addEventListener('click', () => authenticate('register'));
document.getElementById('logoutButton').addEventListener('click', logout);
document.getElementById('goalButton').addEventListener('click', saveGoal);
document.getElementById('dashboardMonth').addEventListener('change', loadDashboard);
ui.text.addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') analyzeText(); });
initialize();
