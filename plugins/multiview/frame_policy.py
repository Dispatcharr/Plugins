"""PTS-aware reduction of scale work for sources faster than output."""

from collections import deque
from fractions import Fraction


class FrameReduction:
    """Keep one complete frame per output presentation interval.

    This deliberately runs after decode. Decoder-level frame skipping can throw
    away B-pictures and break mixed broadcast cadence before PTS selection.
    """

    def __init__(self, output_fps):
        self.output_fps = float(Fraction(str(output_fps)))
        self.intervals = deque(maxlen=30)
        self.anchor = None
        self.last_pts = None
        self.last_bucket = None
        self.active = False

    def reset(self):
        self.intervals.clear()
        self.anchor = None
        self.last_pts = None
        self.last_bucket = None
        self.active = False

    def keep(self, pts) -> bool:
        """Whether this decoded frame needs scaling and queueing."""
        if pts is None:
            return True
        if self.anchor is None:
            self.anchor = pts
        if self.last_pts is not None:
            interval = pts - self.last_pts
            if 0 < interval < 1.0:
                self.intervals.append(interval)
        self.last_pts = pts

        if len(self.intervals) == self.intervals.maxlen:
            source_fps = len(self.intervals) / sum(self.intervals)
            if self.active:
                self.active = source_fps > self.output_fps * 1.05
            else:
                self.active = source_fps > self.output_fps * 1.15
            if not self.active:
                self.last_bucket = None

        if not self.active:
            return True
        bucket = int((pts - self.anchor) * self.output_fps)
        if self.last_bucket is not None and bucket <= self.last_bucket:
            return False
        self.last_bucket = bucket
        return True
