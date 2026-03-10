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
