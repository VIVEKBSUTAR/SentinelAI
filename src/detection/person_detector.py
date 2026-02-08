from ultralytics import YOLO
from src.core.models import Detection
from src.core.bbox_utils import is_valid_bbox


class PersonDetector:
    def __init__(self, model_path="yolov8n.pt", conf_thresh=0.3):
        self.model = YOLO(model_path)
        self.conf_thresh = conf_thresh

    def detect(self, frame_data):
        results = self.model(frame_data.frame, verbose=False)
        detections = []

        for r in results:
            if r.boxes is None:
                continue

            for box, conf, cls in zip(
                r.boxes.xyxy.cpu().numpy(),
                r.boxes.conf.cpu().numpy(),
                r.boxes.cls.cpu().numpy(),
            ):
                if int(cls) != 0 or conf < self.conf_thresh:
                    continue

                bbox = tuple(map(int, box))
                if not is_valid_bbox(bbox, frame_data.width, frame_data.height):
                    continue

                detections.append(
                    Detection(bbox=bbox, confidence=float(conf), cls="person")
                )

        return detections
