from nonebot import logger, get_driver, require, on_command, on_type, get_bot, get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment, MessageEvent ,GroupMessageEvent, PrivateMessageEvent, PokeNotifyEvent
from nonebot.matcher import Matcher
from nonebot.params import ArgPlainText, CommandArg
from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.utils import run_sync
from nonebot.exception import MatcherException, ActionFailed
require("nonebot_plugin_apscheduler")
require("nonebot_plugin_waiter")
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_waiter import waiter,prompt
import os, shutil, json, asyncio, random, httpx
from datetime import datetime
from typing import List, Union
from pathlib import Path
from .config import Config
from .nwpu_query import NwpuQuery
from .utils import generate_img_from_html, generate_grades_to_msg, get_exams_msg
from .nwpu_electric import get_campaus, get_building, get_room, get_electric_left

__plugin_meta__ = PluginMetadata(
    name="西工大翱翔门户成绩监控",
    description="翱翔门户成绩监控插件，能获取成绩、排名、绩点，当出现新成绩时推送给使用者",
    usage="https://github.com/qllokirin/nonebot-plugin-npu/blob/master/README.md",
    type="application",
    homepage="https://github.com/qllokirin/nonebot-plugin-npu",
    supported_adapters={"~onebot.v11"},
    config=Config,
)
driver = get_driver()
global_config = get_plugin_config(Config)

nwpu = on_command("翱翔", rule=to_me(), aliases={"npu", "nwpu"}, priority=10, block=True)

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


