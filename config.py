"""
全局配置文件 config.py
排程日历、班次参数，所有硬编码常量放这里，不要散落在代码各处。
"""
from datetime import datetime

# 排程时间原点：第一周起始 周一 早上 8 点
SCHEDULE_START: datetime = datetime(2026, 11, 9, 8, 0, 0)

# 每日工作：两班合计 16 小时 08:00 ~ 24:00，单位小时
WORK_HOUR_PER_DAY = 16
WORK_MINUTE_PER_DAY = WORK_HOUR_PER_DAY * 60

# 周日是否排产：False = 周日不生产
ALLOW_SUNDAY = False

# 兜底文字交期映射（业务确认过）
TEXT_DEADLINE_MAP = {
    "尽快": datetime(2026, 11, 10, 17, 0),
    "月底前": datetime(2026, 11, 30, 17, 0),
}
