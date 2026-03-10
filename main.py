import sys
import time

from src.ingestion.camera_ingestion import CameraIngestion
from src.detection.person_detector import PersonDetector
from src.tracking.tracker import Tracker
from src.tracking.track_manager import TrackManager
from src.core.config import load_config
from src.core.logger import setup_logger
from src.events.event_engine import EventEngine

# Dashboard integration
import threading
import asyncio
from src.dashboard.server import run_server
from src.dashboard.routes import RECENT_EVENTS, PIPELINE_STATUS
from src.dashboard.ws_manager import manager as ws_manager


def main():
    config = load_config()
    log = setup_logger("pipeline")

    # Determine which camera to use
    camera_id = sys.argv[1] if len(sys.argv) > 1 else list(config["cameras"].keys())[0]

    pipeline_cfg = config["pipeline"]
    detection_cfg = config["detection"]

    camera = CameraIngestion(camera_id, config=config)
    detector = PersonDetector(
        model_path=detection_cfg["model"],
        conf_thresh=detection_cfg["confidence_threshold"],
    )
    tracker = Tracker()
    manager = TrackManager(camera_id)
    event_engine = EventEngine(
        config=config,
        eval_interval=pipeline_cfg.get("event_eval_interval", 3),
    )

    target_fps = pipeline_cfg["target_fps"]
    fps_hysteresis = pipeline_cfg["fps_hysteresis"]
    adjust_cooldown = pipeline_cfg["adjust_cooldown_sec"]
    detection_interval = pipeline_cfg["detection_interval"]["default"]
    min_interval = pipeline_cfg["detection_interval"]["min"]
    max_interval = pipeline_cfg["detection_interval"]["max"]

    # FPS tracking
    fps_window_start = time.time()
    frames_in_window = 0
    last_adjust_time = 0.0

    # Initialize dashboard status
    PIPELINE_STATUS["cameras"] = {
        camera_id: {"active": True, "fps": 0.0}
    }

    # Start dashboard in a background thread
    dashboard_thread = threading.Thread(
        target=run_server, 
        kwargs={"host": "0.0.0.0", "port": 8000},
        daemon=True
    )
    dashboard_thread.start()

    log.info(f"Starting pipeline for camera '{camera_id}'")

    while True:
        try:
            camera.open()
            log.info(f"Camera '{camera_id}' started")

            while True:
                frame_data = camera.read()

                run_detection = frame_data.frame_id % detection_interval == 0

                # Detection & Tracking
                if run_detection:
                    t0 = time.time()
                    detections = detector.detect(frame_data)
                    detect_time = time.time() - t0

                    t1 = time.time()
                    tracks = tracker.update(detections, frame_data.frame)
                    track_time = time.time() - t1

                    manager.update(tracks)
                    
                    # Event detection
                    events = event_engine.evaluate(tracks, frame_data, manager)
                    
                    # Push events to dashboard
                    for e in events:
                        # Convert to dict for JSON serialization
                        event_dict = {
                            "event_type": e.event_type,
                            "camera_id": e.camera_id,
                            "timestamp": e.timestamp,
                            "severity": e.severity,
                            "description": e.description,
                            "track_ids": e.track_ids,
                            "zone_name": e.zone_name,
                            "metadata": e.metadata
                        }
                        RECENT_EVENTS.append(event_dict)
                        if len(RECENT_EVENTS) > 100:
                            RECENT_EVENTS.pop(0)
                            
                        # Broadcast immediately via websocket
                        msg = {"type": "event", "data": event_dict}
                        # Handle async broadcast from sync code
                        try:
                            loop = asyncio.get_running_loop()
                            asyncio.run_coroutine_threadsafe(ws_manager.broadcast(msg), loop)
                        except RuntimeError:
                            pass
                else:
                    detect_time = 0.0
                    track_time = 0.0
                    detections = []

                # FPS calculation
                frames_in_window += 1
                now = time.time()

                if now - fps_window_start >= 1.0:
                    fps = frames_in_window / (now - fps_window_start)

                    # Adaptive control with hysteresis + cooldown
                    if now - last_adjust_time >= adjust_cooldown:
                        if fps < target_fps - fps_hysteresis and detection_interval < max_interval:
                            detection_interval += 1
                            last_adjust_time = now
                            log.info(
                                f"FPS={fps:.2f} low → increasing detection_interval to {detection_interval}"
                            )
                        elif fps > target_fps + fps_hysteresis and detection_interval > min_interval:
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
                    
                    # Update status for REST API
                    PIPELINE_STATUS["cameras"][camera_id] = {
                        "active": True, 
                        "fps": fps
                    }

                    fps_window_start = now
                    frames_in_window = 0

        except Exception as e:
            log.error(f"Pipeline error: {e}. Restarting...")
            camera.close()
            time.sleep(1)


if __name__ == "__main__":
    main()
