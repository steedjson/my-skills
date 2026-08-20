#!/usr/bin/env bash
# 列出 Google Chrome 全部标签页：tab序号 / 标题 / URL
set -euo pipefail

osascript <<'EOF'
on run
  tell application "Google Chrome"
    set total to (count of windows)
    if total = 0 then
      return "NO_WINDOWS"
    end if
    set out to ""
    repeat with w in windows
      repeat with i from 1 to (count of tabs of w)
        set t to tab i of w
        set out to out & i & " / " & (title of t) & " / " & (URL of t) & linefeed
      end repeat
    end repeat
  end tell
  if out is "" then
    return "NO_TABS"
  end if
  return out
end run
EOF
