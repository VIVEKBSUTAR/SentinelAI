import pytest
import numpy as np
import cv2

from src.ingestion.frame_stabilizer import FrameStabilizer


def _make_frame(h=480, w=640):
    """Return a synthetic BGR frame with trackable features."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    # Draw a grid of small rectangles so goodFeaturesToTrack has corners.
    for y in range(40, h - 40, 60):
        for x in range(40, w - 40, 60):
            cv2.rectangle(frame, (x, y), (x + 20, y + 20), (255, 255, 255), -1)
    return frame


def _shift_frame(frame, dx, dy):
    """Translate *frame* by (dx, dy) pixels."""
    mat = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(frame, mat, (frame.shape[1], frame.shape[0]),
                          borderMode=cv2.BORDER_REPLICATE)


class TestFrameStabilizer:
    """Tests for the FrameStabilizer class."""

    def test_first_frame_returned_unchanged(self):
        stab = FrameStabilizer(smoothing_window=5)
        frame = _make_frame()
        result = stab.stabilize(frame)
        np.testing.assert_array_equal(result, frame)

    def test_output_shape_matches_input(self):
        stab = FrameStabilizer(smoothing_window=5)
        base = _make_frame()
        stab.stabilize(base)
        shifted = _shift_frame(base, 3, 2)
        result = stab.stabilize(shifted)
        assert result.shape == base.shape

    def test_output_dtype_matches_input(self):
        stab = FrameStabilizer(smoothing_window=5)
        base = _make_frame()
        stab.stabilize(base)
        shifted = _shift_frame(base, 5, -3)
        result = stab.stabilize(shifted)
        assert result.dtype == base.dtype

    def test_stabilization_reduces_jitter(self):
        """A sequence of jittered frames should produce less displacement
        than the raw jitter after stabilization."""
        stab = FrameStabilizer(smoothing_window=10)
        base = _make_frame()

        # Feed the base frame first
        stab.stabilize(base)

        # Create a sequence of jittered frames (alternating ±5px)
        diffs_raw = []
        diffs_stab = []
        for i in range(1, 21):
            dx = 5 * ((-1) ** i)
            dy = 3 * ((-1) ** i)
            jittered = _shift_frame(base, dx, dy)
            stabilized = stab.stabilize(jittered)

            # Measure how far each result is from the base using centre
            # region comparison (avoids border artifacts).
            h, w = base.shape[:2]
            crop = slice(h // 4, 3 * h // 4), slice(w // 4, 3 * w // 4)
            diff_raw = np.mean(np.abs(
                jittered[crop].astype(float) - base[crop].astype(float)
            ))
            diff_stabilized = np.mean(np.abs(
                stabilized[crop].astype(float) - base[crop].astype(float)
            ))
            diffs_raw.append(diff_raw)
            diffs_stab.append(diff_stabilized)

        avg_raw = np.mean(diffs_raw)
        avg_stab = np.mean(diffs_stab)
        # Stabilized output should be closer to the base than raw jitter.
        assert avg_stab < avg_raw, (
            f"Stabilization did not reduce jitter: raw={avg_raw:.2f}, "
            f"stabilized={avg_stab:.2f}"
        )

    def test_reset_clears_state(self):
        stab = FrameStabilizer(smoothing_window=5)
        base = _make_frame()
        stab.stabilize(base)
        stab.stabilize(_shift_frame(base, 10, 10))

        stab.reset()

        # After reset the next call acts like the first call
        result = stab.stabilize(base)
        np.testing.assert_array_equal(result, base)

    def test_invalid_smoothing_window_raises(self):
        with pytest.raises(ValueError):
            FrameStabilizer(smoothing_window=0)
        with pytest.raises(ValueError):
            FrameStabilizer(smoothing_window=-5)

    def test_uniform_frame_no_crash(self):
        """A solid-color frame has no features — should return gracefully."""
        stab = FrameStabilizer(smoothing_window=5)
        blank = np.full((480, 640, 3), 128, dtype=np.uint8)
        result1 = stab.stabilize(blank)
        result2 = stab.stabilize(blank)
        assert result1.shape == blank.shape
        assert result2.shape == blank.shape

    def test_smoothing_window_one_acts_as_passthrough(self):
        """With window=1 the smoothed trajectory equals the actual one,
        so no correction is applied and the output is the input."""
        stab = FrameStabilizer(smoothing_window=1)
        base = _make_frame()
        stab.stabilize(base)
        shifted = _shift_frame(base, 8, -4)
        result = stab.stabilize(shifted)
        # With window=1 the correction is zero → output ≈ input
        np.testing.assert_array_equal(result, shifted)
