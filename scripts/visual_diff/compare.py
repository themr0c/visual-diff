"""Pixel-level screenshot comparison and annotation."""


def _merge_cells_to_bboxes(cells, cell_size, max_w, max_h, padding_x=12, padding_y=4):
    """Merge adjacent grid cells into bounding boxes with padding."""
    if not cells:
        return []
    pixel_rects = []
    for cx, cy in cells:
        x1 = cx * cell_size
        y1 = cy * cell_size
        x2 = min(x1 + cell_size, max_w)
        y2 = min(y1 + cell_size, max_h)
        pixel_rects.append((x1, y1, x2, y2))
    merged = []
    for rect in pixel_rects:
        x1, y1, x2, y2 = rect
        x1 = max(0, x1 - padding_x)
        y1 = max(0, y1 - padding_y)
        x2 = min(max_w, x2 + padding_x)
        y2 = min(max_h, y2 + padding_y)
        did_merge = False
        for i, (mx1, my1, mx2, my2) in enumerate(merged):
            if not (x2 < mx1 or x1 > mx2 or y2 < my1 or y1 > my2):
                merged[i] = (min(x1, mx1), min(y1, my1), max(x2, mx2), max(y2, my2))
                did_merge = True
                break
        if not did_merge:
            merged.append((x1, y1, x2, y2))
    return merged


def compare_screenshots(a_path, b_path, output_dir, slug):
    """Compare two screenshots and produce annotated versions.

    Returns ('identical'|'changed', change_pct).
    Annotated PNGs: dimmed unchanged areas, original pixels in changed bboxes,
    3px red border around each changed region.
    """
    import numpy as np
    from PIL import Image

    img_a = Image.open(a_path).convert('RGB')
    img_b = Image.open(b_path).convert('RGB')

    max_w = max(img_a.width, img_b.width)
    max_h = max(img_a.height, img_b.height)
    if img_a.size != (max_w, max_h):
        canvas = Image.new('RGB', (max_w, max_h), (255, 255, 255))
        canvas.paste(img_a, (0, 0))
        img_a = canvas
    if img_b.size != (max_w, max_h):
        canvas = Image.new('RGB', (max_w, max_h), (255, 255, 255))
        canvas.paste(img_b, (0, 0))
        img_b = canvas

    arr_a = np.array(img_a)
    arr_b = np.array(img_b)

    diff = np.abs(arr_a.astype(np.int16) - arr_b.astype(np.int16)).sum(axis=2)
    changed_mask = diff > 30

    if not changed_mask.any():
        return 'identical', 0.0

    change_pct = int(changed_mask.sum()) / (max_w * max_h) * 100

    cell_size = 50
    ys, xs = np.nonzero(changed_mask)
    cell_coords = np.column_stack((xs // cell_size, ys // cell_size))
    changed_cells = set(map(tuple, np.unique(cell_coords, axis=0)))
    bboxes = _merge_cells_to_bboxes(changed_cells, cell_size, max_w, max_h)

    amber = np.array([255, 180, 0], dtype=np.float32)

    for arr, suffix in [(arr_a, 'a'), (arr_b, 'b')]:
        result = (arr.astype(np.float32) * 0.55 + 255 * 0.45).astype(np.uint8)
        for x1, y1, x2, y2 in bboxes:
            region = arr[y1:y2, x1:x2].astype(np.float32)
            result[y1:y2, x1:x2] = np.clip(region * 0.88 + amber * 0.12, 0, 255).astype(np.uint8)
        Image.fromarray(result).save(str(output_dir / f"{slug}_{suffix}_annotated.png"))

    return 'changed', change_pct
