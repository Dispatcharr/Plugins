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
    """Round to the nearest even integer.

    Must round (not truncate): custom-registry rects go fraction -> pixel ->
    fraction -> pixel through _split_row/_split_grid, and a plain int(v)
    truncation turns a value that's a hair below an integer due to float
    error (e.g. 639.999999998) into 638 instead of 640 -- a systematic 1-2px
    gap between otherwise-touching tiles.
    """
    r = int(round(v))
    return r - (r % 2)


def tile_rects(layout: str, n: int, out_w: int, out_h: int, custom_registry: dict = None) -> list:
    """Return [(x, y, w, h, valign, halign), ...], one entry per tile.

    `valign`/`halign` say where to anchor a tile's letterboxed/pillarboxed
    content within its rect: "center" (default) or, for tiles stacked
    adjacent to a sibling along an axis, "top"/"bottom"/"left"/"right" to
    push the content against the shared edge (padding lands on the outer
    edge instead) so adjacent tiles' content touches with no gap. Aspect
    ratio is always preserved; content is never cropped.

    `layout` of the form "custom:<style_id>" looks up a user-defined style in
    *custom_registry* (the `multiview_custom_layouts` settings dict: style_id
    -> {"name": ..., "elements": [...]}, see `_resolve_elements`). Falls back
    to the auto-grid if the style or its elements can't cover this channel count.
    """
    if isinstance(layout, str) and layout.startswith("custom:"):
        style = (custom_registry or {}).get(layout[len("custom:"):])
        elements = (style or {}).get("elements") if style else None
        fractions = _resolve_elements(elements, n, out_w, out_h) if elements else None
        if fractions:
            rects = [
                (x * out_w, y * out_h, w * out_w, h * out_h, valign, halign)
                for (x, y, w, h, valign, halign) in fractions
            ]
            return [(_even(x), _even(y), _even(w), _even(h), valign, halign)
                    for (x, y, w, h, valign, halign) in rects]
        layout = "auto"

    if layout == "featured":
        rects = _featured_rects(n, out_w, out_h)
    elif layout == "top_featured":
        rects = _top_featured_rects(n, out_w, out_h)
    else:
        rects = _auto_grid_rects(n, out_w, out_h)
    return [(_even(x), _even(y), _even(w), _even(h), valign, halign)
            for (x, y, w, h, valign, halign) in rects]


def _auto_grid_rects(n: int, out_w: int, out_h: int) -> list:
    """Square-ish grid; last partial row is horizontally centered.

    Content in the top row is pushed down and the bottom row pushed up (same
    idea as the side-stack valign trick in _featured_rects) so aspect-ratio
    letterboxing collects at the outer top/bottom edges instead of doubling
    up where rows meet.
    """
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
        if rows == 1:
            valign = "center"
        elif r == 0:
            valign = "bottom"
        elif r == rows - 1:
            valign = "top"
        else:
            valign = "center"
        rects.append((x, y, tile_w, tile_h, valign, "center"))
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

    rects = [(0, 0, main_w, out_h, "center", "center")]
    for i in range(side_count):
        if side_count == 1:
            valign = "center"
        elif i == 0:
            valign = "bottom"
        elif i == side_count - 1:
            valign = "top"
        else:
            valign = "center"
        rects.append((main_w, i * side_h, side_w, side_h, valign, "center"))
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

    rects = [(0, 0, out_w, main_h, "center", "center")]
    for i in range(bottom_count):
        if bottom_count == 1:
            halign = "center"
        elif i == 0:
            halign = "right"
        elif i == bottom_count - 1:
            halign = "left"
        else:
            halign = "center"
        rects.append((x_offset + i * tile_w, main_h, tile_w, bottom_h, "center", halign))
    return rects[:n]


def _split_row(el: dict, count: int, out_w: int, out_h: int) -> list:
    """Split a row element into `count` naturally-sized, touching tiles,
    centered as a block per the row's halign/valign -- same approach as
    _top_featured_rects's bottom row, generalized to any rect/direction.

    Returns fractional (x, y, w, h, valign, halign) tuples. Tile size is
    capped by both the row's own thickness and a 16:9 assumption, so tiles
    never stretch to fill the whole row -- the block is anchored within
    the row's rect per its own halign/valign, and edge tiles push their
    content toward the interior (touching, no gap) just like the built-in
    featured layouts, leaving any leftover space in the row untouched.
    """
    x, y, w, h = el["x"], el["y"], el["w"], el["h"]
    valign = el.get("valign", "center")
    halign = el.get("halign", "center")
    vertical = el.get("direction") == "vertical"
    row_w_px, row_h_px = w * out_w, h * out_h
    # Round the row's own origin, the natural tile size, and the block
    # offset to even pixels *once*, then step by that same integer for
    # every piece -- arbitrary (freeform-dragged) el x/y/w/h fractions
    # otherwise survive a fraction -> pixel -> fraction -> pixel round
    # trip with float error, which independently rounding each piece's
    # position and width can turn into a systematic 1-2px gap between
    # tiles that are supposed to touch.
    pieces = []
    if vertical:
        row_y_px = _even(y * out_h)
        natural_px = _even(min(row_h_px / count, row_w_px * 9 / 16))
        total_px = natural_px * count
        avail_px = row_h_px
        offset_px = _even(0 if valign == "top" else (avail_px - total_px if valign == "bottom" else (avail_px - total_px) / 2))
        piece_h = natural_px / out_h
        for i in range(count):
            piece_valign = "center" if count == 1 else ("bottom" if i == 0 else "top" if i == count - 1 else "center")
            piece_y_px = row_y_px + offset_px + i * natural_px
            pieces.append((x, piece_y_px / out_h, w, piece_h, piece_valign, halign))
    else:
        row_x_px = _even(x * out_w)
        natural_px = _even(min(row_w_px / count, row_h_px * 16 / 9))
        total_px = natural_px * count
        avail_px = row_w_px
        offset_px = _even(0 if halign == "left" else (avail_px - total_px if halign == "right" else (avail_px - total_px) / 2))
        piece_w = natural_px / out_w
        for i in range(count):
            piece_halign = "center" if count == 1 else ("right" if i == 0 else "left" if i == count - 1 else "center")
            piece_x_px = row_x_px + offset_px + i * natural_px
            pieces.append((piece_x_px / out_w, y, piece_w, h, valign, piece_halign))
    return pieces


