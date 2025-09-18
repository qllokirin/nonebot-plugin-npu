from nonebot import logger, get_driver, require, get_bot, get_plugin_config, on_notice
from nonebot.adapters.onebot.v11 import Bot, MessageSegment, Event
from nonebot.exception import MatcherException, ActionFailed

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_waiter")
from nonebot_plugin_apscheduler import scheduler
import os, shutil, json, asyncio, random, httpx, glob, traceback
from datetime import datetime
from pathlib import Path
from .config import Config
from .nwpu_query import NwpuQuery
from .nwpu_electric import get_electric_left
from .draw_course_schedule_pic import check_if_course_schedule_only_one, get_all_lessons
from .utils import (
    generate_img_from_grades,
    generate_grades_to_msg,
    if_begin_lesson_day_is_tomorrow,
    get_exams_msg,
)

driver = get_driver()
global_config = get_plugin_config(Config)

# bot是否在线 最开始启动时是离线的 与ws握手成功后变为True,断连后变为False
if_connected = False


offline = on_notice(priority=1, block=False)


@offline.handle()
async def _(event: Event):
    global if_connected
    if event.get_event_name() == "notice.bot_offline":
        if_connected = False


@driver.on_bot_disconnect
async def disconnect():
    """bot断连 暂停定时任务"""
    global if_connected
    if_connected = False
    logger.info("bot失联，关闭定时任务")
    job_ids = [
        "check_power",
        "check_new_info",
        "check_course_schedule",
        "check_new_lesson_begin_tomorrow",
    ]
    for job_id in job_ids:
        if scheduler.get_job(job_id) is not None:
            scheduler.pause_job(job_id)


@driver.on_bot_connect
async def connect():
    """bot接入 启动定时任务"""
    global if_connected
    if_connected = True
    logger.info("bot接入，启动定时任务")
    scheduler.resume_job("check_power")
    scheduler.resume_job("check_new_info")
    scheduler.resume_job("check_course_schedule")
    scheduler.resume_job("check_new_lesson_begin_tomorrow")
    if global_config.npu_if_check_when_connect:
        await scheduler.get_job("check_power").func()
        await scheduler.get_job("check_new_info").func()
        await scheduler.get_job("check_course_schedule").func()
        await scheduler.get_job("check_new_lesson_begin_tomorrow").func()


async def check_grades_and_ranks_and_exams(qq, bot):
    try:
        folder_path = Path(__file__).parent / "data"
        info_file_path = folder_path / f"{qq}.json"
        nwpu_query_class_sched = NwpuQuery(folder_path, info_file_path)
        # 留2分钟空闲时间
        sleep_time = random.uniform(
            0,
            (
                (global_config.npu_check_time - 2) * 60
                if global_config.npu_check_time >= 2
                else 0
            ),
        )
        await asyncio.sleep(sleep_time)
        grades_change = []
        ranks_change = []
        exams_change = []

        if if_connected:
            if await nwpu_query_class_sched.use_recent_cookies_login():
                # 先检测成绩变化
                if global_config.npu_if_check_grades:
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
                # 检测rank的变化
                # 已陨落

                # 检测考试变化
                if global_config.npu_if_check_exams:
                    if "exams" in nwpu_query_class_sched.info:
                        exams_old = nwpu_query_class_sched.info.get("exams", [])
                        exams = await nwpu_query_class_sched.get_exams()
                        new_exams = [exam for exam in exams if exam not in exams_old]
                        if new_exams:
                            logger.info(f"{qq}出新考试啦")
                            new_courses = [new_exam["course"] for new_exam in new_exams]
                            new_course_msg = ""
                            for new_course in new_courses:
                                new_course_msg += new_course + "\n"
                            new_course_msg = new_course_msg[:-1]
                            await bot.send_private_msg(
                                user_id=int(qq),
                                message=f"你有新的考试有：\n" + new_course_msg,
                            )
                            await bot.send_private_msg(
                                user_id=int(qq),
                                message=f"你的全部未结束考试有：\n"
                                + get_exams_msg(exams),
                            )
                            logger.info(f"{qq}的新考试已推送\n{new_course_msg}")
                    else:
                        await nwpu_query_class_sched.get_exams()
            else:
                logger.error(f"{qq}的cookies失效了,删除该信息")
                if "electric_information" in nwpu_query_class_sched.info:
                    info = {
                        "electric_information": nwpu_query_class_sched.info[
                            "electric_information"
                        ]
                    }
                    info_file_path.write_text(
                        json.dumps(info, indent=4, ensure_ascii=False), encoding="utf-8"
                    )
                else:
                    info_file_path.unlink(missing_ok=True)
                await bot.send_private_msg(
                    user_id=int(qq),
                    message=f"你的登陆信息已失效，请输入 翱翔 重新登陆",
                )
                logger.info(f"{qq}登录信息过期已推送")
        else:
            logger.info("bot失联，终止更新")
        await nwpu_query_class_sched.close_client()
    except (httpx.TimeoutException, httpx.ReadTimeout, httpx.ConnectTimeout):
        logger.error(f"{qq}的检测check_grades_and_ranks_and_exams定时任务Timeout")
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


