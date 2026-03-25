import sys
import time

from src.core.logger import setup_logger
from src.core.heartbeat import Heartbeat
from src.core.config import load_config
from src.ingestion.camera_ingestion import CameraIngestion
from src.detection.person_detector import PersonDetector
from src.tracking.tracker import Tracker
from src.tracking.track_manager import TrackManager
from src.events.event_engine import EventEngine


def run_camera(camera_id: str):
    config = load_config()
    log = setup_logger(f"worker.{camera_id}")

    cam_cfg = config.get("cameras", {}).get(camera_id)
    if cam_cfg is None:
        log.error(f"Camera worker requested unknown camera_id='{camera_id}'")
        return
    if not cam_cfg.get("enabled", True):
        log.info(f"Camera worker skipped for disabled camera '{camera_id}'")
        return

    log.info(f"Camera worker starting for '{camera_id}'")

    camera = CameraIngestion(camera_id, config=config)
    detection_cfg = config["detection"]
    pipeline_cfg = config["pipeline"]

    detector = PersonDetector(
        model_path=detection_cfg["model"],
        conf_thresh=detection_cfg["confidence_threshold"],
    )
    tracker = Tracker()
    manager = TrackManager(camera_id)
    heartbeat = Heartbeat(camera_id)
    event_engine = EventEngine(
        config=config,
        eval_interval=pipeline_cfg.get("event_eval_interval", 3),
    )

    detection_interval = pipeline_cfg["detection_interval"]["default"]

    try:
        camera.open()

        while True:
            frame_data = camera.read()

            run_detection = frame_data.frame_id % detection_interval == 0

            if run_detection:
                detections = detector.detect(frame_data)
                tracks = tracker.update(detections, frame_data.frame)
                manager.update(tracks)
                event_engine.evaluate(tracks, frame_data, manager)
            
            heartbeat.beat()

    except KeyboardInterrupt:
        log.info(f"Worker '{camera_id}' interrupted")
    except Exception as e:
        log.error(f"Worker '{camera_id}' error: {e}")
    finally:
        camera.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python camera_worker.py <camera_id>")
        sys.exit(1)
    run_camera(sys.argv[1])
