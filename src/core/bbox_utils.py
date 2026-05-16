def is_valid_bbox(bbox, frame_width, frame_height, max_area_ratio=0.95):
    x1, y1, x2, y2 = bbox

    if x2 <= x1 or y2 <= y1:
        return False

    if x1 < 0 or y1 < 0 or x2 > frame_width or y2 > frame_height:
        return False

    box_area = (x2 - x1) * (y2 - y1)
    frame_area = frame_width * frame_height

    if box_area / frame_area > max_area_ratio:
        return False

    return True


def bboxes_intersect(bbox1, bbox2, margin=50):
    """Check if two bounding boxes intersect, optionally expanding bbox1 by margin."""
    x1_min, y1_min, x1_max, y1_max = bbox1
    x2_min, y2_min, x2_max, y2_max = bbox2

    x1_min -= margin
    y1_min -= margin
    x1_max += margin
    y1_max += margin

    if x1_max < x2_min or x1_min > x2_max:
        return False
    if y1_max < y2_min or y1_min > y2_max:
        return False
    return True
