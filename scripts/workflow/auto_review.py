#!/usr/bin/env python3
"""auto_review · 写完后 LLM 自审 5+1 维度 · 不达标重写一次。

自审维度(0-5 分制):
  1. hook_strength      前 3 句钩子强度
  2. word_count_min     字数下限(>=1500)
  3. image_count_min    图数(cover + chart-1..4 = 5)
  4. catchphrase_min    智辰口头禅出现次数(从 identity/voice/catchphrases.md)
  5. forbidden_check    禁忌词检测(从 identity/voice/forbidden.md)
  6. case_realism       案例类专属 · 配图 prompt 真实感

阈值:任一维度 < threshold(默认 3) · 触发重写 · 仍不达标 push Discord 人工介入。

设计公约:
  - 维度 1 / 6 调 LLM(claude -p)· 其他维度纯文本/文件检查
  - LLM 失败 → 这两维度记 None · 不阻断(避免把全自动卡死)
  - threshold / max_retries 从 config/auto-schedule.yaml 读
  - 不动 markdown 文件 · 只输出评分 · retry 由调用方(auto-review.sh)决定

用法:
  python3 scripts/workflow/auto_review.py                # 用 session 当前 article
  python3 scripts/workflow/auto_review.py --md output/2026-04-23-x.md
  python3 scripts/workflow/auto_review.py --json         # 输出 JSON 给 shell 解析
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _state  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG = ROOT / "config" / "auto-schedule.yaml"
IDENTITY = ROOT / "identity"
PUSH = ROOT / "discord-bot" / "push.py"
PY = ROOT / "venv" / "bin" / "python3"
if not PY.exists():
    PY = Path("python3")

DEFAULT_THRESHOLD = 3
DEFAULT_WORD_MIN = 1500
DEFAULT_IMAGE_MIN = 5
DEFAULT_CATCHPHRASE_MIN = 1


# ============================================================
# Helpers · 加载配置 / identity 词表
# ============================================================
def load_review_cfg() -> dict:
    """读 config/auto-schedule.yaml#review · 兜底用 default。"""
    if not CONFIG.exists():
        return {}
    try:
        cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return cfg.get("review", {}) or {}


def _read_lines_no_blank_no_comment(p: Path) -> list[str]:
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(">"):
            continue
        # 去 markdown bullet 前缀
        s = re.sub(r"^[-*+]\s+", "", s)
        if s:
            out.append(s)
    return out


def load_catchphrases() -> list[str]:
    return _read_lines_no_blank_no_comment(IDENTITY / "voice" / "catchphrases.md")


def load_forbidden() -> list[str]:
    return _read_lines_no_blank_no_comment(IDENTITY / "voice" / "forbidden.md")


# ============================================================
# 纯文本维度
# ============================================================
def _word_count(md: str) -> int:
    """中文字符数(简单口径 · 不严格)· 去掉 markdown 语法。"""
    text = re.sub(r"```.*?```", "", md, flags=re.DOTALL)  # 去代码块
    text = re.sub(r"`[^`]*`", "", text)                    # 去 inline code
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)       # 去图片
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)   # 去链接 · 留 text
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL) # 去注释
    text = re.sub(r"^#+\s.*$", "", text, flags=re.MULTILINE) # 去 heading
    text = re.sub(r"\s+", "", text)
    return len(text)


def _image_count(md: str) -> int:
    """统计 ![](images/xxx.png) 占位符数(预期 5 张)。"""
    return len(re.findall(r"!\[[^\]]*\]\(\s*images/[^)]+\)", md))


def _catchphrase_hits(md: str, phrases: list[str]) -> tuple[int, list[str]]:
    """返回命中次数 + 命中的句子列表。"""
    hits = []
    count = 0
    for p in phrases:
        if not p:
            continue
        # 取前 8 个字作 substring 匹配(完整短语容易因标点变体不命中)
        key = p[:8]
        if key and key in md:
            hits.append(p)
            count += md.count(key)
    return count, hits


# LLM 套话连接词(humanize 维度) · 命中即扣分
_LLM_CONNECTORS = (
    "然而", "此外", "总之", "综上", "与此同时", "值得一提的是",
    "首先,", "其次,", "最后,", "总而言之", "综上所述",
    "拭目以待", "值得关注", "希望对你有帮助", "不可否认",
)

