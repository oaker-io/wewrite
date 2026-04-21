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
from pathlib import Path

# 末尾压轴卡片 · style.yaml 的 brand 字段 = 宸的 AI 掘金笔记
DEFAULT_BOTTOM_CARD = """
:::author-card
name: 智辰老师
tagline: 独立开发者 · AI 非共识观察者 · openclaw 武汉创业群群主
bio: 每天一篇 AI 行业非共识解读。不追热搜情绪,只挖热搜之下被忽略的真信号。从 Cursor 估值到豆包"豆脚",帮你看清下一波该上车还是该撤。
mp_brand: 宸的 AI 掘金笔记
mp_desc: 记录 AI Agent 与工具的真实使用过程与长期价值。
mp_meta: 关注获取每日 AI 非共识 · 掘金看智辰
tags: [AI 非共识, AI Coding, 武汉创业, Skill 开发]
footer: 扫码加我微信备注「AI Coding」· 我会拉你进读者群 · 武汉朋友可扫下方 openclaw 群码
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
    "mp_meta: 关注获取每日 AI 非共识 · 掘金看智辰"
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


def sanitize_for_publish(md: str, *, bottom_card: str = DEFAULT_BOTTOM_CARD) -> str:
    """四件套清理 · 幂等。"""
    md = _strip_leading_h1(md)
    md = _clear_cover_alt(md)
    md = _ensure_bottom_card(md, bottom_card)
    md = _ensure_mp_brand_in_last_card(md)
    return md


def prepare_for_publish(md_path: Path, *, suffix: str = "._publish.md") -> Path:
    """读取 md_path · sanitize · 写到同目录的 <stem>._publish.md · 返回新路径。

    如果清理后内容与原文件一致,直接返回原路径(不写临时文件)。
    临时文件与原文件同目录,确保 markdown 内的相对图片路径仍可解析。
    """
    src = md_path.read_text(encoding="utf-8")
    cleaned = sanitize_for_publish(src)
    if cleaned == src:
        return md_path
    out = md_path.with_name(md_path.stem + suffix)
    out.write_text(cleaned, encoding="utf-8")
    return out
