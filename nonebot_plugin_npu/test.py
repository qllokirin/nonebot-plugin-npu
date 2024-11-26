from nonebot import logger, get_driver, require, on_command, on_type, get_bot, get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment, MessageEvent, GroupMessageEvent, \
    PrivateMessageEvent, PokeNotifyEvent
from nonebot.matcher import Matcher
from nonebot.params import ArgPlainText, CommandArg
from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.utils import run_sync
from nonebot.exception import MatcherException, ActionFailed

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_waiter")
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_waiter import waiter, prompt
import os, shutil, json, asyncio, random, httpx, glob
from datetime import datetime
from typing import List, Union
from pathlib import Path
from .config import Config
from .nwpu_query import NwpuQuery
from .utils import generate_img_from_html, generate_grades_to_msg, get_exams_msg, if_begin_lesson_day_is_tomorrow
from .nwpu_electric import get_campus, get_building, get_room, get_electric_left
from .draw_course_schedule_pic import check_if_course_schedule_only_one, draw_course_schedule_pic


async def test():
    """测试用函数 就不用每次都发消息测试了"""
    pass
    # nwpu_query_class = NwpuQuery()
    # folder_path = os.path.join(os.path.dirname(__file__), 'data', '2456590695')
    # cookies_path = os.path.join(folder_path, 'cookies.txt')
    # if os.path.isfile(cookies_path):
    #         if await nwpu_query_class.use_recent_cookies_login(cookies_path):
    #             if os.path.isfile(os.path.join(folder_path, 'info.json')):
    #                 with open((os.path.join(folder_path, 'info.json')), 'r', encoding='utf-8') as f:
    #                     nwpu_query_class.student_assoc = json.loads(f.read())["student_assoc"]
    #             else:
    #                 if not await nwpu_query_class.get_student_assoc(folder_path):
    #                     logger.error(f"获取信息失败")
    #                     raise Exception("获取信息失败")
    #             if await check_if_course_schedule_only_one(folder_path):
    #                 pass
    #                 # await nwpu.send("检测到已存在课表文件，生成图片中...")
    #             else:
    #                 # await nwpu.send("没有课表文件或有多个课表文件，正在获取课表，请稍等")
    #                 await nwpu_query_class.get_course_table(folder_path)
    #             course_schedule_path = await draw_course_schedule_pic(folder_path)
    #             print(course_schedule_path)
    #             # await nwpu.finish(MessageSegment.image(Path(course_schedule_path)))
