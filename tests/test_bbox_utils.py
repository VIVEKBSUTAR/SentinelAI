import pytest
from src.core.bbox_utils import is_valid_bbox


class TestIsValidBbox:
    """Tests for bbox validation utility."""

    def test_valid_bbox(self):
        assert is_valid_bbox((10, 10, 100, 100), 640, 480) is True

    def test_zero_width(self):
        assert is_valid_bbox((100, 10, 100, 100), 640, 480) is False

    def test_zero_height(self):
        assert is_valid_bbox((10, 100, 100, 100), 640, 480) is False

    def test_inverted_coords(self):
        assert is_valid_bbox((100, 100, 10, 10), 640, 480) is False

    def test_negative_x(self):
        assert is_valid_bbox((-1, 10, 100, 100), 640, 480) is False

    def test_negative_y(self):
        assert is_valid_bbox((10, -1, 100, 100), 640, 480) is False

    def test_exceeds_frame_width(self):
        assert is_valid_bbox((10, 10, 641, 100), 640, 480) is False

    def test_exceeds_frame_height(self):
        assert is_valid_bbox((10, 10, 100, 481), 640, 480) is False

    def test_too_large_area(self):
        # Box covers > 80% of frame
        assert is_valid_bbox((0, 0, 600, 450), 640, 480) is False

    def test_edge_bbox(self):
        # Box exactly at frame boundary
        assert is_valid_bbox((0, 0, 640, 480), 640, 480) is False

    def test_small_bbox(self):
        assert is_valid_bbox((100, 100, 110, 110), 640, 480) is True

    def test_custom_max_area_ratio(self):
        # 90% area ratio allowed
        assert is_valid_bbox((0, 0, 600, 450), 640, 480, max_area_ratio=0.95) is True
