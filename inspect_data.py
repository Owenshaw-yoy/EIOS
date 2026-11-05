# 此py文件意在读取从main中生成好的表格，方便后续分析数据时，把准备数据和分析数据分开
# 导入其他文件定义好的函数
from data_quality import check_required_columns, check_missing_values
# 导入pandas
import pandas as pd
# 导入matplotlib绘图工具
# matplotlib 是绘图库，pyplot是它提供的一组绘图功能
import matplotlib.pyplot as plt

# # 定义函数：检查CSV是否包含我们需要的字段：
# def check_required_columns(data, required_columns):
#     missing_columns = set(required_columns) - set(data.columns)

#     if missing_columns:
#         raise ValueError(f"缺少必要字段：{missing_columns}")
# # 上述函数定义原理是利用集合的概念计算缺集：
# # .cilumns：pandas中得到列名，是csv_data的属性
# # 如果存在missing_columns，就代表这一列都没有
# 这一部分函数已经转移到专用的data_quality的py文件里分开放置，我们在这里只需要导入即可

# # 定义缺失值检查函数
# def check_missing_values(data, required_columns):
#     # 从传入的表格中选出required_columns里列出的字段并检查
#     missing_counts = data[required_columns].isna().sum()

#     print("必要字段的缺失值数量：")
#     print(missing_counts)

#     if missing_counts.sum() > 0:
#         raise ValueError("必要字段存在缺失值")
# 这一部分函数已经转移到专用的data_quality的py文件里分开放置

# 读取load_all_first96.csv表格
# 把结果整理为DataFrame的表格，交给变量csv_data
csv_data = pd.read_csv("load_all_first96.csv")

print("数据规模：", csv_data.shape)
print("各列的数据类型：")
print(csv_data.dtypes) # .dtypes方法：用于查看DataFrame中的 每一列的数据类型
print("前 3 条记录：")
print(csv_data.iloc[:3])

# 下一步
# 增加功能：检查文件里是否有我们需要的字段和数据
# 字段：表格中用来描述某类信息的一列
# 我们需要检查三件事：1.必要的列是否存在 2.表格是否有数据 3.必要列中是否存在缺失值

# 检查字段，自己设置需要检查什么字段
required_columns = ["scenario_id", "time", "load_id", "p_mw"]
check_required_columns(csv_data, required_columns)
# 把我们想检查的字段和已有的设置为集合set，然后相减可以如果不是空集合则有缺失



# 检查文件是否有数据
if csv_data.empty:
    raise ValueError("CSV 文件没有数据")

# 统计缺失值
# missing_counts = csv_data[required_columns].isna().sum()
# # 取出我们关心的四列，.isna()得到一张True/False表，sum可以把True/False相加
# # 只要总数大于0就暂停

# print("必要字段的缺失值数量：")
# print(missing_counts)

# if missing_counts.sum() > 0:
#     raise ValueError("必要字段中存在缺失值，请检查数据")
check_missing_values(csv_data, required_columns)

print("字段和缺失值检查通过")

# 下一步
# 检查：1.时间能不能被识别成日期时间 2.同一个负荷在同一时间有没有被重复记录

# 同样，转换时间，将时间从文本的形式转换为pandas时间的形式
csv_data["time"] = pd.to_datetime(
    csv_data["time"], format="%d.%m.%Y %H:%M"
)

# 只查看时间这一列的类型：.dtype是查看整张表各列的类型，而前面加约束time则查看时间类型
print("时间列转换后的类型：", csv_data["time"].dtype)

# 检查是否重复记录：
# 先确定我们需要确定负荷信息的三个字段key_columns:
key_columns = ["scenario_id", "time", "load_id"]
# 如果存在连续两行有一样的数据，那么就有可能是重复录入
# .duplicated()是pandas的查重方法，subset表示那些列中的数据重复了
duplicate_rows = csv_data.duplicated(subset=key_columns)
# 返回的是True/Fales

# True代表1，False代表0，把他们加起来就可以得到重复记录数
print("重复记录数量：", duplicate_rows.sum())

# 如果至少有一个为True，就报错，但是不会自己删数据
if duplicate_rows.any():
    raise ValueError("同一场景、时间和负荷存在重复记录")

print("时间和重复记录检查通过")

# 下一步
# 直接使用读回的 CSV 计算总负荷和峰值

csv_data["p_mw"] = pd.to_numeric(csv_data["p_mw"], errors="raise")
# 它把 p_mw 这一列转换成数值类型。目前读到的是 float64，已经可以计算；
# 增加这一步是为了以后读取其他 CSV 时，如果某个功率写成了无法转换的文本，
# 程序会直接提示错误，不会继续求和。

# 按照情景和时间进行分组，再在组内求功率和
csv_total = csv_data.groupby(
    ["scenario_id", "time"], as_index=False
)["p_mw"].sum()

peak_index = csv_total["p_mw"].idxmax()

print("总负荷表规模：", csv_total.shape)
print("第一个时间步的总负荷（MW）：", csv_total["p_mw"].iloc[0])
print("最高总负荷（MW）：", csv_total.loc[peak_index, "p_mw"])
print("最高总负荷出现的时间：", csv_total.loc[peak_index, "time"])

# 下一步
# 绘图展示1月1日号98个负荷总负荷功率

peak_time = csv_total.loc[peak_index, "time"]
peak_power = csv_total.loc[peak_index, "p_mw"]

# 下一步
# 我们已经知道了最高总负荷，再增加三个常用指标
# 计算最低总负荷及其出现时间
lowest_index = csv_total["p_mw"].idxmin()  # .idxmin()：找到最小值所在的行索引
lowest_power = csv_total.loc[lowest_index, "p_mw"] # 使用.loc取出这一行的时间和功率
lowest_time = csv_total.loc[lowest_index, "time"]

# 计算平均总负荷和峰谷差
average_power = csv_total["p_mw"].mean()
peak_valley_difference = peak_power - lowest_power

print(f"最低总负荷（MW）：{lowest_power:.2f}")
print("最低总负荷出现的时间：", lowest_time)
print(f"平均总负荷（MW）：{average_power:.2f}")
print(f"负荷峰谷差（MW）：{peak_valley_difference:.2f}")

# 创建画布和坐标区域：fig：整张图，可以理解为画布；ax：坐标区域
fig, ax = plt.subplots(figsize=(10, 5))

# ax.plot画折线：第一个参数是横轴时间，第二个参数是纵轴总负荷。
# 后面的参数分别设置颜色、线宽和图例名称。
ax.plot(
    csv_total["time"],
    csv_total["p_mw"],
    color="#2468a2",
    linewidth=2,
    label="Total load",
)

# scatter()在图上画点。这里使用刚才算出的 peak_time 和 peak_power，用红点标记峰值
ax.scatter(
    peak_time,
    peak_power,
    color="#e25942",
    s=55,
    label=f"Peak: {peak_power:.2f} MW", # 显示两位小数
    zorder=3,
)

# 设置图表和文字样式
ax.set_title("SimBench Daily Total Load")
ax.set_xlabel("Time")
ax.set_ylabel("Active Power (MW)")
ax.grid(True, linestyle="--", alpha=0.25)
ax.legend()

# 保存和整理图片
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig("daily_load_curve.png", dpi=150) # 保存为分辨率为150

print("图像已保存：daily_load_curve.png")