@nwpu.handle()
async def handel_function(bot: Bot, event: Union[PrivateMessageEvent, GroupMessageEvent], args: Message = CommandArg()):
    try:
        nwpu_query_class = NwpuQuery()
        folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
        if msg := args.extract_plain_text():
            cookies_path = os.path.join(folder_path, 'cookies.txt')
            if os.path.isfile(cookies_path):
                if msg == "排考" or msg == "考试" or msg == "排考信息" or msg == "考试信息":
                    if os.path.isfile(os.path.join(folder_path, 'exams.json')):
                        with open((os.path.join(folder_path, 'exams.json')), 'r', encoding='utf-8') as f:
                            exams_old = json.loads(f.read())
                        if get_exams_msg(folder_path):
                            await nwpu.send("你的未结束考试有：\n"+ get_exams_msg(folder_path))
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
                            await nwpu.send("你的全部未结束考试有：\n"+ get_exams_msg(folder_path))
                        else:
                            await nwpu.send("暂无考试")
                    await nwpu.finish()
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
                            # 同时检测是否有新成绩 因为只获取一学期的成绩不会写入文件
                            if os.path.isfile(os.path.join(folder_path, 'grades.json')):
                                with open((os.path.join(folder_path, 'grades.json')), 'r', encoding='utf-8') as f:
                                    grades_old = json.loads(f.read())
                            else:
                                grades_old = []
                            _, grades = await nwpu_query_class.get_grades(folder_path)
                            new_grades = [grade for grade in grades if grade not in grades_old] if grades and grades_old != [] else []
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
                            new_grades = [grade for grade in grades if grade not in grades_old] if grades and grades_old != [] else []
                            if new_grades:
                                await nwpu.send(f"有新成绩\n{generate_grades_to_msg(new_grades)}")
                            await nwpu.finish()
                        elif msg == "排名":
                            rank_msg, _ = await nwpu_query_class.get_rank(folder_path)
                            await nwpu.finish(rank_msg)
                        elif msg == "全部排考" or msg == "全部考试" or msg == "全部排考信息" or msg == "全部考试信息":
                            await nwpu.send(f"正在获取全部考试信息，请等待")
                            exams_msg, _ = await nwpu_query_class.get_exams(folder_path, True)
                            if exams_msg:
                                await send_forward_msg(bot, event, "全部考试", str(event.self_id), [MessageSegment.text("你的全部考试有：\n"+exams_msg)])
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
                                        "upload_group_file", group_id=event.group_id,  file=course_table_path, name=course_table_name
                                    )
                                    await nwpu.send("请在群文件中查看文件")
                                else:
                                    await bot.call_api(
                                        "upload_private_file", user_id=event.user_id, file=course_table_path, name=course_table_name
                                    )
                                await nwpu.send("此文件需要配合wake up软件使用\n"
                                                "点击->用其他应用打开->选择wake up导入到课程表\n"
                                                "覆盖当前课表->选择学校/教务类型->选择西工大->点击右下角导入按钮即可\n"
                                                "第一次使用可能需要自己手动调整一下课表时间")
                                await nwpu.finish()
                            else:
                                nwpu.finish("暂无课表")
                        elif msg == "退出登录" or msg == "退出登陆":
                            await nwpu.send("正在退出登录")
                            shutil.rmtree(folder_path)
                            await nwpu.send("退出成功")
                            await nwpu.finish()
                        elif msg == "加权百分制成绩":
                            await nwpu.send(f"加权百分制成绩的意思是计算原始百分制成绩的加权平均，不使用gpa（绩点）成绩，P/NP成绩不计入加权百分制成绩中")
                            await nwpu.send(f"正在获取全部成绩，请等待")
                            _, grades = await nwpu_query_class.get_grades(folder_path)
                            if grades:
                                await nwpu.send(f"正在计算加权百分制成绩")
                                grades = [grade for grade in grades if grade['grade_score'].isdigit()]
                                average_grades = sum([float(grade['grade_score']) * float(grade['credit']) for grade in grades]) / sum([float(grade['credit']) for grade in grades])
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
                                    "upload_group_file", group_id=event.group_id,  file=xlsx_path, name=xlsx_name
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
            async def check_login_in_way(event: Event):
                if event.get_plaintext() in ["1", "2", "3"]:
                    return event.get_plaintext()
                else:
                    return False
            await nwpu.send("请选择登陆方式\n1->账号密码手机验证码登录\n2->账号密码邮箱验证码登录\n3->扫码登录\n登录成功后会自动检测是否有新成绩，但若选择扫码登录，一天后登陆凭证会失效，无法长期监测新成绩\n\n会收集必要的信息用于持久登陆和成绩检测，继续登陆代表你已同意")
            login_in_way = await check_login_in_way.wait()
            if login_in_way in ["1","2"]:
                # 输入账号
                if (account := await prompt("请输入账号")) is None:
                    await nwpu.finish("已超时，本次登陆结束")
                account = account.extract_plain_text()
                # 输入密码
                await nwpu.send("请输入密码")
                @waiter(waits=["message"], keep_session=True)
                async def check_password(event: Event):
                    return event.get_plaintext()
                async for password in check_password():
                    if password is None:
                        await nwpu.finish("已超时，本次登陆结束")
                    if password == "停止":
                        await nwpu.finish("已停止，本次登陆结束")
                    else:
                        status = await nwpu_query_class.login(account, password, "securephone" if login_in_way == "1" else "secureemail", folder_path)
                        if status == 0:
                            # 输入验证码
                            @waiter(waits=["message"], keep_session=True)
                            async def check_verification_code(event: Event):
                                return event.get_plaintext()
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
                                    await nwpu.send("学校的排名逻辑是同绩点的可能会被并列为同一名也可能会按顺序排，所以没出成绩时排名也在上下浮动是正常的（因为可能有跟你同绩点也有可能是前面有人同绩点导致你往前一名）")
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
                if await nwpu_query_class.wating_to_scan_qr(folder_path):
                    await nwpu.send(f'扫码登录成功！正在获取全部成绩，请稍等')
                    if os.path.isfile(os.path.join(folder_path, 'info.json')):
                        os.remove(os.path.join(folder_path, 'info.json'))
                    if not await nwpu_query_class.get_student_assoc(folder_path):
                        logger.error(f"获取信息失败")
                        raise Exception("获取信息失败")
                    rank_msg, _ = await nwpu_query_class.get_rank(folder_path)
                    await nwpu.send(rank_msg)
                    await nwpu.send("学校的排名逻辑是同绩点的可能会被并列为同一名也可能会按顺序排，所以没出成绩时排名也在上下浮动是正常的（因为可能有跟你同绩点也有可能是前面有人同绩点导致你往前一名）")
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
                                           message=MessageSegment.text(f"{event.get_user_id()}发生错误\n文件发送失败") + MessageSegment.image(f"https://q.qlogo.cn/headimg_dl?dst_uin={event.get_user_id()}&spec=640"))
        await nwpu.finish("文件发送失败，刚加没多久的新好友大概率出现此问题，请等待几天后重试")
    except Exception as e:
        await nwpu_query_class.close_client()
        logger.error(f"出错了{e}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(user_id=int(superuser), 
                                           message=MessageSegment.text(f"{event.get_user_id()}使用翱翔{args.extract_plain_text()}时发生错误\n{e}") + MessageSegment.image(f"https://q.qlogo.cn/headimg_dl?dst_uin={event.get_user_id()}&spec=640"))
        await nwpu.finish("出错了，请重试")

