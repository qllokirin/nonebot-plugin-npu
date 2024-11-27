import json
import datetime
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from nonebot.utils import run_sync


@run_sync
def check_if_course_schedule_only_one(folder_path):
    """
    检查是否只有一个课程表
    """
    folder_path = Path(folder_path)
    all_course_schedule_files = list(folder_path.glob("*秋.html")) + \
                                list(folder_path.glob("*春.html")) + \
                                list(folder_path.glob("*夏.html"))
    if len(all_course_schedule_files) == 1:
        return True
    else:
        for file in all_course_schedule_files:
            file.unlink()
        return False


def get_time_table(folder_path):
    """
    获取课程表的时间
    """
    folder_path = Path(folder_path)
    html_files = list(folder_path.glob("*.html"))
    lessons_path = [f for f in html_files if f.name.endswith(("春.html", "夏.html", "秋.html"))][0]
    with open(lessons_path, "r", encoding="utf-8") as f:
        data = json.loads(f.read())
    result = []
    for course in data['studentTableVm']['timeTableLayout']['courseUnitList']:
        start_time = str(course['startTime'])
        end_time = str(course['endTime'])
        start_time = start_time[:2] + ":" + start_time[2:] if len(start_time) == 4 else "0" + start_time[
                                                                                          :1] + ":" + start_time[1:]
        end_time = end_time[:2] + ":" + end_time[2:] if len(end_time) == 4 else "0" + end_time[:1] + ":" + end_time[1:]
        result.append(start_time + "\n" + end_time)
    return result


def get_all_lessons(folder_path):
    """
    解析原始课程表数据
    """
    folder_path = Path(folder_path)
    html_files = list(folder_path.glob("*.html"))
    lessons_path = [f for f in html_files if f.name.endswith(("春.html", "夏.html", "秋.html"))][0]
    with open(lessons_path, "r", encoding="utf-8") as f:
        data = json.loads(f.read())
    result = []
    for course in data['studentTableVm']['activities']:
        result.append({
            "courseName": course['courseName'],
            "weekIndexes": course['weekIndexes'],
            "room": course['room'],
            "weekday": course['weekday'],
            "teachers": course['teachers'],
            "startUnit": course['startUnit'],
            "endUnit": course['endUnit'],
        })
    return result, data['studentTableVm']['arrangedLessonSearchVms'][0]['semester']['startDate']


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
def draw_course_schedule_pic(folder_path):
    folder_path = Path(folder_path)
    canvas_width = 1240
    canvas_height = 2770
    bg_color = "#d5ddef"
    text_color = "black"
    font_size = 37
    left_margin = 20
    top_content_gap = 100
    top_margin = 30
    left_content_gap = 150
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
    # 画左侧时间
    time = get_time_table(folder_path)
    # 计算行间距
    line_spacing = (canvas_height - top_content_gap) / len(time)
    for i in range(0, len(time)):
        text = time[i]
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
    lessons_data, begin_time = get_all_lessons(folder_path)
    # 本学期起始日期
    begin_time_datetime = datetime.strptime(begin_time, '%Y-%m-%d')
    # 当前周数
    current_week_index = (datetime.now() - begin_time_datetime).days // 7 + 1
    # 当前星期几
    current_weekday = (datetime.now() - begin_time_datetime).days % 7 + 1
    # 写上方从左到右的文字 "一" 到 "日"
    days = ["一", "二", "三", "四", "五", "六", "日"]
    column_spacing = (canvas_width - left_content_gap) / 7  # 列间距
    x1 = left_content_gap + (current_weekday - 1) * column_spacing
    y1 = 0
    x2 = x1 + column_spacing
    y2 = canvas_height
    draw.rectangle([x1, y1, x2, y2], fill="#B4C6E4")
    for j, day in enumerate(days):
        x_position = left_content_gap + j * column_spacing
        bbox = draw.textbbox((0, 0), day, font=font)
        text_width = (bbox[2] - bbox[0])
        draw.text((x_position + (column_spacing - text_width) / 2, top_margin), day, fill=text_color, font=font)
    # 画各科课程
    for course in lessons_data:
        if current_week_index in course['weekIndexes']:
            text = course['courseName'] + "\n" + course['room'] + "\n" + '\n'.join(course['teachers'])
            x = left_content_gap + (course['weekday'] - 1) * column_spacing + course_margin
            y = top_content_gap + (course['startUnit'] - 1) * line_spacing + course_margin
            width = column_spacing - course_margin * 2
            height = (course['endUnit'] - course['startUnit'] + 1) * line_spacing - course_margin * 2
            radius = 15
            if course['startUnit'] <= 5:
                color = "#74dfcf"
            elif course['startUnit'] <= 10:
                color = "#7ba9f6"
            else:
                color = "#baa7f6"
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
                if y_now + text_height > y + height:
                    break
                if letter == '\n':
                    x_now = x
                    y_now += text_height + text_margin
                    continue
                if x_now + text_width > x + width:
                    x_now = x
                    y_now += text_height + text_margin
                draw.text((x_now, y_now), letter, fill="#F5F5F5", font=font)
                x_now += text_width
    course_schedule_path = Path(folder_path) / "course_schedule_pic.png"
    img.save(course_schedule_path)
    return course_schedule_path


if __name__ == "__main__":
    import asyncio

    data_folder = Path(__file__).parent / "data"
    first_subfolder = next((item for item in data_folder.iterdir() if item.is_dir()), None)
    asyncio.run(draw_course_schedule_pic(first_subfolder))
