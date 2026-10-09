const API_BASE = 'http://127.0.0.1:5000';
const LOCAL_RADIUS_KM = 50;
const DEFAULT_CENTER = { lat: 19.0760, lng: 72.8777 }; // Mumbai

let authToken = localStorage.getItem('token') || '';
let currentUser = JSON.parse(localStorage.getItem('user') || 'null');
let currentPosition = null;

let discoverMap = null;
let organizerMap = null;
let turfMap = null;
let turfOwnerFormMap = null;

let discoverMarker = null;
let organizerMarker = null;
let turfOwnerFormMarker = null;
let turfMarkersLayer = null;

let discoverGeocoder = null;
let organizerGeocoder = null;

const messageEl = document.getElementById('message');
const authStatusEl = document.getElementById('auth-status');
const logoutBtn = document.getElementById('logout-btn');
const organizerTabBtn = document.getElementById('organizer-tab-btn');
const turfOwnerTabBtn = document.getElementById('turf-owner-tab-btn');

const discoverLocationInput = document.getElementById('discover-location');
const discoverLatInput = document.getElementById('discover-lat');
const discoverLngInput = document.getElementById('discover-lng');
const applyDiscoverCoordsBtn = document.getElementById('apply-discover-coords');
const organizerLocationInput = document.getElementById('t-location');
const organizerCoordsEl = document.getElementById('t-location-coords');
const organizerMapFullscreenBtn = document.getElementById('organizer-map-fullscreen');
const organizerMapElement = document.getElementById('organizer-map');
const organizerRegistrationListEl = document.getElementById('organizer-registration-list');
const loadOrganizerRegistrationsBtn = document.getElementById('load-organizer-registrations-btn');

// New filter elements
const tournamentSearchInput = document.getElementById('tournament-search');
const sportFilterSelect = document.getElementById('sport-filter');
const feeFilterSelect = document.getElementById('fee-filter');
const clearFiltersBtn = document.getElementById('clear-filters');

function setMessage(text, isError = false) {
    messageEl.textContent = text;
    messageEl.className = isError ? 'message error' : 'message';
}

function getApiError(data, fallback) {
    if (data && typeof data === 'object') {
        return data.error || data.msg || fallback;
    }
    return fallback;
}

async function readApiPayload(res) {
    const text = await res.text();
    if (!text) {
        return {};
    }

    try {
        return JSON.parse(text);
    } catch (_) {
        return { error: text };
    }
}

function handleAuthFailure(status, data) {
    if (status === 401 || status === 422) {
        clearAuth();
        const err = getApiError(data, 'Session expired. Please login again.');
        const friendlyMsg = err.toLowerCase().includes('token has expired') || err.toLowerCase().includes('signature')
            ? 'Your session has expired. Please log in again to continue.'
            : err;
        setMessage(friendlyMsg, true);
        switchTab('auth-view');
        return true;
    }
    return false;
}

