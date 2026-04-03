from nonebot import logger, get_driver, require, get_bot, get_plugin_config, on_notice
from nonebot.adapters.onebot.v11 import Bot, MessageSegment, Event
from nonebot.exception import MatcherException, ActionFailed

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_waiter")
require("nonebot_plugin_htmlkit")
from nonebot_plugin_htmlkit import html_to_pic
from nonebot_plugin_apscheduler import scheduler
import os, shutil, json, asyncio, random, httpx, glob, traceback
from datetime import datetime
from pathlib import Path
from .config import Config
from .nwpu_query import NwpuQuery
from .nwpu_electric import get_electric_left
from .draw_course_schedule_pic import check_if_course_schedule_only_one, get_all_lessons
from .draw_money_pic import draw_money_info_pic
from .utils import (
    generate_img_from_grades,
    generate_grades_to_msg,
    generate_money_to_msg,
    if_begin_lesson_day_is_tomorrow,
    get_exams_msg,
)

driver = get_driver()
global_config = get_plugin_config(Config)

@driver.on_bot_connect
async def connect():
    """bot接入 启动定时任务"""
    logger.info("bot接入，启动定时任务")
    job_ids = [
        "check_grades",
        "check_money",
        "check_electric"
    ]
    for job_id in job_ids:
        if global_config.npu_if_check_when_connect:
            job = scheduler.get_job(job_id)
            if job is None:
                logger.warning(f"任务 {job_id} 不存在")
            else:
                logger.debug(f"开始执行{job_id}定时任务")
                asyncio.create_task(job.func())

async def scheduled_job_base_task(func, begin_check_hour = None, end_check_hour = None):
    """
    定时任务基础函数
    """
    bot: Bot = get_bot()
    try:
        current_hour = datetime.now().hour
        if (
            (begin_check_hour is None or begin_check_hour <= current_hour)
            and (end_check_hour is None or current_hour < end_check_hour)
        ):
            # 获取全部已登陆的QQ号
            qq_all = []
            data_folder_path = Path(__file__).parent / "data"
            if data_folder_path.exists():
                qq_all = [
                    f.stem for f in data_folder_path.glob("*.json") if f.is_file()
                ]
                if qq_all:
                    logger.info(
                        f"已登录的全部QQ号：{qq_all}，正在检测{func.__name__}等相关信息"
                    )
                else:
                    logger.info("没有账号登陆")
            else:
                logger.info("没有data文件夹")
            tasks = [
                asyncio.create_task(check_base_task(func, qq, bot))
                for qq in qq_all
            ]
            await asyncio.gather(*tasks)
            logger.info(f"本次检测完毕")
        else:
            logger.info(f"bot失联或不在检测时间段中，不检测")
    except asyncio.CancelledError:
        logger.info("Ctrl-C被按下，结束定时任务")
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"定时任务出现错误{e!r}\n堆栈信息:\n{error_trace}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(
                    user_id=int(superuser),
                    message=MessageSegment.text(
                        f"{func.__name__}_scheduled定时任务 发生错误\n{e!r}\n堆栈信息:\n{error_trace}"
                    ),
                )

async def check_base_task(func, qq, bot):
    try:
        folder_path = Path(__file__).parent / "data"
        info_file_path = folder_path / f"{qq}.json"
        nwpu_query_class_sched = NwpuQuery(folder_path, info_file_path)
        if await nwpu_query_class_sched.use_recent_cookies_login():
            await func(qq, bot, nwpu_query_class_sched)
        else:
            logger.error(f"{qq}的cookies失效了,删除该信息")
            info_file_path.unlink(missing_ok=True)
            await bot.send_private_msg(
                user_id=int(qq),
                message=f"你的登陆信息已失效，请输入 翱翔 重新登陆",
            )
            logger.info(f"{qq}登录信息过期已推送")
        await nwpu_query_class_sched.close_client()
    except asyncio.CancelledError:
        logger.info("Ctrl-C被按下，结束定时任务")
        raise
    except (httpx.TimeoutException, httpx.ReadTimeout, httpx.ConnectTimeout):
        logger.error(f"{qq}的检测{func.__name__}定时任务Timeout")
        await nwpu_query_class_sched.close_client()
    except ActionFailed as e:
        logger.error(e.__dict__["info"]["message"])
        await nwpu_query_class_sched.close_client()
        if "发送失败，请先添加对方为好友" in e.__dict__["info"]["message"]:
            logger.info("对方已不是好友，删除该文件")
            info_file_path.unlink()
    except Exception as e:
        await nwpu_query_class_sched.close_client()
        if str(e) == "翱翔教务登录失败，状态码500":
            logger.error(
                "检测check_grades_and_ranks_and_exams定时任务请求超时，状态码500"
            )
            return
        error_trace = traceback.format_exc()
        logger.error(f"定时任务出现错误{e!r}\n堆栈信息:\n{error_trace}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(
                    user_id=int(superuser),
                    message=MessageSegment.text(
                        f"{qq}的检测check_grades_and_ranks_and_exams定时任务 发生错误\n{e!r}\n堆栈信息:\n{error_trace}"
                    )
                    + MessageSegment.image(
                        f"https://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640"
                    ),
                )

