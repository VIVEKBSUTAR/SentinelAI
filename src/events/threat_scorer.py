"""Per-track threat scoring with time-based decay.

Each event type contributes points to a track's threat score.
When the score crosses defined thresholds, the engine can emit
escalation events and trigger system-wide responses like resolution upgrades.
"""

import time
from src.core.logger import setup_logger

log = setup_logger("threat_scorer")

# Points awarded per event type
EVENT_POINTS = {
    "person_count": 0,
    "loitering": 2,
    "zone_intrusion": 5,
    "unusual_motion": 3,
    "crowd_formation": 3,
    "abandoned_object": 4,
}

# Threat levels and their thresholds
THREAT_LEVELS = [
    (5, "elevated", "warning"),
    (10, "high", "warning"),
    (15, "critical", "critical"),
]

# Score decays by this many points per second
DECAY_RATE = 0.05  # 1 point per 20 seconds


class ThreatScorer:
    """Maintains a threat score per tracked person.

    Usage:
        scorer = ThreatScorer()
        # Call when an event fires for a track
        escalation = scorer.record_event(track_id, event_type, timestamp)
        if escalation:
            # emit escalation event
        # Call periodically to decay scores
        scorer.decay(current_time)
    """

    def __init__(self):
        # track_id → {"score": float, "last_update": float,
        #              "level": str, "events": [str]}
        self._scores: dict[int, dict] = {}

    def record_event(self, track_id: int, event_type: str, timestamp: float) -> dict | None:
        """Record an event for a track and return an escalation dict if the
        threat level increased, or None otherwise.

        Returns
        -------
        dict or None
            {"track_id": int, "score": float, "level": str, "severity": str,
             "events": [str]} if the level escalated, else None.
        """
        points = EVENT_POINTS.get(event_type, 1)
        if points == 0:
            return None

        if track_id not in self._scores:
            self._scores[track_id] = {
                "score": 0.0,
                "last_update": timestamp,
                "level": "normal",
                "events": [],
            }

        entry = self._scores[track_id]

        # Apply decay since last update
        elapsed = max(0, timestamp - entry["last_update"])
        entry["score"] = max(0, entry["score"] - elapsed * DECAY_RATE)
        entry["last_update"] = timestamp

        # Add points
        entry["score"] += points
        if event_type not in entry["events"]:
            entry["events"].append(event_type)

        # Check for level escalation
        old_level = entry["level"]
        new_level = "normal"
        new_severity = "info"

        for threshold, level, severity in THREAT_LEVELS:
            if entry["score"] >= threshold:
                new_level = level
                new_severity = severity

        entry["level"] = new_level

        if new_level != old_level and new_level != "normal":
            log.info(
                f"Threat escalation: track {track_id} → {new_level} "
                f"(score={entry['score']:.1f}, events={entry['events']})"
            )
            return {
                "track_id": track_id,
                "score": round(entry["score"], 1),
                "level": new_level,
                "severity": new_severity,
                "events": list(entry["events"]),
            }

        return None

    def get_score(self, track_id: int) -> float:
        """Get the current threat score for a track."""
        entry = self._scores.get(track_id)
        return entry["score"] if entry else 0.0

    def get_level(self, track_id: int) -> str:
        """Get the current threat level for a track."""
        entry = self._scores.get(track_id)
        return entry["level"] if entry else "normal"

    def get_high_threat_tracks(self) -> set:
        """Return track IDs with elevated or higher threat level."""
        return {
            tid for tid, entry in self._scores.items()
            if entry["level"] in ("elevated", "high", "critical")
        }

    def decay(self, current_time: float):
        """Apply time-based decay to all scores and clean up zeroed entries."""
        to_remove = []
        for tid, entry in self._scores.items():
            elapsed = max(0, current_time - entry["last_update"])
            entry["score"] = max(0, entry["score"] - elapsed * DECAY_RATE)
            entry["last_update"] = current_time

            # Update level after decay
            new_level = "normal"
            for threshold, level, _ in THREAT_LEVELS:
                if entry["score"] >= threshold:
                    new_level = level
            entry["level"] = new_level

            if entry["score"] <= 0:
                to_remove.append(tid)

        for tid in to_remove:
            del self._scores[tid]

    def remove_track(self, track_id: int):
        """Remove a track from scoring (when it ends)."""
        self._scores.pop(track_id, None)