function authHeaders() {
    return {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${authToken}`,
    };
}

function switchTab(tabId) {
    document.querySelectorAll('.view').forEach((view) => view.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach((btn) => btn.classList.remove('active'));

    const targetView = document.getElementById(tabId);
    const targetBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);

    if (targetView) {
        targetView.classList.add('active');
    }
    if (targetBtn) {
        targetBtn.classList.add('active');
    }

    setTimeout(() => {
        if (typeof discoverMap !== 'undefined' && discoverMap) discoverMap.invalidateSize();
        if (typeof organizerMap !== 'undefined' && organizerMap) organizerMap.invalidateSize();
        if (typeof turfMap !== 'undefined' && turfMap) turfMap.invalidateSize();
        if (typeof turfOwnerFormMap !== 'undefined' && turfOwnerFormMap) turfOwnerFormMap.invalidateSize();
    }, 100);
}

function updateAuthUI() {
    if (currentUser) {
        authStatusEl.textContent = `Logged in as ${currentUser.name} (${currentUser.role})`;
        logoutBtn.classList.remove('hidden');
    } else {
        authStatusEl.textContent = 'Not logged in';
        logoutBtn.classList.add('hidden');
    }

    if (currentUser && currentUser.role === 'organizer') {
        if (organizerTabBtn) organizerTabBtn.classList.remove('hidden');
    } else {
        if (organizerTabBtn) organizerTabBtn.classList.add('hidden');
        if (document.getElementById('organizer-view') && document.getElementById('organizer-view').classList.contains('active')) {
            switchTab('discover-view');
        }
    }

    if (currentUser && currentUser.role === 'turf_owner') {
        if (turfOwnerTabBtn) turfOwnerTabBtn.classList.remove('hidden');
    } else {
        if (turfOwnerTabBtn) turfOwnerTabBtn.classList.add('hidden');
        if (document.getElementById('turf-owner-view') && document.getElementById('turf-owner-view').classList.contains('active')) {
            switchTab('discover-view');
        }
    }
}

function persistAuth(token, user) {
    authToken = token;
    currentUser = user;
    localStorage.setItem('token', authToken);
    localStorage.setItem('user', JSON.stringify(currentUser));
    updateAuthUI();
}

function clearAuth() {
    authToken = '';
    currentUser = null;
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    updateAuthUI();
}

function cardTournament(t, index) {
    const distanceText = t.distance === null || t.distance === undefined ? 'Distance unavailable' : `${t.distance} km away`;
    const entryFeeText = t.entry_fee === 0 ? 'FREE' : `\u20B9${t.entry_fee}`;

    const liveLink = t.youtube_link ? `<a href="${t.youtube_link}" target="_blank" onclick="event.stopPropagation();" style="color: var(--danger); font-weight: bold; margin-bottom: 8px; display: inline-block;">📺 Watch Live</a>` : '';

    return `
        <div class="card fade-in" style="animation-delay:${Math.min(index * 0.08, 0.5)}s" onclick="openTournamentDetails(event, ${t.id})">
            <h3>${t.name}</h3>
            ${liveLink}
            <p><strong>${t.sport}</strong> | ${t.mode}</p>
            <p>Location: ${distanceText}</p>
            <p>Date: ${t.date}</p>
            <p>Fee: ${entryFeeText}</p>
            <button onclick="event.stopPropagation(); registerTournament(${t.id})" class="primary-btn">Register</button>
        </div>
    `;
}

function filterTournaments(tournaments) {
    const searchTerm = tournamentSearchInput.value.toLowerCase();
    const sportFilter = sportFilterSelect.value;
    const feeFilter = feeFilterSelect.value;

    return tournaments.filter(tournament => {
        const matchesSearch = tournament.name.toLowerCase().includes(searchTerm) ||
            tournament.sport.toLowerCase().includes(searchTerm);
        const matchesSport = !sportFilter || tournament.sport.toLowerCase() === sportFilter.toLowerCase();

        let matchesFee = true;
        if (feeFilter === 'free') {
            matchesFee = tournament.entry_fee === 0;
        } else if (feeFilter === '0-500') {
            matchesFee = tournament.entry_fee > 0 && tournament.entry_fee <= 500;
        } else if (feeFilter === '500-1000') {
            matchesFee = tournament.entry_fee > 500 && tournament.entry_fee <= 1000;
        } else if (feeFilter === '1000-2000') {
            matchesFee = tournament.entry_fee > 1000 && tournament.entry_fee <= 2000;
        } else if (feeFilter === '2000+') {
            matchesFee = tournament.entry_fee > 2000;
        }

        return matchesSearch && matchesSport && matchesFee;
    });
}

function renderTournaments(list) {
    const container = document.getElementById('tournament-list');
    const filteredList = filterTournaments(list);

    if (filteredList.length === 0) {
        container.innerHTML = '<p class="hint">No tournaments found matching your criteria.</p>';
        return;
    }
    container.innerHTML = filteredList.map((t, index) => cardTournament(t, index)).join('');
}

function clearFilters() {
    tournamentSearchInput.value = '';
    sportFilterSelect.value = '';
    feeFilterSelect.value = '';
    loadTournaments();
}

function initMaps(lat, lng) {
    if (!window.L) {
        return;
    }

    if (!discoverMap) {
        discoverMap = L.map('discover-map').setView([lat, lng], 11);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
        }).addTo(discoverMap);

        discoverMarker = L.marker([lat, lng], { draggable: true }).addTo(discoverMap);
        discoverMarker.on('dragend', () => {
            const pos = discoverMarker.getLatLng();
            currentPosition = { lat: pos.lat, lng: pos.lng };
            updateDiscoverInputs(pos.lat, pos.lng);
            loadTournaments();
        });

        if (window.L.Control && window.L.Control.Geocoder) {
            discoverGeocoder = L.Control.geocoder({
                defaultMarkGeocode: false,
                placeholder: 'Search city or address...',
            })
                .on('markgeocode', (e) => {
                    const center = e.geocode.center;
                    discoverMap.setView(center, 12);
                    discoverMarker.setLatLng(center);
                    currentPosition = { lat: center.lat, lng: center.lng };
                    updateDiscoverInputs(center.lat, center.lng, e.geocode.name || '');
                    loadTournaments();
                })
                .addTo(discoverMap);
        }
    } else {
        discoverMap.setView([lat, lng], 11);
        discoverMarker.setLatLng([lat, lng]);
    }

    if (!organizerMap && document.getElementById('organizer-map')) {
        organizerMap = L.map('organizer-map').setView([lat, lng], 11);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
        }).addTo(organizerMap);

        organizerMarker = L.marker([lat, lng], { draggable: true }).addTo(organizerMap);
        organizerMarker.on('dragend', () => {
            const pos = organizerMarker.getLatLng();
            updateOrganizerInputs(pos.lat, pos.lng);
        });

        organizerMap.on('click', (e) => {
            organizerMarker.setLatLng(e.latlng);
            updateOrganizerInputs(e.latlng.lat, e.latlng.lng);
        });

        if (window.L.Control && window.L.Control.Geocoder) {
            organizerGeocoder = L.Control.geocoder({
                defaultMarkGeocode: false,
                placeholder: 'Search venue location...',
            })
                .on('markgeocode', (e) => {
                    const center = e.geocode.center;
                    organizerMap.setView(center, 13);
                    organizerMarker.setLatLng(center);
                    updateOrganizerInputs(center.lat, center.lng, e.geocode.name || '');
                })
                .addTo(organizerMap);
        }
    }

    if (!turfMap && document.getElementById('turf-map')) {
        turfMap = L.map('turf-map').setView([lat, lng], 11);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
        }).addTo(turfMap);
        turfMarkersLayer = L.layerGroup().addTo(turfMap);
    }

    initTurfOwnerFormMap();
}

function parseLatControl(val) {
    if (!val) return null;
    let s = String(val).trim().toUpperCase().replace(/E/g, '');
    if (s.includes(',')) {
        s = s.split(',')[0].trim();
    }
    const n = parseFloat(s);
    return isNaN(n) ? null : n;
}

function parseLngControl(val) {
    if (!val) return null;
    let s = String(val).trim().toUpperCase().replace(/E/g, '');
    if (s.includes(',')) {
        s = s.split(',')[1] ? s.split(',')[1].trim() : s.split(',')[0].trim();
    }
    const n = parseFloat(s);
    return isNaN(n) ? null : n;
}

function handleCoordsPaste(rawStr) {
    if (!rawStr) return;
    const parts = rawStr.split(',');
    if (parts.length >= 2) {
        const lat = parseLatControl(parts[0]);
        const lng = parseLngControl(parts[1]);
        if (lat !== null && lng !== null) {
            document.getElementById('turf-owner-lat').value = lat.toFixed(6);
            document.getElementById('turf-owner-lng').value = lng.toFixed(6);
            if (turfOwnerFormMap && turfOwnerFormMarker) {
                turfOwnerFormMap.setView([lat, lng], 13);
                turfOwnerFormMarker.setLatLng([lat, lng]);
            }
        }
    } else {
        const lat = parseLatControl(rawStr);
        if (lat !== null) {
            document.getElementById('turf-owner-lat').value = lat.toFixed(6);
        }
    }
}

function initTurfOwnerFormMap() {
    const mapEl = document.getElementById('turf-owner-form-map');
    if (!mapEl || !window.L || turfOwnerFormMap) return;

    const initialLat = currentPosition ? currentPosition.lat : DEFAULT_CENTER.lat;
    const initialLng = currentPosition ? currentPosition.lng : DEFAULT_CENTER.lng;

    turfOwnerFormMap = L.map('turf-owner-form-map').setView([initialLat, initialLng], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
    }).addTo(turfOwnerFormMap);

    turfOwnerFormMarker = L.marker([initialLat, initialLng], { draggable: true }).addTo(turfOwnerFormMap);

    function updateInputsFromMarker(lat, lng, label = '') {
        document.getElementById('turf-owner-lat').value = lat.toFixed(6);
        document.getElementById('turf-owner-lng').value = lng.toFixed(6);
        document.getElementById('turf-owner-coords-paste').value = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
        if (document.getElementById('turf-owner-coords-hint')) {
            document.getElementById('turf-owner-coords-hint').textContent = `Pinpoint set: ${lat.toFixed(5)}, ${lng.toFixed(5)}`;
        }
        if (label && document.getElementById('turf-owner-address') && !document.getElementById('turf-owner-address').value) {
            document.getElementById('turf-owner-address').value = label;
        }
    }

    updateInputsFromMarker(initialLat, initialLng);

    turfOwnerFormMarker.on('dragend', () => {
        const pos = turfOwnerFormMarker.getLatLng();
        updateInputsFromMarker(pos.lat, pos.lng);
    });

    turfOwnerFormMap.on('click', (e) => {
        turfOwnerFormMarker.setLatLng(e.latlng);
        updateInputsFromMarker(e.latlng.lat, e.latlng.lng);
    });

    if (window.L.Control && window.L.Control.Geocoder) {
        L.Control.geocoder({
            defaultMarkGeocode: false,
            placeholder: 'Search location (e.g. Pune Railway Station)...',
        })
            .on('markgeocode', (e) => {
                const center = e.geocode.center;
                turfOwnerFormMap.setView(center, 14);
                turfOwnerFormMarker.setLatLng(center);
                updateInputsFromMarker(center.lat, center.lng, e.geocode.name || '');
            })
            .addTo(turfOwnerFormMap);
    }
}

function updateDiscoverInputs(lat, lng, label = '') {
    if (discoverLatInput) discoverLatInput.value = lat.toFixed(6);
    if (discoverLngInput) discoverLngInput.value = lng.toFixed(6);
    if (label && discoverLocationInput) discoverLocationInput.value = label;
}

function updateOrganizerInputs(lat, lng, label = '') {
    const latEl = document.getElementById('t-lat');
    const lngEl = document.getElementById('t-lng');

    if (latEl) latEl.value = lat.toFixed(6);
    if (lngEl) lngEl.value = lng.toFixed(6);
    if (organizerCoordsEl) {
        organizerCoordsEl.textContent = `Selected: ${lat.toFixed(5)}, ${lng.toFixed(5)}`;
    }
    if (label && organizerLocationInput) {
        organizerLocationInput.value = label;
    }
}

function toggleOrganizerMapFullscreen() {
    if (!organizerMapElement || !organizerMap) {
        return;
    }

    const isFullscreen = organizerMapElement.classList.toggle('organizer-map-fullscreen');
    document.body.classList.toggle('organizer-map-fullscreen-lock', isFullscreen);

    if (organizerMapFullscreenBtn) {
        organizerMapFullscreenBtn.textContent = isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Map';
    }

    setTimeout(() => {
        organizerMap.invalidateSize();
    }, 150);
}

function applyManualDiscoverCoords() {
    const latVal = parseFloat(discoverLatInput.value);
    const lngVal = parseFloat(discoverLngInput.value);

    if (Number.isNaN(latVal) || Number.isNaN(lngVal)) {
        setMessage('Please enter valid numerical latitude and longitude.', true);
        return;
    }

    currentPosition = { lat: latVal, lng: lngVal };
    initMaps(latVal, lngVal);
    loadTournaments();
    loadTurfs();
    setMessage('Coordinates set successfully.');
}

async function loadTournaments() {
    const radius = document.getElementById('radius').value;
    const sportFilter = sportFilterSelect ? sportFilterSelect.value : '';

    let url = `${API_BASE}/tournaments?radius=${radius}`;
    if (currentPosition) {
        url += `&lat=${currentPosition.lat}&lng=${currentPosition.lng}`;
    }
    if (sportFilter) {
        url += `&sport=${encodeURIComponent(sportFilter)}`;
    }

    try {
        const res = await fetch(url);
        const data = await readApiPayload(res);
        if (!res.ok) {
            setMessage(getApiError(data, 'Failed to fetch tournaments'), true);
            return;
        }
        renderTournaments(data);
    } catch (err) {
        setMessage(err.message, true);
    }
}

function requestLocationAndLoad() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                currentPosition = { lat: pos.coords.latitude, lng: pos.coords.longitude };
                updateDiscoverInputs(currentPosition.lat, currentPosition.lng, 'Current Location');
                updateOrganizerInputs(currentPosition.lat, currentPosition.lng);
                initMaps(currentPosition.lat, currentPosition.lng);
                loadTournaments();
                loadTurfs();
            },
            () => {
                currentPosition = DEFAULT_CENTER;
                updateDiscoverInputs(DEFAULT_CENTER.lat, DEFAULT_CENTER.lng, 'Mumbai (Default)');
                updateOrganizerInputs(DEFAULT_CENTER.lat, DEFAULT_CENTER.lng);
                initMaps(DEFAULT_CENTER.lat, DEFAULT_CENTER.lng);
                loadTournaments();
                loadTurfs();
            }
        );
    } else {
        currentPosition = DEFAULT_CENTER;
        updateDiscoverInputs(DEFAULT_CENTER.lat, DEFAULT_CENTER.lng, 'Mumbai (Default)');
        updateOrganizerInputs(DEFAULT_CENTER.lat, DEFAULT_CENTER.lng);
        initMaps(DEFAULT_CENTER.lat, DEFAULT_CENTER.lng);
        loadTournaments();
        loadTurfs();
    }
}

async function registerUser(e) {
    e.preventDefault();
    const name = document.getElementById('reg-name').value;
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-password').value;
    const role = document.getElementById('reg-role').value;

    const payload = {
        name,
        email,
        password,
        role,
        latitude: currentPosition ? currentPosition.lat : null,
        longitude: currentPosition ? currentPosition.lng : null,
    };

    try {
        const res = await fetch(`${API_BASE}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await readApiPayload(res);
        if (!res.ok) {
            setMessage(getApiError(data, 'Registration failed'), true);
            return;
        }

        setMessage('Registered successfully. Please login.');
        document.getElementById('register-form').reset();
    } catch (err) {
        setMessage(err.message, true);
    }
}

