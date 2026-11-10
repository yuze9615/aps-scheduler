"""run.py —— 命令行入口：一条命令跑通整条排产流水线

用法：
    python run.py data/宏达精密_订单台账.xlsx --out out
产出（out/）：排单表.xlsx / 甘特图.html / 交期风险清单.md / 数据体检报告.md
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from core import pipeline


def main():
    parser = argparse.ArgumentParser(description="宏达精密本地排产助手")
    parser.add_argument("excel_file", help="客户台账 xlsx 路径")
    parser.add_argument("--out", default="./out", help="输出目录")
    args = parser.parse_args()

    if not os.path.exists(args.excel_file):
        print(f"❌ 文件不存在：{args.excel_file}")
        sys.exit(1)

    print(f"📖 读取：{args.excel_file}")
    res = pipeline.run_pipeline(args.excel_file, args.out)

    print(f"   订单 {res['orders']} / 设备 {res['devices']}（可用 {res['available']}）"
          f" / 工艺路线 {res['routes']}")
    print(f"   可排作业 {res['schedulable']} / 剔除 {res['skipped']} / "
          f"工序任务 {res['tasks']}")
    print(f"   排程规则 {res['rule']} / makespan {res['makespan_min']} 分钟")

    if res["violations"]:
        print(f"❌ 校验发现 {len(res['violations'])} 条违反：")
        for v in res["violations"]:
            print("   ", v)
        sys.exit(2)
    print("✅ 校验通过：0 违反（不重不漏 / 机器对 / 不倒序 / 不重叠）")

    print("📦 已产出：")
    for p in res["files"].values():
        print("   ", p)


if __name__ == "__main__":
    main()
