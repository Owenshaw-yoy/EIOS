# V4：准备预测数据：得到每个时间步的总负荷，为后续制作预测样本做准备。
# 这个之前做过，这里是V4专用的

import simbench as sb
import pandas as pd
import torch # 引入torch库
# 引入数据加载库
from torch.utils.data import TensorDataset, DataLoader
import time
from pathlib import Path # 处理文件路径的工具

# 使用与 V1—V3 相同的场景
scenario_id = "1-MV-comm--0-sw"
net = sb.get_simbench_net(scenario_id)

# 取得各负荷在各时间步的绝对有功功率，单位为 MW
load_p = sb.get_absolute_profiles_from_relative_profiles(
    net, "load", "p_mw"
)

# 检查原始功率数据中是否存在缺失值
missing_count = load_p.isna().sum().sum()
# load_p.isna()：检查表格中哪些位置是缺失值
# 第一个 .sum()：分别统计每一列有多少个缺失值
# 第二个 .sum()：把各列的数量加起来，得到整张表的缺失值数量

if missing_count > 0:
    raise ValueError(f"负荷功率存在 {missing_count} 个缺失值，暂时不能汇总")

# 将每个时间步的各个负荷相加，得到总负荷
total_load = load_p.sum(axis=1)

print("各负荷功率表的形状：", load_p.shape)
print("总负荷的时间步数量：", len(total_load))
print("前 5 个时间步的总负荷（MW）：")
print(total_load.head())
# 得到2016年全年所有时间步对应下的总负荷

# 下一步：看看这些负荷值对应的原始时间
# 取得各时间步对应的原始时间
time_column = net.profiles["load"]["time"]

print("\n前 5 个时间标记：")
print(time_column.head())

print(
    "时间与总负荷的行索引是否一致：",
    time_column.index.equals(total_load.index)
)

# 下一步：整理为表
# 将场景、时间和总负荷整理成一张表
forecast_data = pd.DataFrame({
    "scenario_id": scenario_id,
    "time": pd.to_datetime(time_column, format="%d.%m.%Y %H:%M"),
    "p_mw": total_load,
})

print("\n总负荷数据前 5 行：")
print(forecast_data.head())

# 开始把这张表整理为一个预测样本
# 为每个当前时间点，找到下一个时间点的实际负荷，作为目标值

# 原数据单纯以15min排序错误，存在时区切换，只采用15min计时法会报错 
# 这里只采用以15min分段的样本 
# 按时间先后排列整张表，并重新整理行索引
# forecast_data = forecast_data.sort_values("time").reset_index(drop=True)

# 检查相邻时间点之间是否都是 15 分钟
# time_intervals = forecast_data["time"].diff().iloc[1:]
# diff()：计算时间差，.iloc[1:]代表从第二行开始取

# if (time_intervals != pd.Timedelta(minutes=15)).any():
#     raise ValueError("时间间隔存在异常，无法按 15 分钟构造预测样本")

# 将下一时间点的时间和负荷作为预测目标
forecast_data["target_time"] = forecast_data["time"].shift(-1)
forecast_data["target_p_mw"] = forecast_data["p_mw"].shift(-1)
# .shift(-1) 把下一行的值放到当前行

# 计算当前记录与下一条记录的时间标记之差
target_intervals = forecast_data["target_time"] - forecast_data["time"]

# 只选择时间标记相差 15 分钟的样本对
valid_pair = target_intervals == pd.Timedelta(minutes=15)

sample_pairs = forecast_data.loc[valid_pair].copy()

print("\n符合 15 分钟间隔的样本对数量：", len(sample_pairs))

print(
    sample_pairs[["time", "p_mw", "target_time", "target_p_mw"]].head()
)

# 下一步，加入前一个时间点的负荷值：
# 形成：前一个时间点的负荷 + 当前时间点的负荷 → 下一时间点的负荷
# 从原始顺序的表中，取得前一个时间点和它的负荷
forecast_data["previous_time"] = forecast_data["time"].shift(1)
forecast_data["previous_p_mw"] = forecast_data["p_mw"].shift(1)

# 判断前一个时间标记到当前时间标记是否相差 15 分钟
previous_intervals = forecast_data["time"] - forecast_data["previous_time"]
valid_previous = previous_intervals == pd.Timedelta(minutes=15)

# 前一个到当前、当前到目标，都要符合 15 分钟间隔
valid_sample = valid_previous & valid_pair

# 筛选出可以用于当前预测任务的样本
samples = forecast_data.loc[valid_sample].copy()

print("\n可用的双输入样本数量：", len(samples))

