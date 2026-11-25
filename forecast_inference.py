# 加载模型，作为以后预测功能的入口
from pathlib import Path

import torch

from forecast_model import LoadForecastTransformer
import pandas as pd


def load_forecast_model(checkpoint_path):
    """加载已保存的 Transformer 模型和 checkpoint 信息。"""

    checkpoint = torch.load(
        checkpoint_path,
        map_location="cpu",
        weights_only=True
    )

    model = LoadForecastTransformer(
        history_steps=checkpoint["history_steps"],
        d_model=checkpoint["d_model"]
    )

    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    return model, checkpoint

def predict_next_load(model, history_values):
    """使用历史总负荷预测下一时间步的总负荷。"""

    # 从模型的位置编码组件中取得要求的历史时间步数量
    expected_steps = model.position_embedding.num_embeddings

    if len(history_values) != expected_steps:
        raise ValueError(
            f"模型需要 {expected_steps} 条历史负荷，"
            f"实际收到 {len(history_values)} 条"
        )

    # 一条样本、expected_steps 个时间步、每步一个负荷值
    input_tensor = torch.tensor(
        history_values,
        dtype=torch.float32
    ).reshape(1, expected_steps, 1)

    model.eval()

    with torch.no_grad():
        prediction = model(input_tensor)

    return prediction.item()

# 添加预测流程函数

def forecast_from_history(model, checkpoint, load_data):
    """根据历史总负荷表，返回下一时间步的预测结果。"""

    # 按数据原有顺序取得最后一段历史
    history = load_data.tail(checkpoint["history_steps"]).copy()

    # 检查历史数据与模型场景是否一致
    if not history["scenario_id"].eq(checkpoint["scenario_id"]).all():
        raise ValueError("历史数据场景与模型场景不一致")

    # 检查负荷值是否缺失
    if history["p_mw"].isna().any():
        raise ValueError("历史总负荷存在缺失值，无法预测")

    # 检查窗口内的时间标记
    history["time"] = pd.to_datetime(history["time"])
    time_intervals = history["time"].diff().iloc[1:]

    if not time_intervals.eq(pd.Timedelta(minutes=15)).all():
        raise ValueError("历史时间标记不连续，无法构造 15 分钟预测输入")

    # 调用已经写好的 Transformer 预测函数
    transformer_prediction = predict_next_load(
        model,
        history["p_mw"].to_numpy()
    )

    # 最新负荷也作为简单基线的预测值
    latest_load = float(history["p_mw"].iloc[-1])

    return {
        "scenario_id": checkpoint["scenario_id"],
        "history_count": len(history),
        "history_start": history["time"].iloc[0],
        "history_end": history["time"].iloc[-1],
        "horizon_minutes": 15,
        "latest_load_mw": latest_load,
        "baseline_prediction_mw": latest_load,
        "transformer_prediction_mw": transformer_prediction,
    }

def main():
    # 指定之前保存的第 2 轮模型
    checkpoint_path = Path(__file__).resolve().parent / (
        "transformer_best_1795590008985786000.pt"
    )

    model, checkpoint = load_forecast_model(checkpoint_path)

    print("模型加载成功")
    print("模型场景：", checkpoint["scenario_id"])
    print("保存轮次：", checkpoint["epoch"])
    print(
        f"保存时的验证 MAE："
        f"{checkpoint['validation_mae_mw']:.4f} MW"
    )

        # 读取 V3 生成的单日总负荷文件
    history_path = Path(__file__).resolve().parent / "daily_total_load.csv"
    daily_data = pd.read_csv(history_path)

        # 调用预测流程函数
    result = forecast_from_history(model, checkpoint, daily_data)

    # 当前示例按时间标记向后推 15 分钟
    expected_time = result["history_end"] + pd.Timedelta(
        minutes=result["horizon_minutes"]
    )

    print("\n历史数据文件：", history_path)
    print("预测场景：", result["scenario_id"])
    print("历史记录数量：", result["history_count"])
    print("历史开始时间：", result["history_start"])
    print("历史结束时间：", result["history_end"])
    print("预计预测时间标记：", expected_time)

    print(f"最新实际负荷：{result['latest_load_mw']:.4f} MW")
    print(f"简单基线预测：{result['baseline_prediction_mw']:.4f} MW")
    print(f"Transformer 预测：{result['transformer_prediction_mw']:.4f} MW")

# 至此，V4的预测和V3接轨；能够利用V3的输出数据，结合我们训练的模型，进行下一步的预测
# 上述是将预测流程进行封装
if __name__ == "__main__":
    main()