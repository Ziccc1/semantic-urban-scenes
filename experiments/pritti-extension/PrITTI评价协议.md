# PrITTI 连续扩展评价

负责人与交接顺序见[团队分工](https://github.com/Ziccc1/semantic-urban-scenes/blob/main/docs/三维语义城市场景生成_四人分工与验收.md)。PrITTI 负责人交付同一坐标系下的扩展前、首次扩展和最终采用状态，附窗口、重叠区、保留区、原生掩码及其含义。PDD 负责人检查异常、给出位置及建议范围，Scene-Scale Diffusion 负责人参与人工复核。

## 首样本检查

| 对象 | 计算口径 | 人工复核 |
| --- | --- | --- |
| 道路 | 在接缝两侧相邻地面格上，用两侧均有效且至少一侧为道路的格对作为分母，双侧均为道路的格对作为分子。沿接缝索引记录单侧道路位置。无道路格对记 null，保留分母。 | 查看道路走向、宽度和是否在合理位置终止。格对匹配率可定位候选，连通性由同视角图和后续区域检查确认。 |
| 地面 | 两侧有效格对的绝对高度差，记录 P95（米）、阈值和超阈格的位置。无有效格对记 null。 | 区分自然坡度、路沿或台阶与生成接缝。首个真实样例确认阈值后再用于全组。 |
| 已保留区域 | 比较同坐标保留格的有效性、类别与米制高度，记录变化占比及坐标。空保护区记 null。物体另按稳定 ID 记录新增、删除和参数变化，ID 无法对应时记录待复核。 | 检查修正范围外是否出现地面或物体变化。在三维和俯视核对相同位置。 |
| 开销 | 收集每步 elapsed_ms、每次 attempt 的状态和种子、额外调用次数。 | 核对失败、跳过和沿用状态的原因。 |

地面脚本 `检查扩展接缝.py` 接受两个已对齐的 NPZ。均包含二维 `labels`、`z_m` 和布尔 `valid`，before 还含布尔 `protected`。索引顺序为 `[x,y]`，`--axis 0` 代表沿 X 扩展，`--edge 2` 表示在 X=1 和 X=2 两列之间检查。标签编号由 PrITTI 导出给出，高度上升方向统一为 +Z。原生无效掩码和保留掩码先按各自约定转换。首次测试可用参数 `--road-id 1 --axis 0 --edge 2 --height-threshold-m 0.25` 复查下列人工网格，0.25 m 是测试值。

每步分别评价首次和最终采用的状态。最终记录以 run_id、sample_id、strategy、step 连接 steps.json，定位索引在真实样例到达后按栅格原点和格尺寸转换成共享米制区域，再分配 region ID。真实样本到达前，评价阈值、掩码变换、物体匹配及修正策略仍待联调。

[人工 4×3 网格验收](小网格校验.json)识别出一处道路缺口、一处 0.5 m 地面高度跳变和一处保留格类别变化，空区域均返回 null。

## 按 `steps.json` 生成逐步评价表

请 PrITTI 负责人提供一组同初始街区的 A/B/C 样例。需要 `manifest.json`、`steps.json`、各步父状态、首次生成和最终采用状态、实际保留区掩码，以及窗口、重叠区、坐标变换和尝试日志。演示包使用 `ground_objects_json`，地面格是 `[x,y,z,label_id]`，各状态须位于同一个米制网格。

评价侧车 `geometry.json` 由两位负责人根据首个真实样例核对后填写。其 `grid` 包含 `shape_xy`、首格中心 `first_center_xy_m` 和 `cell_size_xy_m`。`road_ids` 取清单实际标签。`steps` 每条沿用 `run_id`、`sample_id`、`strategy`、`step` 四键，记录 `seam_axis`、`seam_edge`、可选的半开 `seam_span`、`height_threshold_m` 和样例内相对的 `protected_mask_path`。掩码为与共享 XY 网格同形的布尔 NPY。`protected_height_tolerance_m` 可单独指定保留区高度容差，缺省为 0。不要把人工测试阈值当作真实场景阈值。

`attempts_record` 由日志提供方确认。若 `attempts` 含首次生成，填写 `all_calls`，若仅登记额外调用，填写 `extra_calls`。未确认时仍输出日志中可数的调用，但额外调用留空。`elapsed_ms` 是整步耗时，在首次和采用两行重复显示，求和时按步计一次。

```powershell
python 'experiments/pritti-extension/evaluate_steps.py' '<样例目录>' `
  --steps '<steps.json>' --geometry '<geometry.json>' --output '<新输出目录>' --input-kind pritti
python 'experiments/pritti-extension/smoke_evaluation.py' '<新测试目录>'
```

`evaluation.json` 保留输入哈希、首次和采用状态指标、异常栅格索引、米制中心和建议 XY 范围。`evaluation.md` 是按四键排序的结果表。候选范围要由 PrITTI 负责人复核后再映射成实际掩码。物体保留和人工判定需结合稳定 ID 与同坐标视图复核，目前在输出中标为待审核。

新脚本已用人工 A/B/C 小网格及一个跳过步骤验收，核对了范围坐标、调用数、前后差异和上下步状态引用。真实扩展输入、阈值校准、人工复核及最终对照都待交接。
