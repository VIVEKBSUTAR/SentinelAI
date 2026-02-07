import time


class TrackManager:
    def __init__(self, camera_id: str, inactivity_timeout: float = 2.0):
        self.camera_id = camera_id
        self.inactivity_timeout = inactivity_timeout
        self.active_tracks = {}
        self.completed_tracks = {}

    def update(self, tracked_objects: list):
        """
        tracked_objects: list of dicts with keys [track_id, bbox, class]
        """
        now = time.time()
        seen_track_ids = set()

        # Update or create tracks
        for obj in tracked_objects:
            track_id = obj["track_id"]
            seen_track_ids.add(track_id)

            if track_id not in self.active_tracks:
                # New track
                self.active_tracks[track_id] = {
                    "track_id": track_id,
                    "camera_id": self.camera_id,
                    "start_time": now,
                    "last_seen_time": now,
                    "end_time": None,
                    "frame_count": 1,
                    "bboxes": [obj["bbox"]],
                }
                print(f"[TRACK START] id={track_id} camera={self.camera_id}")
            else:
                track = self.active_tracks[track_id]
                track["last_seen_time"] = now
                track["frame_count"] += 1
                track["bboxes"].append(obj["bbox"])

        # Close inactive tracks
        to_close = []
        for track_id, track in self.active_tracks.items():
            if track_id not in seen_track_ids:
                if now - track["last_seen_time"] > self.inactivity_timeout:
                    to_close.append(track_id)

        for track_id in to_close:
            track = self.active_tracks.pop(track_id)
            track["end_time"] = now
            track["duration_seconds"] = track["end_time"] - track["start_time"]
            self.completed_tracks[track_id] = track
            print(
                f"[TRACK END] id={track_id} duration={track['duration_seconds']:.2f}s frames={track['frame_count']}"
            )

    def get_active_tracks(self):
        return self.active_tracks

    def get_completed_tracks(self):
        return self.completed_tracks