'''
戳一戳返回排名信息
'''
poke_noetify = on_type(types=PokeNotifyEvent, priority=1)
@poke_noetify.handle()
async def _(
    bot: Bot,
    event : PokeNotifyEvent
):
    try:
        if event.is_tome():
            logger.info('被戳一戳力')
            nwpu_query_class = NwpuQuery()
            folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
            cookies_path = os.path.join(folder_path, 'cookies.txt')
            if os.path.isfile(cookies_path):
                    await poke_noetify.send("正在登入翱翔门户")
                    if await nwpu_query_class.use_recent_cookies_login(cookies_path):
                        if os.path.isfile(os.path.join(folder_path, 'info.json')):
                            with open((os.path.join(folder_path, 'info.json')), 'r', encoding='utf-8') as f:
                                nwpu_query_class.student_assoc = json.loads(f.read())["student_assoc"]
                        else:
                            if not await nwpu_query_class.get_student_assoc(folder_path):
                                logger.error(f"获取信息失败")
                                raise Exception("获取信息失败")
                        rank_msg, _ = await nwpu_query_class.get_rank(folder_path)
                        await nwpu_query_class.close_client()
                        await poke_noetify.finish(rank_msg)
                    else:
                        shutil.rmtree(folder_path)
                        await nwpu_query_class.close_client()
                        await poke_noetify.finish("登陆失败 cookie过期，请输入 翱翔 进行登陆")
            else:
                await nwpu_query_class.close_client()
                await poke_noetify.finish("你还没有登陆过，请输入 翱翔 进行登陆")
    except MatcherException:
        raise
    except Exception as e:
        logger.error(f"出错了{e}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(user_id=int(superuser), 
                                           message=MessageSegment.text(f"{event.get_user_id()}使用戳一戳时发生错误\n{e}") + MessageSegment.image(f"https://q.qlogo.cn/headimg_dl?dst_uin={event.get_user_id()}&spec=640"))
        await poke_noetify.finish("出错了，请重试")


# bot是否在线 最开始启动时是离线的 与ws握手成功后变为True,断连后变为False
if_connected = False
async def get_grades_and_ranks_and_exams(qq):
    try:
        # 留2分钟空闲时间
        sleep_time = random.uniform(0, (global_config.npu_check_time - 2) * 60 if global_config.npu_check_time >= 2 else 0)
        await asyncio.sleep(sleep_time)
        grades_change = []
        ranks_change = []
        exams_change = []
        failure_qq = []

        folder_path = os.path.join(os.path.dirname(__file__), 'data', qq)
        cookies_path = os.path.join(folder_path, 'cookies.txt')
        nwpu_query_class_sched = NwpuQuery()
        if if_connected:
            # 登陆
            if await nwpu_query_class_sched.use_recent_cookies_login(cookies_path):
                if os.path.isfile(os.path.join(folder_path, 'info.json')):
                    with open((os.path.join(folder_path, 'info.json')), 'r', encoding='utf-8') as f:
                        nwpu_query_class_sched.student_assoc = json.loads(f.read())["student_assoc"]
                else:
                    if not await nwpu_query_class_sched.get_student_assoc(folder_path):
                        logger.error(f"{qq}的student_assoc获取失败，本次不检测")
                        await nwpu_query_class_sched.close_client()
                        return grades_change, ranks_change, exams_change, failure_qq
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
                            grades_change.append([qq, pic_path, generate_grades_to_msg(new_grades)])
                            logger.info(f"{qq}出新成绩啦")
                    else:
                        await nwpu_query_class_sched.get_grades(folder_path)

                # 检测rank的变化
                if global_config.npu_if_check_rank:
                    if os.path.exists(os.path.join(folder_path, 'rank.txt')):
                        with open((os.path.join(folder_path, 'rank.txt')), 'r', encoding='utf-8') as f:
                            rank_old = f.read()
                        rank_msg, rank = await nwpu_query_class_sched.get_rank(folder_path)
                        if str(rank_old) != str(rank):
                            ranks_change.append([qq, rank_old, rank, rank_msg])
                            logger.info(f"{qq}的rank变化啦")
                    else:
                        await nwpu_query_class_sched.get_rank(folder_path)
                
                # 检测考试变化
                if global_config.npu_if_check_exams:
                    if os.path.exists(os.path.join(folder_path, 'exams.json')):
                        with open((os.path.join(folder_path, 'exams.json')), 'r', encoding='utf-8') as f:
                            exams_old = json.loads(f.read())
                        exams_msg, exams = await nwpu_query_class_sched.get_exams(folder_path)
                        new_exams = [exam for exam in exams if exam not in exams_old]
                        if new_exams:
                            exams_change.append([qq, new_exams, exams_msg])
                            logger.info(f"{qq}出新考试啦")
                    else:
                        await nwpu_query_class_sched.get_exams(folder_path)
            else:
                logger.error(f"{qq}的cookies失效了,删除该文件夹")
                failure_qq.append(qq)
                shutil.rmtree(folder_path)
        else:
            logger.info("bot失联，终止更新")
        await nwpu_query_class_sched.close_client()
        return grades_change, ranks_change, exams_change, failure_qq
    except httpx.TimeoutException as e:
        logger.error(f"TimeoutException httpx超时{e}")
        await nwpu_query_class_sched.close_client()
        return grades_change, ranks_change, exams_change, failure_qq
    except Exception as e:
        logger.error(f"定时任务出现新错误{e}")
        await nwpu_query_class_sched.close_client()
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
    if global_config.npu_if_check_when_connect:
        await scheduler.get_job('check_new_info').func()

