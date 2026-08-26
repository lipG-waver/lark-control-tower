#!/usr/bin/env python3
"""SwiftBar 插件：菜单栏战线视图（每 5 分钟刷新，只读本地缓存，不打网络）

结构：战线为一等公民——每条战线顶层展开，线内先亮 P0/临期火警，
再列项目（阶段+进度，子菜单=该项目的活任务），散活收进子菜单。
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
STAGE_ICON = {"构想": "💭", "搭建": "🔨", "验收": "🔍", "上线": "🚀",
              "运维": "⚙️", "等外部": "⏳"}


def clip(s, n=40):
    return s if len(s) <= n else s[: n - 1] + "…"


def main():
    tasks, projects, cache_ts = [], [], ""
    if CACHE.exists():
        c = json.loads(CACHE.read_text())
        tasks = c.get("tasks", [])
        projects = c.get("projects", [])
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
    for p in projects:
        lines.setdefault(p.get("line", "其他"), {"projects": [], "tasks": []})["projects"].append(p)
    for t in tasks:
        lines.setdefault(t.get("line", "其他"), {"projects": [], "tasks": []})["tasks"].append(t)

    def alive_count(L):
        return sum(1 for t in L["tasks"] if t["status"] != paused)

    for line in sorted(lines, key=lambda l: -alive_count(lines[l])):
        L = lines[line]
        hot = [t for t in L["tasks"] if is_hot(t)]
        print("---")
        flame = f" · 🔴{len(hot)}" if hot else ""
        print(f"{line} · {alive_count(L)} 活{flame} | {FONT} color=#555555")
        for t in hot:
            mark = "🔴" if (t.get("prio") or "").startswith("P0") else (
                "🟠" if t["status"] == ST["review"] else "⏰")
            d = datetime.fromtimestamp(t["ddl"] / 1000).strftime("%m/%d") if t.get("ddl") else ""
            print(f"{mark} {clip(t['title'], 36)} {d} | href={BASE_URL} {FONT} color=#c0563f")
        for p in sorted(L["projects"], key=lambda x: -x.get("alive", 0)):
            icon = STAGE_ICON.get(p.get("stage") or "", "▫️")
            print(f"{icon} {clip(p['title'], 32)} · {p.get('done', 0)}/{p.get('total', 0)}"
                  f" | href={BASE_URL} {FONT}")
            kids = [t for t in L["tasks"] if t.get("parent") == p["rid"] and not is_hot(t)]
            for t in kids:
                pz = "⏸ " if t["status"] == paused else ""
                print(f"-- {pz}{clip(t['title'])} | href={BASE_URL} {FONT}")
        loose = [t for t in L["tasks"]
                 if not any(t.get("parent") == p["rid"] for p in L["projects"])
                 and not is_hot(t)]
        if loose:
            print(f"▫️ 散活 ({len(loose)}) | {FONT}")
            for t in loose:
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
