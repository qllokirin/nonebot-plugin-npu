from pydantic import BaseModel


class Config(BaseModel):
    # 每60分钟执行一次，执行时在60分钟内随机sleep，错开检测时间，减少服务器压力
    npu_check_time: int = 60
    npu_if_check_grades: bool = True
    npu_begin_check_hour: int = 8
    npu_end_check_hour: int = 22
    # 每80分钟执行一次，执行时在80分钟内随机sleep，错开检测时间，减少服务器压力
    npu_check_money_time: int = 80
    npu_if_check_money: bool = False
    # 每天12点执行一次，执行时在30分钟内随机sleep
    npu_electric_check_time: int = 30
    # 在链接上bot时就全部执行一遍，方便测试
    npu_if_check_when_connect: bool = False
    superusers: set[str]
