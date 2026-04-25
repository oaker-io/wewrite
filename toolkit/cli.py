#!/usr/bin/env python3
"""
CLI entry point for WeWrite.

Usage:
    python cli.py preview article.md --theme professional-clean
    python cli.py publish article.md --appid wx123 --secret abc123
    python cli.py themes
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

import yaml

from converter import WeChatConverter, preview_html
from theme import load_theme, list_themes
from wechat_api import get_access_token, upload_image, upload_thumb
from publisher import create_draft, create_draft_bundle, create_image_post

# Config file search order
CONFIG_PATHS = [
    Path.cwd() / "config.yaml",
    Path(__file__).parent.parent / "config.yaml",  # skill root
    Path(__file__).parent / "config.yaml",          # toolkit dir
    Path.home() / ".config" / "wewrite" / "config.yaml",
]


def load_config() -> dict:
    """Load config from first found config.yaml."""
    for p in CONFIG_PATHS:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return {}


def _build_converter(engine, theme_name, font_size=None):
    """Return (converter, theme_obj_or_none). Supports 'native' and 'md2wx'."""
    if engine == "md2wx":
        from converter_md2wx import Md2wxConverter
        return Md2wxConverter(theme_name=theme_name, font_size=font_size), None
    theme = load_theme(theme_name)
    return WeChatConverter(theme=theme), theme


def cmd_preview(args):
    """Generate HTML preview and open in browser."""
    converter, theme = _build_converter(args.engine, args.theme, getattr(args, "font_size", None))
    result = converter.convert_file(args.input)

    # md2wx returns complete HTML; native returns body-only needing preview_html wrapping
    # 2026-04-25:剥 aipickgold 编辑器糖背景色 · 让 preview 真实反映 publish 后样子
    from sanitize import strip_decorative_backgrounds
    if args.engine == "md2wx":
        full_html = strip_decorative_backgrounds(result.html)
    else:
        full_html = preview_html(strip_decorative_backgrounds(result.html), theme)

    # Write to temp file
    input_path = Path(args.input)
    output = args.output or str(input_path.with_suffix(".html"))
    Path(output).write_text(full_html, encoding="utf-8")

    print(f"Title: {result.title}")
    print(f"Digest: {result.digest}")
    print(f"Images: {len(result.images)}")
    print(f"Output: {output}")

    if not args.no_open:
        webbrowser.open(f"file://{Path(output).absolute()}")
        print("Opened in browser.")


def cmd_publish(args):
    """Convert, upload images, and create WeChat draft."""
    cfg = load_config()
    wechat_cfg = cfg.get("wechat", {})

    # Resolve from CLI args → config.yaml fallback
    appid = args.appid or wechat_cfg.get("appid")
    secret = args.secret or wechat_cfg.get("secret")
    theme_name = args.theme or cfg.get("theme", "professional-clean")
    author = args.author or wechat_cfg.get("author")

    if not appid or not secret:
        print("Error: --appid and --secret required (or set in config.yaml)", file=sys.stderr)
        sys.exit(1)

    # 发布前 sanitize · 默认开 · `--no-sanitize` 关。
    # 修复 republish/直接调 cli 时绕过 sanitize 导致 author-card 不渲染。
    input_path = Path(args.input)
    if not getattr(args, "no_sanitize", False):
        from sanitize import prepare_for_publish
        sanitized = prepare_for_publish(input_path)
        if sanitized != input_path:
            print(f"Sanitized: {sanitized.name}")
        input_path = sanitized

    converter, _theme = _build_converter(args.engine, theme_name, getattr(args, "font_size", None))
    result = converter.convert_file(str(input_path))

    print(f"Title: {result.title}")
    print(f"Digest: {result.digest}")
    print(f"Images found: {len(result.images)}")
    print(f"Engine: {args.engine}")

    # Get access token
    token = get_access_token(appid, secret)
    print("Access token obtained.")

    # Upload images referenced in article and replace src
    # Resolve relative paths against the markdown file's directory
    md_dir = input_path.resolve().parent
    html = result.html
    # 2026-04-25:剥 aipickgold 编辑器糖背景色 · 保留 linear-gradient(author-card brand 视觉)
    from sanitize import strip_decorative_backgrounds
    html = strip_decorative_backgrounds(html)
    for img_src in result.images:
        if img_src.startswith(("http://", "https://")):
            print(f"Skipping remote image: {img_src}")
            continue

        # Try: absolute → relative to CWD → relative to markdown file
        img_path = Path(img_src)
        if not img_path.is_absolute():
            if not img_path.exists():
                img_path = md_dir / img_src

        if img_path.exists():
            print(f"Uploading image: {img_src}")
            wechat_url = upload_image(token, str(img_path))
            html = html.replace(img_src, wechat_url)
            print(f"  -> {wechat_url}")
        else:
            print(f"Warning: image not found: {img_src} (searched {md_dir})")

    # Upload cover / thumb
    # 优先级:--thumb (1:1 看一看小图) > --cover (2.35:1 大封面)
    # 看一看 feed 用 thumb_media_id 显示右侧 80×80 缩略 · 1:1 cover-square 在小尺寸下文字更清晰
    # 没传 --thumb 但传了 --cover 时 · 用 cover 当 thumb(向后兼容)
    thumb_media_id = None
    thumb_path = getattr(args, "thumb", None)
    if thumb_path:
        print(f"Uploading thumb (1:1 看一看小图): {thumb_path}")
        thumb_media_id = upload_thumb(token, thumb_path)
        print(f"  -> media_id: {thumb_media_id}")
    elif args.cover:
        print(f"Uploading cover (作 thumb): {args.cover}")
        thumb_media_id = upload_thumb(token, args.cover)
        print(f"  -> media_id: {thumb_media_id}")

    # 评论开关(默认开 · --no-comments 关 · --fans-only-comments 只允许粉丝评论)
    open_comment = not getattr(args, "no_comments", False)
    fans_only_comment = getattr(args, "fans_only_comments", False)

    # Create draft
    title = args.title or result.title or input_path.stem
    digest = args.digest or result.digest
    draft = create_draft(
        access_token=token,
        title=title,
        html=html,
        digest=digest,
        thumb_media_id=thumb_media_id,
        author=author,
        open_comment=open_comment,
        fans_only_comment=fans_only_comment,
    )

    print(f"\nDraft created! media_id: {draft.media_id}")
    print(f"  comments: {'开' if open_comment else '关'} · fans_only: {'是' if fans_only_comment else '否'}")


def _process_one_article(
    md_path: Path,
    *,
    engine: str,
    theme_name: str,
    font_size,
    cover: str | None,
    thumb: str | None,
    title: str | None,
    digest: str | None,
    author: str | None,
    no_sanitize: bool,
    shortform: bool,
    token: str,
) -> dict:
    """处理单篇 md(sanitize → convert → 上传图 → 上传 cover/thumb)· 返回 article dict for create_draft_bundle。

    bundle 流程的子函数 · 不直接调 API。
    """
    if not no_sanitize:
        from sanitize import prepare_for_publish
        sanitized = prepare_for_publish(md_path, shortform=shortform)
        if sanitized != md_path:
            print(f"  Sanitized [{md_path.name}]: -> {sanitized.name}")
        md_path = sanitized

    converter, _theme = _build_converter(engine, theme_name, font_size)
    result = converter.convert_file(str(md_path))
    print(f"  Title: {result.title}")
    print(f"  Digest: {result.digest}")
    print(f"  Images: {len(result.images)} · Engine: {engine}")

    md_dir = md_path.resolve().parent
    html = result.html
    # 2026-04-25:同 publish · 剥 aipickgold 编辑器糖背景色
    from sanitize import strip_decorative_backgrounds
    html = strip_decorative_backgrounds(html)
    for img_src in result.images:
        if img_src.startswith(("http://", "https://")):
            continue
        img_path = Path(img_src)
        if not img_path.is_absolute() and not img_path.exists():
            img_path = md_dir / img_src
        if img_path.exists():
            wechat_url = upload_image(token, str(img_path))
            html = html.replace(img_src, wechat_url)
        else:
            print(f"  Warning: image not found: {img_src}")

    thumb_media_id = None
    if thumb:
        print(f"  Uploading thumb (1:1): {thumb}")
        thumb_media_id = upload_thumb(token, thumb)
    elif cover:
        print(f"  Uploading cover (作 thumb): {cover}")
        thumb_media_id = upload_thumb(token, cover)

    return {
        "title": (title or result.title or md_path.stem)[:64],
        "html": html,
        "digest": (digest or result.digest)[:120],
        "thumb_media_id": thumb_media_id,
        "author": author,
    }


def cmd_publish_bundle(args):
    """一次推 1-8 篇 (主推 + N 副推) · 占同一次群发配额。

    用法:
      cli.py publish-bundle \\
        --main output/2026-04-23-cursor.md --main-cover output/images/cover.png \\
                                           --main-thumb output/images/cover-square.png \\
        --companion output/2026-04-23-cursor-quick.md --companion-thumb output/images/cover-square.png \\
        --companion output/2026-04-23-cursor-pitfall.md --companion-thumb output/images/cover-square2.png \\
        --engine md2wx --theme focus-navy

    默认评论开 · 全部允许非粉丝评论(涨粉漏斗)。
    """
    cfg = load_config()
    wechat_cfg = cfg.get("wechat", {})

    appid = args.appid or wechat_cfg.get("appid")
    secret = args.secret or wechat_cfg.get("secret")
    theme_name = args.theme or cfg.get("theme", "professional-clean")
    author = args.author or wechat_cfg.get("author")

    if not appid or not secret:
        print("Error: --appid and --secret required (or set in config.yaml)", file=sys.stderr)
        sys.exit(1)

    if not args.main:
        print("Error: --main 必填(主推 md 路径)", file=sys.stderr)
        sys.exit(1)

    # 副推数组(--companion 可重复)
    companions = args.companion or []
    if len(companions) > 7:
        print(f"Error: 副推最多 7 篇(微信总数限 8)· 收到 {len(companions)} 篇", file=sys.stderr)
        sys.exit(1)

    # thumb / cover 副推数组(必须跟 --companion 一一对应)
    companion_thumbs = args.companion_thumb or []
    companion_covers = args.companion_cover or []
    if companion_thumbs and len(companion_thumbs) != len(companions):
        print(f"Error: --companion-thumb 数 {len(companion_thumbs)} 跟 --companion 数 {len(companions)} 不匹配", file=sys.stderr)
        sys.exit(1)
    if companion_covers and len(companion_covers) != len(companions):
        print(f"Error: --companion-cover 数 {len(companion_covers)} 跟 --companion 数 {len(companions)} 不匹配", file=sys.stderr)
        sys.exit(1)

    token = get_access_token(appid, secret)
    print(f"Access token obtained · 准备 publish-bundle (1 主 + {len(companions)} 副)")

    # 主推
    print(f"\n[main] {args.main}")
    main_article = _process_one_article(
        Path(args.main),
        engine=args.engine, theme_name=theme_name, font_size=getattr(args, "font_size", None),
        cover=args.main_cover, thumb=args.main_thumb,
        title=args.main_title, digest=args.main_digest,
        author=author, no_sanitize=args.no_sanitize,
        shortform=False,  # 主推用完整 author-card
        token=token,
    )

    # 副推(全部当短文 sanitize · mini author-card)
    bundle_articles = [main_article]
    for i, comp_md in enumerate(companions):
        thumb = companion_thumbs[i] if companion_thumbs else None
        cover = companion_covers[i] if companion_covers else None
        print(f"\n[companion-{i+1}] {comp_md}")
        comp_article = _process_one_article(
            Path(comp_md),
            engine=args.engine, theme_name=theme_name, font_size=getattr(args, "font_size", None),
            cover=cover, thumb=thumb,
            title=None, digest=None,
            author=author, no_sanitize=args.no_sanitize,
            shortform=True,  # 副推用 mini author-card
            token=token,
        )
        bundle_articles.append(comp_article)

    print(f"\n→ create_draft_bundle ({len(bundle_articles)} 篇)...")
    draft = create_draft_bundle(token, bundle_articles)
    print(f"\nBundle draft created! media_id: {draft.media_id}")
    print(f"  共 {len(bundle_articles)} 篇 (1 main + {len(companions)} companions)")
    print(f"  评论:全部默认开 · 允许非粉丝评论")
    print(f"  这 1 个 media_id 占用 1 次群发配额(订阅号每日 1 次)")


def cmd_themes(args):
    """List available themes."""
    names = list_themes()
    for name in names:
        theme = load_theme(name)
        print(f"  {name:24s} {theme.description}")


def cmd_image_post(args):
    """Create a WeChat image post (小绿书) from image files."""
    cfg = load_config()
    wechat_cfg = cfg.get("wechat", {})

    appid = args.appid or wechat_cfg.get("appid")
    secret = args.secret or wechat_cfg.get("secret")

    if not appid or not secret:
        print("Error: --appid and --secret required (or set in config.yaml)", file=sys.stderr)
        sys.exit(1)

    images = args.images
    if not images:
        print("Error: at least 1 image required", file=sys.stderr)
        sys.exit(1)
    if len(images) > 20:
        print(f"Error: max 20 images, got {len(images)}", file=sys.stderr)
        sys.exit(1)

    token = get_access_token(appid, secret)
    print(f"Uploading {len(images)} images as permanent materials...")

    media_ids = []
    for img_path in images:
        p = Path(img_path)
        if not p.exists():
            print(f"Error: image not found: {img_path}", file=sys.stderr)
            sys.exit(1)
        print(f"  Uploading: {p.name}")
        mid = upload_thumb(token, str(p))
        media_ids.append(mid)
        print(f"    -> {mid}")

    title = args.title
    if len(title) > 32:
        print(f"Warning: title truncated to 32 chars (was {len(title)})")
        title = title[:32]

    content = args.content or ""

    result = create_image_post(
        access_token=token,
        title=title,
        image_media_ids=media_ids,
        content=content,
        open_comment=True,
    )

    print(f"\nImage post draft created!")
    print(f"  media_id: {result.media_id}")
    print(f"  images: {result.image_count}")
    print(f"  title: {title}")
    print(f"  请到公众号后台草稿箱检查并发布")


def cmd_gallery(args):
    """Render all themes side by side in a browser gallery."""
    from concurrent.futures import ThreadPoolExecutor

    # Use provided markdown or a built-in sample
    if args.input:
        md_text = Path(args.input).read_text(encoding="utf-8")
    else:
        md_text = _gallery_sample_markdown()

    names = list_themes()
    results = {}

    def render_theme(name):
        theme = load_theme(name)
        converter = WeChatConverter(theme=theme)
        result = converter.convert(md_text)
        return name, theme.description, result.html

    # Parallel rendering
    with ThreadPoolExecutor(max_workers=8) as pool:
        for name, desc, html in pool.map(lambda n: render_theme(n), names):
            results[name] = (desc, html)

    # Build gallery HTML
    gallery_html = _build_gallery_html(results, names)
    output = args.output or "/tmp/wewrite-gallery.html"
    Path(output).write_text(gallery_html, encoding="utf-8")
    print(f"Gallery: {output} ({len(names)} themes)")

    if not args.no_open:
        webbrowser.open(f"file://{Path(output).absolute()}")


def cmd_learn_theme(args):
    """Learn a theme from a WeChat article URL."""
    import subprocess
    script = Path(__file__).parent.parent / "scripts" / "learn_theme.py"
    cmd = [sys.executable, str(script), args.url, "--name", args.name]
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def _gallery_sample_markdown():
    return """# 示例文章标题

