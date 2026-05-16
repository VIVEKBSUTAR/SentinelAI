import time
from threading import Lock


class DashboardState:
    """Thread-safe in-memory state backing dashboard API and stream endpoints."""

    def __init__(self):
        self._lock = Lock()
        self._events = []
        self._pipeline_status = {"cameras": {}}
        self._frame_buffers = {}
        self._camera_person_counts: dict = {}   # camera_id → person count
        self._camera_suspicious: dict  = {}     # camera_id → suspicious track count
        self._camera_person_ids: dict = {}      # camera_id → set of person IDs
        self._camera_resolution: dict = {}      # camera_id → "normal" | "enhanced"
        self.system_start_time = time.time()

    # ── Events ───────────────────────────────────────────────────────────────

    def add_event(self, event_dict, max_events=200):
        with self._lock:
            # Assign a numeric ID if not already set
            if "id" not in event_dict:
                event_dict = dict(event_dict)
                event_dict["id"] = len(self._events)
            event_dict.setdefault("acknowledged", False)
            self._events.append(event_dict)
            if len(self._events) > max_events:
                self._events.pop(0)

    def get_recent_events(self, limit=50, severity=None, event_type=None, camera_id=None):
        with self._lock:
            events = list(self._events)
        if severity:
            events = [e for e in events if e.get("severity") == severity]
        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]
        if camera_id:
            events = [e for e in events if e.get("camera_id") == camera_id]
        return events[-limit:]

    def get_event_by_id(self, event_id: int):
        with self._lock:
            for e in self._events:
                if e.get("id") == event_id:
                    return dict(e)
        return None

    def acknowledge_event(self, event_id: int) -> bool:
        with self._lock:
            for e in self._events:
                if e.get("id") == event_id:
                    e["acknowledged"] = True
                    return True
        return False

    def acknowledge_all(self):
        with self._lock:
            for e in self._events:
                e["acknowledged"] = True

    def clear_events(self):
        with self._lock:
            self._events.clear()

    def get_event_count(self):
        with self._lock:
            return len(self._events)

    def get_event_slice(self, start, end):
        with self._lock:
            return list(self._events[start:end])

    def get_all_events(self):
        with self._lock:
            return list(self._events)

    # ── Camera status ────────────────────────────────────────────────────────

    def set_camera_status(self, camera_id, active, fps,
                          person_count=0, suspicious_count=0,
                          person_ids=None, resolution_mode="normal"):
        with self._lock:
            self._pipeline_status.setdefault("cameras", {})[camera_id] = {
                "active": bool(active),
                "fps": float(fps),
                "person_count": int(person_count),
                "suspicious_count": int(suspicious_count),
                "resolution_mode": resolution_mode,
            }
            self._camera_person_counts[camera_id] = int(person_count)
            self._camera_suspicious[camera_id] = int(suspicious_count)
            self._camera_person_ids[camera_id] = set(person_ids or [])
            self._camera_resolution[camera_id] = resolution_mode

    def get_pipeline_status(self):
        with self._lock:
            cameras = {k: dict(v) for k, v in
                       self._pipeline_status.get("cameras", {}).items()}
            return {"cameras": cameras}

    def get_total_person_count(self):
        """Return the number of UNIQUE persons across all cameras."""
        with self._lock:
            all_ids = set()
            for ids in self._camera_person_ids.values():
                all_ids.update(ids)
            return len(all_ids)

    def get_unique_person_ids(self) -> set:
        """Return the union of all active person IDs across cameras."""
        with self._lock:
            all_ids = set()
            for ids in self._camera_person_ids.values():
                all_ids.update(ids)
            return all_ids

    # ── Frame buffers ────────────────────────────────────────────────────────

    def set_frame(self, camera_id, frame_bytes):
        with self._lock:
            self._frame_buffers[camera_id] = frame_bytes

    def get_frame(self, camera_id):
        with self._lock:
            return self._frame_buffers.get(camera_id)


dashboard_state = DashboardState()
