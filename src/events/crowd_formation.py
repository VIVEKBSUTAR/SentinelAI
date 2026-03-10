from src.events.base_event import BaseEventRule
from src.events.models import Event


class CrowdFormationRule(BaseEventRule):
    """Detects when too many people gather in the scene.

    Triggers when the number of simultaneously tracked people exceeds
    the threshold. Rate-limited to avoid repeated alerts.
    """

    name = "crowd_formation"

    def __init__(self, count_threshold=5, cooldown=30.0):
        self.count_threshold = count_threshold
        self.cooldown = cooldown
        self.last_alerted = 0.0

    def evaluate(self, tracks, frame_data, track_manager):
        now = frame_data.timestamp
        count = len(tracks)

        if count < self.count_threshold:
            return []

        if now - self.last_alerted < self.cooldown:
            return []

        self.last_alerted = now

        return [
            Event(
                event_type="crowd_formation",
                camera_id=frame_data.camera_id,
                timestamp=now,
                severity="warning",
                description=(
                    f"Crowd detected: {count} people "
                    f"(threshold: {self.count_threshold})"
                ),
                track_ids=[t.track_id for t in tracks],
                metadata={
                    "count": count,
                    "threshold": self.count_threshold,
                },
            )
        ]
