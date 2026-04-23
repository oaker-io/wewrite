#!/usr/bin/env bash
# auto-publish.sh · 12:00 launchd 触发
# 调 cli.py publish-bundle 一次推 1 主 + N 副 · 占 1 次群发配额
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_common.sh"

step_check_enabled "publish"
load_keys

LOG="$LOG_DIR/auto-publish.$(date +%F).log"

STATE=$("$PY" -c "
import yaml
try:
    s = yaml.safe_load(open('output/session.yaml', encoding='utf-8')) or {}
    print(s.get('state', 'idle'))
except Exception:
    print('idle')
" 2>/dev/null)

echo "[$(date '+%F %T')] → auto_publish · state=$STATE" >> "$LOG"

if [[ "$STATE" != "imaged" ]] && [[ "$STATE" != "done" ]]; then
  echo "[$(date '+%F %T')] ✗ skip · state=$STATE 不是 imaged/done" >> "$LOG"
  notify_failure "publish" "session.state=$STATE · 没到 imaged"
  exit 1
fi

# 检查 companion_articles 是否存在 · 走 bundle 还是单篇
COMP_COUNT=$("$PY" -c "
import yaml
try:
    s = yaml.safe_load(open('output/session.yaml', encoding='utf-8')) or {}
    sched = s.get('auto_schedule') or {}
    print(len(sched.get('companion_articles') or []))
except Exception:
    print(0)
" 2>/dev/null)

echo "[$(date '+%F %T')] · companion 数: $COMP_COUNT" >> "$LOG"

if [[ "$COMP_COUNT" -eq 0 ]]; then
  # 没副推 · 走老 publish.py(单篇 · 兼容)
  echo "[$(date '+%F %T')] → 单篇模式:publish.py --auto" >> "$LOG"
  if "$PY" scripts/workflow/publish.py --auto >> "$LOG" 2>&1; then
    echo "[$(date '+%F %T')] ✓ publish 完成" >> "$LOG"
    exit 0
  else
    rc=$?
    echo "[$(date '+%F %T')] ✗ publish exit=$rc" >> "$LOG"
    notify_failure "publish" "publish.py --auto 退出 $rc"
    exit $rc
  fi
fi

# Bundle 模式 · 调 cli.py publish-bundle
echo "[$(date '+%F %T')] → bundle 模式 (1 主 + $COMP_COUNT 副)" >> "$LOG"

# 用 python 拼 cli 参数 · 处理路径 / 标题 / cover / thumb
"$PY" - << 'PYEOF' >> "$LOG" 2>&1
import yaml, subprocess, sys
from pathlib import Path

REPO_ROOT = Path('.').resolve()
SESSION = REPO_ROOT / 'output' / 'session.yaml'
IMAGES = REPO_ROOT / 'output' / 'images'

s = yaml.safe_load(SESSION.read_text(encoding='utf-8')) or {}
sched = s.get('auto_schedule') or {}
main_md = s.get('article_md')
main_topic = s.get('selected_topic') or {}
comp_articles = sched.get('companion_articles') or []
comp_topics = sched.get('companions') or []

if not main_md:
    print('❌ 无 article_md', file=sys.stderr)
    sys.exit(1)

main_title = (main_topic.get('title') or '')[:60] or '(untitled)'
cover_main = IMAGES / 'cover.png'
thumb_main = IMAGES / 'cover-square.png'

cli_args = [
    str(REPO_ROOT / 'venv' / 'bin' / 'python3'),
    str(REPO_ROOT / 'toolkit' / 'cli.py'), 'publish-bundle',
    '--main', main_md,
    '--main-title', main_title,
    '--engine', 'md2wx',
    '--theme', 'focus-navy',
]
if cover_main.exists():
    cli_args += ['--main-cover', str(cover_main.relative_to(REPO_ROOT))]
if thumb_main.exists():
    cli_args += ['--main-thumb', str(thumb_main.relative_to(REPO_ROOT))]

# 副推 · 一一对应 thumb (cover-square-cN.png)
for i, comp_md in enumerate(comp_articles):
    cli_args += ['--companion', comp_md]
    comp_thumb = IMAGES / f'cover-square-c{i+1}.png'
    if comp_thumb.exists():
        cli_args += ['--companion-thumb', str(comp_thumb.relative_to(REPO_ROOT))]
    else:
        # 兜底用主推 thumb (避免 wechat 报错)
        if thumb_main.exists():
            cli_args += ['--companion-thumb', str(thumb_main.relative_to(REPO_ROOT))]

print(f'→ 调 cli.py publish-bundle (1 主 + {len(comp_articles)} 副)')
print(f'  cmd: {" ".join(cli_args[2:])}')

r = subprocess.run(cli_args, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=600)
if r.returncode != 0:
    print(f'❌ publish-bundle 失败: rc={r.returncode}', file=sys.stderr)
    print(r.stdout[-1000:])
    print(r.stderr[-500:], file=sys.stderr)
    sys.exit(2)

print(r.stdout[-2000:])

# 抽 media_id
import re
m = re.search(r'Bundle draft created!\s+media_id:\s*(\S+)', r.stdout)
media_id = m.group(1) if m else '?'

# 更新 session
s2 = yaml.safe_load(SESSION.read_text(encoding='utf-8')) or {}
s2['state'] = 'done'
s2['draft_media_id'] = media_id
SESSION.write_text(
    yaml.safe_dump(s2, allow_unicode=True, sort_keys=False),
    encoding='utf-8',
)
print(f'\n✓ session done · media_id={media_id} · 1 主 + {len(comp_articles)} 副')

# push Discord 通知
push_py = REPO_ROOT / 'discord-bot' / 'push.py'
py = REPO_ROOT / 'venv' / 'bin' / 'python3'
if not py.exists():
    py = 'python3'
notify_text = (
    f'🚀 **bundle 草稿就绪 · auto** (1 主 + {len(comp_articles)} 副)\n'
    f'📝 主推:{main_title}\n'
    + '\n'.join([f'  📎 副推 {i+1}: {(t.get("title") or "")[:40]}' for i, t in enumerate(comp_topics)])
    + f'\n🆔 {media_id[:30]}\n\n'
    f'📦 已自动:H1 去重 · 封面 alt 清空 · 主推完整 author-card · 副推 mini card · 评论已开\n\n'
    '📅 19:30 推群发提醒 · 20:00 推置顶话术'
)
subprocess.run([str(py), str(push_py), '--text', notify_text], timeout=60)
PYEOF

rc=$?
if [[ $rc -ne 0 ]]; then
  echo "[$(date '+%F %T')] ✗ bundle publish exit=$rc" >> "$LOG"
  notify_failure "publish" "publish-bundle 退出 $rc"
  exit $rc
fi

echo "[$(date '+%F %T')] ✓ bundle publish 完成" >> "$LOG"
exit 0
