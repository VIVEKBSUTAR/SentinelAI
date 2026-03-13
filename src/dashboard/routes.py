import time
from collections import deque
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
import json
import cv2

from src.core.config import load_config

router = APIRouter()

# In-memory stores for dashboard data
RECENT_EVENTS = []
PIPELINE_STATUS = {}
SYSTEM_START_TIME = time.time()

# Shared frame buffer — main.py pushes frames here (thread-safe deque)
# Key: camera_id, Value: latest JPEG-encoded frame bytes
FRAME_BUFFERS = {}


@router.get("/api/config")
async def get_config():
    """Return the currently loaded configuration (camera list, zones)."""
    return load_config()


@router.get("/api/events")
async def get_events(limit: int = 50):
    """Get recent events for dashboard initialization."""
    return JSONResponse(content=[e for e in RECENT_EVENTS[-limit:]])


@router.get("/api/status")
async def get_status():
    """Get overall system and camera status."""
    return JSONResponse(content=PIPELINE_STATUS)


@router.get("/api/stats")
async def get_stats():
    """Aggregated statistics for the stat cards."""
    config = load_config()
    total_cameras = len(config.get("cameras", {}))
    active_cameras = sum(
        1 for cam in (PIPELINE_STATUS.get("cameras") or {}).values()
        if cam.get("active")
    )

    # Event breakdown by severity
    severity_counts = {"info": 0, "warning": 0, "critical": 0}
    type_counts = {}
    for e in RECENT_EVENTS:
        sev = e.get("severity", "info")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        etype = e.get("event_type", "unknown")
        type_counts[etype] = type_counts.get(etype, 0) + 1

    # Latest person count from most recent person_count event
    person_count = 0
    for e in reversed(RECENT_EVENTS):
        if e.get("event_type") == "person_count":
            person_count = e.get("metadata", {}).get("count", 0)
            break

    # Average FPS across active cameras
    fps_values = [
        cam.get("fps", 0)
        for cam in (PIPELINE_STATUS.get("cameras") or {}).values()
        if cam.get("active")
    ]
    avg_fps = sum(fps_values) / len(fps_values) if fps_values else 0

    return JSONResponse(content={
        "total_cameras": total_cameras,
        "active_cameras": active_cameras,
        "person_count": person_count,
        "total_events": len(RECENT_EVENTS),
        "severity_counts": severity_counts,
        "type_counts": type_counts,
        "avg_fps": round(avg_fps, 1),
        "uptime_seconds": round(time.time() - SYSTEM_START_TIME),
    })


@router.get("/api/events/timeline")
async def get_events_timeline(cursor: int = 0, limit: int = 30):
    """Cursor-based paginated events for infinite scroll."""
    # cursor = index from the end (0 = most recent)
    total = len(RECENT_EVENTS)
    start = max(0, total - cursor - limit)
    end = max(0, total - cursor)
    page = RECENT_EVENTS[start:end]
    page.reverse()  # newest first

    return JSONResponse(content={
        "events": page,
        "next_cursor": cursor + limit if start > 0 else None,
        "total": total,
    })


def generate_mjpeg(camera_id: str):
    """Generator that yields MJPEG frames for streaming at ~15fps."""
    while True:
        frame_bytes = FRAME_BUFFERS.get(camera_id)
        if frame_bytes is not None:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame_bytes
                + b"\r\n"
            )
            time.sleep(1 / 15)  # Cap at ~15fps to reduce bandwidth
        else:
            time.sleep(0.2)  # Wait for first frame


@router.get("/api/video_feed/{camera_id}")
async def video_feed(camera_id: str):
    """MJPEG stream for a specific camera."""
    return StreamingResponse(
        generate_mjpeg(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
