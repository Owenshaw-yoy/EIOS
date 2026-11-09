# 我们已经在mysql中建立了一天的负荷汇总记录，包括告警的时间步数
# 现在我们要针对这一天的告警，记录具体的告警记录和每个告警时间步的功率
# 由于第二份文件是第一份汇总的详细版，所以我们需要先进行检查
# 两份文件的必要字段是否存在、必要值是否缺失；
# 日汇总是否只有一条；
# 告警行数是否等于汇总中的告警数量；
# 有告警时，场景、日期和阈值是否与汇总一致，告警主键是否重复。
# 我们已经有了load_alerts.csv，所以我们只需要取得数据
# 此程序最新功能：一次读取3份 CSV，并在同一个事务中把一天的完整总负荷、日汇总和告警明细保存到 MySQL
# 同时做了必要的一致性检查。
# mysql的数据库基于python的表格，当输入的新的日期后，python会更新数据
# 但是执行mysql写入新的数据时，旧数据不会消失，而是新数据追加写入，因为主键不同
# mysql不会更新，旧数据是基于旧的python表格。
import pandas as pd

from data_quality import check_required_columns, check_missing_values

import getpass
import math
import pymysql

from datetime import datetime, time, timedelta
import sys

# 日汇总文件需要的字段
summary_columns = [
    "scenario_id",
    "date",
    "time_steps",
    "peak_power_mw",
    "peak_time",
    "lowest_power_mw",
    "lowest_time",
    "average_power_mw",
    "peak_valley_difference_mw",
    "estimated_energy_mwh",
    "alert_threshold_mw",
    "alert_time_steps",
]

# 告警文件需要的字段
alert_columns = [
    "scenario_id",
    "time",
    "p_mw",
    "threshold_mw",
    "excess_mw",
    "alert_reason",
]

# 读取两份已有的结果文件
summary_data = pd.read_csv("daily_load_summary.csv")
alerts_data = pd.read_csv("load_alerts.csv")

# 检查字段是否存在
check_required_columns(summary_data, summary_columns)
check_required_columns(alerts_data, alert_columns)

# 日汇总应该只有一条
if len(summary_data) != 1:
    raise ValueError("日汇总文件应该只有一条数据")

# 检查必要字段的缺失值
check_missing_values(summary_data, summary_columns)
check_missing_values(alerts_data, alert_columns)

# 取出日汇总记录
summary_record = summary_data.iloc[0].to_dict()

# 把汇总中的日期转换为日期类型
summary_date = pd.to_datetime(
    summary_record["date"],
    format="%Y-%m-%d",
    errors="raise",
).date()

print("汇总场景：", summary_record["scenario_id"])
print("汇总日期：", summary_date)

# 原来的交互输入方式
# target_date = input("请输入要处理的日期（YYYY-MM-DD）：").strip()

# 可以从命令行接收日期；没有提供时，仍然手动输入
if len(sys.argv) > 2:
    raise ValueError("保存程序最多只接受一个日期参数")
elif len(sys.argv) == 2:
    target_date = sys.argv[1].strip()
    print("命令行提供的处理日期：", target_date)
else:
    target_date = input("请输入要处理的日期（YYYY-MM-DD）：").strip()


if target_date != str(summary_date):
    raise ValueError("输入日期与日汇总文件中的日期不一致")

# 检查汇总里的告警数量与明细行数
expected_alert_steps = summary_record["alert_time_steps"]

if len(alerts_data) != expected_alert_steps:
    raise ValueError("告警明细行数与日汇总中的告警数量不一致")

# 告警文件有数据时，再检查每条记录
# .empty 用来判断 DataFrame 是否为空，如果没有告警的话，CSV只有表头->
# 此时跳过逐行检查，再结合日汇总中的告警数量判断两份文件的数量是否对应
if not alerts_data.empty:
    alerts_data["time"] = pd.to_datetime(
        alerts_data["time"],
        format="%Y-%m-%d %H:%M:%S",
        errors="raise",
    )

    if (alerts_data["scenario_id"] != summary_record["scenario_id"]).any():
        raise ValueError("告警明细的场景与日汇总不一致")
    
    # .dt.date 从每个告警时间中取出日期
    if (alerts_data["time"].dt.date != summary_date).any():
        raise ValueError("告警明细的日期与日汇总不一致")

    if (alerts_data["threshold_mw"] != summary_record["alert_threshold_mw"]).any():
        raise ValueError("告警明细的阈值与日汇总不一致")

    if alerts_data.duplicated(subset=["scenario_id", "time"]).any():
        raise ValueError("同一场景和时间存在重复告警")

