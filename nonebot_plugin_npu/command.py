from nonebot import logger, require, on_command, on_type, get_plugin_config
from nonebot.adapters.onebot.v11 import (
    Bot,
    Event,
    Message,
    MessageSegment,
    MessageEvent,
    GroupMessageEvent,
    PrivateMessageEvent,
    PokeNotifyEvent,
)
from nonebot.params import CommandArg
from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.exception import MatcherException, ActionFailed

require("nonebot_plugin_waiter")
from nonebot_plugin_waiter import waiter, prompt
import os, json, httpx, traceback, time, shutil, uuid
from datetime import datetime
from typing import List, Union
from pathlib import Path
from .config import Config
from .nwpu_query import NwpuQuery
from .utils import generate_img_from_grades, generate_grades_to_msg, get_exams_msg
from .nwpu_electric import get_campus, get_building, get_room, get_electric_left
from .draw_course_schedule_pic import (
    check_if_course_schedule_only_one,
    draw_course_schedule_pic,
)

global_config = get_plugin_config(Config)


async def send_forward_msg(
    bot: Bot,
    event: MessageEvent,
    name: str,
    uin: str,
    user_message: List[MessageSegment],
):
    def to_json(info: MessageSegment):
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


nwpu = on_command(
    "翱翔", rule=to_me(), aliases={"npu", "nwpu"}, priority=10, block=True
)
# 空闲教室信息获取并生图时间太长所以缓存
msg_empty_classroom_all = None
msg_empty_classroom_all_time = datetime.fromtimestamp(time.time()).date()


