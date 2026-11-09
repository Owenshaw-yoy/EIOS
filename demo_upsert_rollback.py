# 此文件用于测试mysql的相关功能是否符合预期
import getpass
import pandas as pd
import pymysql

from data_quality import check_required_columns, check_missing_values

# V3：做一个手动导入每日负荷总结表daily_load_summary.csv进我们的sql数据库
# 日汇总文件中需要具备的字段
required_columns = [
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
] # 与daily_load_summary.csv一样

# 读取当前日汇总文件
summary_data = pd.read_csv("daily_load_summary.csv")

# 检查必要字段是否存在
check_required_columns(summary_data, required_columns)

# 当前日汇总文件应该只有一条数据，即我们选定的日期下的数据
if len(summary_data) != 1:
    raise ValueError("日汇总文件应该只有一条数据")

# 检查必要字段是否存在缺失值
check_missing_values(summary_data, required_columns)

# 取出第一行，并转换为字典
summary_record = summary_data.iloc[0].to_dict()

print("文件中的场景：", summary_record["scenario_id"])
print("文件中的日期：", summary_record["date"])

# 由操作者指定本次要导入的日期
target_date = input("请输入要导入的日期（YYYY-MM-DD）：").strip()

# 防止你想导入的日期和目前表中的日期不一致而导入错误
if target_date != str(summary_record["date"]):
    raise ValueError("输入日期与日汇总文件中的日期不一致")

# 开始插入数据
# 使用字典中的字段名作为 SQL 参数
# INSERT INTO daily_load_summary：向这张表插入记录
# 第一组是字段，对应的是列名
# 第二组列出这些字段对应的数据
# %(date)s 这样的写法是占位符。
# 等会儿我们把 summary_record 字典交给 PyMySQL，由它按照键名提供对应的值。
# 同时我们需要保证插入同一时间的属性时，数据需要更新而非不允许插入同一时间数据
# 整体逻辑是：先尝试插入这条新记录；如果没有主键冲突，就新增；
# 如果主键冲突，就执行 ON DUPLICATE KEY UPDATE 后面的更新
# 在这张表中，我们设置的主键是：scenario_id + date
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
# 后面的AS部分：如果遇到主键重复或冲突，就执行后面的更新，而不是报错

# 运行时输入账号和密码
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

# 复制日汇总字典，制作一个单独的测试场景
demo_record = summary_record.copy()
demo_record["scenario_id"] = "EIOS_UPSERT_DEMO"

try:
    # 确保本次测试不会自动提交
    connection.autocommit(False)

    with connection.cursor() as cursor:
        # 先确认这个测试场景编号没有被使用
        cursor.execute(
            "SELECT COUNT(*) FROM daily_load_summary WHERE scenario_id = %s",
            (demo_record["scenario_id"],),
        )

        if cursor.fetchone()[0] != 0:
            raise ValueError("测试场景编号已经存在，请停止测试")

        # 第一次：测试场景不存在，应新增
        insert_result = cursor.execute(insert_sql, demo_record)

        # 第二次：相同场景、日期和数据，应保持不变
        same_result = cursor.execute(insert_sql, demo_record)

        # 第三次：保持主键不变，模拟一个字段发生变化
        demo_record["alert_time_steps"] += 1
        update_result = cursor.execute(insert_sql, demo_record)

        # 查询事务中的测试结果
        cursor.execute(
            "SELECT alert_time_steps FROM daily_load_summary "
            "WHERE scenario_id = %s AND `date` = %s",
            (demo_record["scenario_id"], demo_record["date"]),
        )
        demo_alert_steps = cursor.fetchone()[0]

        print("第一次新增的返回值：", insert_result)
        print("第二次相同数据的返回值：", same_result)
        print("第三次数值变化的返回值：", update_result)
        print("事务中查询到的模拟告警时间步：", demo_alert_steps)

    # 测试结束：撤销本次尚未提交的测试数据
    connection.rollback()
    print("测试数据已回滚")

except Exception:
    connection.rollback()
    raise

finally:
    connection.close()