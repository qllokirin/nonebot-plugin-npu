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

import re
import time
import json
import os
import smtplib
from email.mime.text import MIMEText
import requests
import rsa
import base64
from bs4 import BeautifulSoup

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
        self.session = requests.session()

    def use_recent_cookies_login(self, cookies_path):
        URL = ("https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn"
               "%2F%3Fpath%3Dhttps%3A%2F%2Fecampus.nwpu.edu.cn")
        if os.path.isfile(cookies_path):
            with open(cookies_path, 'r', encoding='utf-8') as f:
                new_cookies = json.loads(f.read())
            self.session.cookies.update(new_cookies)
            response = self.session.get(URL, headers=self.headers)
            response.encoding = 'utf-8'
        else:
            return False
        if len(response.history) != 0:
            return True
        else:
            return False

    def login(self, username, password, device, folder_path):
        URL = ("https://uis.nwpu.edu.cn/cas/login?service=https%3A%2F%2Fecampus.nwpu.edu.cn"
               "%2F%3Fpath%3Dhttps%3A%2F%2Fecampus.nwpu.edu.cn")
        self.device = device
        self.username = username

        # RSA加密password
        URL_key = 'https://uis.nwpu.edu.cn/cas/jwt/publicKey'
        public_key = self.session.get(URL_key, headers=self.headers2).text
        public_key = rsa.PublicKey.load_pkcs1_openssl_pem(public_key.encode())
        password = rsa.encrypt(password.encode(), public_key)
        password = "__RSA__" + base64.b64encode(password).decode()
        self.password = password

        response = self.session.get(URL, headers=self.headers)
        response.encoding = 'utf-8'
        str1 = re.search('var hmSiteId = "(.*?)"', response.text)
        new_cookies = {
            ("Hm_lvt_" + str1.group(1)): str(int(time.time())),
            ("Hm_lpvt_" + str1.group(1)): str(int(time.time()))
        }
        self.session.cookies.update(new_cookies)

        if len(response.history) == 0:
            #  没有重定向到主页，开始输入账号
            self.execution = re.search('name="execution" value="(.*?)"', response.text)
            self.fpVisitorId = re.search('name="fpVisitorId" value="(.*?)"', response.text)

            if device == "securephone" or device == "secureemail":
                URL = 'https://uis.nwpu.edu.cn/cas/mfa/detect'
                data = {
                    'username': self.username,
                    'password': self.password,
                }
                response = self.session.post(URL, data=data, headers=self.headers2)
                self.state_code = json.loads(response.text)['data']['state']

                URL = f'https://uis.nwpu.edu.cn/cas/mfa/initByType/{device}?state={self.state_code}'
                response = self.session.get(URL, headers=self.headers2)
                if json.loads(response.text)['code'] != 0:
                    return json.loads(response.text)['code']
                else:
                    gid = json.loads(response.text)['data']['gid']
                    URL = f'https://uis.nwpu.edu.cn/attest/api/guard/{device}/send'
                    self.data = {'gid': gid}
                    self.session.post(URL, data=json.dumps(self.data), headers=self.headers3)
                    return 0
            elif device == "qr":
                URL = 'https://uis.nwpu.edu.cn/cas/qr/init'
                response = self.session.get(URL, headers=self.headers2)
                self.state_key = json.loads(response.text)['data']['stateKey']
                URL = f'https://uis.nwpu.edu.cn/cas/qr/qrcode?r={int(time.time_ns()/1000000)}'
                response = self.session.get(URL, headers=self.headers)
                with open(os.path.join(folder_path, 'qr.png'), 'wb') as f:
                    f.write(response.content)
                return "wating_to_scan_qr"

    def wating_to_scan_qr(self,folder_path):
        URL = 'https://uis.nwpu.edu.cn/cas/qr/comet'
        while True:
            time.sleep(1)
            response = self.session.post(URL, headers=self.headers2)
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
                self.session.post(URL, data=self.data, headers=self.headers)
                cookies = json.dumps(self.session.cookies.get_dict())
                with open((os.path.join(folder_path, 'cookies.txt')), 'w', encoding='utf-8') as f:
                    f.write(cookies)
                return True

    def verification_code_login(self, captcha, folder_path):
        URL = f'https://uis.nwpu.edu.cn/attest/api/guard/{self.device}/valid'
        self.data['code'] = captcha
        response = self.session.post(URL, data=json.dumps(self.data), headers=self.headers3)
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
            self.session.post(URL, data=self.data, headers=self.headers)
            cookies = json.dumps(self.session.cookies.get_dict())
            with open((os.path.join(folder_path, 'cookies.txt')), 'w', encoding='utf-8') as f:
                f.write(cookies)
            return 2

    # 查询成绩
    def get_grades(self, folder_path, sem_query=0):
        # 0 是查询全部成绩 是几就是查询后几个学期的
        URL = 'https://jwxt.nwpu.edu.cn/student/sso-login'
        self.session.get(URL, headers=self.headers)
        URL = 'https://jwxt.nwpu.edu.cn/student/for-std/grade/sheet'
        response = self.session.get(URL, headers=self.headers)
        self.student_assoc = re.search('semester-index/(.*)', response.url).group(1)
        response = self.session.get(
            'https://jwxt.nwpu.edu.cn/student/for-std/grade/sheet/semester-index/' + self.student_assoc,
            headers=self.headers)
        semester = re.findall('<option value="(.+?)"', response.text)
        grades = []
        grades_msg = []
        sem_query_ = sem_query
        if sem_query == 0: sem_query = len(semester)
        for sem in semester:
            URL = 'https://jwxt.nwpu.edu.cn/student/for-std/grade/sheet/info/' + self.student_assoc + '?semester=' + sem
            response = self.session.get(URL, headers=self.headers2)
            response = json.loads(response.text)['semesterId2studentGrades'][sem]
            for course in response:
                name = course['course']['nameZh']
                grade_score = course['gaGrade']
                gpa = str(course['gp'])
                credit = course['course']['credits']
                grade_detail = re.findall('>(.+?)</span>', course['gradeDetail'])
                grades_msg.append(f'{name}, {grade_score}, {gpa}, {credit}, {grade_detail}')
                grades_one_subject = {
                    "name": name,
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

    def get_rank(self, folder_path):
        while True:
            URL = 'https://jwxt.nwpu.edu.cn/student/sso-login'
            self.session.get(URL, headers=self.headers)
            URL = 'https://jwxt.nwpu.edu.cn/student/for-std/grade/sheet'
            response = self.session.get(URL, headers=self.headers)
            match = re.search('semester-index/(.*)', response.url)
            if match:
                self.student_assoc = match.group(1)
                break
            # 偶尔会出现 目前怀疑为页面没有加载完全 故多次运行
        URL = 'https://jwxt.nwpu.edu.cn/student/for-std/student-portrait'
        self.session.get(URL, headers=self.headers)
        URL = f'https://jwxt.nwpu.edu.cn/student/for-std/student-portrait/getMyGrades?studentAssoc={self.student_assoc}&semesterAssoc='
        response = self.session.get(URL, headers=self.headers)
        gpa = response.json()['stdGpaRankDto']['gpa']
        rank = response.json()['stdGpaRankDto']['rank']
        before_rank_gpa = response.json()['stdGpaRankDto']['beforeRankGpa']
        after_rank_gpa = response.json()['stdGpaRankDto']['afterRankGpa']
        rank_msg = f"你的绩点是{gpa},排名是{rank}"
        if before_rank_gpa:
            rank_msg += f"\n和前一名差{before_rank_gpa - gpa:.3f}绩点"
        if after_rank_gpa:
            rank_msg += f"\n与后一名差{gpa - after_rank_gpa:.3f}绩点"
        rank_msg += f"\n\n学校的排名逻辑是同绩点的可能会被并列为同一名也可能会按顺序排，所以没出成绩时排名也在上下浮动是正常的（因为可能有跟你同绩点也有可能是前面有人同绩点导致你往前一名）"
        with open((os.path.join(folder_path, 'rank.txt')), 'w', encoding='utf-8') as f:
            f.write(str(rank))
        return rank_msg, rank

    # 查询考试信息
    def get_exams(self, folder_path, is_finished_show=False):
        URL = 'https://jwxt.nwpu.edu.cn/student/sso-login'
        self.session.get(URL, headers=self.headers)
        URL = 'https://jwxt.nwpu.edu.cn/student/for-std/exam-arrange'
        response = self.session.get(URL, headers=self.headers)
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
                    time = row.find_all('div', class_='time')[0].text
                    # 地点
                    location = ', '.join([span.text for span in row.find('td').find_all('span')])
                    # 课程
                    course = row.find_all('td')[1].find('span').text
                    # 状态
                    status = row.find_all('td')[2].text.strip()

                    exam = {
                        "if_finished": finished,
                        "time": time,
                        "location": location,
                        "course": course,
                        "status": status
                    }
                    exams.append(exam)

                    exams_msg +="名称："+course+"\n"
                    exams_msg +="地点："+location+"\n"
                    exams_msg +="时间："+time+"\n\n"
        exams_msg = exams_msg[:-2]
        with open(os.path.join(folder_path, 'exams.json'), 'w', encoding='utf-8') as f:
            json.dump(exams, f, indent=4, ensure_ascii=False, )
        return exams_msg, exams