async function loginUser(e) {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    try {
        const res = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });

        const data = await readApiPayload(res);
        if (!res.ok) {
            setMessage(getApiError(data, 'Login failed'), true);
            return;
        }

        persistAuth(data.access_token, data.user);
        setMessage(`Welcome back, ${data.user.name}!`);
        document.getElementById('login-form').reset();
        switchTab('discover-view');
        loadMyTeams();
        loadMyTurfBookings();
        if (data.user.role === 'turf_owner') {
            loadTurfOwnerDashboard();
        }
    } catch (err) {
        setMessage(err.message, true);
    }
}

async function createTournament(e) {
    e.preventDefault();
    if (!currentUser || currentUser.role !== 'organizer') {
        setMessage('Only logged in organizers can create tournaments.', true);
        return;
    }

    const latVal = parseFloat(document.getElementById('t-lat').value);
    const lngVal = parseFloat(document.getElementById('t-lng').value);

    const payload = {
        name: document.getElementById('t-name').value,
        venue_name: document.getElementById('t-venue-name').value,
        sport: document.getElementById('t-sport').value,
        date: document.getElementById('t-date').value,
        entry_fee: parseFloat(document.getElementById('t-fee').value),
        mode: document.getElementById('t-mode').value,
        venue_address: document.getElementById('t-location').value,
        organizer_phone: document.getElementById('t-contact').value,
        youtube_link: document.getElementById('t-youtube').value,
        latitude: !Number.isNaN(latVal) ? latVal : (currentPosition ? currentPosition.lat : DEFAULT_CENTER.lat),
        longitude: !Number.isNaN(lngVal) ? lngVal : (currentPosition ? currentPosition.lng : DEFAULT_CENTER.lng),
    };

    try {
        const res = await fetch(`${API_BASE}/tournaments`, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify(payload),
        });

        const data = await readApiPayload(res);
        if (!res.ok) {
            if (handleAuthFailure(res.status, data)) {
                return;
            }
            setMessage(getApiError(data, 'Failed to create tournament'), true);
            return;
        }

        setMessage('Tournament created successfully!');
        document.getElementById('create-tournament-form').reset();
        if (organizerCoordsEl) {
            organizerCoordsEl.textContent = 'No location selected';
        }
        loadTournaments();
        loadOrganizerRegistrations();
        switchTab('discover-view');
    } catch (err) {
        setMessage(err.message, true);
    }
}