def _split_grid(el: dict, count: int) -> list:
    """Split a "grid" element's rect into `count` pieces, square-ish 2D grid.

    Same cols/rows formula as _auto_grid_rects, scoped to this element's own
    rect. Unlike the whole-canvas auto-grid, every piece uses the grid
    element's own single valign/halign uniformly -- a deliberate
    simplification, not a full reimplementation of _auto_grid_rects's
    per-row edge-push polish.
    """
    x, y, w, h = el["x"], el["y"], el["w"], el["h"]
    valign = el.get("valign", "center")
    halign = el.get("halign", "center")
    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)
    tile_w = w / cols
    tile_h = h / rows

    last_row_count = count % cols or cols
    empty_cells = cols - last_row_count
    offset_x = (empty_cells * tile_w) / 2 if empty_cells > 0 else 0

    pieces = []
    for i in range(count):
        c = i % cols
        r = i // cols
        is_last = r == rows - 1 and empty_cells > 0
        px = x + c * tile_w + (offset_x if is_last else 0)
        py = y + r * tile_h
        pieces.append((px, py, tile_w, tile_h, valign, halign))
    return pieces


def _distribute_dynamic_counts(remaining: int, dynamics: list) -> list:
    """Max-min fair distribution of `remaining` channels across dynamic
    elements, respecting each element's optional "max" cap (None = unlimited).

    Repeatedly hands out an even share to every still-eligible ("active")
    element; any element that would exceed its cap is clamped and dropped
    from the active set, and its unused share flows back in on the next
    pass. Degrades to a plain even split with the remainder going to the
    earliest elements when no caps are set (matches the pre-cap behavior
    exactly). Returns a list of counts, one per dynamic element, same order
    as `dynamics`.
    """
    counts = [0] * len(dynamics)
    caps = [d.get("max") for d in dynamics]
    active = set(range(len(dynamics)))
    left = remaining
    while left > 0 and active:
        share = left // len(active)
        if share == 0:
            for idx in sorted(active)[:left]:
                counts[idx] += 1
            break
        progressed = False
        for idx in list(active):
            cap = caps[idx]
            room = (cap - counts[idx]) if cap is not None else None
            give = share if room is None else min(share, room)
            if give > 0:
                counts[idx] += give
                left -= give
                progressed = True
            if cap is not None and counts[idx] >= cap:
                active.discard(idx)
        if not progressed:
            break
    return counts


def _resolve_elements(elements: list, n: int, out_w: int, out_h: int) -> "list | None":
    """Resolve a custom style's element list into n fractional tile rects.

    Mirrors src/dash/ui/src/utils/styleResolve.js -- keep both in sync; that
    JS copy exists only so the editor's live preview doesn't need a network
    round-trip per drag.

    Each "static" element consumes exactly one channel slot, in element
    order. Remaining channels (n - number of statics) are divided across
    "dynamic" elements (type "row" or "grid") via `_distribute_dynamic_counts`
    (even split by default, respecting each element's optional "max" cap). A
    "row" splits its count along a single axis; a "grid" arranges its count
    in a square-ish 2D grid (see _split_grid). Returns None if there are no
    dynamic elements and n exceeds the static count, or if the dynamic
    elements' caps can't collectively absorb the remainder -- caller falls
    back to the whole-canvas auto-grid in that case.
    """
    statics = [e for e in elements if e.get("type") == "static"]
    dynamics = [e for e in elements if e.get("type") in ("row", "grid")]
    remaining = max(0, n - len(statics))
    if remaining > 0 and not dynamics:
        return None

    counts = _distribute_dynamic_counts(remaining, dynamics)

    result = []
    channel_idx = 0
    dyn_i = 0
    for el in elements:
        if channel_idx >= n:
            break
        el_type = el.get("type")
        if el_type == "static":
            result.append((el["x"], el["y"], el["w"], el["h"], el.get("valign", "center"), el.get("halign", "center")))
            channel_idx += 1
        elif el_type in ("row", "grid"):
            count = counts[dyn_i]
            dyn_i += 1
            if count <= 0:
                continue
            result.extend(_split_row(el, count, out_w, out_h) if el_type == "row" else _split_grid(el, count))
            channel_idx += count

    if channel_idx < n:
        return None
    return result[:n]
