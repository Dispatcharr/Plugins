from apps.proxy.live_proxy.services.channel_service import ChannelService
from apps.proxy.ts_proxy.services.channel_service import ChannelService as LegacyService

ChannelService._update_stream_stats_in_db(1)
LegacyService._update_stream_stats_in_db(2)
