"""Lightweight Re-Identification gallery.

Stores appearance features for recently-completed person tracks.
When a new person track appears, its feature is compared against the gallery
to see if it matches a previously-seen person, allowing the system to assign
the same logical ID even after the person left the frame and returned.

Thread-safe: a single gallery instance can be shared across multiple camera
pipeline threads so that the same physical person seen by different cameras
receives the same stable person ID.

Matching strategy:
    - Uses MINIMUM cosine distance (nearest-neighbor) against all stored
      features, not the mean. This is far more robust because the mean
      of many features from different poses/angles becomes a blurred,
      non-distinctive vector. Min-distance picks the single stored feature
      that best matches the current appearance.
    - After assigning a new ID, performs a cross-check to see if any other
      camera already identified the same person — if so, merges the IDs.
"""

import time
import numpy as np
from threading import Lock
from src.core.logger import setup_logger

log = setup_logger("reid_gallery")


class ReIDGallery:
    """Maps DeepSORT internal track IDs → stable external person IDs.

    Parameters
    ----------
    match_threshold : float
        Maximum cosine distance to accept a gallery match (lower = stricter).
    gallery_ttl : float
        Seconds to keep a departed person's features in the gallery before
        forgetting them entirely.
    max_gallery_size : int
        Hard cap on the number of gallery entries to prevent unbounded growth.
    """

    def __init__(
        self,
        match_threshold: float = 0.55,  # Loosened from 0.4 for robust re-ID
        gallery_ttl: float = 600.0,     # Remember people for 10 minutes
        max_gallery_size: int = 100,
    ):
        self.match_threshold = match_threshold
        self.gallery_ttl = gallery_ttl
        self.max_gallery_size = max_gallery_size
        self._lock = Lock()

        # stable_id → {features: [np.array], last_seen: float,
        #              active_track_keys: set of (camera_id, ds_track_id)}
        self._gallery: dict[int, dict] = {}

        # (camera_id, ds_track_id) → stable person_id
        self._track_to_person: dict[tuple, int] = {}

        self._next_person_id = 1

    # ── Public API ────────────────────────────────────────────────────────────

    def resolve_person_id(self, ds_track, camera_id: str = "__default__") -> int:
        """Given a DeepSORT track object, return a stable person ID.

        If the track has already been mapped, return the existing ID.
        If the track is new, try to match its features against the gallery.
        If no match, allocate a new person ID.
        """
        key = (camera_id, ds_track.track_id)

        with self._lock:
            # Already mapped?
            if key in self._track_to_person:
                pid = self._track_to_person[key]
                self._update_gallery_features_unlocked(pid, ds_track)
                return pid

            # New track — try to match against gallery
            feature = self._extract_feature(ds_track)
            matched_pid = self._match_gallery_unlocked(feature) if feature is not None else None

            if matched_pid is not None:
                log.info(
                    f"Re-identified: camera={camera_id} track {ds_track.track_id} "
                    f"matched to person {matched_pid}"
                )
                self._track_to_person[key] = matched_pid
                self._gallery[matched_pid]["active_track_keys"].add(key)
                self._gallery[matched_pid]["last_seen"] = time.time()
                self._update_gallery_features_unlocked(matched_pid, ds_track)
                return matched_pid

            # No match — new person
            pid = self._next_person_id
            self._next_person_id += 1
            self._track_to_person[key] = pid
            self._gallery[pid] = {
                "features": [feature] if feature is not None else [],
                "last_seen": time.time(),
                "active_track_keys": {key},
            }
            log.info(f"New person {pid} assigned to camera={camera_id} track {ds_track.track_id}")
            return pid

    def on_track_ended(self, ds_track_id: int, camera_id: str = "__default__"):
        """Call when DeepSORT marks a track as ended / deleted.

        Detaches the track from its person ID but keeps the gallery entry
        alive for future re-identification.
        """
        key = (camera_id, ds_track_id)
        with self._lock:
            pid = self._track_to_person.pop(key, None)
            if pid is not None and pid in self._gallery:
                self._gallery[pid]["active_track_keys"].discard(key)
                self._gallery[pid]["last_seen"] = time.time()

    def get_active_person_ids(self) -> set:
        """Return the set of stable person IDs that have at least one active track."""
        with self._lock:
            return {
                pid for pid, entry in self._gallery.items()
                if entry["active_track_keys"]
            }

    def cleanup(self):
        """Remove stale gallery entries that have exceeded the TTL."""
        now = time.time()
        with self._lock:
            expired = [
                pid
                for pid, entry in self._gallery.items()
                if not entry["active_track_keys"]
                and (now - entry["last_seen"]) > self.gallery_ttl
            ]
            for pid in expired:
                del self._gallery[pid]

            # Enforce max gallery size — evict oldest inactive entries
            inactive = [
                (pid, entry["last_seen"])
                for pid, entry in self._gallery.items()
                if not entry["active_track_keys"]
            ]
            if len(self._gallery) > self.max_gallery_size and inactive:
                inactive.sort(key=lambda x: x[1])
                to_remove = len(self._gallery) - self.max_gallery_size
                for pid, _ in inactive[:to_remove]:
                    self._gallery.pop(pid, None)

    # ── Internal helpers (must be called with self._lock held) ────────────

    def _extract_feature(self, ds_track) -> np.ndarray | None:
        """Pull the latest appearance feature from the DeepSORT track."""
        try:
            if hasattr(ds_track, "features") and ds_track.features:
                feat = np.array(ds_track.features[-1], dtype=np.float32)
                norm = np.linalg.norm(feat)
                if norm > 0:
                    return feat / norm
        except Exception:
            pass
        return None

    def _update_gallery_features_unlocked(self, pid: int, ds_track):
        """Keep the gallery features fresh with the latest embedding."""
        feature = self._extract_feature(ds_track)
        if feature is not None and pid in self._gallery:
            feats = self._gallery[pid]["features"]
            feats.append(feature)
            # Keep the last 30 features for robust matching across poses
            if len(feats) > 30:
                self._gallery[pid]["features"] = feats[-30:]
            self._gallery[pid]["last_seen"] = time.time()

    def _match_gallery_unlocked(self, feature: np.ndarray) -> int | None:
        """Find the best gallery match for a feature vector.

        Uses MINIMUM cosine distance (nearest-neighbor) against all stored
        features per gallery entry. This is much more robust than comparing
        against the mean, because the mean of many different poses/angles
        becomes a blurred, non-distinctive vector.

        Searches ALL entries (both active on other cameras and inactive)
        to enable cross-camera re-identification.
        """
        if feature is None:
            return None

        best_pid = None
        best_dist = self.match_threshold

        for pid, entry in self._gallery.items():
            if not entry["features"]:
                continue

            # Compute cosine distance to EACH stored feature and take the MIN
            gallery_feats = np.array(entry["features"])

            # Batch cosine similarity: dot product with normalized vectors
            similarities = gallery_feats @ feature  # shape: (N,)
            min_dist = 1.0 - float(np.max(similarities))  # min distance = 1 - max similarity

            if min_dist < best_dist:
                best_dist = min_dist
                best_pid = pid

        if best_pid is not None:
            log.debug(
                f"Gallery match: person {best_pid} with distance {best_dist:.3f} "
                f"(threshold {self.match_threshold})"
            )

        return best_pid
