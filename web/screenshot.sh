#!/bin/bash
# 用 Chrome 无头模式给页面截图（用于与作者文章截图并排比对）
# 用法: web/screenshot.sh <html路径> <输出png> [宽] [高]
set -u
HTML="$1"; OUT="$2"; W="${3:-1076}"; H="${4:-560}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE="$(mktemp -d /tmp/chrome-shot-XXXXXX)"
rm -f "$OUT"
"$CHROME" --headless --disable-gpu --no-sandbox --no-first-run --no-default-browser-check \
  --disable-extensions --disable-background-networking --disable-sync \
  --user-data-dir="$PROFILE" --hide-scrollbars \
  --screenshot="$OUT" --window-size="$W,$H" --force-device-scale-factor=2 \
  --virtual-time-budget=6000 "file://$HTML" >/dev/null 2>&1 &
PID=$!
for _ in $(seq 1 40); do
  [ -s "$OUT" ] && break
  sleep 0.5
done
sleep 1
pkill -9 -P "$PID" 2>/dev/null
kill -9 "$PID" 2>/dev/null
rm -rf "$PROFILE"
if [ -s "$OUT" ]; then
  echo "截图完成: $OUT ($(file -b "$OUT" | cut -c1-40))"
else
  echo "截图失败"; exit 1
fi