print("汇总中的告警时间步：", expected_alert_steps)
print("告警文件中的记录数：", len(alerts_data))
print("上述基本检查通过")

# V3：现在准备导入一天完整时间步的总负荷：
# 读取总负荷曲线文件
total_columns = ["scenario_id", "time", "p_mw"]
total_data = pd.read_csv("daily_total_load.csv")

check_required_columns(total_data, total_columns)
check_missing_values(total_data, total_columns)

if total_data.empty:
    raise ValueError("总负荷文件没有数据")

# 转换时间和功率的数据类型
total_data["time"] = pd.to_datetime(
    total_data["time"],
    format="%Y-%m-%d %H:%M:%S",
    errors="raise",
)
total_data["p_mw"] = pd.to_numeric(total_data["p_mw"], errors="raise")

# 场景需要与日汇总一致
if (total_data["scenario_id"] != summary_record["scenario_id"]).any():
    raise ValueError("总负荷文件的场景与日汇总不一致")

# 当前场景应有当天完整的 96 个 15 分钟时间步
actual_times = pd.DatetimeIndex(total_data["time"].sort_values())
expected_times = pd.date_range(
    start=pd.Timestamp(summary_date),
    periods=96,
    freq="15min",
)

if len(total_data) != summary_record["time_steps"]:
    raise ValueError("总负荷记录数与日汇总的时间步数不一致")

if not actual_times.equals(expected_times):
    raise ValueError("总负荷时间步不完整、重复或日期不一致")

# 功率需要是有限数值
if not all(math.isfinite(value) for value in total_data["p_mw"]):
    raise ValueError("总负荷功率中存在非有限数值")

# 日汇总与完整总负荷数据一致性检查
# 用总负荷曲线重新计算日汇总中的主要数值
max_power = total_data["p_mw"].max()
min_power = total_data["p_mw"].min()

calculated_metrics = {
    "peak_power_mw": max_power,
    "lowest_power_mw": min_power,
    "average_power_mw": total_data["p_mw"].mean(),
    "peak_valley_difference_mw": max_power - min_power,
    "estimated_energy_mwh": total_data["p_mw"].sum() * 0.25,
}

for field, calculated_value in calculated_metrics.items():
    if not math.isclose(
        float(summary_record[field]),
        float(calculated_value),
        rel_tol=1e-10,
        abs_tol=1e-8,
    ):
        raise ValueError(f"总负荷曲线与日汇总的 {field} 不一致")

# 通过时间查找对应的总负荷
power_by_time = total_data.set_index("time")["p_mw"]

# 确认汇总中的最高、最低负荷时间对应正确的功率
for time_field, power_field in [
    ("peak_time", "peak_power_mw"),
    ("lowest_time", "lowest_power_mw"),
]:
    result_time = pd.to_datetime(summary_record[time_field], errors="raise")

    if result_time not in power_by_time.index:
        raise ValueError(f"日汇总中的 {time_field} 不在总负荷曲线中")

    if not math.isclose(                        # 允许误差
        float(power_by_time.loc[result_time]),
        float(summary_record[power_field]),
        rel_tol=1e-10,
        abs_tol=1e-8,
    ):
        raise ValueError(f"日汇总中的 {time_field} 与功率不一致")

# 完整日总负荷曲线与告警明细的一致性检查，避免把同一天但内容不对应的几份文件混着保存
# 根据总负荷曲线和阈值，核对告警明细
threshold = float(summary_record["alert_threshold_mw"])

if not math.isfinite(threshold):
    raise ValueError("日汇总中的告警阈值不是有限数值")

expected_alert_times = set(
    total_data.loc[total_data["p_mw"] >= threshold, "time"]
)
actual_alert_times = set(alerts_data["time"])

if expected_alert_times != actual_alert_times:
    raise ValueError("总负荷曲线与告警明细的时间点不一致")

