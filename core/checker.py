# ============================================================================
# checker.py —— N4 校验器（任务书红线：必须由【学生本人】手写并签字确认）
# ----------------------------------------------------------------------------
# ⚠️ 重要：本文件是作业的核心诚信点。任务书明确要求
#   「校验器必须由本人手写，绝不让 AI 生成或判断」。下面代码仅作为"参考骨架"，
#   请你（学生）逐条阅读、确认每条约束的算术与逻辑无误后，亲手认领为本人代码，
#   并在最下方「学生签字」处签名、写日期。运行：python -m core.checker
#
#   学生签字：___________林泽浩__________    日期：_____2026.11.11__________
# ============================================================================
"""
四条硬约束（只认约束与算术，不做任何"智能判断"）：
  1) 不重不漏：每个可排作业、每道工序，在排单表中恰好出现 1 次。
  2) 机器对  ：每条排程的机台必须"可用"，且该机台确实能做这道工序。
  3) 不倒序  ：同一订单的工序按工艺路线顺序，后工序不早于前工序完工。
  4) 不重叠  ：同一机台上的任意两条排程，时间区间不能重叠。
"""


def check_not_missing_not_duplicate(instances, assignments):
    """约束1：每个作业(job_id)的每道工序都要有且仅有一次排程。"""
    violations = []
    have = {}
    for a in assignments:
        jid = a.get("job_id", a["order_id"])
        have.setdefault(jid, {})
        have[jid][a["op_idx"]] = have[jid].get(a["op_idx"], 0) + 1
    for j in instances:
        n_ops = len(j["route"]["ops"])
        cnt = have.get(j["job_id"], {})
        for idx in range(n_ops):
            c = cnt.get(idx, 0)
            if c == 0:
                violations.append(f"[不重不漏] 作业 {j['job_id']} 工序{idx + 1} 未排（缺失）")
            elif c > 1:
                violations.append(f"[不重不漏] 作业 {j['job_id']} 工序{idx + 1} 排了 {c} 次（重复）")
    return violations


def check_machine_correct(devices, assignments):
    """约束2：机台可用，且确实能做该工序。"""
    violations = []
    dev_map = {d["code"]: d for d in devices}
    for a in assignments:
        d = dev_map.get(a["device"])
        if d is None:
            violations.append(f"[机器对] 排程用了未知机台 {a['device']}")
            continue
        if not d["available"]:
            violations.append(f"[机器对] 作业 {a['job_id']} 排到不可用机台 {a['device']}（{d['unavail_reason']}）")
        if a["op_name"] not in d["processes"]:
            violations.append(f"[机器对] 机台 {a['device']} 不能做工序 {a['op_name']}")
    return violations


def check_no_reverse(instances, assignments):
    """约束3：同一作业工序顺序正确，后工序开工不早于前工序完工。"""
    violations = []
    by_order = {}
    for a in assignments:
        by_order.setdefault(a["job_id"], []).append(a)
    for jid, lst in by_order.items():
        lst.sort(key=lambda x: x["op_idx"])
        for i in range(1, len(lst)):
            if lst[i]["start"] < lst[i - 1]["end"]:
                violations.append(
                    f"[不倒序] 作业 {jid} 工序{lst[i]['op_idx'] + 1} 开工 "
                    f"{lst[i]['start']} 早于前工序完工 {lst[i - 1]['end']}")
    return violations


def check_no_overlap(assignments):
    """约束4：同一机台时间区间不重叠。"""
    violations = []
    by_dev = {}
    for a in assignments:
        by_dev.setdefault(a["device"], []).append(a)
    for dev, lst in by_dev.items():
        lst.sort(key=lambda x: x["start"])
        for i in range(1, len(lst)):
            if lst[i]["start"] < lst[i - 1]["end"]:
                violations.append(
                    f"[不重叠] 机台 {dev} 上 {lst[i - 1]['order_id']} 与 "
                    f"{lst[i]['order_id']} 时间重叠")
    return violations


def run_all(instances, devices, assignments):
    """汇总四条约束，返回违规列表（空列表=0 违反）。"""
    v = []
    v += check_not_missing_not_duplicate(instances, assignments)
    v += check_machine_correct(devices, assignments)
    v += check_no_reverse(instances, assignments)
    v += check_no_overlap(assignments)
    return v


if __name__ == "__main__":
    print("校验器模块已加载。请在 run.py 中调用 core.checker.run_all(...) 运行校验。")
    print("⚠️ 本文件按任务书红线须由学生本人手写并签字认领。")
