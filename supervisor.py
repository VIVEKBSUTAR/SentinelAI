import subprocess
import time
import signal
import sys

from src.core.heartbeat import HeartbeatMonitor
from src.core.config import load_config
from src.core.logger import setup_logger


def main():
    config = load_config()
    log = setup_logger("supervisor")

    cameras = list(config["cameras"].keys())
    processes = {}
    running = True

    monitor = HeartbeatMonitor(
        cameras,
        timeout=10.0,
        startup_grace=5.0,
    )

    def shutdown_handler(signum, frame):
        nonlocal running
        running = False
        log.info("[SUPERVISOR] Shutdown requested")

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    log.info(f"Supervisor starting cameras: {cameras}")

    for cam in cameras:
        p = subprocess.Popen(
            [sys.executable, "camera_worker.py", cam]
        )
        processes[cam] = p
        log.info(f"[SUPERVISOR] Started {cam} pid={p.pid}")

    while running:
        time.sleep(1)

        for cam in cameras:
            p = processes[cam]

            if running and (p.poll() is not None or monitor.is_stale(cam)):
                log.warning(f"[SUPERVISOR] Restarting {cam}")

                p.terminate()
                p.wait()

                new_p = subprocess.Popen(
                    [sys.executable, "camera_worker.py", cam]
                )
                processes[cam] = new_p
                monitor.mark_restart(cam)

                log.info(f"[SUPERVISOR] Restarted {cam} pid={new_p.pid}")

    for p in processes.values():
        p.terminate()
        p.wait()

    log.info("[SUPERVISOR] Exiting cleanly")


if __name__ == "__main__":
    main()
