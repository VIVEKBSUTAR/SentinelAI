from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json

from src.core.config import load_config

router = APIRouter()

# In-memory store for late-joining clients to get history.
# In a real deployed app, this would be a database.
# We will inject events here from the main pipeline.
RECENT_EVENTS = []
PIPELINE_STATUS = {}


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
