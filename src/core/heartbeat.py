import json
import time
from pathlib import Path


class Heartbeat:
    def __init__(self, camera_id, base_dir="runtime/heartbeats"):
        self.camera_id = camera_id
        self.path = Path(base_dir) / f"{camera_id}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def beat(self):
        data = {
            "camera_id": self.camera_id,
            "timestamp": time.time()
        }
        self.path.write_text(json.dumps(data))


class HeartbeatMonitor:
    def __init__(
        self,
        cameras,
        base_dir="runtime/heartbeats",
        timeout=10.0,
        startup_grace=5.0
    ):
        self.timeout = timeout
        self.startup_grace = startup_grace
        self.start_times = {cam: time.time() for cam in cameras}

        self.paths = {
            cam: Path(base_dir) / f"{cam}.json"
            for cam in cameras
        }

    def mark_restart(self, camera_id):
        self.start_times[camera_id] = time.time()

    def is_stale(self, camera_id):
        now = time.time()

        # Startup grace period
        if now - self.start_times[camera_id] < self.startup_grace:
            return False

        path = self.paths[camera_id]

        if not path.exists():
            return True

        try:
            data = json.loads(path.read_text())
            last = data["timestamp"]
        except Exception:
            return True

        return (now - last) > self.timeout
