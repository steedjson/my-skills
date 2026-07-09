#!/bin/bash
# vlong skills 安装器
#
# 用法：
#   curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/install.sh | bash
#   curl -fsSL .../install.sh | bash -s -- route-effort
#   curl -fsSL .../install.sh | bash -s -- route-effort --with-skill-opt
#   curl -fsSL .../install.sh | bash -s -- route-effort --with-skill-opt --with-workflow
#   curl -fsSL .../install.sh | bash -s -- --all --with-skill-opt
#
# 无论开发者在仓库内直接运行，还是用户通过 curl|bash 安装，
# 最终都统一为「本地目录」再执行安装逻辑：
#   - 仓库内运行：直接用当前目录，零网络请求
#   - curl|bash 运行：一次性把仓库 clone/下载到临时目录，用完即删
# 这样避免了逐文件 curl 触发 GitHub API 限流（429），
# 也让 shared/install_skill.sh 只需要处理本地文件复制，不必区分 curl/cp。

set -euo pipefail

REPO_URL="https://github.com/steedjson/my-skills.git"
TARBALL_URL="https://codeload.github.com/steedjson/my-skills/tar.gz/refs/heads/main"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/shared/install_skill.sh" ] && [ -d "$SCRIPT_DIR/.git" ]; then
  # 开发者模式：脚本本身在仓库内运行，直接用当前目录，不下载
  REPO_ROOT="$SCRIPT_DIR"
  echo "🔧 本地模式：使用 $REPO_ROOT"
else
  # 用户安装模式：把仓库一次性 materialize 到临时目录
  TMP_REPO=$(mktemp -d)
  trap 'rm -rf "${TMP_REPO:-}"' EXIT

  CLONE_OK=false
  if command -v git >/dev/null 2>&1; then
    echo "📦 克隆仓库到临时目录…"
    if git clone --depth 1 -q "$REPO_URL" "$TMP_REPO" 2>/dev/null; then
      CLONE_OK=true
    else
      # git clone 失败（网络限流/离线/防火墙等）：清理残留，回退到 tarball
      echo "⚠️  git clone 失败，回退到压缩包下载…" >&2
      rm -rf "$TMP_REPO"
      mkdir -p "$TMP_REPO"
    fi
  fi

  if [ "$CLONE_OK" = false ]; then
    echo "📦 下载仓库压缩包到临时目录…"
    curl -fsSL "$TARBALL_URL" | tar -xz -C "$TMP_REPO" --strip-components=1
  fi

  REPO_ROOT="$TMP_REPO"
fi
export REPO_ROOT

# 加载共享安装函数（纯本地文件操作，无网络请求）
source "$REPO_ROOT/shared/install_skill.sh"

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

# 默认安装全部：优先用 jq 正确解析 JSON，没有 jq 再退回 grep/sed
if [ "$INSTALL_ALL" = true ] || [ ${#SKILLS_TO_INSTALL[@]} -eq 0 ]; then
  if command -v jq >/dev/null 2>&1; then
    mapfile -t SKILLS_TO_INSTALL < <(jq -r '.skills[].name' "$REPO_ROOT/skills.json")
  else
    SKILLS_TO_INSTALL=($(grep '"name"' "$REPO_ROOT/skills.json" | grep -v '"vlong"' | sed 's/.*"name": *"\([^"]*\)".*/\1/'))
  fi
fi

# 标题
echo "╔══════════════════════════════╗"
echo "║        vlong skills          ║"
echo "╚══════════════════════════════╝"
echo ""
echo "安装：${SKILLS_TO_INSTALL[*]}"
echo ""

for skill in "${SKILLS_TO_INSTALL[@]}"; do
  install_skill "$skill" "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
done

echo "完成！升级：重新运行安装命令"
