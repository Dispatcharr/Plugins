"""Tile geometry for each multiview layout.

Each layout maps N tiles to a list of pixel rectangles (x, y, w, h) inside the
output frame. The compositor scales each child into its rect and blits it onto
the canvas, so the geometry here defines the visual style. All values are even
(rounded) so chroma subsampling and scaling stay clean.

The grid/featured/top_featured math is the same as the original xstack layouts;
only the return shape changed (rectangles instead of filter strings).
"""

import math


def _even(v: int) -> int:
    return int(v) - (int(v) % 2)


def tile_rects(layout: str, n: int, out_w: int, out_h: int) -> list:
    """Return [(x, y, w, h), ...], one rect per tile, for the given layout."""
    if layout == "featured":
        rects = _featured_rects(n, out_w, out_h)
    elif layout == "top_featured":
        rects = _top_featured_rects(n, out_w, out_h)
    else:
        rects = _auto_grid_rects(n, out_w, out_h)
    return [(_even(x), _even(y), _even(w), _even(h)) for (x, y, w, h) in rects]


def _auto_grid_rects(n: int, out_w: int, out_h: int) -> list:
    """Square-ish grid; last partial row is horizontally centered."""
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    tile_w = out_w // cols
    tile_h = out_h // rows

    last_row_count = n % cols or cols
    empty_cells = cols - last_row_count
    offset_x = (empty_cells * tile_w) // 2 if empty_cells > 0 else 0

    rects = []
    for i in range(n):
        c = i % cols
        r = i // cols
        is_last = r == rows - 1 and empty_cells > 0
        x = c * tile_w + (offset_x if is_last else 0)
        y = r * tile_h
        rects.append((x, y, tile_w, tile_h))
    return rects


def _featured_rects(n: int, out_w: int, out_h: int) -> list:
    """Channel 0 large on the left; remaining channels stacked on the right.

    Side column width is the natural 16:9 width for the tile height, capped so
    the featured stream always occupies at least 60% of the output width.
    """
    side_count = max(1, n - 1)
    side_h = out_h // side_count
    side_w = min(round(side_h * 16 / 9), round(out_w * 0.4))
    main_w = out_w - side_w

    rects = [(0, 0, main_w, out_h)]
    for i in range(side_count):
        rects.append((main_w, i * side_h, side_w, side_h))
    return rects[:n]


def _top_featured_rects(n: int, out_w: int, out_h: int) -> list:
    """Channel 0 large on top; remaining channels in a centered bottom row.

    Bottom row height is the natural 16:9 height for the tile width, capped so
    the featured stream always occupies at least 60% of the output height. Tile
    width is back-computed so bottom tiles stay 16:9; the row is centered.
    """
    bottom_count = max(1, n - 1)
    initial_tile_w = out_w // bottom_count
    natural_h = round(initial_tile_w * 9 / 16)
    bottom_h = min(natural_h, round(out_h * 0.4))
    main_h = out_h - bottom_h
    tile_w = round(bottom_h * 16 / 9)
    x_offset = max(0, (out_w - tile_w * bottom_count) // 2)

    rects = [(0, 0, out_w, main_h)]
    for i in range(bottom_count):
        rects.append((x_offset + i * tile_w, main_h, tile_w, bottom_h))
    return rects[:n]
