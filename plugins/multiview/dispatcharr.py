"""Thin wrappers over Dispatcharr's live-proxy internals.

The live tile encoder reads a real channel over HTTP from the realsrc endpoint;
this module is what that endpoint calls to produce the channel's MPEG-TS bytes.
It mirrors the init -> add_client -> get_buffer -> StreamGenerator -> cleanup
sequence of apps/proxy/live_proxy/views.py::stream_ts so the channel shows up in
Dispatcharr's stats and is torn down cleanly when the tile goes away.

All imports are deferred into the functions: this only ever runs inside the
Dispatcharr process, but the module must still be importable standalone (tests,
command builders) without Django configured.
"""

import logging
import uuid as _uuid

logger = logging.getLogger(__name__)

USER_AGENT = "multiview-plugin"
CLIENT_IP = "127.0.0.1"


def resolve_channel_uuid(value) -> "str | None":
    """Accept a Dispatcharr channel id (int/str pk) or a channel uuid, return the
    canonical channel uuid string.

    Dispatcharr's live proxy keys channels by uuid throughout (see
    url_utils.get_stream_info_for_switch -> get_object_or_404(Channel, uuid=...)),
    so the uuid is the identifier we must pass to live_stream, not the integer pk.
    """
    # Already a uuid?
    try:
        return str(_uuid.UUID(str(value)))
    except (TypeError, ValueError):
        pass
    # Otherwise treat it as an integer pk and look up the uuid.
    try:
        from apps.channels.models import Channel
        return str(Channel.objects.values_list("uuid", flat=True).get(id=int(value)))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"multiview: cannot resolve channel uuid for {value!r}: {e}")
        return None


def live_stream(channel_id):
    """Yield MPEG-TS chunks for a real Dispatcharr channel.

    Generator. Initializes the channel if needed, registers a client, and
    streams via StreamGenerator with channel_initializing=True (so Dispatcharr's
    own connect/buffer wait applies). Always removes the client on exit, whether
    the consumer disconnects (GeneratorExit) or the stream ends.
    """
    from apps.proxy.live_proxy.server import ProxyServer
    from apps.proxy.live_proxy.services.channel_service import ChannelService
    from apps.proxy.live_proxy.url_utils import get_stream_info_for_switch
    from apps.proxy.live_proxy.output.ts.generator import StreamGenerator

    info = get_stream_info_for_switch(channel_id)
    if not info or info.get("error"):
        err = (info or {}).get("error", "no stream info")
        logger.warning(f"multiview: channel {channel_id} unavailable: {err}")
        return

    ok = ChannelService.initialize_channel(
        channel_id,
        info["url"],
        info.get("user_agent"),
        transcode=info.get("transcode", False),
        stream_profile_value=info.get("stream_profile"),
        stream_id=info.get("stream_id"),
        m3u_profile_id=info.get("m3u_profile_id"),
        stream_name=info.get("stream_name"),
    )
    if not ok:
        logger.warning(f"multiview: initialize_channel failed for {channel_id}")
        return

    proxy = ProxyServer.get_instance()
    client_id = str(_uuid.uuid4())
    client_manager = proxy.client_managers.get(channel_id)
    if client_manager is None:
        logger.warning(f"multiview: no client manager for channel {channel_id}")
        return

    client_manager.add_client(
        client_id, CLIENT_IP,
        user_agent=USER_AGENT, user=None, output_format="mpegts",
    )

    try:
        buffer = proxy.get_buffer(channel_id)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"multiview: get_buffer failed for {channel_id}: {e}")
        _safe_remove(client_manager, client_id)
        return

    logger.info(f"multiview: streaming channel {channel_id} as client {client_id}")
    gen = StreamGenerator(
        channel_id, client_id, CLIENT_IP, USER_AGENT,
        channel_initializing=True, user=None, buffer=buffer,
    ).generate()

    try:
        for chunk in gen:
            if chunk:
                yield chunk
    finally:
        try:
            gen.close()
        except Exception:
            pass
        _safe_remove(client_manager, client_id)
        logger.info(f"multiview: channel {channel_id} client {client_id} closed")


def _safe_remove(client_manager, client_id) -> None:
    try:
        client_manager.remove_client(client_id)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"multiview: remove_client {client_id} failed: {e}")
