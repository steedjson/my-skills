#!/bin/bash
# route-effort skill 安装脚本
# 支持两种方式：
#   本地：./install.sh
#   远程：curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort/install.sh | bash
#
# 可选标志：
#   --with-workflow   同时安装 effort-routed-task.js（Workflow 高级用法）

set -euo pipefail

VERSION="2.1.0"
REPO_RAW="https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort"
SKILL_DIR="$HOME/.claude/skills/route-effort"
WORKFLOW_DIR="$HOME/.claude/workflows"
WITH_WORKFLOW=false

for arg in "$@"; do
  [ "$arg" = "--with-workflow" ] && WITH_WORKFLOW=true
done

echo "=== Route-Effort Skill 安装程序 v${VERSION} ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-/dev/stdin}")" 2>/dev/null && pwd || echo "")"
IS_REMOTE=false
if [ -z "$SCRIPT_DIR" ] || [ "$SCRIPT_DIR" = "/" ]; then
  IS_REMOTE=true
fi

fetch_file() {
  local filename="$1"
  local dest="$2"
  if [ "$IS_REMOTE" = true ]; then
    echo "  ↓ 下载 $filename..."
    curl -fsSL "$REPO_RAW/$filename" -o "$dest"
  else
    echo "  ↓ 复制 $filename..."
    cp "$SCRIPT_DIR/$filename" "$dest"
  fi
}

if [ -f "$SKILL_DIR/SKILL.md" ]; then
  INSTALLED_VER=$(grep '^version:' "$SKILL_DIR/SKILL.md" 2>/dev/null | awk '{print $2}' || echo "unknown")
  echo "已检测到已安装版本：v${INSTALLED_VER}，将升级至 v${VERSION}"
fi

echo "📦 安装目标："
echo "  Skill → $SKILL_DIR/SKILL.md"
[ "$WITH_WORKFLOW" = true ] && echo "  Workflow → $WORKFLOW_DIR/effort-routed-task.js（可选）"
echo

mkdir -p "$SKILL_DIR"
fetch_file "SKILL.md" "$SKILL_DIR/SKILL.md"

if [ "$WITH_WORKFLOW" = true ]; then
  mkdir -p "$WORKFLOW_DIR"
  fetch_file "effort-routed-task.js" "$WORKFLOW_DIR/effort-routed-task.js"
  echo
  echo "✅ 安装完成！v${VERSION}（含 Workflow）"
  echo
  echo "Workflow 用法："
  echo "  Workflow({ scriptPath: '$WORKFLOW_DIR/effort-routed-task.js', args: {task: '...'} })"
else
  echo
  echo "✅ 安装完成！v${VERSION}"
  echo
  echo "  如需 Workflow 执行模式：./install.sh --with-workflow"
fi

echo
echo "基础用法（无需 Workflow）："
echo "  通过 Skill 工具调用：skill: 'route-effort'"
echo "  直接咨询：'按 route-effort 规则，此任务用哪个 effort？'"
echo
echo "文档：$REPO_RAW/SKILL.md"
