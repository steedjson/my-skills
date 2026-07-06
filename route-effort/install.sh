#!/bin/bash
# route-effort 独立安装入口（薄壳）
# 直接调用包级安装器，等价于：
#   cd .. && ./install.sh route-effort [options]
#
# 用法：
#   ./install.sh
#   ./install.sh --with-skill-opt
#   ./install.sh --with-skill-opt --with-workflow
#
# 远程安装：
#   curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort/install.sh | bash

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-/dev/stdin}")" 2>/dev/null && pwd || echo "")"
IS_LOCAL=false
if [ -n "$SKILL_DIR" ] && [ "$SKILL_DIR" != "/" ]; then
  IS_LOCAL=true
  ROOT_INSTALL="$SKILL_DIR/../install.sh"
fi

if [ "$IS_LOCAL" = true ] && [ -f "$ROOT_INSTALL" ]; then
  # 本地：调用根安装器安装此 skill
  exec bash "$ROOT_INSTALL" route-effort "$@"
else
  # 远程：下载根安装器执行
  TMP=$(mktemp)
  curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/install.sh -o "$TMP"
  bash "$TMP" route-effort "$@"
  rm -f "$TMP"
fi
