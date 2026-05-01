# wewrite STATUS (2026-04-29)

## 5 层定位
**L3 — 内容触达 (REACH)** · 微信公众号每日 1 篇发布

## 运行状态
- daemon 数量:**15**(master-brief §3 写「7 daemon」,实际 15)
- daemon 列表(`com.wewrite.*`):
  - 主链:`auto-pick` / `auto-write` / `auto-images` / `auto-review` / `auto-publish`
  - 守护:`auto-publish-guard` / `auto-notify` / `auto-comment-kickoff` / `auto-daily-report`
  - 资源/KOL:`auto-fetch-kol` / `auto-discover-kol` / `auto-hotspot-poll`
  - 同步/统计:`auto-sync-xhs` / `auto-stats`
  - Discord:`discord`(常驻 RunAtLoad=true)
- 最近 7 天活跃日志:**93 条**(最高活跃)

## 已知卡点 🔥
- ❌ **catchphrase 词库格式 bug**(W1 周日修)
- ❌ **image_count 流程时序 bug**(W1 周日修)
- ⚠️ `lib/llm_service.py:86` 仍用 `Path.home() / "cpa"` 老硬编码,**未 patch**(W1 Phase A.9 待修;有 fallback 不阻断)
- ⚠️ master-brief §3 daemon 数严重低估(7 vs 实际 15)

## 关键路径
- 主链:`scripts/auto/*.sh` + `scripts/workflow/*.py`
- 库:`lib/llm_service.py` / `lib/xhs_mcp_client.py`(同 xhswrite 复用)
- 配置:`config.yaml`(gitignored)+ `auto-schedule.yaml`
- 文档:`SKILL.md` / `CLAUDE.md`

## 依赖
- 依赖谁:`cpa`(LLM)+ `md2wx`(公众号排版)
- 谁依赖我:无(L3 输出端)
