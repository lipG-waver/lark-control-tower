#!/bin/bash
# 菜单栏「交给 Claude…」— 弹输入框，拿到内容后开新 Terminal 跑 claude
# 注意：必须先 activate 再 display dialog，否则后台进程弹的框拿不到键盘焦点（无光标/中文输入法不挂载）
HERE="$(cd "$(dirname "$0")" && pwd)"
WORKDIR=$(/usr/bin/python3 -c "import json,pathlib;print(pathlib.Path(json.load(open('$HERE/config.json')).get('claude_workdir','~')).expanduser())")
PROMPT=$(osascript <<'EOF' 2>/dev/null
tell application "System Events"
  activate
  set r to display dialog "想让 Claude 干什么？" default answer "" with title "🎛️ 掌控台 → Claude" buttons {"取消", "启动"} default button "启动"
  return text returned of r
end tell
EOF
)
if [ -n "$PROMPT" ]; then
  osascript "$HERE/launch_claude.applescript" "$PROMPT" "$WORKDIR"
fi
