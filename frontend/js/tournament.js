// NEW FEATURE - DO NOT MODIFY EXISTING CODE
const TOURNAMENT_API_BASE = 'http://127.0.0.1:5000';

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
const tournamentParams = new URLSearchParams(window.location.search);
const tournamentId = tournamentParams.get('id');

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
function getTournamentPageToken() {
    return localStorage.getItem('token') || '';
}

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
const titleEl = document.getElementById('tournament-title');
const subtitleEl = document.getElementById('tournament-subtitle');
const venueNameEl = document.getElementById('venue-name');
const venueAddressEl = document.getElementById('venue-address');
const mapsLinkEl = document.getElementById('open-google-maps');
const contactLockedEl = document.getElementById('contact-locked');
const contactCardEl = document.getElementById('contact-card');
const orgNameEl = document.getElementById('org-name');
const orgPhoneEl = document.getElementById('org-phone');
const orgEmailEl = document.getElementById('org-email');
const orgVerifiedEl = document.getElementById('org-verified');
const commentsListEl = document.getElementById('comments-list');
const commentFormEl = document.getElementById('comment-form');
const commentTextEl = document.getElementById('comment-text');
const commentMessageEl = document.getElementById('comment-message');

let venueMap = null;
let venueMarker = null;

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
function getApiErrorMessage(data, fallback) {
    if (data && typeof data === 'object') {
        return data.error || data.msg || fallback;
    }
    return fallback;
}

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
function isAuthExpiredMessage(message) {
    const text = String(message || '').toLowerCase();
    return text.includes('token has expired') || text.includes('missing authorization header') || text.includes('bad authorization header');
}

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
function clearStaleTournamentAuth() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
}

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
async function parsePayload(res) {
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

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
function formatDateSafe(value) {
    if (!value) {
        return '-';
    }
    return new Date(value).toLocaleString();
}

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
function createGoogleMapsUrlForVenue(lat, lng) {
    if (window.SportsPlatformVenue && typeof window.SportsPlatformVenue.createGoogleMapsUrl === 'function') {
        return window.SportsPlatformVenue.createGoogleMapsUrl(lat, lng);
    }
    return `https://www.google.com/maps?q=${encodeURIComponent(`${lat},${lng}`)}`;
}

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
function renderVenueMap(lat, lng) {
    const point = [Number(lat), Number(lng)];
    if (!venueMap) {
        venueMap = L.map('venue-map').setView(point, 14);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
        }).addTo(venueMap);
        venueMarker = L.marker(point).addTo(venueMap);
        return;
    }

    venueMap.setView(point, 14);
    if (venueMarker) {
        venueMarker.setLatLng(point);
    } else {
        venueMarker = L.marker(point).addTo(venueMap);
    }
}

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
function renderComments(comments) {
    if (!comments.length) {
        commentsListEl.innerHTML = '<p class="muted">No comments yet.</p>';
        return;
    }

    commentsListEl.innerHTML = comments
        .map(
            (item) => `
            <article class="comment-item">
                <p>${item.comment_text}</p>
                <p class="muted">${formatDateSafe(item.created_at)}</p>
            </article>
        `
        )
        .join('');
}

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
async function loadTournamentDetails() {
    if (!tournamentId) {
        subtitleEl.textContent = 'Missing tournament id.';
        return;
    }

    const res = await fetch(`${TOURNAMENT_API_BASE}/tournament/${encodeURIComponent(tournamentId)}`);
    const data = await parsePayload(res);
    if (!res.ok) {
        subtitleEl.textContent = data.error || 'Failed to load tournament details.';
        return;
    }

    titleEl.textContent = data.name;
    subtitleEl.textContent = `${data.sport} | ${data.mode} | Date: ${data.date}`;
    venueNameEl.textContent = data.venue_name || data.name || '-';
    venueAddressEl.textContent = data.venue_address || '-';
    mapsLinkEl.href = createGoogleMapsUrlForVenue(data.latitude, data.longitude);

    const liveStreamContainer = document.getElementById('live-stream-container');
    const youtubeLinkEl = document.getElementById('youtube-link');
    if (data.youtube_link) {
        liveStreamContainer.classList.remove('hidden');
        youtubeLinkEl.href = data.youtube_link;
    } else {
        liveStreamContainer.classList.add('hidden');
    }

    renderVenueMap(data.latitude, data.longitude);
}

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
async function loadOrganizerContact() {
    const authTokenForTournamentPage = getTournamentPageToken();
    if (!authTokenForTournamentPage) {
        contactLockedEl.classList.remove('hidden');
        contactCardEl.classList.add('hidden');
        return;
    }

    const res = await fetch(`${TOURNAMENT_API_BASE}/tournament/${encodeURIComponent(tournamentId)}/organizer-contact`, {
        headers: { Authorization: `Bearer ${authTokenForTournamentPage}` },
    });
    const data = await parsePayload(res);

    if (!res.ok) {
        const apiMessage = getApiErrorMessage(data, 'Unable to load organizer contact.');
        if (isAuthExpiredMessage(apiMessage)) {
            clearStaleTournamentAuth();
            contactLockedEl.textContent = 'Session expired. Login again from Account tab.';
        } else {
            contactLockedEl.textContent = apiMessage;
        }
        contactLockedEl.classList.remove('hidden');
        contactCardEl.classList.add('hidden');
        return;
    }

    contactLockedEl.classList.add('hidden');
    contactCardEl.classList.remove('hidden');
    orgNameEl.textContent = data.organizer_name || '-';
    orgPhoneEl.textContent = data.phone || '-';
    orgEmailEl.textContent = data.email || '-';
    orgVerifiedEl.textContent = data.verified ? 'Verified' : 'Not verified';
}

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
async function loadComments() {
    const res = await fetch(`${TOURNAMENT_API_BASE}/tournament/${encodeURIComponent(tournamentId)}/comments`);
    const data = await parsePayload(res);
    if (!res.ok) {
        commentsListEl.innerHTML = `<p class="muted">${getApiErrorMessage(data, 'Failed to load comments.')}</p>`;
        return;
    }
    renderComments(data);
}

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
async function postComment(event) {
    event.preventDefault();
    const authTokenForTournamentPage = getTournamentPageToken();

    if (!authTokenForTournamentPage) {
        commentMessageEl.textContent = 'Login is required to post a comment.';
        return;
    }

    const commentText = commentTextEl.value.trim();
    if (!commentText) {
        commentMessageEl.textContent = 'Comment cannot be empty.';
        return;
    }

    const res = await fetch(`${TOURNAMENT_API_BASE}/tournament/${encodeURIComponent(tournamentId)}/comments`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authTokenForTournamentPage}`,
        },
        body: JSON.stringify({ comment_text: commentText }),
    });
    const data = await parsePayload(res);
    if (!res.ok) {
        const apiMessage = getApiErrorMessage(data, 'Failed to post comment.');
        if (isAuthExpiredMessage(apiMessage)) {
            clearStaleTournamentAuth();
            commentMessageEl.textContent = 'Session expired. Login again from Account tab.';
        } else {
            commentMessageEl.textContent = apiMessage;
        }
        return;
    }

    commentMessageEl.textContent = 'Comment posted.';
    commentFormEl.reset();
    loadComments();
}

// NEW FEATURE - DO NOT MODIFY EXISTING CODE
function setupTournamentPage() {
    commentFormEl.addEventListener('submit', postComment);
    loadTournamentDetails();
    loadOrganizerContact();
    loadComments();
}

setupTournamentPage();
