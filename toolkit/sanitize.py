"""Bot 发布前 markdown 兜底清理。

修四类高频问题(直接对接 publish.py · 也可独立调用):
  1. **去重 H1**:WeChat 草稿箱标题由 publish 单独传入,文章 H1 会重复显示。
  2. **清空 cover alt**:`![封面](images/cover.png)` 会让 md2wx 渲染出 "封面"
     二字。统一改成 `![](images/cover.png)`。
  3. **末尾兜底 author-card**:若末尾 30 行内不存在 `:::author-card`,
     自动追加一张「智辰老师」卡片(含 mp_brand 嵌入「宸的 AI 掘金笔记」)。
  4. **就地补 mp_brand**:末尾 author-card 若缺 `mp_brand` 字段(老版本生成的
     卡只有 name/tagline/bio/tags/footer),就地插入 mp_brand/mp_desc/mp_meta
     三行,让嵌入公众号关注卡视觉稳定渲染。

运行方式:
    from sanitize import sanitize_for_publish, prepare_for_publish

公约:纯函数 + 幂等 · 多次执行结果一致 · 无副作用文件写入(prepare 除外)。
"""
from __future__ import annotations

import re
import yaml
from datetime import datetime
from pathlib import Path

# 末尾压轴卡片 · style.yaml 的 brand 字段 = 宸的 AI 掘金笔记
DEFAULT_BOTTOM_CARD = """
:::author-card
name: 智辰老师
tagline: 独立开发者 · AI 红利观察者 · openclaw 武汉创业群群主
bio: 每天一篇 AI 行业红利解读。不追热搜情绪,只挖热搜之下被忽略的真信号。从 Cursor 估值到豆包"豆脚",帮你看清下一波该上车还是该撤。
mp_brand: 宸的 AI 掘金笔记
mp_desc: 记录 AI Agent 与工具的真实使用过程与长期价值。
mp_meta: 关注获取每日 AI 红利信号 · 看智辰
tags: [AI 红利, AI Coding, 武汉创业, Skill 开发]
footer: 扫码加我微信备注「AI Coding」· 我会拉你进读者群 · 武汉朋友可扫下方 openclaw 群码
:::
""".strip()

# 短文(副推位)mini 版 · 不带 bio + 复杂 tags · 只 mp_brand + 1 行 footer
# 给 sanitize_for_publish(..., shortform=True) 用
DEFAULT_BOTTOM_CARD_SHORTFORM = """
:::author-card
name: 智辰老师
tagline: AI 红利 · 看智辰
mp_brand: 宸的 AI 掘金笔记
mp_desc: 每天 1 篇 AI 真信号 + 1-2 篇副推。
mp_meta: 关注 · 看智辰
footer: 扫码加我微信备注「AI」· 拉你进读者群
:::
""".strip()

_RE_H1 = re.compile(r'^\s*#\s+\S')
_RE_COVER_IMG = re.compile(
    r'!\[[^\]]*\](\(\s*(?:[^)\s]*/)?cover\.[a-zA-Z0-9]+\s*\))'
)
# 匹配整个 :::author-card ... ::: 块 · DOTALL 允许内容跨行
_RE_AUTHOR_CARD_BLOCK = re.compile(
    r'(:::author-card[ \t]*\r?\n)([\s\S]*?)(\r?\n:::)'
)
_TAIL_LOOKBACK_LINES = 30

# 末尾 author-card 若缺 mp_brand 字段就地补这三行(嵌入公众号关注卡)
DEFAULT_MP_FIELDS = (
    "mp_brand: 宸的 AI 掘金笔记\n"
    "mp_desc: 记录 AI Agent 与工具的真实使用过程与长期价值。\n"
    "mp_meta: 关注获取每日 AI 红利信号 · 看智辰"
)


def _strip_leading_h1(text: str) -> str:
    """删掉首个 H1(及紧随的空行)。其余 H1 不动。保留原文末尾换行。"""
    trailing_nl = "\n" if text.endswith("\n") else ""
    lines = text.splitlines()
    out: list[str] = []
    dropped = False
    skip_blank_after = False
    for line in lines:
        if not dropped and _RE_H1.match(line):
            dropped = True
            skip_blank_after = True
            continue
        if skip_blank_after and line.strip() == "":
            skip_blank_after = False
            continue
        skip_blank_after = False
        out.append(line)
    return "\n".join(out) + trailing_nl


