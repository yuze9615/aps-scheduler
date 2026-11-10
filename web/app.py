"""app.py —— 本地网页服务（仅用 Python 标准库 http.server，不用 Flask）

API：
  POST /api/upload            上传台账 xlsx，返回 sheets/rows（非 xlsx/缺 sheet 给中文报错）
  POST /api/generate          生成排产，返回 JSON（指标/排单表/风险/体检）
  GET  /api/download/{type}   下载产物（排单表xlsx/甘特html/风险md/体检md），中文文件名不乱码
  GET  /                      返回前端 index.html

用法：python web/app.py --port 8765
"""
import os
import sys
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core import pipeline, reader, cleaner

UPLOAD_DIR = os.path.join(ROOT, "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
UPLOADS = {}            # file_id -> 保存路径（进程内内存映射）
_counter = 0


# ---------------- 工具 ----------------
def _json_resp(handler, obj, code=200):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _err(handler, msg, code=400):
    _json_resp(handler, {"error": msg}, code)


def _parse_multipart(body, boundary):
    """极简 multipart 解析，返回 {字段名: (文件名或None, 字节)}。"""
    parts = body.split(b"--" + boundary)
    fields = {}
    for part in parts:
        if part in (b"", b"--", b"--\r\n"):
            continue
        if part.startswith(b"\r\n"):
            part = part[2:]
        if b"\r\n\r\n" not in part:
            continue
        head, data = part.split(b"\r\n\r\n", 1)
        if data.endswith(b"\r\n"):
            data = data[:-2]
        # 解析 Content-Disposition
        name = None
        fname = None
        for line in head.decode("utf-8", "ignore").split("\r\n"):
            if "content-disposition" in line.lower():
                if "name=" in line:
                    name = line.split("name=")[1].split(";")[0].strip('"')
                if "filename=" in line:
                    fname = line.split("filename=")[1].split(";")[0].strip('"')
        fields[name] = (fname, data)
    return fields


def _save_upload(body, boundary, filename):
    global _counter
    fields = _parse_multipart(body, boundary)
    fdata = fields.get("file")
    if not fdata or not fdata[1]:
        return None, "未收到文件字段 file"
    fname = fdata[0] or filename or "upload.xlsx"
    if not fname.lower().endswith((".xlsx", ".xls")):
        return None, "只接受 .xlsx / .xls 台账文件"
    _counter += 1
    fid = f"tmp_{_counter}"
    path = os.path.join(UPLOAD_DIR, fid + "_" + os.path.basename(fname))
    with open(path, "wb") as f:
        f.write(fdata[1])
    UPLOADS[fid] = path
    return fid, None


# ---------------- 请求处理 ----------------
class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._serve_file(os.path.join(ROOT, "web", "index.html"), "text/html; charset=utf-8")
        elif parsed.path.startswith("/api/download/"):
            self._download(parsed)
        else:
            _err(self, "未知路径", 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        ctype = self.headers.get("Content-Type", "")
        if parsed.path == "/api/upload":
            self._upload(body, ctype)
        elif parsed.path == "/api/generate":
            self._generate(body)
        else:
            _err(self, "未知接口", 404)

    # ---- 上传 ----
    def _upload(self, body, ctype):
        if "multipart/form-data" not in ctype:
            return _err(self, "上传需用 multipart/form-data")
        boundary = ctype.split("boundary=")[-1].strip().encode("utf-8")
        fid, err = _save_upload(body, boundary, "upload.xlsx")
        if err:
            return _err(self, err)
        try:
            raw = reader.read_workbook(UPLOADS[fid])
            rows = {k: len(v["rows"]) for k, v in raw.items()}
            _json_resp(self, {"file_id": fid, "sheets": list(raw.keys()), "rows": rows})
        except Exception as e:
            _json_resp(self, {"file_id": fid, "sheets": [], "rows": {},
                             "warning": f"读取异常：{e}"}, 200)

    # ---- 生成 ----
    def _generate(self, body):
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return _err(self, "请求体不是合法 JSON")
        fid = payload.get("file_id")
        if not fid or fid not in UPLOADS:
            return _err(self, "缺少有效的 file_id（请先上传）")
        out_dir = os.path.join(ROOT, "out")
        try:
            res = pipeline.run_pipeline(UPLOADS[fid], out_dir)
        except Exception as e:
            return _err(self, f"生成失败：{e}")
        if res["violations"]:
            return _json_resp(self, {"ok": False, "violations": res["violations"]}, 200)
        _json_resp(self, {"ok": True, **res})

    # ---- 下载 ----
    def _download(self, parsed):
        ftype = parsed.path.split("/")[-1]
        names = {"schedule": "排单表.xlsx", "gantt": "甘特图.html",
                 "risk": "交期风险清单.md", "health": "数据体检报告.md"}
        if ftype not in names:
            return _err(self, "未知下载类型")
        path = os.path.join(ROOT, "out", names[ftype])
        if not os.path.exists(path):
            return _err(self, "产物尚未生成，请先点生成")
        mime = {"schedule": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "gantt": "text/html; charset=utf-8",
                "risk": "text/markdown; charset=utf-8",
                "health": "text/markdown; charset=utf-8"}[ftype]
        with open(path, "rb") as f:
            data = f.read()
        fname = names[ftype]
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        # 中文文件名不乱码：用 RFC5987 filename*
        self.send_header("Content-Disposition",
                        f"attachment; filename*=UTF-8''{urllib.parse.quote(fname)}")
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    # ---- 静态文件 ----
    def _serve_file(self, path, mime):
        if not os.path.exists(path):
            return _err(self, "文件不存在", 404)
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass  # 静默


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"🌐 排产助手已启动：http://localhost:{args.port}  （Ctrl+C 退出）")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
