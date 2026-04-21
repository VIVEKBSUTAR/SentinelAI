import time
import cv2
import threading

# CPU optimization: limit OpenCV internal threads to prevent contention
# across multiple camera threads. Remove or increase when GPU is available.
cv2.setNumThreads(2)
import torch
torch.set_num_threads(2)  # CPU optimization: limit PyTorch threads, same as OpenCV

from src.ingestion.camera_ingestion import CameraIngestion
from src.detection.person_detector import PersonDetector
from src.tracking.tracker import Tracker
from src.tracking.track_manager import TrackManager
from src.core.config import load_config, get_enabled_camera_ids
from src.core.logger import setup_logger
from src.events.event_engine import EventEngine
from src.dashboard.server import run_server
from src.dashboard.state import dashboard_state
from src.dashboard.ws_manager import manager as ws_manager

# ── Bbox drawing colours ──────────────────────────────────────────────────────
_GREEN = (0, 255, 80)      # confirmed track (normal)
_RED   = (0, 30, 255)      # suspicious / alert track
_FONT  = cv2.FONT_HERSHEY_SIMPLEX


def _draw_bboxes(frame, tracks, suspicious_ids: set):
    """Draw green (normal) or red (suspicious) boxes on a copy of frame."""
    out = frame.copy()
    for t in tracks:
        x1, y1, x2, y2 = t.bbox
        color = _RED if t.track_id in suspicious_ids else _GREEN
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f"ID:{t.track_id}"
        cv2.putText(out, label, (x1, max(y1 - 6, 10)), _FONT, 0.45, color, 1, cv2.LINE_AA)
    return out


