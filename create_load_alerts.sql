CREATE TABLE load_alerts (
    scenario_id VARCHAR(64) NOT NULL,  # 场景编号
    `time` DATETIME NOT NULL,          # 触发阈值的时间点
    p_mw DOUBLE NOT NULL,              # 当前时间点的总负荷，MW
    threshold_mw DOUBLE NOT NULL,      # 本次使用的示例阈值，MW
    excess_mw DOUBLE NOT NULL,         # 总负荷减去阈值，MW
    alert_reason VARCHAR(255) NOT NULL, # 告警原因

    PRIMARY KEY (scenario_id, `time`)
) ENGINE = InnoDB;