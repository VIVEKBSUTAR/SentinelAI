from src.ingestion.camera_ingestion import CameraIngestion
from src.detection.person_detector import PersonDetector
from src.tracking.tracker import Tracker
from src.tracking.track_manager import TrackManager
from src.core.logger import setup_logger
import time


def main():
    log = setup_logger()

    camera = CameraIngestion("sony")
    detector = PersonDetector()
    tracker = Tracker()
    manager = TrackManager("sony")

    while True:
        try:
            camera.open()
            log.info("Camera started")

            while True:
                frame_data = camera.read()
                detections = detector.detect(frame_data)
                tracks = tracker.update(detections, frame_data.frame)
                manager.update(tracks)

        except Exception as e:
            log.error(f"Pipeline error: {e}. Restarting...")
            camera.close()
            time.sleep(1)


if __name__ == "__main__":
    main()
