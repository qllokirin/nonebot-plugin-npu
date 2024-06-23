from nonebot import get_driver
from nonebot.plugin import PluginMetadata
from .config import Config
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment, MessageEvent ,GroupMessageEvent, PrivateMessageEvent
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
import asyncio
from typing import Any, List, Tuple, Union
from .utils import generate_img_from_html
from .utils import generate_grades_to_msg
from .utils import get_exams_msg
from .nwpu_electric import get_campaus,get_building,get_room,get_electric_left

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-npu",
    description="",
    usage="",
    config=Config,
)
driver = get_driver()
global_config = driver.config
config = Config.parse_obj(global_config)

nwpu = on_command("翱翔", rule=to_me(), aliases={"npu", "nwpu"}, priority=10, block=True)
nwpu_query_class = None
folder_path = ""
account = None

async def send_forward_msg(
    bot: Bot,
    event: MessageEvent,
    name: str,
    uin: str,
    user_message: List[Message],
):
    def to_json(info: Message):
        return {
            "type": "node",
            "data": {"name": name, "uin": uin, "content": info},
        }

    messages = [to_json(info) for info in user_message]
    if isinstance(event, GroupMessageEvent):
        return await bot.call_api(
            "send_group_forward_msg", group_id=event.group_id, messages=messages
        )
    else:
        return await bot.call_api(
            "send_private_forward_msg", user_id=event.user_id, messages=messages
        )


async def send_private_forward_msg(
    bot: Bot,
    user_id: str,
    name: str,
    uin: str,
    user_message: List[Message],
):
    def to_json(info: Message):
        return {
            "type": "node",
            "data": {"name": name, "uin": uin, "content": info},
        }

    messages = [to_json(info) for info in user_message]
    return await bot.call_api(
        "send_private_forward_msg", user_id=user_id, messages=messages
    )

@nwpu.handle()
async def handel_function(bot: Bot,matcher: Matcher, event: Union[PrivateMessageEvent, GroupMessageEvent], args: Message = CommandArg()):
    global folder_path
    global account
    global nwpu_query_class
    del nwpu_query_class
    nwpu_query_class = NwpuQuery()
    folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
    account = []
    if msg := args.extract_plain_text():
        cookies_path = os.path.join(folder_path, 'cookies.txt')
        if os.path.isfile(cookies_path):
            if msg == "排考" or msg == "考试" or msg == "排考信息" or msg == "考试信息":
                if get_exams_msg(folder_path):
                    await nwpu.finish("你的全部未结束考试有：\n"+ get_exams_msg(folder_path))
                else:
                    await nwpu.finish("暂无考试")
            else:
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
                        await nwpu.send(rank_msg)
                        await nwpu.finish()
                    elif msg == "全部成绩":
                        await nwpu.send(f"正在获取全部成绩，请等待")
                        _, grades = nwpu_query_class.get_grades(folder_path)
                        pic_path = os.path.join(folder_path, 'grades.jpg')
                        generate_img_from_html(grades, folder_path)
                        await nwpu.send(MessageSegment.image(Path(pic_path)))
                        await nwpu.finish()
                    elif msg == "排名":
                        rank_msg, _ = nwpu_query_class.get_rank(folder_path)
                        await nwpu.finish(rank_msg)
                    elif msg == "全部排考" or msg == "全部考试" or msg == "全部排考信息" or msg == "全部考试信息":
                        await nwpu.send(f"正在获取全部考试信息，请等待")
                        exams_msg, _ = nwpu_query_class.get_exams(folder_path, True)
                        if exams_msg:
                            exams_msg, _ = nwpu_query_class.get_exams(folder_path, False)
                            await nwpu.finish()
                        else:
                            await nwpu.finish("暂无考试")
                    else:
                        await nwpu.finish("那是什么 我不知道\n"
                                        "发送 help 可获取全部指令")
                else:
                    shutil.rmtree(folder_path)
                    await nwpu.finish("登陆失败 cookie过期，请输入 /翱翔 进行登陆")
        else:
            await nwpu.finish("你还没有登陆过，请输入 /翱翔 进行登陆")
    else:
        logger.info("全新的账号正在登陆中")


@nwpu.got("account_infomation", prompt="请选择登陆方式\n1->账号密码手机验证码登录\n2->账号密码邮箱验证码登录\n3->扫码登录\n登录成功后会自动检测是否有新成绩，但若选择扫码登录，一天后登陆凭证会失效，无法长期监测新成绩\n\n会收集必要的信息用于持久登陆和成绩检测，继续登陆代表你已同意")
async def get_username(bot : Bot,event: Event, account_infomation: str = ArgPlainText()):
    account.append(account_infomation)
    folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
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
            await nwpu.send(f"登陆成功！正在获取全部成绩，请稍等")
            _, grades = nwpu_query_class.get_grades(folder_path)
            pic_path = os.path.join(folder_path, 'grades.jpg')
            generate_img_from_html(grades, folder_path)
            await nwpu.send(MessageSegment.image(Path(pic_path)))
            rank_msg, _ = nwpu_query_class.get_rank(folder_path)
            await nwpu.send(rank_msg)
            exams_msg, _ = nwpu_query_class.get_exams(folder_path)
            exams_msg = ("你的考试有：\n" + exams_msg) if exams_msg else "暂无考试"
            await nwpu.send(exams_msg)
            await nwpu.finish()
        elif status == 3:
            account.pop()
            await nwpu.reject(f'验证码错误，请重新输入验证码\n输入 停止 可以终止此次登陆')
        else:
            await nwpu.finish(f'出错了，返回状态码{status}，此次登陆已终止')