async function registerTournament(tournamentId) {
    if (!currentUser) {
        setMessage('Please login to register for a tournament.', true);
        switchTab('auth-view');
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/tournaments/${tournamentId}/register`, {
            method: 'POST',
            headers: authHeaders(),
        });

        const data = await readApiPayload(res);
        if (!res.ok) {
            if (handleAuthFailure(res.status, data)) {
                return;
            }
            setMessage(getApiError(data, 'Registration failed'), true);
            return;
        }

        setMessage('Registered for tournament!');
        loadRegistrations();
    } catch (err) {
        setMessage(err.message, true);
    }
}

async function loadRegistrations() {
    if (!currentUser) {
        document.getElementById('registration-list').innerHTML = '<p class="hint">Please login to view your registrations.</p>';
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/my-registrations`, {
            headers: authHeaders(),
        });

        const data = await readApiPayload(res);
        if (!res.ok) {
            if (handleAuthFailure(res.status, data)) {
                return;
            }
            setMessage(getApiError(data, 'Failed to load registrations'), true);
            return;
        }

        const container = document.getElementById('registration-list');
        if (data.length === 0) {
            container.innerHTML = '<p class="hint">You have not registered for any tournaments yet.</p>';
            return;
        }

        container.innerHTML = data
            .map((reg, index) => `
                <div class="card fade-in" style="animation-delay:${Math.min(index * 0.08, 0.5)}s">
                    <h3>${reg.name}</h3>
                    <p>Sport: ${reg.sport} | ${reg.mode}</p>
                    <p>Date: ${reg.date}</p>
                    <p>Fee: ${reg.entry_fee === 0 ? 'FREE' : '\u20B9' + reg.entry_fee}</p>
                </div>
            `)
            .join('');
    } catch (err) {
        setMessage(err.message, true);
    }
}

async function loadOrganizerRegistrations() {
    if (!currentUser || currentUser.role !== 'organizer' || !organizerRegistrationListEl) {
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/organizer/registrations`, {
            headers: authHeaders(),
        });

        const data = await readApiPayload(res);
        if (!res.ok) {
            if (handleAuthFailure(res.status, data)) {
                return;
            }
            setMessage(getApiError(data, 'Failed to load registrations'), true);
            return;
        }

        if (!Array.isArray(data) || data.length === 0) {
            organizerRegistrationListEl.innerHTML = '<p class="hint">No registrations submitted for your tournaments yet.</p>';
            return;
        }

        organizerRegistrationListEl.innerHTML = data
            .map((item, index) => {
                const rows = Array.isArray(item.registrations) ? item.registrations : [];
                const members = rows.length > 0
                    ? rows.map((reg) => `<li><span>${reg.user_name}</span> <small>${reg.user_email}</small></li>`).join('')
                    : '<li><span>No registrations yet.</span></li>';

                return `
                    <div class="card fade-in" style="animation-delay:${Math.min(index * 0.08, 0.5)}s">
                        <h3>${item.name}</h3>
                        <p>${item.sport} | ${item.mode}</p>
                        <p>Date: ${item.date}</p>
                        <p><strong>${rows.length}</strong> registered</p>
                        <ul class="organizer-registration-users">${members}</ul>
                    </div>
                `;
            })
            .join('');
    } catch (err) {
        setMessage(err.message, true);
    }
}

// --- EXCLUSIVE FEATURE: TURF FINDER & LIVE SLOT BOOKING LOGIC ---
let activeTurfForBooking = null;
let selectedSlotTime = null;
let selectedBookingDate = new Date().toISOString().split('T')[0];

async function loadTurfs() {
    const listEl = document.getElementById('turf-list');
    if (!listEl) return;

    const sport = document.getElementById('turf-sport-filter') ? document.getElementById('turf-sport-filter').value : '';
    const facility = document.getElementById('turf-facility-filter') ? document.getElementById('turf-facility-filter').value : '';
    const maxPrice = document.getElementById('turf-max-price') ? document.getElementById('turf-max-price').value : '';
    const search = document.getElementById('turf-search-input') ? document.getElementById('turf-search-input').value.toLowerCase() : '';

    let url = `${API_BASE}/turfs?`;
    if (currentPosition) url += `lat=${currentPosition.lat}&lng=${currentPosition.lng}&`;
    if (sport) url += `sport=${encodeURIComponent(sport)}&`;
    if (facility) url += `facility=${encodeURIComponent(facility)}&`;
    if (maxPrice) url += `max_price=${encodeURIComponent(maxPrice)}&`;

    try {
        const res = await fetch(url);
        const data = await readApiPayload(res);
        if (!res.ok) {
            setMessage(getApiError(data, 'Failed to fetch turfs'), true);
            return;
        }

        let turfs = Array.isArray(data) ? data : [];
        if (search) {
            turfs = turfs.filter(t => t.name.toLowerCase().includes(search) || t.address.toLowerCase().includes(search) || t.sport.toLowerCase().includes(search));
        }

        if (turfMarkersLayer && window.L) {
            turfMarkersLayer.clearLayers();
            turfs.forEach(t => {
                const marker = L.marker([t.latitude, t.longitude]).addTo(turfMarkersLayer);
                marker.bindPopup(`
                    <div style="color:#000;">
                        <strong>${t.name}</strong><br/>
                        ${t.sport} | \u20B9${t.price_per_hour}/hr<br/>
                        <button onclick="openTurfBookingModal(${t.id})" style="padding:4px 8px; font-size:0.75rem; margin-top:4px;">Book Slot</button>
                    </div>
                `);
            });
        }

        if (turfs.length === 0) {
            listEl.innerHTML = '<p class="hint">No turfs found matching your search parameters.</p>';
            return;
        }

        listEl.innerHTML = turfs.map((t, index) => {
            const facilitiesTags = t.facilities ? t.facilities.map(f => `<span class="facility-tag">${f}</span>`).join('') : '';
            return `
                <div class="card fade-in" style="animation-delay:${Math.min(index * 0.08, 0.5)}s">
                    <img src="${t.image_url}" alt="${t.name}" style="width:100%; height:140px; object-fit:cover; border-radius:8px; margin-bottom:8px;">
                    <h3>${t.name}</h3>
                    <p><strong>Sport:</strong> ${t.sport} | ⭐ ${t.rating}</p>
                    <p><strong>Location:</strong> ${t.address}</p>
                    <p><strong>Price:</strong> \u20B9${t.price_per_hour} / hour</p>
                    <div style="margin:6px 0;">${facilitiesTags}</div>
                    <button onclick="openTurfBookingModal(${t.id})" class="primary-btn">View Availability & Book</button>
                </div>
            `;
        }).join('');

    } catch (err) {
        setMessage(err.message, true);
    }
}

async function openTurfBookingModal(turfId) {
    try {
        const res = await fetch(`${API_BASE}/turfs/${turfId}`);
        const turf = await readApiPayload(res);
        if (!res.ok) {
            setMessage(getApiError(turf, 'Failed to fetch turf details'), true);
            return;
        }

        activeTurfForBooking = turf;
        selectedSlotTime = null;

        const modal = document.getElementById('turf-booking-modal');
        const container = document.getElementById('turf-modal-details');

        const mapsUrl = `https://www.google.com/maps?q=${encodeURIComponent(`${turf.latitude},${turf.longitude}`)}`;
        const facilitiesTags = turf.facilities ? turf.facilities.map(f => `<span class="facility-tag">${f}</span>`).join('') : '';

        container.innerHTML = `
            <img src="${turf.image_url}" style="width:100%; height:200px; object-fit:cover; border-radius:12px; margin-bottom:12px;">
            <h2>${turf.name}</h2>
            <p><strong>Sport:</strong> ${turf.sport} | ⭐ ${turf.rating}</p>
            <p><strong>Address:</strong> ${turf.address} <a href="${mapsUrl}" target="_blank" style="color:var(--accent-3); margin-left:6px;">[Get Directions]</a></p>
            <p><strong>Price:</strong> \u20B9${turf.price_per_hour} per slot (1 hour)</p>
            <p><strong>Owner Contact:</strong> ${turf.owner_name} (${turf.owner_email})</p>
            <div style="margin:10px 0;"><strong>Facilities:</strong> ${facilitiesTags}</div>
            <p style="font-size:0.85rem; color:var(--muted);"><strong>Rules & Guidelines:</strong> ${turf.rules}</p>
            
            <hr style="border-color:var(--panel-border); margin:16px 0;">
            
            <h4>Select Date & Live Hourly Slot</h4>
            <div style="display:flex; gap:10px; align-items:center; margin-bottom:12px;">
                <label for="slot-date-picker">Date:</label>
                <input type="date" id="slot-date-picker" value="${selectedBookingDate}" onchange="changeBookingDate(this.value, ${turf.id})">
            </div>

            <div id="slots-container">Loading available slots...</div>

            <div id="booking-summary" class="panel-box hidden" style="margin-top:16px;">
                <p>Selected Slot: <strong id="summary-slot-time">None</strong></p>
                <p>Total Price: <strong id="summary-price" style="color:var(--accent-2)">\u20B90</strong></p>
                <button onclick="confirmBookTurfSlot(${turf.id})" class="primary-btn">Confirm & Book Slot</button>
            </div>
        `;

        modal.classList.remove('hidden');
        loadSlotsForDate(turfId, selectedBookingDate);

    } catch (err) {
        setMessage(err.message, true);
    }
}

