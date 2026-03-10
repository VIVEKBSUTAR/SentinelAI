import yaml
from pathlib import Path


_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "cameras.yaml"


def load_config(path=None):
    """Load and return the project configuration from YAML."""
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH

    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    _validate(config)
    return config


def _validate(config):
    """Basic validation of required config keys."""
    if "cameras" not in config:
        raise ValueError("Config missing 'cameras' section")

    if "pipeline" not in config:
        raise ValueError("Config missing 'pipeline' section")

    if "detection" not in config:
        raise ValueError("Config missing 'detection' section")

    for cam_id, cam_cfg in config["cameras"].items():
        if "source" not in cam_cfg:
            raise ValueError(f"Camera '{cam_id}' missing 'source'")


def get_camera_source(config, camera_id):
    """Get the device source index for a camera ID."""
    if camera_id not in config["cameras"]:
        raise ValueError(f"Unknown camera id: {camera_id}")
    return config["cameras"][camera_id]["source"]
