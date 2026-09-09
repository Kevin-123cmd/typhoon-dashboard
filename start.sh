#!/usr/bin/env bash
# 全国台风实时监测大屏 —— 一键启动
cd "$(dirname "$0")"

echo "============================================"
echo "  全国台风实时监测大屏"
echo "============================================"
echo

PY=python3
command -v python3 >/dev/null 2>&1 || PY=python

echo "[1/2] 拉取最新台风数据 ..."
"$PY" scripts/fetch_typhoon.py

echo
echo "[2/2] 启动本地服务 http://localhost:8080"
echo "      按 Ctrl+C 停止"
echo

( sleep 1; command -v open >/dev/null && open http://localhost:8080 ) 2>/dev/null &

exec "$PY" -m http.server 8080 --bind 0.0.0.0