function closeTurfBookingModal() {
    const modal = document.getElementById('turf-booking-modal');
    if (modal) modal.classList.add('hidden');
}

async function changeBookingDate(newDate, turfId) {
    selectedBookingDate = newDate;
    selectedSlotTime = null;
    document.getElementById('booking-summary').classList.add('hidden');
    loadSlotsForDate(turfId, newDate);
}

async function loadSlotsForDate(turfId, dateStr) {
    const container = document.getElementById('slots-container');
    if (!container) return;

    try {
        const res = await fetch(`${API_BASE}/turfs/${turfId}/slots?date=${dateStr}`);
        const data = await readApiPayload(res);
        if (!res.ok || !data.slots) {
            container.innerHTML = '<p class="hint">Failed to load slots.</p>';
            return;
        }

        container.innerHTML = `
            <div class="slots-grid">
                ${data.slots.map(s => {
            const statusClass = s.status === 'available' ? 'available' : 'booked';
            const disabled = s.status !== 'available' ? 'disabled' : '';
            return `
                        <button class="slot-btn ${statusClass}" ${disabled} onclick="selectTurfSlot('${s.time_slot}', ${s.price}, this)">
                            ${s.time_slot}<br/>
                            <small>${s.status.toUpperCase()}</small>
                        </button>
                    `;
        }).join('')}
            </div>
        `;

    } catch (err) {
        container.innerHTML = `<p class="hint">${err.message}</p>`;
    }
}

function selectTurfSlot(timeSlot, price, btnEl) {
    document.querySelectorAll('.slot-btn').forEach(b => b.classList.remove('selected'));
    btnEl.classList.add('selected');

    selectedSlotTime = timeSlot;
    document.getElementById('summary-slot-time').textContent = timeSlot;
    document.getElementById('summary-price').textContent = `\u20B9${price}`;
    document.getElementById('booking-summary').classList.remove('hidden');
}

