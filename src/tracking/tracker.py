from deep_sort_realtime.deepsort_tracker import DeepSort
from src.core.models import Track
import time


class Tracker:
    def __init__(self):
        self.ds = DeepSort(
            max_age=45,                 # allow longer gaps between detections
            n_init=5,                   # require more confirmations
            max_cosine_distance=0.3,    # looser appearance matching for CPU
            nn_budget=None,
        )

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

        tracks = self.ds.update_tracks(ds_inputs, frame=frame)

        results = []
        now = time.time()

        for t in tracks:
            if not t.is_confirmed():
                continue

            l, t_, r, b = map(int, t.to_ltrb())
            results.append(
                Track(
                    track_id=t.track_id,
                    bbox=(l, t_, r, b),
                    cls="person",
                    last_seen=now,
                )
            )

        return results
