"""Smoke + unit tests for scripts/workflow/sanitize.py + author_card mp_brand 渲染。

跑法:
  cd /Users/mahaochen/wechatgzh/wewrite
  venv/bin/python3 -m unittest tests.test_sanitize -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "toolkit"))

from sanitize import (
    sanitize_for_publish,
    prepare_for_publish,
    DEFAULT_BOTTOM_CARD,
    _strip_leading_h1,
    _clear_cover_alt,
    _has_author_card_at_bottom,
    _ensure_mp_brand_in_last_card,
)
from author_card import preprocess_author_card


# -----------------------------------------------------------------
# 1. _strip_leading_h1
# -----------------------------------------------------------------
class StripH1(unittest.TestCase):
    def test_drops_first_h1_and_blank(self):
        md = "# 标题\n\n正文第一段\n\n## H2\n二段\n"
        out = _strip_leading_h1(md)
        self.assertNotIn("# 标题", out)
        self.assertIn("正文第一段", out)
        self.assertIn("## H2", out)

    def test_preserves_h2_h3(self):
        md = "## H2\n### H3\n# H1 in middle 不动\n"
        out = _strip_leading_h1(md)
        # 首个 H1 在中间 · 仍然会被去掉(规则:首个 H1)
        self.assertNotIn("# H1 in middle", out)
        self.assertIn("## H2", out)
        self.assertIn("### H3", out)

    def test_no_h1_unchanged(self):
        md = "正文\n\n## H2\n"
        self.assertEqual(_strip_leading_h1(md), md)

    def test_idempotent(self):
        md = "# 标题\n\n正文\n"
        once = _strip_leading_h1(md)
        twice = _strip_leading_h1(once)
        self.assertEqual(once, twice)


# -----------------------------------------------------------------
# 2. _clear_cover_alt
# -----------------------------------------------------------------
class ClearCoverAlt(unittest.TestCase):
    def test_strips_chinese_alt(self):
        self.assertEqual(
            _clear_cover_alt("![封面](images/cover.png)"),
            "![](images/cover.png)",
        )

    def test_strips_english_alt(self):
        self.assertEqual(
            _clear_cover_alt("![Cover](cover.jpg)"),
            "![](cover.jpg)",
        )

    def test_leaves_chart_images(self):
        md = "![图表 1](images/chart-1.png)"
        self.assertEqual(_clear_cover_alt(md), md)

    def test_leaves_qr_images(self):
        md = "![智辰老师聊 ai](images/qr-zhichen.png)"
        self.assertEqual(_clear_cover_alt(md), md)

    def test_idempotent(self):
        md = "![封面](images/cover.png)"
        once = _clear_cover_alt(md)
        twice = _clear_cover_alt(once)
        self.assertEqual(once, twice)


# -----------------------------------------------------------------
# 3. _has_author_card_at_bottom
# -----------------------------------------------------------------
class HasAuthorCard(unittest.TestCase):
    def test_card_at_end(self):
        md = "正文\n\n:::author-card\nname: x\n:::\n"
        self.assertTrue(_has_author_card_at_bottom(md))

    def test_no_card(self):
        md = "正文\n\n## 结尾\n"
        self.assertFalse(_has_author_card_at_bottom(md))

    def test_card_only_at_top_far_from_bottom(self):
        # 卡片在开头 + 30+ 行正文 → 末尾 30 行内没有 → False
        body = "\n".join([f"line {i}" for i in range(50)])
        md = ":::author-card\nname: x\n:::\n\n" + body
        self.assertFalse(_has_author_card_at_bottom(md))


# -----------------------------------------------------------------
# 4. sanitize_for_publish 全流程
# -----------------------------------------------------------------
class SanitizeFullFlow(unittest.TestCase):
    def test_full_three_fixes(self):
        md = (
            "# 标题重复了\n\n"
            "![封面](images/cover.png)\n\n"
            "正文第一段。\n"
        )
        out = sanitize_for_publish(md)
        self.assertNotIn("# 标题重复了", out)
        self.assertNotIn("![封面]", out)
        self.assertIn("![](images/cover.png)", out)
        self.assertIn(":::author-card", out)
        self.assertIn("智辰老师", out)
        self.assertIn("mp_brand: 宸的 AI 掘金笔记", out)

    def test_keeps_existing_card(self):
        md = (
            "正文\n\n"
            ":::author-card\nname: 自定义\n:::\n"
        )
        out = sanitize_for_publish(md)
        self.assertEqual(out.count(":::author-card"), 1)
        self.assertIn("name: 自定义", out)

    def test_idempotent(self):
        md = (
            "# H1\n\n![封面](images/cover.png)\n\n正文\n"
        )
        once = sanitize_for_publish(md)
        twice = sanitize_for_publish(once)
        self.assertEqual(once, twice)


# -----------------------------------------------------------------
# 5. prepare_for_publish 文件 IO
# -----------------------------------------------------------------
class PrepareFileIO(unittest.TestCase):
    def test_clean_file_returns_self(self):
        # "clean" 现在意味着:无 H1 / 无 cover alt / 末尾 author-card 已含 mp_brand
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "clean.md"
            p.write_text(
                "正文\n\n"
                ":::author-card\n"
                "name: x\n"
                "mp_brand: 宸的 AI 掘金笔记\n"
                ":::\n",
                encoding="utf-8",
            )
            out = prepare_for_publish(p)
            self.assertEqual(out, p)

    def test_dirty_file_writes_publish_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "dirty.md"
            p.write_text("# H1\n\n正文\n", encoding="utf-8")
            out = prepare_for_publish(p)
            self.assertNotEqual(out, p)
            self.assertTrue(out.exists())
            self.assertTrue(out.name.endswith("._publish.md"))
            content = out.read_text(encoding="utf-8")
            self.assertNotIn("# H1", content)
            self.assertIn(":::author-card", content)
            # 原文件不变
            self.assertIn("# H1", p.read_text(encoding="utf-8"))


# -----------------------------------------------------------------
# 6. author_card mp_brand 嵌入卡渲染
# -----------------------------------------------------------------
class AuthorCardMpBrand(unittest.TestCase):
    def test_mp_card_rendered(self):
        md = (
            ":::author-card\n"
            "name: 智辰老师\n"
            "mp_brand: 宸的 AI 掘金笔记\n"
            "mp_desc: 记录 AI Agent 与工具的真实使用过程与长期价值。\n"
            "mp_meta: 关注获取每日 AI 非共识\n"
            ":::"
        )
        html = preprocess_author_card(md, theme_id="focus-navy")
        self.assertIn("宸的 AI 掘金笔记", html)
        self.assertIn("记录 AI Agent", html)
        self.assertIn("关注获取每日 AI 非共识", html)
        # 视觉占位的箭头
        self.assertIn("›", html)

    def test_no_mp_card_when_brand_absent(self):
        md = (
            ":::author-card\n"
            "name: 普通卡\n"
            "bio: 没有 mp\n"
            ":::"
        )
        html = preprocess_author_card(md)
        # 没有 mp_brand · 不应渲染嵌入卡(箭头不存在)
        # 但 name/bio 仍在
        self.assertIn("普通卡", html)
        self.assertIn("没有 mp", html)
        self.assertNotIn("mp_brand", html)

    def test_mp_id_emits_mp_common_profile(self):
        md = (
            ":::author-card\n"
            "name: x\n"
            "mp_brand: 宸的 AI 掘金笔记\n"
            "mp_id: gh_test123\n"
            ":::"
        )
        html = preprocess_author_card(md)
        # mp_id 触发 mp-common-profile 占位标签(WeChat 渲染器若识别会替换)
        self.assertIn("mp-common-profile", html)
        self.assertIn("gh_test123", html)

    def test_gradient_in_render(self):
        """WeChat 实测支持 linear-gradient · 必须在 bg/strip/avatar 渲染。"""
        md = (
            ":::author-card\n"
            "name: 测试\n"
            "mp_brand: x\n"
            ":::"
        )
        html = preprocess_author_card(md, theme_id="focus-navy")
        # bg 渐变(135deg)
        self.assertIn("linear-gradient(135deg", html)
        # strip 渐变(90deg)
        self.assertIn("linear-gradient(90deg", html)

    def test_no_flex_no_webkit(self):
        """flex 和 -webkit-* 是 WeChat 必死属性 · 永远不能出现。"""
        md = (
            ":::author-card\n"
            "name: x\n"
            "mp_brand: y\n"
            "mp_desc: z\n"
            ":::"
        )
        html = preprocess_author_card(md)
        self.assertNotIn("display: flex", html)
        self.assertNotIn("display:flex", html)
        self.assertNotIn("-webkit-", html)
        self.assertNotIn("object-fit", html)

    def test_theme_color_adaptation(self):
        """66 个 theme 应通过 THEME_TO_STYLE 映射到 8 个 STYLES 的不同色板。"""
        from author_card import STYLES

        # 验证每个色板预设的 bg_start 颜色实际进入 HTML
        md = ":::author-card\nname: x\n:::"
        seen_bgs = set()
        for style_id, style in STYLES.items():
            html = preprocess_author_card(md.replace("name: x", f"name: x\nstyle: {style_id}"))
            self.assertIn(style["bg_start"], html, f"{style_id} 的 bg_start 未渲染")
            seen_bgs.add(style["bg_start"])
        # 8 个色板应有 8 种不同 bg 起色
        self.assertEqual(len(seen_bgs), len(STYLES))


# -----------------------------------------------------------------
# 6.5  _ensure_mp_brand_in_last_card · 老卡缺字段就地补
# -----------------------------------------------------------------
class EnsureMpBrand(unittest.TestCase):
    def test_old_card_without_mp_brand_gets_filled(self):
        md = (
            "正文\n\n"
            ":::author-card\n"
            "name: 智辰老师\n"
            "bio: 老 prompt 写出的卡 · 没 mp 字段\n"
            "tags: [AI]\n"
            ":::\n"
        )
        out = _ensure_mp_brand_in_last_card(md)
        self.assertIn("mp_brand: 宸的 AI 掘金笔记", out)
        self.assertIn("mp_desc: 记录 AI Agent", out)
        self.assertIn("mp_meta: 关注获取每日 AI 非共识", out)
        # 原字段保留
        self.assertIn("name: 智辰老师", out)
        self.assertIn("bio: 老 prompt", out)

    def test_card_with_mp_brand_unchanged(self):
        md = (
            "正文\n\n"
            ":::author-card\n"
            "name: x\n"
            "mp_brand: 已经有了\n"
            ":::\n"
        )
        out = _ensure_mp_brand_in_last_card(md)
        self.assertEqual(out, md)

    def test_only_last_card_modified(self):
        # 文章中段一张 + 末尾一张 · 只补末尾那张
        md = (
            ":::author-card\nname: 中段卡\nbio: x\n:::\n\n"
            "正文\n\n"
            ":::author-card\nname: 末尾卡\nbio: y\n:::\n"
        )
        out = _ensure_mp_brand_in_last_card(md)
        # 中段卡不应有 mp_brand
        first_block = out.split(":::author-card")[1].split(":::")[0]
        self.assertNotIn("mp_brand", first_block)
        # 末尾卡应有
        last_block = out.split(":::author-card")[-1].split(":::")[0]
        self.assertIn("mp_brand", last_block)

    def test_no_card_unchanged(self):
        md = "正文\n\n## 结尾\n"
        self.assertEqual(_ensure_mp_brand_in_last_card(md), md)

    def test_idempotent(self):
        md = (
            ":::author-card\n"
            "name: x\n"
            "bio: y\n"
            ":::\n"
        )
        once = _ensure_mp_brand_in_last_card(md)
        twice = _ensure_mp_brand_in_last_card(once)
        self.assertEqual(once, twice)

    def test_full_sanitize_chains_mp_fix(self):
        """sanitize_for_publish 末尾应自动补 mp_brand。"""
        md = (
            "# 标题\n\n"
            "![封面](images/cover.png)\n\n"
            "正文。\n\n"
            ":::author-card\n"
            "name: 智辰老师\n"
            "bio: 老卡缺 mp\n"
            ":::\n"
        )
        out = sanitize_for_publish(md)
        # H1 去 / cover alt 清 / 末卡补 mp 三行 · 全部生效
        self.assertNotIn("# 标题", out)
        self.assertNotIn("![封面]", out)
        self.assertIn("![](images/cover.png)", out)
        self.assertIn("mp_brand:", out)
        self.assertIn("mp_desc:", out)
        self.assertIn("mp_meta:", out)


# -----------------------------------------------------------------
# 7. cli.py:cmd_publish 接 sanitize 的 hook 测试
# -----------------------------------------------------------------
class CliPublishSanitizeHook(unittest.TestCase):
    """断言 cli.py:cmd_publish 默认会调 prepare_for_publish。"""

    def _make_args(self, **overrides):
        from types import SimpleNamespace
        defaults = dict(
            input=None, theme=None, appid="x", secret="x",
            cover=None, title=None, author=None, digest=None,
            engine="md2wx", font_size=None, no_sanitize=False,
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def _patch_publish_deps(self):
        """打桩 cli.cmd_publish 全部外部依赖,只验 sanitize 行为。"""
        import cli
        import unittest.mock as mock
        token_p = mock.patch.object(cli, "get_access_token", return_value="tok")
        upload_p = mock.patch.object(cli, "upload_thumb", return_value="mid")
        draft_p = mock.patch.object(cli, "create_draft",
                                    return_value=mock.MagicMock(media_id="m"))
        load_p = mock.patch.object(cli, "load_config",
                                   return_value={"wechat": {"appid": "x", "secret": "x"}})
        return token_p, upload_p, draft_p, load_p

    def test_default_sanitizes_dirty_md(self):
        sys.path.insert(0, str(REPO_ROOT / "toolkit"))
        import cli
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "dirty.md"
            md.write_text("# 重复标题\n\n![封面](images/cover.png)\n\n正文\n",
                          encoding="utf-8")

            seen_path = []

            class FakeResult:
                html = "<p>x</p>"; title = "t"; digest = "d"; images = []

            class FakeConv:
                def convert_file(self, path):
                    seen_path.append(path)
                    return FakeResult()

            patches = self._patch_publish_deps()
            with mock.patch.object(cli, "_build_converter",
                                    return_value=(FakeConv(), None)):
                for p in patches:
                    p.start()
                try:
                    cli.cmd_publish(self._make_args(input=str(md)))
                finally:
                    for p in patches:
                        p.stop()

            self.assertEqual(len(seen_path), 1)
            self.assertTrue(seen_path[0].endswith("._publish.md"),
                            f"converter saw {seen_path[0]} · 应是 sanitized 副本")

    def test_no_sanitize_flag_skips(self):
        sys.path.insert(0, str(REPO_ROOT / "toolkit"))
        import cli
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "dirty.md"
            md.write_text("# H1\n\n正文\n", encoding="utf-8")

            seen_path = []

            class FakeResult:
                html = "<p>x</p>"; title = "t"; digest = "d"; images = []

            class FakeConv:
                def convert_file(self, path):
                    seen_path.append(path)
                    return FakeResult()

            patches = self._patch_publish_deps()
            with mock.patch.object(cli, "_build_converter",
                                    return_value=(FakeConv(), None)):
                for p in patches:
                    p.start()
                try:
                    cli.cmd_publish(self._make_args(input=str(md), no_sanitize=True))
                finally:
                    for p in patches:
                        p.stop()

            self.assertEqual(seen_path, [str(md)],
                             "--no-sanitize 应直接喂原路径给 converter")
            # 同时确认未生成临时副本
            self.assertFalse((md.with_suffix(".publish.md")).exists())


# -----------------------------------------------------------------
# 8. publish.py 放宽 state gating
# -----------------------------------------------------------------
class PublishWorkflowStateGating(unittest.TestCase):
    """state ∈ {imaged, done} 都允许跑;其他状态仍拒绝。"""

    def _import_publish(self):
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "workflow"))
        import importlib
        if "publish" in sys.modules:
            del sys.modules["publish"]
        import publish
        return publish

    def _run_main_with_state(self, state):
        """mock _state.load() · 调 publish.main · 返回 (exit_code, stderr)。"""
        import io, contextlib
        import unittest.mock as mock
        publish = self._import_publish()

        # mock _state.load 返回指定 state · 没 article_md 故第二关 sys.exit(1)
        with mock.patch.object(publish._state, "load",
                               return_value={"state": state, "article_md": None}):
            buf = io.StringIO()
            try:
                with contextlib.redirect_stderr(buf):
                    publish.main()
            except SystemExit as e:
                return e.code, buf.getvalue()
            return 0, buf.getvalue()

    def test_done_state_allowed_past_first_gate(self):
        """state=done 不应在第一关报错(应跌到 article_md 缺失这第二关)。"""
        rc, err = self._run_main_with_state("done")
        # 第一关报错文案是 "要先 write → images" · 第二关是 "无 article_md"
        self.assertNotIn("要先 write → images", err)
        self.assertIn("无 article_md", err)

    def test_imaged_state_still_works(self):
        rc, err = self._run_main_with_state("imaged")
        self.assertNotIn("要先 write → images", err)
        self.assertIn("无 article_md", err)

    def test_idle_state_rejected(self):
        rc, err = self._run_main_with_state("idle")
        self.assertEqual(rc, 1)
        self.assertIn("要先 write → images", err)

    def test_wrote_state_rejected(self):
        rc, err = self._run_main_with_state("wrote")
        self.assertEqual(rc, 1)
        self.assertIn("要先 write → images", err)


# -----------------------------------------------------------------
# 9. bot.py:_classify_intent 加 republish 路由
# -----------------------------------------------------------------
class BotIntentRepublish(unittest.TestCase):
    """state=done 时识别 republish 关键词;其他状态不误触发。"""

    def _classify(self, text, state):
        sys.path.insert(0, str(REPO_ROOT / "discord-bot"))
        # bot.py 顶部要 DISCORD_BOT_TOKEN · 测试时塞个假的避免 import 失败
        import os
        os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
        if "bot" in sys.modules:
            del sys.modules["bot"]
        import bot
        return bot._classify_intent(text, state)

    def test_republish_in_done_natural(self):
        action, _ = self._classify("请你重新排版发布到草稿箱", "done")
        self.assertEqual(action, "republish")

    def test_republish_keywords(self):
        for kw in ["重新排版", "重新发布", "重发", "重排", "republish",
                   "再发一次", "再推一次"]:
            action, _ = self._classify(kw, "done")
            self.assertEqual(action, "republish",
                             f"关键词 {kw!r} 在 done 应触发 republish")

    def test_republish_not_triggered_outside_done(self):
        # 在 imaged · wrote · idle 状态下,「重新排版」不应触发 republish
        for state in ["imaged", "wrote", "idle", "briefed"]:
            action, _ = self._classify("重新排版", state)
            self.assertNotEqual(action, "republish",
                                f"state={state} 不应触发 republish")

    def test_republish_priority_over_brief(self):
        # 「开始」会触发 brief · 但「重新排版开始一下」在 done 应优先 republish
        action, _ = self._classify("重新排版", "done")
        self.assertEqual(action, "republish")

    def test_unrelated_text_in_done_falls_back(self):
        action, _ = self._classify("写 GPT-5 评测", "done")
        # 「写 ...」是 custom_idea 优先级
        self.assertEqual(action, "custom_idea")


# -----------------------------------------------------------------
# 10. bot.py 「选题:XXX / 主题:XXX」前缀路由到 custom_idea
# -----------------------------------------------------------------
class BotIntentCustomIdeaPrefix(unittest.TestCase):
    """修「选题:XXX」被错路由到 brief 的 bug。"""

    def _classify(self, text, state="idle"):
        sys.path.insert(0, str(REPO_ROOT / "discord-bot"))
        import os
        os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
        if "bot" in sys.modules:
            del sys.modules["bot"]
        import bot
        return bot._classify_intent(text, state)

    def test_xuanti_with_topic_routes_to_custom_idea(self):
        """「选题: claude design的使用技巧」应进 custom_idea 不进 brief。"""
        action, kw = self._classify("选题: claude design的使用技巧")
        self.assertEqual(action, "custom_idea")
        self.assertEqual(kw["idea"], "claude design的使用技巧")

    def test_xuanti_with_chinese_colon(self):
        action, kw = self._classify("选题:Cursor 2.0 冲击 Claude Code")
        self.assertEqual(action, "custom_idea")
        self.assertIn("Cursor", kw["idea"])

    def test_xuanti_no_colon_with_space(self):
        action, kw = self._classify("选题 AI Agent 编排范式转变")
        self.assertEqual(action, "custom_idea")
        self.assertIn("AI Agent", kw["idea"])

    def test_zhuti_prefix_routes_to_custom_idea(self):
        action, kw = self._classify("主题:AI 非共识周报")
        self.assertEqual(action, "custom_idea")
        self.assertEqual(kw["idea"], "AI 非共识周报")

    def test_huati_prefix_routes_to_custom_idea(self):
        action, kw = self._classify("话题: 大模型降智观察")
        self.assertEqual(action, "custom_idea")
        self.assertEqual(kw["idea"], "大模型降智观察")

    def test_xuanti_alone_still_triggers_brief(self):
        """「选题」单独成词无内容 · 仍是 brief 意图。"""
        for word in ["选题", "选题吧", "看看选题", "今天选题", "选个题"]:
            action, _ = self._classify(word)
            self.assertEqual(action, "brief", f"{word!r} 应触发 brief")

    def test_brief_keywords_still_work(self):
        """brief 其他关键词不受影响。"""
        for word in ["brief", "今日热点", "今天写", "开始", "看看有什么写"]:
            action, _ = self._classify(word)
            self.assertEqual(action, "brief", f"{word!r} 应触发 brief")


# -----------------------------------------------------------------
# 11. bot.py 「教程/干货/方法论:XXX」前缀路由到 tutorial_idea
# -----------------------------------------------------------------
class BotIntentTutorial(unittest.TestCase):
    """干货系列入口 · 触发词:教程/干货/方法论/手把手/how to/如何 + 内容。"""

    def _classify(self, text, state="idle"):
        sys.path.insert(0, str(REPO_ROOT / "discord-bot"))
        import os
        os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
        if "bot" in sys.modules:
            del sys.modules["bot"]
        import bot
        return bot._classify_intent(text, state)

    def test_jiaocheng_with_topic(self):
        action, kw = self._classify("教程: claude design 9 个使用技巧")
        self.assertEqual(action, "tutorial_idea")
        self.assertIn("claude design", kw["idea"])

    def test_ganhuo_prefix(self):
        action, kw = self._classify("干货:Cursor 配置完整 SOP")
        self.assertEqual(action, "tutorial_idea")
        self.assertEqual(kw["idea"], "Cursor 配置完整 SOP")

    def test_fangfalun_prefix(self):
        action, kw = self._classify("方法论: 用 Claude 重构遗留代码的 5 个原则")
        self.assertEqual(action, "tutorial_idea")
        self.assertIn("Claude", kw["idea"])

    def test_shoubashou_prefix(self):
        action, kw = self._classify("手把手: 30 分钟搭一个 RAG demo")
        self.assertEqual(action, "tutorial_idea")
        self.assertIn("RAG", kw["idea"])

    def test_howto_english(self):
        action, kw = self._classify("how to use claude code mcp")
        self.assertEqual(action, "tutorial_idea")
        self.assertIn("claude code mcp", kw["idea"])

    def test_howto_no_space(self):
        action, kw = self._classify("howto 用 cursor 接管代码库")
        self.assertEqual(action, "tutorial_idea")
        self.assertIn("cursor", kw["idea"])

    def test_ruhe_prefix(self):
        action, kw = self._classify("如何 把 claude design 嵌进现有项目")
        self.assertEqual(action, "tutorial_idea")
        self.assertIn("claude design", kw["idea"])

    def test_tutorial_priority_over_custom_idea(self):
        """「教程」+ 内容 应优先于「写」前缀(避免「写教程: XX」误走 hotspot)。"""
        # 注:用户实际输入「教程: XX」会先匹配 tutorial · 不会到 custom_idea
        action, _ = self._classify("教程: A")  # 内容太短(<3 字符) · 不应触发
        self.assertNotEqual(action, "tutorial_idea")

    def test_tutorial_keyword_alone_no_topic(self):
        """单词「教程」无内容 · 不应误触发(返回 fallback)。"""
        action, _ = self._classify("教程")
        # 单纯「教程」会被 r'^(?:教程|...)\s*[::,,、]?\s*(.+)' 匹配但 (.+) 要求至少 1 字符
        # 所以「教程」(0 字符)不命中 · fallback 到 claude_fallback
        self.assertNotEqual(action, "tutorial_idea")

    def test_xuanti_still_routes_to_custom_idea(self):
        """「选题: XX」依然走 hotspot 系列(custom_idea) · 不被 tutorial 截胡。"""
        action, kw = self._classify("选题: claude design的使用技巧")
        self.assertEqual(action, "custom_idea")
        self.assertIn("claude design", kw["idea"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