for _, alert in alerts_data.iterrows():
    curve_power = float(power_by_time.loc[alert["time"]])

    if not math.isclose(
        float(alert["p_mw"]),
        curve_power,
        rel_tol=1e-10,
        abs_tol=1e-8,
    ):
        raise ValueError("告警功率与对应时间的总负荷不一致")

# 整理成 executemany 需要的多条记录
total_rows = []

for _, row in total_data.iterrows():
    total_rows.append(
        (
            str(row["scenario_id"]),
            row["time"].to_pydatetime(),
            float(row["p_mw"]),
        )
    )

print("总负荷与汇总、告警检查通过，准备写入时间步：", len(total_rows))

# V3，检查完整总负荷、告警明细与日汇总表一致后，开始写入mysql库：
insert_sql = """
INSERT INTO daily_load_summary ( 
    scenario_id,
    `date`,
    time_steps,
    peak_power_mw,
    peak_time,
    lowest_power_mw,
    lowest_time,
    average_power_mw,
    peak_valley_difference_mw,
    estimated_energy_mwh,
    alert_threshold_mw,
    alert_time_steps
)
VALUES (
    %(scenario_id)s,
    %(date)s,
    %(time_steps)s,
    %(peak_power_mw)s,
    %(peak_time)s,
    %(lowest_power_mw)s, 
    %(lowest_time)s,
    %(average_power_mw)s,
    %(peak_valley_difference_mw)s,
    %(estimated_energy_mwh)s,
    %(alert_threshold_mw)s,
    %(alert_time_steps)s
) AS new 
ON DUPLICATE KEY UPDATE
    time_steps = new.time_steps,
    peak_power_mw = new.peak_power_mw,
    peak_time = new.peak_time,
    lowest_power_mw = new.lowest_power_mw,
    lowest_time = new.lowest_time,
    average_power_mw = new.average_power_mw,
    peak_valley_difference_mw = new.peak_valley_difference_mw,
    estimated_energy_mwh = new.estimated_energy_mwh,
    alert_threshold_mw = new.alert_threshold_mw,
    alert_time_steps = new.alert_time_steps
"""

# 准备告警记录库与SQL：
# 把告警 DataFrame 整理为数据库需要的多条记录
alert_rows = []

for _, alert in alerts_data.iterrows():
    power = float(alert["p_mw"])
    threshold = float(alert["threshold_mw"])
    excess = float(alert["excess_mw"])

    # 检查功率、阈值和超出量是否为有限数值
    if not all(math.isfinite(value) for value in (power, threshold, excess)):
        raise ValueError("告警功率、阈值或超出量不是有限数值")

    # 当前规则：总负荷达到或超过阈值才应有告警
    if power < threshold:
        raise ValueError("告警记录中的总负荷低于阈值")

    # 允许浮点计算存在极小的数值误差
    if not math.isclose(
        excess,
        power - threshold,
        rel_tol=0,
        abs_tol=1e-8,
    ):
        raise ValueError("告警记录中的超出量与功率、阈值不一致")

    alert_rows.append(
        (
            str(alert["scenario_id"]),
            alert["time"].to_pydatetime(),
            power,
            threshold,
            excess,
            str(alert["alert_reason"]),
        )
    )

# 当天 00:00 到次日 00:00，确定要替换的时间范围
day_start = datetime.combine(summary_date, time.min)
day_end = day_start + timedelta(days=1)

scope_values = (
    summary_record["scenario_id"],
    day_start,
    day_end,
)

# 删除同一场景、同一天的旧告警
delete_alert_sql = """
DELETE FROM load_alerts
WHERE scenario_id = %s
  AND `time` >= %s
  AND `time` < %s
"""

# 插入本次告警明细
insert_alert_sql = """
INSERT INTO load_alerts (
    scenario_id,
    `time`,
    p_mw,
    threshold_mw,
    excess_mw,
    alert_reason
)
VALUES (%s, %s, %s, %s, %s, %s)
"""

# 在提交前检查数据库中的当日告警数量
count_alert_sql = """
SELECT COUNT(*)
FROM load_alerts
WHERE scenario_id = %s
  AND `time` >= %s
  AND `time` < %s
"""
# 删除同一场景、同一天的旧总负荷
delete_total_sql = """
DELETE FROM daily_total_load
WHERE scenario_id = %s
  AND `time` >= %s
  AND `time` < %s
"""

