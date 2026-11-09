# 在EIOS数据库中创建第一个表：
CREATE TABLE daily_load_summary (
    scenario_id VARCHAR(64) NOT NULL, # 场景编号，最多保存64字符
    `date` DATE NOT NULL,
    time_steps INT NOT NULL,     # 列名；列类型；NOT NULL表示这个字段不能缺失
    peak_power_mw DOUBLE NOT NULL,
    peak_time DATETIME NOT NULL,
    lowest_power_mw DOUBLE NOT NULL,
    lowest_time DATETIME NOT NULL,
    average_power_mw DOUBLE NOT NULL,
    peak_valley_difference_mw DOUBLE NOT NULL,
    estimated_energy_mwh DOUBLE NOT NULL,
    alert_threshold_mw DOUBLE NOT NULL,
    alert_time_steps INT NOT NULL,
    PRIMARY KEY (scenario_id, `date`)
    # 把场景编号和日期的组合作为主键。相同场景的不同日期可以分别保存；
    # 如果两条记录的场景和日期都一样，数据库会阻止直接插入重复主键。
) ENGINE = InnoDB;  # 指定这张表使用InnoDB引擎

