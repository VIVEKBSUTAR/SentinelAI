from src.ingestion.camera_ingestion import CameraIngestion
from src.analysis.person_detection import PersonDetector


def main():
    camera = CameraIngestion(camera_id="sony")
    detector = PersonDetector()

    try:
        camera.open()
        data = camera.read()
        frame = data["frame"]

        detections = detector.detect(frame)

        print("Camera ID:", data["camera_id"])
        print("Timestamp:", data["timestamp"])
        print("Frame shape:", frame.shape)
        print("People detected:", len(detections))

    finally:
        camera.close()


if __name__ == "__main__":
    main()
