# 此程序运用一键启动运行的入口程序
# main.py —-> 数据生成和整理
# inspect_data.py  --> 读取数据并分析
import subprocess
import sys

# subprocess.run运行第一个程序，并等待它结束
print("第一步：准备负荷数据", flush=True)
# subprocess.run([sys.executable, "main.py"], check=True) 原写法
date_arguments = sys.argv[1:]
subprocess.run([sys.executable, "main.py"] + date_arguments, check=True)


# 运行第二个程序并等待它结束
print("第二步：检查数据并生成分析结果", flush=True)
subprocess.run([sys.executable, "inspect_data.py"], check=True)

print("项目流程运行完成")