display_columns = [
    "previous_time", "previous_p_mw",
    "time", "p_mw",
    "target_time", "target_p_mw",
]

print(samples[display_columns].head(3).to_string(index=False))

# 下一步：从 samples 中分别取出输入和目标
# 输入特征：前一个时间和当前时间步的负荷，目标：下一个时间步的实际负荷
# 上述总体构成样本，后续会把上面的样本划分为训练集和验证集

# 取出两个输入特征
X = samples[["previous_p_mw", "p_mw"]]

# 取出需要预测的目标值
y = samples["target_p_mw"]

print("\n全部样本的输入形状：", X.shape)
print("全部样本的目标形状：", y.shape)

print("\n第一个样本的输入：")
print(X.iloc[0])

print("\n第一个样本的目标：")
print(y.iloc[0])

# 按时间划分样本
# 训练集：用来训练模型；
# 验证集：开发过程中比较模型或调整参数；
# 测试集：等模型选定后，再用来评估它在后续数据上的表现。
# 设置验证集和测试集的开始时间
validation_start = pd.Timestamp("2016-10-01")
test_start = pd.Timestamp("2016-12-01")

# 训练集：目标时间早于 2016 年 10 月 1 日
train_samples = samples.loc[
    samples["target_time"] < validation_start
].copy()

# 验证集：目标时间从 10 月 1 日开始，早于 12 月 1 日
validation_samples = samples.loc[
    (samples["target_time"] >= validation_start)
    & (samples["target_time"] < test_start)
].copy()

# 测试集：目标时间从 12 月 1 日开始
test_samples = samples.loc[
    samples["target_time"] >= test_start
].copy()

print("\n训练集样本数量：", len(train_samples))
print("验证集样本数量：", len(validation_samples))
print("测试集样本数量：", len(test_samples))

# 下一步，从这三部分取出模型需要的x和y
# 模型使用的两个输入列
feature_columns = ["previous_p_mw", "p_mw"]

# 从训练集中取出输入和目标
X_train = train_samples[feature_columns]
y_train = train_samples["target_p_mw"]

# 从验证集中取出输入和目标
X_validation = validation_samples[feature_columns]
y_validation = validation_samples["target_p_mw"]

# 从测试集中取出输入和目标
X_test = test_samples[feature_columns]
y_test = test_samples["target_p_mw"]

print("\n训练集：X", X_train.shape, "，y", y_train.shape)
print("验证集：X", X_validation.shape, "，y", y_validation.shape)
print("测试集：X", X_test.shape, "，y", y_test.shape)

# 下一步
# 简单基线：预测下一时刻负荷等于当前负荷
baseline_prediction = X_validation["p_mw"]

# 预测值与验证集实际目标值的绝对误差
baseline_errors = (baseline_prediction - y_validation).abs()
# .abs()：把每次预测与实际值的差转为绝对值

# 对所有验证样本的绝对误差求平均
baseline_mae = baseline_errors.mean()

# MAE：平均绝对误差
print(f"\n基线预测的验证集 MAE：{baseline_mae:.4f} MW")

# 下一步，将我们准备好的训练数据交给pytorch

# PyTorch 张量（Tensor）：可以理解成一种用来保存和计算数字的数据结构
# 它和你熟悉的 Python 列表、pandas 表格有相似之处，
# 但它还可以配合 PyTorch 的自动求导和模型训练功能使用。
# 张量的作用：1.组织模型的输入、输出和参数
#           2.方便对大量数字一起计算
#           3.配合自动求导进行训练

# 张量的维数：我们组织信息的方向，维数越多，说明这个数据从不同角度包含的信息越多
# 例如，张量(26296, 2)是二维的，表示1.我们的输入数据有26296个。2.每个输入数据有两个时间步
# shape（形状）为“每个方向分别有多大”，
# 而维度就是“有几个这样的方向”。
# 具体每个方向代表样本、时间还是特征，由我们组织数据的方式来决定。

# 将训练集的输入转换为 PyTorch 张量
X_train_tensor = torch.tensor(
    X_train.to_numpy(),
    dtype=torch.float32
)
# torch.float32 是一种浮点数类型

# 将训练集的目标值转换为 PyTorch 张量
y_train_tensor = torch.tensor(
    y_train.to_numpy(),
    dtype=torch.float32
).reshape(-1, 1)

print("\n训练输入张量的形状：", X_train_tensor.shape)
print("训练目标张量的形状：", y_train_tensor.shape)

print("第一条训练输入：", X_train_tensor[0])
print("第一条训练目标：", y_train_tensor[0])

# 下一步，创建第一个模型，让他接受两个负荷值，给出一个预测值

