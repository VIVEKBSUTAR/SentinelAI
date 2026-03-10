from src.events.base_event import BaseEventRule
from src.events.models import Event


def _point_in_polygon(px, py, polygon):
    """Ray-casting algorithm for point-in-polygon check."""
    n = len(polygon)
    inside = False

    x1, y1 = polygon[0]
    for i in range(1, n + 1):
        x2, y2 = polygon[i % n]
        if py > min(y1, y2):
            if py <= max(y1, y2):
                if px <= max(x1, x2):
                    if y1 != y2:
                        xinters = (py - y1) * (x2 - x1) / (y2 - y1) + x1
                    if y1 == y2 or px <= xinters:
                        inside = not inside
        x1, y1 = x2, y2

    return inside


class ZoneIntrusionRule(BaseEventRule):
    """Detects when a person enters a restricted zone.

    Zones are defined as polygons in the config under 'zones'.
    A track's bbox centroid is checked against each restricted zone.
    """

    name = "zone_intrusion"

    def __init__(self, zones_config=None):
        self.zones = {}
        self.alerted = {}  # {(track_id, zone_name): True}

        if zones_config:
            for zone_name, zone_cfg in zones_config.items():
                if zone_cfg.get("type") == "restricted":
                    self.zones[zone_name] = {
                        "camera": zone_cfg["camera"],
                        "polygon": zone_cfg["polygon"],
                    }

    def evaluate(self, tracks, frame_data, track_manager):
        events = []

        for zone_name, zone in self.zones.items():
            if zone["camera"] != frame_data.camera_id:
                continue

            polygon = zone["polygon"]

            for track in tracks:
                key = (track.track_id, zone_name)

                if key in self.alerted:
                    continue

                cx = (track.bbox[0] + track.bbox[2]) / 2
                cy = (track.bbox[1] + track.bbox[3]) / 2

                if _point_in_polygon(cx, cy, polygon):
                    self.alerted[key] = True
                    events.append(
                        Event(
                            event_type="zone_intrusion",
                            camera_id=frame_data.camera_id,
                            timestamp=frame_data.timestamp,
                            severity="critical",
                            description=(
                                f"Person (track {track.track_id}) entered "
                                f"restricted zone '{zone_name}'"
                            ),
                            track_ids=[track.track_id],
                            zone_name=zone_name,
                            metadata={
                                "centroid": [round(cx), round(cy)],
                            },
                        )
                    )

        # Cleanup stale alerts
        active_ids = {t.track_id for t in tracks}
        self.alerted = {
            k: v for k, v in self.alerted.items() if k[0] in active_ids
        }

        return events
