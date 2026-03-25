import time
from threading import Lock

import cv2

from src.core.models import FrameData
from src.core.config import load_config, get_camera_source
from src.core.logger import setup_logger
from src.ingestion.frame_stabilizer import FrameStabilizer

log = setup_logger("ingestion")


class CameraIngestion:
    """Reads frames from a camera device and produces FrameData objects."""

    _claimed_sources = set()
    _claim_lock = Lock()

    def __init__(self, camera_id, config=None):
        self.camera_id = camera_id
        self.config = config or load_config()
        self.source = get_camera_source(self.config, camera_id)
        self.cap = None
        self.frame_count = 0
        self._claimed_source = None

    def _claim_source(self, source: int) -> bool:
        with self._claim_lock:
            if source in self._claimed_sources:
                return False
            self._claimed_sources.add(source)
            self._claimed_source = source
            return True

    def _release_claim(self):
        with self._claim_lock:
            if self._claimed_source in self._claimed_sources:
                self._claimed_sources.remove(self._claimed_source)
            self._claimed_source = None

    def _open_source(self, source: int):
        # AVFoundation is the most reliable backend on macOS for camera capture.
        cap = cv2.VideoCapture(source, cv2.CAP_AVFOUNDATION)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            cap.release()
            return None

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Warm up camera and validate that at least one real frame can be read.
        for _ in range(20):
            ok, frame = cap.read()
            if ok and frame is not None and frame.size > 0:
                return cap
            time.sleep(0.05)

        cap.release()
        return None

        # Optional frame stabilization
        stab_cfg = self.config.get("pipeline", {}).get("stabilization", {})
        if stab_cfg.get("enabled", False):
            window = stab_cfg.get("smoothing_window", 30)
            self.stabilizer = FrameStabilizer(smoothing_window=window)
            log.info(
                f"Frame stabilization enabled for '{camera_id}' "
                f"(window={window})"
            )
        else:
            self.stabilizer = None

    def open(self):
        """Open the camera device for reading.

        Tries the configured source index first.  If that fails, scans
        indices 0-4 as a fallback so the pipeline doesn't crash when
        device numbers shift (e.g. USB camera unplugged).
        """
        preferred = int(self.source)
        if self._claim_source(preferred):
            cap = self._open_source(preferred)
            if cap is not None:
                self.cap = cap
                self.source = preferred
                log.info(f"Camera '{self.camera_id}' opened (source={self.source})")
                return
            self._release_claim()

        # Configured source failed — try alternatives
        log.warning(
            f"Configured source {self.source} failed for '{self.camera_id}'. "
            "Scanning alternative indices…"
        )

        for idx in range(5):
            if idx == preferred:
                continue  # already tried

            if not self._claim_source(idx):
                continue

            cap = self._open_source(idx)
            if cap is not None:
                self.cap = cap
                self.source = idx
                log.info(
                    f"Camera '{self.camera_id}' opened on fallback index {idx}"
                )
                return
            self._release_claim()

        raise RuntimeError(
            f"Failed to open camera '{self.camera_id}': "
            f"configured source={self.source} and indices 0-4 all failed"
        )

    def read(self):
        """Read the next frame and return a FrameData object."""
        if self.cap is None:
            raise RuntimeError("Camera not opened. Call open() first.")

        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError(f"Failed to read frame from camera '{self.camera_id}'")

        if self.stabilizer is not None:
            frame = self.stabilizer.stabilize(frame)

        self.frame_count += 1
        h, w = frame.shape[:2]

        return FrameData(
            camera_id=self.camera_id,
            frame_id=self.frame_count,
            timestamp=time.time(),
            frame=frame,
            width=w,
            height=h,
        )

    def close(self):
        """Release the camera device."""
        if self.cap:
            self.cap.release()
            self.cap = None
            self._release_claim()
            log.info(f"Camera '{self.camera_id}' closed")
        if self.stabilizer is not None:
            self.stabilizer.reset()

    def is_open(self):
        """Check if the camera is currently open."""
        return self.cap is not None and self.cap.isOpened()