# 先从简单的线性模型开始：
# 预测负荷 = w1 × 前一个负荷 + w2 × 当前负荷 + b
# w1，w2叫权重，b叫偏执，他们都是模型的参数
# 先固定一个种子方便复现
torch.manual_seed(42)
model = torch.nn.Linear(2, 1)
# 创建一个线性模型：输入 2 个值，输出 1 个值
# model = torch.nn.Linear(2, 1)
# torch.nn 中包含构建神经网络时可以使用的组件，`Linear` 是其中的线性层
# 括号里的1，2分别表示：2 个输入值 → 线性层 → 1 个输出值

# 查看模型结构和初始参数
print("\n模型结构：", model)
print("初始权重：", model.weight)
print("初始偏置：", model.bias)

# 取出第一条训练样本
first_input = X_train_tensor[0:1] # 先把第一个样本给模型看
first_target = y_train_tensor[0:1]

# 让模型根据输入计算预测值
first_prediction = model(first_input)

print("\n第一条输入：", first_input)
print("模型的初始预测：", first_prediction)
print("对应的实际目标：", first_target)

# 此时模型还没有开始学习，准确性很差
# 接下来我们需要告诉模型有好差，并将其转换为他能够使用的信息
# 下一步，计算损失和梯度
# 创建均方误差损失函数
loss_function = torch.nn.MSELoss()

# 计算第一条训练样本的损失
loss = loss_function(first_prediction, first_target)
print("\n第一条样本的平方损失：", loss.item())

# 反向传播：计算模型参数对应的梯度
loss.backward()
# 梯度的意义：告诉模型在当前参数附近，改变每个参数会让损失怎样变化

print("权重的梯度：", model.weight.grad)
print("偏置的梯度：", model.bias.grad)

# 下一步，完成一次参数更新
# 新权重 = 原权重 - 学习率 × 梯度
# 创建优化器，让它管理模型参数
optimizer = torch.optim.SGD(model.parameters(), lr=0.001)

# 根据刚才算出的梯度，更新一次参数
optimizer.step()

print("\n更新后的权重：", model.weight)
print("更新后的偏置：", model.bias)

# 用更新后的模型再次计算这条样本
updated_prediction = model(first_input)
print("更新后的预测：", updated_prediction)

# 目前已经打通了一次训练和修正更新，下面进入全部训练集的训练

# 使用整个训练集训练模型
epochs = 10000 # 使用完整训练集重复学习10000轮

for epoch in range(epochs):
    # 清除上一次计算留下的梯度
    optimizer.zero_grad()

    # 正向传播：计算整个训练集的预测值
    train_predictions = model(X_train_tensor)

    # 计算整个训练集的平均平方损失
    train_loss = loss_function(train_predictions, y_train_tensor)

    # 反向传播：计算各参数的梯度
    train_loss.backward()

    # 根据梯度更新权重和偏置
    optimizer.step()

    # 每 100 轮输出一次损失
    if (epoch + 1) % 500 == 0:
        print(
            f"第 {epoch + 1} 轮，"
            f"本轮更新前的训练 MSE：{train_loss.item():.4f} MW²"
        )

print("\n训练后的权重：", model.weight)
print("训练后的偏置：", model.bias)

# 训练完后，在验证集上与基线比较，看看结果如何
# 把验证集的输入和目标转换为张量
X_validation_tensor = torch.tensor(
    X_validation.to_numpy(),
    dtype=torch.float32
)

y_validation_tensor = torch.tensor(
    y_validation.to_numpy(),
    dtype=torch.float32
).reshape(-1, 1)

# 使用训练好的模型进行验证
model.eval() # 切换到评估模式

with torch.no_grad():
    validation_predictions = model(X_validation_tensor)

    validation_mae = (
        validation_predictions - y_validation_tensor
    ).abs().mean()

print(f"\n线性模型的验证集 MAE：{validation_mae.item():.4f} MW")
print(f"简单基线的验证集 MAE：{baseline_mae:.4f} MW")

# 即使训练轮次为10000轮样本，值仍然压不过基线
# 接下来改用非线性神经网络

# 增加ReLU的激活函数
# 2 个输入 → 8 个中间值 → ReLU → 1 个预测值

# 为新模型的随机初始化设置种子
torch.manual_seed(42)

# 创建一个小型非线性神经网络
mlp_model = torch.nn.Sequential(
    torch.nn.Linear(2, 8), # 把每个样本的输入转换为8个中间值
    torch.nn.ReLU(), # 对这些中间值进行非线性处理
    torch.nn.Linear(8, 1) # 根据8个中间值计算一个负荷预测值 
)

