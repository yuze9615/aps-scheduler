"""pipeline.py —— 串联 读表→清洗→排程→校验→出报表

供命令行(run.py)与网页(web/app.py)共用。返回 JSON 友好的结果字典。
"""
import os
from datetime import datetime

from config import SCHEDULE_START
from core import reader, cleaner, instance, solver, checker, report


def _build_risk(instances, order_end):
    """构造交期风险列表（与 report.write_risk_md 同源逻辑）。"""
    items = []
    late = 0
    for j in sorted(instances, key=lambda x: (x["deadline"] is None, x["deadline"] or 0)):
        end = order_end.get(j["job_id"])
        if j["deadline"] is None or end is None:
            items.append({"order_id": j["order_id"], "product": j["product"], "qty": j["qty"],
                          "deadline": None, "end": None, "late": None, "note": "交期缺失/未排，需人工确认"})
            continue
        delta = (end - j["deadline"]).total_seconds() / 86400
        is_late = delta > 0
        if is_late:
            late += 1
        items.append({
            "order_id": j["order_id"], "product": j["product"], "qty": j["qty"],
            "deadline": j["deadline"].strftime("%Y-%m-%d %H:%M"),
            "end": end.strftime("%Y-%m-%d %H:%M"), "late": is_late,
            "delta_days": round(delta, 1), "note": "按期" if not is_late else "迟到",
        })
    return items, late


def run_pipeline(excel_path, out_dir):
    """跑完整流水线，写四件产物到 out_dir，返回结果字典。"""
    cal = solver.Calendar()
    raw = reader.read_workbook(excel_path)
    orders, devices, routes, issues = cleaner.clean(raw)
    instances, skipped = instance.build_instances(orders, routes, SCHEDULE_START)
    best = solver.schedule(instances, devices, cal)
    assignments, makespan, order_end = best["assignments"], best["makespan"], best["order_end"]
    violations = checker.run_all(instances, devices, assignments)

    os.makedirs(out_dir, exist_ok=True)
    files = {
        "xlsx": os.path.join(out_dir, "排单表.xlsx"),
        "html": os.path.join(out_dir, "甘特图.html"),
        "risk": os.path.join(out_dir, "交期风险清单.md"),
        "health": os.path.join(out_dir, "数据体检报告.md"),
    }
    report.write_schedule_xlsx(files["xlsx"], assignments)
    report.write_gantt_html(files["html"], assignments, devices, makespan, cal)
    report.write_risk_md(files["risk"], instances, order_end)
    report.write_health_md(files["health"], issues, {
        "orders": len(orders), "schedulable": len(instances), "skipped": len(skipped),
        "devices": len(devices),
        "available": sum(1 for d in devices if d["available"]),
        "unavailable": sum(1 for d in devices if not d["available"]),
        "routes": len(routes), "rule": best["rule"],
        "makespan_min": cal.elapsed(makespan), "tasks": len(assignments),
    })

    risk_items, late = _build_risk(instances, order_end)
    schedule_json = [{
        "job_id": a["job_id"], "order_id": a["order_id"], "device": a["device"],
        "op_name": a["op_name"], "qty": a["qty"], "minutes": a["minutes"],
        "start": a["start"].strftime("%Y-%m-%d %H:%M"),
        "end": a["end"].strftime("%Y-%m-%d %H:%M"),
    } for a in assignments]

    return {
        "violations": violations,
        "rule": best["rule"],
        "makespan_min": cal.elapsed(makespan),
        "makespan_end": makespan.strftime("%Y-%m-%d %H:%M"),
        "orders": len(orders), "schedulable": len(instances), "skipped": len(skipped),
        "devices": len(devices), "available": sum(1 for d in devices if d["available"]),
        "routes": len(routes), "tasks": len(assignments),
        "late": late,
        "schedule": schedule_json,
        "risk": risk_items,
        "health_issues": issues,
        "files": files,
    }