def _clear_cover_alt(text: str) -> str:
    """`![封面](images/cover.png)` → `![](images/cover.png)`(只动 cover.*)"""
    return _RE_COVER_IMG.sub(r'![]\1', text)


def _has_author_card_at_bottom(text: str) -> bool:
    tail = "\n".join(text.splitlines()[-_TAIL_LOOKBACK_LINES:])
    return ":::author-card" in tail


def _ensure_bottom_card(text: str, card_md: str = DEFAULT_BOTTOM_CARD) -> str:
    if _has_author_card_at_bottom(text):
        return text
    return text.rstrip() + "\n\n" + card_md.strip() + "\n"


def _ensure_mp_brand_in_last_card(
    text: str, mp_fields: str = DEFAULT_MP_FIELDS,
) -> str:
    """末尾 author-card 缺 mp_brand 字段时,就地补三行。

    只动**最后一个** :::author-card 块(典型场景:文末压轴卡)。
    其他 author-card(如文章中段插的)不动。
    """
    matches = list(_RE_AUTHOR_CARD_BLOCK.finditer(text))
    if not matches:
        return text
    last = matches[-1]
    block_body = last.group(2)
    if "mp_brand" in block_body:
        return text
    new_body = block_body.rstrip() + "\n" + mp_fields.strip()
    return text[:last.start(2)] + new_body + text[last.end(2):]


# 文末互动 CTA 三件套(2026-04-26 加 · 涨粉漏斗)
# Why:Agent 调研显示文末 CTA 引导提升「在看」率 30%+ · 转发率 15%+ ·
# 算法分数显著 → 推荐池 +。新号 30 天扶持期靠这个达阈值才进推荐。
# 插入位置:正文末尾 → 此 CTA → author-card → QR
DEFAULT_CTA_BLOCK = """
---

👉 **觉得有用?点「在看」+ 转发到群** · 你的一次互动 = 算法多推 100 个智辰

⭐ **设星标 · 不漏每天的 AI 红利信号**(订阅号信息流默认折叠 · 设⭐才置顶)

💬 **评论区告诉我**:你的具体场景 · 下篇案例可能就拆你的
""".strip()


def _ensure_cta_block(text: str, cta_md: str = DEFAULT_CTA_BLOCK) -> str:
    """正文末尾 + author-card 之前插 CTA 三件套 · 涨粉漏斗。

    幂等:tail 30 行含「设星标」或「点在看」就跳过(防重复)。
    无 author-card 兜底:append 到末尾(QR 块会在它之后再加)。
    """
    tail = "\n".join(text.splitlines()[-_TAIL_LOOKBACK_LINES:])
    if "设星标" in tail or "点「在看」" in tail or "点在看" in tail:
        return text
    matches = list(_RE_AUTHOR_CARD_BLOCK.finditer(text))
    if not matches:
        return text.rstrip() + "\n\n" + cta_md.strip() + "\n"
    # 插在最后一个 author-card 的 :::author-card 行之前
    first = matches[-1]
    insert_at = first.start()
    return text[:insert_at] + cta_md.strip() + "\n\n" + text[insert_at:]


# 文末必须带的 QR 二维码块 · 武汉群是用户私域核心入口(2026-04-25 加)
# 2026-05-02:QR path 提到 style.yaml(qr_zhichen / qr_openclaw 绝对路径)
# 修跨目录运行时 sanitize 注入的相对路径 images/qr-*.png 在外部目录找不到的 bug
_qr_config_cache: "dict | None" = None


