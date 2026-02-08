from src.ingestion.camera_ingestion import CameraIngestion
from src.detection.person_detector import PersonDetector
from src.tracking.tracker import Tracker
from src.tracking.track_manager import TrackManager
from src.core.logger import setup_logger
import time


TARGET_FPS = 12.0
FPS_HYSTERESIS = 2.0

MIN_DETECTION_INTERVAL = 2
MAX_DETECTION_INTERVAL = 6

ADJUST_COOLDOWN_SEC = 3.0


def main():
    log = setup_logger()

    camera = CameraIngestion("sony")
    detector = PersonDetector()
    tracker = Tracker()
    manager = TrackManager("sony")

    detection_interval = 3

    # FPS tracking
    fps_window_start = time.time()
    frames_in_window = 0

    last_adjust_time = 0.0
    last_detections = []

    while True:
        try:
            camera.open()
            log.info("Camera started")

            while True:
                frame_data = camera.read()

                run_detection = frame_data.frame_id % detection_interval == 0

                # Detection
                if run_detection:
                    t0 = time.time()
                    detections = detector.detect(frame_data)
                    detect_time = time.time() - t0
                    last_detections = detections
                else:
                    detections = []
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

                    # Adaptive control with hysteresis + cooldown
                    if now - last_adjust_time >= ADJUST_COOLDOWN_SEC:
                        if (
                            fps < TARGET_FPS - FPS_HYSTERESIS
                            and detection_interval < MAX_DETECTION_INTERVAL
                        ):
                            detection_interval += 1
                            last_adjust_time = now
                            log.info(
                                f"FPS={fps:.2f} low → increasing detection_interval to {detection_interval}"
                            )

                        elif (
                            fps > TARGET_FPS + FPS_HYSTERESIS
                            and detection_interval > MIN_DETECTION_INTERVAL
                        ):
                            detection_interval -= 1
                            last_adjust_time = now
                            log.info(
                                f"FPS={fps:.2f} high → decreasing detection_interval to {detection_interval}"
                            )

                    log.info(
                        f"FPS={fps:.2f} | detections={len(detections)} | "
                        f"detect_time={detect_time:.3f}s | track_time={track_time:.3f}s | "
                        f"detection_interval={detection_interval}"
                    )

                    fps_window_start = now
                    frames_in_window = 0

        except Exception as e:
            log.error(f"Pipeline error: {e}. Restarting...")
            camera.close()
            time.sleep(1)


if __name__ == "__main__":
    main()