# 为新模型创建自己的优化器
mlp_optimizer = torch.optim.SGD(
    mlp_model.parameters(),
    lr=0.001
)

# 使用训练集训练
mlp_epochs = 2000

for epoch in range(mlp_epochs):
    mlp_optimizer.zero_grad()

    mlp_predictions = mlp_model(X_train_tensor)
    mlp_loss = loss_function(mlp_predictions, y_train_tensor)

    mlp_loss.backward()
    mlp_optimizer.step()

    if (epoch + 1) % 500 == 0:
        print(
            f"神经网络第 {epoch + 1} 轮，"
            f"更新前训练 MSE：{mlp_loss.item():.4f} MW²"
        )

# 在与线性模型相同的验证集上计算 MAE
mlp_model.eval()

with torch.no_grad():
    mlp_validation_predictions = mlp_model(X_validation_tensor)

    mlp_validation_mae = (
        mlp_validation_predictions - y_validation_tensor
    ).abs().mean()

print(f"\n神经网络的验证集 MAE：{mlp_validation_mae.item():.4f} MW")
print(f"简单基线的验证集 MAE：{baseline_mae:.4f} MW")

# 开始准备 Transformer 使用的较长历史序列
# 一条序列样本使用 96 个历史时间步
history_steps = 96

# 取原始顺序中的前 96 个负荷值
history_values = forecast_data["p_mw"].iloc[:history_steps].to_numpy()

# 整理为：1 条样本、96 个时间步、每个时间步 1 个负荷值
sequence_example = torch.tensor(
    history_values,
    dtype=torch.float32
).reshape(1, history_steps, 1)
# 张量维度上升为3，1个样本，96个时间步，每个时间步有1个负荷值

# 第 96 个下标对应接下来要预测的实际负荷
sequence_target = forecast_data["p_mw"].iloc[history_steps]

print("\n序列输入的形状：", sequence_example.shape)
print("输入的起始时间：", forecast_data["time"].iloc[0])
print("输入的最后时间：", forecast_data["time"].iloc[history_steps - 1])
print("目标时间：", forecast_data["time"].iloc[history_steps])
print("目标实际负荷：", sequence_target)

# 当前只是取出了第一条长序列样本
# 我们计划让一个模型接收一条包含 96 个历史负荷值的序列，然后预测下一个负荷值
# 之前只给模型两个值，它能看到的历史很短。
# 给它更长的历史，是希望它有机会参考更多变化过程

# 将全年总负荷转为一维张量，方便后面按位置切片
power_values = torch.tensor(
    forecast_data["p_mw"].to_numpy(),
    dtype=torch.float32
)
# 需要先检查96个样本之间的间隔，当间隔不是15分钟时，说明样本有问题，需要调整

# 判断每一行的时间标记与前一行是否相差 15 分钟
regular_intervals = (
    forecast_data["time"].diff() == pd.Timedelta(minutes=15)
)
# 需要检查滑动窗口在时间轴上的连续性
# 分别保存每条样本的输入、目标和目标所在的原始行位置
sequence_inputs = []
sequence_targets = []
sequence_target_positions = []

# target_position 表示当前样本目标值所在的行位置
for target_position in range(history_steps, len(forecast_data)):

    # 检查从第一个输入到目标之间的 96 个相邻时间间隔
    first_interval_position = target_position - history_steps + 1

    window_is_regular = regular_intervals.iloc[
        first_interval_position : target_position + 1
    ].all()

    # 只跳过时间标记不连续的样本
    if not window_is_regular:
        continue

    # 取目标之前的 96 个负荷值作为输入
    sequence_inputs.append(
        power_values[target_position - history_steps : target_position]
    )

    # 取目标位置上的实际负荷作为目标值
    sequence_targets.append(power_values[target_position])

    # 记录目标对应原始数据中的行位置
    sequence_target_positions.append(target_position)

# 将多条样本组合成张量
X_sequences = torch.stack(sequence_inputs).reshape(-1, history_steps, 1)
y_sequences = torch.stack(sequence_targets).reshape(-1, 1)

print("\n可用的 96 步样本数量：", len(sequence_targets))
print("序列输入张量的形状：", X_sequences.shape)
print("序列目标张量的形状：", y_sequences.shape)
print("前两个样本的目标行位置：", sequence_target_positions[:2])

print(
    "第一个样本的目标时间：",
    forecast_data["time"].iloc[sequence_target_positions[0]]
)
print("第一个样本的目标负荷：", y_sequences[0])
# 至此，全年数据整理成了可用的长序列样

