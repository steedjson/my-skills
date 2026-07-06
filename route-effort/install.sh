#!/bin/bash
# route-effort 独立安装入口（薄壳）
# 等价于：curl -fsSL .../install.sh | bash -s -- route-effort [options]
#
# 用法：
#   curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort/install.sh | bash
#   curl -fsSL .../route-effort/install.sh | bash -s -- --with-skill-opt
#   curl -fsSL .../route-effort/install.sh | bash -s -- --with-skill-opt --with-workflow

set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/steedjson/my-skills/main"
TMP=$(mktemp)
curl -fsSL "$REPO_RAW/install.sh" -o "$TMP"
bash "$TMP" route-effort "$@"
rm -f "$TMP"
