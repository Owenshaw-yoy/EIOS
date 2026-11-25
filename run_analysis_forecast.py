# 新建一个整合函数
# 输入历史日期，例如 2016-01-05
#              ↓
# 运行已有的 run_all.py
#              ↓
# 准备数据、分析负荷、生成 daily_total_load.csv
#              ↓
# 读取总负荷，调用 V4 预测函数
#              ↓
# 输出简单基线和 Transformer 的预测结果

from pathlib import Path
import subprocess
import sys

import pandas as pd

from forecast_inference import load_forecast_model, forecast_from_history


def main():
    # 运行时需要输入一个历史日期
    if len(sys.argv) != 2:
        print("用法：python run_analysis_forecast.py YYYY-MM-DD")
        sys.exit(1)

    history_date = sys.argv[1].strip()
    project_dir = Path(__file__).resolve().parent

    # 先加载已训练好的模型
    checkpoint_path = project_dir / (
        "transformer_best_1795590008985786000.pt"
    )

    model, checkpoint = load_forecast_model(checkpoint_path)

    print("模型加载完成", flush=True)

    # 调用现有的单日数据准备和分析流程
    print(f"\n第一步：分析 {history_date} 的历史负荷", flush=True)

    subprocess.run(
        [
            sys.executable,
            str(project_dir / "run_all.py"), # 整合之前的run_all.py
            history_date
        ],
        cwd=project_dir,
        check=True
    )

    # 读取上一步生成的总负荷文件
    print("\n第二步：根据历史总负荷进行预测", flush=True)

    history_path = project_dir / "daily_total_load.csv"
    daily_data = pd.read_csv(history_path)

    result = forecast_from_history(model, checkpoint, daily_data)

    # 当前示例按时间标记向后推 15 分钟
    expected_time = result["history_end"] + pd.Timedelta(
        minutes=result["horizon_minutes"]
    )

    print("\n--- 负荷预测结果 ---")
    print("场景：", result["scenario_id"])
    print("历史记录数量：", result["history_count"])
    print("历史结束时间：", result["history_end"])
    print("预计预测时间标记：", expected_time)

    print(f"最新实际负荷：{result['latest_load_mw']:.4f} MW")
    print(f"简单基线预测：{result['baseline_prediction_mw']:.4f} MW")
    print(f"Transformer 预测：{result['transformer_prediction_mw']:.4f} MW")


if __name__ == "__main__":
    main()
   
   
    # run_analysis_forecast.py
    #     │
    #     ├─ 1. 加载保存好的 Transformer 模型
    #     │
    #     ├─ 2. 调用 run_all.py，分析 2016-01-05
    #     │       ├─ main.py：准备当天的负荷数据
    #     │       └─ inspect_data.py：检查数据、统计和告警，
    #     │                           生成总负荷 CSV 等结果
    #     │
    #     └─ 3. 读取 daily_total_load.csv
    #             └─ 调用 forecast_from_history()
    #                    ├─ 计算简单基线预测
    #                    └─ 计算 Transformer 预测