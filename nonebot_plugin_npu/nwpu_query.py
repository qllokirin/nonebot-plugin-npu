"""
MIT License

Copyright (c) 2023 Huang Junlin

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

初版来自https://github.com/cheanus/Automation/blob/main/GradesMonitorLinux.py
"""

# 翱翔教务给参的时候老接口还活着，新接口都是用qLx64euN=，有点加密，先不逆了，用老接口吧

from nonebot import logger
import re
import time
import json
import os
import httpx
import rsa
import base64
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
from pathlib import Path
import openpyxl
import copy
import urllib.parse

if __name__ != "__main__":
    from .draw_empty_classroom_pic import draw_empty_classroom_pic
    from .utils import (
        handle_training_program_data,
        handle_completed_and_incomplete_course,
        max_dict_depth,
        write_to_excel,
        fromat_excel,
        generate_grades_to_msg,
        get_exams_msg
    )
    from .jwxt.get_new_cookie_Fkjfy9yPdPQuP import get_new_cookie_Fkjfy9yPdPQuP
    from .draw_course_schedule_pic import (
        check_if_course_schedule_only_one,
        draw_course_schedule_pic,
    )
else:
    from jwxt.get_new_cookie_Fkjfy9yPdPQuP import get_new_cookie_Fkjfy9yPdPQuP
    from utils import generate_grades_to_msg, get_exams_msg
    from draw_course_schedule_pic import (
        check_if_course_schedule_only_one,
        draw_course_schedule_pic,
    )


