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
from nonebot.utils import run_sync

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler
from nonebot import logger
import os
import shutil
from .nwpu_query import NwpuQuery
import json
from .utils import generate_img_from_html

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-npu",
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


@nwpu.got("account_infomation", prompt="请选择登陆方式\n1->账号密码手机验证码登录\n2->账号密码邮箱验证码登录\n3->扫码登录")
async def get_username(event: Event, account_infomation: str = ArgPlainText()):
    account.append(account_infomation)
    folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
    if len(account) == 1:
        if account[0] == "3":
            account.append("")
        elif account[0] == "1" or account[0] == "2":
            await nwpu.reject(f'请输入账号')
        else:
            account.pop()
            await nwpu.reject('回复错误，请重新回复')
    if len(account) == 2:
        if int(account[0]) == 1 or int(account[0]) == 2:
            await nwpu.reject(f'请输入密码')
        elif int(account[0]) == 3:
            account.append("")
        else:
            await nwpu.finish(f'没有这个登陆方式，此次登陆已终止')
    if len(account) == 3:
        if account[-1] == "停止":
            await nwpu.finish(f'此次登陆已终止')
        if int(account[0]) == 1 or int(account[0]) == 2:
            await nwpu.send("正在登陆中...")
        elif int(account[0]) == 3:
            await nwpu.send("正在发送二维码...")
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        ways = ["securephone", "secureemail", "qr"]
        status = nwpu_query_class.login(account[1], account[2], ways[int(account[0])-1], folder_path)
        if status == "wating_to_scan_qr":
            await nwpu.send(MessageSegment.image(Path(os.path.join(folder_path, 'qr.png'))))
            if nwpu_query_class.wating_to_scan_qr(folder_path):
                await nwpu.send(f'扫码登录成功')
                account.append("")
            else:
                await nwpu.finish(f'扫码出错，时间超时过期or其他原因，此次登陆已终止')
        elif status == 0:
            await nwpu.reject(f'登陆中...请输入验证码')
        elif status == -1:
            account.pop()
            await nwpu.reject(f'密码错误，请重新输入密码\n输入 停止 可以终止此次登陆\n多次连续四次密码错误会导致账号锁定，可以在锁定输停止进行重开')
        else:
            await nwpu.finish(f'出错了，返回状态码{status}，此次登陆已终止')
    if len(account) == 4:
        if account[-1] == "停止":
            await nwpu.finish(f'此次登陆已终止')
        if int(account[0]) == 1 or int(account[0]) == 2:
            await nwpu.send(f'正在输入验证码进行登陆')
            status = nwpu_query_class.verification_code_login(account[3], folder_path)
        elif int(account[0]) == 3:
            status = 2
        if status == 2:
            await nwpu.send(f"正在获取全部成绩，请稍等")
            _, grades = nwpu_query_class.get_grades(folder_path)
            pic_path = os.path.join(folder_path, 'grades.jpg')
            generate_img_from_html(grades, folder_path)
            await nwpu.send(MessageSegment.image(Path(pic_path)))
            rank_msg, _ = nwpu_query_class.get_rank(folder_path)
            await nwpu.finish(rank_msg)
        elif status == 3:
            account.pop()
            await nwpu.reject(f'验证码错误，请重新输入验证码\n输入 停止 可以终止此次登陆')
        else:
            await nwpu.finish(f'出错了，返回状态码{status}，此次登陆已终止')

@run_sync
def get_grades_and_ranks():
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

    grades_change = []
    ranks_change = []

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
                pic_path = os.path.join(folder_path, 'grades.jpg')
                generate_img_from_html(new_grades, folder_path)
                grades_change.append([qq, pic_path])
            else:
                logger.info(f"{qq}的grades没变，没出新成绩")

            # 检测rank的变化
            with open((os.path.join(folder_path, 'rank.txt')), 'r', encoding='utf-8') as f:
                rank_old = f.read()
            rank_msg, rank = nwpu_query_class_sched.get_rank(folder_path)
            if str(rank_old) != str(rank):
                ranks_change.append([qq, rank_old, rank, rank_msg])
            else:
                logger.info(f"{qq}的rank没变，是{rank}")
        else:
            logger.error(f"{qq}的cookies失效了")
        del nwpu_query_class_sched
    return grades_change, ranks_change

@scheduler.scheduled_job("cron", minute="*/15")
async def every_15_minutes_check():
    grades_change, ranks_change = await get_grades_and_ranks()
    for qq, pic_path in grades_change:
        bot: Bot = get_bot()
        await bot.send_private_msg(user_id=int(qq), message=f"出新成绩啦")
        await bot.send_private_msg(user_id=int(qq), message=MessageSegment.image(Path(pic_path)))
    for qq, rank_old, rank, rank_msg in ranks_change:
        bot: Bot = get_bot()
        await bot.send_private_msg(user_id=int(qq),
                                   message=f"你的rank发生了变化,{rank_old}->{rank}\n{rank_msg}")