def _load_qr_config() -> dict:
    """从 wewrite/style.yaml 读 QR 绝对路径 · 缓存 · 失败 fallback 到相对路径。

    style.yaml 中 top-level key:
      qr_zhichen: /absolute/path/to/qr-zhichen.png
      qr_openclaw: /absolute/path/to/qr-openclaw.png
    缺失时 fallback `images/qr-*.png`(只在 wewrite 自宅运行 OK)。
    """
    global _qr_config_cache
    if _qr_config_cache is not None:
        return _qr_config_cache

    config = {
        "zhichen": "images/qr-zhichen.png",
        "openclaw": "images/qr-openclaw.png",
    }

    # sanitize.py 在 wewrite/toolkit/ 下 · style.yaml 在 wewrite/ 下
    style_path = Path(__file__).resolve().parent.parent / "style.yaml"
    if style_path.exists():
        try:
            data = yaml.safe_load(style_path.read_text(encoding="utf-8")) or {}
            if data.get("qr_zhichen"):
                config["zhichen"] = str(data["qr_zhichen"])
            if data.get("qr_openclaw"):
                config["openclaw"] = str(data["qr_openclaw"])
        except (yaml.YAMLError, OSError):
            # 配置坏 · 不阻断 sanitize · 用 fallback 相对路径
            pass

    _qr_config_cache = config
    return config


def _build_qr_block(config: "dict | None" = None) -> str:
    """构造 QR markdown 块 · 路径来自 _load_qr_config(优先 style.yaml 绝对路径)。"""
    if config is None:
        config = _load_qr_config()
    return (
        f"### 👋 加我个人微信\n\n"
        f"![智辰老师聊 ai]({config['zhichen']})\n\n"
        f"### 🔥 武汉同城 · OpenClaw 创业群\n\n"
        f"![openclaw 武汉创业群]({config['openclaw']})"
    )


# 保留 DEFAULT_QR_BLOCK 常量(向后兼容 · 测试 / 老代码 import)
# 实际注入用 _build_qr_block() · 走 style.yaml 配置
DEFAULT_QR_BLOCK = _build_qr_block({
    "zhichen": "images/qr-zhichen.png",
    "openclaw": "images/qr-openclaw.png",
})


def _ensure_qr_block(text: str, qr_md: "str | None" = None) -> str:
    """末尾 author-card 之后插入 QR 二维码块(若尾部还没有)。

    qr_md 默认 None · 自动调 _build_qr_block() 从 style.yaml 读绝对路径(2026-05-02)。
    显式传 qr_md 字符串仍受支持(向后兼容 / 测试)。

    幂等:看尾部 30 行是否已含 `qr-openclaw` · 有就跳过。
    无 author-card 时也注入(直接 append 到末尾)· 防 shortform 兜底失败也能保 QR。
    """
    if qr_md is None:
        qr_md = _build_qr_block()
    tail = "\n".join(text.splitlines()[-_TAIL_LOOKBACK_LINES:])
    if "qr-openclaw" in tail:
        return text
    matches = list(_RE_AUTHOR_CARD_BLOCK.finditer(text))
    if not matches:
        # 无 author-card · 直接 append 到末尾
        return text.rstrip() + "\n\n" + qr_md.strip() + "\n"
    # 把 QR 块插到最后一个 author-card 闭合 ::: 之后
    last = matches[-1]
    insert_at = last.end()
    return text[:insert_at] + "\n\n" + qr_md.strip() + text[insert_at:]


# aipickgold UTM tracking · 用户从公众号点过来的流量统计
# 加 ?utm_source=mp&utm_date=YYYY-MM-DD 到 aipickgold.com 链接
# 末尾 nginx log 看 referer + query 即可
_RE_AIPICKGOLD_LINK = re.compile(
    r'(https?://(?:www\.)?aipickgold\.com[^\s\)\]"\']*)'
)


# =================================================================
# HTML 后处理:剥 aipickgold 编辑器糖背景色(2026-04-25 加)
# Why:aipickgold 服务端给 callout / quote / list-item 等加纯色 background
# 那是编辑器里的 viewing aid · 推到微信草稿箱后视觉杂乱 · 应该用微信原底。
# 保留含 linear-gradient 的 background(author-card brand 视觉)。
# =================================================================
def _strip_bg_keep_gradient(style: str) -> str:
    """从 inline style 删 background / background-color · 保留含 gradient 的。"""
    if not style:
        return style
    out = []
    for decl in style.split(";"):
        decl = decl.strip()
        if not decl:
            continue
        if ":" not in decl:
            out.append(decl)
            continue
        key = decl.split(":", 1)[0].strip().lower()
        val = decl.split(":", 1)[1].strip().lower()
        if key in ("background", "background-color"):
            if "gradient" in val:
                out.append(decl)
            # 否则丢(纯色背景 = 编辑器糖)
            continue
        out.append(decl)
    return "; ".join(out)


