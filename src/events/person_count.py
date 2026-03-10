from src.events.base_event import BaseEventRule
from src.events.models import Event


class PersonCountRule(BaseEventRule):
    """Emits periodic person count events.

    Reports the number of people currently being tracked.
    Emits at most once every `interval` seconds to avoid flooding.
    """

    name = "person_count"

    def __init__(self, interval=5.0):
        self.interval = interval
        self.last_emitted = 0.0

    def evaluate(self, tracks, frame_data, track_manager):
        now = frame_data.timestamp

        if now - self.last_emitted < self.interval:
            return []

        count = len(tracks)
        self.last_emitted = now

        return [
            Event(
                event_type="person_count",
                camera_id=frame_data.camera_id,
                timestamp=now,
                severity="info",
                description=f"{count} person(s) detected",
                track_ids=[t.track_id for t in tracks],
                metadata={"count": count},
            )
        ]
