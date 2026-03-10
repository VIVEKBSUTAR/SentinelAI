from src.core.logger import setup_logger
from src.events.models import Event
from src.events.person_count import PersonCountRule
from src.events.loitering import LoiteringRule
from src.events.zone_intrusion import ZoneIntrusionRule
from src.events.crowd_formation import CrowdFormationRule
from src.events.unusual_motion import UnusualMotionRule
from src.events.abandoned_object import AbandonedObjectRule

log = setup_logger("event_engine")


class EventEngine:
    """Runs all registered event rules and collects events.

    The engine is called each frame with the current pipeline state.
    It evaluates rules at a configurable interval to reduce overhead.
    """

    def __init__(self, config=None, eval_interval=3):
        """Initialize the event engine with rules based on config.

        Args:
            config: Project config dict (from cameras.yaml).
            eval_interval: Evaluate rules every N frames.
        """
        self.eval_interval = eval_interval
        self.rules = []
        self.event_log = []

        events_cfg = (config or {}).get("events", {})
        zones_cfg = (config or {}).get("zones", {})

        # Register rules with config-driven thresholds
        self.rules.append(
            PersonCountRule(
                interval=events_cfg.get("person_count_interval", 5.0)
            )
        )
        self.rules.append(
            LoiteringRule(
                duration_threshold=events_cfg.get("loitering_duration", 30.0),
                distance_threshold=events_cfg.get("loitering_distance", 100.0),
            )
        )
        self.rules.append(
            ZoneIntrusionRule(zones_config=zones_cfg)
        )
        self.rules.append(
            CrowdFormationRule(
                count_threshold=events_cfg.get("crowd_threshold", 5),
                cooldown=events_cfg.get("crowd_cooldown", 30.0),
            )
        )
        self.rules.append(
            UnusualMotionRule(
                speed_threshold=events_cfg.get("speed_threshold", 150.0),
            )
        )
        self.rules.append(
            AbandonedObjectRule(
                max_duration=events_cfg.get("abandoned_max_duration", 10.0),
            )
        )

        log.info(
            f"EventEngine initialized with {len(self.rules)} rules: "
            f"{[r.name for r in self.rules]}"
        )

    def evaluate(self, tracks, frame_data, track_manager):
        """Run all rules and return new events.

        Should be called on every frame — internal interval
        controls how often rules actually run.
        """
        if frame_data.frame_id % self.eval_interval != 0:
            return []

        all_events = []

        for rule in self.rules:
            try:
                events = rule.evaluate(tracks, frame_data, track_manager)
                for event in events:
                    self._log_event(event)
                    all_events.append(event)
            except Exception as e:
                log.error(f"Rule '{rule.name}' failed: {e}")

        return all_events

    def _log_event(self, event):
        """Log and store the event."""
        self.event_log.append(event)

        icon = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🚨",
        }.get(event.severity, "•")

        log.info(
            f"{icon} [{event.event_type.upper()}] "
            f"camera={event.camera_id} | {event.description}"
        )

    def get_recent_events(self, n=50):
        """Return the most recent N events."""
        return self.event_log[-n:]

    def get_event_counts(self):
        """Return counts by event type."""
        counts = {}
        for event in self.event_log:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
        return counts
