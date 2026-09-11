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

echo [1/3] 后台拉取最新台风数据（最小化窗口运行，不影响启动）...
start "台风数据抓取" /min %PY% scripts\fetch_typhoon.py

echo.
echo [2/3] 启动本地服务 http://localhost:8080
echo       关闭此窗口即可停止服务
echo.

REM 延迟2秒后自动打开浏览器（确保服务已启动，避免"拒绝连接"）
start "" /min cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8080"

echo [3/3] 服务启动中，浏览器将在2秒后自动打开...
echo       若未自动打开，请手动访问 http://localhost:8080
echo.

%PY% -m http.server 8080 --bind 0.0.0.0
