# V3：这一步是通过python查询MySQL中的完整日负荷数据、历史日汇总和告警明细
# 即使现在的CSV是最新的，但是mysql只要已经保存过之前的数据，我们就能直接查询
# 而不需要重新运行python的数据
# 输入一次场景和日期，就能够把 MySQL 中的三类结果都取出来。
from datetime import datetime, time, timedelta
import getpass
import pymysql
import matplotlib.pyplot as plt


# 输入要查询的场景和日期
scenario_id = input("请输入场景编号：").strip()
date_text = input("请输入查询日期（YYYY-MM-DD）：").strip()

# 将输入的日期字符串转换为日期对象
target_date = datetime.strptime(date_text, "%Y-%m-%d").date()

# 计算当天 00:00 和次日 00:00
day_start = datetime.combine(target_date, time.min)
day_end = day_start + timedelta(days=1)

# 运行时输入数据库账号和密码
db_user = input("请输入 MySQL 用户名：").strip()
db_password = getpass.getpass("请输入 MySQL 密码：")

# 下一步，准备查询语句：
# 按场景和日期查询一条日汇总
summary_sql = """
SELECT
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
FROM daily_load_summary
WHERE scenario_id = %s
  AND `date` = %s
"""
# 上面的%s是占位符，用户输入什么信息，这里就会变成什么信息
# 占位符的数量要和后面cursor.execute(summary_sql, (scenario_id, target_date))对应

# 按场景和时间范围查询当天的告警明细
alerts_sql = """
SELECT
    `time`,
    p_mw,
    threshold_mw,
    excess_mw,
    alert_reason
FROM load_alerts
WHERE scenario_id = %s
  AND `time` >= %s
  AND `time` < %s
ORDER BY `time`
"""
# 按场景和时间范围查询当天的总负荷曲线
total_sql = """
SELECT
    `time`,
    p_mw
FROM daily_total_load
WHERE scenario_id = %s
  AND `time` >= %s
  AND `time` < %s
ORDER BY `time`
"""

# select ... from .... where ....：SQL查询语句

# 下一步，连接数据库并展示结果
# 连接数据库
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
# DictCursor使得让查询到的数字按照字典类型使用，输入键名即能够取得值

try:
    with connection.cursor() as cursor:
        # 查询日汇总
        cursor.execute(summary_sql, (scenario_id, target_date))
        summary = cursor.fetchone()
        # fetchone()取一条记录，同一时间，同一场景最多只有一条
        # 日汇总的主键是场景和日期的组合，所以同一场景日期只会有一条日汇总
        # 所以只需要取一条记录即可
        if summary is None:
            print("没有查到该场景、该日期的日汇总记录。")
            print("请确认场景和日期是否正确，以及数据是否已经入库。")

        else:
            print("\n【日负荷汇总】")
            print(f"场景：{summary['scenario_id']}")
            print(f"日期：{summary['date']}")
            print(f"时间步数：{summary['time_steps']}")
            print(
                f"最高负荷：{summary['peak_power_mw']:.2f} MW，"
                f"时间：{summary['peak_time']}"
            )
            print(
                f"最低负荷：{summary['lowest_power_mw']:.2f} MW，"
                f"时间：{summary['lowest_time']}"
            )
            print(f"平均负荷：{summary['average_power_mw']:.2f} MW")
            print(f"峰谷差：{summary['peak_valley_difference_mw']:.2f} MW")
            print(f"估算用电量：{summary['estimated_energy_mwh']:.2f} MWh")
            print(f"告警阈值：{summary['alert_threshold_mw']:.2f} MW")
            print(f"汇总中的告警时间步：{summary['alert_time_steps']}")

            # 查询同一天的告警明细
            cursor.execute(alerts_sql, (scenario_id, day_start, day_end))
            alerts = cursor.fetchall()

            print(f"\n【告警明细：{len(alerts)} 条】")

            if not alerts: # 查到了日汇总，但没有查到明细，说明没有告警
                print("当天没有查到告警明细。")
            else:
                for alert in alerts:
                    print(
                        f"{alert['time']} | "
                        f"总负荷 {alert['p_mw']:.2f} MW | "
                        f"阈值 {alert['threshold_mw']:.2f} MW | "
                            f"超出 {alert['excess_mw']:.2f} MW | "
                        f"原因：{alert['alert_reason']}"
                    )
            # 查询同一天的总负荷曲线
            cursor.execute(total_sql, (scenario_id, day_start, day_end))
            total_rows = cursor.fetchall()

            print(f"\n【总负荷曲线：{len(total_rows)} 条】")

            if not total_rows:
                print("数据库中没有查到该日期的总负荷记录。")
            else:
                print("前 5 个时间步：")
                for row in total_rows[:5]:  # 只取出前五条作为显示
                    print(
                        f"{row['time']} | "
                        f"总负荷 {row['p_mw']:.2f} MW"
                    )
                # 增加画图代码：让查询程序直接用 MySQL 里读取的历史数据画图。
                # 这样，以后即使当前 CSV 已经被其他日期覆盖，
                # 只要数据库里保存过那一天，就仍然能画出那一天的负荷曲线：
                
                # 把数据库记录整理成画图需要的时间和功率
                curve_times = []
                curve_powers = []

                for row in total_rows:
                    curve_times.append(row["time"])
                    curve_powers.append(row["p_mw"])

                # 创建画布并绘制总负荷曲线
                fig, ax = plt.subplots(figsize=(10, 5))

                ax.plot(
                    curve_times,
                    curve_powers,
                    color="#2468a2",
                    linewidth=1.5,
                    label="Total load",
                )

                # 画出日汇总中保存的示例告警阈值
                ax.axhline(
                    y=summary["alert_threshold_mw"],
                    color="#d1495b",
                    linestyle="--",
                    label=f"Example threshold: {summary['alert_threshold_mw']:.1f} MW",
                )

                # 有告警时，在曲线上标出告警时间点
                if alerts:
                    alert_times = []
                    alert_powers = []

                    for alert in alerts:
                        alert_times.append(alert["time"])
                        alert_powers.append(alert["p_mw"])

                    ax.scatter(
                        alert_times,
                        alert_powers,
                        color="#f4a261",
                        label="Alert time steps",
                        zorder=3,
                    )

                ax.set_title(f"Daily Load - {scenario_id} - {target_date}")
                ax.set_xlabel("Time")
                ax.set_ylabel("Total load (MW)")
                ax.grid(True, linestyle="--", alpha=0.25)
                ax.legend()

                fig.autofmt_xdate()
                fig.tight_layout()
                fig.savefig("db_daily_load_curve.png", dpi=150)
                plt.close(fig)

                print("数据库曲线图已保存：db_daily_load_curve.png")

finally:
    connection.close()