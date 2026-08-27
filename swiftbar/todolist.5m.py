#!/usr/bin/env python3
"""SwiftBar 插件：菜单栏战线视图（每 5 分钟刷新，只读本地缓存，不打网络）

结构：业务线为一等公民（=项目归属，单表单维度）——每条线顶层展开，
线内先亮 P0/待审/临期火警，再直列进行中任务，待办/暂停收进子菜单。
"""
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


def clip(s, n=40):
    return s if len(s) <= n else s[: n - 1] + "…"


def main():
    tasks, cache_ts = [], ""
    if CACHE.exists():
        c = json.loads(CACHE.read_text())
        tasks = c.get("tasks", [])
        cache_ts = c.get("ts", "")[:16].replace("T", " ")
    now = datetime.now()
    soon_ts = (now + timedelta(days=3)).timestamp() * 1000
    paused = ST["paused"]

    def is_hot(t):
        if t["status"] == paused:
            return False
        return ((t.get("prio") or "").startswith("P0")
                or t["status"] == ST["review"]
                or (t.get("ddl") and t["ddl"] <= soon_ts))

    hot_total = sum(1 for t in tasks if is_hot(t))
    print(f"🎛️{hot_total if hot_total else ''}")
    print("---")
    print(f"⌨️ 交给 Claude… | bash={ASK} terminal=false {FONT}")
    print(f"🖥 打开掌控台 | href=http://127.0.0.1:{PORT}/ {FONT}")

    lines = {}
    for t in tasks:
        lines.setdefault(t.get("line", "其他"), []).append(t)

    def alive_count(ts):
        return sum(1 for t in ts if t["status"] != paused)

    for line in sorted(lines, key=lambda l: -alive_count(lines[l])):
        ts_line = lines[line]
        hot = [t for t in ts_line if is_hot(t)]
        print("---")
        flame = f" · 🔴{len(hot)}" if hot else ""
        print(f"{line} · {alive_count(ts_line)} 活{flame} | {FONT} color=#555555")
        for t in hot:
            mark = "🔴" if (t.get("prio") or "").startswith("P0") else (
                "🟠" if t["status"] == ST["review"] else "⏰")
            d = datetime.fromtimestamp(t["ddl"] / 1000).strftime("%m/%d") if t.get("ddl") else ""
            print(f"{mark} {clip(t['title'], 36)} {d} | href={BASE_URL} {FONT} color=#c0563f")
        doing = [t for t in ts_line if t["status"] == ST["doing"] and not is_hot(t)]
        for t in doing:
            print(f"🔨 {clip(t['title'], 36)} | href={BASE_URL} {FONT}")
        todo = [t for t in ts_line if t["status"] == ST["todo"] and not is_hot(t)]
        if todo:
            print(f"▫️ 待办 ({len(todo)}) | {FONT}")
            for t in todo:
                print(f"-- {clip(t['title'])} | href={BASE_URL} {FONT}")
        pz = [t for t in ts_line if t["status"] == paused]
        if pz:
            print(f"⏸ 暂停 ({len(pz)}) | {FONT}")
            for t in pz:
                print(f"-- {clip(t['title'])} | href={BASE_URL} {FONT}")

    md_items, _ = parse_todo_md()
    md_doing = [i for i in md_items if i["doing"] and not i["sub"]]
    if md_doing:
        print("---")
        print(f"📋 个人进行中 ({len(md_doing)}) | {FONT}")
        for i in md_doing[:8]:
            print(f"-- {clip(i['title'])} | {FONT}")
    print("---")
    print(f"数据时间 {cache_ts or '无缓存'} | {FONT} color=#8a857b")
    print(f"🔄 立即拉取刷新 | bash=/usr/bin/python3 param1={RENDER} "
          f"terminal=false refresh=true {FONT}")


if __name__ == "__main__":
    main()
