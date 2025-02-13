from nonebot import logger, get_driver, require, get_bot, get_plugin_config, on_notice
from nonebot.adapters.onebot.v11 import Bot, MessageSegment, Event
from nonebot.exception import MatcherException, ActionFailed

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_waiter")
from nonebot_plugin_apscheduler import scheduler
import os, shutil, json, asyncio, random, httpx, glob, traceback
from datetime import datetime
from pathlib import Path
from .test import test
from .config import Config
from .nwpu_query import NwpuQuery
from .nwpu_electric import get_electric_left
from .draw_course_schedule_pic import check_if_course_schedule_only_one, get_all_lessons
from .utils import generate_img_from_html, generate_grades_to_msg, if_begin_lesson_day_is_tomorrow

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
    scheduler.pause_job('check_power')
    scheduler.pause_job('check_new_info')
    scheduler.pause_job('check_course_schedule')
    scheduler.pause_job('check_new_lesson_begin_tomorrow')


@driver.on_bot_connect
async def connect():
    """bot接入 启动定时任务"""
    await test()
    global if_connected
    if_connected = True
    logger.info("bot接入，启动定时任务")
    scheduler.resume_job('check_power')
    scheduler.resume_job('check_new_info')
    scheduler.resume_job('check_course_schedule')
    scheduler.resume_job('check_new_lesson_begin_tomorrow')
    if global_config.npu_if_check_when_connect:
        # await scheduler.get_job('check_power').func()
        # await scheduler.get_job('check_new_info').func()
        await scheduler.get_job('check_course_schedule').func()
        # await scheduler.get_job('check_new_lesson_begin_tomorrow').func()


