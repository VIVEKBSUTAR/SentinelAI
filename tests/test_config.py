import pytest
import os
import tempfile
import yaml

from src.core.config import load_config, get_camera_source


@pytest.fixture
def valid_config_path():
    """Create a temporary valid config file."""
    config = {
        "cameras": {
            "test_cam": {"source": 0, "type": "usb"},
            "test_cam2": {"source": 1, "type": "builtin"},
        },
        "pipeline": {
            "target_fps": 12,
            "detection_interval": {"min": 2, "max": 6, "default": 3},
            "fps_hysteresis": 2.0,
            "adjust_cooldown_sec": 3.0,
        },
        "detection": {
            "model": "yolov8n.pt",
            "confidence_threshold": 0.3,
        },
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config, f)
        path = f.name

    yield path
    os.unlink(path)


class TestLoadConfig:
    def test_loads_valid_config(self, valid_config_path):
        config = load_config(valid_config_path)
        assert "cameras" in config
        assert "pipeline" in config
        assert "detection" in config

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path.yaml")

    def test_missing_cameras_section(self, tmp_path):
        bad_config = tmp_path / "bad.yaml"
        bad_config.write_text(yaml.dump({"pipeline": {}, "detection": {}}))
        with pytest.raises(ValueError, match="cameras"):
            load_config(str(bad_config))

    def test_missing_pipeline_section(self, tmp_path):
        bad_config = tmp_path / "bad.yaml"
        bad_config.write_text(yaml.dump({"cameras": {"cam": {"source": 0}}, "detection": {}}))
        with pytest.raises(ValueError, match="pipeline"):
            load_config(str(bad_config))

    def test_camera_missing_source(self, tmp_path):
        bad_config = tmp_path / "bad.yaml"
        bad_config.write_text(yaml.dump({
            "cameras": {"cam": {"type": "usb"}},
            "pipeline": {},
            "detection": {},
        }))
        with pytest.raises(ValueError, match="source"):
            load_config(str(bad_config))


class TestGetCameraSource:
    def test_valid_camera(self, valid_config_path):
        config = load_config(valid_config_path)
        assert get_camera_source(config, "test_cam") == 0
        assert get_camera_source(config, "test_cam2") == 1

    def test_unknown_camera(self, valid_config_path):
        config = load_config(valid_config_path)
        with pytest.raises(ValueError, match="Unknown camera"):
            get_camera_source(config, "nonexistent")
