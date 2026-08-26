#!/usr/bin/env python3
"""控制塔渲染器 — 拉飞书多维表格 TODO（lark-cli bot 身份）+ 可选解析本地
TODO.md，渲染成一页自刷新 HTML 仪表盘。

配置在同目录 config.json（复制 config.example.json 改）。
拉取失败时用上次缓存渲染并挂"数据可能过期"横幅。
手动跑: python3 render_console.py
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache.json"


def load_config():
    p = HERE / "config.json"
    if not p.exists():
        sys.exit("缺 config.json — 先 cp config.example.json config.json 并填好")
    cfg = json.loads(p.read_text())
    for k in ("todo_md", "output", "claude_workdir"):
        if cfg.get(k):
            cfg[k] = str(Path(cfg[k]).expanduser())
    if not Path(cfg["output"]).is_absolute():
        cfg["output"] = str(HERE / cfg["output"])
    return cfg


CFG = load_config()
F = CFG["feishu"]["fields"]
ST = CFG["feishu"]["status_names"]
BASE_URL = f"https://{CFG['feishu']['tenant']}/base/{CFG['feishu']['app_token']}"

PRIO_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def prio_rank(p):
    return PRIO_ORDER.get((p or "")[:2], 4)


def flat_text(v):
    if isinstance(v, list):
        return "".join(s.get("text", "") for s in v if isinstance(s, dict))
    return v or ""


def fetch_feishu():
    body = {
        "page_size": 500,
        "filter": {
            "conjunction": "and",
            "conditions": [
                {"field_name": F["status"], "operator": "isNot", "value": [s]}
                for s in CFG["feishu"]["closed_statuses"]
            ],
        },
    }
    cmd = [
        "lark-cli", "api", "POST",
        f"/open-apis/bitable/v1/apps/{CFG['feishu']['app_token']}"
        f"/tables/{CFG['feishu']['table_id']}/records/search",
        "--data", json.dumps(body, ensure_ascii=False), "--as", "bot",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    d = json.loads(r.stdout)
    if d.get("code") != 0:
        raise RuntimeError(f"lark code={d.get('code')} {d.get('msg')}")
    tasks = []
    for it in d["data"]["items"]:
        f = it["fields"]
        title = flat_text(f.get(F["title"])).strip()
        if not title:
            continue
        tasks.append({
            "title": title,
            "status": f.get(F["status"]) or ST["todo"],
            "prio": f.get(F["priority"]),
            "line": f.get(F["line"]) or "其他",
            "owner": "、".join(u.get("name", "")
                              for u in (f.get(F["owner"]) or [])),
            "ddl": f.get(F["ddl"]),
            "note": flat_text(f.get(F["note"])).strip(),
            "rid": it["record_id"],
        })
    return tasks


def parse_todo_md():
    """抓 TODO.md 里 ☐/◐ 的条目（"长期/G 节"单独收进折叠区）。"""
    path = CFG.get("todo_md")
    if not path or not Path(path).exists():
        return [], []
    items, longterm = [], []
    section = ""
    in_g = False
    for line in Path(path).read_text().splitlines():
        h = re.match(r"^#{2,3}\s+(.*)", line)
        if h:
            section = h.group(1).strip()
            in_g = bool(re.match(r"^G\d?\.?", section)) or "长期" in section
            continue
        m = re.match(r"^(\s*)- ([☐◐])\s*\*{0,2}(.+?)\*{0,2}\s*(?:—|$)", line)
        if not m:
            continue
        indent, mark, title = m.group(1), m.group(2), m.group(3).strip()
        title = re.sub(r"\*+", "", title)
        entry = {"title": title, "doing": mark == "◐", "section": section,
                 "sub": len(indent) > 0}
        (longterm if in_g else items).append(entry)
    return items, longterm


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def ddl_badge(ms, now):
    if not ms:
        return ""
    d = datetime.fromtimestamp(ms / 1000)
    days = (d.date() - now.date()).days
    label = d.strftime("%m/%d")
    if days < 0:
        return f'<span class="ddl over">已过期 {label}</span>'
    if days <= 3:
        return f'<span class="ddl soon">DDL {label}</span>'
    return f'<span class="ddl">DDL {label}</span>'


def task_row(t, now):
    pc = f"p{t['prio'][1]}" if t["prio"] and len(t["prio"]) > 1 and t["prio"][1].isdigit() else "px"
    prio = f'<span class="pr {pc}">{esc(t["prio"] or "—")}</span>'
    owner = f'<span class="mm"> · {esc(t["owner"])}</span>' if t["owner"] else ""
    note = esc(t["note"][:120])
    note_html = f'<div class="mm nt">{note}</div>' if note else ""
    return (f'<div class="mini"><div class="mt">{prio}{esc(t["title"])}'
            f'{ddl_badge(t["ddl"], now)}{owner}</div>{note_html}</div>')


def render(tasks, todo_items, todo_long, now, stale_msg=""):
    p0 = [t for t in tasks if (t["prio"] or "").startswith("P0")
          and t["status"] != ST["paused"]]
    review = [t for t in tasks if t["status"] == ST["review"]]
    ddl_soon = [t for t in tasks if t["ddl"] and
                datetime.fromtimestamp(t["ddl"] / 1000) <= now + timedelta(days=3)
                and t["status"] != ST["paused"] and t not in p0]
    doing = [t for t in tasks if t["status"] == ST["doing"] and t not in p0]
    todo = [t for t in tasks if t["status"] == ST["todo"] and t not in p0]
    paused = [t for t in tasks if t["status"] == ST["paused"]]
    for lst in (doing, todo):
        lst.sort(key=lambda t: (prio_rank(t["prio"]), t["line"]))

    md_doing = [i for i in todo_items if i["doing"] and not i["sub"]]
    md_todo = [i for i in todo_items if not i["doing"] and not i["sub"]]

    def group_by_line(lst):
        g = {}
        for t in lst:
            g.setdefault(t["line"], []).append(t)
        return sorted(g.items(), key=lambda kv: -len(kv[1]))

    def details_block(summary, rows, open_=False):
        op = " open" if open_ else ""
        return (f'<details{op}><summary><span class="chev">▶</span>{summary}</summary>'
                + "".join(rows) + "</details>")

    top_count = len(p0) + len(review) + len(ddl_soon) + len(md_doing)
    stale_html = f'<div class="stale">⚠️ {esc(stale_msg)}</div>' if stale_msg else ""

    focus_rows = "".join(task_row(t, now) for t in p0)
    review_rows = "".join(task_row(t, now) for t in review)
    ddl_rows = "".join(task_row(t, now) for t in ddl_soon)

    doing_blocks = "".join(
        details_block(f'{esc(line)} <span class="cnt">{len(ts)}</span>',
                      [task_row(t, now) for t in ts])
        for line, ts in group_by_line(doing))
    todo_blocks = "".join(
        details_block(f'{esc(line)} <span class="cnt">{len(ts)}</span>',
                      [task_row(t, now) for t in ts])
        for line, ts in group_by_line(todo))
    paused_rows = "".join(task_row(t, now) for t in paused)

    md_doing_rows = "".join(
        f'<div class="mini"><div class="mt">◐ {esc(i["title"])}'
        f'<span class="mm"> · {esc(i["section"][:24])}</span></div></div>'
        for i in md_doing)
    md_todo_rows = "".join(
        f'<div class="mini"><div class="mt">☐ {esc(i["title"])}'
        f'<span class="mm"> · {esc(i["section"][:24])}</span></div></div>'
        for i in md_todo)
    md_long_rows = "".join(
        f'<div class="mini"><div class="mt">{esc(i["title"])}'
        f'<span class="mm"> · {esc(i["section"][:24])}</span></div></div>'
        for i in todo_long)

    md_section = ""
    if todo_items or todo_long:
        md_section = f"""
