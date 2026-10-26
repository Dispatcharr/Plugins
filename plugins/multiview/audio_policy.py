"""PTS bounds for the compositor's PCM FIFO."""

import math


def samples_before_pts(pts, samples, pts_limit, rate):
    """Return how many samples may be emitted without passing *pts_limit*."""
    if pts is None or pts_limit is None:
        return samples
    available = math.floor((pts_limit - pts) * rate + 1e-6)
    return max(0, min(samples, available))
