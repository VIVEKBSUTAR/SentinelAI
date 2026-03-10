import time

import cv2

from src.core.models import FrameData
from src.core.config import load_config, get_camera_source
from src.core.logger import setup_logger

log = setup_logger("ingestion")


class CameraIngestion:
    """Reads frames from a camera device and produces FrameData objects."""

    def __init__(self, camera_id, config=None):
        self.camera_id = camera_id
        self.config = config or load_config()
        self.source = get_camera_source(self.config, camera_id)
        self.cap = None
        self.frame_count = 0

    def open(self):
        """Open the camera device for reading.

        Tries the configured source index first.  If that fails, scans
        indices 0-4 as a fallback so the pipeline doesn't crash when
        device numbers shift (e.g. USB camera unplugged).
        """
        self.cap = cv2.VideoCapture(self.source)
        if self.cap.isOpened():
            log.info(f"Camera '{self.camera_id}' opened (source={self.source})")
            return

        # Configured source failed — try alternatives
        log.warning(
            f"Configured source {self.source} failed for '{self.camera_id}'. "
            "Scanning alternative indices…"
        )
        self.cap.release()

        for idx in range(5):
            if idx == self.source:
                continue  # already tried
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                self.cap = cap
                self.source = idx
                log.info(
                    f"Camera '{self.camera_id}' opened on fallback index {idx}"
                )
                return
            cap.release()

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
            log.info(f"Camera '{self.camera_id}' closed")

    def is_open(self):
        """Check if the camera is currently open."""
        return self.cap is not None and self.cap.isOpened()
