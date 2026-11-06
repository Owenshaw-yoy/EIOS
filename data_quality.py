# 此文件用于提供数据检查函数

import pandas as pd
# 定义函数：检查CSV是否包含我们需要的字段：
def check_required_columns(data, required_columns):
    missing_columns = set(required_columns) - set(data.columns)

    if missing_columns:
        raise ValueError(f"缺少必要字段：{missing_columns}")
# 上述函数定义原理是利用集合的概念计算缺集：
# .cilumns：pandas中得到列名，是csv_data的属性
# 如果存在missing_columns，就代表这一列都没有

# 定义缺失值检查函数
def check_missing_values(data, required_columns):
    # 从传入的表格中选出required_columns里列出的字段并检查
    missing_counts = data[required_columns].isna().sum()

    print("必要字段的缺失值数量：")
    print(missing_counts)

    if missing_counts.sum() > 0:
        raise ValueError("必要字段存在缺失值")

# 完善电量计算有关的检查
# 确认选中日确实有完整的 96 个时间步
def check_daily_time_steps(data):
    # 提取不重复的时间点，并按时间排序
    time_points = pd.DatetimeIndex( 
    #.DatetimeInde把时间点整理成 pandas 的日期时间索引，方便和后面生成的时间序列比较
        data["time"].drop_duplicates().sort_values()
    )
    # drop_duplicates()：同一时间有 98 个负荷，所以时间会重复出现。
    # 这里先取出不重复的时间点,sort_values()将时间点按先后顺序排序

    if time_points.empty:
        raise ValueError("时间列没有数据")

    # 从当天 00:00 开始，生成 96 个间隔 15 分钟的时间点
    expected_times = pd.date_range( # 从当前0点开始生成理想的时间步
        start=time_points[0].normalize(), # 取出第一个时间点00:00
        periods=96,
        freq="15min",
    )

    if not time_points.equals(expected_times): # 和实际的比较
        raise ValueError("时间步不完整或间隔异常，应为一天 96 个 15 分钟时间步")

    return len(time_points)

# 检查每个时间步是否有98个负荷
def check_loads_per_time(data, expected_load_count):
    # 按场景和时间分组，统计每组有多少个不同的负荷编号
    load_counts = data.groupby(
        ["scenario_id", "time"]
    )["load_id"].nunique()
    # .nunique()是pandas方法，用来统计每组中不同负荷编号的数量

    # 找出负荷数量不等于预期数量的时间步
    wrong_counts = load_counts[load_counts != expected_load_count]

    if not wrong_counts.empty:
        raise ValueError(
            f"以下时间步的负荷数量不等于 {expected_load_count}：\n"
            f"{wrong_counts.head(3)}"
        )

    return len(load_counts)