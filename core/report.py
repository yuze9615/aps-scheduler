"""report.py —— 产出四件交付物

  1) 周排单表  out/排单表.xlsx   （机台/单号/工序/数量/开工/完工/工时）
  2) 甘特图    out/甘特图.html    （单文件，断网可打开）
  3) 风险清单  out/交期风险清单.md
  4) 体检报告  out/数据体检报告.md
"""
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment


def write_schedule_xlsx(path, assignments):
    """排单表 xlsx。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "排单表"
    head = ["机台", "单号", "工序", "数量", "开工", "完工", "工时(分钟)"]
    ws.append(head)
    for c in ws[1]:
        c.font = Font(bold=True)
    for a in sorted(assignments, key=lambda x: (x["device"], x["start"])):
        ws.append([
            a["device"], a["order_id"], f"{a['op_name']}(工序{a['op_idx'] + 1})",
            a["qty"], a["start"].strftime("%m-%d %H:%M"),
            a["end"].strftime("%m-%d %H:%M"), a["minutes"],
        ])
    # 列宽
    for col in ("A", "B", "C", "D", "E", "F", "G"):
        ws.column_dimensions[col].width = 16
    wb.save(path)


def write_gantt_html(path, assignments, devices, makespan, cal):
    """甘特图 HTML（单文件，离线可用）。行=机台，按工作时间定位色块。"""
    used = sorted({a["device"] for a in assignments})
    total_min = cal.elapsed(makespan) or 1
    scale = 0.5                                    # 每分钟 0.5px
    width = int(total_min * scale) + 20

    rows_html = ""
    for dev in used:
        bars = ""
        for a in [x for x in assignments if x["device"] == dev]:
            left = int(cal.elapsed(a["start"]) * scale)
            w = max(2, int(a["minutes"] * scale))
            tip = (f"{a['order_id']} {a['op_name']} 数量{a['qty']} "
                   f"{a['start']:%m-%d %H:%M}~{a['end']:%m-%d %H:%M}")
            bars += (f'<div class="bar" style="left:{left}px;width:{w}px" '
                     f'title="{tip}"></div>')
        rows_html += (f'<div class="row"><div class="label">{dev}</div>'
                      f'<div class="track" style="width:{width}px">{bars}</div></div>')

    html = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>宏达精密 周排程甘特图</title>
<style>
 body{{font-family:system-ui,"Microsoft YaHei",sans-serif;margin:20px}}
 h2{{margin:0 0 10px}} .row{{display:flex;align-items:center;margin:2px 0}}
 .label{{width:90px;font-size:13px}} .track{{position:relative;height:22px;
   background:#f3f4f6;border:1px solid #e5e7eb}}
 .bar{{position:absolute;top:2px;height:18px;background:#3b82f6;border-radius:3px}}
 .bar:hover{{background:#1d4ed8}}
 .legend{{color:#666;font-size:12px;margin-top:8px}}
</style></head><body>
<h2>宏达精密 · 周排程甘特图</h2>
<div>总工时跨度 {total_min} 分钟（{makespan:%Y-%m-%d %H:%M} 止）</div>
{rows_html}
<div class="legend">悬停色块查看 单号/工序/数量/起止时间；蓝条=一道工序任务。</div>
</body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def write_risk_md(path, instances, order_end, assignments):
    """交期风险清单 md。含「卡在哪台机/工序」列（瓶颈卡点）。"""
    lines = ["# 交期风险清单", ""]
    # 每个作业最后一道工序 = 卡点机台/工序
    last_by_job = {}
    for a in assignments:
        cur = last_by_job.get(a["job_id"])
        if cur is None or a["end"] > cur["end"]:
            last_by_job[a["job_id"]] = a
    late = 0
    for j in sorted(instances, key=lambda x: (x["deadline"] is None, x["deadline"] or 0)):
        end = order_end.get(j["job_id"])
        last = last_by_job.get(j["job_id"])
        bottleneck = f"{last['device']} / {last['op_name']}" if last else "—"
        if j["deadline"] is None or end is None:
            lines.append(f"- ⚠️ {j['order_id']}（{j['product']}，{j['qty']}件）："
                         f"交期缺失/未排，需人工确认（卡点：{bottleneck}）")
            continue
        delta = (end - j["deadline"]).total_seconds() / 86400
        if delta > 0:
            late += 1
            lines.append(f"- ❌ {j['order_id']}（{j['product']}，{j['qty']}件）："
                         f"交期 {j['deadline']:%m-%d %H:%M}，预计完工 "
                         f"{end:%m-%d %H:%M}，迟到 {delta:.1f} 天，卡在 {bottleneck}")
        else:
            lines.append(f"- ✅ {j['order_id']}（{j['product']}，{j['qty']}件）："
                         f"交期 {j['deadline']:%m-%d %H:%M}，预计完工 "
                         f"{end:%m-%d %H:%M}，按期（卡点：{bottleneck}）")
    lines.append("")
    lines.append(f"**迟到单数：{late} / {len(instances)}**")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_health_md(path, issues, stats):
    """数据体检报告 md。"""
    lines = ["# 数据体检报告", ""]
    lines.append(f"- 订单数：{stats['orders']}（可排 {stats['schedulable']} / 剔除 {stats['skipped']}）")
    lines.append(f"- 设备数：{stats['devices']}（可用 {stats['available']} / 不可用 {stats['unavailable']}）")
    lines.append(f"- 工艺路线：{stats['routes']} 个产品")
    lines.append(f"- 排程规则：{stats['rule']}（makespan {stats['makespan_min']} 分钟）")
    lines.append(f"- 工序任务数：{stats['tasks']}")
    lines.append("")
    lines.append("## 脏数据 / 异常逐条清单")
    lines.append("")
    if not issues:
        lines.append("（未发现脏数据）")
    for i, it in enumerate(issues, 1):
        lines.append(f"{i}. **[{it['类别']}]** {it['位置']} — 现象：`{it['现象']}`；"
                     f"处理：{it['处理']}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
