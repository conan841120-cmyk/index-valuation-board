#!/usr/bin/env bash
# 本地手动 / 定时触发一次云端估值看板任务。
# 依赖：gh 已登录（token 需含 repo 或 actions:write scope）。
# 用途：作为外部定时器的补充（Mac 睡眠/关机时不可靠，不推荐作为唯一触发方式）。
set -euo pipefail

REPO="conan841120-cmyk/index-valuation-board"
WORKFLOW="daily.yml"

gh workflow run "$WORKFLOW" --repo "$REPO"
echo "已触发。查看状态："
echo "  gh run list --repo $REPO --limit 3"
