from nonebot import logger, require, on_command, on_type, get_plugin_config
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment, MessageEvent, GroupMessageEvent, \
    PrivateMessageEvent, PokeNotifyEvent
from nonebot.params import CommandArg
from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.exception import MatcherException, ActionFailed

require("nonebot_plugin_waiter")
from nonebot_plugin_waiter import waiter, prompt
import os, shutil, json
from typing import List, Union
from pathlib import Path
from .config import Config
from .nwpu_query import NwpuQuery
from .utils import generate_img_from_html, generate_grades_to_msg, get_exams_msg
from .nwpu_electric import get_campus, get_building, get_room, get_electric_left
from .draw_course_schedule_pic import check_if_course_schedule_only_one, draw_course_schedule_pic

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


nwpu = on_command("翱翔", rule=to_me(), aliases={"npu", "nwpu"}, priority=10, block=True)


@nwpu.handle()
async def nwpu_handel_function(bot: Bot, event: Union[PrivateMessageEvent, GroupMessageEvent],
                               args: Message = CommandArg()):
    nwpu_query_class = NwpuQuery()
    try:
        folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
        if msg := args.extract_plain_text().strip():
            cookies_path = os.path.join(folder_path, 'cookies.txt')
            if os.path.isfile(cookies_path):
                if msg == "排考" or msg == "考试" or msg == "排考信息" or msg == "考试信息":
                    if os.path.isfile(os.path.join(folder_path, 'exams.json')):
                        with open((os.path.join(folder_path, 'exams.json')), 'r', encoding='utf-8') as f:
                            exams_old = json.loads(f.read())
                        if get_exams_msg(folder_path):
                            await nwpu.send("你的未结束考试有：\n" + get_exams_msg(folder_path))
                        else:
                            await nwpu.send("暂无考试")
                        await nwpu_query_class.use_recent_cookies_login(cookies_path)
                        _, exams = await nwpu_query_class.get_exams(folder_path)
                        if exams_old != exams:
                            new_exams = [exam for exam in exams if exam not in exams_old]
                            if new_exams:
                                await nwpu.send(f"检测到有新考试，你的全部未结束考试有：\n{get_exams_msg(folder_path)}")
                    else:
                        await nwpu_query_class.use_recent_cookies_login(cookies_path)
                        await nwpu_query_class.get_exams(folder_path)
                        if get_exams_msg(folder_path):
                            await nwpu.send("你的全部未结束考试有：\n" + get_exams_msg(folder_path))
                        else:
                            await nwpu.send("暂无考试")
                    await nwpu.finish()
                elif msg == "本周课表":
                    if await check_if_course_schedule_only_one(folder_path):
                        await nwpu.send("检测到已存在课表文件，生成图片中...\n"
                                        "若实际有课但图片显示无课，请发送 翱翔课表 更新课表后查看")
                    else:
                        await nwpu.send("没有课表文件或有多个课表文件，正在重新获取最新课表，请稍等")
                        await nwpu_handel_function(bot, event, Message(MessageSegment.text("课表")))
                        await nwpu.send("获取完毕，生成图片中...\n后续可以直接输入 翱翔本周课表 查看")
                    course_schedule_path = await draw_course_schedule_pic(folder_path)
                    await nwpu.finish(MessageSegment.image(Path(course_schedule_path)))
                else:
                    await nwpu.send("正在登入翱翔门户")
                    if await nwpu_query_class.use_recent_cookies_login(cookies_path):
                        if os.path.isfile(os.path.join(folder_path, 'info.json')):
                            with open((os.path.join(folder_path, 'info.json')), 'r', encoding='utf-8') as f:
                                nwpu_query_class.student_assoc = json.loads(f.read())["student_assoc"]
                        else:
                            if not await nwpu_query_class.get_student_assoc(folder_path):
                                logger.error(f"获取信息失败")
                                raise Exception("获取信息失败")
                        if msg == "成绩":
                            sem_query_num = 1
                            await nwpu.send(f"正在获取最近一学期的成绩，请稍等")
                            _, grades = await nwpu_query_class.get_grades(folder_path, sem_query_num)
                            if grades:
                                pic_path = os.path.join(folder_path, 'grades.jpg')
                                await generate_img_from_html(grades, folder_path)
                                await nwpu.send(MessageSegment.image(Path(pic_path)))
                            elif grades is None:
                                await nwpu.send("成绩获取失败，请稍后再试")
                            else:
                                await nwpu.send("最近的一学期暂无成绩喵")
                            rank_msg, _ = await nwpu_query_class.get_rank(folder_path)
                            await nwpu.send(rank_msg)
                            # 同时检测是否有新成绩 因为只获取一个学期的成绩不会写入文件
                            if os.path.isfile(os.path.join(folder_path, 'grades.json')):
                                with open((os.path.join(folder_path, 'grades.json')), 'r', encoding='utf-8') as f:
                                    grades_old = json.loads(f.read())
                            else:
                                grades_old = []
                            _, grades = await nwpu_query_class.get_grades(folder_path)
                            new_grades = [grade for grade in grades if
                                          grade not in grades_old] if grades and grades_old != [] else []
                            if new_grades:
                                await nwpu.send(f"有新成绩\n{generate_grades_to_msg(new_grades)}")
                            await nwpu.finish()
                        elif msg == "全部成绩":
                            await nwpu.send(f"正在获取全部成绩，请等待")
                            # 同时检测是否有新成绩
                            if os.path.isfile(os.path.join(folder_path, 'grades.json')):
                                with open((os.path.join(folder_path, 'grades.json')), 'r', encoding='utf-8') as f:
                                    grades_old = json.loads(f.read())
                            else:
                                grades_old = []
                            _, grades = await nwpu_query_class.get_grades(folder_path)
                            if grades:
                                pic_path = os.path.join(folder_path, 'grades.jpg')
                                await generate_img_from_html(grades, folder_path)
                                await nwpu.send(MessageSegment.image(Path(pic_path)))
                            elif grades is None:
                                await nwpu.send("成绩获取失败，请稍后再试")
                            else:
                                await nwpu.send("无成绩喵")
                            new_grades = [grade for grade in grades if
                                          grade not in grades_old] if grades and grades_old != [] else []
                            if new_grades:
                                await nwpu.send(f"有新成绩\n{generate_grades_to_msg(new_grades)}")
                            await nwpu.finish()
                        elif msg == "排名":
                            rank_msg, _ = await nwpu_query_class.get_rank(folder_path)
                            await nwpu.finish(rank_msg)
                        elif msg == "全部排名":
                            rank_msg, _ = await nwpu_query_class.get_rank(folder_path, True)
                            await nwpu.finish(rank_msg)
                        elif msg == "综测排名":
                            water_rank_msg = await nwpu_query_class.get_water_rank()
                            if water_rank_msg:
                                await nwpu.finish(water_rank_msg)
                            else:
                                await nwpu.finish("暂无综测排名信息")
                        elif msg == "全部排考" or msg == "全部考试" or msg == "全部排考信息" or msg == "全部考试信息":
                            await nwpu.send(f"正在获取全部考试信息，请等待")
                            exams_msg, _ = await nwpu_query_class.get_exams(folder_path, True)
                            if exams_msg:
                                await send_forward_msg(bot, event, "全部考试", str(event.self_id),
                                                       [MessageSegment.text("你的全部考试有：\n" + exams_msg)])
                                await nwpu.finish()
                            else:
                                await nwpu.finish("暂无考试")
                        elif msg == "课表":
                            await nwpu.send("正在获取最近有课的一学期的课表，请稍等")
                            course_table_path, course_table_name = await nwpu_query_class.get_course_table(folder_path)
                            if course_table_path:
                                await nwpu.send("发送中")
                                if isinstance(event, GroupMessageEvent):
                                    await bot.call_api(
                                        "upload_group_file", group_id=event.group_id, file=course_table_path,
                                        name=course_table_name
                                    )
                                    await nwpu.send("请在群文件中查看文件")
                                else:
                                    await bot.call_api(
                                        "upload_private_file", user_id=event.user_id, file=course_table_path,
                                        name=course_table_name
                                    )
                                await nwpu.send("此文件需要配合wake up软件使用\n"
                                                "点击->用其他应用打开->选择wake up导入到课程表\n"
                                                "覆盖当前课表->选择学校/教务类型->选择西工大->点击右下角导入按钮即可\n"
                                                "第一次使用可能需要自己手动调整一下课表时间")
                            else:
                                nwpu.finish("暂无课表")
                        elif msg == "退出登录" or msg == "退出登陆":
                            await nwpu.send("正在退出登录")
                            shutil.rmtree(folder_path)
                            await nwpu.send("退出成功")
                            await nwpu.finish()
                        elif msg == "加权百分制成绩":
                            await nwpu.send(
                                f"加权百分制成绩的意思是计算原始百分制成绩的加权平均，不使用gpa（绩点）成绩，P/NP成绩不计入加权百分制成绩中")
                            await nwpu.send(f"正在获取全部成绩，请等待")
                            _, grades = await nwpu_query_class.get_grades(folder_path)
                            if grades:
                                await nwpu.send(f"正在计算加权百分制成绩")
                                grades = [grade for grade in grades if grade['grade_score'].isdigit()]
                                average_grades = sum(
                                    [float(grade['grade_score']) * float(grade['credit']) for grade in grades]) / sum(
                                    [float(grade['credit']) for grade in grades])
                                await nwpu.send(f"加权百分制成绩为{average_grades:.4f}")
                            elif grades is None:
                                await nwpu.send("成绩获取失败，请稍后再试")
                            else:
                                await nwpu.send("无成绩喵")
                            await nwpu.finish()
                        # 此功能难以实现，废弃
                        elif msg == "培养方案完成情况":
                            await nwpu.send("正在计算培养方案完成情况，请稍等")
                            await nwpu_query_class.get_grades(folder_path)
                            xlsx_path, xlsx_name = await nwpu_query_class.get_training_program(folder_path)
                            await nwpu.send("发送中")
                            if isinstance(event, GroupMessageEvent):
                                await bot.call_api(
                                    "upload_group_file", group_id=event.group_id, file=xlsx_path, name=xlsx_name
                                )
                            else:
                                await bot.call_api(
                                    "upload_private_file", user_id=event.user_id, file=xlsx_path, name=xlsx_name
                                )
                            await nwpu.send("未完成课程为红色填充\n"
                                            "未完成模块为黄色填充\n"
                                            "未匹配课程为灰色填充\n"
                                            "已匹配课程为蓝色字体（按课程代号匹配）\n"
                                            "qq预览无法看见颜色填充，请使用相关软件打开查看\n"
                                            "程序可能会有出错之处，仅供参考")
                            await nwpu.send("此功能已废弃，必有不对之处，请谨慎使用")
                            await nwpu.finish()
                        else:
                            await nwpu.finish("那是什么 我不知道\n"
                                              "发送 help 可获取全部指令")
                    else:
                        shutil.rmtree(folder_path)
                        await nwpu.finish("登陆失败 cookie过期，请输入 翱翔 进行登陆")
            else:
                await nwpu.finish("你还没有登陆过，请输入 翱翔 进行登陆")
        else:
            logger.info("全新的账号正在登陆中")

            # 选择登陆方式
            @waiter(waits=["message"], keep_session=True)
            async def check_login_in_way(event_: Event):
                if event_.get_plaintext() in ["1", "2", "3"]:
                    return event_.get_plaintext()
                else:
                    return False

            await nwpu.send(
                "请选择登陆方式\n1->账号密码手机验证码登录\n2->账号密码邮箱验证码登录\n3->扫码登录\n登录成功后会自动检测是否有新成绩，但若选择扫码登录，一天后登陆凭证会失效，无法长期监测新成绩\n\n会收集必要的信息用于持久登陆和成绩检测，继续登陆代表你已同意")
            login_in_way = await check_login_in_way.wait()
            if login_in_way in ["1", "2"]:
                # 输入账号
                if (account := await prompt("请输入账号")) is None:
                    await nwpu.finish("已超时，本次登陆结束")
                account = account.extract_plain_text().strip()
                # 输入密码
                await nwpu.send("请输入密码")

                @waiter(waits=["message"], keep_session=True)
                async def check_password(event_: Event):
                    return event_.get_plaintext()

                async for password in check_password():
                    if password is None:
                        await nwpu.finish("已超时，本次登陆结束")
                    if password == "停止":
                        await nwpu.finish("已停止，本次登陆结束")
                    else:
                        status = await nwpu_query_class.login(account, password,
                                                              "securephone" if login_in_way == "1" else "secureemail"
                                                              )
                        if status == 0:
                            # 输入验证码
                            @waiter(waits=["message"], keep_session=True)
                            async def check_verification_code(event_: Event):
                                return event_.get_plaintext()

                            await nwpu.send("登陆中...请输入验证码")
                            async for verification_code in check_verification_code():
                                if verification_code is None:
                                    await nwpu.finish("已超时，本次登陆结束")
                                if verification_code == "停止":
                                    await nwpu.finish("已停止，本次登陆结束")
                                status = await nwpu_query_class.verification_code_login(verification_code, folder_path)
                                if status == 2:
                                    await nwpu.send(f"登陆成功！正在获取全部成绩，请稍等")
                                    if os.path.isfile(os.path.join(folder_path, 'info.json')):
                                        os.remove(os.path.join(folder_path, 'info.json'))
                                    if not await nwpu_query_class.get_student_assoc(folder_path):
                                        logger.error(f"获取信息失败")
                                        raise Exception("获取信息失败")
                                    rank_msg, _ = await nwpu_query_class.get_rank(folder_path)
                                    await nwpu.send(rank_msg)
                                    await nwpu.send(
                                        "学校的排名逻辑是同绩点的可能会被并列为同一名也可能会按顺序排，所以没出成绩时排名也在上下浮动是正常的（因为可能有跟你同绩点也有可能是前面有人同绩点导致你往前一名）")
                                    _, grades = await nwpu_query_class.get_grades(folder_path)
                                    if grades:
                                        pic_path = os.path.join(folder_path, 'grades.jpg')
                                        await generate_img_from_html(grades, folder_path)
                                        await nwpu.send(MessageSegment.image(Path(pic_path)))
                                    elif grades is None:
                                        await nwpu.send("成绩获取失败，请稍后再试")
                                    else:
                                        await nwpu.send("无成绩喵")
                                    exams_msg, _ = await nwpu_query_class.get_exams(folder_path)
                                    exams_msg = ("你的考试有：\n" + exams_msg) if exams_msg else "暂无考试"
                                    await nwpu.finish(exams_msg)
                                elif status == 3:
                                    await nwpu.send(f'验证码错误，请重新输入验证码\n输入 停止 可以终止此次登陆')
                                    continue
                                else:
                                    await nwpu.finish(f'出错了，返回状态码{status}，此次登陆已终止')
                        elif status == -1:
                            await nwpu.send(f'密码错误，请重新输入密码\n输入 停止 可以终止此次登陆')
                            continue
                        else:
                            await nwpu.finish(f'出错了，返回状态码{status}，此次登陆已终止')
            elif login_in_way == "3":
                # 扫码登录
                await nwpu.send(f'请稍等，获取二维码中...')
                await nwpu_query_class.login_with_qr(folder_path)
                await nwpu.send(MessageSegment.image(Path(os.path.join(folder_path, 'qr.png'))))
                if await nwpu_query_class.waiting_to_scan_qr(folder_path):
                    await nwpu.send(f'扫码登录成功！正在获取全部成绩，请稍等')
                    if os.path.isfile(os.path.join(folder_path, 'info.json')):
                        os.remove(os.path.join(folder_path, 'info.json'))
                    if not await nwpu_query_class.get_student_assoc(folder_path):
                        logger.error(f"获取信息失败")
                        raise Exception("获取信息失败")
                    rank_msg, _ = await nwpu_query_class.get_rank(folder_path)
                    await nwpu.send(rank_msg)
                    await nwpu.send(
                        "学校的排名逻辑是同绩点的可能会被并列为同一名也可能会按顺序排，所以没出成绩时排名也在上下浮动是正常的（因为可能有跟你同绩点也有可能是前面有人同绩点导致你往前一名）")
                    _, grades = await nwpu_query_class.get_grades(folder_path)
                    if grades:
                        pic_path = os.path.join(folder_path, 'grades.jpg')
                        await generate_img_from_html(grades, folder_path)
                        await nwpu.send(MessageSegment.image(Path(pic_path)))
                    elif grades is None:
                        await nwpu.send("成绩获取失败，请稍后再试")
                    else:
                        await nwpu.send("无成绩喵")
                    exams_msg, _ = await nwpu_query_class.get_exams(folder_path)
                    exams_msg = ("你的考试有：\n" + exams_msg) if exams_msg else "暂无考试"
                    await nwpu.finish(exams_msg)
                else:
                    await nwpu.finish(f'扫码出错，时间超时过期or其他原因，此次登陆已终止')
            elif login_in_way is None:
                await nwpu.finish("已超时，本次登陆结束")
            else:
                await nwpu.finish(f'没有这个登陆方式，请选择1或2或3，此次登陆已终止')
    except MatcherException:
        await nwpu_query_class.close_client()
        raise
    except ActionFailed:
        await nwpu_query_class.close_client()
        logger.error(f"文件发送失败")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(user_id=int(superuser),
                                           message=MessageSegment.text(
                                               f"{event.get_user_id()}发生错误\n文件发送失败") + MessageSegment.image(
                                               f"https://q.qlogo.cn/headimg_dl?dst_uin={event.get_user_id()}&spec=640"))
        await nwpu.finish("文件发送失败，刚加没多久的新好友大概率出现此问题，请等待几天后重试")
    except Exception as e:
        await nwpu_query_class.close_client()
        logger.error(f"出错了{e!r}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(user_id=int(superuser),
                                           message=MessageSegment.text(
                                               f"{event.get_user_id()}使用翱翔{args.extract_plain_text().strip()}时发生错误\n{e!r}") + MessageSegment.image(
                                               f"https://q.qlogo.cn/headimg_dl?dst_uin={event.get_user_id()}&spec=640"))
        await nwpu.finish("出错了，请重试")