# 匹配 inline style="..."(含前导可选空格)· 非贪婪
# Why 不用 BeautifulSoup:aipickgold 给的 style 偶尔嵌双引号(eg "SF Mono") ·
# html.parser 在嵌套 " 处闭合 attribute · 后面字符全成 boolean attrs · 输出脏
# 纯 regex 在 style="..." 字符串边界处理 · 不 parse 结构 · 对不规范 HTML 也稳
_STYLE_ATTR_RE = re.compile(r' ?style="([^"]*)"', re.DOTALL)


def strip_decorative_backgrounds(html: str) -> str:
    """剥 aipickgold 编辑器糖背景色 · 让微信草稿用原底。

    保留含 linear-gradient / radial-gradient 的 background(author-card brand 视觉)。
    用纯 regex 处理 style="..." · 不 parse HTML 结构 · 对 aipickgold 不规范 HTML 容错。
    幂等。
    """
    if not html or "background" not in html.lower():
        return html

    def _replace(m: re.Match) -> str:
        new_style = _strip_bg_keep_gradient(m.group(1))
        if not new_style.strip():
            return ""  # 空 style attr 整个删(连同前导空格)
        return f' style="{new_style}"'

    return _STYLE_ATTR_RE.sub(_replace, html)


def _add_utm_to_aipickgold(md: str, *, date_str: str | None = None) -> str:
    """给所有 aipickgold.com 链接加 UTM 参数 · 已有 utm 的不重加。"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    utm = f"utm_source=mp&utm_date={date_str}"

    def _add(m: re.Match) -> str:
        url = m.group(1)
        # 已经有 utm_source · 不动
        if "utm_source=" in url:
            return url
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{utm}"

    return _RE_AIPICKGOLD_LINK.sub(_add, md)


def sanitize_for_publish(
    md: str,
    *,
    bottom_card: str | None = None,
    shortform: bool = False,
) -> str:
    """四件套清理 · 幂等。

    五件套 + 涨粉漏斗 UTM + QR 兜底:
      1. _strip_leading_h1
      2. _clear_cover_alt
      3. _ensure_bottom_card
      4. _ensure_mp_brand_in_last_card
      5. _ensure_qr_block(2026-04-25 加 · 武汉群 + 个人微信 QR 兜底)
      6. _add_utm_to_aipickgold(2026-04-23 加 · 涨粉追踪)

    Args:
        bottom_card: 自定义末尾卡片 · None 时按 shortform 决定走 DEFAULT 还是 SHORTFORM
        shortform: True 时走短文 mini 版 author-card(2026-04-23 加)
    """
    if bottom_card is None:
        bottom_card = DEFAULT_BOTTOM_CARD_SHORTFORM if shortform else DEFAULT_BOTTOM_CARD
    md = _strip_leading_h1(md)
    md = _clear_cover_alt(md)
    md = _ensure_bottom_card(md, bottom_card)
    md = _ensure_mp_brand_in_last_card(md)
    md = _ensure_cta_block(md)   # 2026-04-26 · CTA 三件套(在 author-card 之前)
    md = _ensure_qr_block(md)
    md = _add_utm_to_aipickgold(md)
    return md


def prepare_for_publish(
    md_path: Path,
    *,
    suffix: str = "._publish.md",
    shortform: bool = False,
) -> Path:
    """读取 md_path · sanitize · 写到同目录的 <stem>._publish.md · 返回新路径。

    如果清理后内容与原文件一致,直接返回原路径(不写临时文件)。
    临时文件与原文件同目录,确保 markdown 内的相对图片路径仍可解析。

    Args:
        shortform: True 时用短文 mini author-card 兜底(2026-04-23 加)
    """
    src = md_path.read_text(encoding="utf-8")
    cleaned = sanitize_for_publish(src, shortform=shortform)
    if cleaned == src:
        return md_path
    out = md_path.with_name(md_path.stem + suffix)
    out.write_text(cleaned, encoding="utf-8")
    return out
