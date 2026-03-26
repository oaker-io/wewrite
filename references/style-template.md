# 如何创建客户配置

## 快速开始

1. 复制 `clients/demo/style.yaml` 到 `clients/{客户名}/style.yaml`
2. 修改配置项
3. 对 Agent 说：「用 {客户名} 的配置写一篇公众号文章」

## 必填字段

```yaml
name: "客户名称"
industry: "行业"
topics:                    # 内容方向（列表）
  - "方向1"
  - "方向2"
tone: "写作风格描述"
theme: "professional-clean" # 排版主题
```

## 可选字段

```yaml
target_audience: "目标受众描述"
voice: "写作人称和语感"
word_count: "1500-2500"
blacklist:
  words: ["禁忌词1", "禁忌词2"]
  topics: ["禁忌话题1"]
reference_accounts: ["参考账号1", "参考账号2"]
cover_style: "封面风格描述"
cover_template: "/path/to/cover.png"  # 设置后跳过 AI 生成封面
author: "署名"
```

## 可用排版主题

| 主题 | 说明 |
|------|------|
| professional-clean | 专业简洁（默认，适合大部分企业） |
| tech-modern | 科技风（蓝紫渐变，适合技术/产品类） |
| warm-editorial | 暖色编辑风（适合生活/文化类） |
| minimal | 极简黑白（适合文学/严肃内容） |
