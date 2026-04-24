#!/usr/bin/env bash
# auto-write.sh · 08:00 launchd 触发
# 跑 1 次 write.py(主推) + N 次 write.py --style shortform --idea "<companion title>"(副推)
# 副推 article 路径写到 session.yaml 的 companion_articles 字段
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_common.sh"

step_check_enabled "write"
require_binary claude
load_keys

LOG="$LOG_DIR/auto-write.$(date +%F).log"

# 从 session.yaml 读 auto_schedule
read_session_field() {
  "$PY" -c "
import yaml
try:
    s = yaml.safe_load(open('output/session.yaml', encoding='utf-8')) or {}
    sched = s.get('auto_schedule') or {}
    print(sched.get('$1', '$2'))
except Exception:
    print('$2')
" 2>/dev/null
}

STATE=$("$PY" -c "
import yaml
try:
    s = yaml.safe_load(open('output/session.yaml', encoding='utf-8')) or {}
    print(s.get('state', 'idle'))
except Exception:
    print('idle')
" 2>/dev/null)

STYLE=$(read_session_field "style" "hotspot")

echo "[$(date '+%F %T')] → auto_write · style=$STYLE · session.state=$STATE" >> "$LOG"

if [[ "$STATE" != "briefed" ]]; then
  echo "[$(date '+%F %T')] ✗ skip · state=$STATE 不是 briefed" >> "$LOG"
  notify_failure "write" "session.state=$STATE · 不是 briefed · auto_pick 是不是没跑成功?"
  exit 1
fi

# 主推:write.py 0 --style $STYLE
echo "[$(date '+%F %T')] → main: write.py 0 --style $STYLE" >> "$LOG"
if "$PY" scripts/workflow/write.py 0 --style "$STYLE" >> "$LOG" 2>&1; then
  MAIN_MD=$("$PY" -c "
import yaml
s = yaml.safe_load(open('output/session.yaml', encoding='utf-8')) or {}
print(s.get('article_md', ''))
" 2>/dev/null)
  echo "[$(date '+%F %T')] ✓ main 写完 · $MAIN_MD" >> "$LOG"
else
  rc=$?
  echo "[$(date '+%F %T')] ✗ main write.py exit=$rc" >> "$LOG"
  notify_failure "write" "主推 write.py 退出 $rc"
  exit $rc
fi

# 副推循环:跑 N 次 write.py --idea "<companion title>" --style shortform
# 副推完成后回写 session.yaml#auto_schedule.companion_articles 字段
"$PY" - << 'PYEOF' >> "$LOG" 2>&1
import yaml, subprocess, sys
from pathlib import Path

REPO_ROOT = Path('.').resolve()
SESSION = REPO_ROOT / 'output' / 'session.yaml'

s = yaml.safe_load(SESSION.read_text(encoding='utf-8')) or {}
sched = s.get('auto_schedule') or {}
companions = sched.get('companions') or []
companion_styles = sched.get('companion_styles') or []

if not companions:
    print('· 无副推 · 跳过 companion 循环')
    sys.exit(0)

print(f'→ 跑 {len(companions)} 次副推 write...')
companion_articles = []
for i, ct in enumerate(companions):
    title = ct.get('title', '')
    style = companion_styles[i] if i < len(companion_styles) else 'shortform'
    print(f'\n[companion-{i+1}/{len(companions)}] style={style} · {title[:50]}')
    py = REPO_ROOT / 'venv' / 'bin' / 'python3'
    if not py.exists():
        py = 'python3'
    # write.py --idea 路径 · 不动 session.state(它会试图覆盖)
    # 我们 trick: 跑完后从 session.article_md 读路径 · 然后 restore session.state=wrote
    state_before = s.get('state')
    main_md_before = s.get('article_md')

    r = subprocess.run(
        [str(py), 'scripts/workflow/write.py', '--idea', title, '--style', style],
        cwd=str(REPO_ROOT),
        capture_output=True, text=True, timeout=900,
    )
    if r.returncode != 0:
        print(f'  ✗ companion-{i+1} write 失败: rc={r.returncode}')
        print(r.stderr[-500:])
        # 不阻断 · 继续下一篇
        continue

    # write.py --idea 会覆盖 session.article_md · 抽出来当 companion 路径
    s_after = yaml.safe_load(SESSION.read_text(encoding='utf-8')) or {}
    comp_md = s_after.get('article_md')
    if comp_md and comp_md != main_md_before:
        companion_articles.append(comp_md)
        print(f'  ✓ companion-{i+1} 写完 · {comp_md}')
    else:
        print(f'  ⚠ companion-{i+1} article_md 未变 · 可能写失败')

# 回写 session: state 恢复 wrote · article_md 恢复主推 · companion_articles 写新字段
s_final = yaml.safe_load(SESSION.read_text(encoding='utf-8')) or {}
s_final['state'] = 'wrote'
s_final['article_md'] = main_md_before
sched_final = s_final.get('auto_schedule') or {}
sched_final['companion_articles'] = companion_articles
s_final['auto_schedule'] = sched_final
SESSION.write_text(
    yaml.safe_dump(s_final, allow_unicode=True, sort_keys=False),
    encoding='utf-8',
)
print(f'\n✓ 副推循环完成 · companion_articles={companion_articles}')
PYEOF

if [[ $? -ne 0 ]]; then
  echo "[$(date '+%F %T')] ⚠ 副推循环出错 · 主推已写 · 继续" >> "$LOG"
  # 不阻断 · 主推已经 OK · 后续 step 用主推单独走也行
fi

echo "[$(date '+%F %T')] ✓ auto_write 全部完成" >> "$LOG"
exit 0
