"""Lightweight optical-flow based frame stabilization.

The stabilizer reduces camera shake / jitter between consecutive frames
by estimating inter-frame motion (translation + rotation) via sparse
optical flow and then applying a smoothed correction transform.

Algorithm outline
─────────────────
1. Convert the incoming frame to grayscale.
2. Detect Shi-Tomasi corner features in the *previous* grayscale frame.
3. Track those features into the current frame with Lucas-Kanade optical
   flow.
4. Estimate a rigid (Euclidean) transform – dx, dy, da – from the
   matched point pairs.
5. Accumulate those per-frame transforms into a trajectory.
6. Smooth the trajectory with a moving-average window.
7. Apply the *difference* between the smoothed and actual trajectory as a
   correction warp to the current frame.
"""

from collections import deque

import cv2
import numpy as np

from src.core.logger import setup_logger

log = setup_logger("stabilizer")

# Parameters for Shi-Tomasi corner detection
_FEATURE_PARAMS = dict(
    maxCorners=200,
    qualityLevel=0.01,
    minDistance=30,
    blockSize=3,
)

# Parameters for Lucas-Kanade optical flow
_LK_PARAMS = dict(
    winSize=(15, 15),
    maxLevel=3,
    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
)


class FrameStabilizer:
    """Smooth camera output by compensating for inter-frame jitter.

    Parameters
    ----------
    smoothing_window : int
        Number of frames over which to smooth the camera trajectory.
        Larger values produce smoother output but react more slowly to
        intentional camera movement.  ``30`` is a good starting point.
    """

    def __init__(self, smoothing_window: int = 30):
        if smoothing_window < 1:
            raise ValueError("smoothing_window must be >= 1")

        self.smoothing_window = smoothing_window

        # Previous grayscale frame for optical-flow computation.
        self._prev_gray = None

        # Cumulative trajectory (sum of per-frame transforms).
        self._trajectory_x = 0.0
        self._trajectory_y = 0.0
        self._trajectory_a = 0.0

        # Ring buffer of recent trajectory values for smoothing.
        self._buf_x: deque = deque(maxlen=smoothing_window)
        self._buf_y: deque = deque(maxlen=smoothing_window)
        self._buf_a: deque = deque(maxlen=smoothing_window)

    # ── public API ────────────────────────────────────────────────────────

    def stabilize(self, frame: np.ndarray) -> np.ndarray:
        """Return a stabilized copy of *frame*.

        The very first call simply stores the frame for the next
        comparison and returns the original unchanged.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self._prev_gray is None:
            self._prev_gray = gray
            self._buf_x.append(0.0)
            self._buf_y.append(0.0)
            self._buf_a.append(0.0)
            return frame

        # Step 1 – detect features in the previous frame
        prev_pts = cv2.goodFeaturesToTrack(self._prev_gray, **_FEATURE_PARAMS)

        if prev_pts is None:
            # No trackable features – keep frame as-is and move on.
            self._prev_gray = gray
            self._buf_x.append(self._trajectory_x)
            self._buf_y.append(self._trajectory_y)
            self._buf_a.append(self._trajectory_a)
            return frame

        # Step 2 – track features into the current frame
        curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            self._prev_gray, gray, prev_pts, None, **_LK_PARAMS
        )

        # Keep only successfully tracked points
        good_prev = prev_pts[status.flatten() == 1]
        good_curr = curr_pts[status.flatten() == 1]

        if len(good_prev) < 3:
            # Not enough matches – skip stabilization for this frame.
            self._prev_gray = gray
            self._buf_x.append(self._trajectory_x)
            self._buf_y.append(self._trajectory_y)
            self._buf_a.append(self._trajectory_a)
            return frame

        # Step 3 – estimate the rigid transform (translation + rotation)
        dx, dy, da = self._estimate_transform(good_prev, good_curr)

        # Step 4 – accumulate into the trajectory
        self._trajectory_x += dx
        self._trajectory_y += dy
        self._trajectory_a += da

        self._buf_x.append(self._trajectory_x)
        self._buf_y.append(self._trajectory_y)
        self._buf_a.append(self._trajectory_a)

        # Step 5 – compute smoothed trajectory
        smooth_x = np.mean(self._buf_x)
        smooth_y = np.mean(self._buf_y)
        smooth_a = np.mean(self._buf_a)

        # Step 6 – compute and apply correction
        corr_x = smooth_x - self._trajectory_x
        corr_y = smooth_y - self._trajectory_y
        corr_a = smooth_a - self._trajectory_a

        stabilized = self._apply_transform(frame, corr_x, corr_y, corr_a)

        self._prev_gray = gray
        return stabilized

    def reset(self):
        """Clear all internal state so the next frame starts fresh."""
        self._prev_gray = None
        self._trajectory_x = 0.0
        self._trajectory_y = 0.0
        self._trajectory_a = 0.0
        self._buf_x.clear()
        self._buf_y.clear()
        self._buf_a.clear()

    # ── internals ─────────────────────────────────────────────────────────

    @staticmethod
    def _estimate_transform(prev_pts, curr_pts):
        """Return (dx, dy, da) from matched point pairs.

        Uses ``cv2.estimateAffinePartial2D`` to get a rigid
        (similarity) transform, then decomposes it into translation and
        rotation components.
        """
        mat, _ = cv2.estimateAffinePartial2D(prev_pts, curr_pts)

        if mat is None:
            return 0.0, 0.0, 0.0

        dx = mat[0, 2]
        dy = mat[1, 2]
        da = np.arctan2(mat[1, 0], mat[0, 0])
        return float(dx), float(dy), float(da)

    @staticmethod
    def _apply_transform(frame, dx, dy, da):
        """Apply a rigid correction to *frame*."""
        h, w = frame.shape[:2]
        cos_a = np.cos(da)
        sin_a = np.sin(da)
        mat = np.array([
            [cos_a, -sin_a, dx],
            [sin_a,  cos_a, dy],
        ], dtype=np.float64)
        return cv2.warpAffine(frame, mat, (w, h), borderMode=cv2.BORDER_REPLICATE)
