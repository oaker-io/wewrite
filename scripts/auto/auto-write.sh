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
  # state 不是 briefed · 检查是不是跨日 / done 残留 · 是的话补救:reset + 触发 auto-pick
  echo "[$(date '+%F %T')] ⚠ state=$STATE · 检查跨日残留 ..." >> "$LOG"
  RESET_OK=$("$PY" -c "
import sys; sys.path.insert(0, 'scripts/workflow')
import _state
print('1' if _state.reset_if_stale() else '0')
" 2>/dev/null)
  if [[ "$RESET_OK" == "1" ]]; then
    echo "[$(date '+%F %T')] · 跨日 reset 触发 · 补跑 auto-pick.sh" >> "$LOG"
    if "$SCRIPT_DIR/auto-pick.sh" >> "$LOG" 2>&1; then
      STATE=$("$PY" -c "
import yaml
try:
    s = yaml.safe_load(open('output/session.yaml', encoding='utf-8')) or {}
    print(s.get('state', 'idle'))
except Exception:
    print('idle')
" 2>/dev/null)
      STYLE=$(read_session_field "style" "hotspot")
      echo "[$(date '+%F %T')] · 补 pick 完成 · 新 state=$STATE" >> "$LOG"
    fi
  fi
  if [[ "$STATE" != "briefed" ]]; then
    echo "[$(date '+%F %T')] ✗ skip · state=$STATE 仍不是 briefed" >> "$LOG"
    notify_failure "write" "session.state=$STATE · 不是 briefed · auto_pick 是不是没跑成功?"
    exit 1
  fi
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

# 额外主推 + 副推循环:都用 write.py --idea 跑
# extra_mains:跟主推同 style 体量(tutorial/case/hotspot · 1800-3000+ 字)
# companions:shortform 短文(800-1500 字)
# 写完回写 session.yaml#auto_schedule.{extra_main_articles,companion_articles}
"$PY" - << 'PYEOF' >> "$LOG" 2>&1
import yaml, subprocess, sys
from pathlib import Path

REPO_ROOT = Path('.').resolve()
SESSION = REPO_ROOT / 'output' / 'session.yaml'

s = yaml.safe_load(SESSION.read_text(encoding='utf-8')) or {}
sched = s.get('auto_schedule') or {}
extra_mains = sched.get('extra_mains') or []
extra_main_styles = sched.get('extra_main_styles') or []
companions = sched.get('companions') or []
companion_styles = sched.get('companion_styles') or []

py = REPO_ROOT / 'venv' / 'bin' / 'python3'
if not py.exists():
    py = 'python3'

main_md_before = s.get('article_md')


def _write_one(title, style, label):
    """跑一次 write.py --idea · 返回 article_md 路径(失败返回 None)。"""
    print(f'\n[{label}] style={style} · {title[:50]}')
    r = subprocess.run(
        [str(py), 'scripts/workflow/write.py', '--idea', title, '--style', style],
        cwd=str(REPO_ROOT),
        capture_output=True, text=True, timeout=900,
    )
    if r.returncode != 0:
        print(f'  ✗ {label} write 失败: rc={r.returncode}')
        print(r.stderr[-500:])
        return None
    s_after = yaml.safe_load(SESSION.read_text(encoding='utf-8')) or {}
    md = s_after.get('article_md')
    if md and md != main_md_before:
        print(f'  ✓ {label} 写完 · {md}')
        return md
    print(f'  ⚠ {label} article_md 未变 · 可能写失败')
    return None


# 1. 额外主推循环(主推 2+)
extra_main_articles = []
if extra_mains:
    print(f'→ 跑 {len(extra_mains)} 次额外主推 write...')
    for i, em in enumerate(extra_mains):
        title = em.get('title', '')
        style = extra_main_styles[i] if i < len(extra_main_styles) else 'tutorial'
        md = _write_one(title, style, f'extra-main-{i+2}')
        if md:
            extra_main_articles.append(md)

# 2. 副推循环(shortform)
companion_articles = []
if companions:
    print(f'\n→ 跑 {len(companions)} 次副推 write...')
    for i, ct in enumerate(companions):
        title = ct.get('title', '')
        style = companion_styles[i] if i < len(companion_styles) else 'shortform'
        md = _write_one(title, style, f'companion-{i+1}')
        if md:
            companion_articles.append(md)

# 回写 session: state=wrote · article_md=主推 1 · 把 extra+companion 都存起来
s_final = yaml.safe_load(SESSION.read_text(encoding='utf-8')) or {}
s_final['state'] = 'wrote'
s_final['article_md'] = main_md_before
sched_final = s_final.get('auto_schedule') or {}
sched_final['extra_main_articles'] = extra_main_articles
sched_final['companion_articles'] = companion_articles
s_final['auto_schedule'] = sched_final
SESSION.write_text(
    yaml.safe_dump(s_final, allow_unicode=True, sort_keys=False),
    encoding='utf-8',
)
total = 1 + len(extra_main_articles) + len(companion_articles)
print(f'\n✓ 全部 write 循环完成 · 主 1+{len(extra_main_articles)} · 副 {len(companion_articles)} · 共 {total} 篇')
PYEOF

if [[ $? -ne 0 ]]; then
  echo "[$(date '+%F %T')] ⚠ 副推循环出错 · 主推已写 · 继续" >> "$LOG"
  # 不阻断 · 主推已经 OK · 后续 step 用主推单独走也行
fi

echo "[$(date '+%F %T')] ✓ auto_write 全部完成" >> "$LOG"
exit 0
