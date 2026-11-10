# 宏达精密本地排产助手 APS-scheduler

课程实战项目：简化版本地 APS 排产工具，纯本地运行，不联网。

## 这个项目解决什么
给常州宏达精密（机加工厂，12 台设备、两班倒）做一套**纯本地、不联网**的排产工具：
计划员把 Excel 台账（订单 / 设备 / 工艺路线三个 sheet）拖进来，点一下，
就出 ① 周排单表 ② 甘特图 ③ 交期风险清单 ④ 数据体检报告。
客户原话："在办公室电脑上能跑，点一下能出来。"

## 环境依赖
- Python >= 3.10
- 依赖库：openpyxl
- 安装命令：`pip install openpyxl`

## 怎么跑（N4 / N5 完成后补全具体命令）
- 命令行（后端，N4）：`python run.py data/宏达精密_订单台账.xlsx --out out`
- 网页版（N5）：`python web/app.py --port 8765`，浏览器打开 `http://localhost:8765`

## 目录说明
```
aps-scheduler/
├── README.md          本文件
├── .gitignore         排除 __pycache__ / out / 客户数据
├── config.py          长期参数（班次、日历、交期口径）        【N4】
├── run.py             命令行入口                          【N4】
├── core/              后端模块 reader/cleaner/instance/
│                      solver/checker/report               【N4】
├── web/               前端 index.html + 本地服务 app.py      【N5】
├── tests/             单元测试（单号归一/日期解析/校验器抓撞机）【N4】
├── docs/
│   ├── 设计说明书.md   【N2】
│   ├── ui/             三张 UI 原型图 + 交互说明             【N3】
│   └── 测试报告.md     【N6】
├── data/              放客户台账（已被 .gitignore 排除，不进仓库）
└── out/               排单表/甘特/报告等产物（已被 .gitignore 排除）
```

## 节点进度（N1–N6）
| 节点 | 内容 | 分值 | 状态 |
|------|------|------|------|
| N1 | 工作区与 Git 环境 | 10 | ✅ 已完成 |
| N2 | 产品设计开发说明书 | 15 | ✅ 已完成 |
| N3 | 前端 UI 图片 | 10 | ⬜ 待做 |
| N4 | 后端开发 | 25 | ⬜ 待做 |
| N5 | 前后端打通 | 20 | ⬜ 待做 |
| N6 | 真实 Excel 测试 | 20 | ⬜ 待做 |

> ⚠️ 客户台账是商业数据，请勿提交进 Git（见 .gitignore）。
