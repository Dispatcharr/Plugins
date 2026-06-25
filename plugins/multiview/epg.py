"""EPG generation for Dispatcharr Multiview."""

import html
import logging
import os
from datetime import timedelta, timezone as dt_timezone

logger = logging.getLogger(__name__)


def resolve_channel_names(settings: dict, n: int) -> list:
    """Return channel display names for layout n, queried live at call time."""
    try:
        from apps.channels.models import Channel
        selector_type = settings.get(f"multiview_{n}_selector_type", "classic")
        ch_count = max(2, int(settings.get(f"multiview_{n}_channel_count", 4)))
        if selector_type == "regex":
            pattern = settings.get(f"multiview_{n}_regex_pattern", "")
            if not pattern:
                return []
            return list(
                Channel.objects.filter(name__iregex=pattern)
                .order_by("channel_number")[:ch_count]
                .values_list("name", flat=True)
            )
        names = []
        for m in range(1, ch_count + 1):
            ch_id = settings.get(f"multiview_{n}_channel_{m}", "_none")
            if ch_id and ch_id != "_none":
                try:
                    names.append(
                        Channel.objects.values_list("name", flat=True).get(id=int(ch_id))
                    )
                except Channel.DoesNotExist:
                    pass
        return names
    except Exception:
        return []


def _fmt_xmltv_time(dt) -> str:
    utc = dt.astimezone(dt_timezone.utc)
    return utc.strftime("%Y%m%d%H%M%S +0000")


def _build_xmltv(settings: dict, mv_count: int, window_start, window_end) -> str:
    chunk = timedelta(hours=4)

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<tv>"]

    for n in range(1, mv_count + 1):
        name = settings.get(f"multiview_{n}_name", f"Multiview {n}") or f"Multiview {n}"
        lines.append(f'  <channel id="multiview_{n}">')
        lines.append(f"    <display-name>{html.escape(name)}</display-name>")
        lines.append("  </channel>")

    for n in range(1, mv_count + 1):
        name = settings.get(f"multiview_{n}_name", f"Multiview {n}") or f"Multiview {n}"
        epg_source_mode = settings.get(f"multiview_{n}_epg_source_mode", "dummy")

        forwarded = False
        if epg_source_mode == "forward":
            fwd_ch_id = settings.get(f"multiview_{n}_epg_forward_channel", "_none")
            if fwd_ch_id and fwd_ch_id != "_none":
                try:
                    from apps.channels.models import Channel
                    ch = Channel.objects.select_related("epg_data").get(id=int(fwd_ch_id))
                    if ch.epg_data_id:
                        programs = list(
                            ch.epg_data.programs
                            .filter(start_time__lt=window_end, end_time__gt=window_start)
                            .order_by("start_time")
                        )
                        if programs:
                            for prog in programs:
                                lines.append(
                                    f'  <programme start="{_fmt_xmltv_time(prog.start_time)}"'
                                    f' stop="{_fmt_xmltv_time(prog.end_time)}"'
                                    f' channel="multiview_{n}">'
                                )
                                lines.append(f"    <title>{html.escape(prog.title)}</title>")
                                if prog.sub_title:
                                    lines.append(f"    <sub-title>{html.escape(prog.sub_title)}</sub-title>")
                                if prog.description:
                                    lines.append(f"    <desc>{html.escape(prog.description)}</desc>")
                                lines.append("  </programme>")
                            forwarded = True
                except Exception:
                    pass

        if not forwarded:
            epg_title = settings.get(f"multiview_{n}_epg_title", "").strip() or name
            epg_subtitle = settings.get(f"multiview_{n}_epg_subtitle", "").strip()
            categories_raw = settings.get(f"multiview_{n}_epg_categories", "")
            categories = [c.strip() for c in categories_raw.split(",") if c.strip()]
            channel_names = resolve_channel_names(settings, n)
            description = ", ".join(channel_names) if channel_names else name

            slot_start = window_start
            while slot_start < window_end:
                slot_end = min(slot_start + chunk, window_end)
                lines.append(
                    f'  <programme start="{_fmt_xmltv_time(slot_start)}"'
                    f' stop="{_fmt_xmltv_time(slot_end)}"'
                    f' channel="multiview_{n}">'
                )
                lines.append(f"    <title>{html.escape(epg_title)}</title>")
                if epg_subtitle:
                    lines.append(f"    <sub-title>{html.escape(epg_subtitle)}</sub-title>")
                lines.append(f"    <desc>{html.escape(description)}</desc>")
                for cat in categories:
                    lines.append(f"    <category>{html.escape(cat)}</category>")
                lines.append("  </programme>")
                slot_start = slot_end

    lines.append("</tv>")
    return "\n".join(lines) + "\n"


def generate_epg(settings: dict, plugin_dir: str) -> "int | None":
    """Write multiview_epg.xml and register it as an XMLTV EPGSource in Dispatcharr.

    Returns the EPGSource id (so the caller can refresh it in sequence after the
    M3U refresh - firing both refreshes at once collides on Dispatcharr's shared
    DB connection). Does NOT trigger the EPG refresh itself.
    """
    from django.utils import timezone
    from apps.epg.models import EPGSource

    mv_count = max(1, int(settings.get("multiview_count", 1)))

    now = timezone.now()
    window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = window_start + timedelta(days=14)

    xmltv = _build_xmltv(settings, mv_count, window_start, window_end)

    xml_path = os.path.join(plugin_dir, "multiview_epg.xml")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xmltv)

    source, _ = EPGSource.objects.update_or_create(
        name="Dispatcharr Multiview",
        defaults={
            "source_type": "xmltv",
            "url": "",
            "file_path": xml_path,
            "is_active": True,
        },
    )
    return source.id