## 第一部分

这是一段正常的文章内容，用来展示不同主题的排版效果。WeWrite 支持多种排版主题，每种都有独特的视觉风格。

说实话，选主题这件事——看截图永远不如看实际渲染效果。

## 关键数据

| 指标 | 数值 | 变化 |
|------|------|------|
| 阅读量 | 12,580 | +23% |
| 分享率 | 4.7% | +0.8% |
| 完读率 | 68% | -2% |

## 代码示例

```python
def hello():
    print("Hello, WeWrite!")
```

> 好的排版不是让读者注意到设计，而是让读者忘记设计，只记住内容。

## 列表展示

- 第一个要点：简洁是设计的灵魂
- 第二个要点：一致性比创意更重要
- 第三个要点：移动端体验优先

**加粗文本**和*斜体文本*的样式也需要关注。

最后这段用来展示文章结尾的留白和间距效果。一篇好文章的结尾，应该像一首好歌的最后一个音符——恰到好处地收束。
"""


def _join_newline(items):
    """Join items with comma + newline (workaround for f-string limitation)."""
    return ",\n".join(items)


def _build_gallery_html(results, names):
    cards = []
    for name in names:
        desc, html = results[name]
        # Escape for embedding in JS
        escaped_html = html.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')
        cards.append(f"""
        <div class="theme-card" onclick="selectTheme('{name}')">
          <div class="theme-name">{name}</div>
          <div class="theme-desc">{desc}</div>
          <div class="phone-frame">
            <div class="phone-content" id="preview-{name}">{html}</div>
          </div>
          <button class="copy-btn" onclick="event.stopPropagation(); copyHTML('{name}')">复制 HTML</button>
        </div>""")

    # Store HTML data for copy
    data_entries = []
    for name in names:
        desc, html = results[name]
        safe = html.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
        data_entries.append(f"  '{name}': '{safe}'")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WeWrite 主题画廊</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0f0f0f; color: #fff; }}
.header {{ text-align: center; padding: 40px 20px 20px; }}
.header h1 {{ font-size: 28px; font-weight: 700; }}
.header p {{ color: #888; margin-top: 8px; font-size: 15px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 24px; padding: 24px; max-width: 1440px; margin: 0 auto; }}
.theme-card {{ background: #1a1a1a; border-radius: 12px; padding: 16px; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }}
.theme-card:hover {{ transform: translateY(-4px); box-shadow: 0 8px 24px rgba(0,0,0,0.4); }}
.theme-name {{ font-size: 16px; font-weight: 700; margin-bottom: 4px; }}
.theme-desc {{ font-size: 13px; color: #888; margin-bottom: 12px; }}
.phone-frame {{ background: #fff; border-radius: 8px; overflow: hidden; max-height: 480px; overflow-y: auto; }}
.phone-content {{ padding: 16px; font-size: 14px; transform: scale(0.85); transform-origin: top left; width: 118%; }}
.copy-btn {{ margin-top: 12px; width: 100%; padding: 8px; background: #333; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }}
.copy-btn:hover {{ background: #555; }}
.toast {{ position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%); background: #333; color: #fff; padding: 10px 24px; border-radius: 8px; font-size: 14px; display: none; z-index: 999; }}
</style>
</head>
<body>
<div class="header">
  <h1>WeWrite 主题画廊</h1>
  <p>{len(names)} 个主题 · 点击卡片查看大图 · 点击「复制 HTML」直接粘贴到公众号编辑器</p>
</div>
<div class="grid">
{''.join(cards)}
</div>
<div class="toast" id="toast">已复制到剪贴板</div>
<script>
const themeData = {{
{_join_newline(data_entries)}
}};
function copyHTML(name) {{
  const html = themeData[name];
  if (html) {{
    navigator.clipboard.writeText(html).then(() => {{
      const t = document.getElementById('toast');
      t.style.display = 'block';
      setTimeout(() => t.style.display = 'none', 1500);
    }});
  }}
}}
function selectTheme(name) {{
  localStorage.setItem('wewrite-theme', name);
  // Scroll to card for visual feedback
  const el = document.getElementById('preview-' + name);
  if (el) el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
}}
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(
        prog="wewrite",
        description="Markdown to WeChat HTML converter and publisher",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # preview
    p_preview = sub.add_parser("preview", help="Generate HTML and open in browser")
    p_preview.add_argument("input", help="Markdown file path")
    p_preview.add_argument("-t", "--theme", default="professional-clean",
                           help="Theme name (native: English IDs; md2wx: Chinese IDs like 经典-暖橙)")
    p_preview.add_argument("-o", "--output", help="Output HTML file path")
    p_preview.add_argument("--no-open", action="store_true", help="Don't open browser")
    p_preview.add_argument("--engine", choices=["native", "md2wx"], default="native",
                           help="Rendering engine: 'native' (16 themes, zero-dep) or 'md2wx' (40 themes, external CLI)")
    p_preview.add_argument("--font-size", default=None, help="Font size (md2wx only, e.g. 16px)")

    # publish
    p_publish = sub.add_parser("publish", help="Convert and publish as WeChat draft")
    p_publish.add_argument("input", help="Markdown file path")
    p_publish.add_argument("-t", "--theme", default=None, help="Theme name")
    p_publish.add_argument("--appid", default=None, help="WeChat AppID (or set in config.yaml)")
    p_publish.add_argument("--secret", default=None, help="WeChat AppSecret (or set in config.yaml)")
    p_publish.add_argument("--cover", help="Cover image file path")
    p_publish.add_argument("--title", help="Override article title")
    p_publish.add_argument("--author", default=None, help="Article author")
    p_publish.add_argument("--digest", default=None, help="Override article digest (≤120 UTF-8 bytes)")
    p_publish.add_argument("--engine", choices=["native", "md2wx"], default="native",
                           help="Rendering engine: 'native' (16 themes) or 'md2wx' (40 themes)")
    p_publish.add_argument("--font-size", default=None, help="Font size (md2wx only, e.g. 16px)")
    p_publish.add_argument("--no-sanitize", action="store_true",
                           help="Skip H1/cover-alt/author-card auto-sanitize (default off)")
    p_publish.add_argument("--thumb", default=None,
                           help="1:1 看一看小图(优先 · 用作 thumb_media_id · 推荐 1080×1080)")
    p_publish.add_argument("--no-comments", action="store_true",
                           help="关闭评论(默认开评论)")
    p_publish.add_argument("--fans-only-comments", action="store_true",
                           help="只允许粉丝评论(默认允许所有人 · 拉路过转化)")

    # publish-bundle (主推 + 0-7 副推 · 占 1 次群发配额)
    p_bundle = sub.add_parser("publish-bundle",
                              help="一次推 1 主 + 0-7 副 · 占 1 次群发配额(订阅号每日 1 次)")
    p_bundle.add_argument("--main", required=True, help="主推 md 路径")
    p_bundle.add_argument("--main-cover", help="主推大封面 (2.35:1)")
    p_bundle.add_argument("--main-thumb", help="主推 1:1 看一看小图(优先于 main-cover)")
    p_bundle.add_argument("--main-title", help="主推标题(覆盖 H1)")
    p_bundle.add_argument("--main-digest", help="主推摘要")
    p_bundle.add_argument("--companion", action="append", default=[],
                          help="副推 md 路径(可多次 · 最多 7 篇)")
    p_bundle.add_argument("--companion-thumb", action="append", default=[],
                          help="副推 1:1 thumb(必须跟 --companion 数对齐)")
    p_bundle.add_argument("--companion-cover", action="append", default=[],
                          help="副推大封面(可选 · 一般用 thumb)")
    p_bundle.add_argument("-t", "--theme", default=None, help="主题名")
    p_bundle.add_argument("--engine", choices=["native", "md2wx"], default="md2wx",
                          help="渲染引擎")
    p_bundle.add_argument("--font-size", default=None)
    p_bundle.add_argument("--appid", default=None)
    p_bundle.add_argument("--secret", default=None)
    p_bundle.add_argument("--author", default=None)
    p_bundle.add_argument("--no-sanitize", action="store_true",
                          help="跳过 sanitize(默认开 · 主推完整 card · 副推 mini card)")

    # themes
    sub.add_parser("themes", help="List available themes")

    # image-post (小绿书)
    p_imgpost = sub.add_parser("image-post", help="Create WeChat image post (小绿书)")
    p_imgpost.add_argument("images", nargs="+", help="Image file paths (1-20, first = cover)")
    p_imgpost.add_argument("-t", "--title", required=True, help="Post title (max 32 chars)")
    p_imgpost.add_argument("-c", "--content", default="", help="Plain text description (max ~1000 chars)")
    p_imgpost.add_argument("--appid", default=None, help="WeChat AppID")
    p_imgpost.add_argument("--secret", default=None, help="WeChat AppSecret")

    # gallery
    p_gallery = sub.add_parser("gallery", help="Open theme gallery in browser")
    p_gallery.add_argument("input", nargs="?", default=None, help="Markdown file (optional, uses sample if omitted)")
    p_gallery.add_argument("-o", "--output", help="Output HTML file path")
    p_gallery.add_argument("--no-open", action="store_true", help="Don't open browser")

    # learn-theme
    p_learn = sub.add_parser("learn-theme", help="Learn formatting theme from a WeChat article URL")
    p_learn.add_argument("url", help="WeChat article URL")
    p_learn.add_argument("--name", required=True, help="Theme name")

    args = parser.parse_args()

    try:
        if args.command == "preview":
            cmd_preview(args)
        elif args.command == "publish":
            cmd_publish(args)
        elif args.command == "publish-bundle":
            cmd_publish_bundle(args)
        elif args.command == "themes":
            cmd_themes(args)
        elif args.command == "image-post":
            cmd_image_post(args)
        elif args.command == "gallery":
            cmd_gallery(args)
        elif args.command == "learn-theme":
            cmd_learn_theme(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