class NwpuQuery:
    def __init__(self, folder_path, info_file_path):
        self.folder_path = folder_path
        self.info_file_path = info_file_path
        self.state_key = None
        self.fpVisitorId = None
        self.data = None
        self.state_code = None
        self.execution = None
        self.password = None
        self.username = None
        self.device = None
        self.info = None
        self.headers = {
            "accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif, "
                "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"
            ),
            "accept-encoding": "deflate, br",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "referer": "https://ecampus.nwpu.edu.cn/main.html",
            "sec-ch-ua": '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Linux"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/103.0.0.0 Safari/537.36"
            ),
        }
        self.headers2 = self.headers.copy()
        self.headers2["X-Requested-With"] = "XMLHttpRequest"
        self.headers3 = self.headers2.copy()
        self.headers3["Content-Type"] = "application/json; charset=UTF-8"
        self.headers4 = self.headers3.copy()
        self.headers4["Content-Type"] = (
            "application/x-www-form-urlencoded; charset=UTF-8"
        )
        self.student_assoc = None
        self.client = httpx.AsyncClient(follow_redirects=True)
        if self.info_file_path.is_file():
            with open(self.info_file_path, "r", encoding="utf-8") as f:
                data = json.loads(f.read())
                self.info = data

    async def close_client(self):
        await self.client.aclose()

    async def use_recent_cookies_login(self):
        if os.path.isfile(self.info_file_path):
            with open(self.info_file_path, "r", encoding="utf-8") as f:
                data = json.loads(f.read())
                new_cookies = data["cookies"]
                self.info = data
            for name, value in new_cookies.items():
                self.client.cookies.set(name, value)
        else:
            return False
        url = "https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn%2F%3Fpath%3Dhttps%253A%252F%252Fecampus.nwpu.edu.cn%252Fmain.html%2523%252FIndex"
        response = await self.client.get(url, headers=self.headers, timeout=10)
        logger.debug(
            f"是否重定向（登录翱翔门户是否成功）{'True' if len(response.history) else 'False'}"
        )
        if len(response.history) != 0:
            match = re.search(r"ticket=(.*)", str(response.url))
            if match:
                ticket = match.group(1)
            else:
                logger.error("ticket获取失败")
                return False
            self.headers2["x-id-token"] = json.loads(
                base64.b64decode(
                    urllib.parse.unquote(ticket)
                    .split(".")[1]
                    .replace("-", "+")
                    .replace("_", "/")
                )
            )["idToken"]
            url = "https://ecampus.nwpu.edu.cn/main.html"
            response = await self.client.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                await self.login_jwxt()
                with open(self.info_file_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                self.student_assoc = info.get("student_assoc", None)
                return True
            else:
                return False
        else:
            return False

    async def login_jwxt(self):
        url = "https://jwxt.nwpu.edu.cn/student/sso-login"
        response = await self.client.get(url, headers=self.headers)
        logger.debug("第一次sso-login 登陆结果")
        logger.debug(response.status_code)
        new_cookie_Fkjfy9yPdPQuP = await get_new_cookie_Fkjfy9yPdPQuP(
            self.folder_path, response.text
        )
        if new_cookie_Fkjfy9yPdPQuP:
            self.client.cookies.set("Fkjfy9yPdPQuP", new_cookie_Fkjfy9yPdPQuP)
            logger.debug("Fkjfy9yPdPQuP 更新成功")
        else:
            logger.error("Fkjfy9yPdPQuP 更新失败")
        url = "https://jwxt.nwpu.edu.cn/student/sso-login"
        response = await self.client.get(url, headers=self.headers)
        logger.debug("第二次sso-login 登陆结果")
        logger.debug(response.status_code)
        if response.status_code != 200:
            raise Exception(f"翱翔教务登录失败，状态码{response.status_code}")
        return True

    async def login(self, username, password, device):
        """
        返回值: (状态码, 是否需要验证码)
        0, False        不需要验证码时密码正确，此时直接翱翔门户登录成功
        -1, False       不需要验证码时密码错误
        0, True         需要验证码时密码正确
        -1, True        需要验证码时密码错误
        {code}, True    需要验证码时出现错误，状态码为错误码
        """
        url = (
            "https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn"
            "%2F%3Fpath%3Dhttps%3A%2F%2Fecampus.nwpu.edu.cn"
        )
        self.device = device
        self.username = username

        # RSA加密password
        url_key = "https://uis.nwpu.edu.cn/cas/jwt/publicKey"
        response = await self.client.get(url_key, headers=self.headers2, timeout=5)
        public_key = rsa.PublicKey.load_pkcs1_openssl_pem(response.text.encode())
        password = rsa.encrypt(password.encode(), public_key)
        password = "__RSA__" + base64.b64encode(password).decode()
        self.password = password

        response = await self.client.get(url, headers=self.headers, timeout=10)
        response.encoding = "utf-8"
        str1 = re.search('var hmSiteId = "(.*?)"', response.text)
        new_cookies = {
            ("Hm_lvt_" + str1.group(1)): str(int(time.time())),
            ("Hm_lpvt_" + str1.group(1)): str(int(time.time())),
        }
        for name, value in new_cookies.items():
            self.client.cookies.set(name, value)

        self.execution = re.search('name="execution" value="(.*?)"', response.text)
        self.fpVisitorId = re.search('name="fpVisitorId" value="(.*?)"', response.text)
        self.fpVisitorId = ""

        url = "https://uis.nwpu.edu.cn/cas/mfa/detect"
        data = {
            "username": self.username,
            "password": self.password,
        }
        response = await self.client.post(
            url, data=data, headers=self.headers2, timeout=15
        )
        if_need_verification_code = json.loads(response.text)["data"]["need"]
        self.state_code = json.loads(response.text)["data"]["state"]
        if not if_need_verification_code:
            # 不需要验证码的时候应该要判断密码是否正确
            verification_code_login_state = await self.verification_code_login(None)
            if verification_code_login_state == 2:
                logger.debug("密码正确")
                return 0, if_need_verification_code
            else:
                logger.debug(f"密码错误")
                logger.debug(
                    f"verification_code_login_state {verification_code_login_state}"
                )
                return -1, if_need_verification_code
        else:
            # 需要验证码，发送验证码之后用verification_code_login登入
            url = f"https://uis.nwpu.edu.cn/cas/mfa/initByType/{device}?state={self.state_code}"
            response = await self.client.get(url, headers=self.headers2, timeout=15)
            if json.loads(response.text)["code"] != 0:
                return json.loads(response.text)["code"], if_need_verification_code
            else:
                gid = json.loads(response.text)["data"]["gid"]
                url = f"https://uis.nwpu.edu.cn/attest/api/guard/{device}/send"
                self.data = {"gid": gid}
                await self.client.post(
                    url, data=json.dumps(self.data), headers=self.headers3, timeout=15
                )
                return 0, if_need_verification_code

    async def verification_code_login(self, captcha):
        if captcha:
            url = f"https://uis.nwpu.edu.cn/attest/api/guard/{self.device}/valid"
            self.data["code"] = captcha
            response = await self.client.post(
                url, data=json.dumps(self.data), headers=self.headers3
            )
            if json.loads(response.text)["data"]["status"] != 2:
                return json.loads(response.text)["data"]["status"]
        url = (
            "https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn"
            "%2F%3Fpath%3Dhttps%3A%2F%2Fecampus.nwpu.edu.cn"
        )
        self.data = {
            "username": self.username,
            "password": self.password,
            "rememberMe": "true",
            "currentMenu": "1",
            "mfaState": self.state_code,
            "execution": self.execution.group(1),
            "_eventId": "submit",
            "geolocation": "",
            "fpVisitorId": self.fpVisitorId,
            "submit": "稍等片刻……",
        }
        response = await self.client.post(url, data=self.data, headers=self.headers)
        info = {
            "cookies": {cookie.name: cookie.value for cookie in self.client.cookies.jar}
        }
        logger.debug(
            f"是否重定向（登录翱翔门户是否成功）{'True' if len(response.history) else 'False'}"
        )
        if len(response.history) != 0:
            match = re.search(r"ticket=(.*)", str(response.url))
            if match:
                ticket = match.group(1)
            else:
                logger.error("ticket获取失败")
                return 4
            self.headers2["x-id-token"] = json.loads(
                base64.b64decode(
                    urllib.parse.unquote(ticket)
                    .split(".")[1]
                    .replace("-", "+")
                    .replace("_", "/")
                )
            )["idToken"]
        else:
            return 0
        await self.login_jwxt()
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
        with open(self.info_file_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(info, indent=4, ensure_ascii=False))
        return 2

    # 查询student_assoc
    async def get_student_assoc(self):
        url = "https://jwxt.nwpu.edu.cn/student/for-std/grade/sheet"
        response = await self.client.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")
        blocks = soup.find_all("div", class_="student-panel-block")
        student_assoc_all = {}
        for block in blocks:
            student_info = ""
            dl = block.find("dl")
            if dl:
                dts = dl.find_all("dt")
                dds = dl.find_all("dd")
                for dt, dd in zip(dts, dds):
                    key = dt.get_text(strip=True)
                    value = dd.get_text(strip=True)
                    student_info += f"{key}: {value}\n"
            student_info = student_info.strip()
            button = block.find("button", class_="footer btn btn-primary")
            student_assoc_all[button["value"]] = student_info

        if student_assoc_all:
            with open(self.info_file_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            # 如果只有一个信息 直接选
            if len(student_assoc_all) == 1:
                self.student_assoc = list(student_assoc_all.keys())[0]
                info["student_assoc"] = self.student_assoc
                with open(self.info_file_path, "w", encoding="utf-8") as f:
                    json.dump(info, f, indent=4, ensure_ascii=False)
                return True, ""
            # 本科/研究生/博士 默认选一个最后的，后续可以切换
            else:
                self.student_assoc = list(student_assoc_all.keys())[-1]
                info["student_assoc"] = self.student_assoc
                with open(self.info_file_path, "w", encoding="utf-8") as f:
                    json.dump(info, f, indent=4, ensure_ascii=False)
                return True, student_assoc_all
        else:
            logger.error("get_student_assoc failed", self.folder_path)
            return False, ""

    # 查询成绩
    async def get_grades(self, if_only_last_sem=True):
        # if_only_last_semester 仅查询最近一个学期
        try:
            url = f"https://jwxt.nwpu.edu.cn/student/for-std/grade/sheet/semester-index/{self.student_assoc}?"
            response = await self.client.get(url, headers=self.headers, timeout=5)
            semester = re.findall('<option value="(.+?)"', response.text)
            grades = []
            grades_msg = []
            if if_only_last_sem:
                semester = semester[:1]
            for sem in semester:
                url = (
                    "https://jwxt.nwpu.edu.cn/student/for-std/grade/sheet/info/"
                    + self.student_assoc
                    + "?semester="
                    + sem
                )
                response = await self.client.get(url, headers=self.headers2, timeout=8)
                response = json.loads(response.text)["semesterId2studentGrades"][sem]
                for course in response:
                    name = course["course"]["nameZh"]
                    code = course["course"]["code"]
                    course_type = course["courseType"]["nameZh"]
                    grade_score = course["gaGrade"]
                    gpa = str(course["gp"])
                    credit = course["course"]["credits"]
                    grade_detail = re.findall(">(.+?)</span>", course["gradeDetail"])
                    if re.findall(r"缓考成绩:\d+", course["gradeDetail"]):
                        grade_detail += re.findall(
                            r"缓考成绩:\d+", course["gradeDetail"]
                        )
                    if re.findall(r"补考成绩:\d+", course["gradeDetail"]):
                        grade_detail += re.findall(
                            r"补考成绩:\d+", course["gradeDetail"]
                        )
                    if grade_detail != [None] and grade_detail != []:
                        grade_detail[-1] += course["fillAGrace"] or ""
                    grades_msg.append(
                        f"{name}, {grade_score}, {gpa}, {credit}, {grade_detail}"
                    )
                    grades_one_subject = {
                        "name": name,
                        "code": code,
                        "course_type": course_type,
                        "grade_score": grade_score,
                        "gpa": gpa,
                        "credit": credit,
                        "grade_detail": grade_detail,
                    }
                    grades.append(grades_one_subject)
            # 获取全部成绩时才保存成绩
            # 并且非空时才保存 因为偶尔会出现bug推送全部成绩 故推测是因为上一次获取的是全空
            if not if_only_last_sem and grades:
                with open(self.info_file_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                info["grades"] = grades
                with open(self.info_file_path, "w", encoding="utf-8") as f:
                    json.dump(info, f, indent=4, ensure_ascii=False)
            return grades
        except httpx.TimeoutException:
            logger.error(
                f"{self.folder_path}成绩获取超时，返回None，在定时任务中会跳过，在指令获取中会返回错误信息"
            )
            return None

    async def get_rank(self, if_all_semester=False):
        url = "https://jwxt.nwpu.edu.cn/student/for-std/student-portrait"
        await self.client.get(url, headers=self.headers, timeout=5)
        url = "https://jwxt.nwpu.edu.cn/student/for-std/student-portrait/getStdInfo?bizTypeAssoc=2&cultivateTypeAssoc=1"
        response = await self.client.get(url, headers=self.headers, timeout=5)
        grade = response.json()["student"]["grade"]
        major_id = response.json()["student"]["major"]["id"]
        major_name = response.json()["student"]["major"]["nameZh"]
        url = f"https://jwxt.nwpu.edu.cn/student/for-std/student-portrait/getGradeAnalysis?bizTypeAssoc=2&grade={grade}&majorAssoc={major_id}&semesterAssoc="
        response = await self.client.get(url, headers=self.headers, timeout=5)
        score_range_count = response.json()["scoreRangeCount"]
        total_people_numb = sum(score_range_count.values())
        url = f"https://jwxt.nwpu.edu.cn/student/for-std/student-portrait/getMyGrades?studentAssoc={self.student_assoc}&semesterAssoc="
        response = await self.client.get(url, headers=self.headers, timeout=5)
        get_my_grades_json = response.json()
        if response.json() is None:
            return "暂无排名喵"
        else:
            gpa = response.json()["gpa"]
            rank_msg = f"你的绩点是{gpa}，{major_name}专业\n根据学生画像饼图计算专业/学院总人数为{total_people_numb}，排名接口已经消失"
            rank = 0
            url = f"https://jwxt.nwpu.edu.cn/student/for-std/student-portrait/getMyGpa?studentAssoc={self.student_assoc}"
            response = await self.client.get(url, headers=self.headers, timeout=5)
            if response.json()["stdGpaRankDto"] is None:
                rank_msg += "\n暂无前一名与后一名成绩信息"
            else:
                before_rank_gpa = response.json()["stdGpaRankDto"]["beforeRankGpa"]
                after_rank_gpa = response.json()["stdGpaRankDto"]["afterRankGpa"]
                if before_rank_gpa:
                    rank_msg += f"\n和前一名差{before_rank_gpa - gpa:.3f}绩点"
                if after_rank_gpa:
                    rank_msg += f"\n与后一名差{gpa - after_rank_gpa:.3f}绩点"

            with open(self.info_file_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            info["rank"] = rank
            with open(self.info_file_path, "w", encoding="utf-8") as f:
                json.dump(info, f, indent=4, ensure_ascii=False)
            if not if_all_semester:
                return rank_msg
            semesters_all = {
                semester["id"]: semester["nameZh"]
                for semester in get_my_grades_json["semesters"]
            }
            for semester in [
                semester["id"] for semester in get_my_grades_json["semesters"]
            ]:
                url = f"https://jwxt.nwpu.edu.cn/student/for-std/student-portrait/getMyGrades?studentAssoc={self.student_assoc}&semesterAssoc={semester}"
                response = await self.client.get(url, headers=self.headers, timeout=5)
                if response.json() is None:
                    continue
                gpa = response.json()["gpa"]
                rank_msg += (
                    f"\n\n{semesters_all[semester]}\n你的绩点是{gpa}\n排名接口已经消失"
                )
            return rank_msg

    # 查询考试信息
    async def get_exams(self, is_finished_show=False):
        url = "https://jwxt.nwpu.edu.cn/student/for-std/exam-arrange"
        response = await self.client.get(url, headers=self.headers, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.find_all("tr")
        exams = []
        exams_msg = ""
        for row in rows:
            if row.has_attr("data-finished"):
                # 是否结束
                finished = row["data-finished"]
                if (not is_finished_show and finished == "false") or is_finished_show:
                    # 时间
                    time_exam = row.find_all("div", class_="time")[0].text
                    # 地点
                    location = ", ".join(
                        [span.text for span in row.find("td").find_all("span")]
                    )
                    # 课程
                    course = row.find_all("td")[1].find("span").text
                    # 状态
                    status = row.find_all("td")[2].text.strip()

                    exam = {
                        "if_finished": finished,
                        "time": time_exam,
                        "location": location,
                        "course": course,
                        "status": status,
                    }
                    exams.append(exam)

                    exams_msg += "名称：" + course + "\n"
                    exams_msg += "地点：" + location + "\n"
                    exams_msg += "时间：" + time_exam + "\n\n"
        exams_msg = exams_msg[:-2]
        if not is_finished_show:
            with open(self.info_file_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            info["exams"] = exams
            with open(self.info_file_path, "w", encoding="utf-8") as f:
                json.dump(info, f, indent=4, ensure_ascii=False)
        return exams

    # 获取课表信息
    async def get_course_table(self):
        url = "https://jwxt.nwpu.edu.cn/student/for-std/course-table"
        response = await self.client.get(url, headers=self.headers, timeout=10)
        semester = (
            BeautifulSoup(response.text, "html.parser")
            .find("select", {"id": "allSemesters"})
            .find("option", selected=True)
        )
        url = f"https://jwxt.nwpu.edu.cn/student/for-std/course-table/semester/{semester['value']}/print-data/{self.student_assoc}?hasExperiment=true"
        response = await self.client.get(url, headers=self.headers, timeout=10)
        with open(self.info_file_path, "r", encoding="utf-8") as f:
            info = json.load(f)
        info["course_table"] = response.text
        with open(self.info_file_path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=4, ensure_ascii=False)
        return response.text


import asyncio
import os


async def main():
    account = os.environ.get("ACCOUNT")
    logger.info(account)
    if not account:
        account = input("请输入账号: ")
    folder_path = Path(__file__).parent / "test"
    info_file_path = folder_path / f"{account}.json"
    nwpu_query_class = NwpuQuery(folder_path, info_file_path)
    if os.path.isfile(info_file_path):
        await nwpu_query_class.use_recent_cookies_login()
        grades = await nwpu_query_class.get_grades(if_only_last_sem=True)
        logger.info(f"成绩信息: {generate_grades_to_msg(grades)}")
        rank_msg = await nwpu_query_class.get_rank(False)
        logger.info(f"排名信息: {rank_msg}")
        exams = await nwpu_query_class.get_exams(True)
        logger.info(f"考试信息: {get_exams_msg(exams)}")
        course_table_str = await nwpu_query_class.get_course_table()
        logger.info(f"课表信息: {course_table_str}")
        course_schedule_pic_bytes = await draw_course_schedule_pic(
            folder_path, course_table_str
        )
        logger.info(f"课表信息: {course_schedule_pic_bytes[:20]}...")
        # 查看课表图片
        # from PIL import Image
        # from io import BytesIO
        # img = Image.open(BytesIO(course_schedule_pic_bytes))
        # img.show()

        # 空闲教室查询 先不修了
        # empty_classroom_path = await nwpu_query_class.get_empty_classroom()
        # logger.info(empty_classroom_path)
        await nwpu_query_class.close_client()
    else:
        password = os.environ.get("PASSWORD")
        logger.info(password)
        if not password:
            password = input("请输入密码: ")
        status, if_need_verification_code = await nwpu_query_class.login(
            account, password, "securephone"
        )
        logger.info(f"是否需要验证码{if_need_verification_code}")
        if status == 0:
            verification_code = None
            if if_need_verification_code:
                verification_code = input("请输入验证码: ")
            status = await nwpu_query_class.verification_code_login(verification_code)
            if status == 2:
                _, student_assoc_all = await nwpu_query_class.get_student_assoc()
                if student_assoc_all:
                    logger.info(f"")
                    result = []
                    for sid, info in student_assoc_all.items():
                        result.append(f"\n身份号 {sid}:\n{info}\n")
                    logger.info(f"查询到多个身份:\n\n{''.join(result)}")
                    student_assoc = input("请输入要绑定的身份号（六位纯数字）")
                    with open(
                        nwpu_query_class.info_file_path, "r", encoding="utf-8"
                    ) as f:
                        info = json.load(f)
                    info["student_assoc"] = student_assoc
                    with open(
                        nwpu_query_class.info_file_path, "w", encoding="utf-8"
                    ) as f:
                        json.dump(info, f, indent=4, ensure_ascii=False)
                logger.info("登陆成功，再次执行本程序即可登入翱翔教务获取信息")
            elif status == 3:
                print(f"验证码错误，请重新输入验证码\n输入 停止 可以终止此次登陆")
            else:
                print(f"出错了，返回状态码{status}，此次登陆已终止")
        elif status == -1:
            print(f"密码错误，请重新输入密码\n输入 停止 可以终止此次登陆")
        else:
            print(f"出错了，返回状态码{status}，此次登陆已终止")


if __name__ == "__main__":
    asyncio.run(main())

    # 查询空闲教室
    # async def get_empty_classroom(self, folder_path):
    #     # 获取token
    #     url = 'https://idle-classroom.nwpu.edu.cn/cas/login?redirect_uri=https://idle-classroom.nwpu.edu.cn/ui/'
    #     response = await self.client.get(url, headers=self.headers)
    #     match = re.search(r"token=([^&]+)", str(response.url))
    #     token_value = match.group(1)
    #     headers5 = self.headers3.copy()
    #     headers5['X-Id-Token'] = token_value
    #     # 获取所有教学楼
    #     url = "https://idle-classroom.nwpu.edu.cn/api/idleclassroom/building/长安校区"
    #     response = await self.client.get(url, headers=headers5)
    #     building_all = json.loads(response.text)["data"]
    #     building_all = sorted(building_all, key=lambda x: 0 if "教学西楼" in x else 1)
    #     # 计算当前周数
    #     url = "https://idle-classroom.nwpu.edu.cn/api/idleclassroom/week/长安校区"
    #     response = await self.client.get(url, headers=headers5)
    #     week_of_semester = None
    #     start_date_of_week = None
    #     end_date_of_week = None
    #     for week in json.loads(response.text)["data"]:
    #         if week["startDay"] <= int(time.time() * 1000) <= week["endDay"]:
    #             week_of_semester = week["weekOfSemester"]
    #             start_date_of_week = datetime.fromtimestamp(int(week["startDay"]) / 1000).strftime("%Y-%m-%d")
    #             end_date_of_week = datetime.fromtimestamp(int(week["endDay"]) / 1000).strftime("%Y-%m-%d")
    #             break
    #     # 获取课程总节数
    #     url = "https://idle-classroom.nwpu.edu.cn/api/idleclassroom/unit/长安校区"
    #     response = await self.client.get(url, headers=headers5)
    #     unit_list = json.loads(response.text)["data"]
    #     # 获取空闲教室
    #     empty_classroom_all_data=[]
    #     for building in building_all:
    #         url = "https://idle-classroom.nwpu.edu.cn/api/idleclassroom/classroom"
    #         params = {
    #             "building": building,
    #             "campus": "长安校区",
    #             "weekOfSemester": week_of_semester,
    #             "startDateOfWeek": start_date_of_week,
    #             "endDateOfWeek": end_date_of_week,
    #             "roomType": "-2",
    #             "seatCode": "-2",
    #         }
    #         response = await self.client.get(url, headers=headers5, params=params)
    #         data = json.loads(response.text)
    #         if data["code"] == 200:
    #             data["data"]["countMap"][str(datetime.today().isoweekday())] = sorted(data["data"]["countMap"][str(datetime.today().isoweekday())], key=lambda x: int(''.join(filter(str.isdigit, x["classroomName"]))))
    #         empty_classroom_all_data.append(data)
    #     return await draw_empty_classroom_pic(folder_path, unit_list, building_all, empty_classroom_all_data)