async def check_grades_and_ranks_and_exams(qq, bot):
    nwpu_query_class_sched = NwpuQuery()
    try:
        # 留2分钟空闲时间
        sleep_time = random.uniform(0,
                                    (global_config.npu_check_time - 2) * 60 if global_config.npu_check_time >= 2 else 0)
        await asyncio.sleep(sleep_time)
        grades_change = []
        ranks_change = []
        exams_change = []

        folder_path = os.path.join(os.path.dirname(__file__), 'data', qq)
        cookies_path = os.path.join(folder_path, 'cookies.txt')
        if if_connected:
            if await nwpu_query_class_sched.use_recent_cookies_login(cookies_path):
                if os.path.isfile(os.path.join(folder_path, 'info.json')):
                    with open((os.path.join(folder_path, 'info.json')), 'r', encoding='utf-8') as f:
                        nwpu_query_class_sched.student_assoc = json.loads(f.read())["student_assoc"]
                else:
                    if not await nwpu_query_class_sched.get_student_assoc(folder_path):
                        logger.error(f"{qq}的获取信息失败")
                        raise Exception("定时任务{qq}的获取信息失败")
                # 先检测成绩变化
                if global_config.npu_if_check_grades:
                    if os.path.exists(os.path.join(folder_path, 'grades.json')):
                        with open((os.path.join(folder_path, 'grades.json')), 'r', encoding='utf-8') as f:
                            grades_old = json.loads(f.read())
                        _, grades = await nwpu_query_class_sched.get_grades(folder_path)
                        new_grades = [grade for grade in grades if grade not in grades_old] if grades else []
                        if new_grades:
                            pic_path = os.path.join(folder_path, 'grades.jpg')
                            await generate_img_from_html(new_grades, folder_path)
                            grades_change = [qq, pic_path, generate_grades_to_msg(new_grades)]
                            logger.info(f"{qq}出新成绩啦")
                    else:
                        await nwpu_query_class_sched.get_grades(folder_path)
                if grades_change:
                    qq, pic_path, grades_msg = grades_change
                    await bot.send_private_msg(user_id=int(qq), message=f"出新成绩啦！\n{grades_msg}")
                    await bot.send_private_msg(user_id=int(qq), message=MessageSegment.image(Path(pic_path)))
                    logger.info(f"{qq}的新成绩已推送\n{grades_msg}")

                # 检测rank的变化
                if global_config.npu_if_check_rank:
                    if os.path.exists(os.path.join(folder_path, 'rank.txt')):
                        with open((os.path.join(folder_path, 'rank.txt')), 'r', encoding='utf-8') as f:
                            rank_old = f.read()
                        rank_msg, rank = await nwpu_query_class_sched.get_rank(folder_path)
                        if str(rank_old) != str(rank):
                            ranks_change = [qq, rank_old, rank, rank_msg]
                            logger.info(f"{qq}的rank变化啦")
                    else:
                        await nwpu_query_class_sched.get_rank(folder_path)
                if ranks_change:
                    qq, rank_old, rank, rank_msg = ranks_change
                    await bot.send_private_msg(user_id=int(qq),
                                               message=f"你的rank发生了变化,{rank_old}->{rank}\n{rank_msg}")
                    logger.info(f"{qq}的新排名已推送\n{rank_msg}")

                # 检测考试变化
                if global_config.npu_if_check_exams:
                    if os.path.exists(os.path.join(folder_path, 'exams.json')):
                        with open((os.path.join(folder_path, 'exams.json')), 'r', encoding='utf-8') as f:
                            exams_old = json.loads(f.read())
                        exams_msg, exams = await nwpu_query_class_sched.get_exams(folder_path)
                        new_exams = [exam for exam in exams if exam not in exams_old]
                        if new_exams:
                            exams_change = [qq, new_exams, exams_msg]
                            logger.info(f"{qq}出新考试啦")
                    else:
                        await nwpu_query_class_sched.get_exams(folder_path)
                if exams_change:
                    qq, new_exams, exams_msg = exams_change
                    new_courses = [new_exam['course'] for new_exam in new_exams]
                    new_course_msg = ""
                    for new_course in new_courses:
                        new_course_msg += new_course + "\n"
                    new_course_msg = new_course_msg[:-1]
                    await bot.send_private_msg(user_id=int(qq),
                                               message=f"你有新的考试有：\n" + new_course_msg)
                    await bot.send_private_msg(user_id=int(qq),
                                               message=f"你的全部未结束考试有：\n" + exams_msg)
                    logger.info(f"{qq}的新考试已推送\n{new_course_msg}")
            else:
                if os.path.isfile(cookies_path):
                    logger.error(f"{qq}的cookies失效了,删除该文件夹")
                    for file_name in os.listdir(folder_path):
                        file_path = os.path.join(folder_path, file_name)
                        if os.path.isfile(file_path) and file_name != "electric.json":
                            os.remove(file_path)
                    await bot.send_private_msg(user_id=int(qq), message=f"你的登陆信息已失效，请输入 翱翔 重新登陆")
                    logger.info(f"{qq}登录信息过期已推送")
        else:
            logger.info("bot失联，终止更新")
        await nwpu_query_class_sched.close_client()
    except (httpx.TimeoutException, httpx.ReadTimeout, httpx.ConnectTimeout):
        logger.error(f"{qq}的检测check_grades_and_ranks_and_exams定时任务Timeout")
        await nwpu_query_class_sched.close_client()
    except ActionFailed as e:
        logger.error(e.__dict__['info']['message'])
        await nwpu_query_class_sched.close_client()
        if "发送失败，请先添加对方为好友" in e.__dict__['info']['message']:
            logger.info("对方已不是好友，删除该文件夹")
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                if os.path.isfile(file_path):
                    os.remove(file_path)
    except Exception as e:
        await nwpu_query_class_sched.close_client()
        if str(e) == "翱翔教务登录失败，状态码500":
            logger.error("检测check_grades_and_ranks_and_exams定时任务请求超时，状态码500")
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
                    ) + MessageSegment.image(
                        f"https://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640"
                    )
                )


@scheduler.scheduled_job("interval", minutes=global_config.npu_check_time, id="check_new_info")
async def check_grades_and_ranks_and_exams_scheduled():
    """
    定时任务 检测新成绩/考试
    """
    bot: Bot = get_bot()
    try:
        current_hour = datetime.now().hour
        if if_connected and global_config.npu_begin_check_hour <= current_hour < global_config.npu_end_check_hour:
            # 获取全部已登陆的QQ号
            qq_all = []
            data_folder_path = os.path.join(os.path.dirname(__file__), 'data')
            if os.path.exists(data_folder_path):
                qq_all = [f for f in os.listdir(data_folder_path) if os.path.isdir(os.path.join(data_folder_path, f))]
                if qq_all:
                    logger.info(f"已登录的全部QQ号：{qq_all} 开始检查是否有成绩/排名/考试变动")
                else:
                    logger.info("没有账号登陆")
            else:
                logger.info("没有data文件夹")
            tasks = [asyncio.create_task(check_grades_and_ranks_and_exams(qq, bot)) for qq in qq_all]
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
                    )
                )


