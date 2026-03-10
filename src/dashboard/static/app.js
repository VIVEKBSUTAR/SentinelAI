let ws = null;
let eventCount = 0;
let config = {};

// DOM Elements
const statusIndicator = document.querySelector('.status-indicator');
const statusText = document.getElementById('connection-status');
const eventFeed = document.getElementById('event-feed');
const eventCountBadge = document.getElementById('event-count');
const cameraList = document.getElementById('camera-list');

// Initialize
async function init() {
    await fetchConfig();
    setupCameras();
    await fetchRecentEvents();
    connectWebSocket();
    
    // Poll status periodically
    setInterval(fetchStatus, 2000);
}

async function fetchConfig() {
    try {
        const res = await fetch('/api/config');
        config = await res.json();
    } catch (err) {
        console.error('Failed to fetch config', err);
    }
}

function setupCameras() {
    if (!config.cameras) return;
    
    cameraList.innerHTML = '';
    
    Object.keys(config.cameras).forEach(camId => {
        const card = document.createElement('div');
        card.className = 'camera-card';
        card.id = `cam-${camId}`;
        card.innerHTML = `
            <div class="camera-header">
                <span class="camera-id">${camId}</span>
                <span class="camera-status offline" id="status-${camId}">Offline</span>
            </div>
            <div class="camera-stats">
                <div>FPS: <span class="stat-value" id="fps-${camId}">--</span></div>
                <div>Tracks: <span class="stat-value" id="tracks-${camId}">0</span></div>
            </div>
        `;
        cameraList.appendChild(card);
    });
}

async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        const status = await res.json();
        
        // Update camera cards based on status
        Object.entries(status.cameras || {}).forEach(([camId, data]) => {
            const statusEl = document.getElementById(`status-${camId}`);
            const fpsEl = document.getElementById(`fps-${camId}`);
            
            if (statusEl && data.active) {
                statusEl.textContent = 'Active';
                statusEl.className = 'camera-status';
                if (data.fps) fpsEl.textContent = data.fps.toFixed(1);
            } else if (statusEl) {
                statusEl.textContent = 'Offline';
                statusEl.className = 'camera-status offline';
                if (fpsEl) fpsEl.textContent = '--';
            }
        });
    } catch (err) {
        // Silently fail, it's just polling
    }
}

async function fetchRecentEvents() {
    try {
        const res = await fetch('/api/events?limit=20');
        const events = await res.json();
        
        if (events.length > 0) {
            eventFeed.innerHTML = '';
            // Events come oldest first, we prepend so newest is on top
            events.forEach(addEventToFeed);
        }
    } catch (err) {
        console.error('Failed to fetch recent events', err);
    }
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        statusIndicator.className = 'status-indicator connected';
        statusText.textContent = 'Connected (Live)';
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'event') {
            addEventToFeed(data.data);
            
            // Hacky workaround: update track count dynamically from person_count events
            if (data.data.event_type === 'person_count') {
                const tracksEl = document.getElementById(`tracks-${data.data.camera_id}`);
                if (tracksEl) {
                    tracksEl.textContent = data.data.metadata.count;
                }
            }
        }
    };
    
    ws.onclose = () => {
        statusIndicator.className = 'status-indicator disconnected';
        statusText.textContent = 'Disconnected. Reconnecting...';
        setTimeout(connectWebSocket, 3000);
    };
    
    ws.onerror = (err) => {
        console.error('WebSocket error', err);
        ws.close();
    };
}

function addEventToFeed(evt) {
    // Remove empty state if present
    const emptyState = eventFeed.querySelector('.empty-state');
    if (emptyState) emptyState.remove();
    
    eventCount++;
    eventCountBadge.textContent = eventCount;
    
    const card = document.createElement('div');
    card.className = `event-card severity-${evt.severity}`;
    
    const time = new Date(evt.timestamp * 1000).toLocaleTimeString();
    
    let metaHtml = `<span>Cam: ${evt.camera_id}</span>`;
    if (evt.zone_name) {
        metaHtml += `<span>Zone: ${evt.zone_name}</span>`;
    }
    
    card.innerHTML = `
        <div class="event-header">
            <span class="event-type">${evt.event_type.replace('_', ' ')}</span>
            <span class="event-time">${time}</span>
        </div>
        <div class="event-desc">${evt.description}</div>
        <div class="event-meta">
            ${metaHtml}
        </div>
    `;
    
    eventFeed.insertBefore(card, eventFeed.firstChild);
    
    // Keep max 100 events in DOM
    if (eventFeed.children.length > 100) {
        eventFeed.lastChild.remove();
    }
}

// Start
document.addEventListener('DOMContentLoaded', init);