<section><div class="sh"><h2>📋 个人清单（TODO.md）</h2><span class="sub">进行中 {len(md_doing)} · 待办 {len(md_todo)}</span></div>
<div class="card">{md_doing_rows or ''}</div>
<details><summary><span class="chev">▶</span>个人待办 <span class="cnt">{len(md_todo)}</span></summary>{md_todo_rows}</details>
</section>"""
        md_long_block = (f'<details><summary><span class="chev">▶</span>🗓 长期议题 '
                         f'<span class="cnt">{len(todo_long)}</span></summary>{md_long_rows}</details>')
    else:
        md_long_block = ""

    ts_str = now.strftime("%Y-%m-%d %H:%M")
    weekday = "一二三四五六日"[now.weekday()]
    port = CFG["port"]

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="600">
<title>掌控台 · 全部在这</title>
<style>
:root{{--bg:#f5f3ee;--card:#fffdf8;--ink:#2b2a27;--mut:#8a857b;--line:#e6e1d6;
--red:#c0563f;--redbg:#fbeee9;--amber:#b98328;--amberbg:#f9f1df;--green:#5a8a5f;
--greenbg:#eef4ec;--shadow:0 1px 3px rgba(60,50,30,.06),0 6px 20px rgba(60,50,30,.05)}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
font-family:-apple-system,"PingFang SC","Helvetica Neue",Arial,sans-serif;
line-height:1.6;-webkit-font-smoothing:antialiased;padding:0 0 80px}}
.wrap{{max-width:780px;margin:0 auto;padding:0 22px}}
header{{padding:38px 0 8px}}
h1{{font-size:25px;margin:0 0 4px;font-weight:700}}
.date{{color:var(--mut);font-size:13.5px}}
.stale{{background:var(--amberbg);border:1px solid #ecdcb4;color:var(--amber);
border-radius:10px;padding:10px 14px;margin:14px 0;font-size:13.5px;font-weight:600}}
.lead{{margin:18px 0 8px;background:var(--card);border:1px solid var(--line);
border-radius:16px;padding:20px 24px;box-shadow:var(--shadow)}}
.lead .big{{font-size:18px;font-weight:600;line-height:1.55}}
.lead .big b{{color:var(--red)}}
.counts{{display:flex;flex-wrap:wrap;gap:9px;margin-top:14px}}
.pill{{font-size:12.5px;padding:5px 12px;border-radius:20px;font-weight:600;
display:flex;align-items:center;gap:6px;border:1px solid transparent}}
.pill .n{{font-size:14.5px}}
.p-red{{background:var(--redbg);color:var(--red);border-color:#eecdc2}}
.p-amber{{background:var(--amberbg);color:var(--amber);border-color:#ecdcb4}}
.p-green{{background:var(--greenbg);color:var(--green);border-color:#cfe0cb}}
.p-grey{{background:#efece5;color:#9a958b;border-color:#e0dbd0}}
section{{margin-top:30px}}
.sh{{display:flex;align-items:baseline;gap:10px;margin:0 2px 12px}}
.sh h2{{font-size:16.5px;margin:0;font-weight:700}}
.sh .sub{{color:var(--mut);font-size:12.5px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:6px 17px;margin-bottom:11px;box-shadow:var(--shadow)}}
.card.red{{border-left:4px solid var(--red)}}
.mini{{padding:9px 0;border-top:1px solid var(--line);font-size:14px}}
.mini:first-child{{border-top:none}}
.mt{{font-weight:600;line-height:1.5}}
.mm{{color:var(--mut);font-size:12.5px;font-weight:400}}
.nt{{margin-top:2px}}
.pr{{display:inline-block;font-size:11px;padding:0 7px;border-radius:6px;
margin-right:7px;font-weight:700;vertical-align:1px}}
.p0{{background:var(--red);color:#fff}}.p1{{background:#f0dcc3;color:#9a6a1e}}
.p2{{background:#f2ecd4;color:#8a7a30}}.p3{{background:var(--greenbg);color:var(--green)}}
.px{{background:#efece5;color:#9a958b}}
.ddl{{display:inline-block;font-size:11px;padding:0 7px;border-radius:6px;
margin-left:7px;font-weight:700;background:#efece5;color:#9a958b}}
.ddl.soon{{background:var(--amberbg);color:var(--amber)}}
.ddl.over{{background:var(--red);color:#fff}}
details{{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:2px 17px;margin-bottom:10px;box-shadow:var(--shadow)}}
details summary{{cursor:pointer;padding:12px 0;font-weight:600;font-size:14.5px;
list-style:none;display:flex;align-items:center;gap:9px}}
details summary::-webkit-details-marker{{display:none}}
details summary .chev{{color:var(--mut);font-size:11px;transition:.2s}}
details[open] summary .chev{{transform:rotate(90deg)}}
.cnt{{background:#efece5;color:#7a756b;font-size:12px;border-radius:10px;
padding:0 8px;font-weight:700}}
footer{{margin-top:40px;color:var(--mut);font-size:12.5px;text-align:center;
border-top:1px solid var(--line);padding-top:18px;line-height:1.9}}
footer a{{color:var(--mut)}}
</style></head><body><div class="wrap">
<header><h1>🎛️ 掌控台</h1>
<div class="date">{ts_str}（周{weekday}） · 定时自动刷新 · 所有 TODO 都在这一页</div></header>
{stale_html}
<div class="lead">
<div class="big">全部盘点：飞书表 <b>{len(tasks)}</b> 条活任务{f' + 个人清单 <b>{len(md_doing) + len(md_todo)}</b> 条' if todo_items else ''}。<br>
此刻真正要盯的是下面 <b>{top_count}</b> 条，其余都折叠好了——都在，跑不掉。</div>
<div class="counts">
<span class="pill p-red"><span class="n">{len(p0)}</span> P0</span>
<span class="pill p-amber"><span class="n">{len(review)}</span> 待审</span>
<span class="pill p-amber"><span class="n">{len(ddl_soon)}</span> DDL≤3天</span>
<span class="pill p-green"><span class="n">{len(doing)}</span> 进行中</span>
<span class="pill p-grey"><span class="n">{len(todo)}</span> 待办</span>
<span class="pill p-grey"><span class="n">{len(paused)}</span> 暂停</span>
</div></div>

<section><div class="sh"><h2>🔴 P0 · 命门级</h2></div>
<div class="card red">{focus_rows or '<div class="mini mm">当前没有 P0</div>'}</div></section>

<section><div class="sh"><h2>🟠 待你审核</h2><span class="sub">球在你手上</span></div>
<div class="card">{review_rows or '<div class="mini mm">没有待审项</div>'}</div></section>

{f'<section><div class="sh"><h2>⏰ 3 天内到期</h2></div><div class="card red">{ddl_rows}</div></section>' if ddl_rows else ''}
{md_section}

<section><div class="sh"><h2>🟢 进行中（飞书表）</h2><span class="sub">按业务线折叠 · 共 {len(doing)} 条</span></div>
{doing_blocks}</section>

<section><div class="sh"><h2>⚪ 待办（飞书表）</h2><span class="sub">共 {len(todo)} 条</span></div>
{todo_blocks}</section>

<section>
<details><summary><span class="chev">▶</span>⏸ 暂停 <span class="cnt">{len(paused)}</span></summary>{paused_rows}</details>
{md_long_block}
</section>

<section><div class="sh"><h2>⌨️ 交给 Claude</h2><span class="sub">回车提交 · 自动开新 Terminal 窗口启动 claude</span></div>
<div class="card" style="padding:14px 17px">
<div style="display:flex;gap:10px">
<textarea id="cprompt" rows="2" placeholder="想让 Claude 干什么？"
 style="flex:1;resize:vertical;font:inherit;font-size:14px;border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:#fefcf6;color:var(--ink);outline:none"></textarea>
<button id="csend" onclick="runClaude()"
 style="flex:0 0 auto;font:inherit;font-size:14px;font-weight:600;border:none;border-radius:10px;padding:0 20px;background:var(--red);color:#fff;cursor:pointer">启动</button>
</div>
<div id="cstatus" class="mm" style="margin-top:8px"></div>
</div></section>

<footer>数据源：<a href="{BASE_URL}">飞书 TODO 表</a> · 生成于 {ts_str}<br>
改任务去真源改，这页只读 · <a href="https://github.com/lipG-waver/lark-control-tower">lark-control-tower</a></footer>
</div>
<script>
async function runClaude(){{
  const ta=document.getElementById('cprompt'), st=document.getElementById('cstatus');
  const p=ta.value.trim();
  if(!p) return;
  st.textContent='正在打开 Terminal…';
  try{{
    const r=await fetch('http://127.0.0.1:{port}/run',{{method:'POST',
      headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{prompt:p}})}});
    const d=await r.json();
    if(d.ok){{st.textContent='✅ 已开新 Terminal 窗口，claude 正在启动';ta.value='';}}
    else{{st.textContent='❌ '+(d.error||'启动失败');}}
  }}catch(e){{
    st.textContent='❌ 本地服务没在跑（127.0.0.1:{port}）— 跑 install.sh 后自动常驻';
  }}
}}
document.getElementById('cprompt').addEventListener('keydown',e=>{{
  if(e.key==='Enter'&&!e.shiftKey){{e.preventDefault();runClaude();}}
}});
</script>
</body></html>"""


def main():
    now = datetime.now()
    stale_msg = ""
    try:
        tasks = fetch_feishu()
        CACHE.write_text(json.dumps({"ts": now.isoformat(), "tasks": tasks},
                                    ensure_ascii=False))
    except Exception as e:
        if CACHE.exists():
            c = json.loads(CACHE.read_text())
            tasks = c["tasks"]
            stale_msg = f"飞书拉取失败（{e}），显示的是 {c['ts'][:16]} 的缓存数据"
        else:
            print(f"fetch failed and no cache: {e}", file=sys.stderr)
            sys.exit(1)
    todo_items, todo_long = parse_todo_md()
    out = Path(CFG["output"])
    out.write_text(render(tasks, todo_items, todo_long, now, stale_msg))
    print(f"ok {out} tasks={len(tasks)} md={len(todo_items)} stale={bool(stale_msg)}")


if __name__ == "__main__":
    main()