async function confirmBookTurfSlot(turfId) {
    if (!currentUser) {
        setMessage('Please log in to book a turf slot.', true);
        closeTurfBookingModal();
        switchTab('auth-view');
        return;
    }

    if (!selectedSlotTime) {
        setMessage('Please select an available time slot.', true);
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/turfs/${turfId}/book`, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({
                booking_date: selectedBookingDate,
                time_slot: selectedSlotTime
            })
        });

        const data = await readApiPayload(res);
        if (!res.ok) {
            if (handleAuthFailure(res.status, data)) return;
            setMessage(getApiError(data, 'Booking failed'), true);
            loadSlotsForDate(turfId, selectedBookingDate);
            return;
        }

        setMessage('Slot booked successfully! Enjoy your match.');
        closeTurfBookingModal();
        loadMyTurfBookings();
    } catch (err) {
        setMessage(err.message, true);
    }
}

async function loadMyTurfBookings() {
    const listEl = document.getElementById('my-turf-bookings-list');
    if (!listEl) return;

    if (!currentUser) {
        listEl.innerHTML = '<p class="hint">Log in to view your turf booking history.</p>';
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/my-turf-bookings`, {
            headers: authHeaders()
        });
        const data = await readApiPayload(res);
        if (!res.ok) {
            if (handleAuthFailure(res.status, data)) return;
            listEl.innerHTML = '<p class="hint">Failed to load bookings.</p>';
            return;
        }

        let bookings = Array.isArray(data) ? data : [];
        if (bookings.length === 0) {
            listEl.innerHTML = '<p class="hint">No turf slot bookings found.</p>';
            return;
        }

        listEl.innerHTML = bookings.map((b, index) => `
            <div class="card fade-in" style="animation-delay:${Math.min(index * 0.08, 0.5)}s">
                <h3>${b.turf_name}</h3>
                <p><strong>Sport:</strong> ${b.sport}</p>
                <p><strong>Address:</strong> ${b.address}</p>
                <p><strong>Date:</strong> ${b.booking_date} | <strong>Slot:</strong> ${b.time_slot}</p>
                <p><strong>Price:</strong> \u20B9${b.total_price} | <span class="status-badge ${b.status.toLowerCase()}">${b.status}</span></p>
                ${b.status === 'confirmed' ? `<button onclick="cancelTurfBooking(${b.id})" class="ghost" style="color:var(--danger)">Cancel Booking</button>` : ''}
            </div>
        `).join('');

    } catch (err) {
        listEl.innerHTML = `<p class="hint">${err.message}</p>`;
    }
}

async function cancelTurfBooking(bookingId) {
    try {
        const res = await fetch(`${API_BASE}/turf-bookings/${bookingId}/cancel`, {
            method: 'POST',
            headers: authHeaders()
        });
        const data = await readApiPayload(res);
        if (!res.ok) {
            setMessage(getApiError(data, 'Failed to cancel booking'), true);
            return;
        }
        setMessage('Booking cancelled successfully.');
        loadMyTurfBookings();
        if (currentUser && currentUser.role === 'turf_owner') {
            loadTurfOwnerDashboard();
        }
    } catch (err) {
        setMessage(err.message, true);
    }
}

// --- EXCLUSIVE FEATURE: TURF OWNER DASHBOARD LOGIC ---

async function loadTurfOwnerDashboard() {
    if (!currentUser || currentUser.role !== 'turf_owner') return;

    try {
        initTurfOwnerFormMap();

        // 1. Fetch Owner Bookings & Stats
        const resB = await fetch(`${API_BASE}/owner/bookings`, { headers: authHeaders() });
        const dataB = await readApiPayload(resB);
        if (resB.ok && dataB.stats) {
            document.getElementById('owner-total-revenue').textContent = `\u20B9${dataB.stats.total_revenue}`;
            document.getElementById('owner-confirmed-bookings').textContent = dataB.stats.total_bookings;
            document.getElementById('owner-managed-turfs').textContent = dataB.stats.total_turfs;
        }

        const bookingsList = document.getElementById('owner-bookings-list');
        if (bookingsList && dataB.bookings) {
            if (dataB.bookings.length === 0) {
                bookingsList.innerHTML = '<p class="hint">No customer bookings recorded yet.</p>';
            } else {
                bookingsList.innerHTML = dataB.bookings.map((b, index) => `
                    <div class="card fade-in" style="animation-delay:${Math.min(index * 0.08, 0.5)}s">
                        <h3>${b.turf_name}</h3>
                        <p><strong>Customer:</strong> ${b.customer_name} (${b.customer_email})</p>
                        <p><strong>Date:</strong> ${b.booking_date} | <strong>Slot:</strong> ${b.time_slot}</p>
                        <p><strong>Revenue:</strong> \u20B9${b.total_price} | <span class="status-badge ${b.status.toLowerCase()}">${b.status}</span></p>
                        ${b.status === 'confirmed' ? `<button onclick="cancelTurfBooking(${b.id})" class="ghost" style="color:var(--danger)">Cancel Customer Booking</button>` : ''}
                    </div>
                `).join('');
            }
        }

        // 2. Fetch Owner Turfs for Block Select dropdown
        const resT = await fetch(`${API_BASE}/owner/turfs`, { headers: authHeaders() });
        const turfs = await readApiPayload(resT);
        const blockSelect = document.getElementById('block-turf-select');
        if (blockSelect && Array.isArray(turfs)) {
            blockSelect.innerHTML = turfs.map(t => `<option value="${t.id}">${t.name} (${t.sport})</option>`).join('');
        }

    } catch (err) {
        setMessage(err.message, true);
    }
}

async function registerTurf(e) {
    e.preventDefault();
    if (!currentUser) {
        setMessage('Please log in as a Turf Owner.', true);
        switchTab('auth-view');
        return;
    }

    const pasteInput = document.getElementById('turf-owner-coords-paste');
    if (pasteInput && pasteInput.value) {
        handleCoordsPaste(pasteInput.value);
    }

    const latVal = parseLatControl(document.getElementById('turf-owner-lat').value) || (currentPosition ? currentPosition.lat : DEFAULT_CENTER.lat);
    const lngVal = parseLngControl(document.getElementById('turf-owner-lng').value) || (currentPosition ? currentPosition.lng : DEFAULT_CENTER.lng);

    const payload = {
        name: document.getElementById('turf-owner-name').value.trim(),
        sport: document.getElementById('turf-owner-sport').value.trim(),
        address: document.getElementById('turf-owner-address').value.trim(),
        price_per_hour: parseFloat(document.getElementById('turf-owner-price').value),
        facilities: document.getElementById('turf-owner-facilities').value.trim() || 'Floodlights, Parking, Changing Room',
        opening_time: document.getElementById('turf-owner-open').value.trim() || '06:00',
        closing_time: document.getElementById('turf-owner-close').value.trim() || '23:00',
        latitude: latVal,
        longitude: lngVal
    };

    try {
        const res = await fetch(`${API_BASE}/turfs`, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify(payload)
        });

        const data = await readApiPayload(res);
        if (!res.ok) {
            if (handleAuthFailure(res.status, data)) return;
            setMessage(getApiError(data, 'Failed to register turf'), true);
            return;
        }

        setMessage('Turf venue registered successfully!');
        document.getElementById('register-turf-form').reset();
        loadTurfs();
        loadTurfOwnerDashboard();
    } catch (err) {
        setMessage(err.message, true);
    }
}

