import pytest
import time
from unittest.mock import MagicMock

from src.core.models import Detection, Track
from src.tracking.track_manager import TrackManager


class TestTrackManager:
    """Tests for TrackManager lifecycle logic."""

    def setup_method(self):
        self.manager = TrackManager("test_cam")

    def test_new_track_starts(self):
        tracks = [
            Track(track_id=1, bbox=(10, 10, 50, 50), cls="person", last_seen=time.time()),
        ]
        self.manager.update(tracks)

        assert 1 in self.manager.active
        assert self.manager.active[1]["camera_id"] == "test_cam"
        assert self.manager.active[1]["frames"] == 1

    def test_existing_track_updates(self):
        track = Track(track_id=1, bbox=(10, 10, 50, 50), cls="person", last_seen=time.time())

        self.manager.update([track])
        self.manager.update([track])
        self.manager.update([track])

        assert self.manager.active[1]["frames"] == 3
        assert len(self.manager.active[1]["bboxes"]) == 3

    def test_track_ends_when_not_seen(self):
        track = Track(track_id=1, bbox=(10, 10, 50, 50), cls="person", last_seen=time.time())

        self.manager.update([track])
        assert 1 in self.manager.active

        # Empty update — track no longer seen
        self.manager.update([])

        assert 1 not in self.manager.active
        assert 1 in self.manager.completed
        assert "duration" in self.manager.completed[1]

    def test_multiple_tracks(self):
        tracks = [
            Track(track_id=1, bbox=(10, 10, 50, 50), cls="person", last_seen=time.time()),
            Track(track_id=2, bbox=(100, 100, 150, 150), cls="person", last_seen=time.time()),
        ]
        self.manager.update(tracks)

        assert 1 in self.manager.active
        assert 2 in self.manager.active

    def test_partial_track_end(self):
        tracks = [
            Track(track_id=1, bbox=(10, 10, 50, 50), cls="person", last_seen=time.time()),
            Track(track_id=2, bbox=(100, 100, 150, 150), cls="person", last_seen=time.time()),
        ]
        self.manager.update(tracks)

        # Only track 1 continues
        self.manager.update([tracks[0]])

        assert 1 in self.manager.active
        assert 2 in self.manager.completed
