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
"""

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
from .draw_empty_classroom_pic import draw_empty_classroom_pic
from .utils import handle_training_program_data, handle_completed_and_incomplete_course, max_dict_depth, write_to_excel, \
    fromat_excel
import urllib.parse


class NwpuQuery:
    def __init__(self):
        self.state_key = None
        self.fpVisitorId = None
        self.data = None
        self.state_code = None
        self.execution = None
        self.password = None
        self.username = None
        self.device = None
        self.headers = {
            'accept': ('text/html,application/xhtml+xml,application/xml;q=0.9,image/avif, '
                       'image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'),
            'accept-encoding': 'deflate, br',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'referer': 'https://ecampus.nwpu.edu.cn/main.html',
            'sec-ch-ua': '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Linux"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/103.0.0.0 Safari/537.36')
        }
        self.headers2 = self.headers.copy()
        self.headers2['X-Requested-With'] = 'XMLHttpRequest'
        self.headers3 = self.headers2.copy()
        self.headers3['Content-Type'] = 'application/json; charset=UTF-8'
        self.headers4 = self.headers3.copy()
        self.headers4['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        self.student_assoc = None
        self.client = httpx.AsyncClient(follow_redirects=True)

    async def close_client(self):
        await self.client.aclose()

    async def use_recent_cookies_login(self, cookies_path):
        url = "https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn%2F%3Fpath%3Dhttps%3A%2F%2Fecampus.nwpu.edu.cn"
        if os.path.isfile(cookies_path):
            with open(cookies_path, 'r', encoding='utf-8') as f:
                new_cookies = json.loads(f.read())
            for name, value in new_cookies.items():
                self.client.cookies.set(name, value)
        else:
            return False
        response = await self.client.get(url, headers=self.headers, timeout=10)
        if len(response.history) != 0:
            url = 'https://jwxt.nwpu.edu.cn/student/sso-login'
            response = await self.client.get(url, headers=self.headers)
            logger.debug("第一次sso-login 登陆结果")
            logger.debug(response.status_code)
            if response.status_code == 200:
                return True
            retry_count = 3
            current_retry_count = 0
            while current_retry_count < retry_count:
                await asyncio.sleep(2)
                url = 'https://jwxt.nwpu.edu.cn/student/sso-login'
                response = await self.client.get(url, headers=self.headers)
                logger.debug(f"第 {current_retry_count} 次 sso-login 登陆结果: {response.status_code}")
                if response.status_code == 200:
                    logger.debug("登录成功")
                    break
                current_retry_count += 1
                if current_retry_count == retry_count and response.status_code != 200:
                    raise Exception(f"翱翔教务登录失败，状态码{response.status_code}")
            # 超过重试次数也会返回True 会在后面抛出错误 不处理
            # 返回False会删除cookies文件
            return True
        else:
            return False

    async def login(self, username, password, device):
        url = ("https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn"
               "%2F%3Fpath%3Dhttps%3A%2F%2Fecampus.nwpu.edu.cn")
        self.device = device
        self.username = username

        # RSA加密password
        url_key = 'https://uis.nwpu.edu.cn/cas/jwt/publicKey'
        response = await self.client.get(url_key, headers=self.headers2, timeout=5)
        public_key = rsa.PublicKey.load_pkcs1_openssl_pem(response.text.encode())
        password = rsa.encrypt(password.encode(), public_key)
        password = "__RSA__" + base64.b64encode(password).decode()
        self.password = password

        response = await self.client.get(url, headers=self.headers, timeout=10)
        response.encoding = 'utf-8'
        str1 = re.search('var hmSiteId = "(.*?)"', response.text)
        new_cookies = {
            ("Hm_lvt_" + str1.group(1)): str(int(time.time())),
            ("Hm_lpvt_" + str1.group(1)): str(int(time.time()))
        }
        for name, value in new_cookies.items():
            self.client.cookies.set(name, value)

        self.execution = re.search('name="execution" value="(.*?)"', response.text)
        self.fpVisitorId = re.search('name="fpVisitorId" value="(.*?)"', response.text)

        url = 'https://uis.nwpu.edu.cn/cas/mfa/detect'
        data = {
            'username': self.username,
            'password': self.password,
        }
        response = await self.client.post(url, data=data, headers=self.headers2, timeout=15)
        self.state_code = json.loads(response.text)['data']['state']

        url = f'https://uis.nwpu.edu.cn/cas/mfa/initByType/{device}?state={self.state_code}'
        response = await self.client.get(url, headers=self.headers2, timeout=15)
        if json.loads(response.text)['code'] != 0:
            return json.loads(response.text)['code']
        else:
            gid = json.loads(response.text)['data']['gid']
            url = f'https://uis.nwpu.edu.cn/attest/api/guard/{device}/send'
            self.data = {'gid': gid}
            await self.client.post(url, data=json.dumps(self.data), headers=self.headers3, timeout=15)
            return 0

    async def login_with_qr(self, folder_path):
        url = ("https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn"
               "%2F%3Fpath%3Dhttps%3A%2F%2Fecampus.nwpu.edu.cn")

        response = await self.client.get(url, headers=self.headers)
        response.encoding = 'utf-8'
        str1 = re.search('var hmSiteId = "(.*?)"', response.text)
        new_cookies = {
            ("Hm_lvt_" + str1.group(1)): str(int(time.time())),
            ("Hm_lpvt_" + str1.group(1)): str(int(time.time()))
        }
        for name, value in new_cookies.items():
            self.client.cookies.set(name, value)
        self.fpVisitorId = re.search('name="fpVisitorId" value="(.*?)"', response.text)

        url = 'https://uis.nwpu.edu.cn/cas/qr/init'
        response = await self.client.get(url, headers=self.headers2)
        self.state_key = json.loads(response.text)['data']['stateKey']
        url = f'https://uis.nwpu.edu.cn/cas/qr/qrcode?r={int(time.time_ns() / 1000000)}'
        response = await self.client.get(url, headers=self.headers)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        with open(os.path.join(folder_path, 'qr.png'), 'wb') as f:
            f.write(response.content)

    async def waiting_to_scan_qr(self, folder_path):
        url = 'https://uis.nwpu.edu.cn/cas/qr/comet'
        while True:
            time.sleep(1)
            response = await self.client.post(url, headers=self.headers2)
            code = json.loads(response.text)["code"]
            if code == 1:
                return False
            status = int(json.loads(response.text)["data"]["qrCode"]["status"])
            if status == 3:
                url = ("https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn"
                       "%2F%3Fpath%3Dhttps%3A%2F%2Fecampus.nwpu.edu.cn")
                self.data = {
                    'qrCodeKey': self.state_key,
                    'currentMenu': '3',
                    'geolocation': '',
                    'fpVisitorId': self.fpVisitorId
                }
                await self.client.post(url, data=self.data, headers=self.headers)
                cookies = {cookie.name: cookie.value for cookie in self.client.cookies.jar}
                with open((os.path.join(folder_path, 'cookies.txt')), 'w', encoding='utf-8') as f:
                    f.write(json.dumps(cookies, indent=4, ensure_ascii=False))
                url = 'https://jwxt.nwpu.edu.cn/student/sso-login'
                response = await self.client.get(url, headers=self.headers)
                logger.debug("第一次sso-login 登陆结果")
                logger.debug(response.status_code)
                if response.status_code != 200:
                    retry_count = 5
                    current_retry_count = 0
                    while current_retry_count < retry_count:
                        current_retry_count += 1
                        await asyncio.sleep(2)
                        url = 'https://jwxt.nwpu.edu.cn/student/sso-login'
                        response = await self.client.get(url, headers=self.headers)
                        logger.debug(f"第 {current_retry_count} 次 sso-login 登陆结果: {response.status_code}")
                        if response.status_code == 200:
                            logger.debug("登录成功")
                            break
                return True

    async def verification_code_login(self, captcha, folder_path):
        url = f'https://uis.nwpu.edu.cn/attest/api/guard/{self.device}/valid'
        self.data['code'] = captcha
        response = await self.client.post(url, data=json.dumps(self.data), headers=self.headers3)
        if json.loads(response.text)["data"]["status"] != 2:
            return json.loads(response.text)["data"]["status"]
        else:
            url = ("https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn"
                   "%2F%3Fpath%3Dhttps%3A%2F%2Fecampus.nwpu.edu.cn")
            self.data = {
                'username': self.username,
                'password': self.password,
                'rememberMe': 'true',
                'currentMenu': '1',
                'mfaState': self.state_code,
                'execution': self.execution.group(1),
                '_eventId': 'submit',
                'geolocation': '',
                'fpVisitorId': self.fpVisitorId,
                'submit': '稍等片刻……',
            }
            await self.client.post(url, data=self.data, headers=self.headers)
            cookies = {cookie.name: cookie.value for cookie in self.client.cookies.jar}
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            with open((os.path.join(folder_path, 'cookies.txt')), 'w', encoding='utf-8') as f:
                f.write(json.dumps(cookies, indent=4, ensure_ascii=False))
            url = 'https://jwxt.nwpu.edu.cn/student/sso-login'
            response = await self.client.get(url, headers=self.headers)
            logger.debug("第一次sso-login 登陆结果")
            logger.debug(response.status_code)
            if response.status_code != 200:
                retry_count = 3
                current_retry_count = 0
                while current_retry_count < retry_count:
                    current_retry_count += 1
                    await asyncio.sleep(2)
                    url = 'https://jwxt.nwpu.edu.cn/student/sso-login'
                    response = await self.client.get(url, headers=self.headers)
                    logger.debug(f"第 {current_retry_count} 次 sso-login 登陆结果: {response.status_code}")
                    if response.status_code == 200:
                        logger.debug("登录成功")
                        break
            return 2

    # 查询student_assoc
    async def get_student_assoc(self, folder_path) -> bool:
        url = 'https://jwxt.nwpu.edu.cn/student/for-std/grade/sheet'
        response = await self.client.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        student_id_element_1 = soup.find('input', {'id': 'studentId'})
        student_id_element_2 = soup.find('button', {'class': 'footer btn btn-primary'})
        student_assoc = None
        if student_id_element_1:
            student_assoc = student_id_element_1['value']
        elif student_id_element_2:
            student_assoc = student_id_element_2['value']
        if student_assoc:
            self.student_assoc = student_assoc
            info = {"student_assoc": self.student_assoc}
            with open(os.path.join(folder_path, 'info.json'), 'w', encoding='utf-8') as f:
                json.dump(info, f, indent=4, ensure_ascii=False)
            return True
        else:
            logger.error("get_student_assoc failed", folder_path)
            return False

    # 查询成绩
    async def get_grades(self, folder_path, sem_query=0):
        # 0 是查询全部成绩 是几就是查询后几个学期的
        try:
            url = 'https://jwxt.nwpu.edu.cn/student/for-std/grade/sheet'
            response = await self.client.get(url, headers=self.headers, timeout=5)
            semester = re.findall('<option value="(.+?)"', response.text)
            grades = []
            grades_msg = []
            sem_query_ = sem_query
            if sem_query == 0: sem_query = len(semester)
            for sem in semester:
                url = 'https://jwxt.nwpu.edu.cn/student/for-std/grade/sheet/info/' + self.student_assoc + '?semester=' + sem
                response = await self.client.get(url, headers=self.headers2, timeout=5)
                if response.status_code != 200:
                    await self.get_student_assoc(folder_path)
                    raise Exception("student_assoc重新获取")
                response = json.loads(response.text)['semesterId2studentGrades'][sem]
                for course in response:
                    name = course['course']['nameZh']
                    code = course['course']['code']
                    course_type = course['courseType']['nameZh']
                    grade_score = course['gaGrade']
                    gpa = str(course['gp'])
                    credit = course['course']['credits']
                    grade_detail = re.findall('>(.+?)</span>', course['gradeDetail'])
                    if re.findall(r"缓考成绩:\d+", course['gradeDetail']):
                        grade_detail += re.findall(r"缓考成绩:\d+", course['gradeDetail'])
                    if re.findall(r"补考成绩:\d+", course['gradeDetail']):
                        grade_detail += re.findall(r"补考成绩:\d+", course['gradeDetail'])
                    if grade_detail != [None] and grade_detail != []:
                        grade_detail[-1] += (course['fillAGrace'] or "")
                    grades_msg.append(f'{name}, {grade_score}, {gpa}, {credit}, {grade_detail}')
                    grades_one_subject = {
                        "name": name,
                        "code": code,
                        "course_type": course_type,
                        "grade_score": grade_score,
                        "gpa": gpa,
                        "credit": credit,
                        "grade_detail": grade_detail
                    }
                    grades.append(grades_one_subject)
                if (sem_query := sem_query - 1) == 0: break
            # 获取全部成绩时才保存成绩
            # 并且非空时才保存 因为偶尔会出现bug推送全部成绩 故推测是因为上一次获取的是全空
            if sem_query_ == 0 and grades:
                with open(os.path.join(folder_path, 'grades.json'), 'w', encoding='utf-8') as f:
                    json.dump(grades, f, indent=4, ensure_ascii=False, )
            return grades_msg, grades
        except httpx.TimeoutException:
            logger.error(f"{folder_path}成绩获取超时，返回None，在定时任务中会跳过，在指令获取中会返回错误信息")
            return None, None

    async def get_rank(self, folder_path, if_all=False):
        url = 'https://jwxt.nwpu.edu.cn/student/for-std/student-portrait'
        await self.client.get(url, headers=self.headers, timeout=5)
        url = 'https://jwxt.nwpu.edu.cn/student/for-std/student-portrait/getStdInfo?bizTypeAssoc=2&cultivateTypeAssoc=1'
        response = await self.client.get(url, headers=self.headers, timeout=5)
        grade = response.json()['student']['grade']
        major_id = response.json()['student']['major']['id']
        major_name = response.json()['student']['major']['nameZh']
        url = f'https://jwxt.nwpu.edu.cn/student/for-std/student-portrait/getGradeAnalysis?bizTypeAssoc=2&grade={grade}&majorAssoc={major_id}&semesterAssoc='
        response = await self.client.get(url, headers=self.headers, timeout=5)
        score_range_count = response.json()['scoreRangeCount']
        total_people_numb = sum(score_range_count.values())
        url = f"https://jwxt.nwpu.edu.cn/student/for-std/student-portrait/getMyGpa?studentAssoc={self.student_assoc}"
        response = await self.client.get(url, headers=self.headers, timeout=5)
        if response.status_code != 200:
            await self.get_student_assoc(folder_path)
            raise Exception("student_assoc重新获取")
        before_rank_gpa = response.json()['stdGpaRankDto']['beforeRankGpa']
        after_rank_gpa = response.json()['stdGpaRankDto']['afterRankGpa']
        url = f'https://jwxt.nwpu.edu.cn/student/for-std/student-portrait/getMyGrades?studentAssoc={self.student_assoc}&semesterAssoc='
        response = await self.client.get(url, headers=self.headers, timeout=5)
        if response.json() is None:
            return "暂无排名喵", 0
        else:
            gpa = response.json()['gpa']
            rank_msg = f"你的绩点是{gpa}，{major_name}专业\n根据学生画像饼图计算专业/学院总人数为{total_people_numb}，排名接口已经消失"
            rank = 0
            if before_rank_gpa:
                rank_msg += f"\n和前一名差{before_rank_gpa - gpa:.3f}绩点"
            if after_rank_gpa:
                rank_msg += f"\n与后一名差{gpa - after_rank_gpa:.3f}绩点"
            with open((os.path.join(folder_path, 'rank.txt')), 'w', encoding='utf-8') as f:
                f.write(str(rank))
            if not if_all:
                return rank_msg, 0
            semesters_all = {semester["id"]: semester["nameZh"] for semester in response.json()['semesters']}
            for semester in [semester["id"] for semester in response.json()['semesters']]:
                url = f'https://jwxt.nwpu.edu.cn/student/for-std/student-portrait/getMyGrades?studentAssoc={self.student_assoc}&semesterAssoc={semester}'
                response = await self.client.get(url, headers=self.headers, timeout=5)
                if response.json() is None:
                    continue
                gpa = response.json()['gpa']
                rank_msg += f"\n\n{semesters_all[semester]}\n你的绩点是{gpa}\n排名接口已经消失"
            return rank_msg, 0

    # 查询考试信息
    async def get_exams(self, folder_path, is_finished_show=False):
        url = 'https://jwxt.nwpu.edu.cn/student/for-std/exam-arrange'
        response = await self.client.get(url, headers=self.headers, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')
        exams = []
        exams_msg = ""
        for row in rows:
            if row.has_attr('data-finished'):
                # 是否结束
                finished = row['data-finished']
                if (not is_finished_show and finished == 'false') or is_finished_show:
                    # 时间
                    time_exam = row.find_all('div', class_='time')[0].text
                    # 地点
                    location = ', '.join([span.text for span in row.find('td').find_all('span')])
                    # 课程
                    course = row.find_all('td')[1].find('span').text
                    # 状态
                    status = row.find_all('td')[2].text.strip()

                    exam = {
                        "if_finished": finished,
                        "time": time_exam,
                        "location": location,
                        "course": course,
                        "status": status
                    }
                    exams.append(exam)

                    exams_msg += "名称：" + course + "\n"
                    exams_msg += "地点：" + location + "\n"
                    exams_msg += "时间：" + time_exam + "\n\n"
        exams_msg = exams_msg[:-2]
        if not is_finished_show:
            with open(os.path.join(folder_path, 'exams.json'), 'w', encoding='utf-8') as f:
                json.dump(exams, f, indent=4, ensure_ascii=False)
        return exams_msg, exams

    # 获取课表信息
    async def get_course_table(self, folder_path):
        url = 'https://jwxt.nwpu.edu.cn/student/for-std/course-table'
        response = await self.client.get(url, headers=self.headers, timeout=10)
        semester = BeautifulSoup(response.text, 'html.parser').find('select', {'id': 'allSemesters'}).find('option', selected=True)
        url = f"https://jwxt.nwpu.edu.cn/student/for-std/course-table/semester/{semester['value']}/print-data/{self.student_assoc}?hasExperiment=true"
        response = await self.client.get(url, headers=self.headers, timeout=10)
        if response.status_code != 200:
            await self.get_student_assoc(folder_path)
            raise Exception("student_assoc重新获取")
        course_table_path = os.path.join(folder_path, f'{semester.text}.html')
        for file_path in [f for f in list(Path(folder_path).glob("*.html")) if f.name.endswith(("春.html", "夏.html", "秋.html"))]:
            file_path.unlink()
        with open(course_table_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
        return course_table_path, f"{semester.text}.html"

    # 获取综测排名
    async def get_water_rank(self):
        url = 'https://xgpt.nwpu.edu.cn/'
        await self.client.get(url, headers=self.headers)
        url = 'https://xgpt.nwpu.edu.cn/xsfw/sys/xggzptapp/modules/xszm/getFzxx.do'
        response = await self.client.post(url, headers=self.headers, data={"data": urllib.parse.quote(str({}))})
        url = 'https://xgpt.nwpu.edu.cn/xsfw/sys/xggzptapp/modules/xszm/getFxYy.do'
        response = await self.client.post(url, headers=self.headers4, data={"data": urllib.parse.quote(str({"FZDM": [
            data["FZDM"] for data in json.loads(response.text)["data"] if data["FZMC"] == "学生服务"][0]}))})
        url = f'https://xgpt.nwpu.edu.cn/xsfw/sys/xggzptapp/modules/pubWork/appShow.do?id={[data["YYID"] for data in json.loads(response.text)["data"] if data["YYMC"] == "综合测评"][0]}'
        response = await self.client.get(url, headers=self.headers)
        if "选择身份" in response.text:
            role_id = re.search(r',{"id":"(.*?)","text":"本科生组"', response.text).group(1)
            url = 'https://xgpt.nwpu.edu.cn/xsfw/sys/funauthapp/selectRole.do'
            await self.client.post(url, headers=self.headers4,
                                   data={"ROLEID": role_id, "APPNAME": "zhcptybbapp"})
            url = 'https://xgpt.nwpu.edu.cn/xsfw/sys/zhcptybbapp/*default/index.do'
            response = await self.client.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', text=re.compile(r'var pageMeta'))
        begin_year = int(re.search(r'"userId":"(\d+)"', script_tag.string).group(1)[:4])
        now_year = int(re.search(r'"curXN":(\d+)', script_tag.string).group(1)[:4])
        url = 'https://xgpt.nwpu.edu.cn/xsfw/sys/zhcptybbapp/modules/evaluationApplyController/getEvaluationResultsByXn.do'
        water_rank_msg = ""
        for year in range(begin_year, now_year + 1):
            response = await self.client.post(url, headers=self.headers4,
                                              data={"data": urllib.parse.quote(str({"CPXN": str(year), "CPXQ": "3"}))})
            result = response.json()
            if result["data"]:
                water_rank_msg += f'{year}学年 总成绩{result["data"]["ZCJ"]}\n专业排名 {result["data"]["ZYNJPM"]}/{result["data"]["ZYNJRS"]} 班级排名 {result["data"]["BJPM"]}/{result["data"]["BJRS"]}\n\n'
        return water_rank_msg[:-2]

    # 获取培养方案完成情况
    async def get_training_program(self, folder_path):
        url = f'https://jwxt.nwpu.edu.cn/student/for-std/program/root-module-json/{self.student_assoc}'
        response = await self.client.get(url, headers=self.headers2, timeout=10)
        if response.status_code != 200:
            await self.get_student_assoc(folder_path)
            raise Exception("student_assoc重新获取")
        # training_program 的值
        training_program_data = []
        training_program_data_raw = json.loads(response.text)["children"]
        with open(os.path.join(folder_path, "training_program_data_raw.json"), "w", encoding='utf-8') as file:
            json.dump(training_program_data_raw, file, ensure_ascii=False, indent=4)
        handle_training_program_data(training_program_data_raw, training_program_data)
        with open(os.path.join(folder_path, "training_program_data.json"), "w", encoding='utf-8') as file:
            json.dump(training_program_data, file, ensure_ascii=False, indent=4)
        # grades 的值
        with open(os.path.join(folder_path, "grades.json"), "r", encoding='utf-8') as f:
            grades_data = json.load(f)
        # 将已修课程转换为字典形式，便于查找
        completed_courses_all = {course["code"]: course for course in grades_data}
        completed_courses_all_static = copy.deepcopy(completed_courses_all)
        # 删除 requiredCredits 为 0 的首层大分组
        training_program_data = [node for node in training_program_data if node["requiredCredits"] != 0]
        # 匹配已修和未修课程
        handle_completed_and_incomplete_course(training_program_data, completed_courses_all,
                                               completed_courses_all_static)
        with open(os.path.join(folder_path, "training_program_data_handle.json"), "w", encoding='utf-8') as file:
            json.dump(training_program_data, file, ensure_ascii=False, indent=4)
        # 创建Excel表格
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = "培养方案"
        # 写入数据
        write_to_excel(training_program_data, sheet, max_dict_depth(training_program_data))
        # 格式化表格
        fromat_excel(sheet, completed_courses_all)
        xlsx_name = "培养方案完成情况.xlsx"
        xlsx_path = os.path.join(folder_path, xlsx_name)
        wb.save(xlsx_path)
        return xlsx_path, xlsx_name

    # 查询空闲教室
    async def get_empty_classroom(self, folder_path):
        # 获取token
        url = 'https://idle-classroom.nwpu.edu.cn/cas/login?redirect_uri=https://idle-classroom.nwpu.edu.cn/ui/'
        response = await self.client.get(url, headers=self.headers)
        match = re.search(r"token=([^&]+)", str(response.url))
        token_value = match.group(1)
        headers5 = self.headers3.copy()
        headers5['X-Id-Token'] = token_value
        # 获取所有教学楼
        url = "https://idle-classroom.nwpu.edu.cn/api/idleclassroom/building/长安校区"
        response = await self.client.get(url, headers=headers5)
        building_all = json.loads(response.text)["data"]
        building_all = sorted(building_all, key=lambda x: 0 if "教学西楼" in x else 1)
        # 计算当前周数
        url = "https://idle-classroom.nwpu.edu.cn/api/idleclassroom/week/长安校区"
        response = await self.client.get(url, headers=headers5)
        week_of_semester = None
        start_date_of_week = None
        end_date_of_week = None
        for week in json.loads(response.text)["data"]:
            if week["startDay"] <= int(time.time() * 1000) <= week["endDay"]:
                week_of_semester = week["weekOfSemester"]
                start_date_of_week = datetime.fromtimestamp(int(week["startDay"]) / 1000).strftime("%Y-%m-%d")
                end_date_of_week = datetime.fromtimestamp(int(week["endDay"]) / 1000).strftime("%Y-%m-%d")
                break
        # 获取课程总节数
        url = "https://idle-classroom.nwpu.edu.cn/api/idleclassroom/unit/长安校区"
        response = await self.client.get(url, headers=headers5)
        unit_list = json.loads(response.text)["data"]
        # 获取空闲教室
        empty_classroom_all_data=[]
        for building in building_all:
            url = "https://idle-classroom.nwpu.edu.cn/api/idleclassroom/classroom"
            params = {
                "building": building,
                "campus": "长安校区",
                "weekOfSemester": week_of_semester,
                "startDateOfWeek": start_date_of_week,
                "endDateOfWeek": end_date_of_week,
                "roomType": "-2",
                "seatCode": "-2",
            }
            response = await self.client.get(url, headers=headers5, params=params)
            data = json.loads(response.text)
            if data["code"] == 200:
                data["data"]["countMap"][str(datetime.today().isoweekday())] = sorted(data["data"]["countMap"][str(datetime.today().isoweekday())], key=lambda x: int(''.join(filter(str.isdigit, x["classroomName"]))))
            empty_classroom_all_data.append(data)
        return await draw_empty_classroom_pic(folder_path, unit_list, building_all, empty_classroom_all_data)
        