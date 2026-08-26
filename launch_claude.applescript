-- 用法: osascript launch_claude.applescript "任务内容" ["工作目录"]
-- 开一个新 Terminal 窗口，cd 到工作目录并带着 prompt 启动 claude
on run argv
  set thePrompt to item 1 of argv
  if (count of argv) > 1 then
    set theDir to item 2 of argv
  else
    set theDir to (POSIX path of (path to home folder))
  end if
  tell application "Terminal"
    activate
    do script "cd " & quoted form of theDir & " && claude " & quoted form of thePrompt
  end tell
end run
