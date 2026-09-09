@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   全国台风实时监测大屏
echo ============================================
echo.

where python >nul 2>nul
if %errorlevel%==0 (
    set PY=python
) else (
    set PY=py
)

echo [1/2] 拉取最新台风数据 ...
%PY% scripts\fetch_typhoon.py
if %errorlevel% neq 0 (
    echo.
    echo [!] 数据抓取失败，将使用已有数据继续启动
)

echo.
echo [2/2] 启动本地服务 http://localhost:8080
echo       关闭此窗口即可停止服务
echo.

start "" http://localhost:8080
%PY% -m http.server 8080 --bind 0.0.0.0
