#!/bin/bash
# route-effort skill 安装脚本
# 支持两种方式：
#   本地：./install.sh
#   远程：curl -fsSL https://raw.githubusercontent.com/<user>/route-effort/main/install.sh | bash

set -e

REPO_RAW="https://raw.githubusercontent.com/YOUR_USERNAME/route-effort/main"
SKILL_DIR="$HOME/.claude/skills/route-effort"
WORKFLOW_DIR="$HOME/.claude/workflows"

echo "=== Route-Effort Skill 安装程序 ==="

# 检测运行方式（本地 or 远程 curl）
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

echo "📦 安装目标："
echo "  Skill  → $SKILL_DIR/SKILL.md"
echo "  Workflow → $WORKFLOW_DIR/effort-routed-task.js"
echo

mkdir -p "$SKILL_DIR" "$WORKFLOW_DIR"

fetch_file "SKILL.md" "$SKILL_DIR/SKILL.md"
fetch_file "effort-routed-task.js" "$WORKFLOW_DIR/effort-routed-task.js"

echo
echo "✅ 安装完成！"
echo
echo "使用方式："
echo "  Workflow({"
echo "    scriptPath: '$WORKFLOW_DIR/effort-routed-task.js',"
echo "    args: {task: '你的任务描述'}"
echo "  })"
echo
echo "详细文档：$REPO_RAW/README.md"