# 现在在96时序样本上构造数据集，并重新设置基线，确保我们比较的模型使用的样本
# 是在同一个数据集上跑出来的

# 根据之前保存的原始行位置，找到每条序列样本的目标时间
sequence_target_times = forecast_data["time"].iloc[
    sequence_target_positions
].reset_index(drop=True)

# 根据目标时间，制作训练集、验证集和测试集的筛选条件
sequence_train_mask = torch.tensor(
    (sequence_target_times < validation_start).to_numpy(),
    dtype=torch.bool
)
# mask：掩码，用于筛选True和False
sequence_validation_mask = torch.tensor(
    (
        (sequence_target_times >= validation_start)
        & (sequence_target_times < test_start)
    ).to_numpy(),
    dtype=torch.bool
)

sequence_test_mask = torch.tensor(
    (sequence_target_times >= test_start).to_numpy(),
    dtype=torch.bool
)

# 使用相同的筛选条件，分别选出输入和对应目标
X_sequence_train = X_sequences[sequence_train_mask]
y_sequence_train = y_sequences[sequence_train_mask]

X_sequence_validation = X_sequences[sequence_validation_mask]
y_sequence_validation = y_sequences[sequence_validation_mask]

X_sequence_test = X_sequences[sequence_test_mask]
y_sequence_test = y_sequences[sequence_test_mask]

print("\n96 步训练集：X", X_sequence_train.shape, "，y", y_sequence_train.shape)
print("96 步验证集：X", X_sequence_validation.shape, "，y", y_sequence_validation.shape)
print("96 步测试集：X", X_sequence_test.shape, "，y", y_sequence_test.shape)

# 简单基线：取每条序列中最新的负荷值，作为下一时刻的预测
sequence_baseline_predictions = X_sequence_validation[:, -1, :]

# 在这批 96 步验证样本上计算基线 MAE
sequence_baseline_mae = (
    sequence_baseline_predictions - y_sequence_validation
).abs().mean()

print(f"\n96 步验证样本的基线 MAE：{sequence_baseline_mae.item():.4f} MW")

# 现在样本和简单基线已经构建出来了，下面开始构建简单投影
# 原始输入：       [1, 96, 1]
#                     ↓
#                 输入投影层  # 16维内部表示
#                     ↓
# 转换后的表示：   [1, 96, 16]

# 固定随机种子，方便观察相同初始化下的结果
torch.manual_seed(42)

# 设置模型内部表示的维度
d_model = 16

# 输入投影层：每个时间步的 1 个负荷值 → 16 个数字
input_projection = torch.nn.Linear(1, d_model)

# 从训练集中取出第一条完整的序列样本
example_train_sequence = X_sequence_train[0:1]

# 先观察投影效果，这一步暂时不训练
with torch.no_grad():
    example_projected_sequence = input_projection(example_train_sequence)

print("\n输入投影层：", input_projection)
print("投影前的形状：", example_train_sequence.shape)
print("投影后的形状：", example_projected_sequence.shape)

print(
    "第一个时间步的原始负荷：",
    example_train_sequence[0, 0, 0].item()
)
print(
    "这个时间步投影后的前 4 个数字：",
    example_projected_sequence[0, 0, :4]
)
# 下一步，将这些投影和负荷进行位置编码：
# 问题：同样的负荷值如果出现在序列的不同位置，当前投影层会给出相同的表示，
# 因为它使用的是同一套参数。那么模型怎么区分“较早的值”和“最新的值”？

# 创建位置编号：0、1、2，……、95
positions = torch.arange(history_steps)

# 创建一张位置编码表：96 个位置，每个位置用 16 个数字表示
position_embedding = torch.nn.Embedding(history_steps, d_model)

# 暂时只观察结果，不进行训练
with torch.no_grad():
    # 根据位置编号，取出对应的位置向量
    position_vectors = position_embedding(positions)

    # 增加样本这一维，方便和一条投影后的序列对应相加
    position_vectors_for_batch = position_vectors.reshape(
        1, history_steps, d_model
    )

    # 负荷表示 + 位置表示
    example_with_position = (
        example_projected_sequence + position_vectors_for_batch
    )

print("\n前 5 个位置编号：", positions[:5])
print("位置编码表的形状：", position_embedding.weight.shape)
print("取出的位置向量形状：", position_vectors.shape)
print("加入位置信息后的形状：", example_with_position.shape)

print("\n位置 0 的位置向量前 4 个数字：", position_vectors[0, :4])
print("位置 0 加入位置前的前 4 个数字：", example_projected_sequence[0, 0, :4])
print("位置 0 加入位置后的前 4 个数字：", example_with_position[0, 0, :4])

