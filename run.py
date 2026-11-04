"""
命令行入口 run.py
python run.py 台账路径 --out 输出文件夹
"""
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("excel_file",help="客户台账xlsx路径")
    parser.add_argument("--out",default="./out",help="输出目录")
    args = parser.parse_args()
    print(f"读取文件:{args.excel_file}")
    print(f"输出目录:{args.out}")
    print("【待实现N4后端逻辑】")

if __name__ == "__main__":
    main()
