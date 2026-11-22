# 三维语义城市场景生成

四种方法的代表功能复现、PrITTI 连续扩展对照，以及读取离线样例的三维展示平台。

## 目录

| 路径 | 内容 | 维护人 |
|---|---|---|
| methods/scene-scale-diffusion/ | CarlaSC 无条件生成与可选补全 | Scene-Scale Diffusion 负责人 |
| methods/pdd/ | CarlaSC 多尺度生成与子块衔接 | PDD 负责人 |
| methods/semcity/ | 公开权重生成与区域操作 | SemCity 负责人 |
| methods/pritti/ | KITTI-360 布局生成、单次扩展和掩码调用 | PrITTI 负责人 |
| platform/ | 离线清单读取、三维展示与对照 | SemCity 负责人牵头 |
| experiments/pritti-extension/ | A/B/C 实验驱动、检查与评价记录 | PrITTI、PDD 负责人 |
| examples/ | 允许共享的小样例及索引 | 各方法负责人 |
| docs/ | 分工与平台接入契约 | 全组 |

入组先看 [仓库初始化与协作](docs/repository-setup.md)、[贡献指南](CONTRIBUTING.md)和[平台接入规范](docs/三维语义城市场景生成_平台接入规范.md)。各方法的安装和运行步骤由负责人维护在各自 README，模型环境可独立配置。
