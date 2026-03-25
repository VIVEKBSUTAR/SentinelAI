import time
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from src.core.config import load_config, get_enabled_camera_ids
from src.dashboard.state import dashboard_state

router = APIRouter()


# ── Config ────────────────────────────────────────────────────────────────────

@router.get("/api/config")
async def get_config():
    """Return the currently loaded configuration (camera list, zones)."""
    config = load_config()
    enabled_ids = set(get_enabled_camera_ids(config))
    config["cameras"] = {
        cam_id: cam_cfg
        for cam_id, cam_cfg in config.get("cameras", {}).items()
        if cam_id in enabled_ids
    }
    return config


# ── Events ────────────────────────────────────────────────────────────────────

@router.get("/api/events")
async def get_events(
    limit: int = 50,
    severity: Optional[str] = None,
    event_type: Optional[str] = None,
    camera_id: Optional[str] = None,
):
    """Get recent events with optional filters."""
    events = dashboard_state.get_recent_events(
        limit=limit,
        severity=severity,
        event_type=event_type,
        camera_id=camera_id,
    )
    return JSONResponse(content=events)


@router.get("/api/events/timeline")
async def get_events_timeline(cursor: int = 0, limit: int = 30):
    """Cursor-based paginated events for infinite scroll."""
    total = dashboard_state.get_event_count()
    start = max(0, total - cursor - limit)
    end   = max(0, total - cursor)
    page  = dashboard_state.get_event_slice(start, end)
    page.reverse()
    return JSONResponse(content={
        "events": page,
        "next_cursor": cursor + limit if start > 0 else None,
        "total": total,
    })


@router.get("/api/events/{event_id}")
async def get_event(event_id: int):
    """Retrieve a single event by its numeric ID."""
    event = dashboard_state.get_event_by_id(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return JSONResponse(content=event)


@router.post("/api/events/{event_id}/acknowledge")
async def acknowledge_event(event_id: int):
    """Mark an event as acknowledged."""
    ok = dashboard_state.acknowledge_event(event_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Event not found")
    return JSONResponse(content={"status": "acknowledged", "id": event_id})


@router.post("/api/events/acknowledge_all")
async def acknowledge_all():
    """Acknowledge every pending event."""
    dashboard_state.acknowledge_all()
    return JSONResponse(content={"status": "all_acknowledged"})


@router.delete("/api/events")
async def clear_events():
    """Clear all events from memory."""
    dashboard_state.clear_events()
    return JSONResponse(content={"status": "cleared"})


# ── Cameras ───────────────────────────────────────────────────────────────────

@router.get("/api/cameras")
async def get_cameras():
    """Return configured cameras merged with live runtime status."""
    config = load_config()
    enabled_ids = set(get_enabled_camera_ids(config))
    status = dashboard_state.get_pipeline_status()
    cameras = []
    for cam_id, cam_cfg in config.get("cameras", {}).items():
        if cam_id not in enabled_ids:
            continue
        runtime = status.get("cameras", {}).get(cam_id, {})
        cameras.append({
            "id": cam_id,
            "type": cam_cfg.get("type", "unknown"),
            "source": cam_cfg.get("source"),
            "active": runtime.get("active", False),
            "fps": runtime.get("fps", 0.0),
            "person_count": runtime.get("person_count", 0),
            "suspicious_count": runtime.get("suspicious_count", 0),
        })
    return JSONResponse(content=cameras)


# ── Status & Stats ────────────────────────────────────────────────────────────

@router.get("/api/status")
async def get_status():
    """Get per-camera pipeline status."""
    return JSONResponse(content=dashboard_state.get_pipeline_status())


@router.get("/api/stats")
async def get_stats():
    """Aggregated statistics for the stat cards."""
    config = load_config()
    enabled_ids = set(get_enabled_camera_ids(config))
    total_cameras = len(enabled_ids)
    status = dashboard_state.get_pipeline_status()
    events = dashboard_state.get_all_events()
    active_cameras = sum(
        1 for cam in (status.get("cameras") or {}).values() if cam.get("active")
    )

    severity_counts = {"info": 0, "warning": 0, "critical": 0}
    type_counts: dict = {}
    for e in events:
        sev = e.get("severity", "info")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        etype = e.get("event_type", "unknown")
        type_counts[etype] = type_counts.get(etype, 0) + 1

    # Sum person counts across active cameras
    person_count = sum(
        cam.get("person_count", 0)
        for cam in (status.get("cameras") or {}).values()
        if cam.get("active")
    )

    fps_values = [
        cam.get("fps", 0)
        for cam in (status.get("cameras") or {}).values()
        if cam.get("active")
    ]
    avg_fps = sum(fps_values) / len(fps_values) if fps_values else 0

    unacked = sum(1 for e in events if not e.get("acknowledged", False))

    return JSONResponse(content={
        "total_cameras": total_cameras,
        "active_cameras": active_cameras,
        "person_count": person_count,
        "total_events": len(events),
        "unacknowledged_events": unacked,
        "severity_counts": severity_counts,
        "type_counts": type_counts,
        "avg_fps": round(avg_fps, 1),
        "uptime_seconds": round(time.time() - dashboard_state.system_start_time),
    })


@router.get("/api/health")
async def get_health():
    """System health check — useful for readiness probes and the settings view."""
    status = dashboard_state.get_pipeline_status()
    cameras = status.get("cameras", {})
    active  = sum(1 for c in cameras.values() if c.get("active"))
    return JSONResponse(content={
        "status": "ok" if active > 0 else "degraded",
        "active_cameras": active,
        "total_cameras": len(cameras),
        "event_queue": dashboard_state.get_event_count(),
        "uptime_seconds": round(time.time() - dashboard_state.system_start_time),
        "timestamp": time.time(),
    })


# ── Video Feed ────────────────────────────────────────────────────────────────

def generate_mjpeg(camera_id: str):
    """Generator that yields MJPEG frames at ~15 fps."""
    while True:
        frame_bytes = dashboard_state.get_frame(camera_id)
        if frame_bytes is not None:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame_bytes
                + b"\r\n"
            )
            time.sleep(1 / 15)
        else:
            time.sleep(0.1)


@router.get("/api/video_feed/{camera_id}")
async def video_feed(camera_id: str):
    """MJPEG stream for a specific camera."""
    # Fail fast if there is no available frame yet so the UI can show an explicit error.
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if dashboard_state.get_frame(camera_id) is not None:
            break
        time.sleep(0.05)
    else:
        raise HTTPException(
            status_code=503,
            detail=f"No frames available for camera '{camera_id}'. Ensure pipeline is running.",
        )

    return StreamingResponse(
        generate_mjpeg(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

