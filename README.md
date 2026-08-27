# 🎛️ lark-control-tower

把散落各处的 TODO 收进**一页永远最新的掌控台**：定时拉取飞书多维表格任务 +（可选）本地
Markdown 清单，渲染成自刷新 HTML 仪表盘，挂到 macOS 菜单栏，还能一键把任务丢给
[Claude Code](https://claude.com/claude-code) 去干。

为什么做这个：任务真源在飞书表里没问题，但「要打开飞书才看得到」本身就制造失控感——
事情很多、没有抓手。解法不是再造一个 TODO 应用，而是给已有真源做一个**只读聚合视图**：
随时抬头可见、自动保鲜、告诉你"此刻真正要盯的只有 N 条，其余都折叠好了——都在，跑不掉"。

## 它长什么样

- **HTML 仪表盘**（每 30 分钟自动重渲染，页面每 10 分钟自刷新）：
  🗺 战线（每条业务线：活任务数 + 最近 DDL + 最近完成）→ 🔴 P0 → 🟠 待审 → ⏰ 3 天内到期 → 📋 个人清单 → 🟢 进行中 / ⚪ 待办（按业务线折叠）
- **菜单栏下拉**（SwiftBar 插件）：时钟旁一个 🎛️ 图标 + 热点数字，点开就是 TODO 列表
- **⌨️ 交给 Claude**：仪表盘底部输入框 / 菜单栏弹窗，输入任务回车 →
  自动开新 Terminal 窗口，`cd` 到你的工作目录并带着这句话启动 `claude`

## 架构

```
render_console.py   拉飞书表(lark-cli bot) + 解析 TODO.md → 渲染 dashboard.html
                    失败时用 cache.json 兜底渲染并挂"数据过期"横幅
server.py           127.0.0.1 本地服务: GET / 看板 · POST /run 启动 claude
launch_claude.applescript   开新 Terminal 窗口跑 claude "<prompt>"
ask_claude.sh       菜单栏输入弹窗（System Events activate，修键盘焦点/中文输入法）
swiftbar/todolist.5m.py     SwiftBar 菜单栏插件（只读 cache，不打网络）
install.sh          一键装 launchd（定时渲染+常驻服务）+ 配 SwiftBar
```

## 前置条件

- macOS
- [`lark-cli`](https://www.npmjs.com/package/@larksuite/cli)（`npm i -g @larksuite/cli`），
  且 bot 身份对目标多维表格有读权限（`bitable:app:readonly`）
- 一张任务多维表格，含字段：任务标题 / 状态 / 优先级（P0🔴~P3🟢）/ 业务线 / 认领人 /
  截止日期 / 详情备注 / 完成时间（字段名可在 config 改）。
  设计哲学：**单任务表**——一行=一件可做完的事，「业务线」单选字段即项目归属，
  不设项目级记录；「战线」区直接从任务按业务线聚合（活任务数 / 最近 DDL / 最近完成）
- 可选：[Claude Code](https://claude.com/claude-code) CLI（「交给 Claude」功能用）
- 可选：[SwiftBar](https://github.com/swiftbar/SwiftBar)（菜单栏入口用）

## 安装

```bash
git clone https://github.com/lipG-waver/lark-control-tower.git
cd lark-control-tower
cp config.example.json config.json   # 填 tenant / app_token / table_id
bash install.sh
```

`config.json` 说明：

| 键 | 含义 |
|---|---|
| `feishu.tenant` | 你的飞书租户域名，如 `xxx.feishu.cn` |
| `feishu.app_token` | 多维表格 URL `/base/` 后那串 |
| `feishu.table_id` | 表 id（`tbl` 开头） |
| `feishu.fields` | 你表里的字段名映射 |
| `feishu.closed_statuses` | 不展示的终态（默认 已完成/取消） |
| `todo_md` | 可选，本地 Markdown 清单路径（识别 `- ☐` / `- ◐` 条目） |
| `output` | 渲染产物路径（默认仓库内 `dashboard.html`） |
| `claude_workdir` | 「交给 Claude」时 cd 到哪个目录 |
| `port` | 本地服务端口（默认 8765） |

## 安全说明

- 服务只绑 `127.0.0.1`，不对外网开放；`/run` 用 argv 传参给 osascript，无 shell 注入面
- `config.json` / `cache.json`（含真实任务数据）/ 渲染产物均已 gitignore，**不要提交**
- 国内网络装 SwiftBar 走 GitHub 镜像时，务必用 Homebrew cask 钉的 sha256 校验包再装：
  `brew info --cask swiftbar --json=v2 | jq -r '.casks[0].sha256'` 对比 `shasum -a 256`

## 设计取向

- **只读视图，不做第三套账**：改任务永远回真源（飞书表 / TODO.md）改，看板不写回
- **失败要可见**：拉取失败不是白屏，是缓存兜底 + 显式的"数据过期"横幅
- **折叠但不隐藏**：失控感的解药不是把任务藏起来，是每件事都有个可见的位置

## License

MIT