# LLM 套话开头(humanize 维度)
_LLM_OPENING_PATTERNS = (
    "最近,", "近期,", "随着", "众所周知", "在这个", "让我们",
    "我们一起", "相信大家", "近年来", "在AI时代", "随着AI",
)


def _humanize_check(md: str) -> dict:
    """反 AI 检测维度 · 机械检查(不调 LLM)· 见 references/anti-ai-detection.md。

    检 6 项:
      1. LLM 套话连接词命中数(然而/此外/总之...)
      2. LLM 套话开头(最近,/众所周知...)
      3. 段长方差(全均匀 = AI)
      4. 整数密度(100/50%/1000 等)
      5. 真实经历锚点(地点+时间+人名 计数)
      6. 失败/踩坑/不确定披露(0 处 = AI)

    返回 raw counts + 0-5 综合 humanize 分。
    """
    # 1. LLM 连接词
    connector_hits = sum(md.count(w) for w in _LLM_CONNECTORS)

    # 2. LLM 开头(看前 100 字)
    head = md[:200]
    opening_hits = sum(1 for p in _LLM_OPENING_PATTERNS if p in head)

    # 3. 段长方差(段 = 双换行分隔)· 方差 < 50 算太均匀
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", md) if p.strip() and not p.startswith("#")]
    if len(paragraphs) >= 5:
        lengths = [len(p) for p in paragraphs]
        mean = sum(lengths) / len(lengths)
        var = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    else:
        var = 999  # 段太少不判

    # 4. 整数密度(100 / 50% / 1000 / 10000 等典型 LLM 整数)
    integers = re.findall(r"\b(?:100|1000|10000|50%|100%|10倍|100倍|1000倍|十倍|百倍)\b", md)
    integer_hits = len(integers)

    # 5. 真实锚点(地点 + 时间 + 人名 出现次数)
    anchors = 0
    anchors += len(re.findall(r"(?:武汉|深圳|北京|上海|杭州)(?:光谷|南山|海淀|浦东|西湖)?", md))
    anchors += len(re.findall(r"(?:上周|昨天|凌晨|今早|去年|半年前|3月|4月|5月)\s*(?:[一二三四五六日])?", md))
    anchors += len(re.findall(r"(?:哈工大|清华|北大|半导体|fab|openclaw)", md))
    anchors += len(re.findall(r"(?:张工|李工|王工|某 \w+ 同学|我朋友|群里 \w+)", md))

    # 6. 失败 / 踩坑 / 不确定披露
    failure_hits = sum(md.count(w) for w in (
        "踩坑", "翻车", "失败", "搞砸", "折腾了",
        "我没完全", "我没想清楚", "不确定", "可能不准", "偏差",
        "报错", "卡住了", "搞了半天",
    ))

    # 综合分(0-5)
    score = 5
    if connector_hits >= 2:
        score -= 2
    elif connector_hits >= 1:
        score -= 1
    if opening_hits >= 1:
        score -= 1
    if var < 50 and len(paragraphs) >= 5:
        score -= 1
    if integer_hits >= 4:
        score -= 1
    if anchors == 0:
        score -= 2
    elif anchors == 1:
        score -= 1
    if failure_hits == 0:
        score -= 1
    score = max(0, min(5, score))

    return {
        "score": score,
        "connector_hits": connector_hits,
        "opening_hits": opening_hits,
        "para_var": round(var, 1),
        "integer_hits": integer_hits,
        "anchors": anchors,
        "failure_hits": failure_hits,
    }


def _forbidden_hits(md: str, words: list[str]) -> list[str]:
    return [w for w in words if w and w in md]


# ============================================================
# LLM 维度 · hook_strength + case_realism
# ============================================================
def _claude_score(prompt: str, *, timeout: int = 180) -> int | None:
    """调 claude -p 让它返回 1 个 1-5 分整数 · 解析失败返回 None。"""
    args = [
        "claude", "-p", "--output-format", "text",
        "--permission-mode", "bypassPermissions",
        prompt,
    ]
    try:
        r = subprocess.run(
            args, cwd=str(ROOT),
            capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if r.returncode != 0:
        return None
    out = (r.stdout or "").strip()
    # 抽第一个 1-5 数字
    m = re.search(r"\b([1-5])\b", out)
    if not m:
        return None
    return int(m.group(1))


def score_hook(md: str) -> int | None:
    """前 200 字让 claude 评 1-5 分。"""
    # 取第一段实质正文(跳过 H1 / 图片占位符 / 空行)
    body_start = ""
    for line in md.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "!", "<", ">", ":")):
            continue
        body_start = s
        break
    if not body_start:
        # 退而求其次 · 取前 300 字
        body_start = md[:300]
    snippet = body_start[:300]
    prompt = (
        "你是一个微信公众号编辑 · 评估下面这段文章开头(前 1-3 句)的钩子强度。\n"
        "评分标准:\n"
        "  5 = 强钩子(冲突 / 反预期 / 具体数字 / 制造悬念)· 一行就让人想读下去\n"
        "  4 = 还行钩子\n"
        "  3 = 中规中矩 · 不糟也不亮\n"
        "  2 = 平淡 / 自我介绍 / 背景铺垫太多\n"
        "  1 = 完全没钩子\n\n"
        f"文章开头:\n```\n{snippet}\n```\n\n"
        "**只回答一个 1-5 的数字 · 不要解释。**"
    )
    return _claude_score(prompt, timeout=120)


