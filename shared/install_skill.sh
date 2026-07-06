#!/bin/bash
# shared/install_skill.sh
# 单个 skill 安装函数库，由根 install.sh 和各 skill 的 install.sh 调用
#
# 使用方式：
#   source shared/install_skill.sh
#   install_skill <skill_name> [--with-skill-opt] [--with-workflow]

VLONG_SKILLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

_link_or_copy() {
  local src="$1" dest="$2"
  if [ "$IS_LOCAL" = true ]; then
    mkdir -p "$(dirname "$dest")"
    if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$src" ]; then
      echo "  ✓ 已链接（跳过）: $dest"
    else
      [ -e "$dest" ] && mv "$dest" "${dest}.bak.$(date +%Y%m%d)"
      ln -sf "$src" "$dest"
      echo "  ✓ 链接: $dest → $src"
    fi
  else
    mkdir -p "$(dirname "$dest")"
    curl -fsSL "${REPO_RAW}/${1#$VLONG_SKILLS_DIR/}" -o "$dest"
    echo "  ✓ 下载: $dest"
  fi
}

install_skill() {
  local skill_name="$1"; shift
  local with_workflow=false with_skill_opt=false
  for arg in "$@"; do
    case "$arg" in
      --with-workflow)   with_workflow=true ;;
      --with-skill-opt)  with_skill_opt=true ;;
    esac
  done

  local skill_src="$VLONG_SKILLS_DIR/$skill_name"
  local skill_dest="$HOME/.claude/skills/$skill_name"

  echo "→ 安装 $skill_name"

  # 安装 skill 主目录
  _link_or_copy "$skill_src" "$skill_dest"

  # Workflow
  if [ "$with_workflow" = true ] && [ -f "$skill_src/effort-routed-task.js" ]; then
    local wf_dest="$HOME/.claude/workflows/${skill_name}-task.js"
    _link_or_copy "$skill_src/effort-routed-task.js" "$wf_dest"
  fi

  # SkillOpt 数据目录
  if [ "$with_skill_opt" = true ]; then
    mkdir -p "$skill_src/skill-opt"
    echo "  ✓ skill-opt/: $skill_src/skill-opt"
  fi

  local ver
  ver=$(grep '^version:' "$skill_dest/SKILL.md" 2>/dev/null | awk '{print $2}' || echo "?")
  echo "  ✅ $skill_name v${ver} 安装完成"
  echo ""
}
