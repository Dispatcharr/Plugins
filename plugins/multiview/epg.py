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


def _emit_custom_props(cp: dict, lines: list) -> None:
    """Append XMLTV inner elements derived from a ProgramData.custom_properties dict."""
    if not cp:
        return

    for cat in cp.get("categories") or []:
        lines.append(f"    <category>{html.escape(str(cat))}</category>")

    for kw in cp.get("keywords") or []:
        lines.append(f"    <keyword>{html.escape(str(kw))}</keyword>")

    # episode-num: custom_properties stores 1-based values; xmltv_ns is 0-based.
    season = cp.get("season")
    episode = cp.get("episode")
    if season is not None or episode is not None:
        s = (int(season) - 1) if season is not None else ""
        e = (int(episode) - 1) if episode is not None else ""
        lines.append(f'    <episode-num system="xmltv_ns">{s}.{e}.</episode-num>')
    if cp.get("onscreen_episode"):
        lines.append(f'    <episode-num system="onscreen">{html.escape(str(cp["onscreen_episode"]))}</episode-num>')
    if cp.get("dd_progid"):
        lines.append(f'    <episode-num system="dd_progid">{html.escape(str(cp["dd_progid"]))}</episode-num>')
    for ext_sys in ("thetvdb.com_id", "themoviedb.org_id", "imdb.com_id"):
        if cp.get(ext_sys):
            tag = ext_sys.replace("_id", "")
            lines.append(f'    <episode-num system="{tag}">{html.escape(str(cp[ext_sys]))}</episode-num>')

    if cp.get("date"):
        lines.append(f"    <date>{html.escape(str(cp['date']))}</date>")
    if cp.get("country"):
        lines.append(f"    <country>{html.escape(str(cp['country']))}</country>")
    if cp.get("language"):
        lines.append(f"    <language>{html.escape(str(cp['language']))}</language>")
    if cp.get("original_language"):
        lines.append(f"    <orig-language>{html.escape(str(cp['original_language']))}</orig-language>")

    if cp.get("icon"):
        lines.append(f'    <icon src="{html.escape(str(cp["icon"]))}"/>')

    for img in cp.get("images") or []:
        attrs = ""
        for attr in ("type", "size", "orient", "system"):
            if img.get(attr):
                attrs += f' {attr}="{html.escape(str(img[attr]))}"'
        if img.get("url"):
            lines.append(f"    <image{attrs}>{html.escape(str(img['url']))}</image>")

    if cp.get("rating"):
        sys_attr = f' system="{html.escape(str(cp["rating_system"]))}"' if cp.get("rating_system") else ""
        lines.append(f"    <rating{sys_attr}><value>{html.escape(str(cp['rating']))}</value></rating>")
    for sr in cp.get("star_ratings") or []:
        sys_attr = f' system="{html.escape(str(sr["system"]))}"' if sr.get("system") else ""
        lines.append(f"    <star-rating{sys_attr}><value>{html.escape(str(sr.get('value', '')))}</value></star-rating>")

    if cp.get("previously_shown"):
        details = cp.get("previously_shown_details") or {}
        attrs = ""
        if details.get("start"):
            attrs += f' start="{html.escape(str(details["start"]))}"'
        if details.get("channel"):
            attrs += f' channel="{html.escape(str(details["channel"]))}"'
        lines.append(f"    <previously-shown{attrs}/>")
    if cp.get("premiere"):
        text = cp.get("premiere_text") or ""
        lines.append(f"    <premiere>{html.escape(text)}</premiere>" if text else "    <premiere/>")
    if cp.get("new"):
        lines.append("    <new/>")
    if cp.get("live"):
        lines.append("    <live/>")
    if cp.get("last_chance"):
        text = cp.get("last_chance_text") or ""
        lines.append(f"    <last-chance>{html.escape(text)}</last-chance>" if text else "    <last-chance/>")

    length = cp.get("length")
    if length and length.get("value"):
        units_attr = f' units="{html.escape(str(length["units"]))}"' if length.get("units") else ""
        lines.append(f"    <length{units_attr}>{html.escape(str(length['value']))}</length>")

    video = cp.get("video")
    if video:
        lines.append("    <video>")
        for tag in ("present", "colour", "aspect", "quality"):
            if video.get(tag):
                lines.append(f"      <{tag}>{html.escape(str(video[tag]))}</{tag}>")
        lines.append("    </video>")

    audio = cp.get("audio")
    if audio:
        lines.append("    <audio>")
        for tag in ("present", "stereo"):
            if audio.get(tag):
                lines.append(f"      <{tag}>{html.escape(str(audio[tag]))}</{tag}>")
        lines.append("    </audio>")

    for sub in cp.get("subtitles") or []:
        type_attr = f' type="{html.escape(str(sub["type"]))}"' if sub.get("type") else ""
        lang = html.escape(str(sub["language"])) if sub.get("language") else ""
        inner = f"<language>{lang}</language>" if lang else ""
        lines.append(f"    <subtitles{type_attr}>{inner}</subtitles>")

    for review in cp.get("reviews") or []:
        attrs = ""
        for attr in ("type", "source", "reviewer"):
            if review.get(attr):
                attrs += f' {attr}="{html.escape(str(review[attr]))}"'
        content = html.escape(str(review.get("content", "")))
        lines.append(f"    <review{attrs}>{content}</review>")


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
                            ch_list = ", ".join(resolve_channel_names(settings, n))
                            for prog in programs:
                                lines.append(
                                    f'  <programme start="{_fmt_xmltv_time(prog.start_time)}"'
                                    f' stop="{_fmt_xmltv_time(prog.end_time)}"'
                                    f' channel="multiview_{n}">'
                                )
                                lines.append(f"    <title>{html.escape(prog.title or '')}</title>")
                                if prog.sub_title:
                                    lines.append(f"    <sub-title>{html.escape(prog.sub_title or '')}</sub-title>")
                                desc = prog.description or ""
                                if ch_list:
                                    desc = (desc + "\n(" + ch_list + ")") if desc else "(" + ch_list + ")"
                                if desc:
                                    lines.append(f"    <desc>{html.escape(desc)}</desc>")
                                _emit_custom_props(prog.custom_properties or {}, lines)
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
