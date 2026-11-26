# scene-scale-diffusion

| 项目 | 当前配置 |
|---|---|
| 负责人 | 待认领 |
| 上游代码与固定版本 | [官方源码 `a23745f`](https://github.com/zoomin-lee/scene-scale-diffusion/tree/a23745f37eddedefbf9b6069a0af8ec8b4d0f830) |
| 已验证环境 | Windows、Python 3.13.12、PyTorch 2.11.0+cu128、einops 0.8.2、RTX 5060 Laptop GPU |
| 数据与权重 | CarlaSC Cartesian，使用作者提供的 [discrete_diffusion.tar](https://drive.google.com/file/d/14ZEhIp3hZ-8phMx6prcusxIeiNcztypB/view) |
| 代表功能 | 无条件生成，输出 `128 × 128 × 8` 的语义体素，包含 10 个语义类别和空闲类别 |
| 当前状态 | 已跑通 14 个无条件生成种子和 5 帧条件补全。种子 44 和 7392 的无条件生成样例已导出并完成离线回读。平台联调待验收。 |

## 运行一次无条件生成

从小组仓库根目录执行。下面假设作者源码目录 `scene-scale-diffusion-upstream` 位于小组仓库旁边，权重已放入上游目录下的 `weights`，当前 Python 已安装支持 CUDA 的 PyTorch、NumPy 和 einops。本地若将 einops 单独安装到上游目录的 `.deps`，设置下面的 `PYTHONPATH`。

```powershell
$upstream = (Resolve-Path -LiteralPath '../scene-scale-diffusion-upstream').Path
$env:PYTHONPATH = Join-Path $upstream '.deps'
python -u .\methods\scene-scale-diffusion\sample_discrete.py --upstream $upstream --checkpoint (Join-Path $upstream 'weights\discrete_diffusion.tar') --output .\outputs\scene-scale-diffusion\seed-42 --seed 42
```

脚本调用官方离散扩散采样器，取权重中记录的扩散步数，从随机噪声开始采样。无条件入口只使用 `[1, 128, 128, 8]` 的参考张量形状，运行时无需本地 CarlaSC 数据路径。模型输出中 `0` 表示空闲，`1–10` 是重映射后的语义类别，模型没有独立的未知类别。条件补全的无效区域通过独立的有效区掩码标记。输出目录保存 `voxels.npy` 和 `run.json`，后者记录种子、设置、类别体素数和耗时。复跑时指定新的输出目录。

## 导出平台样例

从小组仓库根目录运行 `export_sample.py`。指定包含 `voxels.npy` 和 `run.json` 的运行目录、上游提交号和一个新输出目录。

```powershell
python .\methods\scene-scale-diffusion\export_sample.py `
  --run-dir .\outputs\scene-scale-diffusion\seed-44 `
  --output .\outputs\scene-scale-diffusion\carla-seed-44-export `
  --code-version a23745f37eddedefbf9b6069a0af8ec8b4d0f830
```

平台从 `manifest.json` 读取展示数据及原始体素的相对路径。展示坐标以米计，体素尺寸为 `0.4 × 0.4 × 0.375`，按照官方数据的范围计算体素中心，并通过 `Y → −Y` 转为右手系。导出使用上游重映射后的类别及色表。 [样例索引](../../examples/README.md) · [CarlaSC 网格配置](https://github.com/UMich-CURLY/3DMapping/blob/main/Data/Generation/SceneCompletion.py#L239-L258) · [CARLA 坐标约定](https://carla.readthedocs.io/en/latest/coordinates/) · [官方色表](https://github.com/zoomin-lee/scene-scale-diffusion/blob/a23745f37eddedefbf9b6069a0af8ec8b4d0f830/datasets/carla.yaml#L51-L75)

## 复现结果与局限

14 个种子均使用官方离散扩散权重，以 `batch_size=1` 运行 100 个扩散步，单样例采样耗时 15.7–17.3 秒。按俯视图上道路格的四邻域统计，最大连通块占该样例道路格的 94.45%–100%，其中 13 个样例出现了额外道路碎片。建筑出现在 8 个样例中，车辆出现在 6 个样例中。这里的道路连通性和类别覆盖用于描述生成结果，评估范围为本次无条件生成的 14 个样例。

两个平台样例都覆盖 10 个语义类别。主样例 `carla-seed-44` 的最大道路连通块占比为 97.93%，对照样例 `carla-seed-7392` 为 94.45%，其道路边缘和支路更易看到断点。条件补全是分工文档中的选做项。

- [种子 44 的俯视和三维体素预览](results/carla-seed-44-3d-preview.png)
- [种子 44 与 7392 的同视角俯视对照](results/platform-seed-44-vs-7392.png)

## 单帧条件补全

使用 CarlaSC Cartesian 测试集 `Town10_Heavy/000000` 的同一帧 LiDAR、语义真值和官方评估计数。提取脚本通过 HTTP Range 读取官方压缩包目录及匹配帧的四个数据文件，并记录压缩包内的路径。单帧 LiDAR 在自身坐标系按官方边界体素化为二值占据。模型使用同一上游提交的 `Con_Diffusion`。 [CarlaSC 测试集下载页](https://umich-curly.github.io/CarlaSC.github.io/download/) · [官方条件模型权重](https://drive.google.com/file/d/10XcHsL_m0ESrurVOxluwYRNZsy9hz_Fd/view)

将条件模型权重保存为上游目录下的 `weights/conditional_discrete_diffusion.tar`。该权重文件的 SHA-256 为 `896c45d969d4e170a2f8e896a394deee843e0e4889c91c6be0299c1795086923`。运行入口需要 CUDA 版 PyTorch、NumPy、einops 和 PyYAML，本地使用 PyYAML 6.0.3。从组内仓库根目录运行以下命令，复跑时为已经存在的目录指定新路径。

```powershell
$upstream = (Resolve-Path -LiteralPath '../scene-scale-diffusion-upstream').Path
$env:PYTHONPATH = Join-Path $upstream '.deps'
python .\methods\scene-scale-diffusion\fetch_completion_frame.py `
  --output .\data\carlasc-completion-test-frame
python .\methods\scene-scale-diffusion\complete_scene.py `
  --upstream $upstream `
  --checkpoint (Join-Path $upstream 'weights\conditional_discrete_diffusion.tar') `
  --frame-dir .\data\carlasc-completion-test-frame `
  --output .\outputs\scene-scale-diffusion\completion-town10-heavy-000000 `
  --seed 42
```

输出目录保存 `observation.npy`、`prediction.npy`、`ground_truth.npy`、`valid_mask.npy` 和含逐类 IoU 的 `run.json`。四个数组共用 `128 × 128 × 8` 原生坐标，预测和真值使用上游重映射后的类别，`0` 为空闲，`1–10` 为语义类别。

本帧使用 `counts > 0` 的 **119,994** 个体素计算指标，忽略 `counts == 0` 的 **11,078** 个体素。占据 IoU 把所有非空类别合并为占据。语义 mIoU 对有效区内并集非零的非空语义类别取平均，本帧共纳入 10 类。 [上游 CarlaSC 评估掩码](https://github.com/zoomin-lee/scene-scale-diffusion/blob/a23745f37eddedefbf9b6069a0af8ec8b4d0f830/utils/tables.py#L94-L105)

种子 42 以 `batch_size=1` 跑完 100 步，耗时 **15.876 秒**。本帧占据 IoU 为 **81.98%**，语义 mIoU 为 **39.29%**。道路和人行道 IoU 分别为 **82.25%** 和 **71.51%**，栏杆与植被 IoU 均为 **0%**。这些指标仅描述这一帧。

[稀疏 LiDAR、条件预测和真值的俯视对照](results/completion-town10-heavy-000000/completion-comparison.png)

### 五帧补全评估

沿用同一权重、种子 42、100 个扩散步和有效体素规则。新增四帧在推理前固定，共覆盖 Town10 的重度、中度、轻度交通序列。使用提取脚本的 `--sample Town10_Heavy/000600` 形式指定表中的序列和帧号，再把该帧目录传给补全脚本。

| 序列及帧号 | 占据 IoU | 语义 mIoU |
|---|---:|---:|
| `Town10_Heavy/000000` | 81.98% | 39.29% |
| `Town10_Heavy/000600` | 74.12% | 36.52% |
| `Town10_Medium/000900` | 85.29% | 37.77% |
| `Town10_Light/000300` | 83.60% | 31.67% |
| `Town10_Light/001200` | 83.18% | 33.13% |
| **五帧合并** | **81.53%** | **40.30%** |

合并指标先累加五帧的交集和并集，再计算 IoU，语义 mIoU 对合并后的 10 个非空类别取平均。评估共纳入 574,206 个有效体素。道路、人行道、车辆和植被的合并 IoU 分别为 85.81%、72.30%、51.61% 和 37.15%。五帧有效区的真值中没有 `Barrier` 类，模型预测了 1,632 个该类体素，因此其合并 IoU 为 0%。本评估范围为 Town10 的五帧。

各帧原生数组由上面的推理命令生成，保存在本地 `outputs/scene-scale-diffusion/`。[五帧汇总和逐帧日志索引](results/completion-five-summary.json) · [五帧逐类 IoU 图](results/completion-five-class-iou.png)

### 稀疏输入与补全结果对照

在同五帧的官方有效区上，把原始 LiDAR 命中体素直接视为占据，以此作为占据基线。模型预测的非空语义体素也统一视为占据。下表先汇总五帧的体素计数，再计算指标。纯几何的 LiDAR 基线只有二值占据，因此这里只比较占据指标。

| 有效区上的预测 | 占据 IoU | 精确率 | 召回率 |
|---|---:|---:|---:|
| 原始稀疏 LiDAR | 37.07% | 97.52% | 37.42% |
| 条件补全 | 81.53% | 94.13% | 85.90% |

在有效区内原始 LiDAR 未命中的体素中，真值占据 55,758 格。模型正确恢复其中 43,862 格，召回率为 78.66%，占据 IoU 为 73.06%。这一子集按输入是否命中划分，其中既可能有遮挡区域，也可能有采样稀疏造成的空缺。全有效区的占据召回提升伴随更多误报，五帧合计误报从 849 格增至 4,773 格。

[逐帧和合并占据对照统计](results/completion-five-occupancy-comparison.json) · [占据对照图](results/completion-five-occupancy-comparison.png)

从仓库根目录复算并保存对照统计。

```powershell
$results = '.\outputs\scene-scale-diffusion'
$frames = 'heavy-000000','heavy-000600','medium-000900','light-000300','light-001200' | ForEach-Object { Join-Path $results "completion-town10-$_" }
python .\methods\scene-scale-diffusion\compare_completion.py @frames --output (Join-Path $results 'completion-five-occupancy-comparison.json')
```