nwpu_course_schedule = on_command("课表", rule=to_me(), aliases={"本周课表", "kb"}, priority=10, block=True)


@nwpu_course_schedule.handle()
async def _(bot: Bot, event: Event, args: Message = CommandArg()):
    if not args.extract_plain_text().strip():
        await nwpu_handel_function(bot, event, Message(MessageSegment.text("本周课表")))


nwpu_electric = on_command("翱翔电费", rule=to_me(), priority=10, block=True)


@nwpu_electric.handle()
async def _(bot: Bot, event: Event, args: Message = CommandArg()):
    try:
        folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        if msg := args.extract_plain_text().strip():
            if msg == "查询":
                folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
                electric_path = os.path.join(folder_path, 'electric.json')
                if os.path.exists(electric_path):
                    with open(electric_path, 'r', encoding='utf-8') as f:
                        electric_information = json.loads(f.read())
                    electric_left = await get_electric_left(electric_information['campus'],
                                                            electric_information['building'],
                                                            electric_information['room'])
                    await nwpu_electric.finish(f'电费剩余{electric_left}')
                else:
                    await nwpu_electric.finish(f'暂未绑定宿舍\n请输入 翱翔电费绑定 进行绑定')
            elif msg == "绑定":
                logger.info("绑定新的宿舍")
                information_all = ""
                msg, campus_all = await get_campus()
                if (campus_msg := await prompt(msg)) is None:
                    await nwpu_electric.finish("已超时，本次绑定结束")
                information_all += campus_all[int(campus_msg.extract_plain_text().strip())]['name'] + " "
                folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
                campus = campus_all[int(campus_msg.extract_plain_text().strip())]['value']
                msg_list, building_all = await get_building(campus)
                msg_all = []
                for msg in msg_list:
                    msg_all.append(MessageSegment.text(msg))
                await send_forward_msg(bot, event, "building_all", str(event.self_id), msg_all)
                if (building_msg := await prompt("")) is None:
                    await nwpu.finish("已超时，本次绑定结束")
                information_all += building_all[int(building_msg.extract_plain_text().strip())]['name'] + " "
                building = building_all[int(building_msg.extract_plain_text().strip())]['value']
                msg_list, room_all = await get_room(campus, building)
                msg_all = []
                for msg in msg_list:
                    msg_all.append(MessageSegment.text(msg))
                await send_forward_msg(bot, event, "room_all", str(event.self_id), msg_all)
                if (room_msg := await prompt("")) is None:
                    await nwpu.finish("已超时，本次绑定结束")
                information_all += room_all[int(room_msg.extract_plain_text().strip())]['name']
                room = room_all[int(room_msg.extract_plain_text().strip())]['value']
                data = {'campus': campus, 'building': building, 'room': room}
                electric_left = await get_electric_left(campus, building, room)
                with open(os.path.join(folder_path, 'electric.json'), 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                await nwpu_electric.send(f'{information_all}，当前剩余电量：{electric_left}')
                await nwpu_electric.finish("每天12点会自动定时查询，电费小于25时会自动提示充值")
            elif msg == "解绑":
                folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
                electric_path = os.path.join(folder_path, 'electric.json')
                if os.path.exists(electric_path):
                    os.remove(electric_path)
                    await nwpu_electric.finish("已解除宿舍绑定")
                else:
                    await nwpu_electric.finish(f'暂未绑定宿舍\n请输入 翱翔电费绑定 进行绑定')
            else:
                await nwpu_electric.finish("请输入 翱翔电费绑定 进行绑定\n"
                                           "或者\n"
                                           "翱翔电费查询 进行电费查询\n"
                                           "翱翔电费解绑 解除绑定\n")
        else:
            await nwpu_electric.finish("请输入 翱翔电费绑定 进行绑定\n"
                                       "或者\n"
                                       "翱翔电费查询 进行电费查询\n"
                                       "翱翔电费解绑 解除绑定\n")
    except MatcherException:
        raise
    except Exception as e:
        logger.error(f"出错了{e!r}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(user_id=int(superuser),
                                           message=MessageSegment.text(
                                               f"{event.get_user_id()}使用翱翔电费{args.extract_plain_text().strip()}发生错误\n{e!r}") + MessageSegment.image(
                                               f"https://q.qlogo.cn/headimg_dl?dst_uin={event.get_user_id()}&spec=640"))
        await nwpu_electric.finish("出错了，请重试")


'''
戳一戳返回排名信息
'''
poke_notify = on_type(types=PokeNotifyEvent, priority=1)


@poke_notify.handle()
async def _(
        bot: Bot,
        event: PokeNotifyEvent
):
    try:
        if event.is_tome():
            logger.info('被戳一戳力')
            await nwpu_handel_function(bot, event, Message(MessageSegment.text("排名")))
    except MatcherException:
        raise
    except Exception as e:
        logger.error(f"出错了{e!r}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(user_id=int(superuser),
                                           message=MessageSegment.text(
                                               f"{event.get_user_id()}使用戳一戳时发生错误\n{e!r}") + MessageSegment.image(
                                               f"https://q.qlogo.cn/headimg_dl?dst_uin={event.get_user_id()}&spec=640"))
        await poke_notify.finish("出错了，请重试")
