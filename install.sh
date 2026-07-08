#!/bin/bash
# vlong skills 安装器
#
# 用法：
#   curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/install.sh | bash
#   curl -fsSL .../install.sh | bash -s -- route-effort
#   curl -fsSL .../install.sh | bash -s -- route-effort --with-skill-opt
#   curl -fsSL .../install.sh | bash -s -- route-effort --with-skill-opt --with-workflow
#   curl -fsSL .../install.sh | bash -s -- --all --with-skill-opt

set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/steedjson/my-skills/main"
export REPO_RAW

# 加载共享安装函数
TMP_SHARED=$(mktemp)
trap 'rm -f "${TMP_SHARED:-}"' EXIT
curl -fsSL "$REPO_RAW/shared/install_skill.sh" -o "$TMP_SHARED"
source "$TMP_SHARED"

# 解析参数
SKILLS_TO_INSTALL=()
EXTRA_ARGS=()
INSTALL_ALL=false

for arg in "$@"; do
  case "$arg" in
    --all)             INSTALL_ALL=true ;;
    --with-skill-opt)  EXTRA_ARGS+=("$arg") ;;
    --with-workflow)   EXTRA_ARGS+=("$arg") ;;
    -*)                ;;
    *)                 SKILLS_TO_INSTALL+=("$arg") ;;
  esac
done

# 默认安装全部
if [ "$INSTALL_ALL" = true ] || [ ${#SKILLS_TO_INSTALL[@]} -eq 0 ]; then
  SKILLS_TO_INSTALL=($(curl -fsSL "$REPO_RAW/skills.json" | grep '"name"' | grep -v '"vlong"' | sed 's/.*"name": *"\([^"]*\)".*/\1/'))
fi

# 标题
echo "╔══════════════════════════════╗"
echo "║        vlong skills          ║"
echo "╚══════════════════════════════╝"
echo ""
echo "安装：${SKILLS_TO_INSTALL[*]}"
echo ""

for skill in "${SKILLS_TO_INSTALL[@]}"; do
  install_skill "$skill" "${EXTRA_ARGS[@]}"
done

echo "完成！升级：重新运行安装命令"
