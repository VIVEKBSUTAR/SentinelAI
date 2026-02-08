import time


class TrackManager:
    def __init__(self, camera_id):
        self.camera_id = camera_id
        self.active = {}
        self.completed = {}

    def update(self, tracks):
        now = time.time()
        seen = set()

        for t in tracks:
            seen.add(t.track_id)

            if t.track_id not in self.active:
                self.active[t.track_id] = {
                    "track_id": t.track_id,
                    "camera_id": self.camera_id,
                    "start_time": now,
                    "last_seen": now,
                    "frames": 1,
                    "bboxes": [t.bbox],
                }
                print(f"[TRACK START] id={t.track_id}")

            else:
                tr = self.active[t.track_id]
                tr["last_seen"] = now
                tr["frames"] += 1
                tr["bboxes"].append(t.bbox)

        ended = [tid for tid in self.active if tid not in seen]

        for tid in ended:
            tr = self.active.pop(tid)
            tr["end_time"] = now
            tr["duration"] = now - tr["start_time"]
            self.completed[tid] = tr
            print(f"[TRACK END] id={tid} frames={tr['frames']}")
