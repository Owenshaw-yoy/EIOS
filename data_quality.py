# 此文件用于提供数据检查函数

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
