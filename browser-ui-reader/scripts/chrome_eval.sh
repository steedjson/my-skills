#!/usr/bin/env bash
# 在 URL 包含 <url片段> 的 Chrome 标签里执行 JS 并打印返回值。
# 用法: chrome_eval.sh <url片段> <js表达式>
# JS 应返回字符串（推荐 JSON.stringify(...)）；返回 null 时输出空串。
# exit: 0 成功 / 3 无匹配标签 / 1 注入失败
set -uo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: chrome_eval.sh <url-substring> <js-expression>" >&2
  exit 2
fi
match="$1"
js="$2"

out=$(osascript - "$match" "$js" <<'APPLESCRIPT' 2>&1
on run argv
  set m to item 1 of argv
  set j to item 2 of argv
  tell application "Google Chrome"
    repeat with w in windows
      repeat with i from 1 to (count of tabs of w)
        set t to tab i of w
        if (URL of t) contains m then
          set r to execute t javascript j
          if r is missing value then
            return ""
          end if
          return (r as string)
        end if
      end repeat
    end repeat
  end tell
  return "NO_TAB_MATCH: " & m
end run
APPLESCRIPT
) && rc=0 || rc=$?

if [ "$rc" -ne 0 ]; then
  echo "chrome_eval: JS 注入失败。" >&2
  echo "  检查 Chrome：显示 → 开发者 → 允许 Apple 事件中的 JavaScript（Allow JavaScript from Apple Events）" >&2
  printf '%s\n' "$out" >&2
  exit 1
fi

case "$out" in
  NO_TAB_MATCH:*)
    echo "chrome_eval: 无标签 URL 包含 [$match]，先用 chrome_tabs.sh 确认目标地址" >&2
    exit 3
    ;;
esac

printf '%s\n' "$out"
exit 0
