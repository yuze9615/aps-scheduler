"""tests/test_basic.py —— 单元测试（≥3 个）

覆盖：单号归一、日期解析、校验器抓"机台时间重叠"。
运行：python -m pytest tests/  或  python tests/test_basic.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cleaner, checker


def test_normalize_order_id():
    """单号三种写法归一为 HD-2026-XXX。"""
    assert cleaner.normalize_order_id("HD-2026-101") == "HD-2026-101"
    assert cleaner.normalize_order_id("HD2026102") == "HD-2026-102"
    assert cleaner.normalize_order_id("104") == "HD-2026-104"


def test_parse_date():
    """多种日期格式 + 中文日期。"""
    assert cleaner.parse_date("2026/11/3") == cleaner.parse_date("2026-11-03")
    assert cleaner.parse_date("2026.11.4") is not None
    assert cleaner.parse_date("11月12日").month == 11
    assert cleaner.parse_date("") is None


def test_checker_catches_overlap():
    """校验器必须抓出同一机台的时间重叠。"""
    devices = [{"code": "CNC-01", "available": True, "processes": ["铣"],
                "unavail_reason": ""}]
    assignments = [
        {"order_id": "A", "op_idx": 0, "op_name": "铣", "device": "CNC-01",
         "start": _dt(9), "end": _dt(11)},
        {"order_id": "B", "op_idx": 0, "op_name": "铣", "device": "CNC-01",
         "start": _dt(10), "end": _dt(12)},   # 与 A 重叠
    ]
    v = checker.check_no_overlap(assignments)
    assert any("不重叠" in x for x in v), "校验器未抓出重叠！"


def _dt(h):
    from datetime import datetime
    return datetime(2026, 11, 9, h, 0)


if __name__ == "__main__":
    test_normalize_order_id()
    test_parse_date()
    test_checker_catches_overlap()
    print("✅ 全部单元测试通过（单号归一 / 日期解析 / 校验器抓撞机）")