async function blockTurfSlot(e) {
    e.preventDefault();
    const turfId = document.getElementById('block-turf-select').value;
    const booking_date = document.getElementById('block-date').value;
    const time_slot = document.getElementById('block-slot-time').value.trim();

    if (!turfId || !booking_date || !time_slot) {
        setMessage('Please fill in all fields to block slot.', true);
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/owner/turfs/${turfId}/block-slot`, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({ booking_date, time_slot })
        });
        const data = await readApiPayload(res);
        if (!res.ok) {
            setMessage(getApiError(data, 'Failed to block slot'), true);
            return;
        }
        setMessage('Slot marked as blocked / unavailable.');
        document.getElementById('block-slot-form').reset();
        loadTurfOwnerDashboard();
    } catch (err) {
        setMessage(err.message, true);
    }
}

window.openTurfBookingModal = openTurfBookingModal;
window.closeTurfBookingModal = closeTurfBookingModal;
window.changeBookingDate = changeBookingDate;
window.selectTurfSlot = selectTurfSlot;
window.confirmBookTurfSlot = confirmBookTurfSlot;
window.cancelTurfBooking = cancelTurfBooking;

// --- TEAM FINDER FRONTEND LOGIC ---
let allTeamsCache = [];

async function loadTeams() {
    const listEl = document.getElementById('team-list');
    if (!listEl) return;

    const sportFilter = document.getElementById('team-sport-select') ? document.getElementById('team-sport-select').value : '';
    const searchFilter = document.getElementById('team-search-input') ? document.getElementById('team-search-input').value.toLowerCase() : '';

    try {
        const url = sportFilter ? `${API_BASE}/teams?sport=${encodeURIComponent(sportFilter)}` : `${API_BASE}/teams`;
        const res = await fetch(url);
        const data = await readApiPayload(res);
        if (!res.ok) {
            setMessage(getApiError(data, 'Failed to load teams'), true);
            return;
        }

        allTeamsCache = Array.isArray(data) ? data : [];
        let filtered = allTeamsCache.filter(t => {
            if (searchFilter && !t.name.toLowerCase().includes(searchFilter) && !t.sport.toLowerCase().includes(searchFilter)) {
                return false;
            }
            return true;
        });

        if (filtered.length === 0) {
            listEl.innerHTML = '<p class="hint">No teams seeking players found. Be the first to post a team!</p>';
            return;
        }

        listEl.innerHTML = filtered.map((team, index) => `
            <div class="card fade-in" style="animation-delay:${Math.min(index * 0.08, 0.5)}s">
                <h3>${team.name}</h3>
                <p><strong>Sport:</strong> ${team.sport}</p>
                <p><strong>Skill Level:</strong> ${team.skill_level}</p>
                <p><strong>Captain:</strong> ${team.creator_name}</p>
                <p><strong>Squad Members:</strong> ${team.members_count}</p>
                <button onclick="requestJoinTeam(${team.id})" class="primary-btn">Request to Join Team</button>
            </div>
        `).join('');

    } catch (err) {
        setMessage(err.message, true);
    }
}

async function createTeam(e) {
    e.preventDefault();
    if (!currentUser) {
        setMessage('Please log in to create a team.', true);
        switchTab('auth-view');
        return;
    }

    const name = document.getElementById('team-name').value.trim();
    const sport = document.getElementById('team-sport').value.trim();
    const skillLevel = document.getElementById('team-skill').value;

    try {
        const res = await fetch(`${API_BASE}/teams`, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({
                name,
                sport,
                skill_level: skillLevel,
                latitude: currentPosition ? currentPosition.lat : null,
                longitude: currentPosition ? currentPosition.lng : null
            })
        });

        const data = await readApiPayload(res);
        if (!res.ok) {
            if (handleAuthFailure(res.status, data)) return;
            setMessage(getApiError(data, 'Failed to create team'), true);
            return;
        }

        setMessage('Team created successfully!');
        document.getElementById('create-team-form').reset();
        loadTeams();
        loadMyTeams();
    } catch (err) {
        setMessage(err.message, true);
    }
}

async function requestJoinTeam(teamId) {
    if (!currentUser) {
        setMessage('Please log in to send join request.', true);
        switchTab('auth-view');
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/teams/${teamId}/join`, {
            method: 'POST',
            headers: authHeaders()
        });

        const data = await readApiPayload(res);
        if (!res.ok) {
            if (handleAuthFailure(res.status, data)) return;
            setMessage(getApiError(data, 'Failed to send request'), true);
            return;
        }

        setMessage(data.message || 'Join request sent to captain!');
        loadMyTeams();
    } catch (err) {
        setMessage(err.message, true);
    }
}