@scheduler.scheduled_job(
    "interval", minutes=global_config.npu_check_time, id="check_new_info"
)
async def check_grades_and_ranks_and_exams_scheduled():
    """
    定时任务 检测新成绩/考试
    """
    bot: Bot = get_bot()
    try:
        current_hour = datetime.now().hour
        if (
            if_connected
            and global_config.npu_begin_check_hour
            <= current_hour
            < global_config.npu_end_check_hour
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
                        f"已登录的全部QQ号：{qq_all} 开始检查是否有成绩/排名/考试变动"
                    )
                else:
                    logger.info("没有账号登陆")
            else:
                logger.info("没有data文件夹")
            tasks = [
                asyncio.create_task(check_grades_and_ranks_and_exams(qq, bot))
                for qq in qq_all
            ]
            await asyncio.gather(*tasks)
            logger.info(f"本次检测完毕")
        else:
            logger.info(f"bot失联或不在检测时间段中，不检测")
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"定时任务出现错误{e!r}\n堆栈信息:\n{error_trace}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(
                    user_id=int(superuser),
                    message=MessageSegment.text(
                        f"check_grades_and_ranks_and_exams_scheduled定时任务 发生错误\n{e!r}\n堆栈信息:\n{error_trace}"
                    ),
                )


async def check_new_lesson_begin_tomorrow(qq, bot):
    try:
        folder_path = Path(__file__).parent / "data"
        info_file_path = folder_path / f"{qq}.json"
        sleep_time = random.uniform(0, 60 * 60)
        await asyncio.sleep(sleep_time)
        data = json.loads(
            json.loads(info_file_path.read_text(encoding="utf-8")).get(
                "course_table", ""
            )
        )
        if msg := if_begin_lesson_day_is_tomorrow(data):
            await bot.send_private_msg(
                user_id=int(qq), message=f"明天有新课程开课，别忘记啦\n\n{msg}"
            )
            logger.info(f"{qq}明天有新课程\n{msg}\n已推送")
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"定时任务出现错误{e!r}\n堆栈信息:\n{error_trace}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(
                    user_id=int(superuser),
                    message=MessageSegment.text(
                        f"{qq}的检测check_new_lesson_begin_tomorrow定时任务 发生错误\n{e!r}\n堆栈信息:\n{error_trace}"
                    )
                    + MessageSegment.image(
                        f"https://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640"
                    ),
                )


@scheduler.scheduled_job("cron", hour="19", id="check_new_lesson_begin_tomorrow")
async def check_new_lesson_begin_tomorrow_scheduled():
    """
    检测明天是否有课程
    """
    bot: Bot = get_bot()
    try:
        # 获取全部已登陆的QQ号
        qq_all = []
        data_folder_path = Path(__file__).parent / "data"
        if data_folder_path.exists():
            qq_all = [f.stem for f in data_folder_path.glob("*.json") if f.is_file()]
            if qq_all:
                logger.info(f"已登录的全部QQ号：{qq_all} 开始检查明天是否有新开课程")
            else:
                logger.info("没有账号登陆")
        else:
            logger.info("没有data文件夹")
        tasks = [
            asyncio.create_task(check_new_lesson_begin_tomorrow(qq, bot))
            for qq in qq_all
        ]
        await asyncio.gather(*tasks)
        logger.info(f"本次新课程检测完毕")
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"定时任务出现错误{e!r}\n堆栈信息:\n{error_trace}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(
                    user_id=int(superuser),
                    message=MessageSegment.text(
                        f"check_new_lesson_begin_tomorrow_scheduled定时任务 发生错误\n{e!r}\n堆栈信息:\n{error_trace}"
                    ),
                )