# 下一步：模型的自注意力机制
# Q：Query查询，当前这个位置用什么表示去和其他位置比较
# K：Key键，每个位置用什么表示来参与比较
# V：Value值，每个位置提供什么内容，供后面加权组合
# 位置 95 的 Q，与所有位置的 K 计算匹配分数
#                          ↓
#           将分数转换成一组注意力权重
#                          ↓
#               用权重组合各位置的 V
#                          ↓
#             得到位置 95 的新表示
# 为注意力组件的初始化固定随机种子
torch.manual_seed(42)

# 创建注意力层
attention_layer = torch.nn.MultiheadAttention(
    embed_dim=d_model,  # 每个时间步的表示有 16 个数字
    num_heads=1,        # 暂时使用一个注意力头，方便学习
    dropout=0.0,
    batch_first=True    # 输入形状按“样本数、时间步、特征数”排列
)

# 切换到评估模式，先观察一次计算
attention_layer.eval()

with torch.no_grad():
    attention_output, attention_weights = attention_layer(
        example_with_position,  # Query 的输入
        example_with_position,  # Key 的输入
        example_with_position,  # Value 的输入
        need_weights=True
    )

print("\n注意力输出的形状：", attention_output.shape)
print("注意力权重的形状：", attention_weights.shape)

print(
    "最新时间步对前 5 个时间步的注意力权重：",
    attention_weights[0, -1, :5]
)

print(
    "最新时间步对自己的注意力权重：",
    attention_weights[0, -1, -1].item()
)

print(
    "最新时间步对全部时间步的权重之和：",
    attention_weights[0, -1, :].sum().item()
)
# 目前只设计了一头注意力头，只计算一组注意力权重
# 如果涉及四个注意力头，就可以设计4套权重
# 这样设计是希望模型有机会从不同的表示角度学习历史时间步之间的关系

# 固定随机种子，方便重复观察
torch.manual_seed(42)

# 创建一个四头注意力层
multihead_attention = torch.nn.MultiheadAttention(
    embed_dim=d_model,
    num_heads=4,
    dropout=0.0,
    batch_first=True
)

multihead_attention.eval()

with torch.no_grad():
    multihead_output, multihead_weights = multihead_attention(
        example_with_position,
        example_with_position,
        example_with_position,
        need_weights=True,
        average_attn_weights=False
    )

print("\n四头注意力输出的形状：", multihead_output.shape)
print("四头注意力权重的形状：", multihead_weights.shape)

print("\n四个头：最新时间步对前 5 个时间步的注意力权重：")
print(multihead_weights[0, :, -1, :5])

print(
    "\n四个头：最新时间步对全部时间步的权重之和：",
    multihead_weights[0, :, -1, :].sum(dim=-1)
)

# 现在我们终于要结合上述，开始构建我们的第一个transformer模型
# 输入：[样本数, 96, 1]
#        96 个历史负荷值
#           ↓
#        输入投影层
#           ↓
#       加入位置编码
#           ↓
#     Transformer 编码器层
#       ├─ 四头自注意力
#       ├─ 前馈神经网络
#       ├─ 残差连接
#       └─ 层归一化
#           ↓
#   取最新时间步的输出表示
#           ↓
#       线性输出层
#           ↓
#   输出：[样本数, 1]
#  下一个时间步的负荷预测值

# 定义一个用于负荷预测的小型 Transformer 模型
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


# 创建一个新的模型实例
torch.manual_seed(42)

transformer_model = LoadForecastTransformer(
    history_steps=history_steps,
    d_model=d_model
)

# 先用一条训练样本观察前向计算
transformer_model.eval()

with torch.no_grad():
    transformer_initial_prediction = transformer_model(
        X_sequence_train[0:1]
    )

print("\nTransformer 初始预测的形状：", transformer_initial_prediction.shape)
print("Transformer 的初始预测：", transformer_initial_prediction)
print("对应的实际目标：", y_sequence_train[0:1])

# 这个模型很大，我们需要分批次训练，设置1批64条，共407批

# 设置每批最多使用多少条样本
batch_size = 64

# 将训练输入和目标组织成数据集
transformer_train_dataset = TensorDataset(
    X_sequence_train,
    y_sequence_train
)

# 将验证输入和目标组织成数据集
transformer_validation_dataset = TensorDataset(
    X_sequence_validation,
    y_sequence_validation
)

# 固定训练样本打乱顺序时使用的随机种子
torch.manual_seed(42)

