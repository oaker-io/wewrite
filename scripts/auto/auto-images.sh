#!/usr/bin/env bash
# auto-images.sh · 10:00 launchd 触发
# 主推 6 张图(images.py · cover + cover-square + chart×4)
# 副推每篇调 images.py --style shortform · 只生 cover-square (和 0-2 chart)
# 副推 cover-square 文件名:cover-square-c1.png / c2.png ...(避免覆盖主推)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_common.sh"

step_check_enabled "images"
require_binary claude
load_keys

LOG="$LOG_DIR/auto-images.$(date +%F).log"

STATE=$("$PY" -c "
import yaml
try:
    s = yaml.safe_load(open('output/session.yaml', encoding='utf-8')) or {}
    print(s.get('state', 'idle'))
except Exception:
    print('idle')
" 2>/dev/null)

echo "[$(date '+%F %T')] → auto_images · session.state=$STATE" >> "$LOG"

if [[ "$STATE" != "wrote" ]]; then
  echo "[$(date '+%F %T')] ✗ skip · state=$STATE 不是 wrote" >> "$LOG"
  notify_failure "images" "session.state=$STATE · 不是 wrote · auto_write 失败?"
  exit 1
fi

# 主推 · images.py 走 _resolve_style · 自动按 image_style 决定 default/case/narrative
echo "[$(date '+%F %T')] → main images" >> "$LOG"
if "$PY" scripts/workflow/images.py --auto >> "$LOG" 2>&1; then
  echo "[$(date '+%F %T')] ✓ main images 完成" >> "$LOG"
else
  rc=$?
  echo "[$(date '+%F %T')] ✗ main images exit=$rc" >> "$LOG"
  notify_failure "images" "主推 images.py 退出 $rc"
  exit $rc
fi

# 副推循环 · 每篇调 images.py --style shortform
# images.py 默认读 session.article_md · 这里要 trick:临时改 session.article_md 跑 · 再 restore
"$PY" - << 'PYEOF' >> "$LOG" 2>&1
import yaml, subprocess, shutil, sys
from pathlib import Path

REPO_ROOT = Path('.').resolve()
SESSION = REPO_ROOT / 'output' / 'session.yaml'
IMAGES = REPO_ROOT / 'output' / 'images'

s = yaml.safe_load(SESSION.read_text(encoding='utf-8')) or {}
sched = s.get('auto_schedule') or {}
comp_articles = sched.get('companion_articles') or []
main_md = s.get('article_md')
main_state = s.get('state')

if not comp_articles:
    print('· 无 companion_articles · 跳过副推 images')
    sys.exit(0)

py = REPO_ROOT / 'venv' / 'bin' / 'python3'
if not py.exists():
    py = 'python3'

print(f'→ 跑 {len(comp_articles)} 次副推 images...')
for i, comp_md in enumerate(comp_articles):
    print(f'\n[companion-{i+1}/{len(comp_articles)}] {comp_md}')
    # trick: 临时覆盖 session.article_md = comp_md · state 保持 wrote
    s_temp = dict(s)
    s_temp['article_md'] = comp_md
    s_temp['state'] = 'wrote'  # images.py 要求 wrote
    # 副推主题
    if i < len(sched.get('companions', [])):
        comp_topic = sched['companions'][i]
        s_temp['selected_topic'] = comp_topic
    SESSION.write_text(
        yaml.safe_dump(s_temp, allow_unicode=True, sort_keys=False),
        encoding='utf-8',
    )
    r = subprocess.run(
        [str(py), 'scripts/workflow/images.py', '--auto', '--style', 'shortform'],
        cwd=str(REPO_ROOT),
        capture_output=True, text=True, timeout=1200,
    )
    if r.returncode != 0:
        print(f'  ✗ companion-{i+1} images 失败: rc={r.returncode}')
        print(r.stderr[-500:])
        # 不阻断 · 继续下一篇
        continue

    # 把生的 cover-square.png 重命名 cover-square-c{i+1}.png 避免下一篇覆盖
    src = IMAGES / 'cover-square.png'
    dst = IMAGES / f'cover-square-c{i+1}.png'
    if src.exists():
        shutil.copy2(src, dst)
        print(f'  ✓ companion-{i+1} cover-square -> {dst.name}')
    # chart-1/-2 也保留(若有)
    for chart in ('chart-1.png', 'chart-2.png'):
        chart_src = IMAGES / chart
        if chart_src.exists():
            chart_dst = IMAGES / chart.replace('.png', f'-c{i+1}.png')
            shutil.copy2(chart_src, chart_dst)
            print(f'  ✓ companion-{i+1} {chart} -> {chart_dst.name}')

# restore session: article_md = main_md · state = imaged
s_final = yaml.safe_load(SESSION.read_text(encoding='utf-8')) or {}
s_final['article_md'] = main_md
s_final['state'] = 'imaged'  # auto-publish 期望 imaged
SESSION.write_text(
    yaml.safe_dump(s_final, allow_unicode=True, sort_keys=False),
    encoding='utf-8',
)
print(f'\n✓ 副推 images 完成 · session restored · state=imaged')
PYEOF

if [[ $? -ne 0 ]]; then
  echo "[$(date '+%F %T')] ⚠ 副推 images 出错 · 主推已 OK" >> "$LOG"
fi

echo "[$(date '+%F %T')] ✓ auto_images 全部完成" >> "$LOG"
exit 0
