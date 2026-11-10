"""cleaner.py —— 脏数据清洗 + 数据体检

输入 reader 读出的原始结构，输出：
  orders   清洗后的订单列表
  devices  清洗后的设备列表（含可用性判定）
  routes   清洗后的工艺路线（工序已拆成 工序名/机台/类型/分钟）
  issues   体检报告条目：{类别, 位置, 现象, 处理}
"""
import re
from datetime import datetime

from config import TEXT_DEADLINE_MAP, SCHEDULE_START


# ---------- 基础解析工具 ----------
def parse_date(s):
    """解析多种日期写法：2026/11/3、2026-11-03、2026.11.4、2026年11月3日、11月12日。"""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    m = re.search(r"(\d{4})?年?(\d{1,2})月(\d{1,2})日?", s)
    if m:
        y = int(m.group(1)) if m.group(1) else SCHEDULE_START.year
        return datetime(y, int(m.group(2)), int(m.group(3)))
    for sep in ("/", "-", "."):
        if sep in s:
            try:
                y, mo, d = s.split(sep)
                return datetime(int(y), int(mo), int(d))
            except ValueError:
                continue
    return None


def normalize_order_id(s):
    """单号归一：HD-2026-101 / HD2026102 / 104 -> HD-2026-101 / HD-2026-102 / HD-2026-104。"""
    s = str(s).strip()
    m = re.search(r"(\d{4})\D*(\d{3})$", s)        # 2026 + 三位
    if m:
        return f"HD-2026-{int(m.group(2)):03d}"
    m = re.search(r"(\d{3})$", s)                  # 纯三位
    if m:
        return f"HD-2026-{int(m.group(1)):03d}"
    return s


def parse_deadline(s):
    """交期解析：日期 / 中文 / 尽快 / 月底前 / 空白。返回 (datetime或None, 类型)。"""
    if s is None or str(s).strip() == "":
        return None, "空白"
    s = str(s).strip()
    if s in TEXT_DEADLINE_MAP:                      # 尽快 / 月底前 等兜底
        return TEXT_DEADLINE_MAP[s], s
    dt = parse_date(s)
    if dt:
        return dt, "日期"
    return None, "无法解析"


def parse_op(cell):
    """解析单个工序格：'下料（SAW-01）20' -> {name, machine, spec_type, minutes}。"""
    s = str(cell).strip()
    m = re.match(r"^(.+?)[（(](.+?)[）)]\s*(\d+)\s*$", s)
    if not m:
        return None
    name, machine, minutes = m.group(1).strip(), m.group(2).strip(), int(m.group(3))
    # 点名=带横线编号(CNC-01)；组=纯前缀(LAT / CNC)
    spec_type = "specific" if "-" in machine else "group"
    return {"name": name, "machine": machine, "spec_type": spec_type, "minutes": minutes}


# ---------- 主清洗 ----------
def clean(raw):
    issues, orders, seen = [], [], {}

    # 1) 订单表
    for r in raw["订单"]["rows"]:
        oid_raw = r.get("单号")
        oid = normalize_order_id(oid_raw)

        if oid in seen:                              # 单号重复
            issues.append({"类别": "单号重复", "位置": f"订单 {oid_raw}",
                           "现象": f"单号 {oid} 出现多次（第二轮追加）",
                           "处理": "保留为独立作业行并标记 duplicate"})
        seen[oid] = seen.get(oid, 0) + 1

        od = parse_date(r.get("接单日期"))           # 接单日期
        if od is None:
            issues.append({"类别": "日期缺失/异常", "位置": f"订单 {oid}",
                           "现象": f"接单日期='{r.get('接单日期')}'",
                           "处理": "默认用排程起点，标记需问客户"})
            od = SCHEDULE_START.replace(hour=8, minute=0)

        dl, dl_type = parse_deadline(r.get("交期"))   # 交期
        if dl is None:
            issues.append({"类别": "交期缺失/异常", "位置": f"订单 {oid}",
                           "现象": f"交期='{r.get('交期')}'",
                           "处理": "标记待问客户，本次不计入迟到评估"})

        try:                                          # 数量
            qty = int(float(r.get("数量"))) if r.get("数量") not in (None, "") else None
        except (ValueError, TypeError):
            qty = None
        if qty is None:
            issues.append({"类别": "数量缺失", "位置": f"订单 {oid}",
                           "现象": f"数量='{r.get('数量')}'",
                           "处理": "标记待问客户，本次剔除该单"})

        remark = str(r.get("备注") or "").strip()      # 备注口头规则
        priority = ("急" in remark) or ("催" in remark)
        material_late = ("材料" in remark) and (("到" in remark) or ("未到" in remark))
        half = ("先做一半" in remark) or ("一半" in remark)

        orders.append({
            "order_id": oid, "customer": r.get("客户"), "product": r.get("产品"),
            "qty": qty, "order_date": od, "deadline": dl, "deadline_type": dl_type,
            "remark": remark, "priority": priority, "material_late": material_late,
            "half": half, "duplicate": seen[oid] > 1,
        })

    # 2) 设备表
    devices = []
    for r in raw["设备"]["rows"]:
        code = r.get("编号")
        dev_id = r.get("设备号") or ""
        processes = [p.strip() for p in str(r.get("可做工序") or "").split("、") if p.strip()]
        try:
            shifts = int(r.get("每日班次"))
        except (ValueError, TypeError):
            shifts = 2
        status = str(r.get("状态") or "").strip()

        available, reason = True, ""
        if "外协" in status:
            available, reason = False, "外协不计本厂"
        elif "停机" in status:
            available, reason = False, status
        elif "闲置" in status:
            available, reason = False, "闲置(需确认)"
        elif not dev_id:
            available, reason = False, "设备号空白"

        if not available:
            issues.append({"类别": "设备不可用", "位置": f"设备 {code}",
                           "现象": status or "设备号空白",
                           "处理": f"从可用产能剔除：{reason}"})
        devices.append({"dev_id": dev_id, "code": code, "model": r.get("型号"),
                        "processes": processes, "shifts": shifts, "status": status,
                        "available": available, "unavail_reason": reason})

    # 3) 工艺路线表
    routes = {}
    for r in raw["工艺路线"]["rows"]:
        product = r.get("产品")
        ops = []
        for k in ("工序1", "工序2", "工序3", "工序4", "工序5"):
            if r.get(k) is None or str(r.get(k)).strip() == "":
                continue
            op = parse_op(r.get(k))
            if op:
                ops.append(op)
        routes[product] = {"ops": ops, "std_total": r.get("单件工时合计"),
                           "remark": str(r.get("备注") or "").strip()}

    return orders, devices, routes, issues
