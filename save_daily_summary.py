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

try:
    with connection.cursor() as cursor:
        # 执行插入，把字典作为参数传入
        # cursor.execute(insert_sql, summary_record)
        # 修改的代码新增了显示这次是更新还是新增，我们需要个变量来判断
        # cursor.execute会返回值1,2,0，我们拿这个值来判断
        affected_rows = cursor.execute(insert_sql, summary_record)
        # insert_sql就是我们刚才配置的值

    # 确认本次写入
    connection.commit()

except Exception:
    # 发生错误时尝试回滚，再把错误显示出来
    connection.rollback()
    raise

finally:
    connection.close()

# 原来的只显示数据插入成功
# print("日汇总写入成功：", summary_record["scenario_id"], summary_record["date"])
# 现在我们还需要判断这次插入的数据是新增的还是更新的，拿我们之前的affected_rows变量判断
if affected_rows == 1:
    print("已新增日汇总：", summary_record["scenario_id"], summary_record["date"])
elif affected_rows == 2:
    print("已更新日汇总：", summary_record["scenario_id"], summary_record["date"])
elif affected_rows == 0:
    print("日汇总已存在，数据没有变化：", summary_record["scenario_id"], summary_record["date"])
else:
    print("保存完成，数据库返回的影响行数：", affected_rows)