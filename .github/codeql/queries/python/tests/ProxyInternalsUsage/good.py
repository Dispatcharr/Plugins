from apps.proxy.live_proxy.services.channel_service import ChannelService
from core.utils import RedisClient

client = RedisClient.get_client()
client.get("my_plugin:state")
ChannelService
