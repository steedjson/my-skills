#!/bin/bash
# shared/install_skill.sh
# 单个 skill 安装函数库
# 用法：source shared/install_skill.sh && install_skill <name> [options]
#
# 依赖 install.sh 导出的 REPO_ROOT：一个本地目录（仓库本身，或已经
# clone/tarball 到临时目录的仓库副本）。本文件只做本地文件复制，不发起
# 任何网络请求 —— 避免对每个文件单独 curl 触发 GitHub API 限流。

REPO_ROOT="${REPO_ROOT:?REPO_ROOT must be set by install.sh before sourcing this file}"

install_skill() {
  local skill_name="$1"; shift

  # 防止路径穿越：只允许小写字母、数字和连字符，长度 1-64
  if ! printf '%s' "$skill_name" | grep -qE '^[a-z0-9][a-z0-9-]{0,63}$'; then
    echo "❌ 非法 skill 名称: '$skill_name'（只允许小写字母、数字和连字符）" >&2
    return 1
  fi

  local src="$REPO_ROOT/$skill_name"
  if [ ! -d "$src" ]; then
    echo "❌ 未找到 skill: '$skill_name'（$src 不存在）" >&2
    return 1
  fi

  local with_workflow=false with_skill_opt=false
  for arg in "$@"; do
    case "$arg" in
      --with-workflow)   with_workflow=true ;;
      --with-skill-opt)  with_skill_opt=true ;;
    esac
  done

  local dest="$HOME/.claude/skills/vlong/$skill_name"
  echo "→ 安装 $skill_name"

  mkdir -p "$dest" "$dest/references" "$dest/scripts"

  _cp() { cp "$src/$1" "$dest/$1" && echo "  ↓ $1"; }
  _cp_opt() { [ -f "$src/$1" ] && cp "$src/$1" "$dest/$1" 2>/dev/null || true; }

  _cp "SKILL.md"
  _cp "README.md"
  _cp_opt "CHANGELOG.md"
  _cp_opt "references/sdk-examples.md"

  for f in log_usage.py train_route_effort.py prepare_skillopt_env.py; do
    if [ -f "$src/scripts/$f" ]; then
      cp "$src/scripts/$f" "$dest/scripts/$f" && chmod +x "$dest/scripts/$f"
    fi
  done

  if [ "$with_workflow" = true ]; then
    mkdir -p "$HOME/.claude/workflows"
    cp "$src/effort-routed-task.js" "$HOME/.claude/workflows/vlong-${skill_name}-task.js"
    echo "  ↓ Workflow: vlong-${skill_name}-task.js"
  fi

  if [ "$with_skill_opt" = true ]; then
    mkdir -p "$dest/skill-opt"
    echo "  ✓ skill-opt/: $dest/skill-opt"
  fi

  # 为 Claude Code 技能发现创建命名空间 symlink
  # Claude Code 只扫描 ~/.claude/skills/ 一级子目录，
  # 而 skill 实际在 vlong/<name>/，所以需要 vlong:<name> 的 symlink
  local skill_link="$HOME/.claude/skills/vlong:$skill_name"
  ln -sfn "$dest" "$skill_link"
  echo "  ↔ symlink: ~/.claude/skills/vlong:$skill_name → vlong/$skill_name"

  local ver
  ver=$(grep '^version:' "$dest/SKILL.md" 2>/dev/null | awk '{print $2}' || echo "?")
  echo "  ✅ $skill_name v${ver} 安装完成"
  echo ""
}
