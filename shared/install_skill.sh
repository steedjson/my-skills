#!/bin/bash
# shared/install_skill.sh
# 单个 skill 安装函数库
# 用法：source shared/install_skill.sh && install_skill <name> [options]

REPO_RAW="${REPO_RAW:-https://raw.githubusercontent.com/steedjson/my-skills/main}"

install_skill() {
  local skill_name="$1"; shift

  # 防止路径穿越：只允许小写字母、数字和连字符，长度 1-64
  if ! printf '%s' "$skill_name" | grep -qE '^[a-z0-9][a-z0-9-]{0,63}$'; then
    echo "❌ 非法 skill 名称: '$skill_name'（只允许小写字母、数字和连字符）" >&2
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

  _dl() { curl -fsSL "$REPO_RAW/$skill_name/$1" -o "$dest/$1" && echo "  ↓ $1"; }

  _dl "SKILL.md"
  _dl "README.md"
  [ -f "$dest/CHANGELOG.md" ] || curl -fsSL "$REPO_RAW/$skill_name/CHANGELOG.md" -o "$dest/CHANGELOG.md" 2>/dev/null || true
  curl -fsSL "$REPO_RAW/$skill_name/references/sdk-examples.md" -o "$dest/references/sdk-examples.md" 2>/dev/null || true

  for f in log_usage.py train_route_effort.py prepare_skillopt_env.py; do
    curl -fsSL "$REPO_RAW/$skill_name/scripts/$f" -o "$dest/scripts/$f" 2>/dev/null && \
      chmod +x "$dest/scripts/$f" || true
  done

  if [ "$with_workflow" = true ]; then
    mkdir -p "$HOME/.claude/workflows"
    curl -fsSL "$REPO_RAW/$skill_name/effort-routed-task.js" \
      -o "$HOME/.claude/workflows/vlong-${skill_name}-task.js"
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