# bot是否在线 最开始启动时是离线的 与ws握手成功后变为True,断连后变为False
if_connected = False
@run_sync
def get_grades_and_ranks_and_exams():
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
    exams_change = []
    failure_qq = []

    for qq in qq_all:
        folder_path = os.path.join(os.path.dirname(__file__), 'data', qq)
        cookies_path = os.path.join(folder_path, 'cookies.txt')
        nwpu_query_class_sched = NwpuQuery()
        # 登陆
        if nwpu_query_class_sched.use_recent_cookies_login(cookies_path) and if_connected:
            # 先检测成绩变化
            if os.path.exists(os.path.join(folder_path, 'grades.json')):
                with open((os.path.join(folder_path, 'grades.json')), 'r', encoding='utf-8') as f:
                    grades_old = json.loads(f.read())
                _, grades = nwpu_query_class_sched.get_grades(folder_path)
                new_grades = [grade for grade in grades if grade not in grades_old]
                if new_grades:
                    pic_path = os.path.join(folder_path, 'grades.jpg')
                    generate_img_from_html(new_grades, folder_path)
                    grades_change.append([qq, pic_path, generate_grades_to_msg(new_grades)])
                    logger.info(f"{qq}出新成绩啦")
            else:
                nwpu_query_class_sched.get_grades(folder_path)

            # 检测rank的变化
            if os.path.exists(os.path.join(folder_path, 'rank.txt')):
                with open((os.path.join(folder_path, 'rank.txt')), 'r', encoding='utf-8') as f:
                    rank_old = f.read()
                rank_msg, rank = nwpu_query_class_sched.get_rank(folder_path)
                if str(rank_old) != str(rank):
                    ranks_change.append([qq, rank_old, rank, rank_msg])
                    logger.info(f"{qq}的rank变化啦")
            else:
                nwpu_query_class_sched.get_rank(folder_path)
            
            # 检测考试变化
            if os.path.exists(os.path.join(folder_path, 'exams.json')):
                with open((os.path.join(folder_path, 'exams.json')), 'r', encoding='utf-8') as f:
                    exams_old = json.loads(f.read())
                exams_msg, exams = nwpu_query_class_sched.get_exams(folder_path)
                new_exams = [exam for exam in exams if exam not in exams_old]
                if new_exams:
                    exams_change.append([qq, new_exams, exams_msg])
                    logger.info(f"{qq}出新考试啦")
            else:
                nwpu_query_class_sched.get_exams(folder_path)
        else:
            logger.error(f"{qq}的cookies失效了,删除该文件夹")
            failure_qq.append(qq)
            shutil.rmtree(folder_path)
        del nwpu_query_class_sched
    return grades_change, ranks_change, exams_change, failure_qq


@driver.on_bot_disconnect
async def disconnect():
    """bot断连 暂停定时任务"""
    global if_connected
    if_connected = False
    logger.info("bot失联，关闭定时任务")
    scheduler.pause_job('check_new_info')
    scheduler.pause_job('check_power')


@driver.on_bot_connect
async def connect():
    """bot接入 启动定时任务"""
    global if_connected
    if_connected = True
    logger.info("bot接入，启动定时任务")
    scheduler.resume_job('check_new_info')
    scheduler.resume_job('check_power')

@scheduler.scheduled_job("cron", minute="*/15",id="check_new_info")
async def every_15_minutes_check():
    """
    定时任务 检测新成绩/rank/考试
    """
    if if_connected:
        bot: Bot = get_bot()
        grades_change, ranks_change, exams_change, failure_qq = await get_grades_and_ranks_and_exams()
        for qq, pic_path, grades_msg in grades_change:
            # 图片有拦截风险 故文字和图片版一起发
            await bot.send_private_msg(user_id=int(qq), message=f"出新成绩啦！\n{grades_msg}")
            await asyncio.sleep(2)
            await bot.send_private_msg(user_id=int(qq), message=MessageSegment.image(Path(pic_path)))
            await asyncio.sleep(2)
            await asyncio.sleep(2)
        for qq, rank_old, rank, rank_msg in ranks_change:
            await bot.send_private_msg(user_id=int(qq),
                                    message=f"你的rank发生了变化,{rank_old}->{rank}\n{rank_msg}")
            await asyncio.sleep(2)
            await asyncio.sleep(2)
        for qq, new_exams, exams_msg in exams_change:
            new_courses = [new_exam['course'] for new_exam in new_exams]
            new_course_msg = ""
            for new_course in new_courses:
                new_course_msg += new_course + "\n"
            new_course_msg = new_course_msg[:-1]
            await bot.send_private_msg(user_id=int(qq),
                                    message=f"你有新的考试有：\n"+new_course_msg)
            await asyncio.sleep(2)
            await bot.send_private_msg(user_id=int(qq),
                                    message=f"你的全部未结束考试有：\n"+exams_msg)
            await asyncio.sleep(2)
            await asyncio.sleep(2)
        for qq in failure_qq:
            await bot.send_private_msg(user_id=int(qq), message=f"你的登陆信息已失效，请输入 /翱翔 重新登陆")
        logger.info(f"本次检测完毕")
    else:
        logger.info(f"bot失联，不检测")

