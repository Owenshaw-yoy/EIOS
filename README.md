# EIOS｜能源数据分析与优化系统

EIOS 是一个面向综合能源系统的工程实践项目。项目基于 SimBench 公开电网基准数据，完成单日负荷数据整理、质量检查、指标统计、示例阈值告警，以及使用 MySQL 保存和查询历史分析结果。

在 V4 中，项目进一步实现了短期总负荷预测：使用最近 96 个 15 分钟负荷值，预测下一时间步的总负荷，并比较简单基线和基于 PyTorch 的 Transformer 模型。

目前 V1—V4 已完成相应的本地工程实践。后续计划结合配电网开展潮流分析，并进行后续探索储能优化的相关内容。

## 数据来源与范围

当前使用 SimBench 的 `1-MV-comm--0-sw` 商业型中压配电网场景：

- 负荷数量：98 个；
- 数据年份：2016 年；
- 时间间隔：15 分钟；
- 常规完整日包含 96 个时间步；
- 单日分析入口处理数据中指定的一天；
- V4 使用 2016 年全年时序中的有效窗口构造训练、验证和测试样本。

项目分析的是公开基准场景中的负荷侧有功功率。
各时间步的总负荷由该场景下各负荷的有功功率相加得到。

数据与工具来源：[SimBench 官方仓库](https://github.com/e2nIEE/simbench)  
许可信息：[SimBench 1.6.3 许可说明](https://github.com/e2nIEE/simbench/blob/v1.6.3/LICENSE)

## 当前功能

- 按日期筛选单日负荷数据；
- 检查必要字段、缺失值、重复记录、时间步和负荷数量；
- 汇总每个时间步的总负荷，计算峰值、谷值、平均负荷和峰谷差；
- 根据 15 分钟时间间隔估算日用电量；
- 使用 12 MW 示例阈值，记录达到或超过阈值的时间步；
- 保存日汇总、告警明细、曲线图片和运行日志；
- 将日汇总、告警明细和总负荷曲线写入 MySQL；
- 按场景和日期查询历史结果，并根据数据库记录绘制曲线；
- 按日期范围查询已保存的日汇总；
- 使用 Python 和 Shell 入口串联单日分析与数据库保存。

注意：12 MW 是演示用阈值。

## 数据处理与保存流程

```text
SimBench 基准场景
       ↓
筛选目标日期、整理负荷明细
       ↓
检查数据并计算各时间步总负荷
       ↓
生成日汇总、告警、曲线和 CSV
       ↓
检查结果之间的一致性
       ↓
在同一个事务中写入 MySQL
       ↓
按日期或日期范围查询历史结果
```

## MySQL 数据表

| 表 | 内容 | 主键 |
|---|---|---|
| `daily_load_summary` | 每个场景每天的一条日汇总 | `scenario_id`、`date` |
| `load_alerts` | 达到示例阈值的时间步明细 | `scenario_id`、`time` |
| `daily_total_load` | 每个时间步的总负荷曲线 | `scenario_id`、`time` |

保存程序使用 InnoDB 事务处理三张表。同一场景、同一天重新导入时，日汇总按主键新增或更新，告警和总负荷明细按当天范围替换。其他日期的记录保留。

当前保存的是各时间步的**总负荷**，没有将每个负荷设备的历史明细分别保存到数据库。同一天多次导入后，数据库保留最新成功导入的结果，不保存每次运行的独立版本。

## 运行环境

当前功能已在现有 macOS 环境中运行，使用 Python 3.11 和 MySQL 9.7.4；Python 依赖记录在 `requirements.txt` 中。

在项目根目录创建并启用虚拟环境后安装依赖：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

MySQL 服务需要单独安装并启动。程序运行时输入数据库用户名和密码，密码不写入项目代码。

### 首次建立数据库表

以下步骤用于首次初始化。已有数据库和同名表时，不需要重复建表。

从项目根目录登录 MySQL。下面以本地 `root` 账号为例，实际使用时请替换为自己的账号：

```bash
mysql -u root -p
```

在 MySQL 命令行中执行：

```sql
CREATE DATABASE IF NOT EXISTS eios CHARACTER SET utf8mb4;
USE eios;

SOURCE create_daily_summary.sql;
SOURCE create_load_alerts.sql;
SOURCE create_daily_total_load.sql;
```

建表脚本用于建立表结构，不会自动导入项目历史数据。

### 分析并保存一天

在项目根目录运行：

```bash
python run_and_save.py 2016-12-01
```

程序先准备和分析数据；分析成功后，再提示输入 MySQL 用户名和密码并保存结果。

也可以分两步执行：

```bash
python run_all.py 2016-12-01
python save_day_results.py
```

第二步输入的处理日期需要与当前分析结果的日期一致。

分析流程成功后才应进行保存。如果分析中途失败，目录中可能仍有旧文件或部分新文件，不能仅凭文件存在就认为本次分析成功。

在 macOS 终端中，也可以使用 Shell 入口：

```bash
chmod +x run_eios.sh
./run_eios.sh 2016-12-01
```

脚本会定位项目目录并使用项目 `.venv` 中的 Python。

### 查询历史结果

查询某一天的日汇总、告警和总负荷曲线：

```bash
python query_day_results.py
```

根据提示输入场景、日期和 MySQL 账号。查询到总负荷后，程序会生成 `db_daily_load_curve.png`。

查询日期范围内已保存的日汇总：

```bash
python query_history.py
```

范围统计只包含数据库中已经保存的日期；未入库的日期不会被当作零值。

## 主要输出

| 文件 | 内容 |
|---|---|
| `load_example.csv` | 第一个负荷的全年数据示例 |
| `load_selected_day.csv` | 目标日各负荷明细 |
| `daily_total_load.csv` | 目标日各时间步的总负荷 |
| `daily_load_summary.csv` | 日指标、示例阈值和告警数量 |
| `load_alerts.csv` | 达到示例阈值的时间、功率、阈值、超出量和原因 |
| `daily_load_curve.png` | 本次分析生成的负荷曲线 |
| `db_daily_load_curve.png` | 根据数据库查询结果生成的历史曲线 |
| `eios.log` | 分析过程、规则触发和部分错误日志 |

成功运行分析后，会重新生成同名 CSV 和 daily_load_curve.png；查询到总负荷数据时，查询程序会生成或覆盖 db_daily_load_curve.png。日志按追加方式记录，MySQL 可以保留不同场景或日期的已导入记录。

## 示例结果

在场景 `1-MV-comm--0-sw` 下分析 `2016-12-01`：

| 指标 | 结果 |
|---|---:|
| 最高总负荷 | 约 13.35 MW，10:45 |
| 最低总负荷 | 约 3.66 MW，01:45 |
| 平均总负荷 | 约 8.54 MW |
| 估算负荷总电量 | 约 205.04 MWh |
| 示例告警阈值 | 12 MW |
| 达到阈值的时间步 | 15 个 |

电量按每个时间步的功率代表相应 15 分钟区间的功率进行估算，并非企业实际计量值。

## V4 短期负荷预测

### 预测任务

项目使用 SimBench 场景 `1-MV-comm--0-sw` 的 2016 年总负荷数据。

- 输入：最近 96 个时间步的总负荷；
- 时间间隔：15 分钟；
- 输出：下一时间步的总负荷预测值，单位为 MW；
- 评价方式：使用历史时序构造滚动单步预测样本；
- 当前运行入口：读取一个历史日的负荷，输出一次下一时间步预测。

对原始时间标记，预测样本保持来源顺序，并筛选输入到目标之间时间标记相邻间隔为 15 分钟的窗口。

### 模型与评价

项目实现了简单持平基线、线性模型、小型神经网络和基于 PyTorch 的 Transformer 预测模型。模型使用训练集学习，通过验证集比较并选择模型，再在较晚的测试时段进行评价。

按预测目标时间划分数据：

- 训练集：目标时间早于 2016-10-01，共 26,108 条样本；
- 验证集：目标时间从 2016-10-01 至 2016-11-30，共 5,764 条样本；
- 测试集：目标时间从 2016-12-01 开始，共 2,976 条样本。

| 数据集 | Transformer MAE | 简单基线 MAE |
|---|---:|---:|
| 验证集 | 0.4117 MW | 0.4146 MW |
| 测试集 | 0.6642 MW | 0.5138 MW |

当前实验中，Transformer 在验证集上略优于基线，但在测试时段的误差高于基线。

### 运行单日分析与预测

在项目根目录、已启用项目虚拟环境并安装依赖后运行：

```bash
python run_analysis_forecast.py 2016-01-05
```

程序先执行单日负荷准备和分析，再读取生成的总负荷文件，输出简单基线和 Transformer 对下一时间步的预测。

该入口会更新单日分析生成的同名结果文件。预测结果当前输出到终端，尚未单独保存到 MySQL；原有的数据库保存与查询功能仍使用 V3 入口。

当前模型加载使用项目中的 `transformer_best_1795590008985786000.pt` 文件。

## 项目文件

| 文件 | 作用 |
|---|---|
| `main.py` | 获取并整理目标日期的负荷数据 |
| `data_quality.py` | 提供数据质量检查函数 |
| `inspect_data.py` | 检查、分析、告警和绘图 |
| `run_all.py` | 依次运行数据准备与分析 |
| `save_day_results.py` | 检查并保存完整单日结果到 MySQL |
| `query_day_results.py` | 查询单日结果并绘制数据库曲线 |
| `query_history.py` | 查询日期范围内已保存的日汇总 |
| `run_and_save.py` | 一键进行单日分析与数据库保存 |
| `run_eios.sh` | 定位项目目录并启动一键程序 |
| `create_*.sql` | 三张数据库表的建表脚本 |
| `requirements.txt` | Python 依赖 |
| `.gitignore` | 忽略虚拟环境和运行产物 |
| `prepare_forecast_data.py` | V4 样本构造、模型学习、训练和评价记录 |
| `forecast_model.py` | Transformer 预测模型结构 |
| `forecast_inference.py` | 模型加载与预测函数 |
| `run_analysis_forecast.py` | 串联单日分析与下一时间步预测 |
| `transformer_best_1795590008985786000.pt` | 当前选定的 Transformer 模型参数 |

学习与演示文件包括 `check_quality_demo.py`、`check_mysql_connection.py`、`save_daily_summary.py` 和 `demo_upsert_rollback.py`。其中 `save_daily_summary.py` 只保存日汇总，不作为三表完整保存流程的日常入口。

## 后续计划

- 持续完善负荷预测的数据输入和模型评价；
- 结合配电网开展潮流分析；
- 在明确设备和约束后探索储能优化调度。