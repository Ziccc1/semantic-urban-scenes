# 贡献指南

1. 克隆仓库，从最新 main 建短期分支，例如 method/pdd-export、platform/import-pdd 或 experiment/pritti-checks。
2. 各自维护所属目录。模型原生推理调用留在 methods，跨步骤实验逻辑放 experiments，展示读取和交互放 platform。接口字段变化同步更新 docs 并请受影响的负责人核对。
3. 提交前运行本模块的最小样例，用 git status --short 和 git diff --cached --stat 核对暂存内容。数据、权重、密钥、第三方整库和大体积输出采用各自的获取渠道，README 记录来源、版本和配置方法。
4. 推分支并开 PR。说明运行命令、样例编号、验证结果、已知限制和涉及的接口。平台接入 PR 由平台负责人试读，专项变更由 PrITTI 与 PDD 负责人交叉检查。
5. 合并后从 main 同步，继续下一项任务。样例编号和运行日志可追溯到代码版本及配置。
