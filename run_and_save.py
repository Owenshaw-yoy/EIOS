# V3：整合现有程序：“分析一天”和“保存到数据库”串成一个入口
# 整体流程：
        # python run_and_save.py 2016-01-04
        # │
        # ├─ ① run_all.py
        # │      ├─ main.py          准备当天负荷数据
        # │      └─ inspect_data.py  检查数据、分析、告警和画图
        # │
        # └─ ② save_day_results.py  检查结果并保存到 MySQL
import subprocess
import sys
from datetime import datetime


# 要求运行时提供一个日期
if len(sys.argv) != 2:
    print("用法：python run_and_save.py YYYY-MM-DD")
    sys.exit(1)

date_text = sys.argv[1].strip()
# sys.argv[1]：取得命令后面的日期

# 检查日期，并统一成 YYYY-MM-DD 格式
try:
    target_date = datetime.strptime(date_text, "%Y-%m-%d").strftime("%Y-%m-%d")
except ValueError:
    print("日期无效，请使用 YYYY-MM-DD 格式，例如 2016-01-04")
    sys.exit(1)

# 先运行数据准备和分析
print(f"第一步：分析 {target_date} 的负荷数据", flush=True)

subprocess.run(
    [sys.executable, "run_all.py", target_date],
    check=True,
)
# sys.executable：使用当前运行这个入口程序的 Python 解释器

# 分析成功后，再运行数据库保存程序
print(f"第二步：将 {target_date} 的结果保存到 MySQL", flush=True)

subprocess.run(
    [sys.executable, "save_day_results.py", target_date],
    check=True,
)
# subprocess.run(...)：启动另一个程序并等待它结束

print(f"单日分析和数据库保存完成：{target_date}")