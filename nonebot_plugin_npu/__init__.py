from nonebot.plugin import PluginMetadata
from .config import Config

__plugin_meta__ = PluginMetadata(
    name="西工大翱翔门户成绩监控",
    description="翱翔门户成绩监控插件，能获取成绩、排名、绩点，当出现新成绩时推送给使用者",
    usage="https://github.com/qllokirin/nonebot-plugin-npu/blob/master/README.md",
    type="application",
    homepage="https://github.com/qllokirin/nonebot-plugin-npu",
    supported_adapters={"~onebot.v11"},
    config=Config,
)

from . import command
from . import schedule