async def check_new_lesson_begin_tomorrow(qq, bot):
    try:
        sleep_time = random.uniform(0, 60 * 60)
        await asyncio.sleep(sleep_time)
        for file in glob.glob(os.path.join(os.path.join(os.path.dirname(__file__), 'data', qq), '*-*.html')):
            if os.path.basename(file).endswith(('秋.html', '春.html', '夏.html')):
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.loads(f.read())
                if msg := if_begin_lesson_day_is_tomorrow(data):
                    await bot.send_private_msg(user_id=int(qq), message=f"明天有新课程开课，别忘记啦\n\n{msg}")
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
                    ) + MessageSegment.image(
                        f"https://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640"
                    )
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
        data_folder_path = os.path.join(os.path.dirname(__file__), 'data')
        if os.path.exists(data_folder_path):
            qq_all = [f for f in os.listdir(data_folder_path) if os.path.isdir(os.path.join(data_folder_path, f))]
            if qq_all:
                logger.info(f"已登录的全部QQ号：{qq_all} 开始检查明天是否有新开课程")
            else:
                logger.info("没有账号登陆")
        else:
            logger.info("没有data文件夹")
        tasks = [asyncio.create_task(check_new_lesson_begin_tomorrow(qq, bot)) for qq in qq_all]
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
                    )
                )


async def check_course_schedule(qq, bot):
    nwpu_query_class_sched = NwpuQuery()
    try:
        sleep_time = random.uniform(0, 60 * 60 * 2)
        await asyncio.sleep(sleep_time)
        folder_path = os.path.join(os.path.dirname(__file__), 'data', qq)
        cookies_path = os.path.join(folder_path, 'cookies.txt')
        if if_connected:
            if await nwpu_query_class_sched.use_recent_cookies_login(cookies_path):
                if os.path.isfile(os.path.join(folder_path, 'info.json')):
                    with open((os.path.join(folder_path, 'info.json')), 'r', encoding='utf-8') as f:
                        nwpu_query_class_sched.student_assoc = json.loads(f.read())["student_assoc"]
                else:
                    if not await nwpu_query_class_sched.get_student_assoc(folder_path):
                        logger.error(f"{qq}的获取信息失败")
                        raise Exception("定时任务{qq}的获取信息失败")
                if global_config.npu_if_check_course_schedule:
                    if await check_if_course_schedule_only_one(folder_path):
                        lessons_data_old, _ = get_all_lessons(folder_path)
                        await nwpu_query_class_sched.get_course_table(folder_path)
                        lessons_data, _ = get_all_lessons(folder_path)
                        lessons_data_new = [course for course in lessons_data if course not in lessons_data_old] if lessons_data else []
                        if lessons_data_new:
                            logger.info(f"{qq}课表有变化啦")
                            msg = "有课表变动/新课程，变动后课程信息/新课程信息如下，需自行对比查看\n（也可能是机器人误报）\n\n"
                            for course in lessons_data_new:
                                msg += f"名称：{course['courseName']}\n" \
                                        f"周次：{course['weekIndexes']}\n" \
                                        f"地点：{course['room']}\n" \
                                        f"星期：{course['weekday']}\n" \
                                        f"教师：{course['teachers']}\n" \
                                        f"开始节数：{course['startUnit']}\n" \
                                        f"结束节数：{course['endUnit']}\n\n"
                            logger.info(msg)
                            if global_config.npu_if_check_course_schedule_send:
                                await bot.send_private_msg(user_id=int(qq),
                                                           message=msg[:-2])
                                lessons_data_old_dict = {course['courseName']: course for course in lessons_data_old}
                                lessons_data_old_not_new = [lessons_data_old_dict.get(course['courseName']) for course in lessons_data_new if lessons_data_old_dict.get(course['courseName'])]
                                msg = ""
                                for course in lessons_data_old_not_new:
                                    msg += f"名称：{course['courseName']}\n" \
                                            f"周次：{course['weekIndexes']}\n" \
                                            f"地点：{course['room']}\n" \
                                            f"星期：{course['weekday']}\n" \
                                            f"教师：{course['teachers']}\n" \
                                            f"开始节数：{course['startUnit']}\n" \
                                            f"结束节数：{course['endUnit']}\n\n"
                                if msg:
                                    await bot.send_private_forward_msg(user_id=int(qq), messages=[
                                        {
                                                "type": "node",
                                                "data": {"name": "呱唧", "uin": bot.self_id, "content": "下面是同课程名的旧课程信息\n无同课程名的旧课程信息的，大概率是新课程"},
                                            },
                                            {
                                                "type": "node",
                                                "data": {"name": "呱唧", "uin": bot.self_id, "content": msg[:-2]},
                                            }
                                    ])
                                else:
                                    await bot.send_private_msg(user_id=int(qq), message="无同课程名的旧课程信息，大概率是新课程")
                                logger.info(f"{qq}的课表变动已推送")
                    else:
                        await nwpu_query_class_sched.get_course_table(folder_path)
            else:
                if os.path.isfile(cookies_path):
                    logger.error(f"{qq}的cookies失效了,删除该文件夹")
                    for file_name in os.listdir(folder_path):
                        file_path = os.path.join(folder_path, file_name)
                        if os.path.isfile(file_path) and file_name != "electric.json":
                            os.remove(file_path)
                    await bot.send_private_msg(user_id=int(qq), message=f"你的登陆信息已失效，请输入 翱翔 重新登陆")
                    logger.info(f"{qq}登录信息过期已推送")
        else:
            logger.info("bot失联，终止更新")
        await nwpu_query_class_sched.close_client()
    except (httpx.TimeoutException, httpx.ReadTimeout, httpx.ConnectTimeout):
        logger.error(f"{qq}的检测check_course_schedule定时任务Timeout")
        await nwpu_query_class_sched.close_client()
    except ActionFailed as e:
        logger.error(e.__dict__['info']['message'])
        await nwpu_query_class_sched.close_client()
        if "发送失败，请先添加对方为好友" in e.__dict__['info']['message']:
            logger.info("对方已不是好友，删除该文件夹")
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                if os.path.isfile(file_path):
                    os.remove(file_path)
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
                    ) + MessageSegment.image(
                        f"https://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640"
                    )
                )


