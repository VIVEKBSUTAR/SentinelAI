import cv2
import time
import yaml
from pathlib import Path
from src.core.models import FrameData


class CameraIngestion:
    def __init__(self, camera_id, config_path="configs/cameras.yaml"):
        self.camera_id = camera_id
        self.cap = None
        self.frame_id = 0

        with open(Path(config_path), "r") as f:
            cfg = yaml.safe_load(f)

        self.camera_index = int(cfg[camera_id])

    def open(self):
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            raise RuntimeError("Camera open failed")

    def read(self):
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("Frame read failed")

        self.frame_id += 1
        h, w = frame.shape[:2]

        return FrameData(
            camera_id=self.camera_id,
            frame_id=self.frame_id,
            timestamp=time.time(),
            frame=frame,
            width=w,
            height=h,
        )

    def close(self):
        if self.cap:
            self.cap.release()
            self.cap = None