async def check_grades(qq, bot, nwpu_query_class_sched):
    logger.debug(f"正在检测{qq}的check_grades")
    if global_config.npu_if_check_grades:
        sleep_time = random.uniform(0, global_config.npu_check_time * 60)
        await asyncio.sleep(sleep_time)
        if "grades" in nwpu_query_class_sched.info:
            grades_old = nwpu_query_class_sched.info.get("grades", [])
            grades = await nwpu_query_class_sched.get_grades(False)
            new_grades = (
                [grade for grade in grades if grade not in grades_old]
                if grades and grades_old != []
                else []
            )
            if new_grades:
                grades_img_bytes = await generate_img_from_grades(
                    new_grades
                )
                grades_msg = generate_grades_to_msg(new_grades)
                logger.info(f"{qq}出新成绩啦")
                await bot.send_private_msg(
                    user_id=int(qq), message=f"出新成绩啦！\n{grades_msg}"
                )
                await bot.send_private_msg(
                    user_id=int(qq),
                    message=MessageSegment.image(grades_img_bytes),
                )
                logger.info(f"{qq}的新成绩已推送\n{grades_msg}")
        else:
            await nwpu_query_class_sched.get_grades()
    else:
        logger.info("未开启成绩检测，不检测")

# 定时任务 check_grades 检查成绩
@scheduler.scheduled_job("interval", minutes=global_config.npu_check_time, id="check_grades")
async def check_grades_scheduled():
    asyncio.create_task(scheduled_job_base_task(check_grades, global_config.npu_begin_check_hour, global_config.npu_end_check_hour))

async def check_electric(qq, bot, nwpu_query_class_sched):
    logger.debug(f"正在检测{qq}的check_electric")
    if "electric" in nwpu_query_class_sched.info:
        electric_information = nwpu_query_class_sched.info["electric"]
        sleep_time = random.uniform(0, global_config.npu_electric_check_time * 60)
        await asyncio.sleep(sleep_time)
        electric_left, information_all = await get_electric_left(
            electric_information["campus"],
            electric_information["building"],
            electric_information["room"],
        )
        logger.info(f"{qq}电费还剩{electric_left}")
        min_electric_left = 20
        if electric_left < min_electric_left:
            logger.info(f"{qq}电费小于{min_electric_left}，推送消息")
            await bot.send_private_msg(
                user_id=int(qq),
                message=f"{information_all}，电费不足{min_electric_left}，当前电费{electric_left}，请及时缴纳\n若不想收到提醒消息，可发送 翱翔电费解绑 进行解除绑定",
            )
# 定时任务 check_electric 检查电费
@scheduler.scheduled_job("cron", hour="12", id="check_electric")
async def check_electric_scheduled():
    asyncio.create_task(scheduled_job_base_task(check_electric))

async def check_money(qq, bot, nwpu_query_class_sched):
    logger.debug(f"正在检测{qq}的check_money")
    if global_config.npu_if_check_money:
        sleep_time = random.uniform(0, global_config.npu_check_money_time * 60)
        await asyncio.sleep(sleep_time)
        if "money" in nwpu_query_class_sched.info:
            money_old = nwpu_query_class_sched.info.get("money", [])
            money = await nwpu_query_class_sched.get_money()
            new_money = (
                [money_one for money_one in money if money_one not in money_old]
                if money and money_old != []
                else []
            )
            # 只保留年月与当前日期相等的
            new_money = (
                [money_one for money_one in new_money if money_one.get("nian") == datetime.now().strftime("%Y") and money_one.get("yue") == datetime.now().strftime("%m")]
                if new_money
                else []
            )
            if new_money:
                money_img_bytes = await draw_money_info_pic(new_money)
                money_msg = generate_money_to_msg(new_money)
                await bot.send_private_msg(
                    user_id=int(qq), message=f"发钱啦~😭\n{money_msg}"
                )
                await bot.send_private_msg(
                    user_id=int(qq),
                    message=MessageSegment.image(money_img_bytes),
                )
                logger.info(f"{qq}的money已推送\n{money_msg}")
        else:
            await nwpu_query_class_sched.get_money()
    else:
        logger.info("未开启money检测，不检测")

# 定时任务 check_money 检查money
@scheduler.scheduled_job("interval", minutes=global_config.npu_check_money_time, id="check_money")
async def check_money_scheduled():
    asyncio.create_task(scheduled_job_base_task(check_money, global_config.npu_begin_check_hour, global_config.npu_end_check_hour))