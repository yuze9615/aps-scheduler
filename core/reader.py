"""reader.py —— 读取台账三表（只读取，不清洗）

约定：每个 sheet 第一行为大标题（如"宏达精密 · 待排产订单..."），
第二行为表头，其下为数据。读取时自动定位表头行并跳过标题行。
"""
from openpyxl import load_workbook


def _read_sheet(ws):
    """返回 (表头列表, 数据行列表)。数据行是 dict：表头->单元格值。"""
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], []

    # 定位表头行：含"单号"/"设备号"/"产品" 的那一行
    header_idx = 0
    for i, r in enumerate(rows):
        cells = " ".join(str(c) for c in r if c is not None)
        if any(k in cells for k in ("单号", "设备号", "产品")):
            header_idx = i
            break

    header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
    keys = ("单号", "设备号", "编号", "产品")
    data = []
    for r in rows[header_idx + 1:]:
        if all(c is None or str(c).strip() == "" for c in r):
            continue  # 跳过全空行
        row = {h: (r[j] if j < len(r) else None) for j, h in enumerate(header)}
        first = str(row.get(header[0]) or "").strip()
        # 跳过底部说明/备注行（如"注：…"、"备注里的口头规则：…"）
        if first.startswith(("注", "备", "说", "总", "合", "*", "说明")):
            continue
        # 工艺路线表底部混入的说明行（含中文标点或过长）跳过
        if header[0] == "产品" and (
                any(p in first for p in "：。，、（）()；") or len(first) > 4):
            continue
        # 关键列全空则跳过（保留 HT-01：编号非空）
        if not any(row.get(k) not in (None, "") for k in keys):
            continue
        data.append(row)
    return header, data


def read_workbook(path):
    """读取三个 sheet，返回 {sheet名: {"header":[], "rows":[{}]}}。"""
    wb = load_workbook(path, data_only=True, read_only=True)
    result = {}
    for name in wb.sheetnames:
        header, rows = _read_sheet(wb[name])
        result[name] = {"header": header, "rows": rows}
    wb.close()
    return result
