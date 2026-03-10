from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class Event:
    """Represents a detected event in the surveillance system."""

    event_type: str
    camera_id: str
    timestamp: float
    severity: str            # "info", "warning", "critical"
    description: str
    track_ids: list = field(default_factory=list)
    zone_name: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def now():
        return time.time()
