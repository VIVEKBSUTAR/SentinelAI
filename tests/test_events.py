import pytest
import time
from unittest.mock import MagicMock
from dataclasses import dataclass

from src.core.models import FrameData, Track
from src.events.models import Event
from src.events.person_count import PersonCountRule
from src.events.loitering import LoiteringRule
from src.events.zone_intrusion import ZoneIntrusionRule, _point_in_polygon
from src.events.crowd_formation import CrowdFormationRule
from src.events.unusual_motion import UnusualMotionRule
from src.events.abandoned_object import AbandonedObjectRule
from src.events.event_engine import EventEngine
from src.tracking.track_manager import TrackManager


def make_frame(camera_id="test_cam", frame_id=1, ts=None):
    """Helper to create a FrameData for testing."""
    return FrameData(
        camera_id=camera_id,
        frame_id=frame_id,
        timestamp=ts or time.time(),
        frame=None,
        width=640,
        height=480,
    )


def make_track(track_id, bbox=(100, 100, 200, 200)):
    return Track(track_id=track_id, bbox=bbox, cls="person", last_seen=time.time())


# --- Event Model Tests ---

class TestEventModel:
    def test_event_creation(self):
        e = Event(
            event_type="test",
            camera_id="cam1",
            timestamp=123.0,
            severity="info",
            description="test event",
        )
        assert e.event_type == "test"
        assert e.track_ids == []
        assert e.metadata == {}

    def test_event_with_metadata(self):
        e = Event(
            event_type="test",
            camera_id="cam1",
            timestamp=123.0,
            severity="warning",
            description="test",
            metadata={"count": 5},
        )
        assert e.metadata["count"] == 5


# --- PersonCountRule Tests ---

class TestPersonCountRule:
    def test_emits_count(self):
        rule = PersonCountRule(interval=0)  # no rate limiting
        tracks = [make_track(1), make_track(2)]
        frame = make_frame()
        manager = TrackManager("test")

        events = rule.evaluate(tracks, frame, manager)
        assert len(events) == 1
        assert events[0].event_type == "person_count"
        assert events[0].metadata["count"] == 2

    def test_rate_limited(self):
        rule = PersonCountRule(interval=10.0)
        tracks = [make_track(1)]
        frame = make_frame()
        manager = TrackManager("test")

        events1 = rule.evaluate(tracks, frame, manager)
        assert len(events1) == 1

        # Second call immediately — should be rate limited
        events2 = rule.evaluate(tracks, frame, manager)
        assert len(events2) == 0

    def test_zero_people(self):
        rule = PersonCountRule(interval=0)
        frame = make_frame()
        manager = TrackManager("test")

        events = rule.evaluate([], frame, manager)
        assert len(events) == 1
        assert events[0].metadata["count"] == 0


# --- LoiteringRule Tests ---

class TestLoiteringRule:
    def test_no_alert_below_threshold(self):
        rule = LoiteringRule(duration_threshold=30.0, distance_threshold=100.0)
        manager = TrackManager("test")
        manager.active[1] = {
            "track_id": 1,
            "start_time": time.time() - 10,  # only 10 seconds
            "bboxes": [(100, 100, 200, 200), (105, 105, 205, 205)],
        }

        frame = make_frame()
        events = rule.evaluate([], frame, manager)
        assert len(events) == 0

    def test_alert_when_loitering(self):
        rule = LoiteringRule(duration_threshold=5.0, distance_threshold=100.0)
        manager = TrackManager("test")
        manager.active[1] = {
            "track_id": 1,
            "start_time": time.time() - 60,  # 60 seconds
            "bboxes": [(100, 100, 200, 200), (105, 105, 205, 205)],  # minimal movement
        }

        frame = make_frame()
        events = rule.evaluate([], frame, manager)
        assert len(events) == 1
        assert events[0].event_type == "loitering"
        assert events[0].severity == "warning"

    def test_no_duplicate_alert(self):
        rule = LoiteringRule(duration_threshold=5.0, distance_threshold=100.0)
        manager = TrackManager("test")
        manager.active[1] = {
            "track_id": 1,
            "start_time": time.time() - 60,
            "bboxes": [(100, 100, 200, 200), (105, 105, 205, 205)],
        }

        frame = make_frame()
        events1 = rule.evaluate([], frame, manager)
        assert len(events1) == 1

        events2 = rule.evaluate([], frame, manager)
        assert len(events2) == 0  # already alerted


