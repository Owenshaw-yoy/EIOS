# V3：创建数据库表
# 每一行记录同一个场景在某个时间步的总负荷

CREATE TABLE daily_total_load (
    scenario_id VARCHAR(64) NOT NULL,
    `time` DATETIME NOT NULL,
    p_mw DOUBLE NOT NULL,

    PRIMARY KEY (scenario_id, `time`)
) ENGINE = InnoDB;