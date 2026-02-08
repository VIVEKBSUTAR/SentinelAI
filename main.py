from src.ingestion.camera_ingestion import CameraIngestion
from src.detection.person_detector import PersonDetector
from src.tracking.tracker import Tracker
from src.tracking.track_manager import TrackManager
from src.core.logger import setup_logger
import time


DETECTION_INTERVAL = 3  # run detection + embeddings every N frames


def main():
    log = setup_logger()

    camera = CameraIngestion("sony")
    detector = PersonDetector()
    tracker = Tracker()
    manager = TrackManager("sony")

    # FPS tracking
    fps_window_start = time.time()
    frames_in_window = 0

    last_detections = []

    while True:
        try:
            camera.open()
            log.info("Camera started")

            while True:
                frame_start = time.time()

                frame_data = camera.read()

                # Detection (frame skipping)
                if frame_data.frame_id % DETECTION_INTERVAL == 0:
                    t0 = time.time()
                    detections = detector.detect(frame_data)
                    detect_time = time.time() - t0
                    last_detections = detections
                else:
                    detections = last_detections
                    detect_time = 0.0

                # Tracking
                t1 = time.time()
                tracks = tracker.update(detections, frame_data.frame)
                track_time = time.time() - t1

                manager.update(tracks)

                # FPS calculation
                frames_in_window += 1
                now = time.time()
                if now - fps_window_start >= 1.0:
                    fps = frames_in_window / (now - fps_window_start)
                    log.info(
                        f"FPS={fps:.2f} | detections={len(detections)} | "
                        f"detect_time={detect_time:.3f}s | track_time={track_time:.3f}s"
                    )
                    fps_window_start = now
                    frames_in_window = 0

        except Exception as e:
            log.error(f"Pipeline error: {e}. Restarting...")
            camera.close()
            time.sleep(1)


if __name__ == "__main__":
    main()
