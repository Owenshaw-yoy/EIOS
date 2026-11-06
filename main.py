import simbench as sb   # 导入simbench第三方库，并给他一个简短的名字sb
import pandas as pd     # 导入pandas数据保存整理的第三方库
import sys              # 导入系统自带标准库模块
# 根据网络编号读取编号为‘1-MV-comm--0-sw’的商用型配电网，结果放进变量net：
scenario_id = "1-MV-comm--0-sw"     # 多赋值给一个scenaro_id后续要用
net = sb.get_simbench_net(scenario_id) # 库提供的函数
# MV代表中压，comm代表商业类型场景
# 至此，net就是一个装着整个配电网资料的容器，里面有很多张表，net就是一个对象：
# net.bus:母线信息表；net.line:线路信息表；net.load:负荷设备信息表；net.profiles:不同类型的时序曲线数据

# 取得负荷的绝对有功功率时序：
# SimBench 的部分原始曲线是相对值，需要结合具体设备的基准功率，才能得到有单位的功率值。
# 这个函数根据设备与曲线的对应关系，使用负荷表中的 p_mw 值进行换算。
# 函数返回一个 DataFrame 对象，并赋给变量 load_p，结果为一张pandas表格，专业名为DataFrame，可以理解为一张Excel表
load_p = sb.get_absolute_profiles_from_relative_profiles(
    net, "load", "p_mw"
)
# 把相对曲线和设备参数对应起来，得到每个负荷在时间步的有功功率

print("\n【全年原始数据示例】")
print('负荷数量',len(net.load))    # len(net.load)：检查网络中有多少个负荷
print('负荷数据规模',load_p.shape)  # 查看功率数据有多少行和列，.shape是pandas的属性，返回行数，列数

print('前3个时间标记：')
print(net.profiles['load']['time'].iloc[:3])
# net.profiles            取得时序数据
# ["load"]                取得负荷相关的时序表
# ["time"]                取得其中的时间列
# .iloc[:3]               取前 3 行   .iloc[选择哪些行, 选择哪些列]

print("前 3 个时间步、前 3 个负荷的功率（MW）：")
print(load_p.iloc[:3, :3])  # pandas按位置取数据的方法，[:3,:3]表示取前三行前三列，三个时间步，前三个负荷

# 至此，我们已经使用的三方库有：SimBench；pandapower；pandas

# print("sb 的类型：", type(sb))
# print("net 的类型：", type(net))
# print("net.load 的类型：", type(net.load))
# print("load_p 的类型：", type(load_p))
# 上述用于理解每个模块是什么

# 下一步：

# 选取时间和负荷：
time_column = net.profiles["load"]["time"] 
# net.profiles是取得网络中的时序变量名，包含：load、powerplants、renewables、storage
# 我们需要取得有关负荷的时间表，所以需要从负荷的时序表中取得time这一列：先根据一个键取出内容，再从取得的内容中取下一层。

# 可以在这里选择想要分析的那一天，结果会同步到表中
# target_date = "2016-01-02"
# 如果传入了想选择的日期，就使用日期，如果没有就默认分析2026-01-01
if len(sys.argv) > 1:
    target_date = sys.argv[1]
else:
    target_date = "2016-01-01"

# 将原始时间标记转换为 pandas 的日期时间
time_as_datetime = pd.to_datetime(
    time_column, format="%d.%m.%Y %H:%M"
)

# 找出属于目标日期的时间行
date_mask = time_as_datetime.dt.strftime("%Y-%m-%d") == target_date
# .dt是pandas提供的日期时间操作入口,.strftime把时间按年月日格式表示
# 之后与target_data比较，返回True/False

# 根据相同的筛选条件，取得对应的时间和负荷功率
selected_time = time_column.loc[date_mask]
selected_load_p = load_p.loc[date_mask].copy()

if selected_time.empty:
    raise ValueError(f"没有找到 {target_date} 的负荷数据")

print("目标日期：", target_date)
print("选中的负荷数据规模：", selected_load_p.shape)
print("该日第一个时间标记：", selected_time.iloc[0])

load_id = load_p.columns[0] # 取出功率表中的第一列的列名
power_column = load_p.iloc[:, 0] # 第一列负荷的所有内容，所以得到第一个负荷的功率

# 检查时间和功率是否对齐，不对齐则抛出异常
if not time_column.index.equals(power_column.index):
    raise ValueError("时间和功率的行索引不一致")

# 把上述采集的数据，用字典创建一张新的表：
result = pd.DataFrame({
    "scenario_id": scenario_id,  # 键值对的方式
    "time": time_column,
    "load_id": load_id,
    "p_mw": power_column,
})

