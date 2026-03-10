import math
from src.events.base_event import BaseEventRule
from src.events.models import Event


class LoiteringRule(BaseEventRule):
    """Detects when a person stays in roughly the same area too long.

    A track is considered loitering if:
    1. It has been active for at least `duration_threshold` seconds.
    2. Its centroid has not moved more than `distance_threshold` pixels
       from its starting position.
    """

    name = "loitering"

    def __init__(self, duration_threshold=30.0, distance_threshold=100.0):
        self.duration_threshold = duration_threshold
        self.distance_threshold = distance_threshold
        self.alerted_tracks = set()

    def evaluate(self, tracks, frame_data, track_manager):
        events = []
        now = frame_data.timestamp

        for track_id, info in track_manager.active.items():
            # Skip if we already alerted for this track
            if track_id in self.alerted_tracks:
                continue

            duration = now - info["start_time"]
            if duration < self.duration_threshold:
                continue

            # Compare first and last bbox centroids
            if len(info["bboxes"]) < 2:
                continue

            first_bbox = info["bboxes"][0]
            last_bbox = info["bboxes"][-1]

            start_cx = (first_bbox[0] + first_bbox[2]) / 2
            start_cy = (first_bbox[1] + first_bbox[3]) / 2
            end_cx = (last_bbox[0] + last_bbox[2]) / 2
            end_cy = (last_bbox[1] + last_bbox[3]) / 2

            displacement = math.sqrt(
                (end_cx - start_cx) ** 2 + (end_cy - start_cy) ** 2
            )

            if displacement < self.distance_threshold:
                self.alerted_tracks.add(track_id)
                events.append(
                    Event(
                        event_type="loitering",
                        camera_id=frame_data.camera_id,
                        timestamp=now,
                        severity="warning",
                        description=(
                            f"Person (track {track_id}) loitering for "
                            f"{duration:.0f}s, moved only {displacement:.0f}px"
                        ),
                        track_ids=[track_id],
                        metadata={
                            "duration": round(duration, 1),
                            "displacement": round(displacement, 1),
                        },
                    )
                )

        # Cleanup: remove ended tracks from alerted set
        active_ids = set(track_manager.active.keys())
        self.alerted_tracks &= active_ids

        return events
