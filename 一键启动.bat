@echo off
chcp 65001 >nul
title AutoGLM Web控制台

echo ========================================
echo    AutoGLM Web控制台 启动脚本
echo ========================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.10+
    echo.
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [√] Python已安装
python --version

:: 检查依赖
echo.
echo [*] 检查Python依赖...

python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [!] 正在安装依赖，请稍候...
    pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)

echo [√] 依赖检查完成
echo.

:: 启动服务
echo ========================================
echo    启动Web服务...
echo ========================================
echo.

cd /d "%~dp0"

:: 延迟后打开浏览器
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

echo 浏览器将自动打开...
echo 如果没有自动打开，请手动访问: http://127.0.0.1:5000
echo.
echo 按 Ctrl+C 可停止服务
echo.

python server.py

pause

