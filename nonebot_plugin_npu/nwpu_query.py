'''
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
'''

from nonebot import logger
import re
import time
import json
import os
import httpx
import rsa
import base64
from bs4 import BeautifulSoup
import openpyxl
import copy
from .utils import handle_training_program_data, handle_completed_and_incomplete_course, max_dict_depth, write_to_excel, fromat_excel
import urllib.parse

class NwpuQuery():
    def __init__(self):
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
        URL = "https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn%2F%3Fpath%3Dhttps%3A%2F%2Fecampus.nwpu.edu.cn"
        if os.path.isfile(cookies_path):
            with open(cookies_path, 'r', encoding='utf-8') as f:
                new_cookies = json.loads(f.read())
            for name, value in new_cookies.items():
                self.client.cookies.set(name, value)
        else:
            return False
        response = await self.client.get(URL, headers=self.headers)
        if len(response.history) != 0:
            URL = 'https://jwxt.nwpu.edu.cn/student/sso-login'
            response = await self.client.get(URL, headers=self.headers)
            return True
        else:
            return False

    async def login(self, username, password, device, folder_path):
        URL = ("https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn"
               "%2F%3Fpath%3Dhttps%3A%2F%2Fecampus.nwpu.edu.cn")
        self.device = device
        self.username = username

        # RSA加密password
        URL_key = 'https://uis.nwpu.edu.cn/cas/jwt/publicKey'
        response = await self.client.get(URL_key, headers=self.headers2)
        public_key = rsa.PublicKey.load_pkcs1_openssl_pem(response.text.encode())
        password = rsa.encrypt(password.encode(), public_key)
        password = "__RSA__" + base64.b64encode(password).decode()
        self.password = password

        response = await self.client.get(URL, headers=self.headers)
        response.encoding = 'utf-8'
        str1 = re.search('var hmSiteId = "(.*?)"', response.text)
        new_cookies = {
            ("Hm_lvt_" + str1.group(1)): str(int(time.time())),
            ("Hm_lpvt_" + str1.group(1)): str(int(time.time()))
        }
        for name, value in new_cookies.items():
            self.client.cookies.set(name, value)
        
        self.execution = re.search('name="execution" value="(.*?)"', response.text)

        URL = 'https://uis.nwpu.edu.cn/cas/mfa/detect'
        data = {
            'username': self.username,
            'password': self.password,
        }
        response = await self.client.post(URL, data=data, headers=self.headers2)
        self.state_code = json.loads(response.text)['data']['state']

        URL = f'https://uis.nwpu.edu.cn/cas/mfa/initByType/{device}?state={self.state_code}'
        response = await self.client.get(URL, headers=self.headers2)
        if json.loads(response.text)['code'] != 0:
            return json.loads(response.text)['code']
        else:
            gid = json.loads(response.text)['data']['gid']
            URL = f'https://uis.nwpu.edu.cn/attest/api/guard/{device}/send'
            self.data = {'gid': gid}
            await self.client.post(URL, data=json.dumps(self.data), headers=self.headers3)
            return 0

    async def login_with_qr(self, folder_path):
        URL = ("https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn"
               "%2F%3Fpath%3Dhttps%3A%2F%2Fecampus.nwpu.edu.cn")

        response = await self.client.get(URL, headers=self.headers)
        response.encoding = 'utf-8'
        str1 = re.search('var hmSiteId = "(.*?)"', response.text)
        new_cookies = {
            ("Hm_lvt_" + str1.group(1)): str(int(time.time())),
            ("Hm_lpvt_" + str1.group(1)): str(int(time.time()))
        }
        for name, value in new_cookies.items():
            self.client.cookies.set(name, value)
        self.fpVisitorId = re.search('name="fpVisitorId" value="(.*?)"', response.text)

        URL = 'https://uis.nwpu.edu.cn/cas/qr/init'
        response = await self.client.get(URL, headers=self.headers2)
        self.state_key = json.loads(response.text)['data']['stateKey']
        URL = f'https://uis.nwpu.edu.cn/cas/qr/qrcode?r={int(time.time_ns()/1000000)}'
        response = await self.client.get(URL, headers=self.headers)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        with open(os.path.join(folder_path, 'qr.png'), 'wb') as f:
            f.write(response.content)

    async def wating_to_scan_qr(self,folder_path):
        URL = 'https://uis.nwpu.edu.cn/cas/qr/comet'
        while True:
            time.sleep(1)
            response = await self.client.post(URL, headers=self.headers2)
            code = json.loads(response.text)["code"]
            if code == 1:
                return False
            status = int(json.loads(response.text)["data"]["qrCode"]["status"])
            if status == 3:
                URL = ("https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn"
                    "%2F%3Fpath%3Dhttps%3A%2F%2Fecampus.nwpu.edu.cn")
                self.data = {
                    'qrCodeKey': self.state_key,
                    'currentMenu': '3',
                    'geolocation': '',
                    'fpVisitorId': self.fpVisitorId
                }
                await self.client.post(URL, data=self.data, headers=self.headers)
                cookies = {cookie.name: cookie.value for cookie in self.client.cookies.jar}
                with open((os.path.join(folder_path, 'cookies.txt')), 'w', encoding='utf-8') as f:
                    f.write(json.dumps(cookies, indent=4, ensure_ascii=False))
                URL = 'https://jwxt.nwpu.edu.cn/student/sso-login'
                await self.client.get(URL, headers=self.headers)
                return True

    async def verification_code_login(self, captcha, folder_path):
        URL = f'https://uis.nwpu.edu.cn/attest/api/guard/{self.device}/valid'
        self.data['code'] = captcha
        response = await self.client.post(URL, data=json.dumps(self.data), headers=self.headers3)
        if json.loads(response.text)["data"]["status"] != 2:
            return json.loads(response.text)["data"]["status"]
        else:
            URL = ("https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn"
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
                'submit': '稍等片刻……',
            }
            await self.client.post(URL, data=self.data, headers=self.headers)
            cookies = {cookie.name: cookie.value for cookie in self.client.cookies.jar}
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            with open((os.path.join(folder_path, 'cookies.txt')), 'w', encoding='utf-8') as f:
                f.write(json.dumps(cookies, indent=4, ensure_ascii=False))
            URL = 'https://jwxt.nwpu.edu.cn/student/sso-login'
            await self.client.get(URL, headers=self.headers)
            return 2

    # 查询student_assoc
    async def get_student_assoc(self, folder_path) -> bool:
        URL = 'https://jwxt.nwpu.edu.cn/student/for-std/grade/sheet'
        response = await self.client.get(URL, headers=self.headers)
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
            logger.info("get_student_assoc failed",folder_path)
            return False

    # 查询成绩
    async def get_grades(self, folder_path, sem_query=0):
        # 0 是查询全部成绩 是几就是查询后几个学期的
        try:
            URL = 'https://jwxt.nwpu.edu.cn/student/for-std/grade/sheet'
            response = await self.client.get(URL, headers=self.headers, timeout=5)
            semester = re.findall('<option value="(.+?)"', response.text)
            grades = []
            grades_msg = []
            sem_query_ = sem_query
            if sem_query == 0: sem_query = len(semester)
            for sem in semester:
                URL = 'https://jwxt.nwpu.edu.cn/student/for-std/grade/sheet/info/' + self.student_assoc + '?semester=' + sem
                response = await self.client.get(URL, headers=self.headers2, timeout=5)
                if response.status_code != 200:
                    logger.error(f"{folder_path}成绩获取失败 状态码: {response.status_code}，返回None，在定时任务中会跳过，在指令获取中会返回错误信息")
                    return None, None
                response = json.loads(response.text)['semesterId2studentGrades'][sem]
                for course in response:
                    name = course['course']['nameZh']
                    code = course['course']['code']
                    course_type = course['courseType']['nameZh']
                    grade_score = course['gaGrade']
                    gpa = str(course['gp'])
                    credit = course['course']['credits']
                    grade_detail = re.findall('>(.+?)</span>', course['gradeDetail'])
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
            if sem_query_ == 0:
                with open(os.path.join(folder_path, 'grades.json'), 'w', encoding='utf-8') as f:
                    json.dump(grades, f, indent=4, ensure_ascii=False, )
            return grades_msg, grades
        except httpx.TimeoutException:
            logger.error(f"{folder_path}成绩获取超时，返回None，在定时任务中会跳过，在指令获取中会返回错误信息")
            return None, None

    async def get_rank(self, folder_path):
        URL = 'https://jwxt.nwpu.edu.cn/student/for-std/student-portrait'
        await self.client.get(URL, headers=self.headers, timeout=5)
        URL = 'https://jwxt.nwpu.edu.cn/student/for-std/student-portrait/getStdInfo?bizTypeAssoc=2&cultivateTypeAssoc=1'
        response = await self.client.get(URL, headers=self.headers, timeout=5)
        grade = response.json()['student']['grade']
        major_id = response.json()['student']['major']['id']
        major_name = response.json()['student']['major']['nameZh']
        URL = f'https://jwxt.nwpu.edu.cn/student/for-std/student-portrait/getGradeAnalysis?bizTypeAssoc=2&grade={grade}&majorAssoc={major_id}&semesterAssoc='
        response = await self.client.get(URL, headers=self.headers, timeout=5)
        score_range_count = response.json()['scoreRangeCount']
        total_poeple_num = sum(score_range_count.values())
        URL = f'https://jwxt.nwpu.edu.cn/student/for-std/student-portrait/getMyGrades?studentAssoc={self.student_assoc}&semesterAssoc='
        response = await self.client.get(URL, headers=self.headers, timeout=5)
        if response.json()['stdGpaRankDto'] is None:
            return "暂无排名，xdx先体验下大学生活喵", 0
        else:
            gpa = response.json()['stdGpaRankDto']['gpa']
            rank = response.json()['stdGpaRankDto']['rank']
            before_rank_gpa = response.json()['stdGpaRankDto']['beforeRankGpa']
            after_rank_gpa = response.json()['stdGpaRankDto']['afterRankGpa']
            rank_msg = f"你的绩点是{gpa}，在{major_name}中排名是{rank}/{total_poeple_num}({rank/total_poeple_num*100:.2f}%)"
            if before_rank_gpa:
                rank_msg += f"\n和前一名差{before_rank_gpa - gpa:.3f}绩点"
            if after_rank_gpa:
                rank_msg += f"\n与后一名差{gpa - after_rank_gpa:.3f}绩点"
            with open((os.path.join(folder_path, 'rank.txt')), 'w', encoding='utf-8') as f:
                f.write(str(rank))
            return rank_msg, rank

    # 查询考试信息
    async def get_exams(self, folder_path, is_finished_show=False):
        URL = 'https://jwxt.nwpu.edu.cn/student/for-std/exam-arrange'
        # 这个接口会获得一个20+mb的html文件，所以timeout设置为30
        response = await self.client.get(URL, headers=self.headers, timeout=30)
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

                    exams_msg +="名称："+course+"\n"
                    exams_msg +="地点："+location+"\n"
                    exams_msg +="时间："+time_exam+"\n\n"
        exams_msg = exams_msg[:-2]
        if not is_finished_show:
            with open(os.path.join(folder_path, 'exams.json'), 'w', encoding='utf-8') as f:
                json.dump(exams, f, indent=4, ensure_ascii=False)
        return exams_msg, exams
    
    # 获取课表信息
    async def get_course_table(self, folder_path):
        URL = 'https://jwxt.nwpu.edu.cn/student/for-std/course-table'
        response = await self.client.get(URL, headers=self.headers, timeout=5)
        all_semesters = BeautifulSoup(response.text, 'html.parser').find('select', {'id': 'allSemesters'}).find_all('option')
        course_table_path = ''
        course_table_name = ''
        # 遍历学期，找到有课的学期就保存
        for semester in all_semesters:
            URL = f"https://jwxt.nwpu.edu.cn/student/for-std/course-table/semester/{semester['value']}/print-data/{self.student_assoc}?hasExperiment=true"
            response = await self.client.get(URL, headers=self.headers, timeout=5)
            if response.json()["studentTableVm"]["credits"] != 0:
                course_table_path = os.path.join(folder_path, f'{semester.text}.html')
                course_table_name = f"{semester.text}.html"
                with open(course_table_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                break
        return course_table_path, course_table_name
    
    # 获取综测排名
    async def get_water_rank(self):
        URL = 'https://xgpt.nwpu.edu.cn/'
        response = await self.client.get(URL, headers=self.headers)
        URL = 'https://xgpt.nwpu.edu.cn/xsfw/sys/xggzptapp/modules/xszm/getFzxx.do'
        response = await self.client.post(URL, headers=self.headers, data={"data" : urllib.parse.quote(str({}))})
        URL = 'https://xgpt.nwpu.edu.cn/xsfw/sys/xggzptapp/modules/xszm/getFxYy.do'
        response = await self.client.post(URL, headers=self.headers4, data={"data" : urllib.parse.quote(str({"FZDM" : [data["FZDM"] for data in json.loads(response.text)["data"] if data["FZMC"] == "学生服务"][0]}))})
        URL = f'https://xgpt.nwpu.edu.cn/xsfw/sys/xggzptapp/modules/pubWork/appShow.do?id={[data["YYID"] for data in json.loads(response.text)["data"] if data["YYMC"] == "综合测评"][0]}'
        response = await self.client.get(URL, headers=self.headers)
        if "选择身份" in response.text:
            role_id = re.search(r',{"id":"(.*?)","text":"本科生组"', response.text).group(1)
            URL = 'https://xgpt.nwpu.edu.cn/xsfw/sys/funauthapp/selectRole.do'
            response = await self.client.post(URL, headers=self.headers4, data={"ROLEID": role_id, "APPNAME": "zhcptybbapp"})
            URL = 'https://xgpt.nwpu.edu.cn/xsfw/sys/zhcptybbapp/*default/index.do'
            response = await self.client.get(URL, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', text=re.compile(r'var pageMeta'))
        begin_year = int(re.search(r'"userId":"(\d+)"', script_tag.string).group(1)[:4])
        now_year = int(re.search(r'"curXN":(\d+)', script_tag.string).group(1)[:4])
        URL = 'https://xgpt.nwpu.edu.cn/xsfw/sys/zhcptybbapp/modules/evaluationApplyController/getEvaluationResultsByXn.do'
        water_rank_msg = ""
        for year in range(begin_year, now_year+1):
            response = await self.client.post(URL, headers=self.headers4, data={"data" : urllib.parse.quote(str({ "CPXN": str(year), "CPXQ":"3" }))})
            result = response.json()
            if result["data"]:
                water_rank_msg += f'{year}学年 总成绩{result["data"]["ZCJ"]}\n专业排名 {result["data"]["ZYNJPM"]}/{result["data"]["ZYNJRS"]} 班级排名 {result["data"]["BJPM"]}/{result["data"]["BJRS"]}\n\n'
        return water_rank_msg[:-2]

    # 获取培养方案完成情况
    async def get_training_program(self, folder_path):
        URL = f'https://jwxt.nwpu.edu.cn/student/for-std/program/root-module-json/{self.student_assoc}'
        response = await self.client.get(URL, headers=self.headers2, timeout=10)
        # training_program 的值
        training_program_data = []
        training_program_data_raw = json.loads(response.text)["children"]
        with open(os.path.join(folder_path,"training_program_data_raw.json"), "w", encoding='utf-8') as file:
            json.dump(training_program_data_raw, file, ensure_ascii=False, indent=4)
        handle_training_program_data(training_program_data_raw, training_program_data)
        with open(os.path.join(folder_path,"training_program_data.json"), "w", encoding='utf-8') as file:
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
        handle_completed_and_incomplete_course(training_program_data, completed_courses_all, completed_courses_all_static)
        with open(os.path.join(folder_path,"training_program_data_handle.json"), "w", encoding='utf-8') as file:
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