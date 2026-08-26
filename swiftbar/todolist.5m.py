#!/usr/bin/env python3
"""SwiftBar 插件：菜单栏 TODOList（每 5 分钟刷新，只读本地缓存，不打网络）"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
try:
    from render_console import parse_todo_md, BASE_URL, CFG, ST  # noqa: E402
except Exception:
    print("🎛️!")
    print("---")
    print("render_console 加载失败 — 检查 config.json")
    sys.exit(0)

CACHE = REPO / "cache.json"
ASK = REPO / "ask_claude.sh"
RENDER = REPO / "render_console.py"
PORT = CFG.get("port", 8765)
FONT = "size=13"


def clip(s, n=44):
    return s if len(s) <= n else s[: n - 1] + "…"


def main():
    tasks, projects, cache_ts = [], [], ""
    if CACHE.exists():
        c = json.loads(CACHE.read_text())
        tasks = c.get("tasks", [])
        projects = c.get("projects", [])
        cache_ts = c.get("ts", "")[:16].replace("T", " ")
    now = datetime.now()
    p0 = [t for t in tasks if (t.get("prio") or "").startswith("P0")
          and t["status"] != ST["paused"]]
    review = [t for t in tasks if t["status"] == ST["review"]]
    soon = [t for t in tasks if t.get("ddl") and
            datetime.fromtimestamp(t["ddl"] / 1000) <= now + timedelta(days=3)
            and t["status"] != ST["paused"]]
    doing = [t for t in tasks if t["status"] == ST["doing"]]
    todo = [t for t in tasks if t["status"] == ST["todo"]]
    md_items, _ = parse_todo_md()
    md_doing = [i for i in md_items if i["doing"] and not i["sub"]]

    hot = len(p0) + len(review) + len(soon)
    print(f"🎛️{hot if hot else ''}")
    print("---")
    print(f"⌨️ 交给 Claude… | bash={ASK} terminal=false {FONT}")
    print(f"🖥 打开掌控台 | href=http://127.0.0.1:{PORT}/ {FONT}")
    print("---")
    if projects:
        by_line = {}
        for p in projects:
            by_line.setdefault(p.get("line", "其他"), []).append(p)
        print(f"🗺 战线 ({len(by_line)}) | {FONT}")
        for line in sorted(by_line, key=lambda l: -sum(x.get("alive", 0)
                                                       for x in by_line[l])):
            ps = by_line[line]
            alive = sum(x.get("alive", 0) for x in ps)
            print(f"-- {line} · {alive} 条活任务 | {FONT}")
            for p in sorted(ps, key=lambda x: -x.get("alive", 0)):
                print(f"---- [{p.get('stage') or '—'}] {clip(p['title'], 34)} "
                      f"{p.get('done', 0)}/{p.get('total', 0)} | href={BASE_URL} {FONT}")
        print("---")
    if p0:
        print(f"🔴 P0 命门 ({len(p0)}) | {FONT} color=#c0563f")
        for t in p0:
            print(f"{clip(t['title'])} | href={BASE_URL} {FONT}")
    if review:
        print(f"🟠 待你审核 ({len(review)}) | {FONT} color=#b98328")
        for t in review:
            print(f"{clip(t['title'])} | href={BASE_URL} {FONT}")
    if soon:
        print(f"⏰ 3 天内到期 ({len(soon)}) | {FONT} color=#b98328")
        for t in soon:
            d = datetime.fromtimestamp(t["ddl"] / 1000).strftime("%m/%d")
            print(f"[{d}] {clip(t['title'], 38)} | href={BASE_URL} {FONT}")
    if md_doing:
        print(f"📋 个人进行中 ({len(md_doing)}) | {FONT}")
        for i in md_doing[:8]:
            print(f"{clip(i['title'])} | {FONT}")
    print("---")
    print(f"🟢 进行中 {len(doing)} 条 | {FONT}")
    for t in doing[:15]:
        print(f"-- {clip(t['title'])} | href={BASE_URL} {FONT}")
    print(f"⚪ 待办 {len(todo)} 条 | {FONT}")
    for t in todo[:15]:
        print(f"-- {clip(t['title'])} | href={BASE_URL} {FONT}")
    print("---")
    print(f"数据时间 {cache_ts or '无缓存'} | {FONT} color=#8a857b")
    print(f"🔄 立即拉取刷新 | bash=/usr/bin/python3 param1={RENDER} "
          f"terminal=false refresh=true {FONT}")


if __name__ == "__main__":
    main()
