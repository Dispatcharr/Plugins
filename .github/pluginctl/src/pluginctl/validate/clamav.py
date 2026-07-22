"""``pluginctl clamav-report``: parse clamscan output into status + findings table.

Ports the "Set ClamAV status outputs" step of the clamav-scan job. ClamAV itself
still runs as the native CLI in the workflow; only the result parsing moves here.
"""

from __future__ import annotations

import hashlib
import os
from typing import Callable, Optional

from ..core import actions


def _sha256_file(path: str) -> str:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def parse_infected_lines(output: str) -> list[str]:
    """Lines ending in ' FOUND' (clamscan --infected format)."""
    return [ln for ln in output.splitlines() if ln.endswith(" FOUND")]


def build_findings_table(infected_lines: list[str], workspace: str,
                         sha256_fn: Optional[Callable[[str], str]] = None) -> str:
    """Render the ``| File | Signature |`` table, linking known hashes to VirusTotal."""
    sha256_fn = sha256_fn or _sha256_file
    rows = ["| File | Signature |", "|------|-----------|"]
    for line in infected_lines:
        # "<path>: <SIG> FOUND"
        full_path = line
        idx = line.rfind(": ")
        if idx != -1 and line.endswith(" FOUND"):
            full_path = line[:idx]
            sig = line[idx + 2:-len(" FOUND")]
        else:
            sig = ""
        file_rel = full_path
        prefix = (workspace or "") + "/"
        if workspace and file_rel.startswith(prefix):
            file_rel = file_rel[len(prefix):]
        digest = sha256_fn(full_path)
        if digest:
            rows.append(f"| `{file_rel}` | [`{sig}`](https://www.virustotal.com/gui/file/{digest}) |")
        else:
            rows.append(f"| `{file_rel}` | `{sig}` |")
    return "\n".join(rows) + "\n"


def run(output_file: str = "clamav-output.txt", scan_exit: int = 0,
        findings_out: str = "clamav-findings.md") -> int:
    workspace = os.environ.get("GITHUB_WORKSPACE", "")
    output = ""
    if os.path.isfile(output_file):
        with open(output_file, encoding="utf-8") as fh:
            output = fh.read()
    infected_lines = parse_infected_lines(output)
    actions.set_output("clamav_infected", str(len(infected_lines)))

    if infected_lines:
        table = build_findings_table(infected_lines, workspace)
        with open(findings_out, "w", encoding="utf-8") as fh:
            fh.write(table)
        actions.set_output("clamav_status", "failure")
        return 0
    if scan_exit >= 2:
        actions.set_output("clamav_status", "failure")
        return 0
    actions.set_output("clamav_status", "success")
    return 0
