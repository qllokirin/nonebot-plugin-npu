from nonebot import get_driver
from nonebot.plugin import PluginMetadata
from .config import Config
from nonebot.adapters.onebot.v11 import Bot, Event, MessageSegment
from nonebot.matcher import Matcher
from nonebot.params import ArgPlainText
from nonebot import on_command, get_bot
from nonebot.rule import to_me
from pathlib import Path
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot import require

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler
from nonebot import logger
import os
import shutil
from .nwpu_query import NwpuQuery
import json
from .utils import generate_img_from_html

__plugin_meta__ = PluginMetadata(
    name="npu",
    description="",
    usage="",
    config=Config,
)

global_config = get_driver().config
config = Config.parse_obj(global_config)

nwpu = on_command("翱翔", rule=to_me(), aliases={"npu", "nwpu"}, priority=10, block=True)
nwpu_query_class = None
folder_path = ""
account = None


@nwpu.handle()
async def handel_function(matcher: Matcher, event: Event, args: Message = CommandArg()):
    global folder_path
    global account
    global nwpu_query_class
    del nwpu_query_class
    nwpu_query_class = NwpuQuery()
    folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    account = []
    if msg := args.extract_plain_text():
        cookies_path = os.path.join(folder_path, 'cookies.txt')
        if os.path.isfile(cookies_path):
            await nwpu.send("正在登入翱翔门户")
            if nwpu_query_class.use_recent_cookies_login(cookies_path):
                if msg == "成绩":
                    sem_query_num = 1
                    await nwpu.send(f"正在获取最近一学期的成绩，请稍等")
                    _, grades = nwpu_query_class.get_grades(folder_path, sem_query_num)
                    pic_path = os.path.join(folder_path, 'grades.jpg')
                    generate_img_from_html(grades, folder_path)
                    await nwpu.send(MessageSegment.image(Path(pic_path)))
                    rank_msg, _ = nwpu_query_class.get_rank(folder_path)
                    await nwpu.finish(rank_msg)
                elif msg == "全部成绩":
                    await nwpu.send(f"正在获取全部成绩，请等待")
                    _, grades = nwpu_query_class.get_grades(folder_path)
                    pic_path = os.path.join(folder_path, 'grades.jpg')
                    generate_img_from_html(grades, folder_path)
                    await nwpu.finish(MessageSegment.image(Path(pic_path)))
                elif msg == "排名":
                    rank_msg, _ = nwpu_query_class.get_rank(folder_path)
                    await nwpu.finish(rank_msg)
                else:
                    await nwpu.finish("那是什么 我不知道\n"
                                      "可选指令：\n"
                                      "/翱翔成绩 or /翱翔排名\n"
                                      "/翱翔全部成绩")
            else:
                await nwpu.finish("登陆失败 cookie过期，请输入 /翱翔 进行登陆")
        else:
            await nwpu.finish("你还没有登陆过，请输入 /翱翔 进行登陆")
    else:
        logger.info("全新的账号正在登陆中")


@nwpu.got("account_infomation", prompt="请输入账号")
async def get_username(account_infomation: str = ArgPlainText()):
    account.append(account_infomation)
    if len(account) == 1:
        await nwpu.reject(f'请输入密码')
    elif len(account) == 2:
        # securephone是手机验证码 secureemail是邮箱验证码
        nwpu_query_class.login(account[0], account[1], "securephone")
        await nwpu.reject(f'登陆中....请输入验证码')
    elif len(account) == 3:
        await nwpu.send(f'正在输入验证码进行登陆')
        nwpu_query_class.verification_code_login(account[2], folder_path)
        await nwpu.send(f"正在获取全部成绩，请等待")
        _, grades = nwpu_query_class.get_grades(folder_path)
        pic_path = os.path.join(folder_path, 'grades.jpg')
        generate_img_from_html(grades, folder_path)
        await nwpu.send(MessageSegment.image(Path(pic_path)))
        rank_msg, _ = nwpu_query_class.get_rank(folder_path)
        await nwpu.send(rank_msg)


@scheduler.scheduled_job("cron", minute="*/1")
async def run_every_10_minutes_check_rank():
    # 获取全部已登陆的QQ号
    qq_all = []
    data_folder_path = os.path.join(os.path.dirname(__file__), 'data')
    if os.path.exists(data_folder_path):
        qq_all = [f for f in os.listdir(data_folder_path) if os.path.isdir(os.path.join(data_folder_path, f))]
        if qq_all:
            logger.info(f"已登录的全部QQ号：{qq_all}")
        else:
            logger.info("没有账号登陆")
    else:
        logger.info("没有data文件夹")
    # qq_all = [] # 若不想给所有的人都推送，硬编码改一下值即可 str类型

    for qq in qq_all:
        folder_path = os.path.join(os.path.dirname(__file__), 'data', qq)
        cookies_path = os.path.join(folder_path, 'cookies.txt')
        nwpu_query_class_sched = NwpuQuery()
        # 登陆
        if nwpu_query_class_sched.use_recent_cookies_login(cookies_path):
            # 先检测成绩变化
            logger.info(f"正在{qq}的检测成绩")
            with open((os.path.join(folder_path, 'grades.json')), 'r', encoding='utf-8') as f:
                grades_old = json.loads(f.read())
            _, grades = nwpu_query_class_sched.get_grades(folder_path)
            new_grades = [grade for grade in grades if grade not in grades_old]
            if new_grades:
                bot: Bot = get_bot()
                pic_path = os.path.join(folder_path, 'grades.jpg')
                generate_img_from_html(new_grades, folder_path)
                await bot.send_private_msg(user_id=int(qq), message=f"出新成绩啦")
                await bot.send_private_msg(user_id=int(qq), message=MessageSegment.image(Path(pic_path)))
            else:
                logger.info(f"{qq}的grades没变，没出新成绩")

            # 检测rank的变化
            with open((os.path.join(folder_path, 'rank.txt')), 'r', encoding='utf-8') as f:
                rank_old = f.read()
            rank_msg, rank = nwpu_query_class_sched.get_rank(folder_path)
            if str(rank_old) != str(rank):
                bot: Bot = get_bot()
                await bot.send_private_msg(user_id=int(qq),
                                           message=f"你的rank发生了变化,{rank_old}->{rank}\n{rank_msg}")
            else:
                logger.info(f"{qq}的rank没变，是{rank}")
        else:
            logger.error(f"{qq}的cookies失效了")
        del nwpu_query_class_sched
