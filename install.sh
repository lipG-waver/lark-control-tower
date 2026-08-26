#!/bin/bash
# 一键安装：launchd 定时渲染（每 30 分钟）+ 常驻本地服务 + SwiftBar 插件目录配置
# 重复运行安全（会先卸载再装载）
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
LA="$HOME/Library/LaunchAgents"

if [ ! -f "$HERE/config.json" ]; then
  echo "❌ 缺 config.json — 先 cp config.example.json config.json 并填好"
  exit 1
fi

chmod +x "$HERE/ask_claude.sh" "$HERE/swiftbar/todolist.5m.py"

echo "== 1/4 首次渲染"
/usr/bin/python3 "$HERE/render_console.py"

echo "== 2/4 装载 launchd（定时渲染 + 常驻服务）"
make_plist() {
  local label=$1; shift
  local keep=$1; shift
  cat > "$LA/$label.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array><string>/usr/bin/python3</string><string>$1</string></array>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  $keep
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/tmp/$label.log</string>
  <key>StandardErrorPath</key><string>/tmp/$label.log</string>
</dict>
</plist>
EOF
  launchctl unload "$LA/$label.plist" 2>/dev/null || true
  launchctl load "$LA/$label.plist"
}
make_plist "com.lark-control-tower.render" "<key>StartInterval</key><integer>1800</integer>" "$HERE/render_console.py"
make_plist "com.lark-control-tower.server" "<key>KeepAlive</key><true/>" "$HERE/server.py"

echo "== 3/4 配置 SwiftBar 插件目录"
if [ -d "/Applications/SwiftBar.app" ]; then
  defaults write com.ameba.SwiftBar PluginDirectory "$HERE/swiftbar"
  open -a SwiftBar
  echo "   SwiftBar 已启动，菜单栏应出现 🎛️ 图标"
else
  echo "   ⚠️ SwiftBar.app 未安装（brew install --cask swiftbar），装好后重跑本脚本"
fi

echo "== 4/4 自检"
sleep 2
PORT=$(/usr/bin/python3 -c "import json;print(json.load(open('$HERE/config.json')).get('port',8765))")
curl -s "http://127.0.0.1:$PORT/health" && echo "  ← 服务正常"
echo "全部完成 ✅  仪表盘: http://127.0.0.1:$PORT/"
