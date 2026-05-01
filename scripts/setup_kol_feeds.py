#!/usr/bin/env python3
"""setup_kol_feeds.py · 把一批 mp.weixin.qq.com/s/ url 自动加进 wewe-rss + 回填 kol_list.yaml。

为什么:
    wewe-rss 没暴露「按公众号名搜索」API · 只有 platform.getMpInfo(wxsLink) 拿 biz_id。
    所以批量加 KOL 必须先有每个 KOL 任意一篇文章 url · 然后调 trpc 完成 add。

流程:
    1. 读一份 url list(每行一个 mp.weixin.qq.com/s/ 文章 url)
    2. 对每个 url 调 trpc platform.getMpInfo → 拿 mpName / mpCover / mpIntro / id(biz)
    3. 调 trpc feed.add → 把 KOL 加进 wewe-rss feed list
    4. 用 mpName fuzzy match 到 config/kol_list.yaml 对应 KOL · 回填 rss_url + status=active
    5. push Discord 报告:加成功 N 个 / 失败 M 个 / 没 match 的 mpName 列表

跑法:
    venv/bin/python3 scripts/setup_kol_feeds.py urls.txt
    venv/bin/python3 scripts/setup_kol_feeds.py - <<EOF
    https://mp.weixin.qq.com/s/aaa...
    https://mp.weixin.qq.com/s/bbb...
    EOF
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KOL_LIST = ROOT / "config" / "kol_list.yaml"
WEWE_RSS_URL = "http://localhost:4000"
AUTH_CODE = "wewrite-zhichen-2026"


def trpc_call(procedure: str, payload: dict, *, mutation: bool = False) -> dict:
    """调 wewe-rss tRPC procedure · 返回 result.data 或 raise。"""
    headers = {"Authorization": AUTH_CODE, "Content-Type": "application/json"}
    if mutation:
        url = f"{WEWE_RSS_URL}/trpc/{procedure}"
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    else:
        encoded = urllib.parse.quote(json.dumps(payload))
        url = f"{WEWE_RSS_URL}/trpc/{procedure}?input={encoded}"
        req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    if "error" in data:
        raise RuntimeError(f"trpc {procedure} error: {data['error'].get('message', data)}")
    return data.get("result", {}).get("data", {})


def get_mp_info(wxs_link: str) -> dict:
    """platform.getMpInfo(wxsLink) · 返回 [{id, name, cover, intro}]。"""
    return trpc_call("platform.getMpInfo", {"wxsLink": wxs_link}, mutation=True)


def add_feed(mp_id: str, mp_name: str, mp_cover: str = "", mp_intro: str = "",
             update_time: int = 0, status: int = 1, sync_time: int = 0,
             has_history: int = 0) -> dict:
    """feed.add → 加进 wewe-rss feed 列表。"""
    return trpc_call(
        "feed.add",
        {
            "id": mp_id, "mpName": mp_name, "mpCover": mp_cover, "mpIntro": mp_intro,
            "syncTime": sync_time, "updateTime": update_time,
            "status": status, "hasHistory": has_history,
        },
        mutation=True,
    )


def fuzzy_match_kol(mp_name: str, kol_list: list[dict]) -> dict | None:
    """mpName → kol_list.yaml 的某个 KOL · 用 substring + 互含。"""
    norm = mp_name.lower().replace(" ", "").replace("·", "")
    for k in kol_list:
        kn = (k.get("name") or "").lower().replace(" ", "").replace("·", "")
        if not kn:
            continue
        if kn == norm or kn in norm or norm in kn:
            return k
        # 进一步 · 拆 「-」分隔的取最后一段(谢无敌-闪亮猫传媒 → 闪亮猫传媒)
        for part in kn.split("-"):
            if len(part) >= 2 and (part in norm or norm in part):
                return k
    return None


def load_kol_list() -> dict:
    if not KOL_LIST.exists():
        print(f"❌ {KOL_LIST} 不存在", file=sys.stderr)
        sys.exit(1)
    return yaml.safe_load(KOL_LIST.read_text(encoding="utf-8")) or {}


def save_kol_list(data: dict) -> None:
    KOL_LIST.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def main() -> int:
    p = argparse.ArgumentParser(description="批量加 KOL 进 wewe-rss + 回填 kol_list.yaml")
    p.add_argument("urls_file", help="一行一个 mp.weixin.qq.com/s/ url 文件 · 用 - 读 stdin")
    p.add_argument("--dry-run", action="store_true", help="不真加 feed · 只解析 + match · debug 用")
    args = p.parse_args()

    if args.urls_file == "-":
        urls = [line.strip() for line in sys.stdin if line.strip()]
    else:
        urls = [
            line.strip() for line in Path(args.urls_file).read_text(encoding="utf-8").splitlines()
            if line.strip() and "mp.weixin.qq.com/s/" in line
        ]

    if not urls:
        print("❌ 没读到任何 mp.weixin.qq.com/s/ url", file=sys.stderr)
        return 1

    print(f"→ {len(urls)} 个 url 待处理\n")

    kol_data = load_kol_list()
    kol_list = kol_data.get("list") or []
    added: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []
    no_match: list[str] = []

    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url[:80]}")
        try:
            info = get_mp_info(url)
            # info 可能是 array(多公众号一文)或 single dict · 取第一个
            if isinstance(info, list) and info:
                info = info[0]
            mp_id = info.get("id") or ""
            mp_name = info.get("name") or ""
            mp_cover = info.get("cover") or ""
            mp_intro = info.get("intro") or ""
            print(f"   ✓ getMpInfo → {mp_name} (biz={mp_id[:20]})")

            if not args.dry_run:
                try:
                    add_feed(mp_id, mp_name, mp_cover, mp_intro)
                except RuntimeError as e:
                    if "Unique constraint" in str(e) or "exists" in str(e).lower():
                        print(f"   · already in feed list · 复用")
                    else:
                        raise

            # match 到 kol_list
            matched = fuzzy_match_kol(mp_name, kol_list)
            if matched:
                rss_url = f"{WEWE_RSS_URL}/feeds/{mp_id}.rss"
                if not args.dry_run:
                    matched["rss_url"] = rss_url
                    matched["biz_name"] = mp_id
                    matched["status"] = "active"
                print(f"   ✓ match → kol_list#{matched.get('name')} · status=active")
                added.append((mp_name, matched.get("name", "?")))
            else:
                print(f"   ⚠ no match in kol_list.yaml · 加进了 wewe-rss 但 wewrite 不会拉")
                no_match.append(mp_name)
        except Exception as e:
            print(f"   ✗ {e}")
            failed.append((url, str(e)))

    if not args.dry_run and added:
        save_kol_list(kol_data)
        print(f"\n✓ kol_list.yaml 更新 · {len(added)} 个 KOL active")

    print(f"\n=== 总结 ===")
    print(f"  成功 add + match : {len(added)}")
    print(f"  add 但没 match   : {len(no_match)} {no_match}")
    print(f"  失败            : {len(failed)}")
    for url, err in failed:
        print(f"    - {url[:60]} · {err[:80]}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
