from deep_sort_realtime.deepsort_tracker import DeepSort
from src.core.models import Track
from src.tracking.reid_gallery import ReIDGallery
import time


class Tracker:
    def __init__(self, camera_id: str = "__default__", reid_gallery: ReIDGallery = None):
        self.camera_id = camera_id
        self.ds = DeepSort(
            max_age=60,
            n_init=5,                   # Require 5 consecutive detections to confirm
            max_cosine_distance=0.5,    # Tighter appearance matching
            nn_budget=None,
        )
        # Use shared gallery if provided, otherwise create a local one
        self.reid = reid_gallery or ReIDGallery(
            match_threshold=0.55,
            gallery_ttl=600.0,
        )
        self._prev_track_ids: set = set()

    def update(self, detections, frame):
        """
        detections: list of Detection objects
        frame: numpy ndarray
        """

        ds_inputs = []

        for d in detections:
            x1, y1, x2, y2 = d.bbox
            ds_inputs.append(
                ([x1, y1, x2 - x1, y2 - y1], d.confidence, d.cls)
            )

        raw_tracks = self.ds.update_tracks(ds_inputs, frame=frame)

        # Detect which tracks have ended since last frame
        current_ids = set()
        results = []
        now = time.time()

        for t in raw_tracks:
            if not t.is_confirmed():
                continue

            current_ids.add(t.track_id)

            # Use the ReID gallery to get a stable person ID
            stable_id = self.reid.resolve_person_id(t, camera_id=self.camera_id)

            l, t_, r, b = map(int, t.to_ltrb())
            results.append(
                Track(
                    track_id=stable_id,
                    bbox=(l, t_, r, b),
                    cls=t.get_det_class() or "unknown",
                    last_seen=now,
                )
            )

        # Notify gallery of ended tracks
        ended = self._prev_track_ids - current_ids
        for tid in ended:
            self.reid.on_track_ended(tid, camera_id=self.camera_id)

        self._prev_track_ids = current_ids

        # Periodic cleanup of stale gallery entries
        self.reid.cleanup()

        return results
