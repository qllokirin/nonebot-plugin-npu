from nonebot import logger, get_driver, require, get_bot, get_plugin_config

import os, shutil, json, asyncio, random, httpx, glob
from pathlib import Path
from .nwpu_query import NwpuQuery
from .draw_course_schedule_pic import check_if_course_schedule_only_one, get_all_lessons


async def test():
    """测试用函数 就不用每次都发消息测试了"""
    pass