@nwpu.handle()
async def nwpu_handel_function(
    bot: Bot,
    event: Union[PrivateMessageEvent, GroupMessageEvent],
    args: Message = CommandArg(),
):
    global msg_empty_classroom_all
    global msg_empty_classroom_all_time
    try:
        user_id = event.get_user_id()
        folder_path = Path(__file__).parent / "data"
        info_file_path = folder_path / f"{user_id}.json"
        nwpu_query_class = NwpuQuery(folder_path, info_file_path)
        if msg := args.extract_plain_text().strip():
            if info_file_path.is_file():
                if (
                    msg == "排考"
                    or msg == "考试"
                    or msg == "排考信息"
                    or msg == "考试信息"
                ):
                    exams_old = nwpu_query_class.info.get("exams", [])
                    if exams_old:
                        if get_exams_msg(exams_old):
                            await nwpu.send(
                                "你的未结束考试有：\n" + get_exams_msg(exams_old)
                            )
                        else:
                            await nwpu.send("暂无考试")
                        await nwpu_query_class.use_recent_cookies_login()
                        exams = await nwpu_query_class.get_exams()
                        if exams_old != exams:
                            new_exams = [
                                exam for exam in exams if exam not in exams_old
                            ]
                            if new_exams:
                                await nwpu.send(
                                    f"检测到有新考试，你的全部未结束考试有：\n{get_exams_msg(new_exams)}"
                                )
                    else:
                        await nwpu_query_class.use_recent_cookies_login()
                        exams = await nwpu_query_class.get_exams()
                        if exams:
                            await nwpu.send("你的全部未结束考试有：\n" + get_exams_msg(exams))
                        else:
                            await nwpu.send("暂无考试")
                    await nwpu.finish()
                elif msg == "本周课表":
                    course_table_str = nwpu_query_class.info.get("course_table", "")
                    if course_table_str:
                        await nwpu.send(
                            "检测到已存在课表信息，生成图片中...\n"
                            "若实际有课但图片显示无课，请发送 翱翔课表 更新课表后查看"
                        )
                    else:
                        await nwpu.send("没有课表信息，正在重新获取最新课表，请稍等")
                        await nwpu_handel_function(
                            bot, event, Message(MessageSegment.text("课表"))
                        )
                        await nwpu.finish(
                            "获取完毕，生成图片中...\n后续可以直接输入 翱翔本周课表 查看"
                        )
                    course_schedule_pic_bytes = await draw_course_schedule_pic(
                        folder_path, course_table_str
                    )
                    await nwpu.finish(MessageSegment.image(course_schedule_pic_bytes))
                elif msg[:4] == "成绩查询":
                    course_name = msg[4:].strip()
                    if not course_name:
                        if (
                            course_name := await prompt("请输入要查询的课程名")
                        ) is None:
                            await nwpu.finish("已超时，本次查询结束")
                        course_name = course_name.extract_plain_text().strip()
                    grades = nwpu_query_class.info.get("grades", [])
                    if grades:
                        count = 0
                        for grade in grades:
                            if course_name in grade["name"]:
                                count += 1
                                await nwpu.send(f"{generate_grades_to_msg([grade])}")
                        await nwpu.finish(f"共查询到{count}门课，查询完毕")
                    else:
                        await nwpu.finish("暂无成绩，请先使用翱翔全部成绩获取成绩")
                else:
                    await nwpu.send("正在登入翱翔门户")
                    if await nwpu_query_class.use_recent_cookies_login():
                        if msg == "成绩":
                            await nwpu.send(f"正在获取最近一学期的成绩，请稍等")
                            grades = await nwpu_query_class.get_grades(True)
                            if grades:
                                grades_img_bytes = await generate_img_from_grades(
                                    grades
                                )
                                await nwpu.finish(
                                    MessageSegment.image(grades_img_bytes)
                                )
                            elif grades is None:
                                await nwpu.finish("成绩获取失败，请稍后再试")
                            else:
                                await nwpu.finish("最近的一学期暂无成绩喵")
                            rank_msg = await nwpu_query_class.get_rank()
                            await nwpu.send(rank_msg)
                            # 同时检测是否有新成绩 因为只获取一个学期的成绩不会写入文件
                            grades_old = nwpu_query_class.info.get("grades", [])
                            grades = await nwpu_query_class.get_grades(False)
                            new_grades = (
                                [grade for grade in grades if grade not in grades_old]
                                if grades and grades_old != []
                                else []
                            )
                            if new_grades:
                                await nwpu.send(
                                    f"有新成绩\n{generate_grades_to_msg(new_grades)}"
                                )
                            await nwpu.finish()
                        elif msg == "全部成绩":
                            await nwpu.send(f"正在获取全部成绩，请等待")
                            # 同时检测是否有新成绩
                            grades_old = nwpu_query_class.info.get("grades", [])
                            grades = await nwpu_query_class.get_grades(False)
                            if grades:
                                grades_img_bytes = await generate_img_from_grades(
                                    grades
                                )
                                await nwpu.send(MessageSegment.image(grades_img_bytes))
                            elif grades is None:
                                await nwpu.send("成绩获取失败，请稍后再试")
                            else:
                                await nwpu.send("无成绩喵")
                            new_grades = (
                                [grade for grade in grades if grade not in grades_old]
                                if grades and grades_old != []
                                else []
                            )
                            if new_grades:
                                await nwpu.send(
                                    f"有新成绩\n{generate_grades_to_msg(new_grades)}"
                                )
                            await nwpu.finish()
                        # elif msg == "空教室查询" or msg == "教室查询" or msg == "空闲教室查询":
                        #     if msg_empty_classroom_all is None or msg_empty_classroom_all_time != datetime.fromtimestamp(time.time()).date():
                        #         await nwpu.send("正在刷新空教室信息，请等待，大约需要十秒")
                        #         msg_empty_classroom_all = await nwpu_query_class.get_empty_classroom(folder_path)
                        #         msg_empty_classroom_all_time = datetime.fromtimestamp(time.time()).date()
                        #     await send_forward_msg(bot, event, (await bot.get_login_info())["nickname"], str(event.self_id), msg_empty_classroom_all)
                        elif msg == "排名":
                            rank_msg = await nwpu_query_class.get_rank()
                            await nwpu.finish(rank_msg)
                        elif msg == "全部排名":
                            rank_msg = await nwpu_query_class.get_rank(True)
                            await nwpu.finish(rank_msg)
                        elif msg == "切换身份" or msg == "切换" or msg == "刷新" or msg == "刷新身份":
                            if_get_student_assoc_success, student_assoc_all = (
                                await nwpu_query_class.get_student_assoc()
                            )
                            if if_get_student_assoc_success:
                                # 有多个身份号需要选择
                                if student_assoc_all:
                                    logger.info(f"")
                                    result = []
                                    for sid, info in student_assoc_all.items():
                                        result.append(f"\n身份号 {sid}:\n{info}\n")
                                    await nwpu.send(
                                        f"查询到多个身份:\n\n{''.join(result)}"
                                    )
                                    if (
                                        student_assoc := await prompt(
                                            "请输入要绑定的身份号（六位纯数字）"
                                        )
                                    ) is None:
                                        await nwpu.finish("已超时，本次登陆结束")
                                    student_assoc = (
                                        student_assoc.extract_plain_text().strip()
                                    )
                                    if student_assoc in str(student_assoc_all) and len(student_assoc) == 6 and student_assoc.isdigit():
                                        nwpu_query_class.student_assoc = student_assoc
                                    else:
                                        await nwpu.send("未匹配到该身份，已随机绑定一个身份")
                                    with open(
                                        nwpu_query_class.info_file_path,
                                        "r",
                                        encoding="utf-8",
                                    ) as f:
                                        info = json.load(f)
                                    new_info = {}
                                    new_info["cookies"] = info["cookies"]
                                    new_info["student_assoc"] = nwpu_query_class.student_assoc
                                    with open(
                                        nwpu_query_class.info_file_path,
                                        "w",
                                        encoding="utf-8",
                                    ) as f:
                                        json.dump(new_info, f, indent=4, ensure_ascii=False)
                                else:
                                    await nwpu.finish("没有可切换的身份")

                                await nwpu.send(
                                    "----------------\n"
                                    "获取排名中...\n"
                                    "----------------"
                                )
                                rank_msg = await nwpu_query_class.get_rank(False)
                                await nwpu.send(rank_msg)
                                await nwpu.send(
                                    "----------------\n"
                                    "获取成绩中...\n"
                                    "----------------"
                                )
                                grades = await nwpu_query_class.get_grades(
                                    if_only_last_sem=False
                                )
                                if grades:
                                    grades_img_bytes = await generate_img_from_grades(
                                        grades
                                    )
                                    await nwpu.send(MessageSegment.image(grades_img_bytes))
                                elif grades is None:
                                    await nwpu.send("成绩获取失败，请稍后再试")
                                else:
                                    await nwpu.send("无成绩喵")
                                await nwpu.send(
                                    "----------------\n"
                                    "获取课表中...\n"
                                    "----------------"
                                )
                                course_schedule_pic_bytes = await draw_course_schedule_pic(
                                    folder_path, await nwpu_query_class.get_course_table()
                                )
                                await nwpu.send(
                                    MessageSegment.image(course_schedule_pic_bytes)
                                )

                                await nwpu.send(
                                    "-------------------\n"
                                    "获取考试信息中...\n"
                                    "-------------------"
                                )
                                exams = await nwpu_query_class.get_exams(False)
                                exams_msg = (
                                    ("你的考试有：\n" + get_exams_msg(exams))
                                    if exams
                                    else "暂无考试"
                                )
                                await nwpu.finish(exams_msg)
                            else:
                                await nwpu.finish(
                                    "获取身份id失败，请使用 翱翔刷新id 手动获取"
                                )
                        elif (
                            msg == "全部排考"
                            or msg == "全部考试"
                            or msg == "全部排考信息"
                            or msg == "全部考试信息"
                        ):
                            await nwpu.send(f"正在获取全部考试信息，请等待")
                            exams = await nwpu_query_class.get_exams(True)
                            if exams:
                                await send_forward_msg(
                                    bot,
                                    event,
                                    (await bot.get_login_info())["nickname"],
                                    str(event.self_id),
                                    [
                                        MessageSegment.text(
                                            "你的全部考试有：\n" + get_exams_msg(exams)
                                        )
                                    ],
                                )
                                await nwpu.finish()
                            else:
                                await nwpu.finish("暂无考试")
                        elif msg == "课表":
                            await nwpu.send("正在获取最近有课的一学期的课表，请稍等")
                            course_table = await nwpu_query_class.get_course_table()
                            course_table_name = (
                                f"course_table_{user_id}_{uuid.uuid4().hex}.html"
                            )
                            course_table_file = folder_path / course_table_name
                            course_table_file.write_text(course_table, encoding="utf-8")
                            logger.debug(f"course_table_file {course_table_file}")
                            if course_table:
                                await nwpu.send("发送中")
                                if isinstance(event, GroupMessageEvent):
                                    await bot.call_api(
                                        "upload_group_file",
                                        group_id=event.group_id,
                                        file=str(course_table_file),
                                        name=course_table_name,
                                    )
                                    await nwpu.send("请在群文件中查看文件")
                                else:
                                    await bot.call_api(
                                        "upload_private_file",
                                        user_id=event.user_id,
                                        file=str(course_table_file),
                                        name=course_table_name,
                                    )
                                await nwpu.send(
                                    "此文件需要配合wake up软件使用\n"
                                    "点击->用其他应用打开->选择wake up导入到课程表\n"
                                    "覆盖当前课表->选择学校/教务类型->选择西工大（浏览器登录）->点击右下角导入按钮即可\n"
                                    "第一次使用可能需要自己手动调整一下课表时间"
                                )
                            else:
                                nwpu.finish("暂无课表")
                            course_table_file.unlink(missing_ok=True)
                        elif msg == "退出登录" or msg == "退出登陆":
                            await nwpu.send("正在退出登录")
                            info_file_path.unlink()
                            await nwpu.finish("退出成功")
                        elif msg == "加权百分制成绩":
                            await nwpu.send(
                                f"加权百分制成绩的意思是计算原始百分制成绩的加权平均，不使用gpa（绩点）成绩，P/NP/优秀等非百分制成绩不计入加权百分制成绩中，补考成绩按60分进行计算"
                            )
                            await nwpu.send(f"正在获取全部成绩，请等待")
                            grades = await nwpu_query_class.get_grades()
                            if grades:
                                await nwpu.send(f"正在计算加权百分制成绩")
                                grades = [
                                    grade
                                    for grade in grades
                                    if grade["grade_score"].isdigit()
                                ]
                                for grade in grades:
                                    if (
                                        grade["grade_detail"]
                                        and grade["grade_detail"][-1][-3:] == "（补）"
                                    ):
                                        grade["grade_score"] = "60"
                                average_grades = sum(
                                    [
                                        float(grade["grade_score"])
                                        * float(grade["credit"])
                                        for grade in grades
                                    ]
                                ) / sum([float(grade["credit"]) for grade in grades])
                                await nwpu.send(f"加权百分制成绩为{average_grades:.4f}")
                            elif grades is None:
                                await nwpu.send("成绩获取失败，请稍后再试")
                            else:
                                await nwpu.send("无成绩喵")
                            await nwpu.finish()
                        else:
                            await nwpu.finish(
                                "那是什么 我不知道\n" "发送 help 可获取全部指令"
                            )
                    else:
                        info_file_path.unlink()
                        await nwpu.finish("登陆失败 cookie过期，请输入 翱翔 进行登陆")
            else:
                await nwpu.finish("你还没有登陆过，请输入 翱翔 进行登陆")
        else:
            logger.info("全新的账号正在登陆中")
            await nwpu.send("请勿相信未经信任的机器人喵~⚠️否则你的账号可能会陷入危险⚠️")
            await nwpu.send(
                "目前仅支持账号密码手机验证码登录，登录成功后会自动检测是否有新成绩\n（扫码登录一天后登陆凭证会失效，故删除）\n会收集必要的信息用于持久登陆和成绩检测，继续登陆代表你已同意"
            )
            # 输入账号
            if (account := await prompt("请输入账号")) is None:
                await nwpu.finish("已超时，本次登陆结束")
            account = account.extract_plain_text().strip()
            # 输入密码
            await nwpu.send("请输入密码，输入 停止 可以终止此次登陆")

            @waiter(waits=["message"], keep_session=True)
            async def check_password(event_: Event):
                return event_.get_plaintext()

            async for password in check_password():
                if password is None:
                    await nwpu.finish("已超时，本次登陆结束")
                if password == "停止":
                    await nwpu.finish("已停止，本次登陆结束")
                else:
                    status, if_need_verification = await nwpu_query_class.login(
                        account, password, "securephone"
                    )
                    logger.debug(
                        f"if_need_verification: {if_need_verification}, status: {status}"
                    )
                    if status == 0:
                        # 输入验证码
                        if not if_need_verification:
                            await nwpu.send("登陆成功！")
                        else:

                            @waiter(waits=["message"], keep_session=True)
                            async def check_verification_code(event_: Event):
                                return event_.get_plaintext()

                            await nwpu.send("登陆中...请输入验证码")
                            async for verification_code in check_verification_code():
                                if verification_code is None:
                                    await nwpu.finish("已超时，本次登陆结束")
                                if verification_code == "停止":
                                    await nwpu.finish("已停止，本次登陆结束")
                                status = await nwpu_query_class.verification_code_login(
                                    verification_code
                                )
                                if status == 2:
                                    await nwpu.send("登陆成功！")
                                elif status == 3:
                                    await nwpu.send(
                                        f"验证码错误，请重新输入验证码\n输入 停止 可以终止此次登陆"
                                    )
                                    continue
                                else:
                                    await nwpu.finish(
                                        f"出错了，返回状态码{status}，此次登陆已终止"
                                    )
                        if_get_student_assoc_success, student_assoc_all = (
                            await nwpu_query_class.get_student_assoc()
                        )
                        if if_get_student_assoc_success:
                            # 有多个身份号需要选择
                            if student_assoc_all:
                                logger.info(f"")
                                result = []
                                for sid, info in student_assoc_all.items():
                                    result.append(f"\n身份号 {sid}:\n{info}\n")
                                await nwpu.send(
                                    f"查询到多个身份:\n\n{''.join(result)}"
                                )
                                if (
                                    student_assoc := await prompt(
                                        "请输入要绑定的身份号（六位纯数字）"
                                    )
                                ) is None:
                                    await nwpu.finish("已超时，本次登陆结束")
                                student_assoc = (
                                    student_assoc.extract_plain_text().strip()
                                )
                                if student_assoc in str(student_assoc_all) and len(student_assoc) == 6 and student_assoc.isdigit():
                                    nwpu_query_class.student_assoc = student_assoc
                                else:
                                    await nwpu.send("未匹配到该身份，已随机绑定一个身份，可使用 翱翔切换 更换身份")
                                with open(
                                    nwpu_query_class.info_file_path,
                                    "r",
                                    encoding="utf-8",
                                ) as f:
                                    info = json.load(f)
                                info["student_assoc"] = nwpu_query_class.student_assoc
                                with open(
                                    nwpu_query_class.info_file_path,
                                    "w",
                                    encoding="utf-8",
                                ) as f:
                                    json.dump(info, f, indent=4, ensure_ascii=False)

                            await nwpu.send(
                                "----------------\n"
                                "获取排名中...\n"
                                "----------------"
                            )
                            rank_msg = await nwpu_query_class.get_rank(False)
                            await nwpu.send(rank_msg)
                            await nwpu.send(
                                "----------------\n"
                                "获取成绩中...\n"
                                "----------------"
                            )
                            grades = await nwpu_query_class.get_grades(
                                if_only_last_sem=False
                            )
                            if grades:
                                grades_img_bytes = await generate_img_from_grades(
                                    grades
                                )
                                await nwpu.send(MessageSegment.image(grades_img_bytes))
                            elif grades is None:
                                await nwpu.send("成绩获取失败，请稍后再试")
                            else:
                                await nwpu.send("无成绩喵")
                            await nwpu.send(
                                "----------------\n"
                                "获取课表中...\n"
                                "----------------"
                            )
                            course_schedule_pic_bytes = await draw_course_schedule_pic(
                                folder_path, await nwpu_query_class.get_course_table()
                            )
                            await nwpu.send(
                                MessageSegment.image(course_schedule_pic_bytes)
                            )

                            await nwpu.send(
                                "-------------------\n"
                                "获取考试信息中...\n"
                                "-------------------"
                            )
                            exams = await nwpu_query_class.get_exams(False)
                            exams_msg = (
                                ("你的考试有：\n" + get_exams_msg(exams))
                                if exams
                                else "暂无考试"
                            )
                            await nwpu.finish(exams_msg)
                        else:
                            await nwpu.finish(
                                "获取身份id失败，请使用 翱翔刷新 手动获取"
                            )
                    elif status == -1:
                        await nwpu.send(
                            f"密码错误，请重新输入密码\n输入 停止 可以终止此次登陆"
                        )
                        continue
                    else:
                        await nwpu.finish(f"出错了，返回状态码{status}，此次登陆已终止")
    except MatcherException:
        await nwpu_query_class.close_client()
        raise
    except (httpx.TimeoutException, httpx.ReadTimeout, httpx.ConnectTimeout):
        await nwpu_query_class.close_client()
        await nwpu.send("请求超时，本次指令已结束，请稍等后重试")
    except ActionFailed:
        try:
            if course_table_file:
                course_table_file.unlink(missing_ok=True)
        except NameError:
            print("course_table_file不存在")
        await nwpu_query_class.close_client()
        logger.error(f"文件发送失败")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(
                    user_id=int(superuser),
                    message=MessageSegment.text(
                        f"{event.get_user_id()}发生错误\n文件发送失败"
                    )
                    + MessageSegment.image(
                        f"https://q.qlogo.cn/headimg_dl?dst_uin={event.get_user_id()}&spec=640"
                    ),
                )
        await nwpu.finish("文件发送失败，请等待几天后重试")
    except Exception as e:
        await nwpu_query_class.close_client()
        if str(e) == "翱翔教务登录失败，状态码500":
            logger.error("nwpu_handel_function翱翔教务登录失败，状态码500")
            raise
        try:
            if course_table_file:
                course_table_file.unlink(missing_ok=True)
        except NameError:
            print("course_table_file不存在")
        error_trace = traceback.format_exc()
        logger.error(f"出错了{e!r}\n堆栈信息:\n{error_trace}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(
                    user_id=int(superuser),
                    message=MessageSegment.text(
                        f"{event.get_user_id()}使用翱翔{args.extract_plain_text().strip()}时发生错误\n{e!r}\n堆栈信息:\n{error_trace}"
                    )
                    + MessageSegment.image(
                        f"https://q.qlogo.cn/headimg_dl?dst_uin={event.get_user_id()}&spec=640"
                    ),
                )
        await nwpu.finish("出错了，请重试")


