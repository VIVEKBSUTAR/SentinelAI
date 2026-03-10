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

                # Clip bounding box to frame dimensions
                x1, y1, x2, y2 = box
                x1 = max(0, int(x1))
                y1 = max(0, int(y1))
                x2 = min(frame_data.width, int(x2))
                y2 = min(frame_data.height, int(y2))
                
                bbox = (x1, y1, x2, y2)
                if not is_valid_bbox(bbox, frame_data.width, frame_data.height):
                    continue

                detections.append(
                    Detection(bbox=bbox, confidence=float(conf), cls="person")
                )

        return detections