async def check_course_schedule(qq, bot):
    try:
        folder_path = Path(__file__).parent / "data"
        info_file_path = folder_path / f"{qq}.json"
        nwpu_query_class_sched = NwpuQuery(folder_path, info_file_path)
        course_table_str_old = json.loads(
            info_file_path.read_text(encoding="utf-8")
        ).get("course_table", "")
        sleep_time = random.uniform(0, 60 * 60 * 2)
        await asyncio.sleep(sleep_time)
        if if_connected and global_config.npu_if_check_course_schedule:
            if await nwpu_query_class_sched.use_recent_cookies_login():
                if "course_table" in nwpu_query_class_sched.info:
                    lessons_data_old, _ = get_all_lessons(course_table_str_old)
                    course_table_str_new = (
                        await nwpu_query_class_sched.get_course_table()
                    )
                    lessons_data, _ = get_all_lessons(course_table_str_new)
                    lessons_data_new = (
                        [
                            course
                            for course in lessons_data
                            if course not in lessons_data_old
                        ]
                        if lessons_data
                        else []
                    )
                    if lessons_data_new:
                        logger.info(f"{qq}课表有变化啦")
                        msg = "有课表变动/新课程，变动后课程信息/新课程信息如下，需自行对比查看\n（也可能是机器人误报）\n\n"
                        for course in lessons_data_new:
                            msg += (
                                f"名称：{course['courseName']}\n"
                                f"周次：{course['weekIndexes']}\n"
                                f"地点：{course['room']}\n"
                                f"星期：{course['weekday']}\n"
                                f"教师：{course['teachers']}\n"
                                f"开始节数：{course['startUnit']}\n"
                                f"结束节数：{course['endUnit']}\n\n"
                            )
                        logger.info(msg)
                        if global_config.npu_if_check_course_schedule_send:
                            await bot.send_private_msg(
                                user_id=int(qq), message=msg[:-2]
                            )
                            lessons_data_old_dict = {
                                course["courseName"]: course
                                for course in lessons_data_old
                            }
                            lessons_data_old_not_new = [
                                lessons_data_old_dict.get(course["courseName"])
                                for course in lessons_data_new
                                if lessons_data_old_dict.get(course["courseName"])
                            ]
                            msg = ""
                            for course in lessons_data_old_not_new:
                                msg += (
                                    f"名称：{course['courseName']}\n"
                                    f"周次：{course['weekIndexes']}\n"
                                    f"地点：{course['room']}\n"
                                    f"星期：{course['weekday']}\n"
                                    f"教师：{course['teachers']}\n"
                                    f"开始节数：{course['startUnit']}\n"
                                    f"结束节数：{course['endUnit']}\n\n"
                                )
                            if msg:
                                await bot.send_private_forward_msg(
                                    user_id=int(qq),
                                    messages=[
                                        {
                                            "type": "node",
                                            "data": {
                                                "name": "呱唧",
                                                "uin": bot.self_id,
                                                "content": "下面是同课程名的旧课程信息\n无同课程名的旧课程信息的，大概率是新课程",
                                            },
                                        },
                                        {
                                            "type": "node",
                                            "data": {
                                                "name": "呱唧",
                                                "uin": bot.self_id,
                                                "content": msg[:-2],
                                            },
                                        },
                                    ],
                                )
                            else:
                                await bot.send_private_msg(
                                    user_id=int(qq),
                                    message="无同课程名的旧课程信息，大概率是新课程",
                                )
                            logger.info(f"{qq}的课表变动已推送")
                else:
                    await nwpu_query_class_sched.get_course_table()
            else:
                logger.error(f"{qq}的cookies失效了,删除该信息")
                if "electric_information" in nwpu_query_class_sched.info:
                    info = {
                        "electric_information": nwpu_query_class_sched.info[
                            "electric_information"
                        ]
                    }
                    info_file_path.write_text(
                        json.dumps(info, indent=4, ensure_ascii=False), encoding="utf-8"
                    )
                else:
                    info_file_path.unlink(missing_ok=True)
                await bot.send_private_msg(
                    user_id=int(qq),
                    message=f"你的登陆信息已失效，请输入 翱翔 重新登陆",
                )
                logger.info(f"{qq}登录信息过期已推送")
        else:
            logger.info("bot失联，终止更新")
        await nwpu_query_class_sched.close_client()
    except (httpx.TimeoutException, httpx.ReadTimeout, httpx.ConnectTimeout):
        logger.error(f"{qq}的检测check_course_schedule定时任务Timeout")
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
            logger.error("检测check_course_schedule定时任务请求超时，状态码500")
            return
        error_trace = traceback.format_exc()
        logger.error(f"定时任务出现错误{e!r}\n堆栈信息:\n{error_trace}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(
                    user_id=int(superuser),
                    message=MessageSegment.text(
                        f"{qq}的检测check_course_schedule定时任务 发生错误\n{e!r}\n堆栈信息:\n{error_trace}"
                    )
                    + MessageSegment.image(
                        f"https://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640"
                    ),
                )


