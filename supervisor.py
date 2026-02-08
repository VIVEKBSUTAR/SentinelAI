import subprocess
import time
import signal
import sys


CAMERAS = ["sony", "mac"]
RESTART_DELAY_SEC = 1.0


class CameraProcess:
    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.process = None

    def start(self):
        self.process = subprocess.Popen(
            [sys.executable, "camera_worker.py", self.camera_id]
        )

    def is_alive(self):
        return self.process and self.process.poll() is None

    def stop(self):
        if self.is_alive():
            self.process.send_signal(signal.SIGTERM)

    def kill(self):
        if self.is_alive():
            self.process.kill()


def main():
    print("Supervisor starting cameras:", CAMERAS)

    workers = {cid: CameraProcess(cid) for cid in CAMERAS}

    for w in workers.values():
        w.start()

    try:
        while True:
            for cid, worker in workers.items():
                if not worker.is_alive():
                    print(f"[SUPERVISOR] Camera {cid} crashed. Restarting...")
                    time.sleep(RESTART_DELAY_SEC)
                    worker.start()

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[SUPERVISOR] Shutdown requested")

        for worker in workers.values():
            worker.stop()

        time.sleep(2)

        for worker in workers.values():
            if worker.is_alive():
                print(f"[SUPERVISOR] Forcing kill of {worker.camera_id}")
                worker.kill()

        print("[SUPERVISOR] Exiting cleanly")


if __name__ == "__main__":
    main()
