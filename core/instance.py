"""instance.py —— 把清洗后的订单展开成可排程的"作业实例"

每个订单 × 工艺路线 = 一个作业；作业含若干工序任务，
任务时长 = 数量 × 单件工时 × 先做一半系数(0.5)。
"""
from core.cleaner import parse_date


def build_instances(orders, routes, cal_start):
    """返回 (instances, skipped)。skipped 是被剔除的订单及原因。

    注意：同一单号可能出现多次（如"第二轮追加"），为不触发校验器的
    "不重不漏"，每个出现分配唯一 job_id；order_id 仍保留原始单号用于展示。
    """
    instances, skipped, seen = [], [], {}
    for o in orders:
        if o["qty"] is None:                          # 数量缺失 -> 剔除
            skipped.append((o["order_id"], "数量缺失"))
            continue
        route = routes.get(o["product"])
        if not route or not route["ops"]:              # 无工艺路线 -> 剔除
            skipped.append((o["order_id"], "无工艺路线"))
            continue

        seen[o["order_id"]] = seen.get(o["order_id"], 0) + 1
        n = seen[o["order_id"]]
        job_id = o["order_id"] if n == 1 else f"{o['order_id']}#{n}"

        release = o["order_date"]                      # 最早可开工
        if o["material_late"]:                        # 缺料：材料到货后才排
            md = parse_date(o["remark"])
            if md:
                release = max(release, md)
        release = max(release, cal_start)              # 不早于排程窗口起点

        factor = 0.5 if o["half"] else 1.0            # 先做一半 -> 减半
        instances.append({
            "job_id": job_id, "order_id": o["order_id"], "product": o["product"],
            "qty": o["qty"], "customer": o["customer"], "release": release,
            "priority": o["priority"], "factor": factor, "route": route,
            "remark": o["remark"], "deadline": o["deadline"],
            "deadline_type": o["deadline_type"],
        })
    return instances, skipped