@scheduler.scheduled_job(
    "cron", day_of_week="sun,thu", hour=16, id="check_course_schedule"
)
async def check_course_schedule_scheduled():
    """
    检测课表是否变动
    """
    bot: Bot = get_bot()
    try:
        # 获取全部已登陆的QQ号
        qq_all = []
        data_folder_path = Path(__file__).parent / "data"
        if data_folder_path.exists():
            qq_all = [f.stem for f in data_folder_path.glob("*.json") if f.is_file()]
            if qq_all:
                logger.info(f"已登录的全部QQ号：{qq_all} 开始检查是否有课表变动")
            else:
                logger.info("没有账号登陆")
        else:
            logger.info("没有data文件夹")
        tasks = [asyncio.create_task(check_course_schedule(qq, bot)) for qq in qq_all]
        await asyncio.gather(*tasks)
        logger.info(f"本次课表变动检测完毕")
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"定时任务出现错误{e!r}\n堆栈信息:\n{error_trace}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(
                    user_id=int(superuser),
                    message=MessageSegment.text(
                        f"check_course_schedule_scheduled定时任务 发生错误\n{e!r}\n堆栈信息:\n{error_trace}"
                    ),
                )


async def check_electric(qq, bot):
    try:
        folder_path = Path(__file__).parent / "data"
        info_file_path = folder_path / f"{qq}.json"
        electric_information = json.loads(
            info_file_path.read_text(encoding="utf-8")
        ).get("electric_information", {})
        if not electric_information:
            return
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
    except ActionFailed as e:
        logger.error(e.__dict__["info"]["message"])
        if "发送失败，请先添加对方为好友" in e.__dict__["info"]["message"]:
            info_file_path.unlink()
    except (httpx.TimeoutException, httpx.ReadTimeout, httpx.ConnectTimeout):
        logger.error(f"{qq}的检测check_electric定时任务Timeout")
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"定时任务出现错误{e!r}\n堆栈信息:\n{error_trace}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(
                    user_id=int(superuser),
                    message=MessageSegment.text(
                        f"{qq}的检测check_electric定时任务 发生错误\n{e!r}\n堆栈信息:\n{error_trace}"
                    )
                    + MessageSegment.image(
                        f"https://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640"
                    ),
                )


@scheduler.scheduled_job("cron", hour="12", id="check_power")
async def check_electric_scheduled():
    bot: Bot = get_bot()
    try:
        # 获取全部已登陆的QQ号
        qq_all = []
        data_folder_path = Path(__file__).parent / "data"
        if data_folder_path.exists():
            qq_all = [f.stem for f in data_folder_path.glob("*.json") if f.is_file()]
            if qq_all:
                logger.info(f"已绑定宿舍的全部QQ号：{qq_all}")
            else:
                logger.info("没有账号绑定")
        else:
            logger.info("没有data文件夹")
        tasks = [asyncio.create_task(check_electric(qq, bot)) for qq in qq_all]
        await asyncio.gather(*tasks)
        logger.info(f"本次电费检测完毕")
    except MatcherException:
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
                        f"check_electric_scheduled定时任务 发生错误\n{e!r}\n堆栈信息:\n{error_trace}"
                    ),
                )
