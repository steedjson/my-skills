#!/bin/bash
# route-effort skill 安装脚本 v2.2.0
#
# 安装模式：
#
#   纯 skill 安装（默认）：
#     本地：  ./install.sh
#     远程：  curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort/install.sh | bash
#
#   带训练支持（含 skill-opt 目录）：
#     本地：  ./install.sh --with-skill-opt
#     远程：  curl -fsSL .../install.sh | bash -s -- --with-skill-opt
#
#   额外选项：
#     --with-workflow     同时安装 effort-routed-task.js（Workflow 执行模式）

set -euo pipefail

VERSION="2.2.0"
REPO_RAW="https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort"
SKILL_DIR="$HOME/.claude/skills/route-effort"
WORKFLOW_DIR="$HOME/.claude/workflows"

# 参数解析
WITH_WORKFLOW=false
WITH_SKILL_OPT=false
for arg in "$@"; do
  case "$arg" in
    --with-workflow)   WITH_WORKFLOW=true ;;
    --with-skill-opt)  WITH_SKILL_OPT=true ;;
  esac
done

echo "=== Route-Effort Skill 安装程序 v${VERSION} ==="
echo ""

# ── 检测安装模式（本地 or 远程）──────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-/dev/stdin}")" 2>/dev/null && pwd || echo "")"
IS_LOCAL=false
if [ -n "$SCRIPT_DIR" ] && [ "$SCRIPT_DIR" != "/" ] && [ -f "$SCRIPT_DIR/SKILL.md" ]; then
  IS_LOCAL=true
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." 2>/dev/null && pwd)"
  SKILL_SOURCE="$SCRIPT_DIR"
fi

# ── 本地安装：创建符号链接 ────────────────────────────────────────
if [ "$IS_LOCAL" = true ]; then
  echo "📍 本地安装（符号链接）"

  if [ -L "$SKILL_DIR" ] && [ "$(readlink "$SKILL_DIR")" = "$SKILL_SOURCE" ]; then
    echo "✓ 已是最新链接，跳过"
  elif [ -d "$SKILL_DIR" ] && [ ! -L "$SKILL_DIR" ]; then
    mv "$SKILL_DIR" "${SKILL_DIR}.bak.$(date +%Y%m%d)"
    echo "⚠️  原目录已备份为 ${SKILL_DIR}.bak.$(date +%Y%m%d)"
    mkdir -p "$(dirname "$SKILL_DIR")"
    ln -sf "$SKILL_SOURCE" "$SKILL_DIR"
    echo "✓ ~/.claude/skills/route-effort → $SKILL_SOURCE"
  else
    mkdir -p "$(dirname "$SKILL_DIR")"
    ln -sf "$SKILL_SOURCE" "$SKILL_DIR"
    echo "✓ ~/.claude/skills/route-effort → $SKILL_SOURCE"
  fi

  if [ "$WITH_WORKFLOW" = true ]; then
    mkdir -p "$WORKFLOW_DIR"
    ln -sf "$SKILL_SOURCE/effort-routed-task.js" "$WORKFLOW_DIR/effort-routed-task.js"
    echo "✓ Workflow 已链接"
  fi

  if [ "$WITH_SKILL_OPT" = true ]; then
    mkdir -p "$SKILL_SOURCE/skill-opt"
    echo "✓ skill-opt/ 目录已创建：$SKILL_SOURCE/skill-opt"
  fi

# ── 远程安装：下载文件 ────────────────────────────────────────────
else
  echo "🌐 远程安装（复制文件）"

  mkdir -p "$SKILL_DIR"
  mkdir -p "$SKILL_DIR/references"
  mkdir -p "$SKILL_DIR/scripts"

  fetch_file() {
    echo "  ↓ 下载 $1..."
    curl -fsSL "$REPO_RAW/$1" -o "$2"
  }

  fetch_file "SKILL.md"                       "$SKILL_DIR/SKILL.md"
  fetch_file "README.md"                      "$SKILL_DIR/README.md"
  fetch_file "CHANGELOG.md"                   "$SKILL_DIR/CHANGELOG.md"
  fetch_file "references/sdk-examples.md"     "$SKILL_DIR/references/sdk-examples.md"

  for f in log_usage.py train_route_effort.py prepare_skillopt_env.py; do
    fetch_file "scripts/$f" "$SKILL_DIR/scripts/$f"
    chmod +x "$SKILL_DIR/scripts/$f"
  done

  echo "✓ 文件已安装到 $SKILL_DIR"

  if [ "$WITH_WORKFLOW" = true ]; then
    mkdir -p "$WORKFLOW_DIR"
    fetch_file "effort-routed-task.js" "$WORKFLOW_DIR/effort-routed-task.js"
    echo "✓ Workflow 脚本已安装"
  fi

  if [ "$WITH_SKILL_OPT" = true ]; then
    mkdir -p "$SKILL_DIR/skill-opt"
    echo "✓ skill-opt/ 目录已创建：$SKILL_DIR/skill-opt"
  fi
fi

# ── 安装结果 ──────────────────────────────────────────────────────
INSTALLED_VER=$(grep '^version:' "$SKILL_DIR/SKILL.md" 2>/dev/null | awk '{print $2}' || echo "unknown")
echo ""
echo "✅ 安装完成！v${INSTALLED_VER}"
echo ""
echo "数据目录：$SKILL_DIR"
[ "$WITH_SKILL_OPT" = true ] && echo "训练数据：$SKILL_DIR/skill-opt/"
echo ""
echo "升级方式："
if [ "$IS_LOCAL" = true ]; then
  echo "  cd $PROJECT_ROOT && git pull"
else
  echo "  重新运行安装脚本（同参数）"
fi
