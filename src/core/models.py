from dataclasses import dataclass
from typing import Tuple
import time


BBox = Tuple[int, int, int, int]


@dataclass(frozen=True)
class FrameData:
    camera_id: str
    frame_id: int
    timestamp: float
    frame: object
    width: int
    height: int


@dataclass(frozen=True)
class Detection:
    bbox: BBox
    confidence: float
    cls: str


@dataclass
class Track:
    track_id: int
    bbox: BBox
    cls: str
    last_seen: float