@scheduler.scheduled_job("cron", day_of_week="sun,thu", hour=16, id="check_course_schedule")
async def check_course_schedule_scheduled():
    """
    检测课表是否变动
    """
    bot: Bot = get_bot()
    try:
        # 获取全部已登陆的QQ号
        qq_all = []
        data_folder_path = os.path.join(os.path.dirname(__file__), 'data')
        if os.path.exists(data_folder_path):
            qq_all = [f for f in os.listdir(data_folder_path) if os.path.isdir(os.path.join(data_folder_path, f))]
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
                    )
                )


async def check_electric(qq, bot):
    try:
        sleep_time = random.uniform(0, global_config.npu_electric_check_time * 60)
        await asyncio.sleep(sleep_time)
        electric_path = os.path.join(os.path.dirname(__file__), 'data', qq, 'electric.json')
        with open(electric_path, 'r', encoding='utf-8') as f:
            electric_information = json.loads(f.read())
        electric_left, information_all = await get_electric_left(electric_information['campus'], electric_information['building'],
                                                electric_information['room'])
        logger.info(f'{qq}电费还剩{electric_left}')
        if electric_left < 15:
            logger.info(f'{qq}电费小于15，推送消息')
            await bot.send_private_msg(user_id=int(qq),
                                       message=f"{information_all}，电费不足15，当前电费{electric_left}，请及时缴纳\n若不想收到提醒消息，可发送 翱翔电费解绑 进行解除绑定")
    except ActionFailed as e:
        logger.error(e.__dict__['info']['message'])
        folder_path = os.path.join(os.path.dirname(__file__), 'data', qq)
        if "发送失败，请先添加对方为好友" in e.__dict__['info']['message']:
            logger.info("对方已不是好友，删除该文件夹")
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                if os.path.isfile(file_path):
                    os.remove(file_path)
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
                    ) + MessageSegment.image(
                        f"https://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640"
                    )
                )


@scheduler.scheduled_job("cron", hour="12", id="check_power")
async def check_electric_scheduled():
    bot: Bot = get_bot()
    try:
        logger.info('检查宿舍电费')
        qq_all = []
        data_folder_path = os.path.join(os.path.dirname(__file__), 'data')
        if os.path.exists(data_folder_path):
            qq_all = [f for f in os.listdir(data_folder_path) if
                      os.path.exists(os.path.join(data_folder_path, f, 'electric.json'))]
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
                    )
                )
