# 此文件意在检查我们定义的检查字段函数是否真实起作用
import pandas as pd

from data_quality import check_required_columns, check_missing_values

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