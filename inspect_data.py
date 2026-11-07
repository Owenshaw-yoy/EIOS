# 此py文件意在读取和分析从main中生成好的表格，将准备数据和分析数据分开
# 导入其他文件定义好的函数
from data_quality import (
    check_required_columns,
    check_missing_values,
    check_daily_time_steps,
    check_loads_per_time
)
# 导入pandas
import pandas as pd
# 导入matplotlib绘图工具
# matplotlib 是绘图库，pyplot是它提供的一组绘图功能
import matplotlib.pyplot as plt

# 导入 Python 自带的日志模块：方便记录告警信息
import logging

# 设置日志文件和日志内容的格式
logging.basicConfig(
    filename="eios.log",
    filemode="a",       # 日志采用追加方式，程序继续运行时，新日志会追加在旧日志后
    level=logging.INFO, # 记录INFO及以上的级别的信息
    format="%(asctime)s | %(levelname)s | %(message)s",
    # 依次显示日志时间、级别和具体内容
    encoding="utf-8",
)
# 先判断数据文件是否能够找到，找不到就报错并记录log
# 本次需要读取的数据文件
input_file = "load_selected_day.csv"

# 原来的固定写法，保留作为学习记录
# logging.info("开始分析负荷明细文件：load_selected_day.csv")

logging.info(f"开始分析负荷明细文件：{input_file}")

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
# csv_data = pd.read_csv("load_all_first96.csv")
# 原来的直接读取写法
# csv_data = pd.read_csv("load_selected_day.csv")

# 读不到文件就报错并记录
try:
    # 读取本次指定的负荷数据文件
    csv_data = pd.read_csv(input_file)
except FileNotFoundError as error:
    # 找不到文件时，记录文件名和具体错误
    logging.error(f"无法找到数据文件：{input_file}；错误信息：{error}")
    raise

# 测试：临时模拟一条缺失的功率数据
# csv_data.loc[0, "p_mw"] = None

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

# 升级：如果出现p_mw字段缺失，那么就应该停止分析，并且把这个错误写入log：
# check_required_columns(csv_data, required_columns)
# 把我们想检查的字段和已有的设置为集合set，然后相减可以如果不是空集合则有缺失
try:
    # 检查数据表是否包含必要字段
    check_required_columns(csv_data, required_columns)
except ValueError as error:
    # 如果检查发现缺少字段，先把错误写进日志
    logging.error(f"数据质量检查失败：{error}")
    # 重新抛出原来的错误，让程序停止
    raise


# 检查文件是否有数据，如果有异常则会停止运行并把运行错误写入日志
try:
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
    time_step_count = check_daily_time_steps(csv_data)
    print("时间步完整性检查通过：", time_step_count)
    expected_load_count = 98
    checked_groups = check_loads_per_time(csv_data, expected_load_count)

    print("每个时间步的负荷数量检查通过：", checked_groups)

    # 下一步
    # 直接使用读回的 CSV 计算总负荷和峰值

    csv_data["p_mw"] = pd.to_numeric(csv_data["p_mw"], errors="raise")
    # 它把 p_mw 这一列转换成数值类型。目前读到的是 float64，已经可以计算；
    # 增加这一步是为了以后读取其他 CSV 时，如果某个功率写成了无法转换的文本，
    # 程序会直接提示错误，不会继续求和。
except ValueError as error:
    logging.error(f"数据质量检查失败：{error}")
    raise

# 按照情景和时间进行分组，再在组内求功率和
csv_total = csv_data.groupby(
    ["scenario_id", "time"], as_index=False
)["p_mw"].sum()

# V2第一步：在构成csv_total后，找出总负荷达到阈值的状态，阈值：12MW
# V2：设置示例总负荷阈值，单位为 MW
alert_threshold_mw = 12.0

# 临时边界测试：把第一个时间步的总负荷设为阈值
# csv_total.loc[0, "p_mw"] = alert_threshold_mw

# logging.info("边界测试：临时将第一个时间步的总负荷设为阈值")

# 判断每个时间步的总负荷是否达到或超过阈值
high_load_mask = csv_total["p_mw"] >= alert_threshold_mw

# 根据判断结果，取出达到阈值的时间步
high_load_data = csv_total.loc[high_load_mask]

print("\n【总负荷阈值检查】")
print(f"示例阈值：{alert_threshold_mw} MW（达到或超过）")
print("达到阈值的时间步数量：", len(high_load_data))
print(high_load_data)

# V2下一步：把筛选结果汇总为一份告警文件，我们还需要记录他的触发原因
# 复制筛选结果，作为告警记录表
alert_records = high_load_data.copy()

# 为每条告警记录添加阈值和原因，同时告诉用户超出多少阈值
alert_records["threshold_mw"] = alert_threshold_mw
# 计算每条记录超出示例阈值的功率
alert_records["excess_mw"] = (
    alert_records["p_mw"] - alert_records["threshold_mw"]
)       # 两列相减然后储存到excess_mw中
alert_records["alert_reason"] = "总负荷达到或超过示例阈值"