def score_case_realism(md: str) -> int | None:
    """案例类专属 · 让 claude 评配图占位符附近的数字真实感。"""
    # 抽所有 ![](images/xxx.png) 上下各 200 字
    img_re = re.compile(r"(!\[[^\]]*\]\(\s*images/[^)]+\))")
    pieces = []
    for m in img_re.finditer(md):
        start = max(0, m.start() - 200)
        end = min(len(md), m.end() + 200)
        pieces.append(md[start:end])
    if not pieces:
        return None  # 没图 · 不评
    sample = "\n---\n".join(pieces)[:2000]
    prompt = (
        "你是一个内容审核 · 评估下面 5 张图占位符附近文字的「数字真实感」。\n"
        "评分标准:\n"
        "  5 = 周围都是具体数字(`$12,847` `4,891 users` `Day 30` 这种 · 不像凑的)\n"
        "  4 = 多数有具体数字 · 偶有模糊\n"
        "  3 = 一半有数字一半没\n"
        "  2 = 多数模糊(「很多用户」「很多收入」)\n"
        "  1 = 全都没数字 / 全是凑数(5000 / 10000 / $1000)\n\n"
        f"配图附近文字:\n```\n{sample}\n```\n\n"
        "**只回答一个 1-5 的数字 · 不要解释。**"
    )
    return _claude_score(prompt, timeout=120)


# ============================================================
# 主流程
# ============================================================
def review(md: str, *, is_case: bool = False, threshold: int = DEFAULT_THRESHOLD,
           skip_llm: bool = False) -> dict:
    """跑一次 review · 返回 scores dict。"""
    cfg = load_review_cfg()
    word_min = int(cfg.get("dimensions", {}).get("word_count_min", DEFAULT_WORD_MIN))
    img_min = int(cfg.get("dimensions", {}).get("image_count_min", DEFAULT_IMAGE_MIN))
    catch_min = int(cfg.get("dimensions", {}).get("catchphrase_min", DEFAULT_CATCHPHRASE_MIN))

    # 纯文本维度
    wc = _word_count(md)
    ic = _image_count(md)
    catches, hit_list = _catchphrase_hits(md, load_catchphrases())
    forbidden_hits = _forbidden_hits(md, load_forbidden())
    humanize = _humanize_check(md)  # 反 AI 检测维度(2026-04-26 加)

    # 这些转 0-5 分制
    word_score = 5 if wc >= word_min else (3 if wc >= word_min * 0.8 else (2 if wc >= word_min * 0.6 else 1))
    image_score = 5 if ic >= img_min else (3 if ic >= img_min - 1 else 1)
    catch_score = 5 if catches >= catch_min else (3 if catches >= 1 else 2)
    forbid_score = 1 if forbidden_hits else 5  # hard fail · 命中即 1 分

    # LLM 维度
    hook_score: int | None = None
    case_score: int | None = None
    if not skip_llm:
        hook_score = score_hook(md)
        if is_case:
            case_score = score_case_realism(md)

    scores = {
        "hook_strength": hook_score,
        "word_count": word_score,
        "image_count": image_score,
        "catchphrase": catch_score,
        "forbidden": forbid_score,
        "case_realism": case_score,
        "humanize": humanize["score"],   # 反 AI 检测综合分(2026-04-26)
    }
    raw = {
        "word_count": wc,
        "image_count": ic,
        "catchphrase_hits": catches,
        "catchphrase_examples": hit_list[:3],
        "forbidden_hits": forbidden_hits,
        "is_case": is_case,
        "humanize": humanize,            # 含 6 子项 raw counts
    }
    # 决定通过/不通过(LLM None 不算 fail)
    failed_dims = []
    for dim, score in scores.items():
        if score is None:
            continue
        if score < threshold:
            failed_dims.append((dim, score))
    return {
        "scores": scores,
        "raw": raw,
        "threshold": threshold,
        "passed": len(failed_dims) == 0,
        "failed_dims": failed_dims,
    }