# 保存CSV：
result.to_csv("load_example.csv", index=False, encoding="utf-8")

print("\n【全年第一个负荷的示例】")
print("已保存：load_example.csv")
print("数据行数：", len(result))
print(result.iloc[:3])

# 下一步
# 扩展为全部负荷，先打印前96个时间步，对应一天的量
# 最后获得所有负荷在第一天的数据

# 复制前96行，所有的98个负荷为一张表，保存为day_power:(旧)
# day_power = load_p.iloc[:96, :].copy()
# 在day_power前第一列新增一列：()中的参数为位置；名字；内容：(旧)
# day_power.insert(0, "time", time_column.iloc[:96])

# 使用目标日期筛选出的功率数据
day_power = selected_load_p.copy()

# 将同一天对应的时间标记加到功率表中
day_power.insert(0, "time", selected_time)

# .melt方法：把负荷展开为记录
all_loads = day_power.melt(
    id_vars="time",         # 保留时间列
    var_name="load_id",     # 把原来的负荷列名放进新列
    value_name="p_mw",      # 把原来的功率数值放进新列
)

# 把场景编号放在新表最前面
all_loads.insert(0, "scenario_id", scenario_id)

# 原来的旧代码，新代码新增了日期选择功能，上述(旧)标记的都是旧代码
# all_loads.to_csv("load_all_first96.csv", index=False, encoding="utf-8")

# 修改后的导出文件名和时间范围
all_loads.to_csv("load_selected_day.csv", index=False, encoding="utf-8")
print(f"\n【目标日期 {target_date} 的分析数据】")
print("时间范围：", selected_time.iloc[0], "至", selected_time.iloc[-1])
# .iloc[-1]表示取最后一行，原来的time_column.iloc[0] 
# 和 time_column.iloc[95] 固定指向全年数据的第一天，现在改为显示所选日期的首尾时间。

# print("时间范围：", time_column.iloc[0], "至", time_column.iloc[95])
print("整理后的数据规模：", all_loads.shape)
print("第一个时间步的前 3 个负荷：")
print(all_loads.iloc[[0, 96, 192]]) # 取新表中的第0行，96行和192行数据验证

# 下一步
# 开始第一个运行指标，将同一时间，同一场景下各负荷的P_WM相加，得到一个总负荷曲线

# 先预处理：转换时间，复制一份all_load里面的数据给新变量，这样all_load的值不会变化
daily_data = all_loads.copy()

# 使用pandas函数：.to_datetime将时间文本转换为日期时间类型
# 转换后，pandas 才能更可靠地按时间排序、比较时间间隔，以及统计某一天的数据
daily_data["time"] = pd.to_datetime(
    daily_data["time"], format="%d.%m.%Y %H:%M"
) # format告诉pandas原来文本的排列方式：上述占位符表示:日，月，年，小时，分钟

# 检查缺失值：.isna()和.any()方法，前者逐个检查缺失值，后者检查结果里是否至少有一个True
if daily_data["time"].isna().any() or daily_data["p_mw"].isna().any():
    raise ValueError("时间或负荷功率存在缺失值，请先检查数据")

# 核心代码：groupby类似SQL语句：把编号相同，时间记录也相同的记录放在一组
daily_total = daily_data.groupby(
    ["scenario_id", "time"], as_index=False
)["p_mw"].sum()                             # 选取每组中的功率那一列，把他们相加
# 为什么同时按场景和时间分组？
# 因为我们需要保留数据属于哪个网络；将来如果有多个场景，也不会把它们同一时刻的负荷混在一起

# 得到98个负荷在同一时间累计功率，没有扣除发电和网损：
daily_total.to_csv("daily_total_load.csv", index=False, encoding="utf-8")

print("总负荷表的规模：", daily_total.shape)
print("前 3 个时间步的总负荷：")
print(daily_total.iloc[:3])

# 核对
print("原始功率表中第一个时间步的负荷和：", selected_load_p.iloc[0, :].sum())
print("汇总表中第一个时间步的负荷和：", daily_total["p_mw"].iloc[0])

# 下一步
# 找出这一天总负荷最大值，以及他出现的时间
# 在工程中，知道最高是多少还不够，还需要知道什么时候发生

# 使用pandas的.idxman()方法，找出这一列的最大值，返回最大值所在的行标签
peak_index = daily_total["p_mw"].idxmax()
# 把这一列的最大功率值和对应的时间拿出来，方法：表格.loc[行标签,列名]
peak_power = daily_total.loc[peak_index, "p_mw"]
peak_time = daily_total.loc[peak_index, "time"]

# 打印
print("最高总负荷（MW）：", peak_power)
print("最高总负荷出现的时间：", peak_time)