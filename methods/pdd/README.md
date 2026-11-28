# PDD

PDD 用公开权重逐级生成 CarlaSC 语义体素。同一个种子保留粗、中、细三个状态，可以在同一坐标下对照道路布局和局部细节。[成果与交接](成果与交接.md) · [三尺度样例](../../examples/pdd/carlasc-v3-20261015/manifest.json)

| 项目 | 已核对的信息 |
|---|---|
| 上游 | [Pyramid Discrete Diffusion](https://github.com/yuhengliu02/pyramid-discrete-diffusion) 的本地源码快照。样例清单记录源码内容哈希 |
| 已验证环境 | Windows、Python 3.9.25、PyTorch 2.7.1+cu118、RTX 4060 Laptop GPU 8 GB |
| 数据与权重 | CarlaSC Cartesian Finer，作者发布的 `infere_s_1.tar`、`infere_s_1_to_s_2.tar`、`infere_s_2_to_s_3.tar`。下载入口与文件哈希见下文和样例清单 |
| 代表功能 | `32×32×4 → 64×64×8 → 256×256×16` 逐级生成，12 个种子完成完整覆盖检查 |
| 主样例 | `carlasc-v3-20261015`，细尺度用域内九块融合与 V3 稀疏小空列修补 |

[作者权重与数据入口](https://github.com/yuhengliu02/pyramid-discrete-diffusion#datasets-and-pretrained-models)

## 复跑与导出

取得组内 `PDD_复现代码.zip` 后，在解压根目录运行。代码包内有上游源码快照、依赖版本和用于官方加载器的一帧三尺度预处理数据。按 `PDD_最小测试/运行说明.md` 配置 CUDA 环境，并将 `$weights` 改为三份权重所在目录。

```powershell
$weights = 'D:/PDD-weights'
$run = 'outputs/pdd/seed-20261015'
python 'PDD_最小测试/reproduce_chain.py' --seed 20261015 --output $run --fine-mode coverage --deterministic `
  --s1-checkpoint (Join-Path $weights 'infere_s_1.tar') `
  --s2-checkpoint (Join-Path $weights 'infere_s_1_to_s_2.tar') `
  --s3-checkpoint (Join-Path $weights 'infere_s_2_to_s_3.tar')
```

每次使用新的输出目录。`s3` 保留官方四块，`s3-full` 保留补边 V1，`chain-validation.json` 记录条件链与融合校验。导出命令如下。

```powershell
python 'PDD_最小测试/export_pdd.py' carlasc-full-replay 'outputs/pdd/carlasc-full-replay' `
  --s1 "$run/s1" --s2 "$run/s2" --s3 "$run/s3-full"
```

课程包含主样例的九个原生窗口，可以从这些已保存的采样重建 V3，复核时无需重新做扩散推理。把代码包解压到课程交付包的解压根目录，在该目录运行以下命令。

```powershell
python 'PDD_最小测试/supported_selection.py' --source '原始输出/域内九块' --output 'outputs/pdd/v3-replay' --base center
(Get-FileHash -Algorithm SHA256 'outputs/pdd/v3-replay/result.txt').Hash -eq (Get-FileHash -Algorithm SHA256 '主样例/source/fine.txt').Hash
```

## 查看样例

组内平台读取主样例的 `manifest.json`，依次加载 `coarse`、`medium`、`fine`。独立查看器读取同一份 V3 主样例。从仓库根目录启动以下本地服务。

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

在 Edge 或 Chrome 打开下方地址，用页面上方的「粗尺度」「中尺度」「细尺度」切换。查看器、仓库主样例及三尺度成果图都使用种子 `20261015` 的 V3。[打开本地查看器](http://127.0.0.1:8765/methods/pdd/preview/) · [主样例静态图](results/three-scales-v3.png)
