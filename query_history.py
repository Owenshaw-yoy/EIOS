# V3：制作一个按日期范围查询日汇总的小功能
# 如果MySQL没有相应的数据库，则需要先添加才能分析
from datetime import datetime
import getpass
import pymysql


# 输入场景和日期范围
scenario_id = input("请输入场景编号：").strip()
start_text = input("请输入开始日期（YYYY-MM-DD）：").strip()
end_text = input("请输入结束日期（YYYY-MM-DD）：").strip()

# 将日期字符串转换为日期对象
start_date = datetime.strptime(start_text, "%Y-%m-%d").date()
end_date = datetime.strptime(end_text, "%Y-%m-%d").date()

if start_date > end_date:
    raise ValueError("开始日期不能晚于结束日期")

# 查询日期范围内已经保存的日汇总
history_sql = """
SELECT
    `date`,
    peak_power_mw,
    estimated_energy_mwh,
    alert_threshold_mw,
    alert_time_steps
FROM daily_load_summary
WHERE scenario_id = %s
  AND `date` >= %s
  AND `date` <= %s
ORDER BY `date`
"""

# 下一步
# 运行时输入数据库账号和密码
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
    cursorclass=pymysql.cursors.DictCursor,
)

try:
    with connection.cursor() as cursor:
        # 三个参数按顺序对应 SQL 中的三个 %s
        cursor.execute(history_sql, (scenario_id, start_date, end_date))
        history_rows = cursor.fetchall()

        if not history_rows:
            print("该场景和日期范围内没有查到日汇总记录。")
        else:
            print(f"\n【范围内已保存汇总的日期：{len(history_rows)} 天】")

            total_energy = 0.0
            total_alert_steps = 0

            for row in history_rows:
                print(
                    f"{row['date']} | "
                    f"峰值 {row['peak_power_mw']:.2f} MW | "
                    f"估算电量 {row['estimated_energy_mwh']:.2f} MWh | "
                    f"示例阈值 {row['alert_threshold_mw']:.2f} MW | "
                    f"告警时间步 {row['alert_time_steps']}"
                )

                total_energy += row["estimated_energy_mwh"]
                total_alert_steps += row["alert_time_steps"]

            print(f"\n已保存日期的估算电量合计：{total_energy:.2f} MWh")
            print(f"已保存日期的告警时间步合计：{total_alert_steps}")

finally:
    connection.close()