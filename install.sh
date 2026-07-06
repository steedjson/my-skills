#!/bin/bash
# vlong skills 包安装器
#
# 本地安装（推荐，符号链接，git pull 即时生效）：
#   ./install.sh                          # 安装全部 skill
#   ./install.sh route-effort             # 安装指定 skill
#   ./install.sh --with-skill-opt         # 安装全部 + 训练支持
#   ./install.sh route-effort --with-skill-opt --with-workflow
#
# 远程安装（复制文件）：
#   curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/install.sh | bash

set -euo pipefail

PACKAGE_NAME="vlong"
REPO_RAW="https://raw.githubusercontent.com/steedjson/my-skills/main"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-/dev/stdin}")" 2>/dev/null && pwd || echo "")"

# 检测本地/远程
IS_LOCAL=false
if [ -n "$SCRIPT_DIR" ] && [ "$SCRIPT_DIR" != "/" ] && [ -f "$SCRIPT_DIR/skills.json" ]; then
  IS_LOCAL=true
fi

export IS_LOCAL REPO_RAW

# 加载共享安装函数
if [ "$IS_LOCAL" = true ]; then
  source "$SCRIPT_DIR/shared/install_skill.sh"
else
  TMP_SHARED=$(mktemp)
  curl -fsSL "$REPO_RAW/shared/install_skill.sh" -o "$TMP_SHARED"
  source "$TMP_SHARED"
  rm -f "$TMP_SHARED"
fi

# 解析参数
SKILLS_TO_INSTALL=()
EXTRA_ARGS=()
INSTALL_ALL=false

for arg in "$@"; do
  case "$arg" in
    --all)              INSTALL_ALL=true ;;
    --with-skill-opt)   EXTRA_ARGS+=("$arg") ;;
    --with-workflow)    EXTRA_ARGS+=("$arg") ;;
    -*)                 ;;
    *)                  SKILLS_TO_INSTALL+=("$arg") ;;
  esac
done

# 从 skills.json 读取所有 skill 名
if command -v jq &>/dev/null && [ "$IS_LOCAL" = true ]; then
  ALL_SKILLS=$(jq -r '.skills[].name' "$SCRIPT_DIR/skills.json")
else
  # fallback：遍历子目录
  ALL_SKILLS=$(find "$SCRIPT_DIR" -maxdepth 2 -name "SKILL.md" | sed "s|$SCRIPT_DIR/||;s|/SKILL.md||")
fi

# 确定要安装的 skill 列表
if [ "$INSTALL_ALL" = true ] || [ ${#SKILLS_TO_INSTALL[@]} -eq 0 ]; then
  mapfile -t SKILLS_TO_INSTALL < <(echo "$ALL_SKILLS")
fi

# 输出标题
PKG_VERSION=$([ "$IS_LOCAL" = true ] && grep '"version"' "$SCRIPT_DIR/skills.json" 2>/dev/null | head -1 | grep -o '"[0-9.]*"' | tr -d '"' || echo "?")
echo "╔══════════════════════════════════════╗"
echo "║  $PACKAGE_NAME skills  v${PKG_VERSION}                    ║"
echo "╚══════════════════════════════════════╝"
echo ""
[ "$IS_LOCAL" = true ] && echo "模式：本地安装（符号链接）" || echo "模式：远程安装（复制文件）"
echo "技能：${SKILLS_TO_INSTALL[*]}"
echo ""

# 安装每个 skill
for skill in "${SKILLS_TO_INSTALL[@]}"; do
  install_skill "$skill" "${EXTRA_ARGS[@]}"
done

echo "所有安装完成！"
echo ""
echo "升级方式："
if [ "$IS_LOCAL" = true ]; then
  echo "  git pull   # 符号链接自动生效，无需重新安装"
else
  echo "  curl -fsSL $REPO_RAW/install.sh | bash"
fi
