# 此文件意在检查我们定义的检查字段函数是否真实起作用
import pandas as pd

from data_quality import (
    check_required_columns, 
    check_missing_values, 
    check_daily_time_steps,
    check_loads_per_time
)

# 创建一张只有 time 和 load_id 两列的小表
sample_data = pd.DataFrame({
    "time": ["2016-01-01 00:00"],
    "load_id": [0],
})

# 要求表中还必须有 p_mw
required_columns = ["time", "load_id", "p_mw"]

try:
    check_required_columns(sample_data, required_columns)
except ValueError as error:
    print("预期发现缺少字段：", error)
else:
    print("检查没有发现缺失字段，请检查函数")
    # 创建一张包含 p_mw 列、但功率值为空的小表
missing_value_data = pd.DataFrame({
    "time": ["2016-01-01 00:00"],
    "load_id": [0],
    "p_mw": [None],
})

# 先检查字段：这次三个字段都存在，应该通过
check_required_columns(missing_value_data, required_columns)

# 再检查字段里的值
try:
    check_missing_values(missing_value_data, required_columns)
except ValueError as error:
    print("预期发现缺失值：", error)
else:
    print("检查没有发现缺失值，请检查函数")

# 构造一天的 96 个时间点，再人为去掉一个
full_day = pd.date_range("2016-12-01", periods=96, freq="15min")
missing_time_data = pd.DataFrame({"time": full_day.delete(10)})

try:
    check_daily_time_steps(missing_time_data)
except ValueError as error:
    print("预期发现时间步问题：", error)
else:
    print("检查失败：没有发现缺失的时间步")

# 假设这个示例场景应该有两个负荷：0 和 1
missing_load_data = pd.DataFrame({
    "scenario_id": ["demo", "demo", "demo"],
    "time": pd.to_datetime([
        "2016-12-01 00:00",
        "2016-12-01 00:00",
        "2016-12-01 00:15",
    ]),
    "load_id": [0, 1, 0],
    "p_mw": [1.0, 2.0, 1.0],
})

try:
    check_loads_per_time(missing_load_data, expected_load_count=2)
except ValueError as error:
    print("预期发现负荷记录缺失：", error)
else:
    print("检查失败：没有发现缺失的负荷记录")