async function loadMyTeams() {
    const container = document.getElementById('my-teams-container');
    if (!container) return;

    if (!currentUser) {
        container.innerHTML = '<p class="hint">Log in to view your team requests.</p>';
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/my-teams`, {
            headers: authHeaders()
        });
        const data = await readApiPayload(res);
        if (!res.ok) {
            if (handleAuthFailure(res.status, data)) return;
            container.innerHTML = '<p class="hint">Failed to load team data.</p>';
            return;
        }

        let html = '';
        const created = data.created_teams || [];
        const requests = data.team_requests || [];

        if (created.length > 0) {
            html += '<h5 style="margin:8px 0;">Teams You Lead</h5>';
            for (const t of created) {
                html += `<div style="margin-bottom:10px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:8px;">
                    <strong>${t.name}</strong> (${t.sport}) - ${t.members_count} member(s)
                    <div id="team-requests-${t.id}"></div>
                </div>`;
                fetchAndRenderCaptainRequests(t.id);
            }
        }

        if (requests.length > 0) {
            html += '<h5 style="margin-top:12px; margin-bottom:8px;">Your Join Requests</h5>';
            html += requests.map(r => `
                <div style="margin-bottom:6px; font-size:0.85rem;">
                    <strong>${r.team_name}</strong> (${r.sport}): 
                    <span class="status-badge ${r.status.toLowerCase()}">${r.status}</span>
                </div>
            `).join('');
        }

        if (created.length === 0 && requests.length === 0) {
            html = '<p class="hint">You have not created or joined any teams yet.</p>';
        }

        container.innerHTML = html;

    } catch (err) {
        container.innerHTML = `<p class="hint">${err.message}</p>`;
    }
}

async function fetchAndRenderCaptainRequests(teamId) {
    try {
        const res = await fetch(`${API_BASE}/teams/${teamId}/requests`, {
            headers: authHeaders()
        });
        const data = await readApiPayload(res);
        const container = document.getElementById(`team-requests-${teamId}`);
        if (!container || !res.ok || !Array.isArray(data)) return;

        if (data.length === 0) {
            container.innerHTML = '<small style="color:var(--muted)">No pending requests.</small>';
            return;
        }

        container.innerHTML = '<ul style="margin:4px 0; padding-left:16px; font-size:0.85rem;">' + data.map(r => `
            <li style="margin:4px 0;">
                ${r.user_name} - <span class="status-badge ${r.status.toLowerCase()}">${r.status}</span>
                ${r.status === 'pending' ? `
                    <button onclick="respondTeamRequest(${r.id}, 'approved')" style="padding:2px 6px; font-size:0.75rem; margin-left:4px;">Approve</button>
                    <button onclick="respondTeamRequest(${r.id}, 'rejected')" class="ghost" style="padding:2px 6px; font-size:0.75rem; margin-left:4px;">Reject</button>
                ` : ''}
            </li>
        `).join('') + '</ul>';
    } catch (_) { }
}

async function respondTeamRequest(requestId, status) {
    try {
        const res = await fetch(`${API_BASE}/teams/requests/${requestId}/respond`, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({ status })
        });
        const data = await readApiPayload(res);
        if (!res.ok) {
            setMessage(getApiError(data, 'Failed to update request'), true);
            return;
        }
        setMessage(`Player request ${status}!`);
        loadMyTeams();
    } catch (err) {
        setMessage(err.message, true);
    }
}

window.requestJoinTeam = requestJoinTeam;
window.respondTeamRequest = respondTeamRequest;
window.registerTournament = registerTournament;

window.openTournamentDetails = function openTournamentDetails(event, tournamentId) {
    if (event && event.target && event.target.closest('button')) {
        return;
    }
    window.location.href = `tournament.html?id=${encodeURIComponent(tournamentId)}`;
};

function attachEvents() {
    document.getElementById('register-form').addEventListener('submit', registerUser);
    document.getElementById('login-form').addEventListener('submit', loginUser);
    document.getElementById('create-tournament-form').addEventListener('submit', createTournament);
    document.getElementById('locate-btn').addEventListener('click', requestLocationAndLoad);
    document.getElementById('radius').addEventListener('change', loadTournaments);
    document.getElementById('load-registrations-btn').addEventListener('click', () => { loadRegistrations(); loadMyTurfBookings(); });
    applyDiscoverCoordsBtn.addEventListener('click', applyManualDiscoverCoords);
    if (organizerMapFullscreenBtn) {
        organizerMapFullscreenBtn.addEventListener('click', toggleOrganizerMapFullscreen);
    }
    if (loadOrganizerRegistrationsBtn) {
        loadOrganizerRegistrationsBtn.addEventListener('click', loadOrganizerRegistrations);
    }

    // Turf Events
    if (document.getElementById('refresh-turfs-btn')) {
        document.getElementById('refresh-turfs-btn').addEventListener('click', loadTurfs);
    }
    if (document.getElementById('turf-search-input')) {
        document.getElementById('turf-search-input').addEventListener('input', loadTurfs);
    }
    if (document.getElementById('turf-sport-filter')) {
        document.getElementById('turf-sport-filter').addEventListener('change', loadTurfs);
    }
    if (document.getElementById('turf-facility-filter')) {
        document.getElementById('turf-facility-filter').addEventListener('change', loadTurfs);
    }
    if (document.getElementById('turf-max-price')) {
        document.getElementById('turf-max-price').addEventListener('input', loadTurfs);
    }

    // Coordinate Paste Listeners
    const pasteEl = document.getElementById('turf-owner-coords-paste');
    if (pasteEl) {
        pasteEl.addEventListener('input', (e) => handleCoordsPaste(e.target.value));
        pasteEl.addEventListener('paste', (e) => {
            setTimeout(() => handleCoordsPaste(e.target.value), 50);
        });
    }

    const latEl = document.getElementById('turf-owner-lat');
    if (latEl) {
        latEl.addEventListener('input', (e) => {
            if (e.target.value.includes(',')) handleCoordsPaste(e.target.value);
        });
    }

    // Turf Owner Dashboard Events
    if (document.getElementById('register-turf-form')) {
        document.getElementById('register-turf-form').addEventListener('submit', registerTurf);
    }
    if (document.getElementById('block-slot-form')) {
        document.getElementById('block-slot-form').addEventListener('submit', blockTurfSlot);
    }
    if (document.getElementById('refresh-owner-dashboard-btn')) {
        document.getElementById('refresh-owner-dashboard-btn').addEventListener('click', loadTurfOwnerDashboard);
    }

    // Team Finder Events
    if (document.getElementById('create-team-form')) {
        document.getElementById('create-team-form').addEventListener('submit', createTeam);
    }
    if (document.getElementById('refresh-teams-btn')) {
        document.getElementById('refresh-teams-btn').addEventListener('click', () => { loadTeams(); loadMyTeams(); });
    }
    if (document.getElementById('team-search-input')) {
        document.getElementById('team-search-input').addEventListener('input', loadTeams);
    }
    if (document.getElementById('team-sport-select')) {
        document.getElementById('team-sport-select').addEventListener('change', loadTeams);
    }

    // New filter event listeners
    tournamentSearchInput.addEventListener('input', loadTournaments);
    sportFilterSelect.addEventListener('change', loadTournaments);
    feeFilterSelect.addEventListener('change', loadTournaments);
    clearFiltersBtn.addEventListener('click', clearFilters);

    document.querySelectorAll('.tab-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            switchTab(btn.dataset.tab);
            if (btn.dataset.tab === 'registrations-view') {
                loadRegistrations();
                loadMyTurfBookings();
            }
            if (btn.dataset.tab === 'organizer-view') {
                loadOrganizerRegistrations();
            }
            if (btn.dataset.tab === 'teams-view') {
                loadTeams();
                loadMyTeams();
            }
            if (btn.dataset.tab === 'turfs-view') {
                loadTurfs();
            }
            if (btn.dataset.tab === 'turf-owner-view') {
                loadTurfOwnerDashboard();
            }
        });
    });

    logoutBtn.addEventListener('click', () => {
        clearAuth();
        setMessage('Logged out.');
    });
}

(function init() {
    if (!document.getElementById('discover-view')) {
        return;
    }
    attachEvents();
    updateAuthUI();
    requestLocationAndLoad();
    loadTurfs();
    loadTeams();
})();

window.SportsPlatformVenue = {
    createGoogleMapsUrl(latitude, longitude) {
        return `https://www.google.com/maps?q=${encodeURIComponent(`${latitude},${longitude}`)}`;
    },
};

function enableTournamentCardNavigation(list) {
    const container = document.getElementById('tournament-list');
    if (!container || !Array.isArray(list)) {
        return;
    }

    const cards = container.querySelectorAll('.card');
    cards.forEach((card, index) => {
        const tournament = list[index];
        if (!tournament) {
            return;
        }

        if (card.dataset.detailBound === '1') {
            return;
        }

        card.dataset.detailBound = '1';
        card.dataset.tournamentId = String(tournament.id);
        card.style.cursor = 'pointer';
        card.title = 'View tournament details';

        card.addEventListener('click', (event) => {
            if (event.target.closest('button')) {
                return;
            }
            window.location.href = `tournament.html?id=${encodeURIComponent(tournament.id)}`;
        });
    });
}

const _existingRenderTournaments = renderTournaments;
renderTournaments = function wrappedRenderTournaments(list) {
    _existingRenderTournaments(list);
    enableTournamentCardNavigation(list);
};