nwpu_course_schedule = on_command(
    "课表", rule=to_me(), aliases={"本周课表", "kb"}, priority=10, block=True
)


@nwpu_course_schedule.handle()
async def _(bot: Bot, event: Event, args: Message = CommandArg()):
    if not args.extract_plain_text().strip():
        await nwpu_handel_function(bot, event, Message(MessageSegment.text("本周课表")))


nwpu_electric = on_command("翱翔电费", rule=to_me(), priority=10, block=True)


@nwpu_electric.handle()
async def _(bot: Bot, event: Event, args: Message = CommandArg()):
    try:
        user_id = event.get_user_id()
        folder_path = Path(__file__).parent / "data"
        info_file_path = folder_path / f"{user_id}.json"
        electric_information = {}
        if info_file_path.exists():
            electric_information = json.loads(info_file_path.read_text(encoding="utf-8")).get("electric_information", {})
        if msg := args.extract_plain_text().strip():
            if msg == "查询":
                if electric_information:
                    electric_left, information_all = await get_electric_left(
                        electric_information["campus"],
                        electric_information["building"],
                        electric_information["room"],
                    )
                    await nwpu_electric.finish(
                        f"{information_all}，当前剩余电量：{electric_left}"
                    )
                else:
                    await nwpu_electric.finish(
                        f"暂未绑定宿舍\n请输入 翱翔电费绑定 进行绑定"
                    )
            elif msg == "绑定":
                try:
                    logger.info("绑定新的宿舍")
                    msg, campus_all = await get_campus()
                    if (campus_msg := await prompt(msg)) is None:
                        await nwpu_electric.finish("已超时，本次绑定结束")
                    campus = campus_all[int(campus_msg.extract_plain_text().strip())][
                        "value"
                    ]
                    msg_list, building_all = await get_building(campus)
                    msg_all = []
                    for msg in msg_list:
                        msg_all.append(MessageSegment.text(msg))
                    await nwpu_electric.send(
                        "请选择楼栋，如0或1，输入停止可终止本次绑定"
                    )
                    await send_forward_msg(
                        bot,
                        event,
                        (await bot.get_login_info())["nickname"],
                        str(event.self_id),
                        msg_all,
                    )
                    if (building_msg := await prompt("")) is None:
                        await nwpu_electric.finish("已超时，本次绑定结束")
                    if building_msg.extract_plain_text().strip() == "停止":
                        await nwpu_electric.finish("已停止，本次绑定结束")
                    building = building_all[
                        int(building_msg.extract_plain_text().strip())
                    ]["value"]
                    msg_list, room_all = await get_room(campus, building)
                    msg_all = []
                    for msg in msg_list:
                        msg_all.append(MessageSegment.text(msg))
                    await nwpu_electric.send(
                        "请选择房间，如0或1，输入停止可终止本次绑定"
                    )
                    await send_forward_msg(
                        bot,
                        event,
                        (await bot.get_login_info())["nickname"],
                        str(event.self_id),
                        msg_all,
                    )
                    if (room_msg := await prompt("")) is None:
                        await nwpu_electric.finish("已超时，本次绑定结束")
                    if room_msg.extract_plain_text().strip() == "停止":
                        await nwpu_electric.finish("已停止，本次绑定结束")
                    room = room_all[int(room_msg.extract_plain_text().strip())]["value"]
                    electric_information = {"campus": campus, "building": building, "room": room}
                    info = json.loads(info_file_path.read_text(encoding="utf-8"))
                    info["electric_information"] = electric_information
                    info_file_path.write_text(
                        json.dumps(info, indent=4, ensure_ascii=False),
                        encoding="utf-8"
                    )
                    electric_left, information_all = await get_electric_left(
                        campus, building, room
                    )
                    await nwpu_electric.send(
                        f"{information_all}，当前剩余电量：{electric_left}"
                    )
                    await nwpu_electric.finish(
                        "会自动定时查询，电费小于一定值时会自动提示"
                    )
                except (ValueError, IndexError):
                    await nwpu_electric.finish(
                        "值错误或数组越界，本次绑定已结束，请输入 翱翔电费绑定 重新开始"
                    )
                except Exception as e:
                    raise e
            elif msg == "解绑":
                if electric_information:
                    info = json.loads(info_file_path.read_text(encoding="utf-8"))
                    info.pop("electric_warning", None)
                    info_file_path.write_text(
                        json.dumps(info, indent=4, ensure_ascii=False),
                        encoding="utf-8"
                    )
                    await nwpu_electric.finish("已解除宿舍绑定")
                else:
                    await nwpu_electric.finish(
                        f"暂未绑定宿舍\n请输入 翱翔电费绑定 进行绑定"
                    )
            else:
                await nwpu_electric.finish(
                    "请输入 翱翔电费绑定 进行绑定\n"
                    "或者\n"
                    "翱翔电费查询 进行电费查询\n"
                    "翱翔电费解绑 解除绑定\n"
                )
        else:
            await nwpu_electric.finish(
                "请输入 翱翔电费绑定 进行绑定\n"
                "或者\n"
                "翱翔电费查询 进行电费查询\n"
                "翱翔电费解绑 解除绑定\n"
            )
    except MatcherException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"出错了{e!r}\n堆栈信息:\n{error_trace}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(
                    user_id=int(superuser),
                    message=MessageSegment.text(
                        f"{event.get_user_id()}使用翱翔电费{args.extract_plain_text().strip()}发生错误\n{e!r}\n堆栈信息:\n{error_trace}"
                    )
                    + MessageSegment.image(
                        f"https://q.qlogo.cn/headimg_dl?dst_uin={event.get_user_id()}&spec=640"
                    ),
                )
        await nwpu_electric.finish("出错了，请重试")


"""
戳一戳返回排名信息
"""
poke_notify = on_type(types=PokeNotifyEvent, priority=1)


@poke_notify.handle()
async def _(bot: Bot, event: PokeNotifyEvent):
    try:
        if event.is_tome():
            logger.info("被戳一戳力")
            await nwpu_handel_function(bot, event, Message(MessageSegment.text("排名")))
    except MatcherException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"出错了{e!r}\n堆栈信息:\n{error_trace}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(
                    user_id=int(superuser),
                    message=MessageSegment.text(
                        f"{event.get_user_id()}使用戳一戳时发生错误\n{e!r}\n堆栈信息:\n{error_trace}"
                    )
                    + MessageSegment.image(
                        f"https://q.qlogo.cn/headimg_dl?dst_uin={event.get_user_id()}&spec=640"
                    ),
                )
        await poke_notify.finish("出错了，请重试")
