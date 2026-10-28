"""Registry-wide maintainer message feed and its local editing commands."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_PATH = ".github/pluginctl/registry-messages.json"
SEVERITIES = ("info", "success", "warning", "critical")
_FIELDS = {"id", "severity", "title", "body", "link", "starts_at", "expires_at", "target", "dev"}
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_COMPARATOR_RE = re.compile(r"^(<=|>=|<|>|=)(v?\d+\.\d+\.\d+)$")
_ESCAPES = {"\\": "\\", '"': '"', "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


class FeedError(ValueError):
    """The maintained message feed does not satisfy its contract."""


def decode_flag_value(value: str, field: str) -> str:
    """Decode JSON-style escapes in a flag value without altering literal newlines."""
    output = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "\\":
            output.append(char)
            index += 1
            continue
        if index + 1 >= len(value):
            raise FeedError(f"{field} has a trailing backslash")
        escaped = value[index + 1]
        if escaped in _ESCAPES:
            output.append(_ESCAPES[escaped])
            index += 2
            continue
        if escaped != "u" or index + 6 > len(value):
            raise FeedError(f"{field} has an invalid escape sequence")
        digits = value[index + 2:index + 6]
        if not all(digit in "0123456789abcdefABCDEF" for digit in digits):
            raise FeedError(f"{field} has an invalid Unicode escape")
        codepoint = int(digits, 16)
        if 0xD800 <= codepoint <= 0xDFFF:
            raise FeedError(f"{field} cannot contain a Unicode surrogate escape")
        output.append(chr(codepoint))
        index += 6
    return "".join(output)


def _timestamp(value: str, field: str) -> dt.datetime:
    if not isinstance(value, str) or not _TIMESTAMP_RE.fullmatch(value):
        raise FeedError(f"{field} must use UTC RFC 3339 format YYYY-MM-DDTHH:MM:SSZ")
    try:
        return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise FeedError(f"{field} is not a valid timestamp") from exc


def _uuid4(value: object) -> str:
    if not isinstance(value, str):
        raise FeedError("id must be a UUIDv4 string")
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise FeedError("id must be a UUIDv4 string") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise FeedError("id must be a canonical lowercase UUIDv4 string")
    return value


def _text(value: object, field: str, required: bool = False) -> str:
    if not isinstance(value, str) or (required and not value.strip()):
        suffix = " a non-empty string" if required else " a string"
        raise FeedError(f"{field} must be{suffix}")
    return value


def _link(value: object) -> str:
    value = _text(value, "link")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise FeedError("link must be an absolute HTTPS URL")
    return value


def parse_target(value: object) -> tuple[tuple[str, tuple[int, int, int]], ...]:
    value = _text(value, "target", required=True)
    comparators = []
    for token in value.split():
        match = _COMPARATOR_RE.fullmatch(token)
        if not match:
            raise FeedError(f"invalid target comparator: {token!r}")
        version = match.group(2).removeprefix("v")
        comparators.append((match.group(1), tuple(int(part) for part in version.split("."))))
    if not comparators:
        raise FeedError("target must contain at least one comparator")
    return tuple(comparators)


def validate_message(value: object) -> dict:
    if not isinstance(value, dict):
        raise FeedError("each message must be an object")
    unknown = set(value) - _FIELDS
    if unknown:
        raise FeedError(f"unknown message field(s): {', '.join(sorted(unknown))}")
    required = {"id", "severity", "body"}
    missing = required - set(value)
    if missing:
        raise FeedError(f"missing required message field(s): {', '.join(sorted(missing))}")

    message = {
        "id": _uuid4(value["id"]),
        "severity": _text(value["severity"], "severity", required=True),
        "body": _text(value["body"], "body", required=True),
    }
    if message["severity"] not in SEVERITIES:
        raise FeedError(f"severity must be one of: {', '.join(SEVERITIES)}")
    for field in ("title",):
        if field in value:
            message[field] = _text(value[field], field, required=True)
    if "link" in value:
        message["link"] = _link(value["link"])
    starts_at = _timestamp(value["starts_at"], "starts_at") if "starts_at" in value else None
    expires_at = _timestamp(value["expires_at"], "expires_at") if "expires_at" in value else None
    if starts_at is not None and expires_at is None:
        raise FeedError("starts_at requires expires_at")
    if starts_at is not None and starts_at >= expires_at:
        raise FeedError("starts_at must be before expires_at")
    if starts_at is not None:
        message["starts_at"] = value["starts_at"]
    if expires_at is not None:
        message["expires_at"] = value["expires_at"]
    if "target" in value:
        parse_target(value["target"])
        message["target"] = value["target"]
    if "dev" in value:
        if not isinstance(value["dev"], bool):
            raise FeedError("dev must be true or false")
        message["dev"] = value["dev"]
    return message


def validate_feed(value: object) -> list[dict]:
    if not isinstance(value, dict) or set(value) != {"messages"} or not isinstance(value["messages"], list):
        raise FeedError("feed must be an object with exactly one messages array")
    messages = [validate_message(item) for item in value["messages"]]
    ids = [message["id"] for message in messages]
    if len(ids) != len(set(ids)):
        raise FeedError("message IDs must be unique")
    return messages


def render(messages: list[dict]) -> str:
    return json.dumps({"messages": messages}, indent=2, ensure_ascii=False) + "\n"


def load(path: str = DEFAULT_PATH, require_canonical: bool = False) -> list[dict]:
    try:
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
    except OSError as exc:
        raise FeedError(f"could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise FeedError(f"invalid JSON in {path}: {exc.msg}") from exc
    messages = validate_feed(data)
    if require_canonical and text != render(messages):
        raise FeedError(f"{path} is not canonical; rewrite it with pluginctl messages")
    return messages


def active(messages: list[dict], now: dt.datetime) -> list[dict]:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(dt.timezone.utc)
    return [message for message in messages if "expires_at" not in message or
            _timestamp(message["expires_at"], "expires_at") > now]


def load_active(path: str = DEFAULT_PATH, now: dt.datetime | None = None) -> list[dict]:
    if not Path(path).exists():
        return []
    return active(load(path), now or dt.datetime.now(dt.timezone.utc))


def write(path: str, messages: list[dict]) -> None:
    validated = validate_feed({"messages": messages})
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(render(validated))
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _prompt(label: str, default: str = "", required: bool = False) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        value = input(f"{label}{suffix}: ").strip()
        value = value or default
        if value or not required:
            return value
        print("A value is required.")


def _prompt_body(default: str = "", keep_if_empty: bool = False) -> str:
    instruction = "Body, finish with a line containing only '.'"
    if keep_if_empty:
        instruction += " (enter '.' immediately to keep current)"
    print(f"{instruction}:")
    lines = []
    while True:
        line = input()
        if line == ".":
            break
        lines.append(line)
    value = "\n".join(lines)
    if not value and keep_if_empty:
        return default
    if not value.strip():
        print("A non-empty body is required.")
        return _prompt_body(default, keep_if_empty)
    return value


def _confirm() -> bool:
    return _prompt("Write this change? (y/N)").lower() in {"y", "yes"}


def _require_interactive(command: str, missing: list[str]) -> None:
    if not _interactive():
        raise FeedError(f"{command} requires: {', '.join(missing)}")


def _find(messages: list[dict], message_id: str) -> tuple[int, dict]:
    _uuid4(message_id)
    for index, message in enumerate(messages):
        if message["id"] == message_id:
            return index, message
    raise FeedError(f"message {message_id} was not found")


def _preview(message: dict) -> None:
    print(json.dumps(message, indent=2, ensure_ascii=False))


def command(args) -> int:
    try:
        if args.messages_command == "check":
            load(args.file, require_canonical=True)
            print(f"{args.file} is valid and canonical.")
            return 0
        messages = [] if args.messages_command == "add" and not Path(args.file).exists() else load(args.file)
        if args.messages_command == "list":
            print(json.dumps(messages, indent=2, ensure_ascii=False))
            return 0
        if args.messages_command == "add":
            interactive = args.severity is None or args.body is None
            if interactive:
                _require_interactive("messages add", ["--severity", "--body"])
                severity = _prompt(f"Severity ({', '.join(SEVERITIES)})", args.severity or "", True)
                body = _prompt_body(args.body or "")
                title = _prompt("Title (optional)", args.title or "")
                link = _prompt("HTTPS link (optional)", args.link or "")
                starts_at = _prompt("Starts at UTC (optional)")
                expires_at = _prompt("Expires at UTC (optional)")
                target = _prompt("Target version range (optional)", args.target or "")
                dev = _prompt("Development builds only? true, false, or blank for all", args.dev or "")
            else:
                severity = decode_flag_value(args.severity, "severity")
                body = decode_flag_value(args.body, "body")
                title = decode_flag_value(args.title, "title") if args.title is not None else ""
                link = decode_flag_value(args.link, "link") if args.link is not None else ""
                starts_at = decode_flag_value(args.starts_at, "starts_at") if args.starts_at is not None else ""
                expires_at = decode_flag_value(args.expires_at, "expires_at") if args.expires_at is not None else ""
                target = decode_flag_value(args.target, "target") if args.target is not None else ""
                dev = args.dev
            message = {"id": str(uuid.uuid4()), "severity": severity, "body": body}
            for field, value in (("title", title), ("link", link), ("starts_at", starts_at),
                                 ("expires_at", expires_at), ("target", target)):
                if value:
                    message[field] = value
            if dev:
                if dev.lower() not in {"true", "false"}:
                    raise FeedError("dev must be true or false")
                message["dev"] = dev.lower() == "true"
            message = validate_message(message)
            if interactive:
                _preview(message)
                if not _confirm():
                    print("No change written.")
                    return 0
            write(args.file, [*messages, message])
            print(message["id"])
            return 0
        if args.messages_command == "remove":
            interactive = args.id is None
            if interactive:
                _require_interactive("messages remove", ["--id"])
                message_id = _prompt("Message UUID", required=True)
            else:
                message_id = args.id
            index, message = _find(messages, message_id)
            if interactive:
                _preview(message)
                if not _confirm():
                    print("No change written.")
                    return 0
            write(args.file, messages[:index] + messages[index + 1:])
            print(message_id)
            return 0
        if args.messages_command == "update":
            mutations = any(getattr(args, field) is not None for field in
                            ("severity", "title", "body", "link", "starts_at", "expires_at", "target", "dev")) or any(
                                getattr(args, f"clear_{field}") for field in
                                ("title", "link", "starts_at", "expires_at", "target", "dev"))
            interactive = args.id is None or not mutations
            if interactive:
                _require_interactive("messages update", ["--id and at least one field mutation"])
                message_id = _prompt("Message UUID", args.id or "", True)
                index, current = _find(messages, message_id)
                candidate = dict(current)
                for field, label in (("severity", "Severity"), ("title", "Title"),
                                     ("link", "HTTPS link"), ("starts_at", "Starts at UTC"),
                                     ("expires_at", "Expires at UTC"), ("target", "Target version range")):
                    value = _prompt(f"{label} (blank keeps current)")
                    if value == "-" and field not in {"severity", "body"}:
                        candidate.pop(field, None)
                        continue
                    if value:
                        candidate[field] = value
                candidate["body"] = _prompt_body(current["body"], keep_if_empty=True)
                dev = _prompt("Development builds only? true, false, blank keeps current, '-' clears")
                if dev == "-":
                    candidate.pop("dev", None)
                elif dev:
                    if dev.lower() not in {"true", "false"}:
                        raise FeedError("dev must be true or false")
                    candidate["dev"] = dev.lower() == "true"
            else:
                message_id = args.id
                index, current = _find(messages, message_id)
                candidate = dict(current)
                for field in ("severity", "title", "body", "link", "starts_at", "expires_at", "target"):
                    value = getattr(args, field)
                    if value is not None and getattr(args, f"clear_{field}", False):
                        raise FeedError(f"cannot combine --{field.replace('_', '-')} with --clear-{field.replace('_', '-')}")
                    if value is not None:
                        candidate[field] = decode_flag_value(value, field)
                if args.dev is not None and args.clear_dev:
                    raise FeedError("cannot combine --dev with --clear-dev")
                if args.dev is not None:
                    candidate["dev"] = args.dev
                for field in ("title", "link", "starts_at", "expires_at", "target", "dev"):
                    if getattr(args, f"clear_{field}"):
                        candidate.pop(field, None)
            candidate["id"] = current["id"]
            candidate = validate_message(candidate)
            if interactive:
                _preview(candidate)
                if not _confirm():
                    print("No change written.")
                    return 0
            messages[index] = candidate
            write(args.file, messages)
            print(candidate["id"])
            return 0
        raise FeedError("unknown messages command")
    except FeedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