# 分批读取训练集
transformer_train_loader = DataLoader(
    transformer_train_dataset,
    batch_size=batch_size,
    shuffle=True
)

# 分批读取验证集
transformer_validation_loader = DataLoader(
    transformer_validation_dataset,
    batch_size=batch_size,
    shuffle=False
)

# 创建 Transformer 自己的优化器
transformer_optimizer = torch.optim.Adam(
    transformer_model.parameters(),
    lr=0.001
)

# 记录本次训练中最低的验证 MAE 和对应轮次
best_validation_mae = float("inf") # float("inf")表示正无穷大
best_epoch = 0

# 使用时间数字区分不同次运行生成的模型文件
checkpoint_path = Path(__file__).resolve().parent / (
    f"transformer_best_{time.time_ns()}.pt"
)
# 先观察 3 轮的训练和验证结果
transformer_epochs = 0

for epoch in range(transformer_epochs):
    epoch_start = time.perf_counter()

    # 切换到训练模式
    transformer_model.train()

    # 用于累计本轮训练过程中各批次的损失
    total_training_loss = 0.0

    # 完整遍历一遍训练集，也就是训练 1 轮
    for batch_number, (batch_inputs, batch_targets) in enumerate(
        transformer_train_loader,
        start=1
    ):
        # 清除上一次更新留下的梯度
        transformer_optimizer.zero_grad()

        # 正向传播：得到当前批次的预测
        batch_predictions = transformer_model(batch_inputs)

        # 复用前面已经定义好的 MSE 损失函数
        batch_loss = loss_function(batch_predictions, batch_targets)

        # 反向传播并更新模型参数
        batch_loss.backward()
        transformer_optimizer.step()

        # 按批次实际样本数量累计损失
        total_training_loss += batch_loss.item() * len(batch_inputs)

        # 输出部分批次的进度
        if (
            batch_number == 1
            or batch_number % 100 == 0
            or batch_number == len(transformer_train_loader)
        ):
            print(
                f"第 {epoch + 1} 轮，训练批次 {batch_number}/{len(transformer_train_loader)}，"
                f"本批更新前 MSE：{batch_loss.item():.4f} MW²"
            )

    # 计算各批次训练损失按样本数加权后的平均值
    training_online_mse = total_training_loss / len(transformer_train_dataset)

    print(
        f"\n第 {epoch + 1} 轮训练过程中，各批更新前的平均 MSE："
        f"{training_online_mse:.4f} MW²"
    )

    # 切换到评估模式，在验证集上计算 MAE
    transformer_model.eval()
    total_validation_abs_error = 0.0

    with torch.no_grad():
        for validation_inputs, validation_targets in transformer_validation_loader:
            validation_predictions = transformer_model(validation_inputs)

            # 累加这一批所有样本的绝对误差
            batch_abs_errors = (
                validation_predictions - validation_targets
            ).abs()

            total_validation_abs_error += batch_abs_errors.sum().item()

    transformer_validation_mae = (
        total_validation_abs_error / len(transformer_validation_dataset)
    )

    print(f"Transformer 的验证集 MAE：{transformer_validation_mae:.4f} MW")
    print(f"同一批验证样本的基线 MAE：{sequence_baseline_mae.item():.4f} MW")
        # 如果当前轮次的验证 MAE 更低，就保存当前模型
    if transformer_validation_mae < best_validation_mae:
        best_validation_mae = transformer_validation_mae
        best_epoch = epoch + 1

        torch.save(
            {
                "model_state_dict": transformer_model.state_dict(),
                "epoch": best_epoch,
                "validation_mae_mw": best_validation_mae,
                "history_steps": history_steps,
                "d_model": d_model,
                "scenario_id": scenario_id,
            },
            checkpoint_path
        )

        print(
            f"已保存本次目前最佳模型："
            f"第 {best_epoch} 轮，验证 MAE {best_validation_mae:.4f} MW"
        )
    print(f"本轮训练和验证耗时：{time.perf_counter() - epoch_start:.1f} 秒")
if transformer_epochs > 0:
    print(f"\n本次训练的最佳轮次：第 {best_epoch} 轮")
    print(f"本次最低验证 MAE：{best_validation_mae:.4f} MW")
    print("模型文件位置：", checkpoint_path)

# 我们现在训练了3轮模型，发现第二轮的模型效果最好，所以我们需要保存模型最好时对应的参数
# 下一步：每轮验证后，如果这轮的验证 MAE 是本次训练中最低的，就把当前模型参数保存下来

# 我们现在已经保存了最优轮次的模型，接下来学习如何加在他
# 从文件加载第 2 轮保存的模型，再用同一批验证数据重新计算 MAE

