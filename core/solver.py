"""solver.py —— 规则排程（FIFO / SPT / MWKR 三种规则取 makespan 最小）

时间模型：每天工作 16h（08:00–24:00），周日不排。用 Calendar 把"工作时长"
映射成真实时刻，保证甘特图日期正确。
"""
from datetime import datetime, timedelta

from config import SCHEDULE_START, WORK_HOUR_PER_DAY, ALLOW_SUNDAY


class Calendar:
    """工作日历：把连续工作分钟映射到真实时刻（跳过非工作时段与周日）。"""

    def __init__(self, start=SCHEDULE_START, hours_per_day=WORK_HOUR_PER_DAY,
                 allow_sunday=ALLOW_SUNDAY):
        self.start = start
        self.sh, self.eh = 8, 8 + hours_per_day        # 工作起止小时
        self.hpd = hours_per_day                        # 每日工作小时数

    def _work_start(self, d):
        return d.replace(hour=self.sh, minute=0, second=0, microsecond=0)

    def _day_end(self, d):
        """当日工作结束时刻（hours_per_day 小时后，eh=24 即次日 00:00）。"""
        return self._work_start(d) + timedelta(hours=self.hpd)

    def _next_slot(self, dt):
        """把任意时刻对齐到最近的工作开始/继续点。"""
        d = dt
        while (not ALLOW_SUNDAY) and d.weekday() == 6:  # 跳过周日
            d = self._work_start(d) + timedelta(days=1)
        ws = self._work_start(d)
        if d <= ws:
            return ws                                   # 还没到今天开工 -> 开工点
        we = self._day_end(d)
        if d < we:
            return d                                    # 当天工作时段内 -> 继续
        return self._next_slot(we + timedelta(minutes=1))  # 超过今日 -> 下一天

    def elapsed(self, dt):
        """从排程起点到 dt 的"工作分钟数"（用于甘特色块定位）。"""
        total = 0
        cur = self.start
        while cur < dt:
            we = self._day_end(cur)
            if dt <= we:
                total += max(0, int((dt - cur).total_seconds() // 60))
                break
            total += int((we - cur).total_seconds() // 60)
            cur = self._next_slot(we + timedelta(minutes=1))
        return total

    def add(self, dt, minutes):
        cur = self._next_slot(dt)
        remain = int(round(minutes))
        while remain > 0:
            we = self._day_end(cur)
            avail = int((we - cur).total_seconds() // 60)
            if remain <= avail:
                cur = cur + timedelta(minutes=remain)
                remain = 0
            else:
                remain -= avail
                cur = self._next_slot(we + timedelta(minutes=1))
        return cur


def _dev_index(devices):
    """构建：设备可用时间字典 + 工序->可用设备列表。"""
    dev_free = {d["code"]: SCHEDULE_START for d in devices if d["available"]}
    by_proc = {}
    for d in devices:
        if not d["available"]:
            continue
        for p in d["processes"]:
            by_proc.setdefault(p, []).append(d["code"])
    return dev_free, by_proc


def _schedule_once(instances, devices, cal, order_sorted):
    """按给定作业顺序做列表排程，返回 (assignments, makespan, order_end)。"""
    dev_free, by_proc = _dev_index(devices)
    assignments, order_end = [], {}
    for j in order_sorted:
        prev_end = j["release"]
        for idx, op in enumerate(j["route"]["ops"]):
            pname = op["name"]
            cands = list(by_proc.get(pname, []))
            chosen = None
            if op["spec_type"] == "specific" and op["machine"] in dev_free:
                chosen = op["machine"]                   # 点名且满足 -> 优先
            if chosen is None:
                if op["spec_type"] == "group" and "-" not in op["machine"]:
                    pref = [c for c in cands if c.startswith(op["machine"])]
                    if pref:
                        cands = pref                     # 组内按前缀筛
                if cands:
                    chosen = min(cands, key=lambda c: dev_free[c])  # 最少负载
            if chosen is None:
                continue                                # 无可用机台 -> 跳过(校验会报缺失)
            dur = int(round(op["minutes"] * j["qty"] * j["factor"]))
            start = cal._next_slot(max(dev_free[chosen], prev_end))
            end = cal.add(start, dur)
            assignments.append({
                "job_id": j["job_id"], "order_id": j["order_id"], "product": j["product"],
                "op_idx": idx, "op_name": pname, "device": chosen,
                "qty": j["qty"], "factor": j["factor"],
                "start": start, "end": end, "minutes": dur,
            })
            dev_free[chosen] = end
            prev_end = end
        order_end[j["job_id"]] = prev_end
    makespan = max((a["end"] for a in assignments), default=SCHEDULE_START)
    return assignments, makespan, order_end


def schedule(instances, devices, cal=None):
    """三种规则各排一次，返回 makespan 最小的结果。"""
    cal = cal or Calendar()
    rules = {
        "FIFO": sorted(instances, key=lambda j: (not j["priority"], j["release"], j["order_id"])),
        "SPT":  sorted(instances, key=lambda j: (not j["priority"], _work(j))),
        "MWKR": sorted(instances, key=lambda j: (not j["priority"], -_work(j))),
    }
    best = None
    for name, ordered in rules.items():
        a, mk, oe = _schedule_once(instances, devices, cal, ordered)
        if best is None or mk < best["makespan"]:
            best = {"rule": name, "assignments": a, "makespan": mk, "order_end": oe}
    return best


def _work(j):
    return sum(op["minutes"] for op in j["route"]["ops"]) * j["qty"]
