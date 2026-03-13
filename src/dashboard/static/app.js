/* ============================================================
   SENTINEL AI — COMMAND CENTER  (v0.9.0)
   All views fully wired to the backend API.
   ============================================================ */
(function () {
    'use strict';

    // ─── Global State ─────────────────────────────────────────────────────────
    const state = {
        ws: null,
        connected: false,
        reconnectDelay: 1000,
        reconnectMax: 16000,
        currentSection: 'dashboard',
        cameras: {},
        cameraStatus: {},   // camera_id → {active, fps, person_count, suspicious_count}
        allEvents: [],       // local mirror of events for table & filters
        filteredEvents: [],
        eventCount: 0,
        unackedCount: 0,
        eventsPage: 0,
        eventsPerPage: 25,
        sortField: 'timestamp',
        sortDir: 'desc',
        systemUptime: 0,
        statsInterval: null,
        uptimeInterval: null,
        camerasInterval: null,
        previousStats: null,
        timelineFilter: 'all',
        currentCamera: null,   // dashboard feed
        selectedEventId: null,
    };

    // ─── DOM helpers ──────────────────────────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => [...document.querySelectorAll(sel)];

    // ─── Init ─────────────────────────────────────────────────────────────────
    async function init() {
        setupNavigation();
        await loadConfig();
        await loadInitialEvents();
        connectWebSocket();
        startStatsPolling();
        startUptimeCounter();
        startCamerasPolling();
        wireButtons();
    }

    // ─── Navigation ───────────────────────────────────────────────────────────
    function setupNavigation() {
        $$('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const section = item.dataset.section;
                navigateTo(section);
            });
        });
    }

    function navigateTo(section) {
        state.currentSection = section;

        // Update nav active state
        $$('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.section === section));

        // Show/hide sections
        $$('.section-view').forEach(s => s.classList.toggle('active', s.id === `section-${section}`));

        // Update topbar title
        $('#topbar-title').textContent = section.toUpperCase();

        // Section-specific actions
        if (section === 'cameras') refreshCamerasView();
        if (section === 'events')  renderEventsTable();
        if (section === 'settings') loadSettingsData();
    }

    // ─── Configuration Loading ────────────────────────────────────────────────
    async function loadConfig() {
        try {
            const res = await fetch('/api/config');
            const config = await res.json();
            state.cameras = config.cameras || {};

            // Camera select (dashboard)
            const sel = $('#camera-select');
            sel.innerHTML = '';
            Object.keys(state.cameras).forEach((camId, i) => {
                const opt = document.createElement('option');
                opt.value = camId;
                opt.textContent = `CAM: ${camId.toUpperCase()}`;
                sel.appendChild(opt);
                if (i === 0) state.currentCamera = camId;
            });
            sel.addEventListener('change', (e) => {
                state.currentCamera = e.target.value;
                startDashboardFeed();
            });

            // Camera filter dropdown in events section
            const camFilter = $('#ev-camera-filter');
            Object.keys(state.cameras).forEach(camId => {
                const opt = document.createElement('option');
                opt.value = camId;
                opt.textContent = camId.toUpperCase();
                camFilter.appendChild(opt);
            });

            // Event type checkboxes (pre-populated from known types)
            const knownTypes = [
                'loitering', 'zone_intrusion', 'crowd_formation',
                'unusual_motion', 'person_count', 'abandoned_object',
            ];
            const typeContainer = $('#ev-type-checks');
            knownTypes.forEach(t => {
                const lbl = document.createElement('label');
                lbl.className = 'check-label';
                lbl.innerHTML = `<input type="checkbox" value="${t}" checked class="ev-type-check"> ${t.replace(/_/g, ' ')}`;
                typeContainer.appendChild(lbl);
            });

            // Zone toggles in settings
            const zones = config.zones || {};
            const zoneContainer = $('#cfg-zones');
            Object.entries(zones).forEach(([zn, zv]) => {
                const row = document.createElement('label');
                row.className = 'zone-toggle-row';
                row.innerHTML = `<input type="checkbox" checked class="zone-ck" data-zone="${escapeHtml(zn)}"> <span>${escapeHtml(zn)}</span> <small class="text-muted">(${escapeHtml(zv.camera || '')})</small>`;
                zoneContainer.appendChild(row);
            });

            // Populate event rule fields from config
            const ev = config.events || {};
            const setVal = (id, val) => { if ($(id)) $(id).value = val || ''; };
            setVal('#cfg-loitering', ev.loitering_duration);
            setVal('#cfg-crowd', ev.crowd_threshold);
            setVal('#cfg-speed', ev.speed_threshold);

            $('#nav-cameras-badge').textContent = Object.keys(state.cameras).length;

            startDashboardFeed();
        } catch (err) {
            console.error('Config load error:', err);
        }
    }

    // ─── Dashboard Camera Feed (MJPEG) ────────────────────────────────────────
    function startDashboardFeed() {
        if (!state.currentCamera) return;
        const img = $('#camera-feed');
        const overlay = $('#feed-overlay');
        const status = $('#feed-status');

        status.textContent = `Connecting to ${state.currentCamera}…`;
        overlay.classList.remove('hidden');

        img.onload = () => overlay.classList.add('hidden');
        img.onerror = () => {
            overlay.classList.remove('hidden');
            status.textContent = 'Feed unavailable – pipeline may not be running';
        };

        // Append timestamp to bust any cached 404
        img.src = `/api/video_feed/${state.currentCamera}?t=${Date.now()}`;
    }

    // ─── WebSocket ────────────────────────────────────────────────────────────
    function connectWebSocket() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}/ws`;
        state.ws = new WebSocket(url);

        state.ws.onopen = () => {
            state.connected = true;
            state.reconnectDelay = 1000;
            updateConnectionUI(true);
        };

        state.ws.onmessage = (ev) => {
            try {
                const msg = JSON.parse(ev.data);
                handleWsMessage(msg);
            } catch (e) { /* ignore malformed */ }
        };

        state.ws.onclose = () => {
            state.connected = false;
            updateConnectionUI(false);
            setTimeout(connectWebSocket, state.reconnectDelay);
            state.reconnectDelay = Math.min(state.reconnectDelay * 2, state.reconnectMax);
        };

        state.ws.onerror = () => state.ws.close();
    }

    function handleWsMessage(msg) {
        if (msg.type === 'event') {
            const evt = msg.data;
            addEventToTimeline(evt);
            // Also add to local events mirror for table
            state.allEvents.unshift(evt);
            state.eventCount++;
            if (!evt.acknowledged) state.unackedCount++;
            $('#event-count-badge').textContent = state.eventCount;
            updateEventsNavBadge();
            // If events section is open, refresh table
            if (state.currentSection === 'events') renderEventsTable();
        }
        if (msg.type === 'status') {
            const d = msg.data;
            state.cameraStatus[d.camera_id] = d;
            updateHudForCamera(d.camera_id);
            // Update camera cards if cameras section is showing
            if (state.currentSection === 'cameras') updateCameraCard(d.camera_id);
        }
    }

    function updateConnectionUI(connected) {
        const dot = $('#status-dot');
        const pill = $('#status-pill');
        const label = $('#connection-label');
        dot.className = 'status-dot' + (connected ? ' connected' : ' disconnected');
        pill.className = 'status-pill' + (connected ? ' connected' : ' disconnected');
        label.textContent = connected ? 'OPERATIONAL' : 'DISCONNECTED';
    }

    // ─── HUD overlay on dashboard feed ────────────────────────────────────────
    function updateHudForCamera(cameraId) {
        if (cameraId !== state.currentCamera) return;
        const st = state.cameraStatus[cameraId] || {};
        const tracksEl = $('#hud-tracks');
        const susEl = $('#hud-suspicious');
        const susWrap = $('#hud-sus-wrap');
        if (tracksEl) tracksEl.textContent = st.person_count || 0;
        if (susEl) susEl.textContent = st.suspicious_count || 0;
        if (susWrap) susWrap.classList.toggle('active', (st.suspicious_count || 0) > 0);
    }

    // ─── Events ───────────────────────────────────────────────────────────────
    async function loadInitialEvents() {
        try {
            const res = await fetch('/api/events?limit=100');
            const events = await res.json();
            state.allEvents = events.reverse(); // newest first
            state.eventCount = events.length;
            state.unackedCount = events.filter(e => !e.acknowledged).length;
            $('#event-count-badge').textContent = state.eventCount;
            updateEventsNavBadge();

            // Populate timeline in reverse so newest is at top
            [...events].reverse().forEach(e => addEventToTimeline(e, false));
        } catch (err) {
            console.error('Events load error:', err);
        }
    }

    function addEventToTimeline(evt, animate = true) {
        const feed = $('#timeline-feed');
        const empty = $('#timeline-empty');
        if (empty) empty.remove();

        // Apply timeline filter
        if (state.timelineFilter !== 'all' && evt.severity !== state.timelineFilter) return;

        const card = document.createElement('div');
        card.className = `event-card severity-${evt.severity || 'info'}${evt.acknowledged ? ' acked' : ''}`;
        if (!animate) card.style.animation = 'none';
        card.dataset.eventId = evt.id ?? '';

        const time = formatTime(evt.timestamp);
        const eventType = (evt.event_type || 'unknown').replace(/_/g, ' ');

        card.innerHTML = `
            <div class="event-header">
                <span class="event-type">${escapeHtml(eventType)}</span>
                <span class="event-time">${time}</span>
            </div>
            <div class="event-desc">${escapeHtml(evt.description || '')}</div>
            <div class="event-meta">
                <span class="event-meta-tag">📷 ${escapeHtml(evt.camera_id || '--')}</span>
                ${evt.zone_name ? `<span class="event-meta-tag">📍 ${escapeHtml(evt.zone_name)}</span>` : ''}
                ${evt.track_ids && evt.track_ids.length ? `<span class="event-meta-tag">🏷 ${evt.track_ids.length} tracks</span>` : ''}
                ${evt.acknowledged ? '<span class="acked-tag">✓ Acked</span>' : ''}
            </div>`;

        card.addEventListener('click', () => openEventModal(evt));
        feed.prepend(card);

        // Trim to prevent unbounded growth
        while (feed.children.length > 200) feed.lastChild.remove();
    }

    // ─── Stats Polling ────────────────────────────────────────────────────────
    function startStatsPolling() {
        fetchStats();
        state.statsInterval = setInterval(fetchStats, 3000);
    }

    async function fetchStats() {
        try {
            const res = await fetch('/api/stats');
            const stats = await res.json();
            updateStatCards(stats);
            state.systemUptime = stats.uptime_seconds || 0;
            state.previousStats = stats;
        } catch (err) { /* silent retry */ }
    }

    function updateStatCards(stats) {
        const set = (id, val) => { const el = $(id); if (el) el.textContent = val; };

        set('#stat-cameras-value', `${stats.active_cameras}/${stats.total_cameras}`);
        set('#topbar-cameras', `${stats.active_cameras}/${stats.total_cameras}`);
        set('#topbar-people', stats.person_count);

        animateCounter($('#stat-people-value'), stats.person_count);
        animateCounter($('#stat-events-value'), stats.total_events);

        const fps = stats.avg_fps > 0 ? stats.avg_fps.toFixed(1) : '--';
        set('#stat-fps-value', fps);
        set('#topbar-fps', fps);

        const total = Math.max(stats.total_events, 1);
        const sev = stats.severity_counts || {};
        const setPct = (id, n) => { const el = $(id); if (el) el.style.width = `${(n / total) * 100}%`; };
        setPct('#sev-bar-critical', sev.critical || 0);
        setPct('#sev-bar-warning', sev.warning || 0);
        setPct('#sev-bar-info', sev.info || 0);

        // Trends
        if (state.previousStats) {
            updateTrend('#trend-people', stats.person_count, state.previousStats.person_count);
            updateTrend('#trend-fps', stats.avg_fps, state.previousStats.avg_fps);
        }

        // Unacked badge
        state.unackedCount = stats.unacknowledged_events || 0;
        updateEventsNavBadge();
    }

    function updateEventsNavBadge() {
        const badge = $('#nav-events-badge');
        if (!badge) return;
        badge.textContent = state.unackedCount;
        badge.classList.toggle('alert', state.unackedCount > 0);
        badge.style.display = state.unackedCount > 0 ? '' : 'none';
    }

    function animateCounter(el, target) {
        if (!el) return;
        const current = parseInt(el.textContent) || 0;
        if (current === target) return;
        el.textContent = target;
        el.style.transform = 'scale(1.15)';
        el.style.color = 'var(--accent)';
        setTimeout(() => { el.style.transform = 'scale(1)'; el.style.color = ''; }, 250);
    }

    function updateTrend(sel, current, previous) {
        const el = $(sel);
        if (!el) return;
        if (current > previous) { el.className = 'stat-trend up'; el.textContent = '▲'; }
        else if (current < previous) { el.className = 'stat-trend down'; el.textContent = '▼'; }
        else { el.className = 'stat-trend neutral'; el.textContent = '—'; }
    }

    // ─── Uptime Counter ───────────────────────────────────────────────────────
    function startUptimeCounter() {
        state.uptimeInterval = setInterval(() => {
            state.systemUptime++;
            const el = $('#uptime-value');
            if (el) el.textContent = formatUptime(state.systemUptime);
        }, 1000);
    }

    // ─── Cameras View ─────────────────────────────────────────────────────────
    function startCamerasPolling() {
        fetchCamerasData();
        state.camerasInterval = setInterval(fetchCamerasData, 3000);
    }

    async function fetchCamerasData() {
        try {
            const res = await fetch('/api/cameras');
            const cameras = await res.json();
            cameras.forEach(cam => {
                state.cameraStatus[cam.id] = cam;
            });
            if (state.currentSection === 'cameras') refreshCamerasView();
        } catch (err) { /* silent */ }
    }

    function refreshCamerasView() {
        const grid = $('#cameras-grid');
        const activeCount = Object.values(state.cameraStatus).filter(c => c.active).length;
        const total = Object.keys(state.cameras).length;
        const countEl = $('#cameras-active-count');
        if (countEl) countEl.textContent = `${activeCount}/${total} active`;

        // Build or update camera cards
        Object.keys(state.cameras).forEach(camId => {
            let card = $(`#cam-card-${camId}`);
            if (!card) {
                card = buildCameraCard(camId);
                grid.appendChild(card);
            }
            updateCameraCard(camId);
        });
    }

    function buildCameraCard(camId) {
        const card = document.createElement('div');
        card.className = 'camera-card';
        card.id = `cam-card-${camId}`;
        card.innerHTML = `
            <div class="camera-card-header">
                <div class="cam-name">
                    <span class="cam-status-dot" id="cam-dot-${escapeHtml(camId)}"></span>
                    <span class="cam-id-label">${escapeHtml(camId.toUpperCase())}</span>
                </div>
                <span class="cam-type-badge">${escapeHtml((state.cameras[camId] || {}).type || 'usb')}</span>
            </div>
            <div class="camera-feed-wrap">
                <img class="camera-card-feed" id="cam-feed-${escapeHtml(camId)}"
                     src="/api/video_feed/${escapeHtml(camId)}"
                     alt="Feed ${escapeHtml(camId)}"/>
                <div class="camera-card-overlay" id="cam-overlay-${escapeHtml(camId)}">
                    <span>Connecting…</span>
                </div>
                <div class="feed-corner tl"></div>
                <div class="feed-corner tr"></div>
                <div class="feed-corner bl"></div>
                <div class="feed-corner br"></div>
                <!-- bbox legend mini -->
                <div class="bbox-legend mini">
                    <span class="bbox-swatch green"></span><span class="bbox-swatch red"></span>
                </div>
            </div>
            <div class="camera-card-stats" id="cam-stats-${escapeHtml(camId)}">
                <div class="cam-stat"><span class="cam-stat-val mono" id="cam-fps-${escapeHtml(camId)}">--</span><span class="cam-stat-lbl">FPS</span></div>
                <div class="cam-stat"><span class="cam-stat-val mono" id="cam-persons-${escapeHtml(camId)}">0</span><span class="cam-stat-lbl">Persons</span></div>
                <div class="cam-stat"><span class="cam-stat-val mono alert" id="cam-sus-${escapeHtml(camId)}">0</span><span class="cam-stat-lbl">Alerts</span></div>
            </div>
            <div class="camera-card-actions">
                <button class="btn btn-ghost btn-sm" onclick="window.sentinelNav('dashboard', '${escapeHtml(camId)}')">
                    View Feed
                </button>
            </div>`;

        const img = card.querySelector(`#cam-feed-${camId}`);
        const overlay = card.querySelector(`#cam-overlay-${camId}`);
        if (img) {
            img.onload = () => { if (overlay) overlay.style.display = 'none'; };
            img.onerror = () => { if (overlay) { overlay.style.display = 'flex'; overlay.querySelector('span').textContent = 'Unavailable'; } };
        }

        return card;
    }

    function updateCameraCard(camId) {
        const st = state.cameraStatus[camId] || {};
        const dot = $(`#cam-dot-${camId}`);
        const fpsEl = $(`#cam-fps-${camId}`);
        const persEl = $(`#cam-persons-${camId}`);
        const susEl = $(`#cam-sus-${camId}`);
        const card = $(`#cam-card-${camId}`);

        if (dot) dot.className = 'cam-status-dot ' + (st.active ? 'online' : 'offline');
        if (fpsEl) fpsEl.textContent = st.fps > 0 ? st.fps.toFixed(1) : '--';
        if (persEl) persEl.textContent = st.person_count || 0;
        if (susEl) {
            susEl.textContent = st.suspicious_count || 0;
            susEl.classList.toggle('alert', (st.suspicious_count || 0) > 0);
        }
        if (card) card.classList.toggle('camera-offline', !st.active);
    }

    // Expose global for inline onclick
    window.sentinelNav = function(section, camId) {
        if (camId) {
            state.currentCamera = camId;
            const sel = $('#camera-select');
            if (sel) sel.value = camId;
        }
        navigateTo(section);
        if (camId) startDashboardFeed();
    };

    // ─── Events Table ─────────────────────────────────────────────────────────
    function getFilteredEvents() {
        const search = ($('#ev-search') || {}).value || '';
        const sevChecks = [].filter.call($$('.ev-sev-check'), c => c.checked).map(c => c.value);
        const typeChecks = [].filter.call($$('.ev-type-check'), c => c.checked).map(c => c.value);
        const camFilter = ($('#ev-camera-filter') || {}).value || '';

        return state.allEvents.filter(e => {
            if (sevChecks.length && !sevChecks.includes(e.severity)) return false;
            if (typeChecks.length && !typeChecks.includes(e.event_type)) return false;
            if (camFilter && e.camera_id !== camFilter) return false;
            if (search) {
                const hay = ((e.description || '') + (e.event_type || '') + (e.camera_id || '')).toLowerCase();
                if (!hay.includes(search.toLowerCase())) return false;
            }
            return true;
        });
    }

    function sortEvents(events) {
        const f = state.sortField;
        const dir = state.sortDir === 'asc' ? 1 : -1;
        return [...events].sort((a, b) => {
            const av = a[f] ?? '', bv = b[f] ?? '';
            return av < bv ? -dir : av > bv ? dir : 0;
        });
    }

    function renderEventsTable() {
        const filtered = sortEvents(getFilteredEvents());
        state.filteredEvents = filtered;

        const countEl = $('#ev-count-label');
        if (countEl) countEl.textContent = `${filtered.length} event${filtered.length !== 1 ? 's' : ''}`;

        const start = state.eventsPage * state.eventsPerPage;
        const page = filtered.slice(start, start + state.eventsPerPage);

        const tbody = $('#events-tbody');
        if (!tbody) return;

        if (page.length === 0) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="6">No events match filters</td></tr>';
        } else {
            tbody.innerHTML = page.map(evt => {
                const time = formatTime(evt.timestamp);
                const typeLabel = (evt.event_type || 'unknown').replace(/_/g, ' ');
                const acked = evt.acknowledged;
                return `<tr class="event-row${acked ? ' acked-row' : ''}" data-id="${evt.id ?? ''}">
                    <td><span class="sev-badge ${evt.severity || 'info'}">${(evt.severity || 'info').toUpperCase()}</span></td>
                    <td class="mono type-cell">${escapeHtml(typeLabel)}</td>
                    <td><span class="cam-badge">${escapeHtml(evt.camera_id || '--')}</span></td>
                    <td class="desc-cell">${escapeHtml(evt.description || '')}</td>
                    <td class="mono time-cell">${time}</td>
                    <td>
                        <div class="row-actions">
                            <button class="btn btn-xs btn-ghost" onclick="window.sentinelAckEvent(${evt.id})" title="Acknowledge" ${acked ? 'disabled' : ''}>
                                ${acked ? '✓' : 'Ack'}
                            </button>
                            <button class="btn btn-xs btn-accent" onclick="window.sentinelOpenEvent(${evt.id})" title="Details">
                                Detail
                            </button>
                        </div>
                    </td>
                </tr>`;
            }).join('');
        }

        renderPagination(filtered.length);

        // Column sort handlers
        $$('.events-table th[data-sort]').forEach(th => {
            th.style.cursor = 'pointer';
            th.addEventListener('click', () => {
                const field = th.dataset.sort;
                if (state.sortField === field) {
                    state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
                } else {
                    state.sortField = field;
                    state.sortDir = 'desc';
                }
                renderEventsTable();
            });
        });
    }

    function renderPagination(total) {
        const pages = Math.ceil(total / state.eventsPerPage);
        const pg = $('#events-pagination');
        if (!pg) return;
        if (pages <= 1) { pg.innerHTML = ''; return; }
        pg.innerHTML = Array.from({length: pages}, (_, i) =>
            `<button class="page-btn${i === state.eventsPage ? ' active' : ''}" onclick="window.sentinelPage(${i})">${i + 1}</button>`
        ).join('');
    }

    window.sentinelPage = (n) => { state.eventsPage = n; renderEventsTable(); };

    window.sentinelAckEvent = async (id) => {
        if (id == null) return;
        try {
            await fetch(`/api/events/${id}/acknowledge`, {method: 'POST'});
            const ev = state.allEvents.find(e => e.id === id);
            if (ev) { ev.acknowledged = true; state.unackedCount = Math.max(0, state.unackedCount - 1); }
            updateEventsNavBadge();
            renderEventsTable();
            showToast('Event acknowledged', 'success');
        } catch { showToast('Failed to acknowledge', 'error'); }
    };

    window.sentinelOpenEvent = (id) => {
        const ev = state.allEvents.find(e => e.id === id);
        if (ev) openEventModal(ev);
    };

    // ─── Event Detail Modal ───────────────────────────────────────────────────
    function openEventModal(evt) {
        state.selectedEventId = evt.id;
        const modal = $('#event-modal');
        const backdrop = $('#modal-backdrop');
        const title = $('#modal-title');
        const body = $('#modal-body');
        const ackBtn = $('#modal-btn-ack');

        title.innerHTML = `<span class="sev-badge ${evt.severity || 'info'}">${(evt.severity || '').toUpperCase()}</span> ${escapeHtml((evt.event_type || '').replace(/_/g, ' '))}`;

        body.innerHTML = `
            <div class="modal-detail-grid">
                <div class="modal-field"><span class="mf-label">Camera</span><span class="mf-val mono">${escapeHtml(evt.camera_id || '--')}</span></div>
                <div class="modal-field"><span class="mf-label">Time</span><span class="mf-val mono">${formatTime(evt.timestamp)}</span></div>
                ${evt.zone_name ? `<div class="modal-field"><span class="mf-label">Zone</span><span class="mf-val mono">${escapeHtml(evt.zone_name)}</span></div>` : ''}
                ${evt.track_ids && evt.track_ids.length ? `<div class="modal-field"><span class="mf-label">Track IDs</span><span class="mf-val mono">${evt.track_ids.join(', ')}</span></div>` : ''}
                <div class="modal-field full"><span class="mf-label">Description</span><span class="mf-val">${escapeHtml(evt.description || '')}</span></div>
                ${evt.metadata && Object.keys(evt.metadata).length ? `<div class="modal-field full">
                    <span class="mf-label">Metadata</span>
                    <pre class="meta-json">${escapeHtml(JSON.stringify(evt.metadata, null, 2))}</pre>
                </div>` : ''}
                <div class="modal-field"><span class="mf-label">Status</span><span class="mf-val">${evt.acknowledged ? '<span class="acked-tag">✓ Acknowledged</span>' : '<span class="pending-tag">Pending</span>'}</span></div>
            </div>`;

        ackBtn.disabled = !!evt.acknowledged;
        ackBtn.onclick = async () => {
            await window.sentinelAckEvent(evt.id);
            evt.acknowledged = true;
            ackBtn.disabled = true;
            ackBtn.textContent = '✓ Acknowledged';
        };

        backdrop.classList.add('open');
        backdrop.setAttribute('aria-hidden', 'false');
    }

    function closeModal() {
        const backdrop = $('#modal-backdrop');
        backdrop.classList.remove('open');
        backdrop.setAttribute('aria-hidden', 'true');
    }

    // ─── Timeline filter pills ────────────────────────────────────────────────
    function setupTimelineFilters() {
        $$('.timeline-filter-bar .filter-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                $$('.timeline-filter-bar .filter-pill').forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                state.timelineFilter = pill.dataset.severity;
                rebuildTimeline();
            });
        });
    }

    function rebuildTimeline() {
        const feed = $('#timeline-feed');
        feed.innerHTML = '';
        const events = [...state.allEvents].reverse();
        if (events.length === 0) {
            feed.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg><span>Waiting for events…</span></div>`;
            return;
        }
        // add newest at top
        events.forEach(e => addEventToTimeline(e, false));
    }

    // ─── Settings / Health ────────────────────────────────────────────────────
    async function loadSettingsData() {
        await refreshHealthData();
        await fetchCamerasData();
        // Populate camera management table
        const tbody = $('#settings-cam-tbody');
        if (!tbody) return;
        const cameras = Object.entries(state.cameras);
        if (!cameras.length) { tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">No cameras configured</td></tr>'; return; }
        tbody.innerHTML = cameras.map(([camId, camCfg]) => {
            const st = state.cameraStatus[camId] || {};
            const active = st.active;
            return `<tr>
                <td class="mono">${escapeHtml(camId)}</td>
                <td>${escapeHtml(camCfg.type || 'usb')}</td>
                <td class="mono">${camCfg.source}</td>
                <td><span class="status-badge ${active ? 'online' : 'offline'}">${active ? 'ACTIVE' : 'OFFLINE'}</span></td>
                <td class="mono">${st.fps > 0 ? st.fps.toFixed(1) : '--'}</td>
                <td class="mono">${st.person_count || 0}</td>
            </tr>`;
        }).join('');
    }

    async function refreshHealthData() {
        try {
            const res = await fetch('/api/health');
            const h = await res.json();
            const set = (id, val) => { const el = $(id); if (el) el.textContent = val; };
            const badge = $('#health-badge');
            if (badge) {
                badge.textContent = h.status.toUpperCase();
                badge.className = 'health-status-badge ' + (h.status === 'ok' ? 'ok' : 'warn');
            }
            set('#health-status', h.status);
            set('#health-cameras', `${h.active_cameras}/${h.total_cameras}`);
            set('#health-queue', h.event_queue);
            set('#health-uptime', formatUptime(h.uptime_seconds));
        } catch {}
    }

    // ─── Export CSV ───────────────────────────────────────────────────────────
    function exportEventsCSV(events) {
        const cols = ['id', 'event_type', 'camera_id', 'severity', 'description', 'timestamp', 'acknowledged'];
        const header = cols.join(',');
        const rows = (events || state.allEvents).map(e =>
            cols.map(c => JSON.stringify(e[c] ?? '')).join(',')
        );
        const blob = new Blob([header + '\n' + rows.join('\n')], {type: 'text/csv'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `sentinel_events_${Date.now()}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        showToast('CSV exported', 'success');
    }

    // ─── Wire all buttons ─────────────────────────────────────────────────────
    function wireButtons() {
        // Dashboard timeline: ack all
        $('#btn-ack-all').addEventListener('click', async () => {
            await fetch('/api/events/acknowledge_all', {method: 'POST'});
            state.allEvents.forEach(e => e.acknowledged = true);
            state.unackedCount = 0;
            updateEventsNavBadge();
            $$('.event-card').forEach(c => c.classList.add('acked'));
            showToast('All events acknowledged', 'success');
        });

        // Timeline filter pills
        setupTimelineFilters();

        // Events section buttons
        $('#btn-apply-filters').addEventListener('click', () => { state.eventsPage = 0; renderEventsTable(); });
        $('#btn-clear-filters').addEventListener('click', () => {
            $$('.ev-sev-check').forEach(c => c.checked = true);
            $$('.ev-type-check').forEach(c => c.checked = true);
            $('#ev-camera-filter').value = '';
            $('#ev-search').value = '';
            state.eventsPage = 0;
            renderEventsTable();
        });

        $('#btn-ack-all-events').addEventListener('click', async () => {
            await fetch('/api/events/acknowledge_all', {method: 'POST'});
            state.allEvents.forEach(e => e.acknowledged = true);
            state.unackedCount = 0;
            updateEventsNavBadge();
            renderEventsTable();
            showToast('All events acknowledged', 'success');
        });

        $('#btn-export-csv').addEventListener('click', () => exportEventsCSV(state.filteredEvents));

        // Events table: live search
        const searchInput = $('#ev-search');
        if (searchInput) {
            searchInput.addEventListener('input', () => { state.eventsPage = 0; renderEventsTable(); });
        }

        // Modal close
        $('#modal-close').addEventListener('click', closeModal);
        $('#modal-btn-close').addEventListener('click', closeModal);
        $('#modal-backdrop').addEventListener('click', (e) => {
            if (e.target === e.currentTarget) closeModal();
        });
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

        // Settings: refresh health
        $('#btn-refresh-health').addEventListener('click', async () => { await refreshHealthData(); showToast('Health refreshed', 'info'); });

        // Settings: export events
        $('#btn-export-events').addEventListener('click', () => exportEventsCSV(state.allEvents));

        // Settings: ack all
        $('#btn-ack-all-settings').addEventListener('click', async () => {
            await fetch('/api/events/acknowledge_all', {method: 'POST'});
            state.allEvents.forEach(e => e.acknowledged = true);
            state.unackedCount = 0;
            updateEventsNavBadge();
            showToast('All events acknowledged', 'success');
        });

        // Settings: clear events
        $('#btn-clear-events').addEventListener('click', async () => {
            if (!confirm('Clear all events from memory? This cannot be undone.')) return;
            await fetch('/api/events', {method: 'DELETE'});
            state.allEvents = [];
            state.eventCount = 0;
            state.unackedCount = 0;
            $('#event-count-badge').textContent = '0';
            updateEventsNavBadge();
            rebuildTimeline();
            renderEventsTable();
            showToast('Event log cleared', 'success');
        });
    }

    // ─── Toast Notifications ──────────────────────────────────────────────────
    function showToast(message, type = 'info') {
        const container = $('#toast-container');
        if (!container) return;
        const t = document.createElement('div');
        t.className = `toast toast-${type}`;
        t.textContent = message;
        container.appendChild(t);
        setTimeout(() => t.classList.add('show'), 10);
        setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 400); }, 3000);
    }

    // ─── Utilities ────────────────────────────────────────────────────────────
    function formatTime(timestamp) {
        if (!timestamp) return '--:--:--';
        const d = new Date(timestamp * 1000);
        return d.toLocaleTimeString('en-GB', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
    }

    function formatUptime(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        return `${pad2(h)}h ${pad2(m)}m ${pad2(s)}s`;
    }

    function pad2(n) { return String(n).padStart(2, '0'); }

    function escapeHtml(str) {
        const map = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
        return String(str).replace(/[&<>"']/g, c => map[c]);
    }

    // ─── Launch ───────────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', init);
})();