# 保存告警记录
alert_records.to_csv("load_alerts.csv", index=False, encoding="utf-8")
print("告警记录已保存：load_alerts.csv")

# 取得本次分析的数据日期，写入logging
analysis_date = csv_total["time"].iloc[0].date()
# 在时间列取出第一个时间，再取出其中日期的部分

# 原来的做法：不论是否触发阈值，都使用 INFO 记录
# logging.info(
#     f"分析日期：{analysis_date}；示例阈值：{alert_threshold_mw} MW；"
#     f"触发时间步：{len(alert_records)}；结果文件：load_alerts.csv"
# )

# 现在：先把需要记录的内容整理成一条消息
log_message = (
    f"分析日期：{analysis_date}；示例阈值：{alert_threshold_mw} MW；"
    f"触发时间步：{len(alert_records)}；结果文件：load_alerts.csv"
)

# 根据是否存在告警记录，选择不同的日志级别
if alert_records.empty:
    print("本次没有触发告警，文件中只有表头。")
    logging.info(log_message)
else:
    # 原来的日志写法
    # logging.warning(log_message)

    # 找出本次告警中的最大超出量
    max_excess_mw = alert_records["excess_mw"].max()
    print(f"最大超出示例阈值：{max_excess_mw:.3f} MW")

    logging.warning(
        f"{log_message}；最大超出示例阈值：{max_excess_mw:.3f} MW"
    )


peak_index = csv_total["p_mw"].idxmax()

print("总负荷表规模：", csv_total.shape)
print("第一个时间步的总负荷（MW）：", csv_total["p_mw"].iloc[0])
print("最高总负荷（MW）：", csv_total.loc[peak_index, "p_mw"])
print("最高总负荷出现的时间：", csv_total.loc[peak_index, "time"])

# 下一步
# 绘图展示98个负荷总负荷功率

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

# 下一步
# 计算一天的使用电量，并导出一份日负荷汇总表
# 电量 = 功率 x 时间 MWh

# 每个时间步对应 15 分钟，也就是 0.25 小时
interval_hours = 0.25

# 估算所有负荷一天消耗的总电量
daily_energy_mwh = csv_total["p_mw"].sum() * interval_hours

print(f"估算总用电量（MWh）：{daily_energy_mwh:.2f}")

# 把一天的分析结果整理成一张汇总表
daily_summary = pd.DataFrame([
    {
        "scenario_id": csv_total["scenario_id"].iloc[0], # 取第一行
        "date": csv_total["time"].iloc[0].date(), # 选取出日期的部分
        "time_steps": len(csv_total),
        "peak_power_mw": peak_power,
        "peak_time": peak_time,
        "lowest_power_mw": lowest_power,
        "lowest_time": lowest_time,
        "average_power_mw": average_power,
        "peak_valley_difference_mw": peak_valley_difference,
        "estimated_energy_mwh": daily_energy_mwh,
        # V2：增加两个信息，记录当天的告警阈值和触发时间步数量
        "alert_threshold_mw": alert_threshold_mw,
        "alert_time_steps": len(alert_records),
    }
])
# 制表逻辑：我们只需要一行代表那一天的用电量，所以说列表里面包含了字典，
# 有几个字典就是有几行，现在只有一个字典，即一行，字典里面的键单独为一列


daily_summary.to_csv("daily_load_summary.csv", index=False, encoding="utf-8")
print("日负荷汇总表已保存：daily_load_summary.csv")

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

# V2：我们打算把告警点直接绘制在图表上：
# 在图中绘制告警阈值线
ax.axhline(                 # 画水平线
    y=alert_threshold_mw,
    color="#d1495b",
    linestyle="--",
    linewidth=1.5,
    label=f"Threshold: {alert_threshold_mw:.1f} MW",
)

# 如果有告警记录，就在曲线上标出告警点
if not alert_records.empty:
    ax.scatter(             # 画散点
        alert_records["time"],
        alert_records["p_mw"],
        color="#f4a261",
        s=35,
        label="Threshold reached",
        zorder=3,
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

# 用绿色点标记最低负荷
ax.scatter(
    lowest_time,
    lowest_power,
    color="#2a9d8f",
    s=55,
    label=f"Lowest: {lowest_power:.2f} MW",
    zorder=3,
)

# 用虚线显示平均负荷
ax.axhline( #.axhline 画一条水平线
    y=average_power,
    color="#8b7a52",
    linestyle="--",
    linewidth=1.5,
    label=f"Average: {average_power:.2f} MW",
)

# 在图的左上角显示估算总电量
ax.text( # .text 在图中添加文字
    0.02,
    0.97,
    f"Estimated load energy: {daily_energy_mwh:.2f} MWh",
    transform=ax.transAxes,
    va="top",
    fontsize=10,
    bbox={"facecolor": "white", "edgecolor": "#dddddd", "alpha": 0.9},
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