@scheduler.scheduled_job("interval", minutes=global_config.npu_check_time, id="check_new_info")
async def check_grades_and_exams():
    """
    定时任务 检测新成绩/考试
    """
    try:
        current_hour = datetime.now().hour
        if if_connected and global_config.npu_begin_check_hour <= current_hour < global_config.npu_end_check_hour:
            bot: Bot = get_bot()
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
            tasks = [get_grades_and_ranks_and_exams(qq) for qq in qq_all]
            running_tasks = [asyncio.create_task(task) for task in tasks]
            for running_task in running_tasks:
                grades_change, ranks_change, exams_change, failure_qq = await running_task
                for qq, pic_path, grades_msg in grades_change:
                    await bot.send_private_msg(user_id=int(qq), message=f"出新成绩啦！\n{grades_msg}")
                    await bot.send_private_msg(user_id=int(qq), message=MessageSegment.image(Path(pic_path)))
                    logger.info(f"{qq}的新成绩已推送\n{grades_msg}")
                    await asyncio.sleep(2)
                for qq, rank_old, rank, rank_msg in ranks_change:
                    await bot.send_private_msg(user_id=int(qq),
                                            message=f"你的rank发生了变化,{rank_old}->{rank}\n{rank_msg}")
                    await asyncio.sleep(2)
                for qq, new_exams, exams_msg in exams_change:
                    new_courses = [new_exam['course'] for new_exam in new_exams]
                    new_course_msg = ""
                    for new_course in new_courses:
                        new_course_msg += new_course + "\n"
                    new_course_msg = new_course_msg[:-1]
                    await bot.send_private_msg(user_id=int(qq),
                                            message=f"你有新的考试有：\n"+new_course_msg)
                    await bot.send_private_msg(user_id=int(qq),
                                            message=f"你的全部未结束考试有：\n"+exams_msg)
                    await asyncio.sleep(2)
                for qq in failure_qq:
                    await bot.send_private_msg(user_id=int(qq), message=f"你的登陆信息已失效，请输入 翱翔 重新登陆")
            logger.info(f"本次检测完毕")
        else:
            logger.info(f"bot失联或不在检测时间段中，不检测")
    except MatcherException:
        raise
    except Exception as e:
        logger.error(f"出错了{e}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(user_id=int(superuser), 
                                           message=f"检测定时任务 发生错误\n{e}")

nwpu_electric = on_command("翱翔电费", rule=to_me(), priority=10, block=True)

