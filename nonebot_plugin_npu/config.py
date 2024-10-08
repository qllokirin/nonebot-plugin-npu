from pydantic import BaseModel

class Config(BaseModel):
    npu_check_time: int = 60
    npu_if_check_grades: bool = True
    npu_if_check_rank: bool = False
    npu_if_check_exams: bool = True
    npu_if_check_when_connect: bool = False
    npu_begin_check_hour: int = 8
    npu_end_check_hour: int = 22
    superusers: set[str]