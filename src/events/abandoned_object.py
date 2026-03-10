from src.events.base_event import BaseEventRule
from src.events.models import Event


class AbandonedObjectRule(BaseEventRule):
    """Detects potential abandoned objects.

    Heuristic: A completed track (person left) that was stationary
    for a very short time may indicate they dropped something.

    This is a simplified heuristic for academic demonstration.
    A production system would need separate object detection to confirm
    the presence of an object after the person leaves.

    Triggers when a completed track:
    1. Had a very short duration (person was briefly present)
    2. Showed minimal movement (stood in one spot, possibly dropped something)
    """

    name = "abandoned_object"

    def __init__(
        self,
        max_duration=10.0,
        max_displacement=80.0,
        cooldown=60.0,
    ):
        self.max_duration = max_duration
        self.max_displacement = max_displacement
        self.cooldown = cooldown
        self.processed_tracks = set()
        self.last_alerted = 0.0

    def evaluate(self, tracks, frame_data, track_manager):
        events = []
        now = frame_data.timestamp

        for track_id, info in track_manager.completed.items():
            if track_id in self.processed_tracks:
                continue

            self.processed_tracks.add(track_id)

            duration = info.get("duration", 0)
            if duration > self.max_duration or duration < 2.0:
                continue

            bboxes = info.get("bboxes", [])
            if len(bboxes) < 2:
                continue

            # Check displacement
            first = bboxes[0]
            last = bboxes[-1]
            cx1 = (first[0] + first[2]) / 2
            cy1 = (first[1] + first[3]) / 2
            cx2 = (last[0] + last[2]) / 2
            cy2 = (last[1] + last[3]) / 2

            import math
            displacement = math.sqrt((cx2 - cx1) ** 2 + (cy2 - cy1) ** 2)

            if displacement > self.max_displacement:
                continue

            if now - self.last_alerted < self.cooldown:
                continue

            self.last_alerted = now
            events.append(
                Event(
                    event_type="abandoned_object",
                    camera_id=info.get("camera_id", frame_data.camera_id),
                    timestamp=now,
                    severity="critical",
                    description=(
                        f"Potential abandoned object: person (track {track_id}) "
                        f"was stationary for {duration:.0f}s then left"
                    ),
                    track_ids=[track_id],
                    metadata={
                        "duration": round(duration, 1),
                        "displacement": round(displacement, 1),
                        "last_position": [round(cx2), round(cy2)],
                    },
                )
            )

        return events
