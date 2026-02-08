import subprocess
import time
import yaml
from pathlib import Path


CAMERA_CONFIG = "configs/cameras.yaml"
RESTART_DELAY_SEC = 2


def load_cameras():
    path = Path(CAMERA_CONFIG)
    if not path.exists():
        raise FileNotFoundError("Camera config not found")

    with open(path, "r") as f:
        return list(yaml.safe_load(f).keys())


def main():
    cameras = load_cameras()
    processes = {}

    print(f"Supervisor starting cameras: {cameras}")

    while True:
        for cam in cameras:
            proc = processes.get(cam)

            if proc is None or proc.poll() is not None:
                if proc is not None:
                    print(f"[SUPERVISOR] Camera {cam} crashed. Restarting...")

                processes[cam] = subprocess.Popen(
                    ["python", "camera_worker.py", cam]
                )

                time.sleep(RESTART_DELAY_SEC)

        time.sleep(1)


if __name__ == "__main__":
    main()