# 批量插入新的总负荷记录
insert_total_sql = """
INSERT INTO daily_total_load (scenario_id, `time`, p_mw)
VALUES (%s, %s, %s)
"""

# 查询事务中保存的当日总负荷记录数
count_total_sql = """
SELECT COUNT(*)
FROM daily_total_load
WHERE scenario_id = %s
  AND `time` >= %s
  AND `time` < %s
""" 

# 连接数据库
db_user = input("请输入 MySQL 用户名：").strip()
db_password = getpass.getpass("请输入 MySQL 密码：")

connection = pymysql.connect(
    host="127.0.0.1",
    port=3306,
    user=db_user,
    password=db_password,
    database="eios",
    charset="utf8mb4",
    connect_timeout=5,
    autocommit=False,
)

try:
    with connection.cursor() as cursor:
        # # 确认两张表都使用支持事务的 InnoDB 引擎
        # cursor.execute(
        #     "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
        #     "WHERE TABLE_SCHEMA = DATABASE() "
        #     "AND TABLE_NAME IN ('daily_load_summary', 'load_alerts')"
        # )
        # table_engines = dict(cursor.fetchall())

        # if (
        #     table_engines.get("daily_load_summary") != "InnoDB"
        #     or table_engines.get("load_alerts") != "InnoDB"
        # ):
        #     raise ValueError(f"两张表需要存在且使用 InnoDB：{table_engines}")
        # 原来是两张表的检查，现在替换为三张表
        # 确认三张表都使用支持事务的 InnoDB 引擎
        cursor.execute(
            "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME IN "
            "('daily_load_summary', 'load_alerts', 'daily_total_load')"
        )
        table_engines = dict(cursor.fetchall())

        if (
            table_engines.get("daily_load_summary") != "InnoDB"
            or table_engines.get("load_alerts") != "InnoDB"
            or table_engines.get("daily_total_load") != "InnoDB"
        ):
            raise ValueError(f"三张表需要存在且使用 InnoDB：{table_engines}")


        # 第一步：新增或更新日汇总
        summary_affected = cursor.execute(insert_sql, summary_record)

        # 第二步：删除该场景、该日期的旧告警
        deleted_alerts = cursor.execute(delete_alert_sql, scope_values)

        # 第三步：有告警时，批量插入新告警
        inserted_alerts = 0
        if alert_rows:
            inserted_alerts = cursor.executemany(insert_alert_sql, alert_rows)
            # cursor.executemany可以一次性插入多条告警

        # 第四步：检查事务中实际保存的告警数量
        cursor.execute(count_alert_sql, scope_values)
        database_alert_count = cursor.fetchone()[0]

        if database_alert_count != len(alert_rows):
            raise ValueError("数据库中的当日告警数量与准备写入的数量不一致")
                # 替换同一场景、同一天的总负荷曲线
        deleted_total = cursor.execute(delete_total_sql, scope_values)
        inserted_total = cursor.executemany(insert_total_sql, total_rows)

        # 在提交前检查写入的总负荷时间步数量
        cursor.execute(count_total_sql, scope_values)
        database_total_count = cursor.fetchone()[0]

        if database_total_count != len(total_rows):
            raise ValueError("数据库中的总负荷数量与准备写入的数量不一致")
    # 两部分都成功后，一起提交
    connection.commit()

except Exception:
    # 提交前发生错误时，尝试撤销本次事务
    try:
        connection.rollback()
    except pymysql.MySQLError as rollback_error:
        print("回滚状态无法确认，请重新查询数据库：", rollback_error)
    raise

finally:
    if connection.open:
        connection.close()

print("保存完成：", summary_record["scenario_id"], summary_date)
print("日汇总影响行数：", summary_affected)
print("替换前删除的旧告警数：", deleted_alerts)
print("本次写入的告警数：", inserted_alerts)
print("数据库中的当日告警数：", database_alert_count)
print("替换前删除的旧总负荷数：", deleted_total)
print("本次写入的总负荷数：", inserted_total)
print("数据库中的当日总负荷数：", database_total_count)