def run_pipeline(camera_id: str, config: dict):
    """Full ingestion→detection→tracking→events pipeline for one camera."""
    log = setup_logger(f"pipeline.{camera_id}")
    pipeline_cfg = config["pipeline"]
    detection_cfg = config["detection"]

    camera = CameraIngestion(camera_id, config=config)
    detector = PersonDetector(
        model_path=detection_cfg["model"],
        conf_thresh=detection_cfg["confidence_threshold"],
    )
    tracker = Tracker()
    track_manager = TrackManager(camera_id)
    event_engine = EventEngine(
        config=config,
        eval_interval=pipeline_cfg.get("event_eval_interval", 3),
    )

    target_fps    = pipeline_cfg["target_fps"]
    fps_hysteresis = pipeline_cfg["fps_hysteresis"]
    adjust_cooldown = pipeline_cfg["adjust_cooldown_sec"]
    detection_interval = pipeline_cfg["detection_interval"]["default"]
    min_interval  = pipeline_cfg["detection_interval"]["min"]
    max_interval  = pipeline_cfg["detection_interval"]["max"]

    fps_window_start = time.time()
    frames_in_window = 0
    last_adjust_time = 0.0
    detect_time = 0.0
    track_time  = 0.0
    detections  = []

    # Per-camera state for bbox overlay
    last_tracks: list = []
    suspicious_ids: set = set()
    suspicious_expiry: dict = {}      # track_id → expiry timestamp
    SUSPICIOUS_TTL = 15.0             # seconds a track stays red after last alert

    encode_params = [cv2.IMWRITE_JPEG_QUALITY, 45]  # CPU optimization: reduced from 60. Restore to 60 when GPU available

    dashboard_state.set_camera_status(camera_id, active=True, fps=0.0)
    log.info(f"Pipeline starting for camera '{camera_id}'")

    while True:
        try:
            camera.open()
            log.info(f"Camera '{camera_id}' opened")

            while True:
                frame_data = camera.read()
                now = time.time()

                run_detection = frame_data.frame_id % detection_interval == 0

                # ── Detection & Tracking ──────────────────────────────────────
                if run_detection:
                    t0 = time.time()
                    # CPU optimization: downscale frame before detection to reduce inference cost.
                    # YOLO inference time scales roughly with resolution squared.
                    # Restore DETECT_WIDTH to match full camera resolution when GPU available.
                    DETECT_WIDTH = 416
                    if frame_data.width > DETECT_WIDTH:
                        scale = DETECT_WIDTH / frame_data.width
                        detect_h = int(frame_data.height * scale)
                        small_frame = cv2.resize(frame_data.frame, (DETECT_WIDTH, detect_h))
                        from src.core.models import FrameData as _FrameData
                        small_frame_data = _FrameData(
                            camera_id=frame_data.camera_id,
                            frame_id=frame_data.frame_id,
                            timestamp=frame_data.timestamp,
                            frame=small_frame,
                            width=DETECT_WIDTH,
                            height=detect_h
                        )
                        raw_detections = detector.detect(small_frame_data)
                        # Scale bounding boxes back up to original frame dimensions
                        scale_x = frame_data.width / DETECT_WIDTH
                        scale_y = frame_data.height / detect_h
                        scaled_detections = []
                        for det in raw_detections:
                            x1, y1, x2, y2 = det.bbox
                            scaled_bbox = (
                                int(x1 * scale_x),
                                int(y1 * scale_y),
                                int(x2 * scale_x),
                                int(y2 * scale_y)
                            )
                            from dataclasses import replace
                            scaled_detections.append(replace(det, bbox=scaled_bbox))
                        detections = scaled_detections
                    else:
                        detections = detector.detect(frame_data)
                    detect_time = time.time() - t0

                    t1 = time.time()
                    last_tracks = tracker.update(detections, frame_data.frame)
                    track_time  = time.time() - t1

                    track_manager.update(last_tracks)

                    events = event_engine.evaluate(last_tracks, frame_data, track_manager)

                    # Update suspicious set based on new events
                    for e in events:
                        if e.severity in ("warning", "critical"):
                            for tid in (e.track_ids or []):
                                suspicious_ids.add(tid)
                                suspicious_expiry[tid] = now + SUSPICIOUS_TTL

                        event_dict = {
                            "id": dashboard_state.get_event_count(),
                            "event_type": e.event_type,
                            "camera_id": e.camera_id,
                            "timestamp": e.timestamp,
                            "severity": e.severity,
                            "description": e.description,
                            "track_ids": e.track_ids,
                            "zone_name": e.zone_name,
                            "metadata": e.metadata,
                            "acknowledged": False,
                        }
                        dashboard_state.add_event(event_dict, max_events=200)
                        ws_manager.broadcast_threadsafe({"type": "event", "data": event_dict})

                # Expire stale suspicious IDs
                expired = [tid for tid, exp in suspicious_expiry.items() if now > exp]
                for tid in expired:
                    suspicious_ids.discard(tid)
                    del suspicious_expiry[tid]

                # ── Push annotated frame to dashboard ─────────────────────────
                if frame_data.frame is not None:
                    try:
                        h, w = frame_data.frame.shape[:2]
                        target_w = 640  # CPU optimization: reduced from 960. Restore to 960 when GPU available
                        if w > target_w:
                            target_h = int(h * (target_w / w))
                            vis = cv2.resize(frame_data.frame, (target_w, target_h))
                            # Scale track bboxes to resized dimensions
                            scale = target_w / w
                            scaled_tracks = []
                            for t in last_tracks:
                                x1, y1, x2, y2 = t.bbox
                                from src.core.models import Track
                                scaled_tracks.append(Track(
                                    track_id=t.track_id,
                                    bbox=(int(x1*scale), int(y1*scale),
                                          int(x2*scale), int(y2*scale)),
                                    cls=t.cls,
                                    last_seen=t.last_seen,
                                ))
                        else:
                            vis = frame_data.frame
                            scaled_tracks = last_tracks

                        vis = _draw_bboxes(vis, scaled_tracks, suspicious_ids)
                        ok, jpeg = cv2.imencode('.jpg', vis, encode_params)  # CPU: quality reduced from 60 to 45. Restore to 60 when GPU available
                        if ok:
                            dashboard_state.set_frame(camera_id, jpeg.tobytes())
                    except Exception as enc_err:
                        log.debug(f"Frame encode error: {enc_err}")

                # ── FPS bookkeeping ───────────────────────────────────────────
                frames_in_window += 1

                if now - fps_window_start >= 1.0:
                    fps = frames_in_window / (now - fps_window_start)

                    if now - last_adjust_time >= adjust_cooldown:
                        if fps < target_fps - fps_hysteresis and detection_interval < max_interval:
                            detection_interval += 1
                            last_adjust_time = now
                        elif fps > target_fps + fps_hysteresis and detection_interval > min_interval:
                            detection_interval -= 1
                            last_adjust_time = now

                    log.info(
                        f"FPS={fps:.2f} | det={len(detections)} | "
                        f"tracks={len(last_tracks)} | sus={len(suspicious_ids)} | "
                        f"dt={detect_time:.3f}s tt={track_time:.3f}s | "
                        f"interval={detection_interval}"
                    )

                    dashboard_state.set_camera_status(
                        camera_id, active=True, fps=fps,
                        person_count=len(last_tracks),
                        suspicious_count=len(suspicious_ids),
                    )
                    # Broadcast status update to all WS clients
                    ws_manager.broadcast_threadsafe({
                        "type": "status",
                        "data": {
                            "camera_id": camera_id,
                            "fps": round(fps, 1),
                            "person_count": len(last_tracks),
                            "suspicious_count": len(suspicious_ids),
                        }
                    })

                    fps_window_start = now
                    frames_in_window = 0

        except Exception as e:
            log.error(f"Pipeline error for '{camera_id}': {e}. Restarting...")
            dashboard_state.set_camera_status(camera_id, active=False, fps=0.0)
            camera.close()
            time.sleep(2)


def main():
    config = load_config()
    log = setup_logger("main")

    cameras = get_enabled_camera_ids(config)
    if not cameras:
        log.warning("No enabled cameras in config. Dashboard will run without pipelines.")
    log.info(f"Starting SentinelAI with cameras: {cameras}")

    # Start dashboard server in background thread
    dashboard_thread = threading.Thread(
        target=run_server,
        kwargs={"host": "0.0.0.0", "port": 8000},
        daemon=True,
        name="dashboard",
    )
    dashboard_thread.start()

    # Start one pipeline thread per camera
    pipeline_threads = []
    for cam_id in cameras:
        t = threading.Thread(
            target=run_pipeline,
            args=(cam_id, config),
            daemon=True,
            name=f"pipeline-{cam_id}",
        )
        t.start()
        pipeline_threads.append(t)
        log.info(f"Pipeline thread started for '{cam_id}'")

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down SentinelAI.")


if __name__ == "__main__":
    main()