nwpu_electric = on_command("翱翔电费", rule=to_me(), priority=10, block=True)

electric_msg = []
campaus_all = None
@nwpu_electric.handle()
async def handel_function(matcher: Matcher, event: Event, args: Message = CommandArg()):
    global campaus_all
    global electric_msg
    folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    electric_msg = []
    if msg := args.extract_plain_text():
        if msg == "查询":
            folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
            electric_path = os.path.join(folder_path, 'electric.json')
            if os.path.exists(electric_path):
                with open(electric_path, 'r', encoding='utf-8') as f:
                    electric_information = json.loads(f.read())
                electric_left = get_electric_left(electric_information['campaus'],electric_information['building'],electric_information['room'])
                await nwpu_electric.finish(f'电费剩余{electric_left}')
            else:
                await nwpu_electric.finish(f'暂未绑定宿舍\n请输入 /翱翔电费绑定 进行绑定')
        elif msg == "绑定":
            logger.info("绑定新的宿舍")
            msg,campaus_all = get_campaus()
            await nwpu_electric.send(msg)
        else:
            await nwpu_electric.finish("请输入 /翱翔电费绑定 进行绑定 \n或者/翱翔电费查询 进行电费查询")
    else:
        await nwpu_electric.finish("请输入 /翱翔电费绑定 进行绑定 \n或者/翱翔电费查询 进行电费查询")
        
building_all = None
room_all = None
@nwpu_electric.got("electric_information", prompt="请选择校区")
async def get_electric_information(bot: Bot, event: Event, electric_information: str = ArgPlainText()):
    global building_all
    global room_all
    electric_msg.append(electric_information)
    folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
    if len(electric_msg) == 1:
        electric_msg[0] = campaus_all[int(electric_msg[0])]['value']
        msg_list,building_all = get_building(electric_msg[0])
        msg_all = []
        for msg in msg_list:
            msg_all.append(MessageSegment.text(msg))
        await send_forward_msg(bot, event, "防tx吞消息楼，里外是一样的", str(event.self_id), msg_all)
        await nwpu_electric.reject()
    elif len(electric_msg) == 2:
        electric_msg[1] = building_all[int(electric_msg[1])]['value']
        msg_list,room_all = get_room(electric_msg[0],electric_msg[1])
        msg_all = []
        for msg in msg_list:
            msg_all.append(MessageSegment.text(msg))
        await send_forward_msg(bot, event, "防tx吞消息楼，里外是一样的", str(event.self_id), msg_all)
        await nwpu_electric.reject()
    elif len(electric_msg) == 3:
        electric_msg[2] = room_all[int(electric_msg[2])]['value']
        data = {'campaus':electric_msg[0],'building':electric_msg[1],'room':electric_msg[2]}
        electric_left = get_electric_left(electric_msg[0],electric_msg[1],electric_msg[2])
        with open(os.path.join(folder_path, 'electric.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False, )
        await nwpu_electric.send(f'当前剩余电量：{electric_left}')
        await nwpu_electric.finish("每天会自动定时查询，电费小于25时会自动提示充值")

@run_sync
def get_nwpu_electric():
    logger.info('检查宿舍电费')
    qq_all = []
    data_folder_path = os.path.join(os.path.dirname(__file__), 'data')
    if os.path.exists(data_folder_path):
        qq_all = [f for f in os.listdir(data_folder_path) if os.path.exists(os.path.join(data_folder_path, f, 'electric.json'))]
        if qq_all:
            logger.info(f"已绑定宿舍的全部QQ号：{qq_all}")
        else:
            logger.info("没有账号绑定")
    else:
        logger.info("没有data文件夹")
    
    electric_all = []
    for qq in qq_all:
        folder_path = os.path.join(os.path.dirname(__file__), 'data', qq)
        electric_path = os.path.join(folder_path, 'electric.json')
        with open(electric_path, 'r', encoding='utf-8') as f:
            electric_information = json.loads(f.read())
        electric_left = get_electric_left(electric_information['campaus'],electric_information['building'],electric_information['room'])
        logger.info(f'{qq}电费还剩{electric_left}')
        if electric_left < 25:
            electric_all.append([qq,electric_left])
    return electric_all

@scheduler.scheduled_job("cron", hour="12", id="check_power")
async def every_15_20_check():
    electric_all = await get_nwpu_electric()
    for qq,electric_left in electric_all:
        bot: Bot = get_bot()
        await bot.send_private_msg(user_id=int(qq), message=f"电费不足25，当前电费{electric_left}，请及时缴纳")
        await asyncio.sleep(2)
    