

from ultralytics import YOLO
import numpy as np


class PersonDetector:
    def __init__(self, model_path: str = "yolov8n.pt", conf_threshold: float = 0.3):
        # Load pretrained YOLOv8 model once
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold

    def detect(self, frame: np.ndarray) -> list:
        # Run inference on a single frame
        results = self.model(frame, verbose=False)
        detections = []

        for r in results:
            if r.boxes is None:
                continue

            boxes = r.boxes.xyxy.cpu().numpy()
            scores = r.boxes.conf.cpu().numpy()
            classes = r.boxes.cls.cpu().numpy()

            for box, score, cls in zip(boxes, scores, classes):
                # COCO class 0 corresponds to 'person'
                if int(cls) == 0 and score >= self.conf_threshold:
                    x1, y1, x2, y2 = map(int, box)
                    detections.append({
                        "bbox": (x1, y1, x2, y2),
                        "confidence": float(score),
                        "class": "person",
                    })

        return detections