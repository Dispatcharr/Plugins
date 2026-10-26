"""Chunked file hashing shared by the ZIP builder and the ClamAV report."""

from __future__ import annotations

import hashlib

CHUNK_SIZE = 1 << 20


def file_digests(path: str, *algorithms: str) -> list[str]:
    """Hex digests of ``path`` for each named algorithm, reading the file once."""
    hashers = [hashlib.new(name) for name in algorithms]
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK_SIZE), b""):
            for hasher in hashers:
                hasher.update(chunk)
    return [hasher.hexdigest() for hasher in hashers]