def push_review_result(result: dict, md_path: Path) -> None:
    s = result["scores"]
    raw = result["raw"]
    h = raw.get("humanize") or {}
    status = "✅ 通过" if result["passed"] else "❌ 未达标"
    lines = [
        f"📊 **auto_review · {status}**",
        f"📂 {md_path.name}",
        "",
        f"• humanize: {s.get('humanize', '?')}/5 "
        f"(连接词 {h.get('connector_hits', 0)} · 锚点 {h.get('anchors', 0)} · "
        f"失败披露 {h.get('failure_hits', 0)})",
        f"• hook_strength: {s['hook_strength']}",
        f"• word_count: {s['word_count']} (实测 {raw['word_count']} 字)",
        f"• image_count: {s['image_count']} (实测 {raw['image_count']} 张)",
        f"• catchphrase: {s['catchphrase']} (命中 {raw['catchphrase_hits']} 次)",
        f"• forbidden: {s['forbidden']}" + (f" (命中 {raw['forbidden_hits']})" if raw['forbidden_hits'] else ""),
    ]
    if raw["is_case"]:
        lines.append(f"• case_realism: {s['case_realism']} ★ 案例真实感")
    if not result["passed"]:
        fd = ", ".join(f"{d}={sc}" for d, sc in result["failed_dims"])
        lines += ["", f"⚠ 不达标维度:{fd}"]
    try:
        subprocess.run(
            [str(PY), str(PUSH), "--text", "\n".join(lines)],
            check=True, timeout=60,
        )
    except Exception as e:
        print(f"⚠ push 失败: {e}", file=sys.stderr)


def main() -> int:
    p = argparse.ArgumentParser(description="auto_review · 5+1 维度自审")
    p.add_argument("--md", help="markdown 路径(默认 session.article_md)")
    p.add_argument("--case", action="store_true", help="强制走 case 维度")
    p.add_argument("--no-case", action="store_true", help="强制不走 case 维度")
    p.add_argument("--threshold", type=int, default=None, help="阈值(默认读 config 或 3)")
    p.add_argument("--skip-llm", action="store_true", help="跳过 LLM 维度(测试用)")
    p.add_argument("--no-push", action="store_true", help="不 push Discord")
    p.add_argument("--json", action="store_true", help="输出 JSON 给 shell 解析")
    args = p.parse_args()

    if args.md:
        md_path = Path(args.md).resolve()
    else:
        s = _state.load()
        rel = s.get("article_md")
        if not rel:
            print("❌ session 无 article_md · 用 --md 显式指定", file=sys.stderr)
            return 1
        md_path = (ROOT / rel).resolve()
    if not md_path.exists():
        print(f"❌ {md_path} 不存在", file=sys.stderr)
        return 1

    # 决定是否 case
    is_case = args.case
    if not is_case and not args.no_case:
        s = _state.load()
        sched = s.get("auto_schedule") or {}
        if sched.get("style") == "case" or sched.get("image_style") == "case-realistic":
            is_case = True

    cfg = load_review_cfg()
    threshold = args.threshold if args.threshold is not None else int(cfg.get("threshold", DEFAULT_THRESHOLD))

    md = md_path.read_text(encoding="utf-8")
    result = review(md, is_case=is_case, threshold=threshold, skip_llm=args.skip_llm)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        s = result["scores"]
        raw = result["raw"]
        print(f"=== auto_review · {md_path.name} ===")
        print(f"is_case={raw['is_case']} · threshold={threshold} · passed={result['passed']}")
        for k, v in s.items():
            print(f"  {k}: {v}")
        print(f"raw: word={raw['word_count']} img={raw['image_count']} "
              f"catch={raw['catchphrase_hits']} forbidden={raw['forbidden_hits']}")
        if not result["passed"]:
            print(f"failed_dims: {result['failed_dims']}")

    if not args.no_push:
        push_review_result(result, md_path)

    return 0 if result["passed"] else 2  # exit 2 = retry signal


if __name__ == "__main__":
    sys.exit(main())
