from deep_sort_realtime.deepsort_tracker import DeepSort


class SingleCameraTracker:
    def __init__(self):
        self.tracker = DeepSort(
            max_age=30,
            n_init=3,
            max_cosine_distance=0.2,
            nn_budget=None,
        )

    def update(self, detections: list, frame):
        """
        detections: list of dicts with keys [bbox, confidence, class]
        frame: numpy ndarray
        """

        ds_detections = []
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            w = x2 - x1
            h = y2 - y1
            ds_detections.append(
                ([x1, y1, w, h], det["confidence"], det["class"])
            )

        tracks = self.tracker.update_tracks(ds_detections, frame=frame)

        results = []
        for track in tracks:
            if not track.is_confirmed():
                continue

            l, t, r, b = track.to_ltrb()
            results.append({
                "track_id": track.track_id,
                "bbox": (int(l), int(t), int(r), int(b)),
                "class": "person",
            })

        return results