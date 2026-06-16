# 多平台改写规则

把一份源内容改写成各平台适配版本时遵循。各平台的具体调性见 `toolkit/platforms/<id>.yaml` 的 `rewrite_brief`。

## 原创铁律（最重要）
- **内容级真改，不是洗稿**：重构信息顺序、换开头、改表达方式、按平台节奏重组，而不是逐句替换近义词。
- 同一份源不能原样多平台发——平台有内容级判重（小红书 180 天去重+原创度权重，抖音多重指纹），照搬必被限流。
- 每个版本要与「源」和「其它平台版本」都拉开差异。

## 人设一致
- 所有平台版本保持同一 persona（见 `style.yaml` / `personas/`）的内核（价值观、视角、专业度）。
- 仅按平台调性适配「表达方式」：长句叙事（公众号）↔ 短句口语+emoji（小红书）↔ 可口播短句（抖音）。

## 质量门（每个版本都要过）
1. 反 AI：`python3 scripts/humanness_score.py <file> --json`，分数应 ≥ 0.6。
2. 原创度：`python3 scripts/similarity_check.py output/source.md <file> --json`，`max_similarity` 应 ≤ 0.6。
3. 不过就重写该平台版本，最多重试 2 次；仍不过则保留最好的一版并说明。

## 产出位置
- 每个平台写到 `output/<platform 的 output_filename>`（如 `output/xiaohongshu.md`、`output/douyin.md`）。
- 小红书需图文：复用源稿已有配图（在 `output/` 内的图片），正文按 markdown 图片语法引用；若源无图，在文末注明「需补图」。
