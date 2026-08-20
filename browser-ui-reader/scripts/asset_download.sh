#!/usr/bin/env bash
# 批量下载图片 URL 到目录。
# 用法: asset_download.sh <urls文件> <输出目录>
# urls文件:
#   - .txt: 每行一个 URL（也接受 HTML/JSON 里混着的 URL，按行提取）
#   - .json: 字符串数组，或对象数组（取 src / url 字段）
# 去重，存为 hash8-原文件名；单张失败不中断，结尾报 FAIL 数。
set -uo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: asset_download.sh <urls-file> <out-dir>" >&2
  exit 2
fi
file="$1"
dir="$2"

[ -f "$file" ] || { echo "asset_download: 找不到 $file" >&2; exit 1; }
mkdir -p "$dir"

is_json=0
if [ "${file##*.}" = "json" ] || [[ "$(head -c1 "$file")" == "[" ]] || [[ "$(head -c1 "$file")" == "{" ]]; then
  is_json=1
fi

if [ "$is_json" -eq 1 ]; then
  urls=$(python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
items = d if isinstance(d, list) else (d.get("images") or d.get("imgs") or [])
for it in items:
    if isinstance(it, dict):
        it = it.get("src") or it.get("url")
    if isinstance(it, str):
        print(it)
' "$file" 2>/dev/null) || { echo "asset_download: JSON 解析失败" >&2; exit 1; }
else
  urls=$(grep -Eo 'https?://[^"'"'"' ]+' "$file" | head -2000)
fi

[ -n "$urls" ] || { echo "asset_download: $file 里没有 URL" >&2; exit 1; }

cd "$dir"
ok=0
fail=0
while IFS= read -r u; do
  [ -n "$u" ] || continue
  # 去重：按 URL 的 md5
  h=$(printf '%s' "$u" | md5 -q | cut -c1-8)
  base=$(printf '%s' "$u" | awk -F/ '{print $NF}')
  base=${base%%\?*}
  base=$(printf '%s' "$base" | tr -c 'A-Za-z0-9._-' '_')
  [ -n "$base" ] || base="asset"
  name="${h}_${base}"
  if curl -fsSL --max-time 30 -- "$u" -o "$name"; then
    echo "OK   $name  <-  $u"
    ok=$((ok+1))
  else
    echo "FAIL $u" >&2
    fail=$((fail+1))
  fi
done < <(printf '%s\n' "$urls" | awk '!seen[$0]++')

echo "----" >&2
echo "done: $ok ok, $fail fail -> $dir" >&2
[ "$fail" -eq 0 ]
