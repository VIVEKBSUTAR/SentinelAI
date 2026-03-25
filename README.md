# SentinelAI

SentinelAI is a real-time, event-driven surveillance pipeline that turns live camera streams into structured incidents and dashboard telemetry.

It is designed to reduce continuous manual monitoring by combining:

- Camera ingestion
- Person detection and tracking
- Rule-based event interpretation
- Live dashboard streaming and APIs

## Latest Development (March 2026)

Recent updates focused on runtime reliability, camera handling, and dashboard clarity:

- Added per-camera enable/disable support in `configs/cameras.yaml` using `enabled: true|false`.
- Runtime now starts only enabled cameras in `main.py` and `supervisor.py`.
- Dashboard config and camera APIs now expose only enabled cameras.
- Video feed endpoint now fails fast with a clear 503 when no frame is available instead of hanging indefinitely.
- Camera ingestion improved for macOS:
	- AVFoundation-first open strategy
	- Warmup read validation before accepting a camera
	- Camera source claim locking to avoid duplicate index conflicts across workers

## Architecture Overview

SentinelAI pipeline flow:

1. Ingestion
2. Detection
3. Tracking
4. Event Engine
5. Dashboard + API + WebSocket

Key modules:

- Ingestion: `src/ingestion/camera_ingestion.py`
- Detection: `src/detection/person_detector.py`
- Tracking: `src/tracking/tracker.py`, `src/tracking/track_manager.py`
- Events: `src/events/event_engine.py`, `src/events/`
- Dashboard server: `src/dashboard/server.py`
- API routes: `src/dashboard/routes.py`
- WebSocket manager: `src/dashboard/ws_manager.py`
- Shared config: `src/core/config.py`, `configs/cameras.yaml`

Runtime entrypoints:

- Full system (recommended): `main.py`
- Camera worker: `camera_worker.py`
- Supervisor mode: `supervisor.py`
- Dashboard-only server: `python -m src.dashboard.server`

## Features

- Multi-camera config via YAML
- Real-time person detection using YOLOv8
- Multi-object tracking and track lifecycle management
- Event rules:
	- person_count
	- loitering
	- zone_intrusion
	- crowd_formation
	- unusual_motion
	- abandoned_object
- Live MJPEG video feed endpoint per camera
- Live event/status updates over WebSocket
- Dashboard views for camera health, feed, and event timeline
- In-memory event acknowledgements and stats APIs

## Project Structure

Core top-level files:

- `main.py`
- `camera_worker.py`
- `supervisor.py`
- `requirements.txt`
- `configs/cameras.yaml`

Source packages:

- `src/ingestion/`
- `src/detection/`
- `src/tracking/`
- `src/events/`
- `src/dashboard/`
- `src/core/`

Tests:

- `tests/`

## Prerequisites

- Python 3.10+ (3.11 recommended)
- macOS/Linux/Windows with OpenCV-compatible camera access
- Webcam(s) connected and permitted by OS privacy settings

Notes:

- On macOS, ensure Terminal/VS Code has Camera permission.
- YOLO model file `yolov8n.pt` is expected in repo root by default.

## Installation

From repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install fastapi uvicorn
```

Why extra install for FastAPI/Uvicorn:

- The dashboard server depends on FastAPI/Uvicorn.
- If your environment already has them, the extra command is harmless.

## Configuration

Main config file: `configs/cameras.yaml`

Camera section example:

```yaml
cameras:
	mac:
		source: 0
		type: builtin
		enabled: true
	sony:
		source: 1
		type: usb
		enabled: false
```

Important fields:

- `source`: camera index used by OpenCV
- `enabled`: whether this camera should be started by runtime
- `pipeline.detection_interval`: dynamic detection cadence limits
- `events.*`: thresholds/cooldowns for event rules
- `zones.*`: polygons used by zone-based rules

## How To Run

### 1. Full system (camera pipelines + dashboard)

Use this for actual feed + events:

```bash
python main.py
```

Open dashboard:

`http://127.0.0.1:8000`

### 2. Dashboard-only mode

Useful for frontend/API checks only:

```bash
python -m src.dashboard.server
```

Important:

- Dashboard-only mode does **not** run camera pipelines.
- You will not get live frames/events unless `main.py` is running.

### 3. Supervisor mode

Starts one worker per enabled camera and restarts stale/dead workers:

```bash
python supervisor.py
```

## How To Verify It Is Working

After starting `python main.py`:

1. Dashboard top bar should show at least one active camera.
2. Camera feed should leave "Connecting" state.
3. Event timeline should start receiving periodic `person_count` entries.

Quick API checks:

- `GET /api/health`
- `GET /api/stats`
- `GET /api/cameras`
- `GET /api/events?limit=20`

## API Summary

Configuration and health:

- `GET /api/config`
- `GET /api/health`
- `GET /api/status`
- `GET /api/stats`

Cameras and feed:

- `GET /api/cameras`
- `GET /api/video_feed/{camera_id}`

Events:

- `GET /api/events`
- `GET /api/events/timeline`
- `GET /api/events/{event_id}`
- `POST /api/events/{event_id}/acknowledge`
- `POST /api/events/acknowledge_all`
- `DELETE /api/events`

WebSocket:

- `WS /ws`

## Troubleshooting

### Dashboard shows "Connecting" forever

- Ensure you started `python main.py` (not only dashboard server).
- Check camera enabled flags in `configs/cameras.yaml`.
- Confirm `/api/cameras` reports active camera(s).

### Camera LED is on but no feed

- Another process may be holding the device.
- Camera index may be wrong (`source` in config).
- macOS privacy permissions may block frame access.

### Repeated camera restart logs

- Disable unavailable devices using `enabled: false`.
- Keep only currently connected/valid camera entries enabled.

### Port 8000 already in use

- Stop the existing process, then restart SentinelAI.

## Testing

Run tests from repository root:

```bash
pytest -q
```

## Development Notes

- This project is in active development.
- Current focus is runtime stability, observability, and clean operator UX.
- Next improvements can include persistent event storage, auth, and deployment packaging.
