from src.ingestion.camera_ingestion import CameraIngestion
from src.analysis.person_detection import PersonDetector
from src.tracking.single_camera_tracker import SingleCameraTracker


def main():
    camera = CameraIngestion(camera_id="sony")
    detector = PersonDetector()
    tracker = SingleCameraTracker()

    frame_count = 0

    try:
        camera.open()

        while True:
            data = camera.read()
            frame = data["frame"]
            frame_count += 1

            detections = detector.detect(frame)
            tracks = tracker.update(detections, frame)

            for t in tracks:
                print(
                    f"Frame {frame_count} | "
                    f"Track ID: {t['track_id']} | "
                    f"bbox: {t['bbox']}"
                )

    except KeyboardInterrupt:
        print("Stopping...")

    finally:
        camera.close()


if __name__ == "__main__":
    main()