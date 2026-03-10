import math
from src.events.base_event import BaseEventRule
from src.events.models import Event


class UnusualMotionRule(BaseEventRule):
    """Detects unusually fast movement (e.g., running).

    Estimates velocity from the last N bboxes in a track's history.
    If the average speed exceeds the threshold, an event is raised.
    """

    name = "unusual_motion"

    def __init__(self, speed_threshold=150.0, min_samples=5, cooldown=10.0):
        self.speed_threshold = speed_threshold   # pixels per second
        self.min_samples = min_samples
        self.cooldown = cooldown
        self.last_alerted = {}  # track_id -> last alert time

    def evaluate(self, tracks, frame_data, track_manager):
        events = []
        now = frame_data.timestamp

        for track_id, info in track_manager.active.items():
            bboxes = info["bboxes"]
            if len(bboxes) < self.min_samples:
                continue

            # Check cooldown
            if now - self.last_alerted.get(track_id, 0) < self.cooldown:
                continue

            # Calculate speed from recent bboxes
            recent = bboxes[-self.min_samples:]
            total_dist = 0.0

            for i in range(1, len(recent)):
                prev = recent[i - 1]
                curr = recent[i]

                prev_cx = (prev[0] + prev[2]) / 2
                prev_cy = (prev[1] + prev[3]) / 2
                curr_cx = (curr[0] + curr[2]) / 2
                curr_cy = (curr[1] + curr[3]) / 2

                total_dist += math.sqrt(
                    (curr_cx - prev_cx) ** 2 + (curr_cy - prev_cy) ** 2
                )

            duration = now - info["start_time"]
            if duration <= 0:
                continue

            # Approximate speed: pixels moved per second
            # Use frame count as time proxy (more stable than wall clock)
            frames = info["frames"]
            if frames < self.min_samples:
                continue

            # Estimate FPS from track data
            fps_estimate = frames / duration if duration > 0 else 12.0
            time_span = len(recent) / fps_estimate if fps_estimate > 0 else 1.0

            speed = total_dist / time_span if time_span > 0 else 0.0

            if speed > self.speed_threshold:
                self.last_alerted[track_id] = now
                events.append(
                    Event(
                        event_type="unusual_motion",
                        camera_id=frame_data.camera_id,
                        timestamp=now,
                        severity="warning",
                        description=(
                            f"Fast movement detected: track {track_id} "
                            f"moving at {speed:.0f} px/s"
                        ),
                        track_ids=[track_id],
                        metadata={
                            "speed_px_per_sec": round(speed, 1),
                            "threshold": self.speed_threshold,
                        },
                    )
                )

        # Cleanup stale entries
        active_ids = set(track_manager.active.keys())
        self.last_alerted = {
            k: v for k, v in self.last_alerted.items() if k in active_ids
        }

        return events
