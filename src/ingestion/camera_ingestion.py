

import cv2
import time
import yaml
from pathlib import Path


class CameraIngestion:
    def __init__(
        self,
        camera_id: str,
        config_path: str = "configs/cameras.yaml",
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
    ):
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.fps = fps
        self.camera_index = self._load_camera_index(config_path)
        self.cap = None

    def _load_camera_index(self, config_path: str) -> int:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Camera config not found: {path}")

        with open(path, "r") as f:
            config = yaml.safe_load(f)

        if self.camera_id not in config:
            raise ValueError(f"Camera ID '{self.camera_id}' not found in camera config")

        return int(config[self.camera_id])

    def open(self) -> None:
        if self.cap is not None:
            return

        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            self.cap = None
            raise RuntimeError(
                f"Failed to open camera '{self.camera_id}' (index {self.camera_index})"
            )

        # Set properties before first read
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

    def read(self) -> dict:
        if self.cap is None:
            raise RuntimeError("Camera not opened. Call open() before read().")

        ret, frame = self.cap.read()
        if not ret or frame is None:
            raise RuntimeError("Failed to read frame from camera")

        return {
            "camera_id": self.camera_id,
            "timestamp": time.time(),
            "frame": frame,
            "height": frame.shape[0],
            "width": frame.shape[1],
        }

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None