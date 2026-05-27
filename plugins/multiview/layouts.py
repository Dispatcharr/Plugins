"""FFmpeg filter-complex builders for each multiview layout."""

import math


def _centered_grid_positions(n: int, cols: int, rows: int, tile_w: int, tile_h: int) -> list[str]:
    """xstack layout positions with the last partial row horizontally centered.

    All positions are hardcoded pixel values. xstack only supports addition in
    layout expressions, so expressions like '2*w0' silently evaluate to 0 and
    cause tiles to overlap. Pixel values avoid that entirely.
    """
    last_row_count = n % cols or cols
    empty_cells = cols - last_row_count
    offset_x = (empty_cells * tile_w) // 2 if empty_cells > 0 else 0

    positions = []
    for i in range(n):
        c = i % cols
        r = i // cols
        is_last = r == rows - 1 and empty_cells > 0
        x = c * tile_w + (offset_x if is_last else 0)
        y = r * tile_h
        positions.append(f"{x}_{y}")
    return positions


def _auto_grid_filter(n: int, out_w: int, out_h: int) -> tuple[str, list[str]]:
    """Return (filter_complex, output_map_args) for an n-input square-ish grid."""
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    tile_w = out_w // cols
    tile_h = out_h // rows

    scale_parts = [
        f"[{i}:v]fps=30000/1001,scale={tile_w}:{tile_h}:force_original_aspect_ratio=decrease,"
        f"pad={tile_w}:{tile_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[v{i}]"
        for i in range(n)
    ]

    positions = _centered_grid_positions(n, cols, rows, tile_w, tile_h)

    inputs_str = "".join(f"[v{i}]" for i in range(n))
    xstack = f"{inputs_str}xstack=inputs={n}:layout={'|'.join(positions)}:fill=black[v]"

    filter_complex = "; ".join(scale_parts) + "; " + xstack
    return filter_complex, ["-map", "[v]"]


def _featured_layout(n: int, out_w: int, out_h: int) -> tuple[int, int, int, int, list[str]]:
    """Return (main_w, main_h, side_w, side_h, positions) for featured layout.

    Side column width is the natural 16:9 width for the tile height, capped so
    the featured stream always occupies at least 60% of the output width.
    """
    side_count = max(1, n - 1)
    side_h = out_h // side_count
    side_w = min(round(side_h * 16 / 9), round(out_w * 0.4))
    main_w = out_w - side_w
    positions = ["0_0"] + [f"{main_w}_{i * side_h}" for i in range(side_count)]
    return main_w, out_h, side_w, side_h, positions


def _featured_filter(n: int, out_w: int, out_h: int) -> tuple[str, list[str]]:
    """Return (filter_complex, output_map_args) for featured layout: channel 0 left, rest stacked right."""
    main_w, main_h, side_w, side_h, positions = _featured_layout(n, out_w, out_h)

    parts = [
        f"[0:v]fps=30000/1001,scale={main_w}:{main_h}:force_original_aspect_ratio=decrease,"
        f"pad={main_w}:{main_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[main]"
    ]
    side_count = n - 1
    for i in range(1, n):
        slot = i - 1
        if side_count == 1:
            pad_y = "(oh-ih)/2"
        elif slot == 0:
            pad_y = "oh-ih"
        elif slot == side_count - 1:
            pad_y = "0"
        else:
            pad_y = "(oh-ih)/2"
        parts.append(
            f"[{i}:v]fps=30000/1001,scale={side_w}:{side_h}:force_original_aspect_ratio=decrease,"
            f"pad={side_w}:{side_h}:(ow-iw)/2:{pad_y}:color=black,setsar=1[s{i}]"
        )

    all_labels = "[main]" + "".join(f"[s{i}]" for i in range(1, n))
    parts.append(f"{all_labels}xstack=inputs={n}:layout={'|'.join(positions)}[v]")

    return "; ".join(parts), ["-map", "[v]"]


def _top_featured_layout(n: int, out_w: int, out_h: int) -> tuple[int, int, int, int, list[str]]:
    """Return (main_w, main_h, tile_w, bottom_h, positions) for top-featured layout.

    Bottom row height is the natural 16:9 height for the tile width, capped so
    the featured stream always occupies at least 60% of the output height.
    Tile width is back-computed from bottom_h so tiles are always 16:9; when the
    40% cap reduces bottom_h the row is narrower than out_w and is centred.
    """
    bottom_count = max(1, n - 1)
    initial_tile_w = out_w // bottom_count
    natural_h = round(initial_tile_w * 9 / 16)
    bottom_h = min(natural_h, round(out_h * 0.4))
    main_h = out_h - bottom_h
    tile_w = round(bottom_h * 16 / 9)
    x_offset = max(0, (out_w - tile_w * bottom_count) // 2)
    positions = ["0_0"] + [f"{x_offset + i * tile_w}_{main_h}" for i in range(bottom_count)]
    return out_w, main_h, tile_w, bottom_h, positions


def _top_featured_filter(n: int, out_w: int, out_h: int) -> tuple[str, list[str]]:
    """Return (filter_complex, output_map_args) for top-featured layout: channel 0 top, rest row bottom."""
    main_w, main_h, tile_w, bottom_h, positions = _top_featured_layout(n, out_w, out_h)

    parts = [
        f"[0:v]fps=30000/1001,scale={main_w}:{main_h}:force_original_aspect_ratio=decrease,"
        f"pad={main_w}:{main_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[main]"
    ]
    for i in range(1, n):
        parts.append(
            f"[{i}:v]fps=30000/1001,scale={tile_w}:{bottom_h}:force_original_aspect_ratio=decrease,"
            f"pad={tile_w}:{bottom_h}:(ow-iw)/2:0:color=black,setsar=1[b{i}]"
        )

    all_labels = "[main]" + "".join(f"[b{i}]" for i in range(1, n))
    parts.append(f"{all_labels}xstack=inputs={n}:layout={'|'.join(positions)}:fill=black[v]")

    return "; ".join(parts), ["-map", "[v]"]
