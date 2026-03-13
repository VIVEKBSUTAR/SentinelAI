/* ============================================================
   SENTINEL AI — DASHBOARD CONTROLLER
   ============================================================ */
(function () {
    'use strict';

    // ─── State ───────────────────────────────────────────────
    const state = {
        ws: null,
        connected: false,
        reconnectDelay: 1000,
        reconnectMax: 16000,
        currentCamera: null,
        cameras: {},
        eventCount: 0,
        previousStats: null,
        statsInterval: null,
        uptimeInterval: null,
        systemUptime: 0,
    };

    // ─── DOM refs ────────────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    const dom = {
        statusPill:       $('#status-pill'),
        statusDot:        $('#status-dot'),
        connectionLabel:  $('#connection-label'),
        uptimeValue:      $('#uptime-value'),
        topbarCameras:    $('#topbar-cameras'),
        topbarFps:        $('#topbar-fps'),
        cameraSelect:     $('#camera-select'),
        cameraFeed:       $('#camera-feed'),
        feedOverlay:      $('.feed-overlay'),
        feedStatus:       $('#feed-status'),
        timelineFeed:     $('#timeline-feed'),
        timelineEmpty:    $('#timeline-empty'),
        eventCountBadge:  $('#event-count-badge'),
        statCamerasVal:   $('#stat-cameras-value'),
        statPeopleVal:    $('#stat-people-value'),
        statEventsVal:    $('#stat-events-value'),
        statFpsVal:       $('#stat-fps-value'),
        sevBarCritical:   $('#sev-bar-critical'),
        sevBarWarning:    $('#sev-bar-warning'),
        sevBarInfo:       $('#sev-bar-info'),
    };

    // ─── Init ────────────────────────────────────────────────
    async function init() {
        await loadConfig();
        await loadInitialEvents();
        connectWebSocket();
        startStatsPolling();
        startUptimeCounter();
    }

    // ─── Configuration loading ───────────────────────────────
    async function loadConfig() {
        try {
            const res = await fetch('/api/config');
            const config = await res.json();
            state.cameras = config.cameras || {};

            // Populate camera select
            dom.cameraSelect.innerHTML = '';
            Object.keys(state.cameras).forEach((camId, i) => {
                const opt = document.createElement('option');
                opt.value = camId;
                opt.textContent = `CAM: ${camId.toUpperCase()}`;
                dom.cameraSelect.appendChild(opt);
                if (i === 0) state.currentCamera = camId;
            });

            dom.cameraSelect.addEventListener('change', (e) => {
                state.currentCamera = e.target.value;
                startCameraFeed();
            });

            startCameraFeed();
        } catch (err) {
            console.error('Failed to load config:', err);
        }
    }

    // ─── Camera Feed (MJPEG) ─────────────────────────────────
    function startCameraFeed() {
        if (!state.currentCamera) return;
        // Setting an img src to the MJPEG endpoint makes it stream
        const feedUrl = `/api/video_feed/${state.currentCamera}`;
        dom.cameraFeed.src = feedUrl;

        dom.cameraFeed.onload = () => {
            dom.feedOverlay.classList.add('hidden');
        };
        dom.cameraFeed.onerror = () => {
            dom.feedOverlay.classList.remove('hidden');
            dom.feedStatus.textContent = 'Feed unavailable';
        };

        dom.feedStatus.textContent = `Connecting to ${state.currentCamera}…`;
    }

    // ─── WebSocket ───────────────────────────────────────────
    function connectWebSocket() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}/ws`;

        state.ws = new WebSocket(url);

        state.ws.onopen = () => {
            state.connected = true;
            state.reconnectDelay = 1000;
            updateConnectionUI(true);
        };

        state.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'event') {
                    addEventToTimeline(msg.data);
                }
            } catch (e) {
                console.warn('WS parse error:', e);
            }
        };

        state.ws.onclose = () => {
            state.connected = false;
            updateConnectionUI(false);
            scheduleReconnect();
        };

        state.ws.onerror = () => {
            state.ws.close();
        };
    }

    function scheduleReconnect() {
        setTimeout(() => {
            connectWebSocket();
        }, state.reconnectDelay);
        state.reconnectDelay = Math.min(state.reconnectDelay * 2, state.reconnectMax);
    }

    function updateConnectionUI(connected) {
        dom.statusDot.className = 'status-dot' + (connected ? ' connected' : ' disconnected');
        dom.statusPill.className = 'status-pill' + (connected ? ' connected' : ' disconnected');
        dom.connectionLabel.textContent = connected ? 'OPERATIONAL' : 'DISCONNECTED';
    }

    // ─── Events ──────────────────────────────────────────────
    async function loadInitialEvents() {
        try {
            const res = await fetch('/api/events?limit=30');
            const events = await res.json();
            // Reverse so newest first in the timeline
            events.reverse().forEach((evt) => addEventToTimeline(evt, false));
        } catch (err) {
            console.error('Failed to load events:', err);
        }
    }

    function addEventToTimeline(evt, animate = true) {
        // Remove empty state
        if (dom.timelineEmpty) {
            dom.timelineEmpty.remove();
        }

        state.eventCount++;
        dom.eventCountBadge.textContent = state.eventCount;

        const card = document.createElement('div');
        card.className = `event-card severity-${evt.severity || 'info'}`;
        if (!animate) card.style.animation = 'none';

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
            </div>
        `;

        // Prepend (newest on top)
        dom.timelineFeed.prepend(card);

        // Trim DOM to prevent unbounded growth
        const maxCards = 200;
        while (dom.timelineFeed.children.length > maxCards) {
            dom.timelineFeed.lastChild.remove();
        }
    }

    // ─── Stats Polling ───────────────────────────────────────
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
        } catch (err) {
            // Silently retry on next interval
        }
    }

    function updateStatCards(stats) {
        // Cameras
        dom.statCamerasVal.textContent = `${stats.active_cameras}/${stats.total_cameras}`;
        dom.topbarCameras.textContent = `${stats.active_cameras}/${stats.total_cameras}`;

        // People
        animateCounter(dom.statPeopleVal, stats.person_count);

        // Events
        animateCounter(dom.statEventsVal, stats.total_events);

        // FPS
        dom.statFpsVal.textContent = stats.avg_fps > 0 ? stats.avg_fps.toFixed(1) : '--';
        dom.topbarFps.textContent = stats.avg_fps > 0 ? stats.avg_fps.toFixed(1) : '--';

        // Severity bar
        const total = stats.total_events || 1;
        const sev = stats.severity_counts || {};
        dom.sevBarCritical.style.width = `${((sev.critical || 0) / total) * 100}%`;
        dom.sevBarWarning.style.width = `${((sev.warning || 0) / total) * 100}%`;
        dom.sevBarInfo.style.width = `${((sev.info || 0) / total) * 100}%`;

        // Trends (compare with previous)
        if (state.previousStats) {
            updateTrend('stat-people', stats.person_count, state.previousStats.person_count);
            updateTrend('stat-fps', stats.avg_fps, state.previousStats.avg_fps);
        }
    }

    function animateCounter(el, target) {
        const current = parseInt(el.textContent) || 0;
        if (current === target) return;
        el.textContent = target;
        el.style.transition = 'transform 0.2s, color 0.3s';
        el.style.transform = 'scale(1.15)';
        el.style.color = 'var(--accent)';
        setTimeout(() => {
            el.style.transform = 'scale(1)';
            el.style.color = '';
        }, 250);
    }

    function updateTrend(cardId, current, previous) {
        const card = document.getElementById(cardId);
        if (!card) return;
        const trend = card.querySelector('.stat-trend');
        if (!trend) return;

        if (current > previous) {
            trend.className = 'stat-trend up';
            trend.textContent = '▲';
        } else if (current < previous) {
            trend.className = 'stat-trend down';
            trend.textContent = '▼';
        } else {
            trend.className = 'stat-trend neutral';
            trend.textContent = '—';
        }
    }

    // ─── Uptime Counter ──────────────────────────────────────
    function startUptimeCounter() {
        state.uptimeInterval = setInterval(() => {
            state.systemUptime++;
            dom.uptimeValue.textContent = formatUptime(state.systemUptime);
        }, 1000);
    }

    function formatUptime(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        return `${pad2(h)}h ${pad2(m)}m ${pad2(s)}s`;
    }

    // ─── Utilities ───────────────────────────────────────────
    function formatTime(timestamp) {
        if (!timestamp) return '--:--:--';
        const d = new Date(timestamp * 1000);
        return d.toLocaleTimeString('en-GB', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    }

    function pad2(n) {
        return String(n).padStart(2, '0');
    }

    function escapeHtml(str) {
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
        return String(str).replace(/[&<>"']/g, (c) => map[c]);
    }

    // ─── Launch ──────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', init);
})();