# 指定之前保存的模型文件
saved_model_path = Path(__file__).resolve().parent / (
    "transformer_best_1795590008985786000.pt"
)

# 从文件读取 checkpoint
saved_checkpoint = torch.load( # 读取字典
    saved_model_path,
    map_location="cpu",
    weights_only=True
)

# 按保存时的设置，重新创建相同结构的模型
loaded_transformer = LoadForecastTransformer( # 将读取到的值加载到模型上
    history_steps=saved_checkpoint["history_steps"],
    d_model=saved_checkpoint["d_model"]
)

# 把文件中的参数加载到新模型
loaded_transformer.load_state_dict(
    saved_checkpoint["model_state_dict"]
)

# 整体的流程为：
# 读取文件
#    ↓
# 按相同结构创建模型
#    ↓
# 把保存的参数装入模型
#    ↓
# 使用模型做预测

# 切换到评估模式
loaded_transformer.eval()

print("\n加载的模型文件：", saved_model_path)
print("保存的场景：", saved_checkpoint["scenario_id"])
print("保存的轮次：", saved_checkpoint["epoch"])
print(
    f"文件中记录的验证 MAE："
    f"{saved_checkpoint['validation_mae_mw']:.4f} MW"
)
# 用加载后的模型重新计算验证集 MAE
loaded_total_abs_error = 0.0

with torch.no_grad():
    for validation_inputs, validation_targets in transformer_validation_loader:
        loaded_predictions = loaded_transformer(validation_inputs)

        loaded_abs_errors = (
            loaded_predictions - validation_targets
        ).abs()

        loaded_total_abs_error += loaded_abs_errors.sum().item()

loaded_validation_mae = (
    loaded_total_abs_error / len(transformer_validation_dataset)
)

print(f"\n加载后重新计算的验证 MAE：{loaded_validation_mae:.4f} MW")
print(f"同一批验证样本的基线 MAE：{sequence_baseline_mae.item():.4f} MW")

# 现在我们已经成功复现了保存的模型并验证
# 下一步：我们要把之前的线性模型和神经网络模型放在一起来比较

# 从同一批 96 步验证样本中，取出最后两个负荷值
two_step_validation_inputs = X_sequence_validation[:, -2:, 0]

# 切换之前的线性模型和神经网络到评估模式
model.eval()
mlp_model.eval()

with torch.no_grad():
    # 使用同一批目标样本对应的两个历史负荷值进行预测
    linear_same_predictions = model(two_step_validation_inputs)
    mlp_same_predictions = mlp_model(two_step_validation_inputs)

    # 与 96 步样本对应的同一批目标值比较
    linear_same_mae = (
        linear_same_predictions - y_sequence_validation
    ).abs().mean().item()

    mlp_same_mae = (
        mlp_same_predictions - y_sequence_validation
    ).abs().mean().item()

print("\n同一批验证样本的双输入形状：", two_step_validation_inputs.shape)
print(f"简单基线验证 MAE：{sequence_baseline_mae.item():.4f} MW")
print(f"线性模型验证 MAE：{linear_same_mae:.4f} MW")
print(f"神经网络验证 MAE：{mlp_same_mae:.4f} MW")
print(f"Transformer 验证 MAE：{loaded_validation_mae:.4f} MW")

# 下一步：使用测试集，即都没见过的时间段来评估模型差异
# 将测试集输入和目标组织成数据集
transformer_test_dataset = TensorDataset(
    X_sequence_test,
    y_sequence_test
)

# 分批读取测试集
transformer_test_loader = DataLoader(
    transformer_test_dataset,
    batch_size=batch_size,
    shuffle=False
)

# 使用加载好的第 2 轮模型进行评估
loaded_transformer.eval()
test_total_abs_error = 0.0

with torch.no_grad():
    for test_inputs, test_targets in transformer_test_loader:
        test_predictions = loaded_transformer(test_inputs)

        test_abs_errors = (
            test_predictions - test_targets
        ).abs()

        test_total_abs_error += test_abs_errors.sum().item()

transformer_test_mae = (
    test_total_abs_error / len(transformer_test_dataset)
)

# 在完全相同的测试样本上计算简单基线
test_baseline_predictions = X_sequence_test[:, -1, :]

test_baseline_mae = (
    test_baseline_predictions - y_sequence_test
).abs().mean().item()

print("\n测试集样本数量：", len(transformer_test_dataset))
print(f"Transformer 测试 MAE：{transformer_test_mae:.4f} MW")
print(f"简单基线测试 MAE：{test_baseline_mae:.4f} MW")