# --- ZoneIntrusionRule Tests ---

class TestPointInPolygon:
    def test_inside(self):
        polygon = [[0, 0], [100, 0], [100, 100], [0, 100]]
        assert _point_in_polygon(50, 50, polygon) is True

    def test_outside(self):
        polygon = [[0, 0], [100, 0], [100, 100], [0, 100]]
        assert _point_in_polygon(150, 150, polygon) is False

    def test_on_edge(self):
        polygon = [[0, 0], [100, 0], [100, 100], [0, 100]]
        # Point on the edge — ray-casting may vary, just ensure no crash
        result = _point_in_polygon(0, 50, polygon)
        assert isinstance(result, bool)


class TestZoneIntrusionRule:
    def test_intrusion_detected(self):
        zones = {
            "restricted": {
                "camera": "test_cam",
                "polygon": [[0, 0], [200, 0], [200, 200], [0, 200]],
                "type": "restricted",
            }
        }
        rule = ZoneIntrusionRule(zones_config=zones)
        track = make_track(1, bbox=(50, 50, 150, 150))  # centroid at (100, 100)
        frame = make_frame()

        events = rule.evaluate([track], frame, TrackManager("test"))
        assert len(events) == 1
        assert events[0].event_type == "zone_intrusion"
        assert events[0].severity == "critical"

    def test_no_intrusion_outside_zone(self):
        zones = {
            "restricted": {
                "camera": "test_cam",
                "polygon": [[0, 0], [50, 0], [50, 50], [0, 50]],
                "type": "restricted",
            }
        }
        rule = ZoneIntrusionRule(zones_config=zones)
        track = make_track(1, bbox=(200, 200, 300, 300))  # centroid at (250, 250)
        frame = make_frame()

        events = rule.evaluate([track], frame, TrackManager("test"))
        assert len(events) == 0

    def test_wrong_camera_ignored(self):
        zones = {
            "restricted": {
                "camera": "other_cam",
                "polygon": [[0, 0], [200, 0], [200, 200], [0, 200]],
                "type": "restricted",
            }
        }
        rule = ZoneIntrusionRule(zones_config=zones)
        track = make_track(1, bbox=(50, 50, 150, 150))
        frame = make_frame(camera_id="test_cam")

        events = rule.evaluate([track], frame, TrackManager("test"))
        assert len(events) == 0


# --- CrowdFormationRule Tests ---

class TestCrowdFormationRule:
    def test_crowd_detected(self):
        rule = CrowdFormationRule(count_threshold=3, cooldown=0)
        tracks = [make_track(i) for i in range(5)]
        frame = make_frame()

        events = rule.evaluate(tracks, frame, TrackManager("test"))
        assert len(events) == 1
        assert events[0].event_type == "crowd_formation"

    def test_no_crowd_below_threshold(self):
        rule = CrowdFormationRule(count_threshold=5, cooldown=0)
        tracks = [make_track(i) for i in range(3)]
        frame = make_frame()

        events = rule.evaluate(tracks, frame, TrackManager("test"))
        assert len(events) == 0


# --- EventEngine Tests ---

class TestEventEngine:
    def test_engine_initializes_all_rules(self):
        engine = EventEngine(config={}, eval_interval=1)
        assert len(engine.rules) == 6

    def test_engine_evaluates_on_interval(self):
        engine = EventEngine(config={}, eval_interval=3)
        tracks = [make_track(1)]
        manager = TrackManager("test")

        # frame_id=1 — not on interval 3
        frame1 = make_frame(frame_id=1)
        events1 = engine.evaluate(tracks, frame1, manager)
        assert events1 == []

        # frame_id=3 — on interval
        frame3 = make_frame(frame_id=3)
        events3 = engine.evaluate(tracks, frame3, manager)
        # Should have at least person_count event
        assert len(events3) >= 1

    def test_engine_stores_events(self):
        engine = EventEngine(config={}, eval_interval=1)
        tracks = [make_track(1)]
        manager = TrackManager("test")
        frame = make_frame(frame_id=1)

        engine.evaluate(tracks, frame, manager)
        assert len(engine.event_log) >= 1

    def test_get_event_counts(self):
        engine = EventEngine(config={}, eval_interval=1)
        tracks = [make_track(1)]
        manager = TrackManager("test")
        frame = make_frame(frame_id=1)

        engine.evaluate(tracks, frame, manager)
        counts = engine.get_event_counts()
        assert "person_count" in counts