@nwpu_electric.handle()
async def handel_function(bot: Bot, event: Event, args: Message = CommandArg()):
    try:
        folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        if msg := args.extract_plain_text():
            if msg == "查询":
                folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
                electric_path = os.path.join(folder_path, 'electric.json')
                if os.path.exists(electric_path):
                    with open(electric_path, 'r', encoding='utf-8') as f:
                        electric_information = json.loads(f.read())
                    electric_left = await get_electric_left(electric_information['campaus'],electric_information['building'],electric_information['room'])
                    await nwpu_electric.finish(f'电费剩余{electric_left}')
                else:
                    await nwpu_electric.finish(f'暂未绑定宿舍\n请输入 翱翔电费绑定 进行绑定')
            elif msg == "绑定":
                logger.info("绑定新的宿舍")
                information_all = ""
                msg,campaus_all = await get_campaus()
                if (campaus_msg := await prompt(msg)) is None:
                    await nwpu_electric.finish("已超时，本次绑定结束")
                information_all += campaus_all[int(campaus_msg.extract_plain_text())]['name'] + " "
                folder_path = os.path.join(os.path.dirname(__file__), 'data', event.get_user_id())
                campaus = campaus_all[int(campaus_msg.extract_plain_text())]['value']
                msg_list,building_all = await get_building(campaus)
                msg_all = []
                for msg in msg_list:
                    msg_all.append(MessageSegment.text(msg))
                await send_forward_msg(bot, event, "building_all", str(event.self_id), msg_all)
                if (building_msg := await prompt("")) is None:
                    await nwpu.nwpu_electric("已超时，本次绑定结束")
                information_all += building_all[int(building_msg.extract_plain_text())]['name'] + " "
                building = building_all[int(building_msg.extract_plain_text())]['value']
                msg_list,room_all = await get_room(campaus,building)
                msg_all = []
                for msg in msg_list:
                    msg_all.append(MessageSegment.text(msg))
                await send_forward_msg(bot, event, "room_all", str(event.self_id), msg_all)
                if (room_msg := await prompt("")) is None:
                    await nwpu.finish("已超时，本次绑定结束")
                information_all += room_all[int(room_msg.extract_plain_text())]['name']
                room = room_all[int(room_msg.extract_plain_text())]['value']
                data = {'campaus':campaus,'building':building,'room':room}
                electric_left = await get_electric_left(campaus, building, room)
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
                await nwpu_electric.finish("请输入 翱翔电费绑定 进行绑定 \n或者 翱翔电费查询 进行电费查询 翱翔电费解绑 接触绑定")
        else:
            await nwpu_electric.finish("请输入 翱翔电费绑定 进行绑定 \n或者 翱翔电费查询 进行电费查询 翱翔电费解绑 接触绑定")
    except MatcherException:
        raise
    except Exception as e:
        logger.error(f"出错了{e}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(user_id=int(superuser), 
                                           message=MessageSegment.text(f"{event.get_user_id()}使用翱翔电费{args.extract_plain_text()}发生错误\n{e}") + MessageSegment.image(f"https://q.qlogo.cn/headimg_dl?dst_uin={event.get_user_id()}&spec=640"))
        await nwpu_electric.finish("出错了，请重试")

async def get_nwpu_electric():
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
        electric_left = await get_electric_left(electric_information['campaus'],electric_information['building'],electric_information['room'])
        logger.info(f'{qq}电费还剩{electric_left}')
        if electric_left < 25:
            electric_all.append([qq,electric_left])
    return electric_all

@scheduler.scheduled_job("cron", hour="12", id="check_power")
async def check_electric():
    try:
        electric_all = await get_nwpu_electric()
        bot: Bot = get_bot()
        for qq,electric_left in electric_all:
            await bot.send_private_msg(user_id=int(qq), message=f"电费不足25，当前电费{electric_left}，请及时缴纳\n若不想收到提醒消息，可发送 翱翔电费解绑 进行解除绑定")
            await asyncio.sleep(2)
    except MatcherException:
        raise
    except Exception as e:
        logger.error(f"出错了{e}")
        if global_config.superusers:
            logger.info(f"发送错误日志给SUPERUSERS")
            for superuser in global_config.superusers:
                await bot.send_private_msg(user_id=int(superuser), 
                                           message=f"电费定时任务 发生错误\n{e}")