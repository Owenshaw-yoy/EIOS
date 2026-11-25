# 进行V4的结构化处理，不能让他在一个prepare.py文件里面
# 定义 Transformer 模型结构
import torch
class LoadForecastTransformer(torch.nn.Module):

    def __init__(self, history_steps, d_model):
        # 初始化 PyTorch 模型的父类
        super().__init__()

        # 每个时间步：1 个负荷值 → d_model 维表示
        self.input_projection = torch.nn.Linear(1, d_model)

        # 为每个序列位置创建一个位置向量
        self.position_embedding = torch.nn.Embedding(
            history_steps,
            d_model
        )

        # 创建一个 Transformer 编码器层
        self.encoder = torch.nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=4,
            dim_feedforward=64,
            dropout=0.0,
            activation="relu",
            batch_first=True
        )

        # 把最新时间步的 d_model 维表示转换成 1 个预测值
        self.output_layer = torch.nn.Linear(d_model, 1)

    def forward(self, x):
        # x 的形状：[样本数, 96, 1]
        x = self.input_projection(x)

        # 生成位置编号，并取出位置向量
        positions = torch.arange(x.shape[1], device=x.device)
        position_vectors = self.position_embedding(positions).unsqueeze(0)

        # 负荷表示和位置表示相加
        x = x + position_vectors

        # 经过 Transformer 编码器层
        x = self.encoder(x)

        # 取每条样本中最新时间步的输出表示
        latest_output = x[:, -1, :]

        # 得到下一个时间步的负荷预测
        prediction = self.output_layer(latest_output)

        return prediction