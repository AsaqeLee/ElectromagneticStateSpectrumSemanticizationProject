# 语义参数测试样例

字段含义同 `SemanticParams`：`yonghu`/`youwu`/`menxian`/`pos_edge`/`neg_edge`/`start`/`end`/`fenbianlv`/`sinr`。所有用例已满足校验：`0 <= start <= end < fenbianlv`，`sinr` 仅为单值或与区间长度一致。

| 用例 | yonghu | youwu | menxian | pos_edge | neg_edge | start | end | fenbianlv | sinr 描述 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A：单值提升 | 1 | 1 | -72.0 | [10, 18] | [5, 24] | 8 | 24 | 128 | 单值 12.5 dB（区间全部抬升 12.5 dB） |
| B：宽带低信噪 | 2 | 1 | -90.0 | [120, 160] | [98, 230] | 100 | 220 | 512 | 单值 5.0 dB（用于低 SINR 参考段） |
| C：自定义矢量 | 3 | 0 | -80.0 | [300, 340, 380] | [260, 420] | 260 | 420 | 1024 | 161 点矢量，线性从 3→18 dB，可用于测试非均匀谱段 |

矢量示例（用例 C）：
```json
{
  "yonghu": 3,
  "youwu": 0,
  "menxian": -80.0,
  "pos_edge": [300, 340, 380],
  "neg_edge": [260, 420],
  "start": 260,
  "end": 420,
  "fenbianlv": 1024,
  "sinr": [3.0, 3.09, 3.18, ..., 17.91, 18.0],
  "freq_min_mhz": 30.0,
  "freq_max_mhz": 2500.0
}
```

使用方式：将表中任意行转为 JSON 保存为 `*.json`，其中用例 C 的 `sinr` 需生成长度 `end-start+1` 的数值数组（示例为线性插值）。然后通过 `python -m src.pipeline.semantic_eval --reference <参考谱> --semantic <json>` 进行评估，或用 `semantic_plot` 进行可视化。***
