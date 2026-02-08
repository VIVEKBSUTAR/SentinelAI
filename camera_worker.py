import time
import sys
import signal

from src.ingestion.camera_ingestion import CameraIngestion
from src.detection.person_detector import PersonDetector
from src.tracking.tracker import Tracker
from src.tracking.track_manager import TrackManager
from src.core.logger import setup_logger


TARGET_FPS = 12.0
FPS_HYSTERESIS = 2.0
MIN_DETECTION_INTERVAL = 2
MAX_DETECTION_INTERVAL = 6
ADJUST_COOLDOWN_SEC = 3.0


shutdown_requested = False


def _handle_shutdown(signum, frame):
    global shutdown_requested
    shutdown_requested = True


def run_camera(camera_id: str):
    global shutdown_requested

    log = setup_logger()
    log.info(f"[CAMERA {camera_id}] Worker starting (pid={os.getpid()})")

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    camera = CameraIngestion(camera_id)
    detector = PersonDetector()
    tracker = Tracker()
    manager = TrackManager(camera_id)

    detection_interval = 3
    fps_window_start = time.time()
    frames_in_window = 0
    last_adjust_time = 0.0

    camera.open()
    log.info(f"[CAMERA {camera_id}] Camera opened")

    try:
        while not shutdown_requested:
            frame_data = camera.read()

            run_detection = frame_data.frame_id % detection_interval == 0

            if run_detection:
                t0 = time.time()
                detections = detector.detect(frame_data)
                detect_time = time.time() - t0
            else:
                detections = []
                detect_time = 0.0

            t1 = time.time()
            tracks = tracker.update(detections, frame_data.frame)
            track_time = time.time() - t1

            manager.update(tracks)

            frames_in_window += 1
            now = time.time()

            if now - fps_window_start >= 1.0:
                fps = frames_in_window / (now - fps_window_start)

                if now - last_adjust_time >= ADJUST_COOLDOWN_SEC:
                    if fps < TARGET_FPS - FPS_HYSTERESIS and detection_interval < MAX_DETECTION_INTERVAL:
                        detection_interval += 1
                        last_adjust_time = now
                        log.info(
                            f"[CAMERA {camera_id}] FPS {fps:.2f} low → interval {detection_interval}"
                        )
                    elif fps > TARGET_FPS + FPS_HYSTERESIS and detection_interval > MIN_DETECTION_INTERVAL:
                        detection_interval -= 1
                        last_adjust_time = now
                        log.info(
                            f"[CAMERA {camera_id}] FPS {fps:.2f} high → interval {detection_interval}"
                        )

                log.info(
                    f"[CAMERA {camera_id}] FPS={fps:.2f} | "
                    f"detect_time={detect_time:.3f}s | "
                    f"track_time={track_time:.3f}s | "
                    f"interval={detection_interval}"
                )

                fps_window_start = now
                frames_in_window = 0

    finally:
        log.info(f"[CAMERA {camera_id}] Shutdown requested, cleaning up")
        try:
            camera.close()
        except Exception as e:
            log.error(f"[CAMERA {camera_id}] Error closing camera: {e}")

        log.info(f"[CAMERA {camera_id}] Exiting cleanly")


if __name__ == "__main__":
    import os

    if len(sys.argv) != 2:
        print("Usage: python camera_worker.py <camera_id>")
        sys.exit(1)

    run_camera(sys.argv[1])
