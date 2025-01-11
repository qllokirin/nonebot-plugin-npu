import re
import base64
import datetime
from io import BytesIO
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.utils import run_sync


def draw_rounded_rectangle(draw, x, y, width, height, radius, fill, outline=None, outline_width=1):
    """
    在指定位置绘制一个圆角矩形。

    :param draw: ImageDraw 对象
    :param x: 矩形左上角 x 坐标
    :param y: 矩形左上角 y 坐标
    :param width: 矩形宽度
    :param height: 矩形高度
    :param radius: 圆角半径
    :param fill: 矩形填充颜色
    :param outline: 矩形边框颜色（可选）
    :param outline_width: 边框宽度（可选）
    """
    # 圆角的四个角
    left, top, right, bottom = x, y, x + width, y + height
    draw.rectangle([left + radius, top, right - radius, bottom], fill=fill)  # 上下直边
    draw.rectangle([left, top + radius, right, bottom - radius], fill=fill)  # 左右直边
    draw.pieslice([left, top, left + 2 * radius, top + 2 * radius], 180, 270, fill=fill)  # 左上角
    draw.pieslice([right - 2 * radius, top, right, top + 2 * radius], 270, 360, fill=fill)  # 右上角
    draw.pieslice([left, bottom - 2 * radius, left + 2 * radius, bottom], 90, 180, fill=fill)  # 左下角
    draw.pieslice([right - 2 * radius, bottom - 2 * radius, right, bottom], 0, 90, fill=fill)  # 右下角

    # 绘制边框（如果需要）
    if outline:
        draw.arc([left, top, left + 2 * radius, top + 2 * radius], 180, 270, fill=outline, width=outline_width)  # 左上角
        draw.arc([right - 2 * radius, top, right, top + 2 * radius], 270, 360, fill=outline, width=outline_width)  # 右上角
        draw.arc([left, bottom - 2 * radius, left + 2 * radius, bottom], 90, 180, fill=outline,
                 width=outline_width)  # 左下角
        draw.arc([right - 2 * radius, bottom - 2 * radius, right, bottom], 0, 90, fill=outline,
                 width=outline_width)  # 右下角
        draw.line([left + radius, top, right - radius, top], fill=outline, width=outline_width)  # 上边
        draw.line([left + radius, bottom, right - radius, bottom], fill=outline, width=outline_width)  # 下边
        draw.line([left, top + radius, left, bottom - radius], fill=outline, width=outline_width)  # 左边
        draw.line([right, top + radius, right, bottom - radius], fill=outline, width=outline_width)  # 右边


@run_sync
def draw_empty_classroom_pic(folder_path, unit_list, building_all, empty_classroom_all_data):
    empty_classroom_result = []
    folder_path = Path(folder_path)
    unit_list = [str(unit) for unit in unit_list]

    # 一张图一张图的生成
    for empty_classroom_data, building in zip(empty_classroom_all_data, building_all):
        if empty_classroom_data["code"] != 200:
            empty_classroom_result.append({
                "success": False,
                "building": building,
                "pic_base64": ""
            })
        else:
            empty_classroom_data_today = empty_classroom_data["data"]["countMap"][str(datetime.today().isoweekday())]
            left_content_gap = 150
            canvas_width = 220 * len(empty_classroom_data_today) + left_content_gap
            canvas_height = 2770
            bg_color = "#d5ddef"
            text_color = "black"
            font_size = 45
            left_margin = 20
            top_content_gap = 100
            top_margin = 30
            # 字与字上下间距
            text_margin = 15
            # 课程与课程块间距
            course_margin = 10
            # 字与课程块间距
            text_margin_with_course_left_right = 6
            text_margin_with_course_top = 15
            split_line_width = 3
            # 背景图 以后再说吧
            # background_image_path = "1.png"
            # background = Image.open(background_image_path)
            # img = background.resize((canvas_width, canvas_height))
            img = Image.new("RGB", (canvas_width, canvas_height), color=bg_color)
            draw = ImageDraw.Draw(img)
            font_path = folder_path.parent.parent / "SmileySans-Oblique.ttf"
            font = ImageFont.truetype(font_path, font_size)
            # 画左侧list 计算行间距
            line_spacing = (canvas_height - top_content_gap) / len(unit_list)
            for i in range(0, len(unit_list)):
                text = str(unit_list[i])
                bbox = draw.textbbox((0, 0), text, font=font)
                text_height = bbox[3] - bbox[1]
                draw.text((left_margin, top_content_gap + i * line_spacing + (line_spacing - text_height) / 2), text,
                          fill=text_color, font=font)
            # 画上午下午晚上分割线
            for i in [4, 6, 10]:
                x1 = 0
                y1 = top_content_gap + i * line_spacing
                x2 = canvas_width
                y2 = y1 + split_line_width
                draw.rectangle([x1, y1, x2, y2], fill="#B4C6E4")
            # 画各个教室文字 计算列间距
            column_spacing = (canvas_width - left_content_gap) / len(empty_classroom_data_today)
            for j, data in enumerate(empty_classroom_data_today):
                try:
                    data = re.match(r".*\d+", data["classroomName"]).group()
                except:
                    print(data)
                    raise
                x_position = left_content_gap + j * column_spacing
                bbox = draw.textbbox((0, 0), data, font=font)
                text_width = (bbox[2] - bbox[0])
                draw.text((x_position + (column_spacing - text_width) / 2, top_margin), data, fill=text_color,
                          font=font)
            # i是序号 every_empty_classroom是从左往右的每个教室的数据
            for i, every_empty_classroom in enumerate(empty_classroom_data_today):
                if not every_empty_classroom["isIdle"]:
                    unit_list_not_idle = [unit for unit in unit_list if unit not in every_empty_classroom["unitList"]]
                    for index in unit_list_not_idle:
                        text = "非空闲"
                        x = left_content_gap + i * column_spacing + course_margin
                        y = top_content_gap + (int(index) - 1) * line_spacing + course_margin
                        width = column_spacing - course_margin * 2
                        height = line_spacing - course_margin * 2
                        radius = 15
                        color = "#74dfcf"
                        draw_rounded_rectangle(draw, x, y, width, height, radius, fill=color, outline="white",
                                               outline_width=4)
                        x = x + text_margin_with_course_left_right
                        y = y + text_margin_with_course_top
                        width = width - text_margin_with_course_left_right * 2
                        height = height - text_margin_with_course_top * 2
                        x_now = x
                        y_now = y
                        # 取第一个字的高做计算 因为比如 - 的高度会很小导致问题
                        bbox = draw.textbbox((0, 0), text[0], font=font)
                        text_height = bbox[3] - bbox[1]
                        for letter in text:
                            bbox = draw.textbbox((0, 0), letter, font=font)
                            text_width = bbox[2] - bbox[0]
                            if letter == '\n':
                                x_now = x
                                y_now += text_height + text_margin
                                continue
                            # 先判断是否需要换行
                            if x_now + text_width > x + width:
                                x_now = x
                                y_now += text_height + text_margin
                            # 再判断是否超出课程块
                            if y_now + text_height > y + height:
                                break
                            draw.text((x_now, y_now), letter, fill="#F5F5F5", font=font)
                            x_now += text_width
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            empty_classroom_result.append({
                "success": True,
                "building": building,
                "pic_base64": img_base64
            })
    msg_all = []
    for result in empty_classroom_result:
        msg_all.append(MessageSegment.text(f"{result['building']}"))
        if result["success"]:
            msg_all.append(MessageSegment.image(f"base64://{result['pic_base64']}"))
        else:
            msg_all.append(MessageSegment.text("获取教室占用信息失败"))
    return msg_all
